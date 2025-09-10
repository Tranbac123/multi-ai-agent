"""Base adapter with reliability enforcement patterns."""

import asyncio
import time
import uuid
from typing import Dict, List, Any, Optional, Callable, TypeVar, Generic
from dataclasses import dataclass
from enum import Enum
import structlog
import redis.asyncio as redis

logger = structlog.get_logger(__name__)

T = TypeVar('T')


class AdapterStatus(Enum):
    """Adapter status."""
    CLOSED = "closed"
    HALF_OPEN = "half_open"
    OPEN = "open"


@dataclass
class AdapterConfig:
    """Adapter configuration."""
    timeout_ms: int = 30000
    max_retries: int = 3
    retry_delay_ms: int = 1000
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout_ms: int = 60000
    bulkhead_max_concurrent: int = 10
    idempotency_ttl_seconds: int = 3600


@dataclass
class AdapterMetrics:
    """Adapter metrics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeout_requests: int = 0
    circuit_breaker_opens: int = 0
    retry_attempts: int = 0
    bulkhead_rejections: int = 0


class BaseAdapter(Generic[T]):
    """Base adapter with reliability enforcement patterns."""
    
    def __init__(
        self,
        name: str,
        config: AdapterConfig,
        redis_client: redis.Redis
    ):
        self.name = name
        self.config = config
        self.redis = redis_client
        self.metrics = AdapterMetrics()
        self.circuit_breaker_state = AdapterStatus.CLOSED
        self.circuit_breaker_failures = 0
        self.circuit_breaker_last_failure = 0
        self.bulkhead_semaphore = asyncio.Semaphore(config.bulkhead_max_concurrent)
    
    async def call(
        self,
        operation: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """Call operation with reliability enforcement."""
        try:
            # Generate idempotency key
            idempotency_key = self._generate_idempotency_key(operation, args, kwargs)
            
            # Check idempotency
            cached_result = await self._check_idempotency(idempotency_key)
            if cached_result is not None:
                logger.info("Idempotent call result returned", adapter=self.name, key=idempotency_key)
                return cached_result
            
            # Check circuit breaker
            if not await self._check_circuit_breaker():
                raise Exception(f"Circuit breaker is open for adapter {self.name}")
            
            # Write-ahead event: tool.call.requested
            await self._write_ahead_event("requested", idempotency_key, operation, args, kwargs)
            
            # Acquire bulkhead semaphore
            async with self.bulkhead_semaphore:
                # Execute with timeout and retries
                result = await self._execute_with_reliability(operation, *args, **kwargs)
                
                # Write-ahead event: tool.call.succeeded
                await self._write_ahead_event("succeeded", idempotency_key, operation, args, kwargs, result)
                
                # Store result for idempotency
                await self._store_idempotency_result(idempotency_key, result)
                
                # Update metrics
                self.metrics.total_requests += 1
                self.metrics.successful_requests += 1
                
                # Reset circuit breaker on success
                await self._reset_circuit_breaker()
                
                return result
                
        except Exception as e:
            # Write-ahead event: tool.call.failed
            await self._write_ahead_event("failed", idempotency_key, operation, args, kwargs, error=str(e))
            
            # Update metrics
            self.metrics.total_requests += 1
            self.metrics.failed_requests += 1
            
            # Update circuit breaker
            await self._update_circuit_breaker_failure()
            
            logger.error("Adapter call failed", adapter=self.name, error=str(e))
            raise
    
    async def _execute_with_reliability(
        self,
        operation: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """Execute operation with timeout and retries."""
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                # Execute with timeout
                result = await asyncio.wait_for(
                    operation(*args, **kwargs),
                    timeout=self.config.timeout_ms / 1000.0
                )
                
                # Log retry attempts
                if attempt > 0:
                    logger.info("Operation succeeded after retry", adapter=self.name, attempt=attempt)
                
                return result
                
            except asyncio.TimeoutError:
                last_exception = asyncio.TimeoutError(f"Operation timed out after {self.config.timeout_ms}ms")
                self.metrics.timeout_requests += 1
                
                if attempt < self.config.max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning("Operation timed out, retrying", adapter=self.name, attempt=attempt, delay=delay)
                    await asyncio.sleep(delay)
                    self.metrics.retry_attempts += 1
                else:
                    logger.error("Operation timed out after all retries", adapter=self.name, attempts=attempt)
                    
            except Exception as e:
                last_exception = e
                
                if attempt < self.config.max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning("Operation failed, retrying", adapter=self.name, attempt=attempt, delay=delay, error=str(e))
                    await asyncio.sleep(delay)
                    self.metrics.retry_attempts += 1
                else:
                    logger.error("Operation failed after all retries", adapter=self.name, attempts=attempt, error=str(e))
        
        # All retries exhausted
        raise last_exception
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff and jitter."""
        base_delay = self.config.retry_delay_ms / 1000.0
        exponential_delay = base_delay * (2 ** attempt)
        
        # Add jitter (±25%)
        import random
        jitter = random.uniform(0.75, 1.25)
        
        return exponential_delay * jitter
    
    async def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker allows the call."""
        if self.circuit_breaker_state == AdapterStatus.CLOSED:
            return True
        
        if self.circuit_breaker_state == AdapterStatus.OPEN:
            # Check if timeout has passed
            current_time = time.time()
            if current_time - self.circuit_breaker_last_failure > self.config.circuit_breaker_timeout_ms / 1000.0:
                # Move to half-open
                self.circuit_breaker_state = AdapterStatus.HALF_OPEN
                logger.info("Circuit breaker moved to half-open", adapter=self.name)
                return True
            return False
        
        if self.circuit_breaker_state == AdapterStatus.HALF_OPEN:
            return True
        
        return False
    
    async def _update_circuit_breaker_failure(self) -> None:
        """Update circuit breaker on failure."""
        self.circuit_breaker_failures += 1
        self.circuit_breaker_last_failure = time.time()
        
        if self.circuit_breaker_failures >= self.config.circuit_breaker_threshold:
            self.circuit_breaker_state = AdapterStatus.OPEN
            self.metrics.circuit_breaker_opens += 1
            logger.warning("Circuit breaker opened", adapter=self.name, failures=self.circuit_breaker_failures)
    
    async def _reset_circuit_breaker(self) -> None:
        """Reset circuit breaker on success."""
        if self.circuit_breaker_state == AdapterStatus.HALF_OPEN:
            self.circuit_breaker_state = AdapterStatus.CLOSED
            self.circuit_breaker_failures = 0
            logger.info("Circuit breaker closed", adapter=self.name)
    
    def _generate_idempotency_key(
        self,
        operation: Callable[..., T],
        args: tuple,
        kwargs: dict
    ) -> str:
        """Generate idempotency key for operation."""
        # Create a hash of the operation and parameters
        import hashlib
        import json
        
        operation_name = operation.__name__ if hasattr(operation, '__name__') else str(operation)
        params = {
            'operation': operation_name,
            'args': args,
            'kwargs': kwargs
        }
        
        params_str = json.dumps(params, sort_keys=True, default=str)
        hash_obj = hashlib.md5(params_str.encode())
        
        return f"idempotency:{self.name}:{hash_obj.hexdigest()}"
    
    async def _check_idempotency(self, key: str) -> Optional[T]:
        """Check if result exists in idempotency cache."""
        try:
            cached_data = await self.redis.get(key)
            if cached_data:
                import json
                return json.loads(cached_data)
            return None
        except Exception as e:
            logger.error("Failed to check idempotency", adapter=self.name, key=key, error=str(e))
            return None
    
    async def _store_idempotency_result(self, key: str, result: T) -> None:
        """Store result in idempotency cache."""
        try:
            import json
            result_json = json.dumps(result, default=str)
            await self.redis.setex(key, self.config.idempotency_ttl_seconds, result_json)
        except Exception as e:
            logger.error("Failed to store idempotency result", adapter=self.name, key=key, error=str(e))
    
    async def _write_ahead_event(
        self,
        event_type: str,
        idempotency_key: str,
        operation: Callable[..., T],
        args: tuple,
        kwargs: dict,
        result: Optional[T] = None,
        error: Optional[str] = None
    ) -> None:
        """Write ahead event for operation."""
        try:
            import json
            import time
            
            event = {
                'event_type': f'tool.call.{event_type}',
                'adapter_name': self.name,
                'idempotency_key': idempotency_key,
                'operation_name': operation.__name__ if hasattr(operation, '__name__') else str(operation),
                'args': args,
                'kwargs': kwargs,
                'timestamp': time.time(),
                'result': result,
                'error': error
            }
            
            event_key = f"write_ahead_event:{idempotency_key}:{event_type}"
            event_json = json.dumps(event, default=str)
            
            await self.redis.setex(event_key, self.config.idempotency_ttl_seconds, event_json)
            
            logger.info("Write-ahead event recorded", adapter=self.name, event_type=event_type, key=idempotency_key)
            
        except Exception as e:
            logger.error("Failed to write ahead event", adapter=self.name, event_type=event_type, error=str(e))
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get adapter metrics."""
        return {
            'name': self.name,
            'total_requests': self.metrics.total_requests,
            'successful_requests': self.metrics.successful_requests,
            'failed_requests': self.metrics.failed_requests,
            'timeout_requests': self.metrics.timeout_requests,
            'circuit_breaker_opens': self.metrics.circuit_breaker_opens,
            'retry_attempts': self.metrics.retry_attempts,
            'bulkhead_rejections': self.metrics.bulkhead_rejections,
            'circuit_breaker_state': self.circuit_breaker_state.value,
            'circuit_breaker_failures': self.circuit_breaker_failures,
            'success_rate': (
                self.metrics.successful_requests / self.metrics.total_requests
                if self.metrics.total_requests > 0 else 0
            )
        }
    
    async def reset_metrics(self) -> None:
        """Reset adapter metrics."""
        self.metrics = AdapterMetrics()
        self.circuit_breaker_state = AdapterStatus.CLOSED
        self.circuit_breaker_failures = 0
        self.circuit_breaker_last_failure = 0
        logger.info("Adapter metrics reset", adapter=self.name)
