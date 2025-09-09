"""Billing engine for usage calculation and invoice generation."""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from uuid import UUID
from decimal import Decimal
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from libs.contracts.billing import BillingPlan, Invoice, UsageReport
from libs.clients.database import get_db_session

logger = structlog.get_logger(__name__)


class BillingEngine:
    """Core billing engine for usage calculation and invoice generation."""
    
    def __init__(self):
        self.usage_rates = {
            "tokens_in": Decimal("0.0001"),  # $0.0001 per token
            "tokens_out": Decimal("0.0002"),  # $0.0002 per token
            "tool_calls": Decimal("0.01"),    # $0.01 per tool call
            "ws_minutes": Decimal("0.05"),    # $0.05 per minute
            "storage_mb": Decimal("0.10")     # $0.10 per MB
        }
    
    async def get_plans(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """Get available billing plans."""
        try:
            stmt = select("plans").where("plans.is_active == True")
            result = await db.execute(stmt)
            rows = result.fetchall()
            
            plans = []
            for row in rows:
                plans.append({
                    "id": row.id,
                    "name": row.name,
                    "price_usd": float(row.price_usd),
                    "quotas": row.quotas,
                    "features": row.features
                })
            
            return plans
            
        except Exception as e:
            logger.error("Failed to get plans", error=str(e))
            return []
    
    async def get_invoices(
        self, 
        tenant_id: UUID, 
        limit: int, 
        offset: int, 
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Get invoices for tenant."""
        try:
            stmt = select("invoices").where(
                "invoices.tenant_id == tenant_id"
            ).order_by("invoices.created_at.desc()).limit(limit).offset(offset)
            
            result = await db.execute(stmt)
            rows = result.fetchall()
            
            invoices = []
            for row in rows:
                invoices.append({
                    "id": row.id,
                    "tenant_id": str(row.tenant_id),
                    "amount": float(row.amount),
                    "status": row.status,
                    "period_start": row.period_start.isoformat(),
                    "period_end": row.period_end.isoformat(),
                    "created_at": row.created_at.isoformat(),
                    "due_date": row.due_date.isoformat() if row.due_date else None
                })
            
            return invoices
            
        except Exception as e:
            logger.error("Failed to get invoices", tenant_id=tenant_id, error=str(e))
            return []
    
    async def preview_invoice(
        self, 
        tenant_id: UUID, 
        start_date: datetime, 
        end_date: datetime, 
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Preview invoice for tenant."""
        try:
            # Get tenant plan
            tenant_stmt = select("tenants").where("tenants.id == tenant_id")
            tenant_result = await db.execute(tenant_stmt)
            tenant = tenant_result.first()
            
            if not tenant:
                raise ValueError("Tenant not found")
            
            # Get usage for period
            usage_stmt = select("usage_counters").where(
                and_(
                    "usage_counters.tenant_id == tenant_id",
                    "usage_counters.day >= start_date",
                    "usage_counters.day <= end_date"
                )
            )
            usage_result = await db.execute(usage_stmt)
            usage_rows = usage_result.fetchall()
            
            # Calculate totals
            total_tokens_in = sum(row.tokens_in for row in usage_rows)
            total_tokens_out = sum(row.tokens_out for row in usage_rows)
            total_tool_calls = sum(row.tool_calls for row in usage_rows)
            total_ws_minutes = sum(row.ws_minutes for row in usage_rows)
            total_storage_mb = sum(row.storage_mb for row in usage_rows)
            
            # Calculate costs
            token_in_cost = total_tokens_in * self.usage_rates["tokens_in"]
            token_out_cost = total_tokens_out * self.usage_rates["tokens_out"]
            tool_calls_cost = total_tool_calls * self.usage_rates["tool_calls"]
            ws_minutes_cost = total_ws_minutes * self.usage_rates["ws_minutes"]
            storage_cost = total_storage_mb * self.usage_rates["storage_mb"]
            
            total_cost = (
                token_in_cost + token_out_cost + tool_calls_cost + 
                ws_minutes_cost + storage_cost
            )
            
            # Get plan base price
            plan_stmt = select("plans").where("plans.id == tenant.plan")
            plan_result = await db.execute(plan_stmt)
            plan = plan_result.first()
            
            base_price = Decimal(str(plan.price_usd)) if plan else Decimal("0")
            total_amount = base_price + total_cost
            
            return {
                "tenant_id": str(tenant_id),
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "base_price": float(base_price),
                "usage_breakdown": {
                    "tokens_in": {
                        "count": total_tokens_in,
                        "rate": float(self.usage_rates["tokens_in"]),
                        "cost": float(token_in_cost)
                    },
                    "tokens_out": {
                        "count": total_tokens_out,
                        "rate": float(self.usage_rates["tokens_out"]),
                        "cost": float(token_out_cost)
                    },
                    "tool_calls": {
                        "count": total_tool_calls,
                        "rate": float(self.usage_rates["tool_calls"]),
                        "cost": float(tool_calls_cost)
                    },
                    "ws_minutes": {
                        "count": total_ws_minutes,
                        "rate": float(self.usage_rates["ws_minutes"]),
                        "cost": float(ws_minutes_cost)
                    },
                    "storage_mb": {
                        "count": total_storage_mb,
                        "rate": float(self.usage_rates["storage_mb"]),
                        "cost": float(storage_cost)
                    }
                },
                "total_usage_cost": float(total_cost),
                "total_amount": float(total_amount)
            }
            
        except Exception as e:
            logger.error("Failed to preview invoice", 
                        tenant_id=tenant_id, 
                        error=str(e))
            raise
    
    async def daily_rollup(self, db: AsyncSession) -> Dict[str, Any]:
        """Run daily usage rollup job."""
        try:
            yesterday = datetime.utcnow().date() - timedelta(days=1)
            
            # Get all tenants with usage
            stmt = select("usage_counters").where(
                "usage_counters.day == yesterday"
            )
            result = await db.execute(stmt)
            usage_rows = result.fetchall()
            
            rollup_count = 0
            for row in usage_rows:
                # Check if invoice should be generated
                if await self._should_generate_invoice(row.tenant_id, db):
                    await self._generate_invoice(row.tenant_id, yesterday, db)
                    rollup_count += 1
            
            logger.info("Daily rollup completed", 
                       date=yesterday.isoformat(), 
                       invoices_generated=rollup_count)
            
            return {
                "date": yesterday.isoformat(),
                "invoices_generated": rollup_count,
                "status": "completed"
            }
            
        except Exception as e:
            logger.error("Daily rollup failed", error=str(e))
            raise
    
    async def _should_generate_invoice(self, tenant_id: UUID, db: AsyncSession) -> bool:
        """Check if invoice should be generated for tenant."""
        # Check if invoice already exists for this month
        month_start = datetime.utcnow().replace(day=1).date()
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        stmt = select("invoices").where(
            and_(
                "invoices.tenant_id == tenant_id",
                "invoices.period_start >= month_start",
                "invoices.period_end <= month_end"
            )
        )
        result = await db.execute(stmt)
        existing_invoice = result.first()
        
        return existing_invoice is None
    
    async def _generate_invoice(
        self, 
        tenant_id: UUID, 
        date: datetime, 
        db: AsyncSession
    ):
        """Generate invoice for tenant."""
        # Calculate month start/end
        month_start = date.replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1) - timedelta(days=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1) - timedelta(days=1)
        
        # Generate invoice preview
        preview = await self.preview_invoice(tenant_id, month_start, month_end, db)
        
        # Create invoice record
        invoice_data = {
            "id": str(uuid4()),
            "tenant_id": tenant_id,
            "amount": preview["total_amount"],
            "status": "pending",
            "period_start": month_start,
            "period_end": month_end,
            "due_date": month_end + timedelta(days=30),
            "created_at": datetime.utcnow()
        }
        
        stmt = insert("invoices").values(**invoice_data)
        await db.execute(stmt)
        await db.commit()
        
        logger.info("Invoice generated", 
                   tenant_id=tenant_id, 
                   invoice_id=invoice_data["id"],
                   amount=invoice_data["amount"])
