"""Billing engine for metered usage and invoicing."""

import asyncio
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import structlog
import redis.asyncio as redis

from apps.billing-service.src.core.usage_tracker import UsageTracker, UsageType

logger = structlog.get_logger(__name__)


class BillingStatus(Enum):
    """Billing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InvoiceStatus(Enum):
    """Invoice status."""
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


@dataclass
class BillingItem:
    """Billing item."""
    item_id: str
    description: str
    quantity: float
    unit_price: float
    total_price: float
    usage_type: UsageType
    metadata: Dict[str, Any] = None


@dataclass
class Invoice:
    """Invoice representation."""
    invoice_id: str
    tenant_id: str
    billing_period_start: float
    billing_period_end: float
    status: InvoiceStatus
    items: List[BillingItem]
    subtotal: float
    tax_amount: float
    total_amount: float
    created_at: float
    due_date: float
    paid_at: Optional[float] = None


class BillingEngine:
    """Billing engine for metered usage and invoicing."""
    
    def __init__(self, redis_client: redis.Redis, usage_tracker: UsageTracker):
        self.redis = redis_client
        self.usage_tracker = usage_tracker
        self.tax_rate = 0.1  # 10% tax rate
        self.invoice_due_days = 30
    
    async def generate_invoice(
        self,
        tenant_id: str,
        billing_period_start: float,
        billing_period_end: float
    ) -> str:
        """Generate invoice for a tenant."""
        try:
            invoice_id = f"inv_{int(time.time())}_{tenant_id}"
            
            # Get usage summary for billing period
            usage_summary = await self._get_usage_summary_for_period(
                tenant_id, billing_period_start, billing_period_end
            )
            
            # Create billing items
            items = await self._create_billing_items(usage_summary)
            
            # Calculate totals
            subtotal = sum(item.total_price for item in items)
            tax_amount = subtotal * self.tax_rate
            total_amount = subtotal + tax_amount
            
            # Create invoice
            invoice = Invoice(
                invoice_id=invoice_id,
                tenant_id=tenant_id,
                billing_period_start=billing_period_start,
                billing_period_end=billing_period_end,
                status=InvoiceStatus.DRAFT,
                items=items,
                subtotal=subtotal,
                tax_amount=tax_amount,
                total_amount=total_amount,
                created_at=time.time(),
                due_date=time.time() + (self.invoice_due_days * 86400)
            )
            
            # Store invoice
            await self._store_invoice(invoice)
            
            logger.info(
                "Invoice generated",
                invoice_id=invoice_id,
                tenant_id=tenant_id,
                total_amount=total_amount
            )
            
            return invoice_id
            
        except Exception as e:
            logger.error("Failed to generate invoice", error=str(e))
            raise
    
    async def process_payment(
        self,
        invoice_id: str,
        payment_amount: float,
        payment_method: str = "credit_card"
    ) -> bool:
        """Process payment for an invoice."""
        try:
            # Get invoice
            invoice = await self._get_invoice(invoice_id)
            if not invoice:
                raise ValueError(f"Invoice {invoice_id} not found")
            
            # Check if payment amount matches
            if abs(payment_amount - invoice.total_amount) > 0.01:
                logger.warning(
                    "Payment amount mismatch",
                    invoice_id=invoice_id,
                    expected=invoice.total_amount,
                    received=payment_amount
                )
                return False
            
            # Update invoice status
            invoice.status = InvoiceStatus.PAID
            invoice.paid_at = time.time()
            
            # Store updated invoice
            await self._store_invoice(invoice)
            
            # Record payment
            await self._record_payment(invoice_id, payment_amount, payment_method)
            
            logger.info(
                "Payment processed",
                invoice_id=invoice_id,
                payment_amount=payment_amount,
                payment_method=payment_method
            )
            
            return True
            
        except Exception as e:
            logger.error("Failed to process payment", error=str(e))
            return False
    
    async def get_invoice(self, invoice_id: str) -> Optional[Invoice]:
        """Get invoice by ID."""
        return await self._get_invoice(invoice_id)
    
    async def get_tenant_invoices(
        self,
        tenant_id: str,
        status: Optional[InvoiceStatus] = None,
        limit: int = 100
    ) -> List[Invoice]:
        """Get invoices for a tenant."""
        try:
            # Get invoice IDs
            pattern = f"invoice:{tenant_id}:*"
            keys = await self.redis.keys(pattern)
            
            invoices = []
            for key in keys:
                try:
                    invoice_id = key.decode().split(':')[-1]
                    invoice = await self._get_invoice(invoice_id)
                    
                    if invoice and (status is None or invoice.status == status):
                        invoices.append(invoice)
                        
                except Exception as e:
                    logger.error("Failed to parse invoice key", error=str(e), key=key)
            
            # Sort by creation date (newest first)
            invoices.sort(key=lambda x: x.created_at, reverse=True)
            
            return invoices[:limit]
            
        except Exception as e:
            logger.error("Failed to get tenant invoices", error=str(e))
            return []
    
    async def get_billing_summary(
        self,
        tenant_id: str,
        months: int = 12
    ) -> Dict[str, Any]:
        """Get billing summary for a tenant."""
        try:
            # Get invoices for the period
            invoices = await self.get_tenant_invoices(tenant_id)
            
            # Filter by date range
            cutoff_time = time.time() - (months * 30 * 86400)
            recent_invoices = [inv for inv in invoices if inv.created_at >= cutoff_time]
            
            # Calculate summary
            total_invoices = len(recent_invoices)
            total_amount = sum(inv.total_amount for inv in recent_invoices)
            paid_amount = sum(inv.total_amount for inv in recent_invoices if inv.status == InvoiceStatus.PAID)
            outstanding_amount = total_amount - paid_amount
            
            # Calculate average monthly bill
            avg_monthly_bill = total_amount / months if months > 0 else 0
            
            return {
                'tenant_id': tenant_id,
                'period_months': months,
                'total_invoices': total_invoices,
                'total_amount': total_amount,
                'paid_amount': paid_amount,
                'outstanding_amount': outstanding_amount,
                'average_monthly_bill': avg_monthly_bill,
                'invoices': [
                    {
                        'invoice_id': inv.invoice_id,
                        'status': inv.status.value,
                        'total_amount': inv.total_amount,
                        'created_at': inv.created_at,
                        'due_date': inv.due_date,
                        'paid_at': inv.paid_at
                    }
                    for inv in recent_invoices
                ]
            }
            
        except Exception as e:
            logger.error("Failed to get billing summary", error=str(e))
            return {'error': str(e)}
    
    async def _get_usage_summary_for_period(
        self,
        tenant_id: str,
        start_time: float,
        end_time: float
    ) -> Dict[str, Any]:
        """Get usage summary for a specific period."""
        try:
            # This would typically query usage data for the specific period
            # For now, we'll get current usage summary
            usage_summary = await self.usage_tracker.get_all_usage_summary(tenant_id)
            
            return usage_summary
            
        except Exception as e:
            logger.error("Failed to get usage summary for period", error=str(e))
            return {}
    
    async def _create_billing_items(self, usage_summary: Dict[str, Any]) -> List[BillingItem]:
        """Create billing items from usage summary."""
        try:
            items = []
            
            usage_types = usage_summary.get('usage_types', {})
            
            for usage_type_name, usage_data in usage_types.items():
                try:
                    usage_type = UsageType(usage_type_name)
                    quantity = usage_data.get('total_usage', 0)
                    cost = usage_data.get('cost', 0)
                    
                    if quantity > 0:
                        unit_price = cost / quantity if quantity > 0 else 0
                        
                        item = BillingItem(
                            item_id=f"item_{int(time.time())}_{usage_type_name}",
                            description=f"{usage_type_name.replace('_', ' ').title()} Usage",
                            quantity=quantity,
                            unit_price=unit_price,
                            total_price=cost,
                            usage_type=usage_type,
                            metadata={'usage_data': usage_data}
                        )
                        
                        items.append(item)
                        
                except Exception as e:
                    logger.error("Failed to create billing item", error=str(e), usage_type=usage_type_name)
            
            return items
            
        except Exception as e:
            logger.error("Failed to create billing items", error=str(e))
            return []
    
    async def _store_invoice(self, invoice: Invoice) -> None:
        """Store invoice in Redis."""
        try:
            invoice_key = f"invoice:{invoice.tenant_id}:{invoice.invoice_id}"
            
            invoice_data = {
                'invoice_id': invoice.invoice_id,
                'tenant_id': invoice.tenant_id,
                'billing_period_start': invoice.billing_period_start,
                'billing_period_end': invoice.billing_period_end,
                'status': invoice.status.value,
                'items': str(invoice.items),
                'subtotal': invoice.subtotal,
                'tax_amount': invoice.tax_amount,
                'total_amount': invoice.total_amount,
                'created_at': invoice.created_at,
                'due_date': invoice.due_date,
                'paid_at': invoice.paid_at or 0
            }
            
            await self.redis.hset(invoice_key, mapping=invoice_data)
            await self.redis.expire(invoice_key, 86400 * 365 * 2)  # 2 years TTL
            
        except Exception as e:
            logger.error("Failed to store invoice", error=str(e))
    
    async def _get_invoice(self, invoice_id: str) -> Optional[Invoice]:
        """Get invoice by ID."""
        try:
            # Search for invoice across all tenants
            pattern = f"invoice:*:{invoice_id}"
            keys = await self.redis.keys(pattern)
            
            if not keys:
                return None
            
            invoice_key = keys[0].decode()
            invoice_data = await self.redis.hgetall(invoice_key)
            
            if not invoice_data:
                return None
            
            # Parse items
            items_data = eval(invoice_data['items'])  # Note: In production, use proper JSON parsing
            items = [BillingItem(**item_data) for item_data in items_data]
            
            return Invoice(
                invoice_id=invoice_data['invoice_id'],
                tenant_id=invoice_data['tenant_id'],
                billing_period_start=float(invoice_data['billing_period_start']),
                billing_period_end=float(invoice_data['billing_period_end']),
                status=InvoiceStatus(invoice_data['status']),
                items=items,
                subtotal=float(invoice_data['subtotal']),
                tax_amount=float(invoice_data['tax_amount']),
                total_amount=float(invoice_data['total_amount']),
                created_at=float(invoice_data['created_at']),
                due_date=float(invoice_data['due_date']),
                paid_at=float(invoice_data['paid_at']) if invoice_data['paid_at'] != '0' else None
            )
            
        except Exception as e:
            logger.error("Failed to get invoice", error=str(e))
            return None
    
    async def _record_payment(
        self,
        invoice_id: str,
        payment_amount: float,
        payment_method: str
    ) -> None:
        """Record payment in Redis."""
        try:
            payment_key = f"payment:{invoice_id}:{int(time.time())}"
            
            payment_data = {
                'invoice_id': invoice_id,
                'payment_amount': payment_amount,
                'payment_method': payment_method,
                'timestamp': time.time()
            }
            
            await self.redis.hset(payment_key, mapping=payment_data)
            await self.redis.expire(payment_key, 86400 * 365 * 2)  # 2 years TTL
            
        except Exception as e:
            logger.error("Failed to record payment", error=str(e))
    
    async def get_payment_history(self, invoice_id: str) -> List[Dict[str, Any]]:
        """Get payment history for an invoice."""
        try:
            pattern = f"payment:{invoice_id}:*"
            keys = await self.redis.keys(pattern)
            
            payments = []
            for key in keys:
                try:
                    payment_data = await self.redis.hgetall(key)
                    if payment_data:
                        payments.append({
                            'invoice_id': payment_data['invoice_id'],
                            'payment_amount': float(payment_data['payment_amount']),
                            'payment_method': payment_data['payment_method'],
                            'timestamp': float(payment_data['timestamp'])
                        })
                except Exception as e:
                    logger.error("Failed to parse payment key", error=str(e), key=key)
            
            # Sort by timestamp (newest first)
            payments.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return payments
            
        except Exception as e:
            logger.error("Failed to get payment history", error=str(e))
            return []
    
    async def get_billing_statistics(self) -> Dict[str, Any]:
        """Get billing statistics."""
        try:
            # Get all invoices
            pattern = "invoice:*:*"
            keys = await self.redis.keys(pattern)
            
            stats = {
                'total_invoices': len(keys),
                'total_revenue': 0,
                'paid_invoices': 0,
                'outstanding_invoices': 0,
                'average_invoice_amount': 0,
                'invoices_by_status': {}
            }
            
            total_amount = 0
            paid_amount = 0
            
            for key in keys:
                try:
                    invoice_data = await self.redis.hgetall(key)
                    if invoice_data:
                        status = invoice_data['status']
                        amount = float(invoice_data['total_amount'])
                        
                        stats['invoices_by_status'][status] = stats['invoices_by_status'].get(status, 0) + 1
                        total_amount += amount
                        
                        if status == InvoiceStatus.PAID.value:
                            paid_amount += amount
                            stats['paid_invoices'] += 1
                        else:
                            stats['outstanding_invoices'] += 1
                            
                except Exception as e:
                    logger.error("Failed to parse invoice key", error=str(e), key=key)
            
            stats['total_revenue'] = total_amount
            stats['paid_revenue'] = paid_amount
            stats['outstanding_revenue'] = total_amount - paid_amount
            
            if stats['total_invoices'] > 0:
                stats['average_invoice_amount'] = total_amount / stats['total_invoices']
            
            return stats
            
        except Exception as e:
            logger.error("Failed to get billing statistics", error=str(e))
            return {'error': str(e)}