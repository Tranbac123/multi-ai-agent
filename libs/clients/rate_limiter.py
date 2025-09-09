"""Rate limiter with Redis token bucket implementation."""

import asyncio
import time
from typing import Optional, Dict, Any
from uuid import UUID
import redis.asyncio as redis
import structlog

logger = structlog.get_logger(__name__)


class TokenBucket:
    """Token bucket rate limiter implementation."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        capacity: int,
        refill_rate: float,
        window_seconds: int = 60
    ):
        self.redis = redis_client
        self.capacity = capacity
        self.refill_rate = refill_rate  # tokens per second
        self.window_seconds = window_seconds
    
    async def is_allowed(
        self, 
        key: str, 
        tokens: int = 1
    ) -> bool:
        """Check if request is allowed and consume tokens."""
        try:
            current_time = time.time()
            window_start = current_time - self.window_seconds
            
            # Get current bucket state
            pipe = self.redis.pipeline()
            pipe.hgetall(f"rate_limit:{key}")
            pipe.zremrangebyscore(f"rate_limit_tokens:{key}", 0, window_start)
            results = await pipe.execute()
            
            bucket_data = results[0] or {}
            last_refill = float(bucket_data.get("last_refill", current_time))
            tokens_available = float(bucket_data.get("tokens", self.capacity))
            
            # Calculate tokens to add based on time elapsed
            time_elapsed = current_time - last_refill
            tokens_to_add = time_elapsed * self.refill_rate
            tokens_available = min(self.capacity, tokens_available + tokens_to_add)
            
            # Check if enough tokens available
            if tokens_available < tokens:
                # Update bucket state
                await self.redis.hset(
                    f"rate_limit:{key}",
                    mapping={
                        "last_refill": current_time,
                        "tokens": tokens_available
                    }
                )
                return False
            
            # Consume tokens
            tokens_available -= tokens
            await self.redis.hset(
                f"rate_limit:{key}",
                mapping={
                    "last_refill": current_time,
                    "tokens": tokens_available
                }
            )
            
            # Record token consumption for analytics
            await self.redis.zadd(
                f"rate_limit_tokens:{key}",
                {str(current_time): current_time}
            )
            
            return True
            
        except Exception as e:
            logger.error("Rate limiter error", key=key, error=str(e))
            # Fail open - allow request if Redis is down
            return True
    
    async def get_remaining_tokens(self, key: str) -> int:
        """Get remaining tokens in bucket."""
        try:
            bucket_data = await self.redis.hgetall(f"rate_limit:{key}")
            if not bucket_data:
                return self.capacity
            
            current_time = time.time()
            last_refill = float(bucket_data.get("last_refill", current_time))
            tokens_available = float(bucket_data.get("tokens", self.capacity))
            
            # Calculate tokens to add
            time_elapsed = current_time - last_refill
            tokens_to_add = time_elapsed * self.refill_rate
            tokens_available = min(self.capacity, tokens_available + tokens_to_add)
            
            return int(tokens_available)
            
        except Exception as e:
            logger.error("Failed to get remaining tokens", key=key, error=str(e))
            return self.capacity


class RateLimiter:
    """Multi-tier rate limiter for different scopes."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.buckets = {
            "global": TokenBucket(redis_client, capacity=10000, refill_rate=100),
            "tenant": TokenBucket(redis_client, capacity=1000, refill_rate=50),
            "user": TokenBucket(redis_client, capacity=100, refill_rate=10),
            "api_key": TokenBucket(redis_client, capacity=500, refill_rate=25)
        }
    
    async def is_allowed(
        self, 
        scope: str, 
        identifier: str, 
        tokens: int = 1
    ) -> bool:
        """Check if request is allowed for scope and identifier."""
        if scope not in self.buckets:
            logger.warning("Unknown rate limit scope", scope=scope)
            return True
        
        key = f"{scope}:{identifier}"
        return await self.buckets[scope].is_allowed(key, tokens)
    
    async def is_tenant_allowed(
        self, 
        tenant_id: UUID, 
        tokens: int = 1
    ) -> bool:
        """Check if tenant request is allowed."""
        return await self.is_allowed("tenant", str(tenant_id), tokens)
    
    async def is_user_allowed(
        self, 
        user_id: UUID, 
        tokens: int = 1
    ) -> bool:
        """Check if user request is allowed."""
        return await self.is_allowed("user", str(user_id), tokens)
    
    async def is_api_key_allowed(
        self, 
        api_key_hash: str, 
        tokens: int = 1
    ) -> bool:
        """Check if API key request is allowed."""
        return await self.is_allowed("api_key", api_key_hash, tokens)
    
    async def get_remaining_tokens(
        self, 
        scope: str, 
        identifier: str
    ) -> int:
        """Get remaining tokens for scope and identifier."""
        if scope not in self.buckets:
            return 0
        
        key = f"{scope}:{identifier}"
        return await self.buckets[scope].get_remaining_tokens(key)
    
    async def reset_limits(self, scope: str, identifier: str):
        """Reset rate limits for scope and identifier."""
        try:
            key = f"{scope}:{identifier}"
            await self.redis.delete(f"rate_limit:{key}")
            await self.redis.delete(f"rate_limit_tokens:{key}")
            logger.info("Rate limits reset", scope=scope, identifier=identifier)
        except Exception as e:
            logger.error("Failed to reset rate limits", 
                        scope=scope, 
                        identifier=identifier, 
                        error=str(e))