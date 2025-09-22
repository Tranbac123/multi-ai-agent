"""Invoice preview and quota enforcement for billing service."""

import asyncio
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import structlog
import redis.asyncio as redis
from datetime import datetime, timezone, timedelta

from apps.billing-service.src.core.usage_tracker import UsageTracker, UsageType, UsageRecord
from apps.billing-service.src.core.billing_engine import BillingEngine, Invoice, InvoiceStatus, BillingItem

logger = structlog.get_logger(__name__)


class QuotaStatus(Enum):
    """Quota status."""
    WITHIN_LIMITS = "within_limits"
    APPROACHING_LIMIT = "approaching_limit"
    EXCEEDED = "exceeded"
    UNLIMITED = "unlimited"


@dataclass
class QuotaLimit:
    """Quota limit definition."""
    usage_type: UsageType
    limit: float
    current_usage: float
    reset_period: str  # "monthly", "daily", "hourly"
    reset_date: datetime
    status: QuotaStatus
    warning_threshold: float = 0.8  # 80% of limit


@dataclass
class InvoicePreview:
    """Invoice preview."""
    preview_id: str
    tenant_id: str
    billing_period_start: datetime
    billing_period_end: datetime
    items: List[BillingItem]
    subtotal: float
    tax_amount: float
    total_amount: float
    currency: str
    usage_summary: Dict[str, Any]
    quota_status: List[QuotaLimit]
    generated_at: datetime


class InvoicePreviewService:
    """Service for generating invoice previews and enforcing quotas."""
    
    def __init__(self, redis_client: redis.Redis, usage_tracker: UsageTracker, billing_engine: BillingEngine):
        self.redis_client = redis_client
        self.usage_tracker = usage_tracker
        self.billing_engine = billing_engine
        
        # Pricing configuration
        self.pricing_rates = {
            UsageType.TOKENS: 0.0001,  # $0.0001 per token
            UsageType.TOOL_CALLS: 0.01,  # $0.01 per tool call
            UsageType.WS_CONNECTIONS: 0.05,  # $0.05 per minute
            UsageType.STORAGE: 0.10,  # $0.10 per MB
            UsageType.API_CALLS: 0.001,  # $0.001 per API call
        }
        
        # Default quota limits
        self.default_quotas = {
            UsageType.TOKENS: 1000000,  # 1M tokens per month
            UsageType.TOOL_CALLS: 10000,  # 10K tool calls per month
            UsageType.WS_CONNECTIONS: 1000,  # 1K minutes per month
            UsageType.STORAGE: 1000,  # 1GB per month
            UsageType.API_CALLS: 100000,  # 100K API calls per month
        }
    
    async def generate_invoice_preview(
        self,
        tenant_id: str,
        billing_period_start: Optional[datetime] = None,
        billing_period_end: Optional[datetime] = None
    ) -> InvoicePreview:
        """Generate invoice preview for a tenant."""
        if billing_period_start is None:
            billing_period_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        if billing_period_end is None:
            if billing_period_start.month == 12:
                billing_period_end = billing_period_start.replace(year=billing_period_start.year + 1, month=1)
            else:
                billing_period_end = billing_period_start.replace(month=billing_period_start.month + 1)
        
        # Get usage data for the period
        usage_data = await self._get_usage_for_period(tenant_id, billing_period_start, billing_period_end)
        
        # Generate billing items
        items = await self._generate_billing_items(usage_data)
        
        # Calculate totals
        subtotal = sum(item.total_price for item in items)
        tax_rate = 0.08  # 8% tax rate
        tax_amount = subtotal * tax_rate
        total_amount = subtotal + tax_amount
        
        # Get quota status
        quota_status = await self._get_quota_status(tenant_id, usage_data)
        
        # Generate usage summary
        usage_summary = self._generate_usage_summary(usage_data)
        
        preview = InvoicePreview(
            preview_id=f"preview_{tenant_id}_{int(time.time())}",
            tenant_id=tenant_id,
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
            items=items,
            subtotal=subtotal,
            tax_amount=tax_amount,
            total_amount=total_amount,
            currency="USD",
            usage_summary=usage_summary,
            quota_status=quota_status,
            generated_at=datetime.now(timezone.utc)
        )
        
        # Cache the preview
        await self._cache_preview(preview)
        
        logger.info("Invoice preview generated", 
                   preview_id=preview.preview_id,
                   tenant_id=tenant_id,
                   total_amount=total_amount)
        
        return preview
    
    async def check_quota_status(self, tenant_id: str, usage_type: UsageType) -> QuotaStatus:
        """Check quota status for a specific usage type."""
        # Get current usage
        current_usage = await self.usage_tracker.get_current_usage(tenant_id, usage_type)
        
        # Get quota limit
        quota_limit = await self._get_quota_limit(tenant_id, usage_type)
        
        if quota_limit is None:
            return QuotaStatus.UNLIMITED
        
        if current_usage >= quota_limit:
            return QuotaStatus.EXCEEDED
        elif current_usage >= quota_limit * 0.8:  # 80% threshold
            return QuotaStatus.APPROACHING_LIMIT
        else:
            return QuotaStatus.WITHIN_LIMITS
    
    async def enforce_quota(self, tenant_id: str, usage_type: UsageType, requested_amount: float) -> Tuple[bool, str]:
        """Enforce quota limits for a request."""
        current_usage = await self.usage_tracker.get_current_usage(tenant_id, usage_type)
        quota_limit = await self._get_quota_limit(tenant_id, usage_type)
        
        if quota_limit is None:
            return True, "Unlimited quota"
        
        if current_usage + requested_amount > quota_limit:
            return False, f"Quota exceeded for {usage_type.value}. Current: {current_usage}, Limit: {quota_limit}, Requested: {requested_amount}"
        
        return True, "Within quota limits"
    
    async def get_quota_limits(self, tenant_id: str) -> List[QuotaLimit]:
        """Get all quota limits for a tenant."""
        limits = []
        
        for usage_type in UsageType:
            limit_value = await self._get_quota_limit(tenant_id, usage_type)
            if limit_value is not None:
                current_usage = await self.usage_tracker.get_current_usage(tenant_id, usage_type)
                status = await self.check_quota_status(tenant_id, usage_type)
                
                limits.append(QuotaLimit(
                    usage_type=usage_type,
                    limit=limit_value,
                    current_usage=current_usage,
                    reset_period="monthly",
                    reset_date=self._get_next_reset_date(),
                    status=status
                ))
        
        return limits
    
    async def _get_usage_for_period(
        self,
        tenant_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[UsageType, List[UsageRecord]]:
        """Get usage data for a specific period."""
        usage_data = {}
        
        for usage_type in UsageType:
            records = await self.usage_tracker.get_usage_records(
                tenant_id=tenant_id,
                usage_type=usage_type,
                start_date=start_date,
                end_date=end_date
            )
            usage_data[usage_type] = records
        
        return usage_data
    
    async def _generate_billing_items(self, usage_data: Dict[UsageType, List[UsageRecord]]) -> List[BillingItem]:
        """Generate billing items from usage data."""
        items = []
        
        for usage_type, records in usage_data.items():
            if not records:
                continue
            
            total_quantity = sum(record.quantity for record in records)
            if total_quantity == 0:
                continue
            
            unit_price = self.pricing_rates.get(usage_type, 0.0)
            total_price = total_quantity * unit_price
            
            items.append(BillingItem(
                item_id=f"{usage_type.value}_{int(time.time())}",
                description=f"{usage_type.value.replace('_', ' ').title()} Usage",
                quantity=total_quantity,
                unit_price=unit_price,
                total_price=total_price,
                usage_type=usage_type,
                metadata={
                    "record_count": len(records),
                    "period_start": records[0].timestamp.isoformat() if records else None,
                    "period_end": records[-1].timestamp.isoformat() if records else None
                }
            ))
        
        return items
    
    async def _get_quota_limit(self, tenant_id: str, usage_type: UsageType) -> Optional[float]:
        """Get quota limit for a tenant and usage type."""
        # Check for tenant-specific quota
        quota_key = f"quota:{tenant_id}:{usage_type.value}"
        quota_data = await self.redis_client.get(quota_key)
        
        if quota_data:
            return float(quota_data)
        
        # Use default quota
        return self.default_quotas.get(usage_type)
    
    async def _get_quota_status(self, tenant_id: str, usage_data: Dict[UsageType, List[UsageRecord]]) -> List[QuotaLimit]:
        """Get quota status for all usage types."""
        limits = []
        
        for usage_type in UsageType:
            quota_limit = await self._get_quota_limit(tenant_id, usage_type)
            if quota_limit is None:
                continue
            
            current_usage = sum(record.quantity for record in usage_data.get(usage_type, []))
            status = await self.check_quota_status(tenant_id, usage_type)
            
            limits.append(QuotaLimit(
                usage_type=usage_type,
                limit=quota_limit,
                current_usage=current_usage,
                reset_period="monthly",
                reset_date=self._get_next_reset_date(),
                status=status
            ))
        
        return limits
    
    def _generate_usage_summary(self, usage_data: Dict[UsageType, List[UsageRecord]]) -> Dict[str, Any]:
        """Generate usage summary from usage data."""
        summary = {}
        
        for usage_type, records in usage_data.items():
            if not records:
                summary[usage_type.value] = {
                    "total_quantity": 0,
                    "record_count": 0,
                    "first_usage": None,
                    "last_usage": None
                }
                continue
            
            summary[usage_type.value] = {
                "total_quantity": sum(record.quantity for record in records),
                "record_count": len(records),
                "first_usage": records[0].timestamp.isoformat(),
                "last_usage": records[-1].timestamp.isoformat()
            }
        
        return summary
    
    def _get_next_reset_date(self) -> datetime:
        """Get the next quota reset date."""
        now = datetime.now(timezone.utc)
        if now.month == 12:
            return now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            return now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    
    async def _cache_preview(self, preview: InvoicePreview) -> None:
        """Cache invoice preview."""
        cache_key = f"invoice_preview:{preview.tenant_id}:{preview.preview_id}"
        cache_data = {
            "preview_id": preview.preview_id,
            "tenant_id": preview.tenant_id,
            "billing_period_start": preview.billing_period_start.isoformat(),
            "billing_period_end": preview.billing_period_end.isoformat(),
            "items": [
                {
                    "item_id": item.item_id,
                    "description": item.description,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "total_price": item.total_price,
                    "usage_type": item.usage_type.value,
                    "metadata": item.metadata
                }
                for item in preview.items
            ],
            "subtotal": preview.subtotal,
            "tax_amount": preview.tax_amount,
            "total_amount": preview.total_amount,
            "currency": preview.currency,
            "usage_summary": preview.usage_summary,
            "quota_status": [
                {
                    "usage_type": limit.usage_type.value,
                    "limit": limit.limit,
                    "current_usage": limit.current_usage,
                    "reset_period": limit.reset_period,
                    "reset_date": limit.reset_date.isoformat(),
                    "status": limit.status.value
                }
                for limit in preview.quota_status
            ],
            "generated_at": preview.generated_at.isoformat()
        }
        
        await self.redis_client.setex(cache_key, 3600, json.dumps(cache_data))  # 1 hour TTL
    
    async def get_cached_preview(self, tenant_id: str, preview_id: str) -> Optional[InvoicePreview]:
        """Get cached invoice preview."""
        cache_key = f"invoice_preview:{tenant_id}:{preview_id}"
        cache_data = await self.redis_client.get(cache_key)
        
        if not cache_data:
            return None
        
        data = json.loads(cache_data)
        
        # Reconstruct the preview object
        items = [
            BillingItem(
                item_id=item["item_id"],
                description=item["description"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                total_price=item["total_price"],
                usage_type=UsageType(item["usage_type"]),
                metadata=item["metadata"]
            )
            for item in data["items"]
        ]
        
        quota_status = [
            QuotaLimit(
                usage_type=UsageType(limit["usage_type"]),
                limit=limit["limit"],
                current_usage=limit["current_usage"],
                reset_period=limit["reset_period"],
                reset_date=datetime.fromisoformat(limit["reset_date"]),
                status=QuotaStatus(limit["status"])
            )
            for limit in data["quota_status"]
        ]
        
        return InvoicePreview(
            preview_id=data["preview_id"],
            tenant_id=data["tenant_id"],
            billing_period_start=datetime.fromisoformat(data["billing_period_start"]),
            billing_period_end=datetime.fromisoformat(data["billing_period_end"]),
            items=items,
            subtotal=data["subtotal"],
            tax_amount=data["tax_amount"],
            total_amount=data["total_amount"],
            currency=data["currency"],
            usage_summary=data["usage_summary"],
            quota_status=quota_status,
            generated_at=datetime.fromisoformat(data["generated_at"])
        )
