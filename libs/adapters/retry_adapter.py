"""Retry adapter with exponential backoff and jitter."""

import asyncio
import random
import time
from typing import Callable, Any, Optional, List, Type
import structlog

logger = structlog.get_logger(__name__)


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Optional[List[Type[Exception]]] = None
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or [Exception]
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt."""
        # Exponential backoff
        delay = self.base_delay * (self.exponential_base ** (attempt - 1))
        
        # Cap at max delay
        delay = min(delay, self.max_delay)
        
        # Add jitter to prevent thundering herd
        if self.jitter:
            jitter_range = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)


class RetryAdapter:
    """Retry adapter with configurable retry behavior."""
    
    def __init__(self, config: RetryConfig):
        self.config = config
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "retry_attempts": 0,
            "total_retry_delay": 0.0
        }
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic."""
        self.stats["total_calls"] += 1
        last_exception = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                result = await func(*args, **kwargs)
                self.stats["successful_calls"] += 1
                
                if attempt > 1:
                    logger.info("Function succeeded after retry", 
                              attempt=attempt, 
                              function=func.__name__)
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Check if exception is retryable
                if not self._is_retryable(e):
                    logger.warning("Non-retryable exception caught", 
                                 exception=str(e), 
                                 function=func.__name__)
                    break
                
                # Check if we should retry
                if attempt >= self.config.max_attempts:
                    logger.error("Max retry attempts exceeded", 
                               attempts=attempt, 
                               function=func.__name__)
                    break
                
                # Calculate delay and wait
                delay = self.config.calculate_delay(attempt)
                self.stats["retry_attempts"] += 1
                self.stats["total_retry_delay"] += delay
                
                logger.warning("Retrying function call", 
                             attempt=attempt, 
                             delay=delay, 
                             exception=str(e),
                             function=func.__name__)
                
                await asyncio.sleep(delay)
        
        # All retries failed
        self.stats["failed_calls"] += 1
        raise last_exception
    
    def _is_retryable(self, exception: Exception) -> bool:
        """Check if exception is retryable."""
        return any(
            isinstance(exception, exc_type) 
            for exc_type in self.config.retryable_exceptions
        )
    
    def get_stats(self) -> dict:
        """Get retry statistics."""
        stats = self.stats.copy()
        
        if stats["total_calls"] > 0:
            stats["success_rate"] = stats["successful_calls"] / stats["total_calls"]
            stats["retry_rate"] = stats["retry_attempts"] / stats["total_calls"]
            stats["avg_retry_delay"] = (
                stats["total_retry_delay"] / max(stats["retry_attempts"], 1)
            )
        else:
            stats["success_rate"] = 0.0
            stats["retry_rate"] = 0.0
            stats["avg_retry_delay"] = 0.0
        
        return stats
    
    def reset_stats(self):
        """Reset statistics."""
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "retry_attempts": 0,
            "total_retry_delay": 0.0
        }


class RetryManager:
    """Manager for multiple retry adapters."""
    
    def __init__(self):
        self.adapters: dict = {}
    
    def get_adapter(self, name: str, config: RetryConfig) -> RetryAdapter:
        """Get or create retry adapter."""
        if name not in self.adapters:
            self.adapters[name] = RetryAdapter(config)
        
        return self.adapters[name]
    
    def get_all_stats(self) -> dict:
        """Get statistics for all retry adapters."""
        return {
            name: adapter.get_stats() 
            for name, adapter in self.adapters.items()
        }
    
    def reset_all_stats(self):
        """Reset statistics for all adapters."""
        for adapter in self.adapters.values():
            adapter.reset_stats()


# Global retry manager
retry_manager = RetryManager()


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Optional[List[Type[Exception]]] = None,
    name: str = "default"
):
    """Decorator for retry functionality."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            config = RetryConfig(
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
                exponential_base=exponential_base,
                jitter=jitter,
                retryable_exceptions=retryable_exceptions
            )
            
            adapter = retry_manager.get_adapter(name, config)
            return await adapter.call(func, *args, **kwargs)
        
        return wrapper
    return decorator


# Predefined retry configurations
QUICK_RETRY = RetryConfig(
    max_attempts=2,
    base_delay=0.1,
    max_delay=1.0,
    exponential_base=2.0,
    jitter=True
)

STANDARD_RETRY = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True
)

LONG_RETRY = RetryConfig(
    max_attempts=5,
    base_delay=2.0,
    max_delay=120.0,
    exponential_base=2.0,
    jitter=True
)
