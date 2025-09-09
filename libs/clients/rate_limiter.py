"""Rate limiter using Redis token bucket algorithm."""

import asyncio
import time
import json
from typing import Optional, Dict, Any
import redis.asyncio as redis
import structlog

logger = structlog.get_logger(__name__)


class TokenBucketRateLimiter:
    """Token bucket rate limiter implementation."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.script = """
        local key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local tokens = tonumber(ARGV[2])
        local interval = tonumber(ARGV[3])
        local now = tonumber(ARGV[4])
        
        local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
        local current_tokens = tonumber(bucket[1]) or capacity
        local last_refill = tonumber(bucket[2]) or now
        
        -- Calculate tokens to add based on time elapsed
        local time_passed = now - last_refill
        local tokens_to_add = math.floor(time_passed / interval) * tokens
        current_tokens = math.min(capacity, current_tokens + tokens_to_add)
        
        -- Check if we have enough tokens
        if current_tokens >= 1 then
            current_tokens = current_tokens - 1
            redis.call('HMSET', key, 'tokens', current_tokens, 'last_refill', now)
            redis.call('EXPIRE', key, 3600)  -- Expire after 1 hour
            return {1, current_tokens, capacity}
        else
            redis.call('HMSET', key, 'tokens', current_tokens, 'last_refill', now)
            redis.call('EXPIRE', key, 3600)
            return {0, current_tokens, capacity}
        end
        """
    
    async def is_allowed(
        self,
        tenant_id: str,
        plan: str,
        scope: str,
        capacity: int,
        tokens_per_interval: int,
        interval_seconds: int
    ) -> tuple[bool, int, int]:
        """
        Check if request is allowed and consume token.
        
        Returns:
            (is_allowed, remaining_tokens, capacity)
        """
        key = f"rate_limit:{tenant_id}:{plan}:{scope}"
        now = int(time.time())
        
        try:
            result = await self.redis.eval(
                self.script,
                keys=[key],
                args=[capacity, tokens_per_interval, interval_seconds, now]
            )
            
            is_allowed = bool(result[0])
            remaining_tokens = int(result[1])
            capacity = int(result[2])
            
            logger.info(
                "Rate limit check",
                tenant_id=tenant_id,
                plan=plan,
                scope=scope,
                is_allowed=is_allowed,
                remaining_tokens=remaining_tokens,
                capacity=capacity
            )
            
            return is_allowed, remaining_tokens, capacity
            
        except Exception as e:
            logger.error(
                "Rate limiter error",
                error=str(e),
                tenant_id=tenant_id,
                plan=plan,
                scope=scope
            )
            # Fail open - allow request if rate limiter fails
            return True, capacity, capacity


class QuotaEnforcer:
    """Quota enforcer for tenant usage limits."""
    
    def __init__(self, redis_client: redis.Redis, db_client):
        self.redis = redis_client
        self.db_client = db_client
        self.rate_limiter = TokenBucketRateLimiter(redis_client)
    
    async def check_quota(
        self,
        tenant_id: str,
        plan: str,
        scope: str,
        usage_type: str
    ) -> tuple[bool, Dict[str, Any]]:
        """
        Check if tenant has quota remaining for the given usage type.
        
        Returns:
            (is_allowed, quota_info)
        """
        try:
            # Get plan quotas from database
            plan_quotas = await self._get_plan_quotas(plan)
            if not plan_quotas:
                logger.warning("Plan not found", plan=plan, tenant_id=tenant_id)
                return False, {"error": "Plan not found"}
            
            # Get current usage for the day
            current_usage = await self._get_current_usage(tenant_id)
            
            # Check quota limits
            quota_info = {
                "plan": plan,
                "scope": scope,
                "usage_type": usage_type,
                "limits": plan_quotas,
                "current_usage": current_usage,
                "remaining": {}
            }
            
            # Check each quota type
            for quota_type, limit in plan_quotas.items():
                current = current_usage.get(quota_type, 0)
                remaining = max(0, limit - current)
                quota_info["remaining"][quota_type] = remaining
                
                if current >= limit:
                    logger.warning(
                        "Quota exceeded",
                        tenant_id=tenant_id,
                        plan=plan,
                        quota_type=quota_type,
                        current=current,
                        limit=limit
                    )
                    return False, quota_info
            
            # Check rate limits
            rate_limit_config = plan_quotas.get("rate_limits", {})
            scope_config = rate_limit_config.get(scope, {})
            
            if scope_config:
                capacity = scope_config.get("capacity", 1000)
                tokens_per_interval = scope_config.get("tokens_per_interval", 100)
                interval_seconds = scope_config.get("interval_seconds", 60)
                
                is_allowed, remaining_tokens, capacity = await self.rate_limiter.is_allowed(
                    tenant_id, plan, scope, capacity, tokens_per_interval, interval_seconds
                )
                
                quota_info["rate_limit"] = {
                    "is_allowed": is_allowed,
                    "remaining_tokens": remaining_tokens,
                    "capacity": capacity
                }
                
                if not is_allowed:
                    logger.warning(
                        "Rate limit exceeded",
                        tenant_id=tenant_id,
                        plan=plan,
                        scope=scope,
                        remaining_tokens=remaining_tokens,
                        capacity=capacity
                    )
                    return False, quota_info
            
            return True, quota_info
            
        except Exception as e:
            logger.error(
                "Quota check error",
                error=str(e),
                tenant_id=tenant_id,
                plan=plan,
                scope=scope
            )
            # Fail open - allow request if quota check fails
            return True, {"error": "Quota check failed"}
    
    async def _get_plan_quotas(self, plan: str) -> Optional[Dict[str, Any]]:
        """Get plan quotas from database."""
        try:
            async with self.db_client.get_session() as session:
                from sqlalchemy import text
                result = await session.execute(
                    text("SELECT quotas FROM plans WHERE id = :plan"),
                    {"plan": plan}
                )
                row = result.fetchone()
                if row:
                    return row[0]
                return None
        except Exception as e:
            logger.error("Failed to get plan quotas", error=str(e), plan=plan)
            return None
    
    async def _get_current_usage(self, tenant_id: str) -> Dict[str, int]:
        """Get current usage for tenant today."""
        try:
            from datetime import date
            today = date.today()
            
            async with self.db_client.get_session(tenant_id) as session:
                from sqlalchemy import text
                result = await session.execute(
                    text("""
                        SELECT tokens_in, tokens_out, tool_calls, ws_minutes, storage_mb
                        FROM usage_counters
                        WHERE tenant_id = :tenant_id AND day = :day
                    """),
                    {"tenant_id": tenant_id, "day": today}
                )
                row = result.fetchone()
                
                if row:
                    return {
                        "tokens_in": row[0] or 0,
                        "tokens_out": row[1] or 0,
                        "tool_calls": row[2] or 0,
                        "ws_minutes": row[3] or 0,
                        "storage_mb": row[4] or 0
                    }
                else:
                    return {
                        "tokens_in": 0,
                        "tokens_out": 0,
                        "tool_calls": 0,
                        "ws_minutes": 0,
                        "storage_mb": 0
                    }
        except Exception as e:
            logger.error("Failed to get current usage", error=str(e), tenant_id=tenant_id)
            return {}
    
    async def increment_usage(
        self,
        tenant_id: str,
        usage_type: str,
        amount: int
    ) -> bool:
        """Increment usage counter for tenant."""
        try:
            from datetime import date
            today = date.today()
            
            async with self.db_client.get_session(tenant_id) as session:
                from sqlalchemy import text
                await session.execute(
                    text("""
                        INSERT INTO usage_counters (tenant_id, day, {usage_type})
                        VALUES (:tenant_id, :day, :amount)
                        ON CONFLICT (tenant_id, day)
                        DO UPDATE SET {usage_type} = usage_counters.{usage_type} + :amount
                    """.format(usage_type=usage_type)),
                    {"tenant_id": tenant_id, "day": today, "amount": amount}
                )
                await session.commit()
                
                logger.info(
                    "Usage incremented",
                    tenant_id=tenant_id,
                    usage_type=usage_type,
                    amount=amount,
                    day=today
                )
                return True
                
        except Exception as e:
            logger.error(
                "Failed to increment usage",
                error=str(e),
                tenant_id=tenant_id,
                usage_type=usage_type,
                amount=amount
            )
            return False