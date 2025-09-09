"""Circuit breaker implementation for resilient service calls."""

import asyncio
import time
from enum import Enum
from typing import Callable, Any, Optional, Dict
import structlog

logger = structlog.get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, calls fail fast
    HALF_OPEN = "half_open"  # Testing if service is back


class CircuitBreaker:
    """Circuit breaker for resilient service calls."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
        name: str = "circuit_breaker"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        
        # Statistics
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.circuit_opened_count = 0
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        self.total_calls += 1
        
        # Check if circuit should be opened
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker transitioning to half-open", 
                           name=self.name)
            else:
                self.failed_calls += 1
                raise CircuitBreakerOpenException(
                    f"Circuit breaker '{self.name}' is OPEN"
                )
        
        try:
            # Execute the function
            result = await func(*args, **kwargs)
            
            # Success - reset failure count
            self._on_success()
            self.successful_calls += 1
            
            return result
            
        except self.expected_exception as e:
            # Expected failure - increment failure count
            self._on_failure()
            self.failed_calls += 1
            
            logger.warning("Circuit breaker caught expected exception", 
                          name=self.name, 
                          exception=str(e))
            raise
            
        except Exception as e:
            # Unexpected failure - also increment failure count
            self._on_failure()
            self.failed_calls += 1
            
            logger.error("Circuit breaker caught unexpected exception", 
                        name=self.name, 
                        exception=str(e))
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt reset."""
        if self.last_failure_time is None:
            return True
        
        return time.time() - self.last_failure_time >= self.recovery_timeout
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time = None
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            if self.state != CircuitState.OPEN:
                self.state = CircuitState.OPEN
                self.circuit_opened_count += 1
                logger.warning("Circuit breaker opened", 
                              name=self.name, 
                              failure_count=self.failure_count)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        success_rate = (
            self.successful_calls / self.total_calls 
            if self.total_calls > 0 else 0.0
        )
        
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": success_rate,
            "circuit_opened_count": self.circuit_opened_count,
            "last_failure_time": self.last_failure_time
        }
    
    def reset(self):
        """Reset circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        logger.info("Circuit breaker reset", name=self.name)


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreakerManager:
    """Manager for multiple circuit breakers."""
    
    def __init__(self):
        self.breakers: Dict[str, CircuitBreaker] = {}
    
    def get_breaker(
        self, 
        name: str, 
        **kwargs
    ) -> CircuitBreaker:
        """Get or create circuit breaker."""
        if name not in self.breakers:
            self.breakers[name] = CircuitBreaker(name=name, **kwargs)
        
        return self.breakers[name]
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuit breakers."""
        return {
            name: breaker.get_stats() 
            for name, breaker in self.breakers.items()
        }
    
    def reset_all(self):
        """Reset all circuit breakers."""
        for breaker in self.breakers.values():
            breaker.reset()
    
    def reset(self, name: str):
        """Reset specific circuit breaker."""
        if name in self.breakers:
            self.breakers[name].reset()


# Global circuit breaker manager
circuit_breaker_manager = CircuitBreakerManager()


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    expected_exception: type = Exception
):
    """Decorator for circuit breaker protection."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            breaker = circuit_breaker_manager.get_breaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                expected_exception=expected_exception
            )
            return await breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator