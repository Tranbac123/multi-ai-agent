"""Quota enforcer for tenant usage limits."""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from uuid import UUID
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from libs.clients.database import get_db_session

logger = structlog.get_logger(__name__)


class QuotaEnforcer:
    """Enforces tenant quotas and usage limits."""
    
    def __init__(self):
        self.quota_types = [
            "max_messages_per_month",
            "max_customers", 
            "max_agents",
            "max_storage_mb"
        ]
    
    async def check_quota(
        self, 
        tenant_id: UUID, 
        quota_type: str, 
        current_usage: int,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Check if tenant is within quota limits."""
        try:
            # Get tenant plan and quotas
            tenant_stmt = select("tenants").where("tenants.id == tenant_id")
            tenant_result = await db.execute(tenant_stmt)
            tenant = tenant_result.first()
            
            if not tenant:
                return {
                    "allowed": False,
                    "reason": "Tenant not found",
                    "quota_type": quota_type,
                    "current_usage": current_usage,
                    "quota_limit": 0
                }
            
            # Get plan quotas
            plan_stmt = select("plans").where("plans.id == tenant.plan")
            plan_result = await db.execute(plan_stmt)
            plan = plan_result.first()
            
            if not plan:
                return {
                    "allowed": False,
                    "reason": "Plan not found",
                    "quota_type": quota_type,
                    "current_usage": current_usage,
                    "quota_limit": 0
                }
            
            quota_limit = plan.quotas.get(quota_type, 0)
            
            if quota_limit == 0:  # Unlimited
                return {
                    "allowed": True,
                    "reason": "Unlimited quota",
                    "quota_type": quota_type,
                    "current_usage": current_usage,
                    "quota_limit": -1
                }
            
            if current_usage >= quota_limit:
                return {
                    "allowed": False,
                    "reason": "Quota exceeded",
                    "quota_type": quota_type,
                    "current_usage": current_usage,
                    "quota_limit": quota_limit
                }
            
            return {
                "allowed": True,
                "reason": "Within quota",
                "quota_type": quota_type,
                "current_usage": current_usage,
                "quota_limit": quota_limit
            }
            
        except Exception as e:
            logger.error("Quota check failed", 
                        tenant_id=tenant_id, 
                        quota_type=quota_type, 
                        error=str(e))
            return {
                "allowed": False,
                "reason": "Quota check failed",
                "quota_type": quota_type,
                "current_usage": current_usage,
                "quota_limit": 0
            }
    
    async def get_current_usage(
        self, 
        tenant_id: UUID, 
        quota_type: str, 
        db: AsyncSession
    ) -> int:
        """Get current usage for quota type."""
        try:
            if quota_type == "max_messages_per_month":
                return await self._get_message_usage(tenant_id, db)
            elif quota_type == "max_customers":
                return await self._get_customer_count(tenant_id, db)
            elif quota_type == "max_agents":
                return await self._get_agent_count(tenant_id, db)
            elif quota_type == "max_storage_mb":
                return await self._get_storage_usage(tenant_id, db)
            else:
                logger.warning("Unknown quota type", quota_type=quota_type)
                return 0
                
        except Exception as e:
            logger.error("Failed to get current usage", 
                        tenant_id=tenant_id, 
                        quota_type=quota_type, 
                        error=str(e))
            return 0
    
    async def _get_message_usage(self, tenant_id: UUID, db: AsyncSession) -> int:
        """Get message usage for current month."""
        try:
            # Get current month start
            now = datetime.utcnow()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Count messages in current month
            stmt = select(func.count("messages.id")).where(
                and_(
                    "messages.tenant_id == tenant_id",
                    "messages.created_at >= month_start"
                )
            )
            result = await db.execute(stmt)
            count = result.scalar() or 0
            
            return count
            
        except Exception as e:
            logger.error("Failed to get message usage", tenant_id=tenant_id, error=str(e))
            return 0
    
    async def _get_customer_count(self, tenant_id: UUID, db: AsyncSession) -> int:
        """Get customer count for tenant."""
        try:
            stmt = select(func.count("customers.id")).where(
                "customers.tenant_id == tenant_id"
            )
            result = await db.execute(stmt)
            count = result.scalar() or 0
            
            return count
            
        except Exception as e:
            logger.error("Failed to get customer count", tenant_id=tenant_id, error=str(e))
            return 0
    
    async def _get_agent_count(self, tenant_id: UUID, db: AsyncSession) -> int:
        """Get agent count for tenant."""
        try:
            stmt = select(func.count("users.id")).where(
                and_(
                    "users.tenant_id == tenant_id",
                    "users.role.in_(['agent', 'admin'])"
                )
            )
            result = await db.execute(stmt)
            count = result.scalar() or 0
            
            return count
            
        except Exception as e:
            logger.error("Failed to get agent count", tenant_id=tenant_id, error=str(e))
            return 0
    
    async def _get_storage_usage(self, tenant_id: UUID, db: AsyncSession) -> int:
        """Get storage usage in MB for tenant."""
        try:
            # This would typically query a file storage table
            # For now, return 0 as placeholder
            return 0
            
        except Exception as e:
            logger.error("Failed to get storage usage", tenant_id=tenant_id, error=str(e))
            return 0
    
    async def enforce_quota(
        self, 
        tenant_id: UUID, 
        quota_type: str, 
        db: AsyncSession
    ) -> bool:
        """Enforce quota and return True if allowed."""
        try:
            current_usage = await self.get_current_usage(tenant_id, quota_type, db)
            quota_check = await self.check_quota(tenant_id, quota_type, current_usage, db)
            
            if not quota_check["allowed"]:
                logger.warning("Quota exceeded", 
                             tenant_id=tenant_id, 
                             quota_type=quota_type,
                             current_usage=current_usage,
                             quota_limit=quota_check["quota_limit"])
                return False
            
            return True
            
        except Exception as e:
            logger.error("Quota enforcement failed", 
                        tenant_id=tenant_id, 
                        quota_type=quota_type, 
                        error=str(e))
            return False
    
    async def get_quota_status(
        self, 
        tenant_id: UUID, 
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get complete quota status for tenant."""
        try:
            status = {}
            
            for quota_type in self.quota_types:
                current_usage = await self.get_current_usage(tenant_id, quota_type, db)
                quota_check = await self.check_quota(tenant_id, quota_type, current_usage, db)
                
                status[quota_type] = {
                    "current_usage": current_usage,
                    "quota_limit": quota_check["quota_limit"],
                    "allowed": quota_check["allowed"],
                    "reason": quota_check["reason"]
                }
            
            return status
            
        except Exception as e:
            logger.error("Failed to get quota status", tenant_id=tenant_id, error=str(e))
            return {}