"""Usage tracker for metered billing."""

import asyncio
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import structlog
import redis.asyncio as redis

logger = structlog.get_logger(__name__)


class UsageType(Enum):
    """Usage types for billing."""
    TOKENS_IN = "tokens_in"
    TOKENS_OUT = "tokens_out"
    TOOL_CALLS = "tool_calls"
    WS_MINUTES = "ws_minutes"
    STORAGE_MB = "storage_mb"
    API_CALLS = "api_calls"


@dataclass
class UsageRecord:
    """Usage record for billing."""
    tenant_id: str
    usage_type: UsageType
    quantity: float
    timestamp: float
    metadata: Dict[str, Any] = None


@dataclass
class UsageLimit:
    """Usage limit for a tenant."""
    tenant_id: str
    usage_type: UsageType
    limit: float
    period: str  # daily, monthly, yearly
    reset_time: float


class UsageTracker:
    """Usage tracker for metered billing."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.usage_limits = {}
        self.pricing_rates = {}
    
    def set_usage_limit(
        self,
        tenant_id: str,
        usage_type: UsageType,
        limit: float,
        period: str = "monthly"
    ) -> None:
        """Set usage limit for a tenant."""
        try:
            limit_key = f"usage_limit:{tenant_id}:{usage_type.value}"
            
            # Calculate reset time based on period
            reset_time = self._calculate_reset_time(period)
            
            usage_limit = UsageLimit(
                tenant_id=tenant_id,
                usage_type=usage_type,
                limit=limit,
                period=period,
                reset_time=reset_time
            )
            
            self.usage_limits[limit_key] = usage_limit
            
            # Store in Redis
            asyncio.create_task(self._store_usage_limit(usage_limit))
            
            logger.info(
                "Usage limit set",
                tenant_id=tenant_id,
                usage_type=usage_type.value,
                limit=limit,
                period=period
            )
            
        except Exception as e:
            logger.error("Failed to set usage limit", error=str(e))
    
    def set_pricing_rate(
        self,
        usage_type: UsageType,
        rate: float,
        unit: str = "per_unit"
    ) -> None:
        """Set pricing rate for usage type."""
        try:
            self.pricing_rates[usage_type.value] = {
                'rate': rate,
                'unit': unit
            }
            
            logger.info(
                "Pricing rate set",
                usage_type=usage_type.value,
                rate=rate,
                unit=unit
            )
            
        except Exception as e:
            logger.error("Failed to set pricing rate", error=str(e))
    
    async def record_usage(
        self,
        tenant_id: str,
        usage_type: UsageType,
        quantity: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Record usage for a tenant."""
        try:
            # Create usage record
            usage_record = UsageRecord(
                tenant_id=tenant_id,
                usage_type=usage_type,
                quantity=quantity,
                timestamp=time.time(),
                metadata=metadata or {}
            )
            
            # Store usage record
            await self._store_usage_record(usage_record)
            
            # Update usage counters
            await self._update_usage_counters(usage_record)
            
            # Check usage limits
            await self._check_usage_limits(tenant_id, usage_type)
            
            logger.info(
                "Usage recorded",
                tenant_id=tenant_id,
                usage_type=usage_type.value,
                quantity=quantity
            )
            
            return True
            
        except Exception as e:
            logger.error("Failed to record usage", error=str(e))
            return False
    
    async def get_usage_summary(
        self,
        tenant_id: str,
        usage_type: UsageType,
        period: str = "monthly"
    ) -> Dict[str, Any]:
        """Get usage summary for a tenant."""
        try:
            # Get usage data
            usage_data = await self._get_usage_data(tenant_id, usage_type, period)
            
            # Calculate summary
            total_usage = sum(record['quantity'] for record in usage_data)
            usage_count = len(usage_data)
            
            # Get usage limit
            limit_key = f"usage_limit:{tenant_id}:{usage_type.value}"
            usage_limit = self.usage_limits.get(limit_key)
            
            # Calculate cost
            cost = await self._calculate_cost(usage_type, total_usage)
            
            return {
                'tenant_id': tenant_id,
                'usage_type': usage_type.value,
                'period': period,
                'total_usage': total_usage,
                'usage_count': usage_count,
                'usage_limit': usage_limit.limit if usage_limit else None,
                'usage_percentage': (total_usage / usage_limit.limit * 100) if usage_limit else 0,
                'cost': cost,
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error("Failed to get usage summary", error=str(e))
            return {'error': str(e)}
    
    async def get_all_usage_summary(
        self,
        tenant_id: str,
        period: str = "monthly"
    ) -> Dict[str, Any]:
        """Get usage summary for all usage types."""
        try:
            summary = {
                'tenant_id': tenant_id,
                'period': period,
                'usage_types': {},
                'total_cost': 0,
                'timestamp': time.time()
            }
            
            # Get summary for each usage type
            for usage_type in UsageType:
                usage_summary = await self.get_usage_summary(tenant_id, usage_type, period)
                summary['usage_types'][usage_type.value] = usage_summary
                summary['total_cost'] += usage_summary.get('cost', 0)
            
            return summary
            
        except Exception as e:
            logger.error("Failed to get all usage summary", error=str(e))
            return {'error': str(e)}
    
    async def check_usage_limit(
        self,
        tenant_id: str,
        usage_type: UsageType,
        additional_usage: float = 0
    ) -> Dict[str, Any]:
        """Check if usage limit would be exceeded."""
        try:
            # Get current usage
            current_usage = await self._get_current_usage(tenant_id, usage_type)
            
            # Get usage limit
            limit_key = f"usage_limit:{tenant_id}:{usage_type.value}"
            usage_limit = self.usage_limits.get(limit_key)
            
            if not usage_limit:
                return {
                    'within_limit': True,
                    'current_usage': current_usage,
                    'usage_limit': None,
                    'remaining_usage': None
                }
            
            # Check if additional usage would exceed limit
            projected_usage = current_usage + additional_usage
            within_limit = projected_usage <= usage_limit.limit
            
            return {
                'within_limit': within_limit,
                'current_usage': current_usage,
                'usage_limit': usage_limit.limit,
                'remaining_usage': max(0, usage_limit.limit - current_usage),
                'projected_usage': projected_usage
            }
            
        except Exception as e:
            logger.error("Failed to check usage limit", error=str(e))
            return {'error': str(e)}
    
    async def _store_usage_record(self, usage_record: UsageRecord) -> None:
        """Store usage record in Redis."""
        try:
            # Store individual record
            record_key = f"usage_record:{usage_record.tenant_id}:{usage_record.usage_type.value}:{int(usage_record.timestamp)}"
            
            record_data = {
                'tenant_id': usage_record.tenant_id,
                'usage_type': usage_record.usage_type.value,
                'quantity': usage_record.quantity,
                'timestamp': usage_record.timestamp,
                'metadata': str(usage_record.metadata) if usage_record.metadata else '{}'
            }
            
            await self.redis.hset(record_key, mapping=record_data)
            await self.redis.expire(record_key, 86400 * 365)  # 1 year TTL
            
            # Add to usage list for easy retrieval
            usage_list_key = f"usage_list:{usage_record.tenant_id}:{usage_record.usage_type.value}"
            await self.redis.lpush(usage_list_key, record_key)
            await self.redis.ltrim(usage_list_key, 0, 9999)  # Keep last 10k records
            
        except Exception as e:
            logger.error("Failed to store usage record", error=str(e))
    
    async def _update_usage_counters(self, usage_record: UsageRecord) -> None:
        """Update usage counters."""
        try:
            # Update daily counter
            daily_key = f"usage_daily:{usage_record.tenant_id}:{usage_record.usage_type.value}:{int(usage_record.timestamp // 86400)}"
            await self.redis.incrbyfloat(daily_key, usage_record.quantity)
            await self.redis.expire(daily_key, 86400 * 30)  # 30 days TTL
            
            # Update monthly counter
            monthly_key = f"usage_monthly:{usage_record.tenant_id}:{usage_record.usage_type.value}:{int(usage_record.timestamp // (86400 * 30))}"
            await self.redis.incrbyfloat(monthly_key, usage_record.quantity)
            await self.redis.expire(monthly_key, 86400 * 365)  # 1 year TTL
            
            # Update yearly counter
            yearly_key = f"usage_yearly:{usage_record.tenant_id}:{usage_record.usage_type.value}:{int(usage_record.timestamp // (86400 * 365))}"
            await self.redis.incrbyfloat(yearly_key, usage_record.quantity)
            await self.redis.expire(yearly_key, 86400 * 365 * 2)  # 2 years TTL
            
        except Exception as e:
            logger.error("Failed to update usage counters", error=str(e))
    
    async def _check_usage_limits(self, tenant_id: str, usage_type: UsageType) -> None:
        """Check usage limits and trigger alerts if exceeded."""
        try:
            limit_key = f"usage_limit:{tenant_id}:{usage_type.value}"
            usage_limit = self.usage_limits.get(limit_key)
            
            if not usage_limit:
                return
            
            # Get current usage
            current_usage = await self._get_current_usage(tenant_id, usage_type)
            
            # Check if limit is exceeded
            if current_usage > usage_limit.limit:
                # Trigger limit exceeded alert
                await self._trigger_limit_exceeded_alert(tenant_id, usage_type, current_usage, usage_limit.limit)
                
        except Exception as e:
            logger.error("Failed to check usage limits", error=str(e))
    
    async def _get_usage_data(
        self,
        tenant_id: str,
        usage_type: UsageType,
        period: str
    ) -> List[Dict[str, Any]]:
        """Get usage data for a period."""
        try:
            if period == "daily":
                # Get today's usage
                today = int(time.time() // 86400)
                daily_key = f"usage_daily:{tenant_id}:{usage_type.value}:{today}"
                usage = await self.redis.get(daily_key)
                return [{'quantity': float(usage) if usage else 0, 'timestamp': time.time()}]
            
            elif period == "monthly":
                # Get this month's usage
                month = int(time.time() // (86400 * 30))
                monthly_key = f"usage_monthly:{tenant_id}:{usage_type.value}:{month}"
                usage = await self.redis.get(monthly_key)
                return [{'quantity': float(usage) if usage else 0, 'timestamp': time.time()}]
            
            elif period == "yearly":
                # Get this year's usage
                year = int(time.time() // (86400 * 365))
                yearly_key = f"usage_yearly:{tenant_id}:{usage_type.value}:{year}"
                usage = await self.redis.get(yearly_key)
                return [{'quantity': float(usage) if usage else 0, 'timestamp': time.time()}]
            
            else:
                # Get all usage records
                usage_list_key = f"usage_list:{tenant_id}:{usage_type.value}"
                record_keys = await self.redis.lrange(usage_list_key, 0, 9999)
                
                usage_data = []
                for record_key in record_keys:
                    record_data = await self.redis.hgetall(record_key)
                    if record_data:
                        usage_data.append({
                            'quantity': float(record_data['quantity']),
                            'timestamp': float(record_data['timestamp'])
                        })
                
                return usage_data
                
        except Exception as e:
            logger.error("Failed to get usage data", error=str(e))
            return []
    
    async def _get_current_usage(self, tenant_id: str, usage_type: UsageType) -> float:
        """Get current usage for a tenant."""
        try:
            # Get monthly usage (current period)
            month = int(time.time() // (86400 * 30))
            monthly_key = f"usage_monthly:{tenant_id}:{usage_type.value}:{month}"
            usage = await self.redis.get(monthly_key)
            
            return float(usage) if usage else 0.0
            
        except Exception as e:
            logger.error("Failed to get current usage", error=str(e))
            return 0.0
    
    async def _calculate_cost(self, usage_type: UsageType, quantity: float) -> float:
        """Calculate cost for usage."""
        try:
            pricing_rate = self.pricing_rates.get(usage_type.value)
            if not pricing_rate:
                return 0.0
            
            return quantity * pricing_rate['rate']
            
        except Exception as e:
            logger.error("Failed to calculate cost", error=str(e))
            return 0.0
    
    async def _store_usage_limit(self, usage_limit: UsageLimit) -> None:
        """Store usage limit in Redis."""
        try:
            limit_key = f"usage_limit:{usage_limit.tenant_id}:{usage_limit.usage_type.value}"
            
            limit_data = {
                'tenant_id': usage_limit.tenant_id,
                'usage_type': usage_limit.usage_type.value,
                'limit': usage_limit.limit,
                'period': usage_limit.period,
                'reset_time': usage_limit.reset_time
            }
            
            await self.redis.hset(limit_key, mapping=limit_data)
            await self.redis.expire(limit_key, 86400 * 365)  # 1 year TTL
            
        except Exception as e:
            logger.error("Failed to store usage limit", error=str(e))
    
    async def _trigger_limit_exceeded_alert(
        self,
        tenant_id: str,
        usage_type: UsageType,
        current_usage: float,
        limit: float
    ) -> None:
        """Trigger limit exceeded alert."""
        try:
            # Store alert
            alert_key = f"usage_alert:{tenant_id}:{usage_type.value}:{int(time.time())}"
            
            alert_data = {
                'tenant_id': tenant_id,
                'usage_type': usage_type.value,
                'current_usage': current_usage,
                'limit': limit,
                'excess_usage': current_usage - limit,
                'timestamp': time.time()
            }
            
            await self.redis.hset(alert_key, mapping=alert_data)
            await self.redis.expire(alert_key, 86400 * 7)  # 7 days TTL
            
            logger.warning(
                "Usage limit exceeded",
                tenant_id=tenant_id,
                usage_type=usage_type.value,
                current_usage=current_usage,
                limit=limit
            )
            
        except Exception as e:
            logger.error("Failed to trigger limit exceeded alert", error=str(e))
    
    def _calculate_reset_time(self, period: str) -> float:
        """Calculate reset time for usage limit."""
        current_time = time.time()
        
        if period == "daily":
            # Reset at midnight
            return current_time + (86400 - (current_time % 86400))
        elif period == "monthly":
            # Reset at beginning of next month
            return current_time + (86400 * 30 - (current_time % (86400 * 30)))
        elif period == "yearly":
            # Reset at beginning of next year
            return current_time + (86400 * 365 - (current_time % (86400 * 365)))
        else:
            return current_time + 86400  # Default to daily
