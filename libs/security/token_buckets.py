"""
Token Bucket Implementation for Rate Limiting

Implements token bucket algorithm for per-tenant rate limiting
with Redis backing for distributed rate limiting.
"""

import asyncio
import time
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass
import structlog
from datetime import datetime, timedelta

logger = structlog.get_logger(__name__)


@dataclass
class TokenBucketConfig:
    """Token bucket configuration."""
    
    capacity: int  # Maximum number of tokens
    refill_rate: float  # Tokens per second
    burst_capacity: Optional[int] = None  # Optional burst capacity
    refill_interval_ms: int = 1000  # Refill interval in milliseconds


@dataclass
class TokenBucketState:
    """Token bucket state."""
    
    tokens: float
    last_refill: float
    burst_tokens: float = 0.0
    total_requests: int = 0
    successful_requests: int = 0
    blocked_requests: int = 0


class TokenBucket:
    """Token bucket implementation for rate limiting."""
    
    def __init__(self, config: TokenBucketConfig, redis_client=None):
        self.config = config
        self.redis_client = redis_client
        self.state = TokenBucketState(
            tokens=float(config.capacity),
            last_refill=time.time()
        )
        
        # Redis key prefix for distributed rate limiting
        self.redis_prefix = "token_bucket"
        
        logger.info("Token bucket initialized", 
                   capacity=config.capacity,
                   refill_rate=config.refill_rate,
                   burst_capacity=config.burst_capacity)
    
    async def consume(self, tokens: int = 1) -> Tuple[bool, Dict[str, Any]]:
        """Consume tokens from the bucket."""
        
        if self.redis_client:
            return await self._consume_distributed(tokens)
        else:
            return await self._consume_local(tokens)
    
    async def _consume_local(self, tokens: int) -> Tuple[bool, Dict[str, Any]]:
        """Consume tokens from local bucket."""
        
        current_time = time.time()
        
        # Refill tokens based on time elapsed
        self._refill_tokens(current_time)
        
        # Check if we have enough tokens
        if self.state.tokens >= tokens:
            self.state.tokens -= tokens
            self.state.total_requests += 1
            self.state.successful_requests += 1
            
            logger.debug("Tokens consumed successfully", 
                        tokens_requested=tokens,
                        tokens_remaining=self.state.tokens)
            
            return True, {
                "tokens_consumed": tokens,
                "tokens_remaining": self.state.tokens,
                "success": True
            }
        else:
            self.state.total_requests += 1
            self.state.blocked_requests += 1
            
            logger.debug("Token consumption blocked", 
                        tokens_requested=tokens,
                        tokens_available=self.state.tokens)
            
            return False, {
                "tokens_requested": tokens,
                "tokens_available": self.state.tokens,
                "success": False,
                "retry_after_seconds": self._calculate_retry_after(tokens)
            }
    
    async def _consume_distributed(self, tokens: int) -> Tuple[bool, Dict[str, Any]]:
        """Consume tokens from distributed bucket using Redis."""
        
        try:
            # Use Redis Lua script for atomic operation
            lua_script = """
            local key = KEYS[1]
            local capacity = tonumber(ARGV[1])
            local refill_rate = tonumber(ARGV[2])
            local tokens_requested = tonumber(ARGV[3])
            local current_time = tonumber(ARGV[4])
            
            local bucket_data = redis.call('HMGET', key, 'tokens', 'last_refill')
            local current_tokens = tonumber(bucket_data[1]) or capacity
            local last_refill = tonumber(bucket_data[2]) or current_time
            
            -- Calculate tokens to refill
            local time_elapsed = current_time - last_refill
            local tokens_to_refill = time_elapsed * refill_rate
            local new_tokens = math.min(capacity, current_tokens + tokens_to_refill)
            
            -- Check if we have enough tokens
            if new_tokens >= tokens_requested then
                new_tokens = new_tokens - tokens_requested
                redis.call('HMSET', key, 'tokens', new_tokens, 'last_refill', current_time)
                redis.call('EXPIRE', key, 3600) -- 1 hour TTL
                return {1, new_tokens}
            else
                redis.call('HMSET', key, 'tokens', new_tokens, 'last_refill', current_time)
                redis.call('EXPIRE', key, 3600)
                return {0, new_tokens}
            end
            """
            
            current_time = time.time()
            result = await self.redis_client.eval(
                lua_script,
                1,  # Number of keys
                f"{self.redis_prefix}:bucket",  # Redis key
                self.config.capacity,  # Capacity
                self.config.refill_rate,  # Refill rate
                tokens,  # Tokens requested
                current_time  # Current time
            )
            
            success = bool(result[0])
            tokens_remaining = result[1]
            
            if success:
                logger.debug("Distributed tokens consumed successfully", 
                            tokens_requested=tokens,
                            tokens_remaining=tokens_remaining)
                
                return True, {
                    "tokens_consumed": tokens,
                    "tokens_remaining": tokens_remaining,
                    "success": True
                }
            else:
                retry_after = self._calculate_retry_after(tokens)
                
                logger.debug("Distributed token consumption blocked", 
                            tokens_requested=tokens,
                            tokens_available=tokens_remaining)
                
                return False, {
                    "tokens_requested": tokens,
                    "tokens_available": tokens_remaining,
                    "success": False,
                    "retry_after_seconds": retry_after
                }
                
        except Exception as e:
            logger.error("Error in distributed token consumption", error=str(e))
            # Fallback to local consumption
            return await self._consume_local(tokens)
    
    def _refill_tokens(self, current_time: float):
        """Refill tokens based on time elapsed."""
        
        time_elapsed = current_time - self.state.last_refill
        tokens_to_refill = time_elapsed * self.config.refill_rate
        
        # Refill main bucket
        self.state.tokens = min(
            self.config.capacity,
            self.state.tokens + tokens_to_refill
        )
        
        # Refill burst bucket if configured
        if self.config.burst_capacity:
            self.state.burst_tokens = min(
                self.config.burst_capacity,
                self.state.burst_tokens + tokens_to_refill
            )
        
        self.state.last_refill = current_time
    
    def _calculate_retry_after(self, tokens_requested: int) -> float:
        """Calculate retry after time for blocked requests."""
        
        if tokens_requested <= 0:
            return 0.0
        
        # Calculate time needed to refill enough tokens
        tokens_needed = tokens_requested - self.state.tokens
        if tokens_needed <= 0:
            return 0.0
        
        retry_after = tokens_needed / self.config.refill_rate
        return max(0.0, retry_after)
    
    async def get_state(self) -> Dict[str, Any]:
        """Get current bucket state."""
        
        current_time = time.time()
        self._refill_tokens(current_time)
        
        return {
            "tokens": self.state.tokens,
            "capacity": self.config.capacity,
            "refill_rate": self.config.refill_rate,
            "burst_tokens": self.state.burst_tokens,
            "burst_capacity": self.config.burst_capacity,
            "total_requests": self.state.total_requests,
            "successful_requests": self.state.successful_requests,
            "blocked_requests": self.state.blocked_requests,
            "success_rate": (
                self.state.successful_requests / max(1, self.state.total_requests)
            ),
            "utilization": (
                (self.config.capacity - self.state.tokens) / self.config.capacity
            )
        }
    
    async def reset(self):
        """Reset bucket to initial state."""
        
        self.state = TokenBucketState(
            tokens=float(self.config.capacity),
            last_refill=time.time()
        )
        
        # Reset Redis state if using distributed mode
        if self.redis_client:
            try:
                await self.redis_client.delete(f"{self.redis_prefix}:bucket")
            except Exception as e:
                logger.error("Error resetting distributed bucket", error=str(e))


class TenantRateLimiter:
    """Rate limiter for multiple tenants with different configurations."""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.tenant_buckets: Dict[str, TokenBucket] = {}
        self.default_configs = self._get_default_configs()
        
        logger.info("Tenant rate limiter initialized")
    
    def _get_default_configs(self) -> Dict[str, TokenBucketConfig]:
        """Get default rate limiting configurations for different tenant tiers."""
        
        return {
            "free": TokenBucketConfig(
                capacity=100,  # 100 requests
                refill_rate=1.0,  # 1 request per second
                burst_capacity=10  # 10 burst requests
            ),
            "standard": TokenBucketConfig(
                capacity=1000,  # 1000 requests
                refill_rate=10.0,  # 10 requests per second
                burst_capacity=50  # 50 burst requests
            ),
            "premium": TokenBucketConfig(
                capacity=10000,  # 10000 requests
                refill_rate=100.0,  # 100 requests per second
                burst_capacity=500  # 500 burst requests
            ),
            "enterprise": TokenBucketConfig(
                capacity=100000,  # 100000 requests
                refill_rate=1000.0,  # 1000 requests per second
                burst_capacity=5000  # 5000 burst requests
            )
        }
    
    async def get_or_create_bucket(
        self, 
        tenant_id: str, 
        tenant_tier: str = "standard"
    ) -> TokenBucket:
        """Get or create token bucket for a tenant."""
        
        if tenant_id not in self.tenant_buckets:
            config = self.default_configs.get(tenant_tier, self.default_configs["standard"])
            
            # Create bucket with tenant-specific Redis key
            bucket = TokenBucket(config, self.redis_client)
            bucket.redis_prefix = f"token_bucket:{tenant_id}"
            
            self.tenant_buckets[tenant_id] = bucket
            
            logger.info("Token bucket created for tenant", 
                       tenant_id=tenant_id,
                       tier=tenant_tier,
                       capacity=config.capacity,
                       refill_rate=config.refill_rate)
        
        return self.tenant_buckets[tenant_id]
    
    async def check_rate_limit(
        self, 
        tenant_id: str, 
        tokens: int = 1,
        tenant_tier: str = "standard"
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check if tenant can consume tokens."""
        
        bucket = await self.get_or_create_bucket(tenant_id, tenant_tier)
        success, result = await bucket.consume(tokens)
        
        # Add tenant information to result
        result["tenant_id"] = tenant_id
        result["tenant_tier"] = tenant_tier
        
        return success, result
    
    async def get_tenant_metrics(self, tenant_id: str) -> Dict[str, Any]:
        """Get rate limiting metrics for a tenant."""
        
        if tenant_id not in self.tenant_buckets:
            return {"error": "Tenant not found"}
        
        bucket = self.tenant_buckets[tenant_id]
        state = await bucket.get_state()
        
        return {
            "tenant_id": tenant_id,
            "bucket_state": state,
            "timestamp": datetime.now().isoformat()
        }
    
    async def reset_tenant_bucket(self, tenant_id: str):
        """Reset rate limiting for a tenant."""
        
        if tenant_id in self.tenant_buckets:
            bucket = self.tenant_buckets[tenant_id]
            await bucket.reset()
            
            logger.info("Token bucket reset for tenant", tenant_id=tenant_id)
    
    async def update_tenant_tier(self, tenant_id: str, new_tier: str):
        """Update tenant tier and recreate bucket with new configuration."""
        
        if new_tier not in self.default_configs:
            raise ValueError(f"Invalid tenant tier: {new_tier}")
        
        # Remove old bucket
        if tenant_id in self.tenant_buckets:
            del self.tenant_buckets[tenant_id]
        
        # Create new bucket with new tier
        await self.get_or_create_bucket(tenant_id, new_tier)
        
        logger.info("Tenant tier updated", 
                   tenant_id=tenant_id,
                   new_tier=new_tier)
    
    def get_all_tenant_metrics(self) -> Dict[str, Any]:
        """Get metrics for all tenants."""
        
        return {
            "total_tenants": len(self.tenant_buckets),
            "tenant_ids": list(self.tenant_buckets.keys()),
            "timestamp": datetime.now().isoformat()
        }
    
    async def cleanup_inactive_tenants(self, max_inactive_hours: int = 24):
        """Clean up inactive tenant buckets."""
        
        # This would typically check Redis TTL or last activity
        # For now, we'll just log the operation
        logger.info("Cleanup of inactive tenants requested", 
                   max_inactive_hours=max_inactive_hours)
