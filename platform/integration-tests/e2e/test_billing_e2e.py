"""E2E tests for billing service."""

import pytest
import asyncio
import time
import json
from unittest.mock import AsyncMock, MagicMock
import redis.asyncio as redis

from apps.billing_service.core.usage_tracker import UsageTracker, UsageType
from apps.billing_service.core.billing_engine import BillingEngine, InvoiceStatus
from apps.billing_service.core.webhook_aggregator import WebhookAggregator, WebhookEventType


@pytest.fixture
async def mock_redis():
    """Mock Redis client."""
    redis_mock = AsyncMock(spec=redis.Redis)
    redis_mock.get.return_value = None
    redis_mock.setex.return_value = True
    redis_mock.hset.return_value = True
    redis_mock.expire.return_value = True
    redis_mock.keys.return_value = []
    redis_mock.hgetall.return_value = {}
    redis_mock.incrbyfloat.return_value = 1.0
    redis_mock.lpush.return_value = 1
    redis_mock.ltrim.return_value = True
    redis_mock.lrange.return_value = []
    return redis_mock


@pytest.fixture
async def usage_tracker(mock_redis):
    """Usage tracker fixture."""
    tracker = UsageTracker(mock_redis)
    
    # Set up pricing rates
    tracker.set_pricing_rate(UsageType.TOKENS_IN, 0.001, "per_token")
    tracker.set_pricing_rate(UsageType.TOKENS_OUT, 0.002, "per_token")
    tracker.set_pricing_rate(UsageType.TOOL_CALLS, 0.01, "per_call")
    tracker.set_pricing_rate(UsageType.WS_MINUTES, 0.05, "per_minute")
    tracker.set_pricing_rate(UsageType.STORAGE_MB, 0.001, "per_mb")
    tracker.set_pricing_rate(UsageType.API_CALLS, 0.005, "per_call")
    
    # Set usage limits
    tracker.set_usage_limit("tenant_001", UsageType.TOKENS_IN, 100000, "monthly")
    tracker.set_usage_limit("tenant_001", UsageType.TOKENS_OUT, 50000, "monthly")
    tracker.set_usage_limit("tenant_001", UsageType.TOOL_CALLS, 1000, "monthly")
    tracker.set_usage_limit("tenant_001", UsageType.WS_MINUTES, 1000, "monthly")
    tracker.set_usage_limit("tenant_001", UsageType.STORAGE_MB, 10000, "monthly")
    tracker.set_usage_limit("tenant_001", UsageType.API_CALLS, 5000, "monthly")
    
    return tracker


@pytest.fixture
async def billing_engine(mock_redis, usage_tracker):
    """Billing engine fixture."""
    return BillingEngine(mock_redis, usage_tracker)


@pytest.fixture
async def webhook_aggregator(mock_redis, usage_tracker, billing_engine):
    """Webhook aggregator fixture."""
    return WebhookAggregator(mock_redis, usage_tracker, billing_engine)


class TestBillingE2E:
    """E2E tests for billing service."""

    @pytest.mark.asyncio
    async def test_webhook_aggregation_flow(self, webhook_aggregator, mock_redis):
        """Test complete webhook aggregation flow."""
        tenant_id = "tenant_001"
        
        # Mock Redis responses for webhook events
        mock_redis.keys.return_value = [
            f"webhook_event:{tenant_id}:event_001".encode(),
            f"webhook_event:{tenant_id}:event_002".encode(),
            f"webhook_event:{tenant_id}:event_003".encode()
        ]
        
        mock_redis.hgetall.side_effect = [
            {
                'event_id': 'event_001',
                'event_type': 'usage_recorded',
                'tenant_id': tenant_id,
                'timestamp': str(time.time() - 3600),
                'data': json.dumps({
                    'usage_type': 'tokens_in',
                    'quantity': 1000
                }),
                'metadata': json.dumps({})
            },
            {
                'event_id': 'event_002',
                'event_type': 'tool_called',
                'tenant_id': tenant_id,
                'timestamp': str(time.time() - 1800),
                'data': json.dumps({
                    'tool_name': 'search_tool',
                    'execution_time': 2.5
                }),
                'metadata': json.dumps({})
            },
            {
                'event_id': 'event_003',
                'event_type': 'ws_connection',
                'tenant_id': tenant_id,
                'timestamp': str(time.time() - 900),
                'data': json.dumps({
                    'connection_duration': 300  # 5 minutes
                }),
                'metadata': json.dumps({})
            }
        ]
        
        # Test webhook processing
        webhook_data = {
            'event_type': 'usage_recorded',
            'tenant_id': tenant_id,
            'data': {
                'usage_type': 'tokens_out',
                'quantity': 500
            },
            'metadata': {}
        }
        
        success = await webhook_aggregator.process_webhook(webhook_data)
        assert success is True
        
        # Test usage counter aggregation
        period_start = time.time() - 7200  # 2 hours ago
        period_end = time.time()
        
        usage_counters = await webhook_aggregator.get_usage_counters(tenant_id, period_start, period_end)
        
        assert 'error' not in usage_counters
        assert usage_counters['tenant_id'] == tenant_id
        assert 'counters' in usage_counters
        assert 'total_cost' in usage_counters
        
        # Verify counters were updated
        counters = usage_counters['counters']
        assert 'tokens_in' in counters
        assert 'tokens_out' in counters
        assert 'tool_calls' in counters
        assert 'ws_minutes' in counters

    @pytest.mark.asyncio
    async def test_invoice_preview_generation(self, webhook_aggregator, mock_redis):
        """Test invoice preview generation."""
        tenant_id = "tenant_001"
        
        # Mock aggregated usage data
        mock_redis.keys.return_value = [f"aggregated_usage:{tenant_id}:1234567890:1234567890".encode()]
        mock_redis.hgetall.return_value = {
            'tenant_id': tenant_id,
            'period_start': '1234567890',
            'period_end': '1234567890',
            'counters': json.dumps({
                'tokens_in': {
                    'tenant_id': tenant_id,
                    'usage_type': 'tokens_in',
                    'total_usage': 1000.0,
                    'count': 10,
                    'last_updated': 1234567890,
                    'period_start': 1234567890,
                    'period_end': 1234567890
                },
                'tokens_out': {
                    'tenant_id': tenant_id,
                    'usage_type': 'tokens_out',
                    'total_usage': 500.0,
                    'count': 10,
                    'last_updated': 1234567890,
                    'period_start': 1234567890,
                    'period_end': 1234567890
                },
                'tool_calls': {
                    'tenant_id': tenant_id,
                    'usage_type': 'tool_calls',
                    'total_usage': 50.0,
                    'count': 50,
                    'last_updated': 1234567890,
                    'period_start': 1234567890,
                    'period_end': 1234567890
                }
            }),
            'total_cost': '2.5',
            'last_aggregated': '1234567890'
        }
        
        # Generate invoice preview
        period_start = time.time() - 86400  # 1 day ago
        period_end = time.time()
        
        preview = await webhook_aggregator.generate_invoice_preview(tenant_id, period_start, period_end)
        
        assert 'error' not in preview
        assert preview['tenant_id'] == tenant_id
        assert preview['billing_period_start'] == period_start
        assert preview['billing_period_end'] == period_end
        assert 'items' in preview
        assert 'subtotal' in preview
        assert 'tax_amount' in preview
        assert 'total_amount' in preview
        assert preview['total_amount'] > 0
        
        # Verify items
        items = preview['items']
        assert len(items) > 0
        
        # Check that items have correct structure
        for item in items:
            assert 'item_id' in item
            assert 'description' in item
            assert 'quantity' in item
            assert 'unit_price' in item
            assert 'total_price' in item
            assert 'usage_type' in item

    @pytest.mark.asyncio
    async def test_plan_enforcement(self, webhook_aggregator, mock_redis):
        """Test plan enforcement for usage limits."""
        tenant_id = "tenant_001"
        
        # Mock current usage data
        mock_redis.get.return_value = "50000"  # Current usage
        
        # Test within limit
        enforcement = await webhook_aggregator.test_plan_enforcement(
            tenant_id, UsageType.TOKENS_IN, 1000
        )
        
        assert enforcement['allowed'] is True
        assert enforcement['status_code'] == 200
        assert 'current_usage' in enforcement
        assert 'usage_limit' in enforcement
        assert 'remaining_usage' in enforcement
        
        # Test over limit
        enforcement = await webhook_aggregator.test_plan_enforcement(
            tenant_id, UsageType.TOKENS_IN, 60000  # Would exceed limit
        )
        
        assert enforcement['allowed'] is False
        assert enforcement['status_code'] == 429
        assert 'Usage limit exceeded' in enforcement['message']

    @pytest.mark.asyncio
    async def test_billing_engine_integration(self, billing_engine, usage_tracker, mock_redis):
        """Test billing engine integration."""
        tenant_id = "tenant_001"
        
        # Mock usage summary
        mock_usage_summary = {
            'usage_types': {
                'tokens_in': {
                    'total_usage': 1000,
                    'cost': 1.0
                },
                'tokens_out': {
                    'total_usage': 500,
                    'cost': 1.0
                },
                'tool_calls': {
                    'total_usage': 50,
                    'cost': 0.5
                }
            }
        }
        
        # Mock usage tracker method
        usage_tracker.get_all_usage_summary = AsyncMock(return_value=mock_usage_summary)
        
        # Generate invoice
        period_start = time.time() - 86400
        period_end = time.time()
        
        invoice_id = await billing_engine.generate_invoice(tenant_id, period_start, period_end)
        
        assert invoice_id is not None
        assert invoice_id.startswith('inv_')
        
        # Verify invoice was stored
        assert mock_redis.hset.called
        assert mock_redis.expire.called

    @pytest.mark.asyncio
    async def test_payment_processing(self, billing_engine, mock_redis):
        """Test payment processing."""
        tenant_id = "tenant_001"
        invoice_id = "inv_1234567890_tenant_001"
        
        # Mock invoice data
        mock_redis.keys.return_value = [f"invoice:{tenant_id}:{invoice_id}".encode()]
        mock_redis.hgetall.return_value = {
            'invoice_id': invoice_id,
            'tenant_id': tenant_id,
            'billing_period_start': '1234567890',
            'billing_period_end': '1234567890',
            'status': 'draft',
            'items': str([]),
            'subtotal': '2.5',
            'tax_amount': '0.25',
            'total_amount': '2.75',
            'created_at': '1234567890',
            'due_date': '1234567890',
            'paid_at': '0'
        }
        
        # Process payment
        success = await billing_engine.process_payment(invoice_id, 2.75, "credit_card")
        
        assert success is True
        
        # Verify payment was recorded
        assert mock_redis.hset.called
        assert mock_redis.expire.called

    @pytest.mark.asyncio
    async def test_usage_tracking_integration(self, usage_tracker, mock_redis):
        """Test usage tracking integration."""
        tenant_id = "tenant_001"
        
        # Record usage
        success = await usage_tracker.record_usage(
            tenant_id=tenant_id,
            usage_type=UsageType.TOKENS_IN,
            quantity=1000,
            metadata={'source': 'test'}
        )
        
        assert success is True
        
        # Verify usage was stored
        assert mock_redis.hset.called
        assert mock_redis.expire.called
        assert mock_redis.incrbyfloat.called
        assert mock_redis.lpush.called
        assert mock_redis.ltrim.called

    @pytest.mark.asyncio
    async def test_usage_limit_checking(self, usage_tracker, mock_redis):
        """Test usage limit checking."""
        tenant_id = "tenant_001"
        
        # Mock current usage
        mock_redis.get.return_value = "50000"
        
        # Check usage limit
        limit_check = await usage_tracker.check_usage_limit(
            tenant_id, UsageType.TOKENS_IN, 1000
        )
        
        assert 'within_limit' in limit_check
        assert 'current_usage' in limit_check
        assert 'usage_limit' in limit_check
        assert 'remaining_usage' in limit_check
        assert 'projected_usage' in limit_check

    @pytest.mark.asyncio
    async def test_billing_summary(self, billing_engine, mock_redis):
        """Test billing summary generation."""
        tenant_id = "tenant_001"
        
        # Mock invoice data
        mock_redis.keys.return_value = [
            f"invoice:{tenant_id}:inv_001".encode(),
            f"invoice:{tenant_id}:inv_002".encode()
        ]
        
        mock_redis.hgetall.side_effect = [
            {
                'invoice_id': 'inv_001',
                'tenant_id': tenant_id,
                'status': 'paid',
                'total_amount': '100.0',
                'created_at': str(time.time() - 86400),
                'due_date': str(time.time() - 86400),
                'paid_at': str(time.time() - 86400)
            },
            {
                'invoice_id': 'inv_002',
                'tenant_id': tenant_id,
                'status': 'draft',
                'total_amount': '50.0',
                'created_at': str(time.time() - 43200),
                'due_date': str(time.time() + 86400),
                'paid_at': '0'
            }
        ]
        
        # Get billing summary
        summary = await billing_engine.get_billing_summary(tenant_id, 12)
        
        assert 'error' not in summary
        assert summary['tenant_id'] == tenant_id
        assert 'total_invoices' in summary
        assert 'total_amount' in summary
        assert 'paid_amount' in summary
        assert 'outstanding_amount' in summary
        assert 'average_monthly_bill' in summary
        assert 'invoices' in summary

    @pytest.mark.asyncio
    async def test_webhook_event_processing(self, webhook_aggregator, mock_redis):
        """Test webhook event processing for different event types."""
        tenant_id = "tenant_001"
        
        # Test different webhook event types
        webhook_events = [
            {
                'event_type': 'usage_recorded',
                'tenant_id': tenant_id,
                'data': {
                    'usage_type': 'tokens_in',
                    'quantity': 1000
                }
            },
            {
                'event_type': 'tool_called',
                'tenant_id': tenant_id,
                'data': {
                    'tool_name': 'search_tool',
                    'execution_time': 2.5
                }
            },
            {
                'event_type': 'ws_connection',
                'tenant_id': tenant_id,
                'data': {
                    'connection_duration': 300
                }
            },
            {
                'event_type': 'storage_used',
                'tenant_id': tenant_id,
                'data': {
                    'storage_mb': 100
                }
            },
            {
                'event_type': 'api_call',
                'tenant_id': tenant_id,
                'data': {
                    'endpoint': '/api/v1/chat',
                    'response_time': 1.5
                }
            }
        ]
        
        # Process each webhook event
        for webhook_data in webhook_events:
            success = await webhook_aggregator.process_webhook(webhook_data)
            assert success is True
        
        # Verify all events were stored
        assert mock_redis.hset.call_count >= len(webhook_events)
        assert mock_redis.expire.call_count >= len(webhook_events)

    @pytest.mark.asyncio
    async def test_error_handling(self, webhook_aggregator, mock_redis):
        """Test error handling in billing service."""
        tenant_id = "tenant_001"
        
        # Test invalid webhook data
        invalid_webhook = {
            'event_type': 'invalid_type',
            'tenant_id': tenant_id,
            'data': {}
        }
        
        success = await webhook_aggregator.process_webhook(invalid_webhook)
        assert success is False
        
        # Test missing required fields
        incomplete_webhook = {
            'event_type': 'usage_recorded',
            'data': {}
        }
        
        success = await webhook_aggregator.process_webhook(incomplete_webhook)
        assert success is False

    @pytest.mark.asyncio
    async def test_performance_under_load(self, webhook_aggregator, mock_redis):
        """Test performance under load."""
        tenant_id = "tenant_001"
        
        # Mock Redis responses
        mock_redis.hset.return_value = True
        mock_redis.expire.return_value = True
        
        # Process multiple webhooks concurrently
        webhook_tasks = []
        for i in range(100):
            webhook_data = {
                'event_type': 'usage_recorded',
                'tenant_id': tenant_id,
                'data': {
                    'usage_type': 'tokens_in',
                    'quantity': 100
                }
            }
            task = webhook_aggregator.process_webhook(webhook_data)
            webhook_tasks.append(task)
        
        # Execute all webhooks concurrently
        start_time = time.time()
        results = await asyncio.gather(*webhook_tasks, return_exceptions=True)
        end_time = time.time()
        
        # Verify all webhooks were processed
        successful_results = [r for r in results if r is True]
        assert len(successful_results) == 100
        
        # Verify performance (should complete within reasonable time)
        execution_time = end_time - start_time
        assert execution_time < 10.0  # Should complete within 10 seconds


if __name__ == '__main__':
    pytest.main([__file__])
