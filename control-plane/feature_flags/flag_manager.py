"""Feature flag manager with Redis caching and PostgreSQL persistence."""

import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from uuid import UUID
import structlog
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert

from libs.clients.database import get_db_session
from libs.contracts.tenant import TenantContext

logger = structlog.get_logger(__name__)


class FeatureFlag:
    """Feature flag definition."""
    
    def __init__(
        self,
        name: str,
        tenant_id: Optional[UUID] = None,
        enabled: bool = False,
        rollout_percentage: float = 0.0,
        conditions: Optional[Dict[str, Any]] = None,
        variants: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        self.name = name
        self.tenant_id = tenant_id
        self.enabled = enabled
        self.rollout_percentage = rollout_percentage
        self.conditions = conditions or {}
        self.variants = variants or {}
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "enabled": self.enabled,
            "rollout_percentage": self.rollout_percentage,
            "conditions": self.conditions,
            "variants": self.variants,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class FlagManager:
    """Feature flag manager with Redis caching."""
    
    def __init__(self, redis_client: redis.Redis, cache_ttl: int = 300):
        self.redis = redis_client
        self.cache_ttl = cache_ttl
    
    async def is_enabled(
        self, 
        flag_name: str, 
        tenant_id: UUID, 
        user_id: Optional[UUID] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if feature flag is enabled for tenant/user."""
        cache_key = f"flag:{flag_name}:{tenant_id}:{user_id or 'global'}"
        
        # Try cache first
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # Load from database
        flag = await self._load_flag(flag_name, tenant_id)
        if not flag:
            return False
        
        # Evaluate flag
        enabled = await self._evaluate_flag(flag, tenant_id, user_id, context or {})
        
        # Cache result
        await self.redis.setex(cache_key, self.cache_ttl, json.dumps(enabled))
        
        return enabled
    
    async def get_variant(
        self,
        flag_name: str,
        tenant_id: UUID,
        user_id: Optional[UUID] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Get feature flag variant for tenant/user."""
        flag = await self._load_flag(flag_name, tenant_id)
        if not flag or not flag.enabled:
            return None
        
        # Check rollout percentage
        if not await self._check_rollout(flag, tenant_id, user_id):
            return None
        
        # Return default variant or first available
        if flag.variants:
            return list(flag.variants.keys())[0]
        
        return None
    
    async def _load_flag(self, flag_name: str, tenant_id: UUID) -> Optional[FeatureFlag]:
        """Load flag from database."""
        async with get_db_session() as db:
            # Try tenant-specific flag first
            stmt = select("feature_flags").where(
                "feature_flags.name == flag_name",
                "feature_flags.tenant_id == tenant_id"
            )
            result = await db.execute(stmt)
            row = result.first()
            
            if row:
                return FeatureFlag(
                    name=row.name,
                    tenant_id=row.tenant_id,
                    enabled=row.enabled,
                    rollout_percentage=row.rollout_percentage,
                    conditions=row.conditions,
                    variants=row.variants,
                    created_at=row.created_at,
                    updated_at=row.updated_at
                )
            
            # Fall back to global flag
            stmt = select("feature_flags").where(
                "feature_flags.name == flag_name",
                "feature_flags.tenant_id.is_(None)"
            )
            result = await db.execute(stmt)
            row = result.first()
            
            if row:
                return FeatureFlag(
                    name=row.name,
                    tenant_id=None,
                    enabled=row.enabled,
                    rollout_percentage=row.rollout_percentage,
                    conditions=row.conditions,
                    variants=row.variants,
                    created_at=row.created_at,
                    updated_at=row.updated_at
                )
        
        return None
    
    async def _evaluate_flag(
        self,
        flag: FeatureFlag,
        tenant_id: UUID,
        user_id: Optional[UUID],
        context: Dict[str, Any]
    ) -> bool:
        """Evaluate flag conditions."""
        if not flag.enabled:
            return False
        
        # Check rollout percentage
        if not await self._check_rollout(flag, tenant_id, user_id):
            return False
        
        # Check conditions
        if flag.conditions:
            return await self._check_conditions(flag.conditions, context)
        
        return True
    
    async def _check_rollout(
        self,
        flag: FeatureFlag,
        tenant_id: UUID,
        user_id: Optional[UUID]
    ) -> bool:
        """Check if user should be included in rollout."""
        if flag.rollout_percentage >= 100.0:
            return True
        
        if flag.rollout_percentage <= 0.0:
            return False
        
        # Use deterministic hash for consistent rollout
        hash_input = f"{flag.name}:{tenant_id}:{user_id or 'global'}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest()[:8], 16)
        rollout_threshold = (hash_value % 100) + 1
        
        return rollout_threshold <= flag.rollout_percentage
    
    async def _check_conditions(
        self,
        conditions: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """Check flag conditions against context."""
        for key, expected_value in conditions.items():
            actual_value = context.get(key)
            
            if isinstance(expected_value, dict):
                # Range condition
                if "min" in expected_value and actual_value < expected_value["min"]:
                    return False
                if "max" in expected_value and actual_value > expected_value["max"]:
                    return False
            elif isinstance(expected_value, list):
                # List condition
                if actual_value not in expected_value:
                    return False
            else:
                # Exact match
                if actual_value != expected_value:
                    return False
        
        return True
    
    async def create_flag(self, flag: FeatureFlag) -> bool:
        """Create or update feature flag."""
        try:
            async with get_db_session() as db:
                stmt = pg_insert("feature_flags").values(
                    name=flag.name,
                    tenant_id=flag.tenant_id,
                    enabled=flag.enabled,
                    rollout_percentage=flag.rollout_percentage,
                    conditions=flag.conditions,
                    variants=flag.variants,
                    created_at=flag.created_at,
                    updated_at=flag.updated_at
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["name", "tenant_id"],
                    set_=dict(
                        enabled=flag.enabled,
                        rollout_percentage=flag.rollout_percentage,
                        conditions=flag.conditions,
                        variants=flag.variants,
                        updated_at=flag.updated_at
                    )
                )
                
                await db.execute(stmt)
                await db.commit()
                
                # Invalidate cache
                await self._invalidate_cache(flag.name, flag.tenant_id)
                
                logger.info("Feature flag created/updated", 
                           flag_name=flag.name, 
                           tenant_id=flag.tenant_id)
                return True
                
        except Exception as e:
            logger.error("Failed to create feature flag", 
                        flag_name=flag.name, 
                        error=str(e))
            return False
    
    async def _invalidate_cache(self, flag_name: str, tenant_id: Optional[UUID]):
        """Invalidate cache for flag."""
        pattern = f"flag:{flag_name}:{tenant_id or '*'}:*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)
