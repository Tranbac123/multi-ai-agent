"""Resilient adapter with circuit breaker, retry, and saga patterns."""

import asyncio
import time
import random
import uuid
from typing import Dict, List, Any, Optional, Callable, TypeVar, Generic
from enum import Enum
import structlog
import redis.asyncio as redis

logger = structlog.get_logger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class RetryStrategy(Enum):
    """Retry strategies."""
    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    LINEAR = "linear"


class ResilientAdapter(Generic[T]):
    """Resilient adapter with circuit breaker, retry, and saga patterns."""
    
    def __init__(
        self,
        name: str,
        redis_client: redis.Redis,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 60.0,
        timeout: float = 30.0,
        bulkhead_size: int = 10
    ):
        self.name = name
        self.redis = redis_client
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_strategy = retry_strategy
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout
        self.timeout = timeout
        self.bulkhead_size = bulkhead_size
        
        # Circuit breaker state
        self.circuit_state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        
        # Bulkhead semaphore
        self.bulkhead_semaphore = asyncio.Semaphore(bulkhead_size)
        
        # Saga state
        self.saga_operations = []
    
    async def execute(
        self,
        operation: Callable[..., T],
        *args,
        idempotency_key: Optional[str] = None,
        compensation: Optional[Callable[..., Any]] = None,
        **kwargs
    ) -> T:
        """Execute operation with resilience patterns."""
        operation_id = str(uuid.uuid4())
        
        try:
            # Check circuit breaker
            if not await self._check_circuit_breaker():
                raise CircuitBreakerOpenError(f"Circuit breaker is open for {self.name}")
            
            # Acquire bulkhead semaphore
            async with self.bulkhead_semaphore:
                # Check idempotency
                if idempotency_key and await self._is_operation_completed(idempotency_key):
                    return await self._get_cached_result(idempotency_key)
                
                # Execute with retry
                result = await self._execute_with_retry(
                    operation, operation_id, *args, **kwargs
                )
                
                # Cache result for idempotency
                if idempotency_key:
                    await self._cache_result(idempotency_key, result)
                
                # Record success
                await self._record_success()
                
                # Add to saga if compensation provided
                if compensation:
                    self.saga_operations.append({
                        'operation_id': operation_id,
                        'operation': operation,
                        'compensation': compensation,
                        'args': args,
                        'kwargs': kwargs,
                        'result': result
                    })
                
                return result
                
        except Exception as e:
            # Record failure
            await self._record_failure()
            logger.error(
                "Operation failed",
                operation_id=operation_id,
                adapter_name=self.name,
                error=str(e)
            )
            raise
    
    async def _execute_with_retry(
        self,
        operation: Callable[..., T],
        operation_id: str,
        *args,
        **kwargs
    ) -> T:
        """Execute operation with retry logic."""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # Execute with timeout
                result = await asyncio.wait_for(
                    operation(*args, **kwargs),
                    timeout=self.timeout
                )
                
                if attempt > 0:
                    logger.info(
                        "Operation succeeded after retry",
                        operation_id=operation_id,
                        attempt=attempt,
                        adapter_name=self.name
                    )
                
                return result
                
            except asyncio.TimeoutError as e:
                last_exception = e
                logger.warning(
                    "Operation timeout",
                    operation_id=operation_id,
                    attempt=attempt,
                    adapter_name=self.name
                )
                
            except Exception as e:
                last_exception = e
                logger.warning(
                    "Operation failed",
                    operation_id=operation_id,
                    attempt=attempt,
                    error=str(e),
                    adapter_name=self.name
                )
            
            # Don't retry on last attempt
            if attempt < self.max_retries:
                delay = self._calculate_retry_delay(attempt)
                await asyncio.sleep(delay)
        
        # All retries failed
        raise last_exception
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay based on strategy."""
        if self.retry_strategy == RetryStrategy.FIXED:
            return self.retry_delay
        elif self.retry_strategy == RetryStrategy.EXPONENTIAL:
            return self.retry_delay * (2 ** attempt) + random.uniform(0, 1)
        elif self.retry_strategy == RetryStrategy.LINEAR:
            return self.retry_delay * (attempt + 1)
        else:
            return self.retry_delay
    
    async def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker allows execution."""
        if self.circuit_state == CircuitState.CLOSED:
            return True
        elif self.circuit_state == CircuitState.OPEN:
            # Check if timeout has passed
            if time.time() - self.last_failure_time > self.circuit_breaker_timeout:
                self.circuit_state = CircuitState.HALF_OPEN
                return True
            return False
        elif self.circuit_state == CircuitState.HALF_OPEN:
            return True
        else:
            return False
    
    async def _record_success(self) -> None:
        """Record successful operation."""
        self.failure_count = 0
        if self.circuit_state == CircuitState.HALF_OPEN:
            self.circuit_state = CircuitState.CLOSED
            logger.info(f"Circuit breaker closed for {self.name}")
    
    async def _record_failure(self) -> None:
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.circuit_breaker_threshold:
            self.circuit_state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker opened for {self.name}",
                failure_count=self.failure_count
            )
    
    async def _is_operation_completed(self, idempotency_key: str) -> bool:
        """Check if operation was already completed."""
        try:
            result_key = f"idempotency:{self.name}:{idempotency_key}"
            return await self.redis.exists(result_key)
        except Exception as e:
            logger.error("Failed to check idempotency", error=str(e))
            return False
    
    async def _get_cached_result(self, idempotency_key: str) -> T:
        """Get cached result for idempotent operation."""
        try:
            result_key = f"idempotency:{self.name}:{idempotency_key}"
            result_data = await self.redis.get(result_key)
            if result_data:
                import json
                return json.loads(result_data)
            else:
                raise ValueError("Cached result not found")
        except Exception as e:
            logger.error("Failed to get cached result", error=str(e))
            raise
    
    async def _cache_result(self, idempotency_key: str, result: T) -> None:
        """Cache result for idempotent operation."""
        try:
            result_key = f"idempotency:{self.name}:{idempotency_key}"
            import json
            await self.redis.setex(
                result_key,
                3600,  # 1 hour TTL
                json.dumps(result, default=str)
            )
        except Exception as e:
            logger.error("Failed to cache result", error=str(e))
    
    async def execute_saga(self) -> List[Any]:
        """Execute saga with compensation on failure."""
        results = []
        
        try:
            # Execute all operations in order
            for operation_data in self.saga_operations:
                result = await operation_data['operation'](
                    *operation_data['args'],
                    **operation_data['kwargs']
                )
                results.append(result)
            
            # Clear saga operations on success
            self.saga_operations.clear()
            
            logger.info(
                "Saga executed successfully",
                adapter_name=self.name,
                operations_count=len(results)
            )
            
            return results
            
        except Exception as e:
            logger.error(
                "Saga execution failed, starting compensation",
                error=str(e),
                adapter_name=self.name
            )
            
            # Execute compensation in reverse order
            await self._execute_compensation()
            
            raise
    
    async def _execute_compensation(self) -> None:
        """Execute compensation for failed saga."""
        # Execute compensation in reverse order
        for operation_data in reversed(self.saga_operations):
            try:
                await operation_data['compensation'](
                    *operation_data['args'],
                    **operation_data['kwargs']
                )
                logger.info(
                    "Compensation executed",
                    operation_id=operation_data['operation_id'],
                    adapter_name=self.name
                )
            except Exception as e:
                logger.error(
                    "Compensation failed",
                    operation_id=operation_data['operation_id'],
                    error=str(e),
                    adapter_name=self.name
                )
        
        # Clear saga operations
        self.saga_operations.clear()
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get adapter statistics."""
        return {
            'name': self.name,
            'circuit_state': self.circuit_state.value,
            'failure_count': self.failure_count,
            'last_failure_time': self.last_failure_time,
            'bulkhead_available': self.bulkhead_semaphore._value,
            'bulkhead_size': self.bulkhead_size,
            'saga_operations_count': len(self.saga_operations),
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'retry_strategy': self.retry_strategy.value,
            'timeout': self.timeout
        }
    
    async def reset_circuit_breaker(self) -> None:
        """Reset circuit breaker to closed state."""
        self.circuit_state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        logger.info(f"Circuit breaker reset for {self.name}")


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class BulkheadFullError(Exception):
    """Exception raised when bulkhead is full."""
    pass


class TimeoutError(Exception):
    """Exception raised when operation times out."""
    pass