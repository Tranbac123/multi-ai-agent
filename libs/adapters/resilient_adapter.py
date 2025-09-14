"""Resilient adapter with circuit breaker, retry, timeout, and bulkhead patterns."""

import asyncio
import time
import functools
from typing import Dict, Any, Optional, Callable, Awaitable, TypeVar, Union
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)

T = TypeVar('T')


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class ResilientAdapter:
    """Resilient adapter with circuit breaker, retry, timeout, and bulkhead patterns."""

    def __init__(
        self,
        name: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        circuit_breaker_config: Optional[Dict[str, Any]] = None,
        bulkhead_size: int = 10,
    ):
        self.name = name
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.bulkhead_size = bulkhead_size
        
        # Circuit breaker configuration
        self.circuit_breaker_config = circuit_breaker_config or {
            "failure_threshold": 5,
            "recovery_timeout": 60.0,
        }
        self.failure_threshold = self.circuit_breaker_config["failure_threshold"]
        self.recovery_timeout = self.circuit_breaker_config["recovery_timeout"]
        
        # Circuit breaker state
        self.circuit_state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.next_attempt_time = 0.0
        
        # Bulkhead semaphore
        self.bulkhead_semaphore = asyncio.Semaphore(bulkhead_size)
        
        # Statistics
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "timeout_requests": 0,
            "circuit_breaker_open": 0,
            "retry_attempts": 0,
            "bulkhead_rejections": 0,
        }

    async def execute(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """Execute function with resilience patterns."""
        self.stats["total_requests"] += 1
        
        # Check circuit breaker
        if not self._is_circuit_breaker_closed():
            self.stats["circuit_breaker_open"] += 1
            raise CircuitBreakerOpenError(f"Circuit breaker is open for {self.name}")
        
        # Acquire bulkhead semaphore
        try:
            await asyncio.wait_for(
                self.bulkhead_semaphore.acquire(), timeout=1.0
            )
        except asyncio.TimeoutError:
            self.stats["bulkhead_rejections"] += 1
            raise BulkheadRejectError(f"Bulkhead is full for {self.name}")
        
        try:
            # Execute with retry logic
            result = await self._execute_with_retry(func, *args, **kwargs)
            
            # Record success
            self._record_success()
            self.stats["successful_requests"] += 1
            
            return result
            
        except Exception as e:
            self._record_failure()
            self.stats["failed_requests"] += 1
            raise
        finally:
            self.bulkhead_semaphore.release()

    async def _execute_with_retry(
        self, func: Callable[..., Awaitable[T]], *args, **kwargs
    ) -> T:
        """Execute function with retry logic."""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # Execute with timeout
                result = await asyncio.wait_for(
                    func(*args, **kwargs), timeout=self.timeout
                )
                return result
                
            except asyncio.TimeoutError as e:
                last_exception = e
                self.stats["timeout_requests"] += 1
                
                if attempt < self.max_retries:
                    delay = min(
                        self.base_delay * (2 ** attempt), self.max_delay
                    )
                    logger.warning(
                        "Request timed out, retrying",
                        adapter=self.name,
                        attempt=attempt,
                        delay=delay,
                    )
                    self.stats["retry_attempts"] += 1
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "Request timed out after all retries",
                        adapter=self.name,
                        attempts=attempt,
                    )
                    
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    delay = min(
                        self.base_delay * (2 ** attempt), self.max_delay
                    )
                    logger.warning(
                        "Request failed, retrying",
                        adapter=self.name,
                        attempt=attempt,
                        delay=delay,
                        error=str(e),
                    )
                    self.stats["retry_attempts"] += 1
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "Request failed after all retries",
                        adapter=self.name,
                        attempts=attempt,
                        error=str(e),
                    )
        
        raise last_exception

    def _is_circuit_breaker_closed(self) -> bool:
        """Check if circuit breaker is closed."""
        current_time = time.time()
        
        if self.circuit_state == CircuitBreakerState.CLOSED:
            return True
        elif self.circuit_state == CircuitBreakerState.OPEN:
            if current_time >= self.next_attempt_time:
                self.circuit_state = CircuitBreakerState.HALF_OPEN
                logger.info(
                    "Circuit breaker transitioning to half-open",
                    adapter=self.name,
                )
                return True
            return False
        elif self.circuit_state == CircuitBreakerState.HALF_OPEN:
            return True
        
        return False

    def _record_success(self):
        """Record successful request."""
        if self.circuit_state == CircuitBreakerState.HALF_OPEN:
            self.circuit_state = CircuitBreakerState.CLOSED
            self.failure_count = 0
            logger.info(
                "Circuit breaker closed after successful request",
                adapter=self.name,
            )
        elif self.circuit_state == CircuitBreakerState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)

    def _record_failure(self):
        """Record failed request."""
        current_time = time.time()
        self.failure_count += 1
        self.last_failure_time = current_time
        
        if self.circuit_state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self.circuit_state = CircuitBreakerState.OPEN
                self.next_attempt_time = current_time + self.recovery_timeout
                logger.warning(
                    "Circuit breaker opened due to failures",
                    adapter=self.name,
                    failure_count=self.failure_count,
                    recovery_time=self.next_attempt_time,
                )
        elif self.circuit_state == CircuitBreakerState.HALF_OPEN:
            self.circuit_state = CircuitBreakerState.OPEN
            self.next_attempt_time = current_time + self.recovery_timeout
            logger.warning(
                "Circuit breaker reopened after failure in half-open state",
                adapter=self.name,
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get adapter statistics."""
        return {
            **self.stats,
            "circuit_breaker_state": self.circuit_state.value,
            "failure_count": self.failure_count,
            "bulkhead_available": self.bulkhead_semaphore._value,
            "bulkhead_capacity": self.bulkhead_size,
        }

    def reset_stats(self):
        """Reset adapter statistics."""
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "timeout_requests": 0,
            "circuit_breaker_open": 0,
            "retry_attempts": 0,
            "bulkhead_rejections": 0,
        }
        self.failure_count = 0
        self.circuit_state = CircuitBreakerState.CLOSED


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


class BulkheadRejectError(Exception):
    """Raised when bulkhead is full."""
    pass


def resilient(
    name: str,
    timeout: float = 30.0,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    circuit_breaker_config: Optional[Dict[str, Any]] = None,
    bulkhead_size: int = 10,
):
    """Decorator for resilient function execution."""
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        adapter = ResilientAdapter(
            name=name,
            timeout=timeout,
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
            circuit_breaker_config=circuit_breaker_config,
            bulkhead_size=bulkhead_size,
        )
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await adapter.execute(func, *args, **kwargs)
        
        wrapper._adapter = adapter
        return wrapper
    
    return decorator


# Global adapter manager
resilient_adapter_manager = {
    "adapters": {},
    "stats": {
        "total_adapters": 0,
        "total_requests": 0,
        "total_failures": 0,
    }
}


def create_database_adapter(name: str) -> ResilientAdapter:
    """Create database adapter with appropriate configuration."""
    return ResilientAdapter(
        name=name,
        timeout=30.0,
        max_retries=3,
        base_delay=1.0,
        max_delay=10.0,
        circuit_breaker_config={
            "failure_threshold": 5,
            "recovery_timeout": 60.0,
        },
        bulkhead_size=20,
    )


def create_api_adapter(name: str) -> ResilientAdapter:
    """Create API adapter with appropriate configuration."""
    return ResilientAdapter(
        name=name,
        timeout=45.0,
        max_retries=3,
        base_delay=2.0,
        max_delay=30.0,
        circuit_breaker_config={
            "failure_threshold": 3,
            "recovery_timeout": 120.0,
        },
        bulkhead_size=10,
    )


def create_llm_adapter(name: str) -> ResilientAdapter:
    """Create LLM adapter with appropriate configuration."""
    return ResilientAdapter(
        name=name,
        timeout=120.0,
        max_retries=2,
        base_delay=5.0,
        max_delay=60.0,
        circuit_breaker_config={
            "failure_threshold": 3,
            "recovery_timeout": 300.0,
        },
        bulkhead_size=5,
    )