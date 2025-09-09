"""Resilient adapter combining circuit breaker, retry, and timeout patterns."""

import asyncio
import time
from typing import Callable, Any, Optional, Dict, Type
from uuid import UUID
import structlog

from .circuit_breaker import CircuitBreaker, CircuitBreakerManager
from .retry_adapter import RetryAdapter, RetryConfig, RetryManager

logger = structlog.get_logger(__name__)


class ResilientAdapter:
    """Resilient adapter combining multiple resilience patterns."""
    
    def __init__(
        self,
        name: str,
        circuit_breaker_config: Optional[Dict[str, Any]] = None,
        retry_config: Optional[RetryConfig] = None,
        timeout: float = 30.0,
        bulkhead_size: int = 10
    ):
        self.name = name
        self.timeout = timeout
        self.bulkhead_size = bulkhead_size
        
        # Initialize circuit breaker
        cb_config = circuit_breaker_config or {}
        self.circuit_breaker = CircuitBreaker(
            name=f"{name}_cb",
            **cb_config
        )
        
        # Initialize retry adapter
        self.retry_config = retry_config or RetryConfig()
        self.retry_adapter = RetryAdapter(self.retry_config)
        
        # Bulkhead semaphore
        self.semaphore = asyncio.Semaphore(bulkhead_size)
        
        # Statistics
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "timeout_calls": 0,
            "circuit_open_calls": 0,
            "bulkhead_rejected_calls": 0,
            "total_execution_time": 0.0
        }
    
    async def call(
        self, 
        func: Callable, 
        *args, 
        **kwargs
    ) -> Any:
        """Execute function with all resilience patterns."""
        start_time = time.time()
        self.stats["total_calls"] += 1
        
        try:
            # Check bulkhead capacity
            if self.semaphore.locked():
                self.stats["bulkhead_rejected_calls"] += 1
                raise BulkheadRejectedException(
                    f"Bulkhead limit reached for {self.name}"
                )
            
            # Acquire semaphore for bulkhead
            async with self.semaphore:
                # Execute with timeout
                result = await asyncio.wait_for(
                    self._execute_with_resilience(func, *args, **kwargs),
                    timeout=self.timeout
                )
                
                self.stats["successful_calls"] += 1
                return result
                
        except asyncio.TimeoutError:
            self.stats["timeout_calls"] += 1
            logger.warning("Function call timed out", 
                          name=self.name, 
                          timeout=self.timeout)
            raise
            
        except BulkheadRejectedException:
            raise
            
        except Exception as e:
            self.stats["failed_calls"] += 1
            logger.error("Function call failed", 
                        name=self.name, 
                        error=str(e))
            raise
            
        finally:
            execution_time = time.time() - start_time
            self.stats["total_execution_time"] += execution_time
    
    async def _execute_with_resilience(
        self, 
        func: Callable, 
        *args, 
        **kwargs
    ) -> Any:
        """Execute function with circuit breaker and retry."""
        try:
            # Use circuit breaker
            result = await self.circuit_breaker.call(
                self.retry_adapter.call,
                func,
                *args,
                **kwargs
            )
            return result
            
        except Exception as e:
            if "Circuit breaker" in str(e) and "is OPEN" in str(e):
                self.stats["circuit_open_calls"] += 1
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        stats = self.stats.copy()
        
        # Calculate rates
        if stats["total_calls"] > 0:
            stats["success_rate"] = stats["successful_calls"] / stats["total_calls"]
            stats["failure_rate"] = stats["failed_calls"] / stats["total_calls"]
            stats["timeout_rate"] = stats["timeout_calls"] / stats["total_calls"]
            stats["circuit_open_rate"] = stats["circuit_open_calls"] / stats["total_calls"]
            stats["bulkhead_rejection_rate"] = stats["bulkhead_rejected_calls"] / stats["total_calls"]
            stats["avg_execution_time"] = stats["total_execution_time"] / stats["total_calls"]
        else:
            stats.update({
                "success_rate": 0.0,
                "failure_rate": 0.0,
                "timeout_rate": 0.0,
                "circuit_open_rate": 0.0,
                "bulkhead_rejection_rate": 0.0,
                "avg_execution_time": 0.0
            })
        
        # Add circuit breaker stats
        stats["circuit_breaker"] = self.circuit_breaker.get_stats()
        
        # Add retry stats
        stats["retry"] = self.retry_adapter.get_stats()
        
        # Add bulkhead stats
        stats["bulkhead"] = {
            "max_concurrent": self.bulkhead_size,
            "available": self.semaphore._value,
            "in_use": self.bulkhead_size - self.semaphore._value
        }
        
        return stats
    
    def reset_stats(self):
        """Reset statistics."""
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "timeout_calls": 0,
            "circuit_open_calls": 0,
            "bulkhead_rejected_calls": 0,
            "total_execution_time": 0.0
        }
        self.retry_adapter.reset_stats()
        self.circuit_breaker.reset()


class BulkheadRejectedException(Exception):
    """Exception raised when bulkhead limit is reached."""
    pass


class ResilientAdapterManager:
    """Manager for multiple resilient adapters."""
    
    def __init__(self):
        self.adapters: Dict[str, ResilientAdapter] = {}
    
    def get_adapter(
        self, 
        name: str, 
        **kwargs
    ) -> ResilientAdapter:
        """Get or create resilient adapter."""
        if name not in self.adapters:
            self.adapters[name] = ResilientAdapter(name=name, **kwargs)
        
        return self.adapters[name]
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all adapters."""
        return {
            name: adapter.get_stats() 
            for name, adapter in self.adapters.items()
        }
    
    def reset_all_stats(self):
        """Reset statistics for all adapters."""
        for adapter in self.adapters.values():
            adapter.reset_stats()
    
    def get_adapter(self, name: str) -> Optional[ResilientAdapter]:
        """Get adapter by name."""
        return self.adapters.get(name)


# Global resilient adapter manager
resilient_adapter_manager = ResilientAdapterManager()


def resilient(
    name: str,
    timeout: float = 30.0,
    bulkhead_size: int = 10,
    circuit_breaker_config: Optional[Dict[str, Any]] = None,
    retry_config: Optional[RetryConfig] = None
):
    """Decorator for resilient function execution."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            adapter = resilient_adapter_manager.get_adapter(
                name=name,
                timeout=timeout,
                bulkhead_size=bulkhead_size,
                circuit_breaker_config=circuit_breaker_config,
                retry_config=retry_config
            )
            return await adapter.call(func, *args, **kwargs)
        
        return wrapper
    return decorator


# Predefined adapter configurations
def create_database_adapter(name: str = "database") -> ResilientAdapter:
    """Create database adapter with appropriate settings."""
    return ResilientAdapter(
        name=name,
        circuit_breaker_config={
            "failure_threshold": 5,
            "recovery_timeout": 30.0,
            "expected_exception": Exception
        },
        retry_config=RetryConfig(
            max_attempts=3,
            base_delay=0.5,
            max_delay=10.0,
            exponential_base=2.0,
            jitter=True
        ),
        timeout=30.0,
        bulkhead_size=20
    )


def create_api_adapter(name: str = "api") -> ResilientAdapter:
    """Create API adapter with appropriate settings."""
    return ResilientAdapter(
        name=name,
        circuit_breaker_config={
            "failure_threshold": 10,
            "recovery_timeout": 60.0,
            "expected_exception": Exception
        },
        retry_config=RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            max_delay=30.0,
            exponential_base=2.0,
            jitter=True
        ),
        timeout=60.0,
        bulkhead_size=50
    )


def create_llm_adapter(name: str = "llm") -> ResilientAdapter:
    """Create LLM adapter with appropriate settings."""
    return ResilientAdapter(
        name=name,
        circuit_breaker_config={
            "failure_threshold": 3,
            "recovery_timeout": 120.0,
            "expected_exception": Exception
        },
        retry_config=RetryConfig(
            max_attempts=2,
            base_delay=2.0,
            max_delay=60.0,
            exponential_base=2.0,
            jitter=True
        ),
        timeout=120.0,
        bulkhead_size=5
    )
