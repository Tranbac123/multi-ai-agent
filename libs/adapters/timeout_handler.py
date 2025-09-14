"""Timeout handler for resilient tool adapters."""

import asyncio
from typing import Callable, Any, Optional, Union
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class TimeoutConfig:
    """Configuration for timeout handler."""

    default_timeout: float = 30.0
    max_timeout: float = 300.0  # 5 minutes
    min_timeout: float = 0.1  # 100ms
    timeout_multiplier: float = 1.5  # For adaptive timeouts


class TimeoutHandler:
    """Timeout handler with adaptive timeout management."""

    def __init__(self, config: TimeoutConfig = None):
        self.config = config or TimeoutConfig()
        self._timeout_history: list[float] = []
        self._max_history = 100

    async def execute_with_timeout(
        self, func: Callable, timeout: Optional[float] = None, *args, **kwargs
    ) -> Any:
        """Execute function with timeout."""
        effective_timeout = self._get_effective_timeout(timeout)

        try:
            result = await asyncio.wait_for(
                func(*args, **kwargs), timeout=effective_timeout
            )

            # Record successful timeout for adaptive behavior
            self._record_timeout(effective_timeout, success=True)
            return result

        except asyncio.TimeoutError:
            self._record_timeout(effective_timeout, success=False)
            logger.warning(f"Function timed out after {effective_timeout}s")
            raise TimeoutError(f"Operation timed out after {effective_timeout}s")

    def _get_effective_timeout(self, timeout: Optional[float]) -> float:
        """Get effective timeout value."""
        if timeout is None:
            timeout = self.config.default_timeout

        # Apply bounds
        timeout = max(timeout, self.config.min_timeout)
        timeout = min(timeout, self.config.max_timeout)

        return timeout

    def _record_timeout(self, timeout: float, success: bool):
        """Record timeout for adaptive behavior."""
        self._timeout_history.append(timeout)

        # Keep only recent history
        if len(self._timeout_history) > self._max_history:
            self._timeout_history = self._timeout_history[-self._max_history :]

    def get_adaptive_timeout(self) -> float:
        """Get adaptive timeout based on history."""
        if not self._timeout_history:
            return self.config.default_timeout

        # Calculate average timeout from recent history
        recent_history = self._timeout_history[-10:]  # Last 10 timeouts
        avg_timeout = sum(recent_history) / len(recent_history)

        # Apply multiplier for safety margin
        adaptive_timeout = avg_timeout * self.config.timeout_multiplier

        # Apply bounds
        adaptive_timeout = max(adaptive_timeout, self.config.min_timeout)
        adaptive_timeout = min(adaptive_timeout, self.config.max_timeout)

        return adaptive_timeout

    def get_timeout_stats(self) -> dict:
        """Get timeout statistics."""
        if not self._timeout_history:
            return {
                "count": 0,
                "average": 0.0,
                "min": 0.0,
                "max": 0.0,
                "adaptive": self.config.default_timeout,
            }

        return {
            "count": len(self._timeout_history),
            "average": sum(self._timeout_history) / len(self._timeout_history),
            "min": min(self._timeout_history),
            "max": max(self._timeout_history),
            "adaptive": self.get_adaptive_timeout(),
        }


class TimeoutError(Exception):
    """Timeout error."""

    pass
