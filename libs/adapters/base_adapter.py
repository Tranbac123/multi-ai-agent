"""Base tool adapter with resilience patterns."""

import asyncio
from typing import Callable, Any, Optional, Dict, List
from abc import ABC, abstractmethod
from dataclasses import dataclass
import structlog

from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from .retry_policy import RetryPolicy, RetryConfig
from .timeout_handler import TimeoutHandler, TimeoutConfig
from .bulkhead import Bulkhead, BulkheadConfig
from .rate_limiter import RateLimiter, RateLimitConfig
from .health_checker import HealthChecker, HealthCheckConfig

logger = structlog.get_logger(__name__)


@dataclass
class AdapterConfig:
    """Configuration for tool adapter."""

    # Circuit breaker config
    circuit_breaker: CircuitBreakerConfig = None

    # Retry policy config
    retry_policy: RetryConfig = None

    # Timeout config
    timeout: TimeoutConfig = None

    # Bulkhead config
    bulkhead: BulkheadConfig = None

    # Rate limiter config
    rate_limiter: RateLimitConfig = None

    # Health checker config
    health_checker: HealthCheckConfig = None

    def __post_init__(self):
        if self.circuit_breaker is None:
            self.circuit_breaker = CircuitBreakerConfig()
        if self.retry_policy is None:
            self.retry_policy = RetryConfig()
        if self.timeout is None:
            self.timeout = TimeoutConfig()
        if self.bulkhead is None:
            self.bulkhead = BulkheadConfig()
        if self.rate_limiter is None:
            self.rate_limiter = RateLimitConfig()
        if self.health_checker is None:
            self.health_checker = HealthCheckConfig()


class BaseToolAdapter(ABC):
    """Base tool adapter with resilience patterns."""

    def __init__(self, name: str, config: AdapterConfig = None):
        self.name = name
        self.config = config or AdapterConfig()

        # Initialize resilience components
        self.circuit_breaker = CircuitBreaker(f"{name}_cb", self.config.circuit_breaker)
        self.retry_policy = RetryPolicy(self.config.retry_policy)
        self.timeout_handler = TimeoutHandler(self.config.timeout)
        self.bulkhead = Bulkhead(f"{name}_bh", self.config.bulkhead)
        self.rate_limiter = RateLimiter(f"{name}_rl", self.config.rate_limiter)
        self.health_checker = HealthChecker(f"{name}_hc", self.config.health_checker)

        # Set up health check function
        self.health_checker.set_check_function(self._health_check)

    @abstractmethod
    async def _execute_tool(self, *args, **kwargs) -> Any:
        """Execute the actual tool logic. Must be implemented by subclasses."""
        pass

    async def execute(self, *args, **kwargs) -> Any:
        """Execute tool with all resilience patterns applied."""
        try:
            # Apply rate limiting
            result = await self.rate_limiter.execute(
                self._execute_with_resilience, *args, **kwargs
            )
            return result

        except Exception as e:
            logger.error(f"Tool adapter {self.name} execution failed: {e}")
            raise

    async def _execute_with_resilience(self, *args, **kwargs) -> Any:
        """Execute with circuit breaker, retry, timeout, and bulkhead."""
        # Apply bulkhead
        result = await self.bulkhead.execute(
            self._execute_with_circuit_breaker, *args, **kwargs
        )
        return result

    async def _execute_with_circuit_breaker(self, *args, **kwargs) -> Any:
        """Execute with circuit breaker and retry policy."""
        # Apply circuit breaker
        result = await self.circuit_breaker.call(
            self._execute_with_retry, *args, **kwargs
        )
        return result

    async def _execute_with_retry(self, *args, **kwargs) -> Any:
        """Execute with retry policy."""
        # Apply retry policy
        result = await self.retry_policy.execute(
            self._execute_with_timeout, *args, **kwargs
        )
        return result

    async def _execute_with_timeout(self, *args, **kwargs) -> Any:
        """Execute with timeout handling."""
        # Apply timeout
        result = await self.timeout_handler.execute_with_timeout(
            self._execute_tool, *args, **kwargs
        )
        return result

    async def _health_check(self) -> bool:
        """Perform health check. Override in subclasses for custom health checks."""
        try:
            # Default health check - try to execute with minimal timeout
            await asyncio.wait_for(self._execute_tool(), timeout=5.0)
            return True
        except Exception as e:
            logger.warning(f"Health check failed for {self.name}: {e}")
            return False

    async def start(self):
        """Start the adapter and its components."""
        await self.health_checker.start()
        logger.info(f"Tool adapter {self.name} started")

    async def stop(self):
        """Stop the adapter and its components."""
        await self.health_checker.stop()
        logger.info(f"Tool adapter {self.name} stopped")

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics for the adapter."""
        return {
            "name": self.name,
            "circuit_breaker": self.circuit_breaker.get_state(),
            "bulkhead": self.bulkhead.get_stats(),
            "rate_limiter": self.rate_limiter.get_stats(),
            "health_checker": self.health_checker.get_status(),
            "timeout_stats": self.timeout_handler.get_timeout_stats(),
        }

    def reset_stats(self):
        """Reset all statistics."""
        self.bulkhead.reset_stats()
        self.rate_limiter.reset_stats()
        self.circuit_breaker.reset()


class ToolAdapterManager:
    """Manager for multiple tool adapters."""

    def __init__(self):
        self.adapters: Dict[str, BaseToolAdapter] = {}
        self._lock = asyncio.Lock()

    def add_adapter(self, name: str, adapter: BaseToolAdapter):
        """Add a tool adapter."""
        self.adapters[name] = adapter

    def get_adapter(self, name: str) -> Optional[BaseToolAdapter]:
        """Get a tool adapter by name."""
        return self.adapters.get(name)

    async def start_all(self):
        """Start all adapters."""
        tasks = []
        for adapter in self.adapters.values():
            tasks.append(adapter.start())
        await asyncio.gather(*tasks)

    async def stop_all(self):
        """Stop all adapters."""
        tasks = []
        for adapter in self.adapters.values():
            tasks.append(adapter.stop())
        await asyncio.gather(*tasks)

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all adapters."""
        return {name: adapter.get_stats() for name, adapter in self.adapters.items()}

    def get_healthy_adapters(self) -> List[str]:
        """Get list of healthy adapter names."""
        healthy = []
        for name, adapter in self.adapters.items():
            if adapter.health_checker.status.value == "healthy":
                healthy.append(name)
        return healthy
