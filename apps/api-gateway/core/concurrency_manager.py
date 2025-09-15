"""Concurrency Manager for per-tenant concurrency token management."""

from typing import Dict, Optional, Set
from dataclasses import dataclass
from enum import Enum
import asyncio
import time
import structlog
from redis.asyncio import Redis

logger = structlog.get_logger(__name__)


class PlanTier(Enum):
    """Tenant plan tiers with concurrency limits."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


@dataclass
class ConcurrencyLimits:
    """Concurrency limits for tenant plan."""
    max_concurrent_requests: int
    max_queue_depth: int
    priority_weight: int
    burst_limit: int
    refill_rate: float  # tokens per second


class ConcurrencyManager:
    """Manages per-tenant concurrency tokens and limits."""
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.token_pools: Dict[str, Set[str]] = {}  # tenant_id -> active_tokens
        self.plan_limits: Dict[PlanTier, ConcurrencyLimits] = {
            PlanTier.FREE: ConcurrencyLimits(
                max_concurrent_requests=5,
                max_queue_depth=10,
                priority_weight=1,
                burst_limit=10,
                refill_rate=1.0
            ),
            PlanTier.PRO: ConcurrencyLimits(
                max_concurrent_requests=20,
                max_queue_depth=50,
                priority_weight=3,
                burst_limit=30,
                refill_rate=3.0
            ),
            PlanTier.ENTERPRISE: ConcurrencyLimits(
                max_concurrent_requests=100,
                max_queue_depth=200,
                priority_weight=10,
                burst_limit=150,
                refill_rate=10.0
            )
        }
        self._start_token_refiller()
    
    def _start_token_refiller(self):
        """Start background task to refill tokens."""
        asyncio.create_task(self._refill_tokens_periodically())
    
    async def acquire_token(self, tenant_id: str, plan: str) -> bool:
        """Acquire concurrency token for tenant based on plan limits."""
        try:
            # Get plan tier
            try:
                plan_tier = PlanTier(plan.lower())
            except ValueError:
                logger.warning("Unknown plan tier, using free tier", tenant_id=tenant_id, plan=plan)
                plan_tier = PlanTier.FREE
            
            limits = self.plan_limits[plan_tier]
            
            # Check current token count
            current_tokens = await self._get_current_tokens(tenant_id)
            
            if current_tokens >= limits.max_concurrent_requests:
                logger.warning("Tenant concurrency limit exceeded",
                             tenant_id=tenant_id,
                             current_tokens=current_tokens,
                             max_tokens=limits.max_concurrent_requests)
                return False
            
            # Acquire token
            token_id = f"{tenant_id}:{int(time.time() * 1000000)}"
            success = await self._acquire_token_redis(tenant_id, token_id, limits)
            
            if success:
                # Track token locally
                if tenant_id not in self.token_pools:
                    self.token_pools[tenant_id] = set()
                self.token_pools[tenant_id].add(token_id)
                
                logger.info("Concurrency token acquired",
                           tenant_id=tenant_id,
                           token_id=token_id,
                           current_tokens=current_tokens + 1,
                           plan=plan_tier.value)
            
            return success
            
        except Exception as e:
            logger.error("Failed to acquire concurrency token",
                        tenant_id=tenant_id,
                        plan=plan,
                        error=str(e))
            return False
    
    async def release_token(self, tenant_id: str, token_id: Optional[str] = None):
        """Release concurrency token when request completes."""
        try:
            if tenant_id in self.token_pools:
                if token_id:
                    # Release specific token
                    self.token_pools[tenant_id].discard(token_id)
                    await self._release_token_redis(tenant_id, token_id)
                else:
                    # Release oldest token
                    if self.token_pools[tenant_id]:
                        oldest_token = min(self.token_pools[tenant_id])
                        self.token_pools[tenant_id].discard(oldest_token)
                        await self._release_token_redis(tenant_id, oldest_token)
                
                logger.info("Concurrency token released",
                           tenant_id=tenant_id,
                           token_id=token_id,
                           remaining_tokens=len(self.token_pools[tenant_id]))
            
        except Exception as e:
            logger.error("Failed to release concurrency token",
                        tenant_id=tenant_id,
                        token_id=token_id,
                        error=str(e))
    
    async def get_tenant_limits(self, tenant_id: str, plan: str) -> ConcurrencyLimits:
        """Get tenant's concurrency limits based on plan."""
        try:
            plan_tier = PlanTier(plan.lower())
            return self.plan_limits[plan_tier]
        except ValueError:
            logger.warning("Unknown plan tier, returning free tier limits", tenant_id=tenant_id, plan=plan)
            return self.plan_limits[PlanTier.FREE]
    
    async def get_tenant_stats(self, tenant_id: str) -> Dict[str, int]:
        """Get tenant's current concurrency statistics."""
        try:
            current_tokens = await self._get_current_tokens(tenant_id)
            queue_depth = await self._get_queue_depth(tenant_id)
            
            return {
                "current_tokens": current_tokens,
                "queue_depth": queue_depth,
                "active_tokens": len(self.token_pools.get(tenant_id, set()))
            }
            
        except Exception as e:
            logger.error("Failed to get tenant stats", tenant_id=tenant_id, error=str(e))
            return {"current_tokens": 0, "queue_depth": 0, "active_tokens": 0}
    
    async def _get_current_tokens(self, tenant_id: str) -> int:
        """Get current number of active tokens for tenant."""
        try:
            key = f"concurrency:tokens:{tenant_id}"
            tokens = await self.redis.scard(key)
            return tokens
        except Exception as e:
            logger.error("Failed to get current tokens", tenant_id=tenant_id, error=str(e))
            return 0
    
    async def _get_queue_depth(self, tenant_id: str) -> int:
        """Get current queue depth for tenant."""
        try:
            key = f"concurrency:queue:{tenant_id}"
            queue_depth = await self.redis.llen(key)
            return queue_depth
        except Exception as e:
            logger.error("Failed to get queue depth", tenant_id=tenant_id, error=str(e))
            return 0
    
    async def _acquire_token_redis(self, tenant_id: str, token_id: str, limits: ConcurrencyLimits) -> bool:
        """Acquire token using Redis for distributed coordination."""
        try:
            key = f"concurrency:tokens:{tenant_id}"
            
            # Use Redis transaction to atomically check and acquire
            async with self.redis.pipeline() as pipe:
                await pipe.scard(key)
                await pipe.sadd(key, token_id)
                await pipe.expire(key, 3600)  # 1 hour expiration
                results = await pipe.execute()
            
            current_count = results[0]
            if current_count >= limits.max_concurrent_requests:
                # Remove token if we exceeded limit
                await self.redis.srem(key, token_id)
                return False
            
            return True
            
        except Exception as e:
            logger.error("Failed to acquire token in Redis", tenant_id=tenant_id, error=str(e))
            return False
    
    async def _release_token_redis(self, tenant_id: str, token_id: str):
        """Release token using Redis."""
        try:
            key = f"concurrency:tokens:{tenant_id}"
            await self.redis.srem(key, token_id)
        except Exception as e:
            logger.error("Failed to release token in Redis", tenant_id=tenant_id, error=str(e))
    
    async def _refill_tokens_periodically(self):
        """Background task to refill tokens periodically."""
        while True:
            try:
                await asyncio.sleep(1.0)  # Refill every second
                
                # Get all active tenants
                pattern = "concurrency:tokens:*"
                keys = await self.redis.keys(pattern)
                
                for key in keys:
                    tenant_id = key.split(":")[-1]
                    await self._refill_tenant_tokens(tenant_id)
                    
            except Exception as e:
                logger.error("Error in token refiller", error=str(e))
                await asyncio.sleep(5.0)  # Wait longer on error
    
    async def _refill_tenant_tokens(self, tenant_id: str):
        """Refill tokens for a specific tenant."""
        try:
            # This would typically get the tenant's plan from database
            # For now, we'll use a default refill rate
            refill_rate = 1.0  # tokens per second
            
            # Implement token bucket refill logic here
            # This is a simplified version
            
        except Exception as e:
            logger.error("Failed to refill tenant tokens", tenant_id=tenant_id, error=str(e))
    
    async def get_system_stats(self) -> Dict[str, any]:
        """Get system-wide concurrency statistics."""
        try:
            stats = {
                "total_active_tokens": 0,
                "total_queue_depth": 0,
                "tenant_stats": {}
            }
            
            # Get stats for all tenants
            pattern = "concurrency:tokens:*"
            keys = await self.redis.keys(pattern)
            
            for key in keys:
                tenant_id = key.split(":")[-1]
                tenant_stats = await self.get_tenant_stats(tenant_id)
                stats["tenant_stats"][tenant_id] = tenant_stats
                stats["total_active_tokens"] += tenant_stats["current_tokens"]
                stats["total_queue_depth"] += tenant_stats["queue_depth"]
            
            return stats
            
        except Exception as e:
            logger.error("Failed to get system stats", error=str(e))
            return {"total_active_tokens": 0, "total_queue_depth": 0, "tenant_stats": {}}
