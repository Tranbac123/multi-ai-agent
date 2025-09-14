"""Retry policy implementation for resilient tool adapters."""

import asyncio
import random
from typing import Callable, Any, Optional, List, Type
from dataclasses import dataclass
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class RetryStrategy(Enum):
    """Retry strategies."""

    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CUSTOM = "custom"


@dataclass
class RetryConfig:
    """Configuration for retry policy."""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    jitter: bool = True
    backoff_multiplier: float = 2.0
    retryable_exceptions: List[Type[Exception]] = None

    def __post_init__(self):
        if self.retryable_exceptions is None:
            self.retryable_exceptions = [Exception]


class RetryPolicy:
    """Retry policy with multiple strategies."""

    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry policy."""
        last_exception = None

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                result = await func(*args, **kwargs)
                if attempt > 1:
                    logger.info(f"Function succeeded on attempt {attempt}")
                return result

            except Exception as e:
                last_exception = e

                # Check if exception is retryable
                if not self._is_retryable(e):
                    logger.warning(f"Exception {type(e).__name__} is not retryable")
                    raise

                # Check if we have more attempts
                if attempt >= self.config.max_attempts:
                    logger.error(f"All {self.config.max_attempts} attempts failed")
                    raise RetryExhaustedError(
                        f"Retry exhausted after {self.config.max_attempts} attempts"
                    ) from last_exception

                # Calculate delay
                delay = self._calculate_delay(attempt)

                logger.warning(
                    f"Attempt {attempt} failed: {e}. Retrying in {delay:.2f}s"
                )
                await asyncio.sleep(delay)

        # This should never be reached, but just in case
        raise RetryExhaustedError("Retry policy exhausted") from last_exception

    def _is_retryable(self, exception: Exception) -> bool:
        """Check if exception is retryable."""
        return any(
            isinstance(exception, exc_type)
            for exc_type in self.config.retryable_exceptions
        )

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt."""
        if self.config.strategy == RetryStrategy.FIXED:
            delay = self.config.base_delay
        elif self.config.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.config.base_delay * (
                self.config.backoff_multiplier ** (attempt - 1)
            )
        elif self.config.strategy == RetryStrategy.LINEAR:
            delay = self.config.base_delay * attempt
        else:
            delay = self.config.base_delay

        # Apply max delay limit
        delay = min(delay, self.config.max_delay)

        # Apply jitter if enabled
        if self.config.jitter:
            jitter_range = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_range, jitter_range)
            delay = max(0, delay)  # Ensure non-negative

        return delay


class ExponentialBackoff(RetryPolicy):
    """Exponential backoff retry policy."""

    def __init__(
        self, max_attempts: int = 3, base_delay: float = 1.0, max_delay: float = 60.0
    ):
        config = RetryConfig(
            max_attempts=max_attempts,
            base_delay=base_delay,
            max_delay=max_delay,
            strategy=RetryStrategy.EXPONENTIAL,
            jitter=True,
        )
        super().__init__(config)


class FixedDelayRetry(RetryPolicy):
    """Fixed delay retry policy."""

    def __init__(self, max_attempts: int = 3, delay: float = 1.0):
        config = RetryConfig(
            max_attempts=max_attempts,
            base_delay=delay,
            strategy=RetryStrategy.FIXED,
            jitter=False,
        )
        super().__init__(config)


class LinearBackoff(RetryPolicy):
    """Linear backoff retry policy."""

    def __init__(
        self, max_attempts: int = 3, base_delay: float = 1.0, max_delay: float = 60.0
    ):
        config = RetryConfig(
            max_attempts=max_attempts,
            base_delay=base_delay,
            max_delay=max_delay,
            strategy=RetryStrategy.LINEAR,
            jitter=True,
        )
        super().__init__(config)


class RetryExhaustedError(Exception):
    """Retry policy exhausted all attempts."""

    pass
