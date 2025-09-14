"""Test billing middleware functionality."""

import pytest
import time
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from fastapi import Request, Response

from apps.api_gateway.middleware.billing_middleware import (
    BillingMiddleware,
    BillingAction,
    BillingDecision,
    BillingConfig,
)
from apps.billing_service.core.usage_tracker import UsageType


class TestBillingMiddleware:
    """Test BillingMiddleware functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis_client = Mock()
        redis_client.get = AsyncMock()
        redis_client.incr = AsyncMock()
        redis_client.expire = AsyncMock()
        return redis_client

    @pytest.fixture
    def mock_usage_tracker(self):
        """Create mock usage tracker."""
        usage_tracker = Mock()
        usage_tracker._get_current_usage = AsyncMock()
        usage_tracker.record_usage = AsyncMock()
        usage_tracker.usage_limits = {}
        return usage_tracker

    @pytest.fixture
    def mock_webhook_aggregator(self):
        """Create mock webhook aggregator."""
        webhook_aggregator = Mock()
        webhook_aggregator.process_webhook = AsyncMock()
        return webhook_aggregator

    @pytest.fixture
    def billing_config(self):
        """Create billing configuration."""
        return BillingConfig(
            enforce_limits=True,
            throttle_threshold=0.8,
            block_threshold=1.0,
            warn_threshold=0.7,
            rate_limit_window=60,
            rate_limit_requests=100,
        )

    @pytest.fixture
    def billing_middleware(self, mock_redis, mock_usage_tracker, mock_webhook_aggregator, billing_config):
        """Create BillingMiddleware instance."""
        return BillingMiddleware(
            redis_client=mock_redis,
            usage_tracker=mock_usage_tracker,
            webhook_aggregator=mock_webhook_aggregator,
            config=billing_config,
        )

    @pytest.mark.asyncio
    async def test_process_request_with_tenant_id(self, billing_middleware):
        """Test processing request with tenant ID."""
        tenant_id = "tenant_123"
        
        # Mock request
        request = Mock()
        request.headers = {"X-Tenant-ID": tenant_id}
        request.url.path = "/api/test"
        request.method = "POST"
        request.client = Mock()
        request.client.host = "192.168.1.1"
        
        # Mock call_next
        call_next = AsyncMock()
        response = Response()
        response.status_code = 200
        response.headers = {}
        call_next.return_value = response
        
        # Mock usage tracker
        billing_middleware.usage_tracker._get_current_usage.return_value = 50.0
        
        result = await billing_middleware(request, call_next)
        
        # Should process request
        call_next.assert_called_once_with(request)
        assert result == response

    @pytest.mark.asyncio
    async def test_process_request_without_tenant_id(self, billing_middleware):
        """Test processing request without tenant ID."""
        # Mock request without tenant ID
        request = Mock()
        request.headers = {}
        request.query_params = {}
        request.path_params = {}
        
        # Mock call_next
        call_next = AsyncMock()
        response = Response()
        response.status_code = 200
        call_next.return_value = response
        
        result = await billing_middleware(request, call_next)
        
        # Should allow request to proceed
        call_next.assert_called_once_with(request)
        assert result == response

    @pytest.mark.asyncio
    async def test_extract_tenant_id_from_headers(self, billing_middleware):
        """Test extracting tenant ID from headers."""
        tenant_id = "tenant_456"
        
        request = Mock()
        request.headers = {"X-Tenant-ID": tenant_id}
        request.query_params = {}
        request.path_params = {}
        
        result = await billing_middleware._extract_tenant_id(request)
        
        assert result == tenant_id

    @pytest.mark.asyncio
    async def test_extract_tenant_id_from_query_params(self, billing_middleware):
        """Test extracting tenant ID from query parameters."""
        tenant_id = "tenant_789"
        
        request = Mock()
        request.headers = {}
        request.query_params = {"tenant_id": tenant_id}
        request.path_params = {}
        
        result = await billing_middleware._extract_tenant_id(request)
        
        assert result == tenant_id

    @pytest.mark.asyncio
    async def test_extract_tenant_id_from_path_params(self, billing_middleware):
        """Test extracting tenant ID from path parameters."""
        tenant_id = "tenant_101"
        
        request = Mock()
        request.headers = {}
        request.query_params = {}
        request.path_params = {"tenant_id": tenant_id}
        
        result = await billing_middleware._extract_tenant_id(request)
        
        assert result == tenant_id

    @pytest.mark.asyncio
    async def test_determine_usage_type_api_calls(self, billing_middleware):
        """Test determining usage type for API calls."""
        request = Mock()
        request.url.path = "/api/test"
        request.method = "POST"
        
        result = await billing_middleware._determine_usage_type(request)
        
        assert result == UsageType.API_CALLS

    @pytest.mark.asyncio
    async def test_determine_usage_type_websocket(self, billing_middleware):
        """Test determining usage type for WebSocket connections."""
        request = Mock()
        request.url.path = "/ws/chat"
        request.method = "GET"
        
        result = await billing_middleware._determine_usage_type(request)
        
        assert result == UsageType.WS_MINUTES

    @pytest.mark.asyncio
    async def test_determine_usage_type_tool_calls(self, billing_middleware):
        """Test determining usage type for tool calls."""
        request = Mock()
        request.url.path = "/tools/search"
        request.method = "POST"
        
        result = await billing_middleware._determine_usage_type(request)
        
        assert result == UsageType.TOOL_CALLS

    @pytest.mark.asyncio
    async def test_determine_usage_type_storage(self, billing_middleware):
        """Test determining usage type for storage operations."""
        request = Mock()
        request.url.path = "/storage/upload"
        request.method = "POST"
        
        result = await billing_middleware._determine_usage_type(request)
        
        assert result == UsageType.STORAGE_MB

    @pytest.mark.asyncio
    async def test_determine_usage_type_chat_tokens(self, billing_middleware):
        """Test determining usage type for chat endpoints."""
        request = Mock()
        request.url.path = "/chat/completion"
        request.method = "POST"
        
        result = await billing_middleware._determine_usage_type(request)
        
        assert result == UsageType.TOKENS_IN

    @pytest.mark.asyncio
    async def test_rate_limit_within_limits(self, billing_middleware):
        """Test rate limiting when within limits."""
        tenant_id = "tenant_123"
        
        request = Mock()
        request.url.path = "/api/test"
        request.method = "POST"
        
        # Mock Redis - current count is 50 (within limit of 100)
        billing_middleware.redis.get.return_value = "50"
        
        result = await billing_middleware._check_rate_limit(request, tenant_id)
        
        assert result.action == BillingAction.ALLOW
        assert result.status_code == 200
        assert "Rate limit OK" in result.message
        
        # Should increment counter
        billing_middleware.redis.incr.assert_called_once()
        billing_middleware.redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, billing_middleware):
        """Test rate limiting when limit is exceeded."""
        tenant_id = "tenant_123"
        
        request = Mock()
        request.url.path = "/api/test"
        request.method = "POST"
        
        # Mock Redis - current count is 100 (at limit)
        billing_middleware.redis.get.return_value = "100"
        
        result = await billing_middleware._check_rate_limit(request, tenant_id)
        
        assert result.action == BillingAction.BLOCK
        assert result.status_code == 429
        assert "Rate limit exceeded" in result.message
        
        # Should not increment counter
        billing_middleware.redis.incr.assert_not_called()

    @pytest.mark.asyncio
    async def test_usage_limits_within_threshold(self, billing_middleware):
        """Test usage limits when within threshold."""
        tenant_id = "tenant_123"
        usage_type = UsageType.API_CALLS
        
        # Mock usage tracker
        billing_middleware.usage_tracker._get_current_usage.return_value = 50.0
        
        # Mock usage limit
        limit_key = f"usage_limit:{tenant_id}:{usage_type.value}"
        billing_middleware.usage_tracker.usage_limits[limit_key] = Mock()
        billing_middleware.usage_tracker.usage_limits[limit_key].limit = 100.0
        
        result = await billing_middleware._check_usage_limits(tenant_id, usage_type)
        
        assert result.action == BillingAction.ALLOW
        assert result.status_code == 200
        assert "Usage within limits" in result.message

    @pytest.mark.asyncio
    async def test_usage_limits_warning_threshold(self, billing_middleware):
        """Test usage limits when at warning threshold."""
        tenant_id = "tenant_123"
        usage_type = UsageType.API_CALLS
        
        # Mock usage tracker - 75% usage (above warn threshold of 70%)
        billing_middleware.usage_tracker._get_current_usage.return_value = 75.0
        
        # Mock usage limit
        limit_key = f"usage_limit:{tenant_id}:{usage_type.value}"
        billing_middleware.usage_tracker.usage_limits[limit_key] = Mock()
        billing_middleware.usage_tracker.usage_limits[limit_key].limit = 100.0
        
        result = await billing_middleware._check_usage_limits(tenant_id, usage_type)
        
        assert result.action == BillingAction.WARN
        assert result.status_code == 200
        assert "Usage approaching limit, warning" in result.message

    @pytest.mark.asyncio
    async def test_usage_limits_throttle_threshold(self, billing_middleware):
        """Test usage limits when at throttle threshold."""
        tenant_id = "tenant_123"
        usage_type = UsageType.API_CALLS
        
        # Mock usage tracker - 85% usage (above throttle threshold of 80%)
        billing_middleware.usage_tracker._get_current_usage.return_value = 85.0
        
        # Mock usage limit
        limit_key = f"usage_limit:{tenant_id}:{usage_type.value}"
        billing_middleware.usage_tracker.usage_limits[limit_key] = Mock()
        billing_middleware.usage_tracker.usage_limits[limit_key].limit = 100.0
        
        result = await billing_middleware._check_usage_limits(tenant_id, usage_type)
        
        assert result.action == BillingAction.THROTTLE
        assert result.status_code == 200
        assert "Usage approaching limit, throttling" in result.message

    @pytest.mark.asyncio
    async def test_usage_limits_block_threshold(self, billing_middleware):
        """Test usage limits when at block threshold."""
        tenant_id = "tenant_123"
        usage_type = UsageType.API_CALLS
        
        # Mock usage tracker - 100% usage (at block threshold)
        billing_middleware.usage_tracker._get_current_usage.return_value = 100.0
        
        # Mock usage limit
        limit_key = f"usage_limit:{tenant_id}:{usage_type.value}"
        billing_middleware.usage_tracker.usage_limits[limit_key] = Mock()
        billing_middleware.usage_tracker.usage_limits[limit_key].limit = 100.0
        
        result = await billing_middleware._check_usage_limits(tenant_id, usage_type)
        
        assert result.action == BillingAction.BLOCK
        assert result.status_code == 429
        assert "Usage limit exceeded" in result.message

    @pytest.mark.asyncio
    async def test_no_usage_limit_set(self, billing_middleware):
        """Test usage limits when no limit is set."""
        tenant_id = "tenant_123"
        usage_type = UsageType.API_CALLS
        
        # Mock usage tracker
        billing_middleware.usage_tracker._get_current_usage.return_value = 50.0
        
        # No usage limit set
        billing_middleware.usage_tracker.usage_limits = {}
        
        result = await billing_middleware._check_usage_limits(tenant_id, usage_type)
        
        assert result.action == BillingAction.ALLOW
        assert result.status_code == 200
        assert "No usage limit set" in result.message

    @pytest.mark.asyncio
    async def test_throttle_action_adds_delay(self, billing_middleware):
        """Test that throttle action adds delay."""
        tenant_id = "tenant_123"
        
        # Mock request
        request = Mock()
        request.headers = {"X-Tenant-ID": tenant_id}
        request.url.path = "/api/test"
        request.method = "POST"
        request.client = Mock()
        request.client.host = "192.168.1.1"
        
        # Mock call_next
        call_next = AsyncMock()
        response = Response()
        response.status_code = 200
        response.headers = {}
        call_next.return_value = response
        
        # Mock usage tracker to return throttle action
        billing_middleware.usage_tracker._get_current_usage.return_value = 85.0
        
        # Mock usage limit
        limit_key = f"usage_limit:{tenant_id}:api_calls"
        billing_middleware.usage_tracker.usage_limits[limit_key] = Mock()
        billing_middleware.usage_tracker.usage_limits[limit_key].limit = 100.0
        
        # Mock Redis for rate limiting
        billing_middleware.redis.get.return_value = "50"
        
        start_time = time.time()
        result = await billing_middleware(request, call_next)
        end_time = time.time()
        
        # Should add delay (at least 0.1 seconds)
        assert end_time - start_time >= 0.1
        assert result == response

    @pytest.mark.asyncio
    async def test_record_usage_after_successful_request(self, billing_middleware):
        """Test recording usage after successful request."""
        tenant_id = "tenant_123"
        
        # Mock request
        request = Mock()
        request.headers = {"X-Tenant-ID": tenant_id}
        request.url.path = "/api/test"
        request.method = "POST"
        request.client = Mock()
        request.client.host = "192.168.1.1"
        
        # Mock call_next
        call_next = AsyncMock()
        response = Response()
        response.status_code = 200
        response.headers = {"X-Token-Count": "50"}
        call_next.return_value = response
        
        # Mock usage tracker
        billing_middleware.usage_tracker._get_current_usage.return_value = 50.0
        
        # Mock usage limit
        limit_key = f"usage_limit:{tenant_id}:api_calls"
        billing_middleware.usage_tracker.usage_limits[limit_key] = Mock()
        billing_middleware.usage_tracker.usage_limits[limit_key].limit = 100.0
        
        # Mock Redis for rate limiting
        billing_middleware.redis.get.return_value = "50"
        
        await billing_middleware(request, call_next)
        
        # Should record usage
        billing_middleware.usage_tracker.record_usage.assert_called_once()
        
        # Should process webhook
        billing_middleware.webhook_aggregator.process_webhook.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_usage_recorded_on_failed_request(self, billing_middleware):
        """Test that usage is not recorded on failed request."""
        tenant_id = "tenant_123"
        
        # Mock request
        request = Mock()
        request.headers = {"X-Tenant-ID": tenant_id}
        request.url.path = "/api/test"
        request.method = "POST"
        request.client = Mock()
        request.client.host = "192.168.1.1"
        
        # Mock call_next returning error
        call_next = AsyncMock()
        response = Response()
        response.status_code = 500
        response.headers = {}
        call_next.return_value = response
        
        # Mock usage tracker
        billing_middleware.usage_tracker._get_current_usage.return_value = 50.0
        
        # Mock usage limit
        limit_key = f"usage_limit:{tenant_id}:api_calls"
        billing_middleware.usage_tracker.usage_limits[limit_key] = Mock()
        billing_middleware.usage_tracker.usage_limits[limit_key].limit = 100.0
        
        # Mock Redis for rate limiting
        billing_middleware.redis.get.return_value = "50"
        
        await billing_middleware(request, call_next)
        
        # Should not record usage for failed requests
        billing_middleware.usage_tracker.record_usage.assert_not_called()
        billing_middleware.webhook_aggregator.process_webhook.assert_not_called()

    @pytest.mark.asyncio
    async def test_calculate_usage_quantity_api_calls(self, billing_middleware):
        """Test calculating usage quantity for API calls."""
        request = Mock()
        response = Mock()
        response.headers = {}
        
        result = await billing_middleware._calculate_usage_quantity(
            request, response, UsageType.API_CALLS
        )
        
        assert result == 1.0

    @pytest.mark.asyncio
    async def test_calculate_usage_quantity_tokens_from_headers(self, billing_middleware):
        """Test calculating usage quantity for tokens from response headers."""
        request = Mock()
        response = Mock()
        response.headers = {"X-Token-Count": "150"}
        
        result = await billing_middleware._calculate_usage_quantity(
            request, response, UsageType.TOKENS_IN
        )
        
        assert result == 150.0

    @pytest.mark.asyncio
    async def test_calculate_usage_quantity_tokens_from_content_length(self, billing_middleware):
        """Test calculating usage quantity for tokens from content length."""
        request = Mock()
        response = Mock()
        response.headers = {"Content-Length": "400"}
        
        result = await billing_middleware._calculate_usage_quantity(
            request, response, UsageType.TOKENS_IN
        )
        
        assert result == 100.0  # 400 / 4

    @pytest.mark.asyncio
    async def test_calculate_usage_quantity_storage_from_headers(self, billing_middleware):
        """Test calculating usage quantity for storage from response headers."""
        request = Mock()
        response = Mock()
        response.headers = {"X-Storage-Size": "2097152"}  # 2MB in bytes
        
        result = await billing_middleware._calculate_usage_quantity(
            request, response, UsageType.STORAGE_MB
        )
        
        assert result == 2.0  # 2MB

    @pytest.mark.asyncio
    async def test_billing_limits_disabled(self, billing_middleware):
        """Test billing limits when disabled."""
        # Disable limits
        billing_middleware.config.enforce_limits = False
        
        tenant_id = "tenant_123"
        
        # Mock request
        request = Mock()
        request.headers = {"X-Tenant-ID": tenant_id}
        request.url.path = "/api/test"
        request.method = "POST"
        request.client = Mock()
        request.client.host = "192.168.1.1"
        
        # Mock call_next
        call_next = AsyncMock()
        response = Response()
        response.status_code = 200
        response.headers = {}
        call_next.return_value = response
        
        result = await billing_middleware(request, call_next)
        
        # Should allow request without checking limits
        call_next.assert_called_once_with(request)
        assert result == response

    @pytest.mark.asyncio
    async def test_error_handling_graceful_degradation(self, billing_middleware):
        """Test error handling with graceful degradation."""
        tenant_id = "tenant_123"
        
        # Mock request
        request = Mock()
        request.headers = {"X-Tenant-ID": tenant_id}
        request.url.path = "/api/test"
        request.method = "POST"
        request.client = Mock()
        request.client.host = "192.168.1.1"
        
        # Mock call_next
        call_next = AsyncMock()
        response = Response()
        response.status_code = 200
        response.headers = {}
        call_next.return_value = response
        
        # Mock usage tracker to raise exception
        billing_middleware.usage_tracker._get_current_usage.side_effect = Exception("Database error")
        
        result = await billing_middleware(request, call_next)
        
        # Should allow request on error (fail open)
        call_next.assert_called_once_with(request)
        assert result == response

    @pytest.mark.asyncio
    async def test_get_tenant_usage_summary(self, billing_middleware):
        """Test getting tenant usage summary."""
        tenant_id = "tenant_123"
        
        # Mock usage tracker
        mock_summary = {
            "usage_types": {
                "api_calls": {"total_usage": 100, "usage_limit": 1000},
                "tokens": {"total_usage": 5000, "usage_limit": 10000}
            }
        }
        billing_middleware.usage_tracker.get_all_usage_summary = AsyncMock(return_value=mock_summary)
        
        result = await billing_middleware.get_tenant_usage_summary(tenant_id)
        
        assert result == mock_summary
        billing_middleware.usage_tracker.get_all_usage_summary.assert_called_once_with(tenant_id)

    @pytest.mark.asyncio
    async def test_get_tenant_billing_status(self, billing_middleware):
        """Test getting tenant billing status."""
        tenant_id = "tenant_123"
        
        # Mock usage summary
        mock_summary = {
            "usage_types": {
                "api_calls": {"total_usage": 100, "usage_limit": 1000, "usage_percentage": 0.1},
                "tokens": {"total_usage": 8500, "usage_limit": 10000, "usage_percentage": 0.85}
            }
        }
        
        with patch.object(billing_middleware, "get_tenant_usage_summary") as mock_get_summary:
            mock_get_summary.return_value = mock_summary
            
            result = await billing_middleware.get_tenant_billing_status(tenant_id)
            
            assert result["tenant_id"] == tenant_id
            assert "usage_summary" in result
            assert "limits_exceeded" in result
            assert "warnings" in result
            assert "billing_status" in result
            
            # Should have warnings for tokens (85% > 70% warn threshold)
            assert len(result["warnings"]) == 1
            assert result["warnings"][0]["usage_type"] == "tokens"
            
            # Should be active (no limits exceeded)
            assert result["billing_status"] == "active"
