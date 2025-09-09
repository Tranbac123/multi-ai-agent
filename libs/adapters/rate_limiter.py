"""Rate limiter implementation for resilient tool adapters."""

import asyncio
import time
from typing import Callable, Any, Optional, Dict
from dataclasses import dataclass
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class RateLimitStrategy(Enum):
    """Rate limiting strategies."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiter."""
    requests_per_second: float = 10.0
    burst_size: int = 20
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET
    window_size: float = 60.0  # For sliding/fixed window strategies


class RateLimiter:
    """Rate limiter implementation."""
    
    def __init__(self, name: str, config: RateLimitConfig = None):
        self.name = name
        self.config = config or RateLimitConfig()
        self._tokens = float(self.config.burst_size)
        self._last_refill = time.time()
        self._lock = asyncio.Lock()
        self._request_times = []  # For sliding window
        self._window_start = time.time()  # For fixed window
        self._window_requests = 0  # For fixed window
        
        # Statistics
        self._total_requests = 0
        self._allowed_requests = 0
        self._rejected_requests = 0
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with rate limiting."""
        if not await self._allow_request():
            self._rejected_requests += 1
            raise RateLimitExceededError(f"Rate limit exceeded for {self.name}")
        
        self._allowed_requests += 1
        return await func(*args, **kwargs)
    
    async def _allow_request(self) -> bool:
        """Check if request is allowed based on rate limit."""
        async with self._lock:
            self._total_requests += 1
            
            if self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                return await self._token_bucket_allow()
            elif self.config.strategy == RateLimitStrategy.SLIDING_WINDOW:
                return await self._sliding_window_allow()
            elif self.config.strategy == RateLimitStrategy.FIXED_WINDOW:
                return await self._fixed_window_allow()
            else:
                return True
    
    async def _token_bucket_allow(self) -> bool:
        """Token bucket rate limiting."""
        now = time.time()
        
        # Refill tokens based on time passed
        time_passed = now - self._last_refill
        tokens_to_add = time_passed * self.config.requests_per_second
        self._tokens = min(self._tokens + tokens_to_add, self.config.burst_size)
        self._last_refill = now
        
        # Check if we have tokens available
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        
        return False
    
    async def _sliding_window_allow(self) -> bool:
        """Sliding window rate limiting."""
        now = time.time()
        window_start = now - self.config.window_size
        
        # Remove old requests outside the window
        self._request_times = [t for t in self._request_times if t > window_start]
        
        # Check if we're under the limit
        if len(self._request_times) < self.config.requests_per_second * self.config.window_size:
            self._request_times.append(now)
            return True
        
        return False
    
    async def _fixed_window_allow(self) -> bool:
        """Fixed window rate limiting."""
        now = time.time()
        
        # Check if we need to reset the window
        if now - self._window_start >= self.config.window_size:
            self._window_start = now
            self._window_requests = 0
        
        # Check if we're under the limit
        if self._window_requests < self.config.requests_per_second * self.config.window_size:
            self._window_requests += 1
            return True
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        return {
            "name": self.name,
            "total_requests": self._total_requests,
            "allowed_requests": self._allowed_requests,
            "rejected_requests": self._rejected_requests,
            "acceptance_rate": self._allowed_requests / self._total_requests if self._total_requests > 0 else 0,
            "current_tokens": self._tokens if self.config.strategy == RateLimitStrategy.TOKEN_BUCKET else None,
            "window_requests": self._window_requests if self.config.strategy == RateLimitStrategy.FIXED_WINDOW else None,
            "config": {
                "requests_per_second": self.config.requests_per_second,
                "burst_size": self.config.burst_size,
                "strategy": self.config.strategy.value,
                "window_size": self.config.window_size
            }
        }
    
    def reset_stats(self):
        """Reset statistics."""
        self._total_requests = 0
        self._allowed_requests = 0
        self._rejected_requests = 0


class RateLimitExceededError(Exception):
    """Rate limit exceeded error."""
    pass
