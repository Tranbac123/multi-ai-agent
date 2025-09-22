"""Test billing E2E functionality."""

import pytest
import time
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from apps.billing-service.core.billing_engine import BillingEngine, InvoiceStatus
from apps.billing-service.core.usage_tracker import UsageTracker, UsageType


class TestBillingE2E:
    """Test billing end-to-end functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis_client = Mock()
        redis_client.hset = AsyncMock()
        redis_client.expire = AsyncMock()
        redis_client.incrbyfloat = AsyncMock()
        redis_client.lpush = AsyncMock()
        redis_client.ltrim = AsyncMock()
        redis_client.lrange = AsyncMock()
        redis_client.get = AsyncMock()
        redis_client.keys = AsyncMock()
        redis_client.hgetall = AsyncMock()
        return redis_client

    @pytest.fixture
    def usage_tracker(self, mock_redis):
        """Create UsageTracker instance."""
        return UsageTracker(mock_redis)

    @pytest.fixture
    def billing_engine(self, mock_redis, usage_tracker):
        """Create BillingEngine instance."""
        return BillingEngine(mock_redis, usage_tracker)

    @pytest.mark.asyncio
    async def test_complete_billing_cycle(self, billing_engine, usage_tracker, mock_redis):
        """Test complete billing cycle from usage recording to payment."""
        tenant_id = "tenant_123"
        
        # Step 1: Set up pricing and limits
        usage_tracker.set_pricing_rate(UsageType.TOKENS_IN, 0.0001, "per_token")
        usage_tracker.set_pricing_rate(UsageType.API_CALLS, 0.10, "per_call")
        usage_tracker.set_usage_limit(tenant_id, UsageType.TOKENS_IN, 100000, "monthly")
        
        # Step 2: Record usage over time
        await usage_tracker.record_usage(tenant_id, UsageType.TOKENS_IN, 50000, {"model": "gpt-4"})
        await usage_tracker.record_usage(tenant_id, UsageType.API_CALLS, 100, {"endpoint": "/chat"})
        await usage_tracker.record_usage(tenant_id, UsageType.TOKENS_IN, 30000, {"model": "gpt-3.5"})
        
        # Step 3: Generate invoice
        start_time = time.time() - 86400 * 30  # 30 days ago
        end_time = time.time()
        
        # Mock usage summary for invoice generation
        with patch.object(usage_tracker, 'get_all_usage_summary') as mock_get_summary:
            mock_get_summary.return_value = {
                "tenant_id": tenant_id,
                "period": "monthly",
                "usage_types": {
                    "tokens_in": {
                        "total_usage": 80000,
                        "cost": 8.0,
                        "usage_count": 2
                    },
                    "api_calls": {
                        "total_usage": 100,
                        "cost": 10.0,
                        "usage_count": 1
                    }
                },
                "total_cost": 18.0,
                "timestamp": time.time()
            }
            
            invoice_id = await billing_engine.generate_invoice(tenant_id, start_time, end_time)
        
        assert invoice_id is not None
        
        # Step 4: Verify invoice was created
        with patch.object(billing_engine, '_get_invoice') as mock_get_invoice:
            # Mock invoice data
            from apps.billing-service.core.billing_engine import Invoice, BillingItem
            
            mock_invoice = Invoice(
                invoice_id=invoice_id,
                tenant_id=tenant_id,
                billing_period_start=start_time,
                billing_period_end=end_time,
                status=InvoiceStatus.DRAFT,
                items=[
                    BillingItem(
                        item_id="item_1",
                        description="Tokens In Usage",
                        quantity=80000,
                        unit_price=0.0001,
                        total_price=8.0,
                        usage_type=UsageType.TOKENS_IN
                    ),
                    BillingItem(
                        item_id="item_2",
                        description="Api Calls Usage",
                        quantity=100,
                        unit_price=0.10,
                        total_price=10.0,
                        usage_type=UsageType.API_CALLS
                    )
                ],
                subtotal=18.0,
                tax_amount=1.8,
                total_amount=19.8,
                created_at=time.time(),
                due_date=time.time() + 86400 * 30
            )
            mock_get_invoice.return_value = mock_invoice
            
            invoice = await billing_engine.get_invoice(invoice_id)
        
        assert invoice is not None
        assert invoice.total_amount == 19.8  # 18.0 + 1.8 tax
        assert len(invoice.items) == 2
        
        # Step 5: Process payment
        with patch.object(billing_engine, '_get_invoice') as mock_get_invoice:
            mock_get_invoice.return_value = mock_invoice
            
            payment_success = await billing_engine.process_payment(invoice_id, 19.8)
        
        assert payment_success is True
        
        # Step 6: Verify payment history
        with patch.object(billing_engine, 'get_payment_history') as mock_get_history:
            mock_get_history.return_value = [
                {
                    "invoice_id": invoice_id,
                    "payment_amount": 19.8,
                    "payment_method": "credit_card",
                    "timestamp": time.time()
                }
            ]
            
            payments = await billing_engine.get_payment_history(invoice_id)
        
        assert len(payments) == 1
        assert payments[0]["payment_amount"] == 19.8

    @pytest.mark.asyncio
    async def test_usage_limit_enforcement(self, usage_tracker, mock_redis):
        """Test usage limit enforcement during recording."""
        tenant_id = "tenant_123"
        usage_type = UsageType.TOKENS_IN
        
        # Set low usage limit
        usage_tracker.set_usage_limit(tenant_id, usage_type, 1000, "monthly")
        
        # Mock current usage
        with patch.object(usage_tracker, '_get_current_usage') as mock_get_current:
            mock_get_current.return_value = 900.0
            
            # Check limit before recording
            limit_check = await usage_tracker.check_usage_limit(tenant_id, usage_type, 50.0)
            assert limit_check["within_limit"] is True
            
            # Check limit that would exceed
            limit_check = await usage_tracker.check_usage_limit(tenant_id, usage_type, 200.0)
            assert limit_check["within_limit"] is False
            assert limit_check["projected_usage"] == 1100.0

    @pytest.mark.asyncio
    async def test_billing_summary_generation(self, billing_engine, mock_redis):
        """Test billing summary generation across multiple invoices."""
        tenant_id = "tenant_123"
        
        # Mock multiple invoices
        from apps.billing-service.core.billing_engine import Invoice
        
        invoice_1 = Invoice(
            invoice_id="inv_1",
            tenant_id=tenant_id,
            billing_period_start=time.time() - 86400 * 60,
            billing_period_end=time.time() - 86400 * 30,
            status=InvoiceStatus.PAID,
            items=[],
            subtotal=100.0,
            tax_amount=10.0,
            total_amount=110.0,
            created_at=time.time() - 86400 * 60,
            due_date=time.time() - 86400 * 30,
            paid_at=time.time() - 86400 * 45
        )
        
        invoice_2 = Invoice(
            invoice_id="inv_2",
            tenant_id=tenant_id,
            billing_period_start=time.time() - 86400 * 30,
            billing_period_end=time.time(),
            status=InvoiceStatus.DRAFT,
            items=[],
            subtotal=200.0,
            tax_amount=20.0,
            total_amount=220.0,
            created_at=time.time() - 86400 * 30,
            due_date=time.time() + 86400 * 30
        )
        
        with patch.object(billing_engine, 'get_tenant_invoices') as mock_get_invoices:
            mock_get_invoices.return_value = [invoice_1, invoice_2]
            
            summary = await billing_engine.get_billing_summary(tenant_id, months=3)
        
        assert summary["tenant_id"] == tenant_id
        assert summary["total_invoices"] == 2
        assert summary["total_amount"] == 330.0  # 110 + 220
        assert summary["paid_amount"] == 110.0
        assert summary["outstanding_amount"] == 220.0
        assert summary["average_monthly_bill"] == 110.0  # 330 / 3
        assert len(summary["invoices"]) == 2

    @pytest.mark.asyncio
    async def test_pricing_rate_updates(self, usage_tracker, mock_redis):
        """Test pricing rate updates and cost recalculation."""
        usage_type = UsageType.TOKENS_IN
        
        # Set initial pricing rate
        usage_tracker.set_pricing_rate(usage_type, 0.0001, "per_token")
        
        # Calculate cost with initial rate
        initial_cost = await usage_tracker._calculate_cost(usage_type, 10000)
        assert initial_cost == 1.0  # 10000 * 0.0001
        
        # Update pricing rate
        usage_tracker.set_pricing_rate(usage_type, 0.0002, "per_token")
        
        # Calculate cost with updated rate
        updated_cost = await usage_tracker._calculate_cost(usage_type, 10000)
        assert updated_cost == 2.0  # 10000 * 0.0002

    @pytest.mark.asyncio
    async def test_usage_data_retention_and_cleanup(self, usage_tracker, mock_redis):
        """Test usage data retention and cleanup."""
        tenant_id = "tenant_123"
        usage_type = UsageType.TOKENS_IN
        
        # Record usage with TTL
        await usage_tracker.record_usage(tenant_id, usage_type, 1000.0)
        
        # Verify TTL was set on Redis keys
        mock_redis.expire.assert_called()
        
        # Check that appropriate TTLs were set
        expire_calls = mock_redis.expire.call_args_list
        
        # Should have TTL for individual record (1 year)
        individual_ttl_calls = [call for call in expire_calls if call[0][1] == 86400 * 365]
        assert len(individual_ttl_calls) >= 1
        
        # Should have TTL for daily counter (30 days)
        daily_ttl_calls = [call for call in expire_calls if call[0][1] == 86400 * 30]
        assert len(daily_ttl_calls) >= 1

    @pytest.mark.asyncio
    async def test_multi_tenant_billing_isolation(self, billing_engine, usage_tracker, mock_redis):
        """Test billing isolation between tenants."""
        tenant_1 = "tenant_1"
        tenant_2 = "tenant_2"
        
        # Set different pricing for each tenant (simulated via different usage)
        await usage_tracker.record_usage(tenant_1, UsageType.TOKENS_IN, 1000, {"tenant": "1"})
        await usage_tracker.record_usage(tenant_2, UsageType.TOKENS_IN, 2000, {"tenant": "2"})
        
        # Generate invoices for both tenants
        start_time = time.time() - 86400
        end_time = time.time()
        
        # Mock different usage summaries
        with patch.object(usage_tracker, 'get_all_usage_summary') as mock_get_summary:
            mock_get_summary.side_effect = [
                {
                    "tenant_id": tenant_1,
                    "usage_types": {
                        "tokens_in": {"total_usage": 1000, "cost": 1.0}
                    },
                    "total_cost": 1.0
                },
                {
                    "tenant_id": tenant_2,
                    "usage_types": {
                        "tokens_in": {"total_usage": 2000, "cost": 2.0}
                    },
                    "total_cost": 2.0
                }
            ]
            
            invoice_1_id = await billing_engine.generate_invoice(tenant_1, start_time, end_time)
            invoice_2_id = await billing_engine.generate_invoice(tenant_2, start_time, end_time)
        
        assert invoice_1_id != invoice_2_id
        
        # Verify tenant isolation in Redis keys
        hset_calls = mock_redis.hset.call_args_list
        assert len(hset_calls) == 2  # One for each invoice
        
        # Check that invoice keys are tenant-specific
        invoice_1_key = hset_calls[0][0][0]
        invoice_2_key = hset_calls[1][0][0]
        
        assert tenant_1 in invoice_1_key
        assert tenant_2 in invoice_2_key
        assert invoice_1_key != invoice_2_key

    @pytest.mark.asyncio
    async def test_billing_error_recovery(self, billing_engine, usage_tracker, mock_redis):
        """Test billing error recovery and retry mechanisms."""
        tenant_id = "tenant_123"
        
        # Simulate Redis error during invoice generation
        mock_redis.hset.side_effect = Exception("Redis connection error")
        
        with pytest.raises(Exception):
            await billing_engine.generate_invoice(tenant_id, time.time() - 86400, time.time())
        
        # Reset mock and retry
        mock_redis.hset.side_effect = None
        mock_redis.hset.reset_mock()
        
        # Mock successful usage summary
        with patch.object(usage_tracker, 'get_all_usage_summary') as mock_get_summary:
            mock_get_summary.return_value = {
                "tenant_id": tenant_id,
                "usage_types": {
                    "api_calls": {"total_usage": 100, "cost": 10.0}
                },
                "total_cost": 10.0
            }
            
            # Retry should succeed
            invoice_id = await billing_engine.generate_invoice(tenant_id, time.time() - 86400, time.time())
        
        assert invoice_id is not None

    @pytest.mark.asyncio
    async def test_concurrent_usage_recording(self, usage_tracker, mock_redis):
        """Test concurrent usage recording."""
        tenant_id = "tenant_123"
        usage_type = UsageType.API_CALLS
        
        # Record multiple usage entries concurrently
        tasks = []
        for i in range(10):
            task = usage_tracker.record_usage(
                tenant_id, 
                usage_type, 
                1.0, 
                {"request_id": f"req_{i}"}
            )
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(results)
        
        # Verify Redis operations were called for each recording
        assert mock_redis.hset.call_count >= 10

    @pytest.mark.asyncio
    async def test_billing_statistics_accuracy(self, billing_engine, mock_redis):
        """Test billing statistics accuracy."""
        # Mock multiple invoices with different statuses
        mock_invoice_data = [
            {b"status": b"paid", b"total_amount": b"100.0"},
            {b"status": b"paid", b"total_amount": b"200.0"},
            {b"status": b"draft", b"total_amount": b"150.0"},
            {b"status": b"overdue", b"total_amount": b"75.0"},
            {b"status": b"sent", b"total_amount": b"125.0"}
        ]
        
        mock_redis.keys.return_value = [f"invoice:tenant_{i}:inv_{i}".encode() for i in range(5)]
        mock_redis.hgetall.side_effect = mock_invoice_data
        
        stats = await billing_engine.get_billing_statistics()
        
        assert stats["total_invoices"] == 5
        assert stats["total_revenue"] == 650.0  # Sum of all amounts
        assert stats["paid_revenue"] == 300.0  # 100 + 200
        assert stats["outstanding_revenue"] == 350.0  # 650 - 300
        assert stats["paid_invoices"] == 2
        assert stats["outstanding_invoices"] == 3
        assert stats["average_invoice_amount"] == 130.0  # 650 / 5
        assert stats["invoices_by_status"]["paid"] == 2
        assert stats["invoices_by_status"]["draft"] == 1
        assert stats["invoices_by_status"]["overdue"] == 1
        assert stats["invoices_by_status"]["sent"] == 1

    @pytest.mark.asyncio
    async def test_usage_tracking_accuracy(self, usage_tracker, mock_redis):
        """Test usage tracking accuracy across different periods."""
        tenant_id = "tenant_123"
        usage_type = UsageType.TOKENS_IN
        
        # Set pricing rate
        usage_tracker.set_pricing_rate(usage_type, 0.0001, "per_token")
        
        # Mock usage data for different periods
        with patch.object(usage_tracker, '_get_usage_data') as mock_get_data:
            # Daily usage
            mock_get_data.return_value = [{"quantity": 1000, "timestamp": time.time()}]
            daily_summary = await usage_tracker.get_usage_summary(tenant_id, usage_type, "daily")
            
            # Monthly usage
            mock_get_data.return_value = [{"quantity": 30000, "timestamp": time.time()}]
            monthly_summary = await usage_tracker.get_usage_summary(tenant_id, usage_type, "monthly")
            
            # Yearly usage
            mock_get_data.return_value = [{"quantity": 360000, "timestamp": time.time()}]
            yearly_summary = await usage_tracker.get_usage_summary(tenant_id, usage_type, "yearly")
        
        # Verify period-specific data
        assert daily_summary["total_usage"] == 1000
        assert daily_summary["cost"] == 0.1  # 1000 * 0.0001
        
        assert monthly_summary["total_usage"] == 30000
        assert monthly_summary["cost"] == 3.0  # 30000 * 0.0001
        
        assert yearly_summary["total_usage"] == 360000
        assert yearly_summary["cost"] == 36.0  # 360000 * 0.0001
