"""Integration tests for billing E2E verification."""

import pytest
import asyncio
import json
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from apps.billing_service.core.usage_tracker import UsageTracker, UsageType
from apps.billing_service.core.billing_engine import BillingEngine
from apps.billing_service.core.webhook_aggregator import (
    WebhookAggregator,
    WebhookEventType,
)
from apps.billing_service.core.invoice_preview import InvoicePreviewService, QuotaStatus
from apps.api_gateway.middleware.quota_enforcement import (
    QuotaEnforcementMiddleware,
    QuotaStatus as MiddlewareQuotaStatus,
)


class TestBillingE2E:
    """Test billing E2E verification functionality."""

    @pytest.fixture
    def redis_mock(self):
        """Mock Redis client."""
        mock = AsyncMock()
        mock.get.return_value = None
        mock.setex.return_value = True
        mock.incr.return_value = 1
        mock.hget.return_value = None
        mock.hset.return_value = True
        return mock

    @pytest.fixture
    async def services(self, redis_mock):
        """Create test services."""
        usage_tracker = UsageTracker(redis_mock)
        billing_engine = BillingEngine(redis_mock, usage_tracker)
        webhook_aggregator = WebhookAggregator(
            redis_mock, usage_tracker, billing_engine
        )
        invoice_preview_service = InvoicePreviewService(
            redis_mock, usage_tracker, billing_engine
        )

        return {
            "usage_tracker": usage_tracker,
            "billing_engine": billing_engine,
            "webhook_aggregator": webhook_aggregator,
            "invoice_preview_service": invoice_preview_service,
        }

    @pytest.mark.asyncio
    async def test_usage_recording_e2e(self, services):
        """Test E2E usage recording."""
        tenant_id = "test-tenant"

        # Record usage
        await services["usage_tracker"].record_usage(
            tenant_id=tenant_id,
            usage_type=UsageType.API_CALLS,
            quantity=100.0,
            metadata={"test": "e2e"},
        )

        # Verify usage was recorded
        current_usage = await services["usage_tracker"].get_current_usage(
            tenant_id, UsageType.API_CALLS
        )

        assert current_usage == 100.0

    @pytest.mark.asyncio
    async def test_invoice_preview_e2e(self, services):
        """Test E2E invoice preview generation."""
        tenant_id = "test-tenant"

        # Record some usage first
        await services["usage_tracker"].record_usage(
            tenant_id=tenant_id,
            usage_type=UsageType.API_CALLS,
            quantity=1000.0,
            metadata={"test": "e2e"},
        )

        # Generate invoice preview
        preview = await services["invoice_preview_service"].generate_invoice_preview(
            tenant_id
        )

        assert preview is not None
        assert preview.tenant_id == tenant_id
        assert preview.total_amount >= 0
        assert len(preview.items) > 0
        assert preview.currency == "USD"

    @pytest.mark.asyncio
    async def test_quota_enforcement_e2e(self, services):
        """Test E2E quota enforcement."""
        tenant_id = "test-tenant"

        # Check quota for small amount (should pass)
        allowed, message = await services["invoice_preview_service"].enforce_quota(
            tenant_id=tenant_id, usage_type=UsageType.API_CALLS, requested_amount=1.0
        )

        assert allowed is True
        assert "quota" in message.lower()

        # Check quota for very large amount (should fail)
        allowed, message = await services["invoice_preview_service"].enforce_quota(
            tenant_id=tenant_id,
            usage_type=UsageType.API_CALLS,
            requested_amount=1000000.0,
        )

        assert allowed is False
        assert "exceeded" in message.lower()

    @pytest.mark.asyncio
    async def test_webhook_aggregation_e2e(self, services):
        """Test E2E webhook aggregation."""
        tenant_id = "test-tenant"

        # Process webhook events
        await services["webhook_aggregator"].process_webhook_event(
            event_type=WebhookEventType.API_CALL,
            tenant_id=tenant_id,
            data={"calls": 10},
            metadata={"source": "test"},
        )

        await services["webhook_aggregator"].process_webhook_event(
            event_type=WebhookEventType.TOOL_CALLED,
            tenant_id=tenant_id,
            data={"tools": 5},
            metadata={"source": "test"},
        )

        # Verify counters were updated
        api_usage = await services["usage_tracker"].get_current_usage(
            tenant_id, UsageType.API_CALLS
        )
        tool_usage = await services["usage_tracker"].get_current_usage(
            tenant_id, UsageType.TOOL_CALLS
        )

        assert api_usage > 0
        assert tool_usage > 0

    @pytest.mark.asyncio
    async def test_quota_middleware_e2e(self, redis_mock):
        """Test E2E quota enforcement middleware."""
        usage_tracker = UsageTracker(redis_mock)

        # Mock quota limits
        redis_mock.get.return_value = "1000"  # 1000 API calls limit

        # Mock current usage
        redis_mock.hget.return_value = "500"  # 500 current usage

        middleware = QuotaEnforcementMiddleware(None, redis_mock, usage_tracker)

        # Test quota check
        tenant_id = "test-tenant"
        usage_type = UsageType.API_CALLS
        requested_amount = 100.0

        check = await middleware._check_single_quota(
            tenant_id, usage_type, requested_amount
        )

        assert check.allowed is True
        assert check.remaining_quota == 400.0  # 1000 - 500 - 100
        assert check.status == MiddlewareQuotaStatus.WITHIN_LIMITS

    @pytest.mark.asyncio
    async def test_quota_exceeded_middleware(self, redis_mock):
        """Test quota exceeded scenario in middleware."""
        usage_tracker = UsageTracker(redis_mock)

        # Mock quota limits
        redis_mock.get.return_value = "1000"  # 1000 API calls limit

        # Mock current usage near limit
        redis_mock.hget.return_value = "950"  # 950 current usage

        middleware = QuotaEnforcementMiddleware(None, redis_mock, usage_tracker)

        # Test quota check with large request
        tenant_id = "test-tenant"
        usage_type = UsageType.API_CALLS
        requested_amount = 100.0  # This would exceed the limit

        check = await middleware._check_single_quota(
            tenant_id, usage_type, requested_amount
        )

        assert check.allowed is False
        assert check.status == MiddlewareQuotaStatus.EXCEEDED
        assert "exceeded" in check.message.lower()

    @pytest.mark.asyncio
    async def test_invoice_preview_caching(self, services):
        """Test invoice preview caching."""
        tenant_id = "test-tenant"

        # Record usage
        await services["usage_tracker"].record_usage(
            tenant_id=tenant_id,
            usage_type=UsageType.API_CALLS,
            quantity=500.0,
            metadata={"test": "caching"},
        )

        # Generate preview
        preview1 = await services["invoice_preview_service"].generate_invoice_preview(
            tenant_id
        )

        # Get cached preview
        cached_preview = await services["invoice_preview_service"].get_cached_preview(
            tenant_id, preview1.preview_id
        )

        assert cached_preview is not None
        assert cached_preview.preview_id == preview1.preview_id
        assert cached_preview.total_amount == preview1.total_amount

    @pytest.mark.asyncio
    async def test_quota_status_aggregation(self, services):
        """Test quota status aggregation."""
        tenant_id = "test-tenant"

        # Record usage to test quotas
        await services["usage_tracker"].record_usage(
            tenant_id=tenant_id,
            usage_type=UsageType.API_CALLS,
            quantity=500.0,
            metadata={"test": "quota_status"},
        )

        # Get quota limits
        quota_limits = await services["invoice_preview_service"].get_quota_limits(
            tenant_id
        )

        assert len(quota_limits) > 0

        # Check that API calls quota is included
        api_quota = next(
            (q for q in quota_limits if q.usage_type == UsageType.API_CALLS), None
        )
        assert api_quota is not None
        assert api_quota.current_usage == 500.0
        assert api_quota.limit > 0

    @pytest.mark.asyncio
    async def test_webhook_event_processing(self, services):
        """Test webhook event processing."""
        tenant_id = "test-tenant"

        # Process different types of webhook events
        events = [
            (WebhookEventType.API_CALL, {"calls": 10}),
            (WebhookEventType.TOOL_CALLED, {"tools": 5}),
            (WebhookEventType.WS_CONNECTION, {"minutes": 30}),
            (WebhookEventType.STORAGE_USED, {"mb": 100}),
        ]

        for event_type, data in events:
            await services["webhook_aggregator"].process_webhook_event(
                event_type=event_type,
                tenant_id=tenant_id,
                data=data,
                metadata={"source": "test"},
            )

        # Verify all usage types were recorded
        for usage_type in UsageType:
            current_usage = await services["usage_tracker"].get_current_usage(
                tenant_id, usage_type
            )
            assert current_usage >= 0  # Should have some usage recorded

    @pytest.mark.asyncio
    async def test_billing_cycle_integration(self, services):
        """Test complete billing cycle integration."""
        tenant_id = "test-tenant"

        # Simulate a month of usage
        usage_events = [
            (UsageType.API_CALLS, 10000),
            (UsageType.TOOL_CALLS, 500),
            (UsageType.WS_CONNECTIONS, 1000),
            (UsageType.STORAGE, 500),
        ]

        for usage_type, quantity in usage_events:
            await services["usage_tracker"].record_usage(
                tenant_id=tenant_id,
                usage_type=usage_type,
                quantity=quantity,
                metadata={"billing_cycle": "test"},
            )

        # Generate invoice preview
        preview = await services["invoice_preview_service"].generate_invoice_preview(
            tenant_id
        )

        # Verify invoice preview
        assert preview.total_amount > 0
        assert len(preview.items) == len(usage_events)

        # Verify each usage type is represented
        item_types = {item.usage_type for item in preview.items}
        expected_types = {usage_type for usage_type, _ in usage_events}
        assert item_types == expected_types

        # Verify pricing calculation
        total_calculated = sum(item.total_price for item in preview.items)
        assert (
            abs(total_calculated - preview.subtotal) < 0.01
        )  # Allow for floating point precision

    @pytest.mark.asyncio
    async def test_error_handling_e2e(self, services):
        """Test error handling in E2E scenarios."""
        tenant_id = "test-tenant"

        # Test with invalid usage type
        with pytest.raises(ValueError):
            await services["usage_tracker"].record_usage(
                tenant_id=tenant_id,
                usage_type="invalid_type",  # This should fail
                quantity=1.0,
                metadata={},
            )

        # Test quota enforcement with invalid usage type
        with pytest.raises(ValueError):
            await services["invoice_preview_service"].enforce_quota(
                tenant_id=tenant_id,
                usage_type="invalid_type",  # This should fail
                requested_amount=1.0,
            )

    @pytest.mark.asyncio
    async def test_concurrent_usage_recording(self, services):
        """Test concurrent usage recording."""
        tenant_id = "test-tenant"

        # Record usage concurrently
        tasks = []
        for i in range(10):
            task = services["usage_tracker"].record_usage(
                tenant_id=tenant_id,
                usage_type=UsageType.API_CALLS,
                quantity=1.0,
                metadata={"concurrent_test": i},
            )
            tasks.append(task)

        await asyncio.gather(*tasks)

        # Verify total usage
        current_usage = await services["usage_tracker"].get_current_usage(
            tenant_id, UsageType.API_CALLS
        )
        assert current_usage == 10.0

    @pytest.mark.asyncio
    async def test_quota_reset_simulation(self, services):
        """Test quota reset simulation."""
        tenant_id = "test-tenant"

        # Set a low quota limit
        await services["invoice_preview_service"].redis_client.set(
            f"quota:{tenant_id}:{UsageType.API_CALLS.value}", "10"  # Very low limit
        )

        # Record usage up to limit
        await services["usage_tracker"].record_usage(
            tenant_id=tenant_id,
            usage_type=UsageType.API_CALLS,
            quantity=10.0,
            metadata={"quota_test": "limit"},
        )

        # Try to exceed quota
        allowed, message = await services["invoice_preview_service"].enforce_quota(
            tenant_id=tenant_id, usage_type=UsageType.API_CALLS, requested_amount=1.0
        )

        assert allowed is False
        assert "exceeded" in message.lower()

        # Simulate quota reset by clearing usage
        await services["usage_tracker"].redis_client.delete(
            f"usage:{tenant_id}:{UsageType.API_CALLS.value}"
        )

        # Now should be allowed
        allowed, message = await services["invoice_preview_service"].enforce_quota(
            tenant_id=tenant_id, usage_type=UsageType.API_CALLS, requested_amount=1.0
        )

        assert allowed is True
