"""Test quota enforcement middleware functionality."""

import pytest
import time
from unittest.mock import Mock, AsyncMock, patch
from fastapi import Request, Response
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from apps.api_gateway.middleware.quota_enforcement import (
    QuotaEnforcementMiddleware,
    QuotaStatus,
    QuotaCheck,
)
from apps.billing_service.core.usage_tracker import UsageType


class TestQuotaEnforcementMiddleware:
    """Test QuotaEnforcementMiddleware functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis_client = Mock()
        redis_client.get = AsyncMock()
        redis_client.setex = AsyncMock()
        return redis_client

    @pytest.fixture
    def mock_usage_tracker(self):
        """Create mock usage tracker."""
        usage_tracker = Mock()
        usage_tracker.get_current_usage = AsyncMock()
        usage_tracker.record_usage = AsyncMock()
        return usage_tracker

    @pytest.fixture
    def quota_middleware(self, mock_redis, mock_usage_tracker):
        """Create QuotaEnforcementMiddleware instance."""
        # Create a simple FastAPI app for testing
        from fastapi import FastAPI
        app = FastAPI()
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        return QuotaEnforcementMiddleware(app, mock_redis, mock_usage_tracker)

    @pytest.mark.asyncio
    async def test_skip_quota_check_for_health_endpoints(self, quota_middleware):
        """Test that quota checks are skipped for health endpoints."""
        # Mock request
        request = Mock()
        request.url.path = "/health"
        request.headers = {}
        request.query_params = {}
        
        # Mock call_next
        call_next = AsyncMock()
        response = Response()
        response.status_code = 200
        call_next.return_value = response
        
        result = await quota_middleware.dispatch(request, call_next)
        
        # Should call next without quota checks
        call_next.assert_called_once_with(request)
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_skip_quota_check_for_docs_endpoints(self, quota_middleware):
        """Test that quota checks are skipped for docs endpoints."""
        request = Mock()
        request.url.path = "/docs"
        request.headers = {}
        request.query_params = {}
        
        call_next = AsyncMock()
        response = Response()
        response.status_code = 200
        call_next.return_value = response
        
        result = await quota_middleware.dispatch(request, call_next)
        
        call_next.assert_called_once_with(request)
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_quota_check_within_limits(self, quota_middleware, mock_usage_tracker):
        """Test quota check when usage is within limits."""
        tenant_id = "tenant_123"
        
        # Mock request with tenant ID
        request = Mock()
        request.url.path = "/api/chat"
        request.headers = {"X-Tenant-ID": tenant_id, "content-length": "100"}
        request.query_params = {}
        
        # Mock usage tracker
        mock_usage_tracker.get_current_usage.return_value = 100.0  # Current usage
        
        # Mock Redis for quota limit
        quota_middleware.redis_client.get.return_value = "1000.0"  # Quota limit
        
        call_next = AsyncMock()
        response = Response()
        response.status_code = 200
        call_next.return_value = response
        
        result = await quota_middleware.dispatch(request, call_next)
        
        # Should allow request
        call_next.assert_called_once_with(request)
        assert result.status_code == 200
        
        # Should record usage
        mock_usage_tracker.record_usage.assert_called()

    @pytest.mark.asyncio
    async def test_quota_check_exceeded(self, quota_middleware, mock_usage_tracker):
        """Test quota check when usage is exceeded."""
        tenant_id = "tenant_123"
        
        # Mock request with tenant ID
        request = Mock()
        request.url.path = "/api/chat"
        request.headers = {"X-Tenant-ID": tenant_id, "content-length": "100"}
        request.query_params = {}
        
        # Mock usage tracker - high current usage
        mock_usage_tracker.get_current_usage.return_value = 950.0  # High usage
        
        # Mock Redis for quota limit
        quota_middleware.redis_client.get.return_value = "1000.0"  # Quota limit
        
        call_next = AsyncMock()
        
        result = await quota_middleware.dispatch(request, call_next)
        
        # Should not call next (request blocked)
        call_next.assert_not_called()
        
        # Should return 429 status
        assert result.status_code == 429
        assert "Quota Exceeded" in result.body.decode()

    @pytest.mark.asyncio
    async def test_quota_check_unlimited(self, quota_middleware, mock_usage_tracker):
        """Test quota check when quota is unlimited."""
        tenant_id = "tenant_123"
        
        # Mock request with tenant ID
        request = Mock()
        request.url.path = "/api/chat"
        request.headers = {"X-Tenant-ID": tenant_id, "content-length": "100"}
        request.query_params = {}
        
        # Mock usage tracker
        mock_usage_tracker.get_current_usage.return_value = 100.0
        
        # Mock Redis - no quota limit (unlimited)
        quota_middleware.redis_client.get.return_value = None
        
        call_next = AsyncMock()
        response = Response()
        response.status_code = 200
        call_next.return_value = response
        
        result = await quota_middleware.dispatch(request, call_next)
        
        # Should allow request
        call_next.assert_called_once_with(request)
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_quota_check_with_query_params(self, quota_middleware, mock_usage_tracker):
        """Test quota check when tenant ID is in query params."""
        tenant_id = "tenant_456"
        
        # Mock request with tenant ID in query params
        request = Mock()
        request.url.path = "/api/completion"
        request.headers = {"content-length": "200"}
        request.query_params = {"tenant_id": tenant_id}
        
        # Mock usage tracker
        mock_usage_tracker.get_current_usage.return_value = 100.0
        
        # Mock Redis for quota limit
        quota_middleware.redis_client.get.return_value = "1000.0"
        
        call_next = AsyncMock()
        response = Response()
        response.status_code = 200
        call_next.return_value = response
        
        result = await quota_middleware.dispatch(request, call_next)
        
        # Should allow request
        call_next.assert_called_once_with(request)
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_no_tenant_id_proceeds(self, quota_middleware):
        """Test that requests without tenant ID proceed without quota checks."""
        # Mock request without tenant ID
        request = Mock()
        request.url.path = "/api/test"
        request.headers = {}
        request.query_params = {}
        
        call_next = AsyncMock()
        response = Response()
        response.status_code = 200
        call_next.return_value = response
        
        result = await quota_middleware.dispatch(request, call_next)
        
        # Should call next without quota checks
        call_next.assert_called_once_with(request)
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_record_usage_after_successful_request(self, quota_middleware, mock_usage_tracker):
        """Test that usage is recorded after successful request."""
        tenant_id = "tenant_123"
        
        # Mock request
        request = Mock()
        request.url.path = "/api/chat"
        request.headers = {"X-Tenant-ID": tenant_id, "content-length": "100"}
        request.query_params = {}
        request.url.path = "/api/chat"
        request.method = "POST"
        
        # Mock usage tracker
        mock_usage_tracker.get_current_usage.return_value = 100.0
        
        # Mock Redis for quota limit
        quota_middleware.redis_client.get.return_value = "1000.0"
        
        call_next = AsyncMock()
        response = Response()
        response.status_code = 200
        call_next.return_value = response
        
        await quota_middleware.dispatch(request, call_next)
        
        # Should record API call usage
        mock_usage_tracker.record_usage.assert_called()
        
        # Check that API_CALLS usage was recorded
        api_call_recorded = False
        token_usage_recorded = False
        
        for call in mock_usage_tracker.record_usage.call_args_list:
            args, kwargs = call
            if args[1] == UsageType.API_CALLS:  # tenant_id, usage_type, quantity, metadata
                api_call_recorded = True
            elif args[1] == UsageType.TOKENS:
                token_usage_recorded = True
        
        assert api_call_recorded
        assert token_usage_recorded

    @pytest.mark.asyncio
    async def test_no_usage_recorded_on_failed_request(self, quota_middleware, mock_usage_tracker):
        """Test that usage is not recorded on failed request."""
        tenant_id = "tenant_123"
        
        # Mock request
        request = Mock()
        request.url.path = "/api/chat"
        request.headers = {"X-Tenant-ID": tenant_id, "content-length": "100"}
        request.query_params = {}
        request.url.path = "/api/chat"
        request.method = "POST"
        
        # Mock usage tracker
        mock_usage_tracker.get_current_usage.return_value = 100.0
        
        # Mock Redis for quota limit
        quota_middleware.redis_client.get.return_value = "1000.0"
        
        call_next = AsyncMock()
        response = Response()
        response.status_code = 500  # Failed request
        call_next.return_value = response
        
        await quota_middleware.dispatch(request, call_next)
        
        # Should not record usage for failed requests
        mock_usage_tracker.record_usage.assert_not_called()

    @pytest.mark.asyncio
    async def test_quota_check_error_handling(self, quota_middleware, mock_usage_tracker):
        """Test quota check error handling."""
        tenant_id = "tenant_123"
        
        # Mock request
        request = Mock()
        request.url.path = "/api/chat"
        request.headers = {"X-Tenant-ID": tenant_id, "content-length": "100"}
        request.query_params = {}
        
        # Mock usage tracker to raise exception
        mock_usage_tracker.get_current_usage.side_effect = Exception("Database error")
        
        call_next = AsyncMock()
        response = Response()
        response.status_code = 200
        call_next.return_value = response
        
        result = await quota_middleware.dispatch(request, call_next)
        
        # Should allow request on error (fail open)
        call_next.assert_called_once_with(request)
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_quota_reset_time_calculation(self, quota_middleware):
        """Test quota reset time calculation."""
        reset_time = quota_middleware._get_quota_reset_time()
        
        # Should be a valid timestamp
        assert isinstance(reset_time, float)
        assert reset_time > time.time()  # Should be in the future

    @pytest.mark.asyncio
    async def test_multiple_quota_types_checked(self, quota_middleware, mock_usage_tracker):
        """Test that multiple quota types are checked for appropriate requests."""
        tenant_id = "tenant_123"
        
        # Mock request for chat endpoint (should check both API calls and tokens)
        request = Mock()
        request.url.path = "/api/chat"
        request.headers = {"X-Tenant-ID": tenant_id, "content-length": "400"}
        request.query_params = {}
        
        # Mock usage tracker
        mock_usage_tracker.get_current_usage.return_value = 100.0
        
        # Mock Redis for quota limit
        quota_middleware.redis_client.get.return_value = "1000.0"
        
        call_next = AsyncMock()
        response = Response()
        response.status_code = 200
        call_next.return_value = response
        
        await quota_middleware.dispatch(request, call_next)
        
        # Should check both API calls and tokens quotas
        assert mock_usage_tracker.get_current_usage.call_count == 2
        
        # Check that both quota types were queried
        call_args = [call[0] for call in mock_usage_tracker.get_current_usage.call_args_list]
        usage_types = [args[1] for args in call_args]  # Second argument is usage_type
        
        assert UsageType.API_CALLS in usage_types
        assert UsageType.TOKENS in usage_types

    @pytest.mark.asyncio
    async def test_completion_endpoint_token_estimation(self, quota_middleware, mock_usage_tracker):
        """Test token estimation for completion endpoints."""
        tenant_id = "tenant_123"
        
        # Mock request for completion endpoint
        request = Mock()
        request.url.path = "/api/completion"
        request.headers = {"X-Tenant-ID": tenant_id, "content-length": "800"}
        request.query_params = {}
        
        # Mock usage tracker
        mock_usage_tracker.get_current_usage.return_value = 100.0
        
        # Mock Redis for quota limit
        quota_middleware.redis_client.get.return_value = "1000.0"
        
        call_next = AsyncMock()
        response = Response()
        response.status_code = 200
        call_next.return_value = response
        
        await quota_middleware.dispatch(request, call_next)
        
        # Should check tokens quota with estimated tokens (800/4 = 200)
        call_args = mock_usage_tracker.get_current_usage.call_args_list
        token_call = next((call for call in call_args if call[0][1] == UsageType.TOKENS), None)
        
        assert token_call is not None

    def test_default_quotas(self, quota_middleware):
        """Test default quota values."""
        default_quotas = quota_middleware.default_quotas
        
        assert UsageType.TOKENS in default_quotas
        assert UsageType.TOOL_CALLS in default_quotas
        assert UsageType.WS_CONNECTIONS in default_quotas
        assert UsageType.STORAGE in default_quotas
        assert UsageType.API_CALLS in default_quotas
        
        assert default_quotas[UsageType.TOKENS] == 1000000
        assert default_quotas[UsageType.TOOL_CALLS] == 10000
        assert default_quotas[UsageType.WS_CONNECTIONS] == 1000
        assert default_quotas[UsageType.STORAGE] == 1000
        assert default_quotas[UsageType.API_CALLS] == 100000

    @pytest.mark.asyncio
    async def test_quota_exceeded_response_format(self, quota_middleware, mock_usage_tracker):
        """Test quota exceeded response format."""
        tenant_id = "tenant_123"
        
        # Mock request
        request = Mock()
        request.url.path = "/api/chat"
        request.headers = {"X-Tenant-ID": tenant_id, "content-length": "100"}
        request.query_params = {}
        
        # Mock usage tracker - high usage
        mock_usage_tracker.get_current_usage.return_value = 950.0
        
        # Mock Redis for quota limit
        quota_middleware.redis_client.get.return_value = "1000.0"
        
        call_next = AsyncMock()
        
        result = await quota_middleware.dispatch(request, call_next)
        
        # Should return 429 with proper format
        assert result.status_code == 429
        assert "Retry-After" in result.headers
        
        # Parse response body
        import json
        body = json.loads(result.body.decode())
        
        assert "error" in body
        assert "message" in body
        assert "details" in body
        assert "retry_after" in body
        
        assert body["error"] == "Quota Exceeded"
        assert body["retry_after"] == 3600
