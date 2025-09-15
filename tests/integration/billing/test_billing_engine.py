"""Test billing engine functionality."""

import pytest
import time
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timezone

from apps.billing_service.core.billing_engine import (
    BillingEngine,
    BillingStatus,
    InvoiceStatus,
    BillingItem,
    Invoice,
)
from apps.billing_service.core.usage_tracker import UsageTracker, UsageType


class TestBillingEngine:
    """Test BillingEngine functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis_client = Mock()
        redis_client.hset = AsyncMock()
        redis_client.expire = AsyncMock()
        redis_client.keys = AsyncMock()
        redis_client.hgetall = AsyncMock()
        redis_client.get = AsyncMock()
        return redis_client

    @pytest.fixture
    def mock_usage_tracker(self):
        """Create mock usage tracker."""
        usage_tracker = Mock()
        usage_tracker.get_all_usage_summary = AsyncMock()
        return usage_tracker

    @pytest.fixture
    def billing_engine(self, mock_redis, mock_usage_tracker):
        """Create BillingEngine instance."""
        return BillingEngine(mock_redis, mock_usage_tracker)

    @pytest.fixture
    def sample_usage_summary(self):
        """Create sample usage summary."""
        return {
            "tenant_id": "tenant_123",
            "period": "monthly",
            "usage_types": {
                "tokens_in": {
                    "total_usage": 10000,
                    "cost": 0.05,
                    "usage_count": 100
                },
                "tokens_out": {
                    "total_usage": 5000,
                    "cost": 0.025,
                    "usage_count": 100
                },
                "api_calls": {
                    "total_usage": 1000,
                    "cost": 0.10,
                    "usage_count": 1000
                }
            },
            "total_cost": 0.175,
            "timestamp": time.time()
        }

    @pytest.mark.asyncio
    async def test_generate_invoice_success(self, billing_engine, mock_usage_tracker, sample_usage_summary):
        """Test successful invoice generation."""
        tenant_id = "tenant_123"
        start_time = time.time() - 86400 * 30  # 30 days ago
        end_time = time.time()
        
        # Mock usage summary
        mock_usage_tracker.get_all_usage_summary.return_value = sample_usage_summary
        
        invoice_id = await billing_engine.generate_invoice(tenant_id, start_time, end_time)
        
        # Verify invoice ID was generated
        assert invoice_id is not None
        assert invoice_id.startswith("inv_")
        assert tenant_id in invoice_id
        
        # Verify Redis storage was called
        billing_engine.redis.hset.assert_called_once()
        billing_engine.redis.expire.assert_called_once()
        
        # Verify usage tracker was called
        mock_usage_tracker.get_all_usage_summary.assert_called_once_with(tenant_id)

    @pytest.mark.asyncio
    async def test_generate_invoice_with_tax_calculation(self, billing_engine, mock_usage_tracker, sample_usage_summary):
        """Test invoice generation with tax calculation."""
        mock_usage_tracker.get_all_usage_summary.return_value = sample_usage_summary
        
        invoice_id = await billing_engine.generate_invoice("tenant_123", time.time() - 86400, time.time())
        
        # Get stored invoice data
        call_args = billing_engine.redis.hset.call_args
        invoice_data = call_args[0][1]
        
        # Verify tax calculation (10% tax rate)
        subtotal = float(invoice_data["subtotal"])
        tax_amount = float(invoice_data["tax_amount"])
        total_amount = float(invoice_data["total_amount"])
        
        assert tax_amount == subtotal * 0.1  # 10% tax
        assert total_amount == subtotal + tax_amount

    @pytest.mark.asyncio
    async def test_generate_invoice_error_handling(self, billing_engine, mock_usage_tracker):
        """Test invoice generation error handling."""
        mock_usage_tracker.get_all_usage_summary.side_effect = Exception("Usage tracker error")
        
        with pytest.raises(Exception, match="Usage tracker error"):
            await billing_engine.generate_invoice("tenant_123", time.time() - 86400, time.time())

    @pytest.mark.asyncio
    async def test_process_payment_success(self, billing_engine):
        """Test successful payment processing."""
        # Create a mock invoice
        invoice = Invoice(
            invoice_id="inv_test_123",
            tenant_id="tenant_123",
            billing_period_start=time.time() - 86400,
            billing_period_end=time.time(),
            status=InvoiceStatus.DRAFT,
            items=[],
            subtotal=100.0,
            tax_amount=10.0,
            total_amount=110.0,
            created_at=time.time(),
            due_date=time.time() + 86400 * 30
        )
        
        # Mock invoice retrieval
        with patch.object(billing_engine, '_get_invoice') as mock_get_invoice:
            mock_get_invoice.return_value = invoice
            
            # Mock invoice storage
            with patch.object(billing_engine, '_store_invoice') as mock_store_invoice:
                # Mock payment recording
                with patch.object(billing_engine, '_record_payment') as mock_record_payment:
                    result = await billing_engine.process_payment("inv_test_123", 110.0)
        
        assert result is True
        assert invoice.status == InvoiceStatus.PAID
        assert invoice.paid_at is not None
        mock_store_invoice.assert_called_once_with(invoice)
        mock_record_payment.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_payment_amount_mismatch(self, billing_engine):
        """Test payment processing with amount mismatch."""
        invoice = Invoice(
            invoice_id="inv_test_123",
            tenant_id="tenant_123",
            billing_period_start=time.time() - 86400,
            billing_period_end=time.time(),
            status=InvoiceStatus.DRAFT,
            items=[],
            subtotal=100.0,
            tax_amount=10.0,
            total_amount=110.0,
            created_at=time.time(),
            due_date=time.time() + 86400 * 30
        )
        
        with patch.object(billing_engine, '_get_invoice') as mock_get_invoice:
            mock_get_invoice.return_value = invoice
            
            result = await billing_engine.process_payment("inv_test_123", 100.0)  # Wrong amount
        
        assert result is False
        assert invoice.status == InvoiceStatus.DRAFT  # Status unchanged

    @pytest.mark.asyncio
    async def test_process_payment_invoice_not_found(self, billing_engine):
        """Test payment processing with non-existent invoice."""
        with patch.object(billing_engine, '_get_invoice') as mock_get_invoice:
            mock_get_invoice.return_value = None
            
            result = await billing_engine.process_payment("non_existent_invoice", 110.0)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_get_invoice_success(self, billing_engine):
        """Test getting invoice successfully."""
        invoice_data = {
            b"invoice_id": b"inv_test_123",
            b"tenant_id": b"tenant_123",
            b"billing_period_start": b"1640995200.0",
            b"billing_period_end": b"1643673600.0",
            b"status": b"draft",
            b"items": b"[]",
            b"subtotal": b"100.0",
            b"tax_amount": b"10.0",
            b"total_amount": b"110.0",
            b"created_at": b"1643673600.0",
            b"due_date": b"1646265600.0",
            b"paid_at": b"0"
        }
        
        billing_engine.redis.keys.return_value = [b"invoice:tenant_123:inv_test_123"]
        billing_engine.redis.hgetall.return_value = invoice_data
        
        invoice = await billing_engine.get_invoice("inv_test_123")
        
        assert invoice is not None
        assert invoice.invoice_id == "inv_test_123"
        assert invoice.tenant_id == "tenant_123"
        assert invoice.status == InvoiceStatus.DRAFT

    @pytest.mark.asyncio
    async def test_get_invoice_not_found(self, billing_engine):
        """Test getting non-existent invoice."""
        billing_engine.redis.keys.return_value = []
        
        invoice = await billing_engine.get_invoice("non_existent_invoice")
        
        assert invoice is None

    @pytest.mark.asyncio
    async def test_get_tenant_invoices_success(self, billing_engine):
        """Test getting tenant invoices successfully."""
        # Mock Redis keys
        billing_engine.redis.keys.return_value = [
            b"invoice:tenant_123:inv_1",
            b"invoice:tenant_123:inv_2"
        ]
        
        # Mock invoice data
        invoice_data_1 = {
            b"invoice_id": b"inv_1",
            b"tenant_id": b"tenant_123",
            b"status": b"draft",
            b"total_amount": b"100.0",
            b"created_at": b"1643673600.0"
        }
        invoice_data_2 = {
            b"invoice_id": b"inv_2",
            b"tenant_id": b"tenant_123",
            b"status": b"paid",
            b"total_amount": b"200.0",
            b"created_at": b"1643673700.0"
        }
        
        billing_engine.redis.hgetall.side_effect = [invoice_data_1, invoice_data_2]
        
        # Mock _get_invoice to return proper Invoice objects
        invoice_1 = Invoice(
            invoice_id="inv_1", tenant_id="tenant_123", billing_period_start=0,
            billing_period_end=0, status=InvoiceStatus.DRAFT, items=[],
            subtotal=100, tax_amount=10, total_amount=100, created_at=1643673600.0,
            due_date=0
        )
        invoice_2 = Invoice(
            invoice_id="inv_2", tenant_id="tenant_123", billing_period_start=0,
            billing_period_end=0, status=InvoiceStatus.PAID, items=[],
            subtotal=200, tax_amount=20, total_amount=200, created_at=1643673700.0,
            due_date=0
        )
        
        with patch.object(billing_engine, '_get_invoice') as mock_get_invoice:
            mock_get_invoice.side_effect = [invoice_1, invoice_2]
            
            invoices = await billing_engine.get_tenant_invoices("tenant_123")
        
        assert len(invoices) == 2
        assert invoices[0].invoice_id == "inv_2"  # Sorted by creation date (newest first)
        assert invoices[1].invoice_id == "inv_1"

    @pytest.mark.asyncio
    async def test_get_tenant_invoices_with_status_filter(self, billing_engine):
        """Test getting tenant invoices with status filter."""
        billing_engine.redis.keys.return_value = [b"invoice:tenant_123:inv_1"]
        
        invoice = Invoice(
            invoice_id="inv_1", tenant_id="tenant_123", billing_period_start=0,
            billing_period_end=0, status=InvoiceStatus.DRAFT, items=[],
            subtotal=100, tax_amount=10, total_amount=100, created_at=time.time(),
            due_date=0
        )
        
        with patch.object(billing_engine, '_get_invoice') as mock_get_invoice:
            mock_get_invoice.return_value = invoice
            
            # Filter for draft invoices
            invoices = await billing_engine.get_tenant_invoices("tenant_123", InvoiceStatus.DRAFT)
            assert len(invoices) == 1
            
            # Filter for paid invoices
            invoices = await billing_engine.get_tenant_invoices("tenant_123", InvoiceStatus.PAID)
            assert len(invoices) == 0

    @pytest.mark.asyncio
    async def test_get_billing_summary_success(self, billing_engine):
        """Test getting billing summary successfully."""
        # Create sample invoices
        invoice_1 = Invoice(
            invoice_id="inv_1", tenant_id="tenant_123", billing_period_start=0,
            billing_period_end=0, status=InvoiceStatus.PAID, items=[],
            subtotal=100, tax_amount=10, total_amount=110, created_at=time.time() - 86400,
            due_date=0
        )
        invoice_2 = Invoice(
            invoice_id="inv_2", tenant_id="tenant_123", billing_period_start=0,
            billing_period_end=0, status=InvoiceStatus.DRAFT, items=[],
            subtotal=200, tax_amount=20, total_amount=220, created_at=time.time() - 86400 * 2,
            due_date=0
        )
        
        with patch.object(billing_engine, 'get_tenant_invoices') as mock_get_invoices:
            mock_get_invoices.return_value = [invoice_1, invoice_2]
            
            summary = await billing_engine.get_billing_summary("tenant_123", months=12)
        
        assert summary["tenant_id"] == "tenant_123"
        assert summary["total_invoices"] == 2
        assert summary["total_amount"] == 330  # 110 + 220
        assert summary["paid_amount"] == 110
        assert summary["outstanding_amount"] == 220
        assert len(summary["invoices"]) == 2

    @pytest.mark.asyncio
    async def test_create_billing_items_from_usage_summary(self, billing_engine, sample_usage_summary):
        """Test creating billing items from usage summary."""
        items = await billing_engine._create_billing_items(sample_usage_summary)
        
        assert len(items) == 3  # tokens_in, tokens_out, api_calls
        
        # Check tokens_in item
        tokens_in_item = next(item for item in items if item.usage_type == UsageType.TOKENS_IN)
        assert tokens_in_item.quantity == 10000
        assert tokens_in_item.total_price == 0.05
        assert tokens_in_item.unit_price == 0.05 / 10000
        
        # Check tokens_out item
        tokens_out_item = next(item for item in items if item.usage_type == UsageType.TOKENS_OUT)
        assert tokens_out_item.quantity == 5000
        assert tokens_out_item.total_price == 0.025
        
        # Check api_calls item
        api_calls_item = next(item for item in items if item.usage_type == UsageType.API_CALLS)
        assert api_calls_item.quantity == 1000
        assert api_calls_item.total_price == 0.10

    @pytest.mark.asyncio
    async def test_create_billing_items_empty_usage(self, billing_engine):
        """Test creating billing items with empty usage."""
        empty_summary = {
            "usage_types": {}
        }
        
        items = await billing_engine._create_billing_items(empty_summary)
        
        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_store_invoice_success(self, billing_engine):
        """Test storing invoice successfully."""
        invoice = Invoice(
            invoice_id="inv_test_123",
            tenant_id="tenant_123",
            billing_period_start=time.time() - 86400,
            billing_period_end=time.time(),
            status=InvoiceStatus.DRAFT,
            items=[],
            subtotal=100.0,
            tax_amount=10.0,
            total_amount=110.0,
            created_at=time.time(),
            due_date=time.time() + 86400 * 30
        )
        
        await billing_engine._store_invoice(invoice)
        
        # Verify Redis storage
        billing_engine.redis.hset.assert_called_once()
        billing_engine.redis.expire.assert_called_once()
        
        # Check storage key format
        call_args = billing_engine.redis.hset.call_args
        assert call_args[0][0] == f"invoice:{invoice.tenant_id}:{invoice.invoice_id}"
        
        # Check TTL (2 years)
        expire_call = billing_engine.redis.expire.call_args
        assert expire_call[0][1] == 86400 * 365 * 2

    @pytest.mark.asyncio
    async def test_record_payment_success(self, billing_engine):
        """Test recording payment successfully."""
        await billing_engine._record_payment("inv_test_123", 110.0, "credit_card")
        
        # Verify Redis storage
        billing_engine.redis.hset.assert_called_once()
        billing_engine.redis.expire.assert_called_once()
        
        # Check payment key format
        call_args = billing_engine.redis.hset.call_args
        assert call_args[0][0].startswith("payment:inv_test_123:")
        
        # Check TTL (2 years)
        expire_call = billing_engine.redis.expire.call_args
        assert expire_call[0][1] == 86400 * 365 * 2

    @pytest.mark.asyncio
    async def test_get_payment_history_success(self, billing_engine):
        """Test getting payment history successfully."""
        # Mock Redis keys
        billing_engine.redis.keys.return_value = [
            b"payment:inv_test_123:1643673600",
            b"payment:inv_test_123:1643673700"
        ]
        
        # Mock payment data
        payment_data_1 = {
            b"invoice_id": b"inv_test_123",
            b"payment_amount": b"110.0",
            b"payment_method": b"credit_card",
            b"timestamp": b"1643673600.0"
        }
        payment_data_2 = {
            b"invoice_id": b"inv_test_123",
            b"payment_amount": b"50.0",
            b"payment_method": b"credit_card",
            b"timestamp": b"1643673700.0"
        }
        
        billing_engine.redis.hgetall.side_effect = [payment_data_1, payment_data_2]
        
        payments = await billing_engine.get_payment_history("inv_test_123")
        
        assert len(payments) == 2
        assert payments[0]["payment_amount"] == 50.0  # Sorted by timestamp (newest first)
        assert payments[1]["payment_amount"] == 110.0

    @pytest.mark.asyncio
    async def test_get_billing_statistics_success(self, billing_engine):
        """Test getting billing statistics successfully."""
        # Mock Redis keys
        billing_engine.redis.keys.return_value = [
            b"invoice:tenant_1:inv_1",
            b"invoice:tenant_2:inv_2",
            b"invoice:tenant_3:inv_3"
        ]
        
        # Mock invoice data
        invoice_data_1 = {
            b"status": b"paid",
            b"total_amount": b"100.0"
        }
        invoice_data_2 = {
            b"status": b"draft",
            b"total_amount": b"200.0"
        }
        invoice_data_3 = {
            b"status": b"paid",
            b"total_amount": b"150.0"
        }
        
        billing_engine.redis.hgetall.side_effect = [invoice_data_1, invoice_data_2, invoice_data_3]
        
        stats = await billing_engine.get_billing_statistics()
        
        assert stats["total_invoices"] == 3
        assert stats["total_revenue"] == 450.0  # 100 + 200 + 150
        assert stats["paid_revenue"] == 250.0  # 100 + 150
        assert stats["outstanding_revenue"] == 200.0
        assert stats["paid_invoices"] == 2
        assert stats["outstanding_invoices"] == 1
        assert stats["average_invoice_amount"] == 150.0  # 450 / 3
        assert stats["invoices_by_status"]["paid"] == 2
        assert stats["invoices_by_status"]["draft"] == 1

    def test_billing_item_creation(self):
        """Test BillingItem creation."""
        item = BillingItem(
            item_id="item_123",
            description="API Calls Usage",
            quantity=1000,
            unit_price=0.10,
            total_price=100.0,
            usage_type=UsageType.API_CALLS,
            metadata={"test": True}
        )
        
        assert item.item_id == "item_123"
        assert item.description == "API Calls Usage"
        assert item.quantity == 1000
        assert item.unit_price == 0.10
        assert item.total_price == 100.0
        assert item.usage_type == UsageType.API_CALLS
        assert item.metadata == {"test": True}

    def test_invoice_creation(self):
        """Test Invoice creation."""
        items = [
            BillingItem(
                item_id="item_1",
                description="Test Item",
                quantity=1,
                unit_price=100.0,
                total_price=100.0,
                usage_type=UsageType.API_CALLS
            )
        ]
        
        invoice = Invoice(
            invoice_id="inv_123",
            tenant_id="tenant_123",
            billing_period_start=time.time() - 86400,
            billing_period_end=time.time(),
            status=InvoiceStatus.DRAFT,
            items=items,
            subtotal=100.0,
            tax_amount=10.0,
            total_amount=110.0,
            created_at=time.time(),
            due_date=time.time() + 86400 * 30
        )
        
        assert invoice.invoice_id == "inv_123"
        assert invoice.tenant_id == "tenant_123"
        assert invoice.status == InvoiceStatus.DRAFT
        assert len(invoice.items) == 1
        assert invoice.subtotal == 100.0
        assert invoice.tax_amount == 10.0
        assert invoice.total_amount == 110.0

    def test_billing_status_enum(self):
        """Test BillingStatus enum values."""
        assert BillingStatus.PENDING.value == "pending"
        assert BillingStatus.PROCESSING.value == "processing"
        assert BillingStatus.COMPLETED.value == "completed"
        assert BillingStatus.FAILED.value == "failed"
        assert BillingStatus.CANCELLED.value == "cancelled"

    def test_invoice_status_enum(self):
        """Test InvoiceStatus enum values."""
        assert InvoiceStatus.DRAFT.value == "draft"
        assert InvoiceStatus.SENT.value == "sent"
        assert InvoiceStatus.PAID.value == "paid"
        assert InvoiceStatus.OVERDUE.value == "overdue"
        assert InvoiceStatus.CANCELLED.value == "cancelled"


# Import patch for mocking
from unittest.mock import patch
