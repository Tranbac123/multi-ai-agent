"""
Base Tool Adapter with Reliability Patterns

Implements comprehensive reliability patterns including timeouts, retries,
circuit-breaker, bulkhead, idempotency, and write-ahead logging.
"""

import asyncio
import time
import uuid
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable, Awaitable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import structlog
import hashlib
from datetime import datetime, timedelta

logger = structlog.get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Circuit is open, failing fast
    HALF_OPEN = "half_open"  # Testing if service recovered


class RetryStrategy(Enum):
    """Retry strategies."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"


@dataclass
class RetryConfig:
    """Retry configuration."""
    
    max_attempts: int = 3
    base_delay_ms: int = 100
    max_delay_ms: int = 5000
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    jitter: bool = True
    backoff_multiplier: float = 2.0


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout_ms: int = 60000  # 1 minute
    half_open_max_calls: int = 3


@dataclass
class BulkheadConfig:
    """Bulkhead configuration."""
    
    max_concurrent_calls: int = 10
    max_wait_time_ms: int = 5000


@dataclass
class TimeoutConfig:
    """Timeout configuration."""
    
    connect_timeout_ms: int = 5000
    read_timeout_ms: int = 30000
    total_timeout_ms: int = 60000


@dataclass
class WriteAheadLog:
    """Write-ahead log entry."""
    
    id: str
    tool_id: str
    operation: str
    parameters: Dict[str, Any]
    timestamp: datetime
    status: str  # requested, succeeded, failed
    result: Optional[Any] = None
    error: Optional[str] = None


class CircuitBreaker:
    """Circuit breaker implementation."""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_calls = 0
        
        logger.info("Circuit breaker initialized", 
                   failure_threshold=config.failure_threshold,
                   success_threshold=config.success_threshold)
    
    async def call(self, func: Callable[[], Awaitable[Any]]) -> Any:
        """Execute function with circuit breaker protection."""
        
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                logger.info("Circuit breaker entering half-open state")
            else:
                raise Exception("Circuit breaker is OPEN")
        
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.config.half_open_max_calls:
                raise Exception("Circuit breaker half-open call limit exceeded")
            self.half_open_calls += 1
        
        try:
            result = await func()
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt reset."""
        if self.last_failure_time is None:
            return True
        
        elapsed_ms = (datetime.now() - self.last_failure_time).total_seconds() * 1000
        return elapsed_ms >= self.config.timeout_ms
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.success_count = 0
                logger.info("Circuit breaker reset to CLOSED state")
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning("Circuit breaker returned to OPEN state from half-open")
        elif self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error("Circuit breaker opened due to failure threshold", 
                        failure_count=self.failure_count)
    
    def get_state(self) -> Dict[str, Any]:
        """Get circuit breaker state."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "half_open_calls": self.half_open_calls
        }


class Bulkhead:
    """Bulkhead implementation for resource isolation."""
    
    def __init__(self, config: BulkheadConfig):
        self.config = config
        self.semaphore = asyncio.Semaphore(config.max_concurrent_calls)
        self.active_calls = 0
        self.waiting_calls = 0
        self.total_calls = 0
        self.rejected_calls = 0
        
        logger.info("Bulkhead initialized", 
                   max_concurrent_calls=config.max_concurrent_calls,
                   max_wait_time_ms=config.max_wait_time_ms)
    
    async def call(self, func: Callable[[], Awaitable[Any]]) -> Any:
        """Execute function with bulkhead protection."""
        
        self.total_calls += 1
        
        try:
            # Try to acquire semaphore with timeout
            await asyncio.wait_for(
                self.semaphore.acquire(),
                timeout=self.config.max_wait_time_ms / 1000.0
            )
            
            self.active_calls += 1
            
            try:
                result = await func()
                return result
            finally:
                self.active_calls -= 1
                self.semaphore.release()
                
        except asyncio.TimeoutError:
            self.rejected_calls += 1
            logger.warning("Bulkhead call rejected due to timeout", 
                          active_calls=self.active_calls,
                          max_concurrent=self.config.max_concurrent_calls)
            raise Exception("Bulkhead timeout - too many concurrent calls")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get bulkhead metrics."""
        return {
            "active_calls": self.active_calls,
            "waiting_calls": self.waiting_calls,
            "total_calls": self.total_calls,
            "rejected_calls": self.rejected_calls,
            "max_concurrent_calls": self.config.max_concurrent_calls,
            "utilization": self.active_calls / self.config.max_concurrent_calls
        }


class RetryManager:
    """Retry manager with exponential backoff and jitter."""
    
    def __init__(self, config: RetryConfig):
        self.config = config
        self.total_retries = 0
        self.successful_retries = 0
        
        logger.info("Retry manager initialized", 
                   max_attempts=config.max_attempts,
                   strategy=config.strategy.value)
    
    async def call_with_retry(
        self, 
        func: Callable[[], Awaitable[Any]],
        is_retryable: Optional[Callable[[Exception], bool]] = None
    ) -> Any:
        """Execute function with retry logic."""
        
        last_exception = None
        
        for attempt in range(self.config.max_attempts):
            try:
                result = await func()
                
                if attempt > 0:
                    self.successful_retries += 1
                    logger.info("Retry succeeded", attempt=attempt + 1)
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Check if error is retryable
                if is_retryable and not is_retryable(e):
                    logger.info("Non-retryable error encountered", error=str(e))
                    raise
                
                # Check if this was the last attempt
                if attempt == self.config.max_attempts - 1:
                    self.total_retries += attempt
                    logger.error("All retry attempts exhausted", 
                               attempts=self.config.max_attempts,
                               error=str(e))
                    raise
                
                # Calculate delay for next attempt
                delay_ms = self._calculate_delay(attempt)
                
                logger.warning("Retry attempt failed, retrying", 
                             attempt=attempt + 1,
                             max_attempts=self.config.max_attempts,
                             delay_ms=delay_ms,
                             error=str(e))
                
                await asyncio.sleep(delay_ms / 1000.0)
        
        # This should never be reached, but just in case
        raise last_exception or Exception("Retry failed")
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt."""
        
        if self.config.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.config.base_delay_ms
        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.base_delay_ms * (attempt + 1)
        else:  # EXPONENTIAL_BACKOFF
            delay = self.config.base_delay_ms * (self.config.backoff_multiplier ** attempt)
        
        # Apply maximum delay limit
        delay = min(delay, self.config.max_delay_ms)
        
        # Add jitter if enabled
        if self.config.jitter:
            import random
            jitter_factor = random.uniform(0.5, 1.5)
            delay *= jitter_factor
        
        return delay
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get retry metrics."""
        return {
            "total_retries": self.total_retries,
            "successful_retries": self.successful_retries,
            "retry_success_rate": self.successful_retries / max(1, self.total_retries),
            "config": {
                "max_attempts": self.config.max_attempts,
                "base_delay_ms": self.config.base_delay_ms,
                "strategy": self.config.strategy.value
            }
        }


class IdempotencyManager:
    """Idempotency manager for safe retries."""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.local_cache: Dict[str, Any] = {}
        self.cache_ttl = 3600  # 1 hour
        
        logger.info("Idempotency manager initialized")
    
    def generate_key(self, tool_id: str, parameters: Dict[str, Any]) -> str:
        """Generate idempotency key from tool and parameters."""
        # Sort parameters for consistent hashing
        sorted_params = sorted(parameters.items())
        param_str = str(sorted_params)
        
        # Create hash
        key_data = f"{tool_id}:{param_str}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def get_result(self, key: str) -> Optional[Any]:
        """Get cached result for idempotency key."""
        
        # Try local cache first
        if key in self.local_cache:
            return self.local_cache[key]
        
        # Try Redis if available
        if self.redis_client:
            try:
                result = await self.redis_client.get(f"idempotency:{key}")
                if result:
                    import json
                    return json.loads(result)
            except Exception as e:
                logger.warning("Failed to get idempotency key from Redis", 
                             key=key, error=str(e))
        
        return None
    
    async def store_result(self, key: str, result: Any):
        """Store result for idempotency key."""
        
        # Store in local cache
        self.local_cache[key] = result
        
        # Store in Redis if available
        if self.redis_client:
            try:
                import json
                await self.redis_client.setex(
                    f"idempotency:{key}",
                    self.cache_ttl,
                    json.dumps(result)
                )
            except Exception as e:
                logger.warning("Failed to store idempotency key in Redis", 
                             key=key, error=str(e))


class WriteAheadLogger:
    """Write-ahead logger for tool operations."""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.local_log: List[WriteAheadLog] = []
        
        logger.info("Write-ahead logger initialized")
    
    async def log_request(self, tool_id: str, operation: str, parameters: Dict[str, Any]) -> str:
        """Log tool request."""
        
        log_id = str(uuid.uuid4())
        log_entry = WriteAheadLog(
            id=log_id,
            tool_id=tool_id,
            operation=operation,
            parameters=parameters,
            timestamp=datetime.now(),
            status="requested"
        )
        
        # Store locally
        self.local_log.append(log_entry)
        
        # Store in Redis if available
        if self.redis_client:
            try:
                import json
                await self.redis_client.setex(
                    f"wal:{log_id}",
                    3600,  # 1 hour TTL
                    json.dumps(log_entry.__dict__, default=str)
                )
            except Exception as e:
                logger.warning("Failed to store WAL entry in Redis", 
                             log_id=log_id, error=str(e))
        
        logger.info("Tool request logged", 
                   log_id=log_id,
                   tool_id=tool_id,
                   operation=operation)
        
        return log_id
    
    async def log_success(self, log_id: str, result: Any):
        """Log successful tool execution."""
        
        # Update local log
        for entry in self.local_log:
            if entry.id == log_id:
                entry.status = "succeeded"
                entry.result = result
                break
        
        # Update Redis if available
        if self.redis_client:
            try:
                entry = next((e for e in self.local_log if e.id == log_id), None)
                if entry:
                    import json
                    await self.redis_client.setex(
                        f"wal:{log_id}",
                        3600,
                        json.dumps(entry.__dict__, default=str)
                    )
            except Exception as e:
                logger.warning("Failed to update WAL entry in Redis", 
                             log_id=log_id, error=str(e))
        
        logger.info("Tool success logged", log_id=log_id)
    
    async def log_failure(self, log_id: str, error: str):
        """Log failed tool execution."""
        
        # Update local log
        for entry in self.local_log:
            if entry.id == log_id:
                entry.status = "failed"
                entry.error = error
                break
        
        # Update Redis if available
        if self.redis_client:
            try:
                entry = next((e for e in self.local_log if e.id == log_id), None)
                if entry:
                    import json
                    await self.redis_client.setex(
                        f"wal:{log_id}",
                        3600,
                        json.dumps(entry.__dict__, default=str)
                    )
            except Exception as e:
                logger.warning("Failed to update WAL entry in Redis", 
                             log_id=log_id, error=str(e))
        
        logger.error("Tool failure logged", log_id=log_id, error=error)


class BaseToolAdapter(ABC):
    """Base tool adapter with comprehensive reliability patterns."""
    
    def __init__(
        self,
        tool_id: str,
        retry_config: Optional[RetryConfig] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
        bulkhead_config: Optional[BulkheadConfig] = None,
        timeout_config: Optional[TimeoutConfig] = None,
        redis_client=None
    ):
        self.tool_id = tool_id
        
        # Initialize reliability components
        self.retry_config = retry_config or RetryConfig()
        self.circuit_breaker_config = circuit_breaker_config or CircuitBreakerConfig()
        self.bulkhead_config = bulkhead_config or BulkheadConfig()
        self.timeout_config = timeout_config or TimeoutConfig()
        
        self.circuit_breaker = CircuitBreaker(self.circuit_breaker_config)
        self.bulkhead = Bulkhead(self.bulkhead_config)
        self.retry_manager = RetryManager(self.retry_config)
        self.idempotency_manager = IdempotencyManager(redis_client)
        self.write_ahead_logger = WriteAheadLogger(redis_client)
        
        # Metrics
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        
        logger.info("Base tool adapter initialized", tool_id=tool_id)
    
    @abstractmethod
    async def _execute_tool(self, parameters: Dict[str, Any]) -> Any:
        """Execute the actual tool logic. Must be implemented by subclasses."""
        pass
    
    async def compensate(self, parameters: Dict[str, Any], result: Any) -> bool:
        """Compensate for tool side effects. Override in subclasses if needed."""
        logger.info("No compensation needed", tool_id=self.tool_id)
        return True
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if an error is retryable. Override in subclasses if needed."""
        # Default: retry on network/timeout errors, don't retry on validation errors
        error_str = str(error).lower()
        retryable_patterns = [
            "timeout", "connection", "network", "temporary", "unavailable",
            "rate limit", "throttle", "service unavailable"
        ]
        
        return any(pattern in error_str for pattern in retryable_patterns)
    
    async def execute(
        self, 
        parameters: Dict[str, Any],
        idempotency_key: Optional[str] = None
    ) -> Any:
        """Execute tool with comprehensive reliability patterns."""
        
        self.total_calls += 1
        start_time = time.time()
        
        # Generate idempotency key if not provided
        if not idempotency_key:
            idempotency_key = self.idempotency_manager.generate_key(self.tool_id, parameters)
        
        # Check idempotency
        cached_result = await self.idempotency_manager.get_result(idempotency_key)
        if cached_result is not None:
            logger.info("Returning cached result for idempotency", 
                       tool_id=self.tool_id,
                       idempotency_key=idempotency_key)
            return cached_result
        
        # Log request to write-ahead log
        wal_id = await self.write_ahead_logger.log_request(
            self.tool_id, "execute", parameters
        )
        
        try:
            # Execute with all reliability patterns
            result = await self._execute_with_reliability(parameters)
            
            # Log success
            await self.write_ahead_logger.log_success(wal_id, result)
            await self.idempotency_manager.store_result(idempotency_key, result)
            
            self.successful_calls += 1
            
            execution_time_ms = (time.time() - start_time) * 1000
            logger.info("Tool execution successful", 
                       tool_id=self.tool_id,
                       execution_time_ms=execution_time_ms)
            
            return result
            
        except Exception as e:
            # Log failure
            await self.write_ahead_logger.log_failure(wal_id, str(e))
            
            self.failed_calls += 1
            
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error("Tool execution failed", 
                        tool_id=self.tool_id,
                        execution_time_ms=execution_time_ms,
                        error=str(e))
            
            raise
    
    async def _execute_with_reliability(self, parameters: Dict[str, Any]) -> Any:
        """Execute tool with all reliability patterns applied."""
        
        async def tool_call():
            # Apply timeout
            return await asyncio.wait_for(
                self.bulkhead.call(
                    lambda: self.circuit_breaker.call(
                        lambda: self.retry_manager.call_with_retry(
                            lambda: self._execute_tool(parameters),
                            self._is_retryable_error
                        )
                    )
                ),
                timeout=self.timeout_config.total_timeout_ms / 1000.0
            )
        
        return await tool_call()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive tool adapter metrics."""
        return {
            "tool_id": self.tool_id,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": self.successful_calls / max(1, self.total_calls),
            "circuit_breaker": self.circuit_breaker.get_state(),
            "bulkhead": self.bulkhead.get_metrics(),
            "retry": self.retry_manager.get_metrics()
        }
