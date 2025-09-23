import time
from typing import Dict, Optional
from collections import defaultdict, deque
from .settings import settings

class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_size: int = 60):
        self.max_requests = max_requests
        self.window_size = window_size
        self.requests: deque = deque()
    
    def is_allowed(self) -> bool:
        now = time.time()
        
        # Remove old requests outside the window
        while self.requests and self.requests[0] <= now - self.window_size:
            self.requests.popleft()
        
        # Check if we're under the limit
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        
        return False

class TokenBucketRateLimiter:
    def __init__(self, max_tokens: int, refill_rate: float):
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate  # tokens per second
        self.tokens = max_tokens
        self.last_refill = time.time()
    
    def consume(self, tokens: int) -> bool:
        now = time.time()
        
        # Refill tokens based on time elapsed
        time_passed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + time_passed * self.refill_rate)
        self.last_refill = now
        
        # Check if we have enough tokens
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        
        return False

class RateLimiter:
    def __init__(self):
        # Per-tenant rate limiters
        self.request_limiters: Dict[str, SlidingWindowRateLimiter] = defaultdict(
            lambda: SlidingWindowRateLimiter(settings.requests_per_minute, 60)
        )
        self.token_limiters: Dict[str, TokenBucketRateLimiter] = defaultdict(
            lambda: TokenBucketRateLimiter(
                settings.tokens_per_minute, 
                settings.tokens_per_minute / 60  # tokens per second
            )
        )
        
        # Global rate limiters
        self.global_request_limiter = SlidingWindowRateLimiter(
            settings.requests_per_minute * 10, 60  # 10x tenant limit globally
        )
    
    async def check_rate_limit(self, tenant_id: str, estimated_tokens: int = 1000) -> bool:
        """Check if request is allowed under rate limits"""
        
        # Check global rate limit first
        if not self.global_request_limiter.is_allowed():
            return False
        
        # Check per-tenant request rate limit
        tenant_request_limiter = self.request_limiters[tenant_id]
        if not tenant_request_limiter.is_allowed():
            return False
        
        # Check per-tenant token rate limit
        tenant_token_limiter = self.token_limiters[tenant_id]
        if not tenant_token_limiter.consume(estimated_tokens):
            return False
        
        return True
    
    def get_tenant_status(self, tenant_id: str) -> Dict[str, any]:
        """Get current rate limit status for a tenant"""
        request_limiter = self.request_limiters[tenant_id]
        token_limiter = self.token_limiters[tenant_id]
        
        return {
            "tenant_id": tenant_id,
            "requests_remaining": settings.requests_per_minute - len(request_limiter.requests),
            "tokens_remaining": int(token_limiter.tokens),
            "window_reset_in": 60 - (time.time() - (request_limiter.requests[0] if request_limiter.requests else time.time())),
            "token_refill_rate": token_limiter.refill_rate
        }
