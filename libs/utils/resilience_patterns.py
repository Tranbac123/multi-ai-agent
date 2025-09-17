"""Common resilience patterns for service operations."""

import asyncio
import time
from typing import Callable, Any, Optional, Type, Union
from functools import wraps
import structlog

from .logging_config import get_logger

logger = get_logger(__name__)


class ResilienceConfig:
    """Configuration for resilience patterns."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        timeout: Optional[float] = None
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.timeout = timeout


def retry_with_exponential_backoff(
    config: Optional[ResilienceConfig] = None,
    exceptions: tuple = (Exception,),
    operation_name: Optional[str] = None
):
    """Decorator for retry with exponential backoff."""
    if config is None:
        config = ResilienceConfig()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    # Apply timeout if configured
                    if config.timeout:
                        return await asyncio.wait_for(
                            func(*args, **kwargs), 
                            timeout=config.timeout
                        )
                    else:
                        return await func(*args, **kwargs)
                        
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == config.max_retries:
                        logger.error(
                            f"Operation failed after {config.max_retries} retries",
                            operation=operation_name or func.__name__,
                            error=str(e),
                            attempts=attempt + 1
                        )
                        raise e
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )
                    
                    # Add jitter to prevent thundering herd
                    if config.jitter:
                        delay *= (0.5 + 0.5 * (time.time() % 1))
                    
                    logger.warning(
                        f"Operation failed, retrying in {delay:.2f}s",
                        operation=operation_name or func.__name__,
                        error=str(e),
                        attempt=attempt + 1,
                        max_retries=config.max_retries,
                        delay=delay
                    )
                    
                    await asyncio.sleep(delay)
            
            # This should never be reached, but just in case
            raise last_exception
        
        return wrapper
    return decorator


def timeout_operation(timeout_seconds: float, operation_name: Optional[str] = None):
    """Decorator for operation timeout."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs), 
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"Operation timed out after {timeout_seconds}s",
                    operation=operation_name or func.__name__
                )
                raise
        return wrapper
    return decorator


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    operation_name: Optional[str] = None
):
    """Simple circuit breaker decorator."""
    def decorator(func: Callable) -> Callable:
        failure_count = 0
        last_failure_time = 0
        circuit_open = False
        
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            nonlocal failure_count, last_failure_time, circuit_open
            
            # Check if circuit should be reset
            if circuit_open:
                if time.time() - last_failure_time > recovery_timeout:
                    circuit_open = False
                    failure_count = 0
                    logger.info(
                        f"Circuit breaker reset",
                        operation=operation_name or func.__name__
                    )
                else:
                    logger.warning(
                        f"Circuit breaker open, operation blocked",
                        operation=operation_name or func.__name__
                    )
                    raise RuntimeError("Circuit breaker is open")
            
            try:
                result = await func(*args, **kwargs)
                # Reset failure count on success
                failure_count = 0
                return result
                
            except Exception as e:
                failure_count += 1
                last_failure_time = time.time()
                
                if failure_count >= failure_threshold:
                    circuit_open = True
                    logger.error(
                        f"Circuit breaker opened after {failure_count} failures",
                        operation=operation_name or func.__name__,
                        failure_count=failure_count,
                        threshold=failure_threshold
                    )
                
                raise e
        
        return wrapper
    return decorator


class ResilienceManager:
    """Manager for resilience patterns."""
    
    def __init__(self, default_config: Optional[ResilienceConfig] = None):
        self.default_config = default_config or ResilienceConfig()
        self.operation_configs: dict = {}
    
    def configure_operation(
        self, 
        operation_name: str, 
        config: ResilienceConfig
    ) -> None:
        """Configure resilience for a specific operation."""
        self.operation_configs[operation_name] = config
    
    def get_config(self, operation_name: str) -> ResilienceConfig:
        """Get configuration for an operation."""
        return self.operation_configs.get(operation_name, self.default_config)
    
    async def execute_with_resilience(
        self,
        operation: Callable,
        operation_name: Optional[str] = None,
        config: Optional[ResilienceConfig] = None
    ) -> Any:
        """Execute an operation with resilience patterns."""
        name = operation_name or operation.__name__
        op_config = config or self.get_config(name)
        
        @retry_with_exponential_backoff(
            config=op_config,
            operation_name=name
        )
        async def _execute():
            return await operation()
        
        return await _execute()
