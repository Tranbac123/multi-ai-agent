"""Test tenant context middleware functionality."""

import pytest
import time
import jwt
from unittest.mock import Mock, AsyncMock, patch
from fastapi import Request
from fastapi.responses import JSONResponse

from apps.api_gateway.middleware.tenant_context import TenantContextMiddleware


class TestTenantContextMiddleware:
    """Test TenantContextMiddleware functionality."""

    @pytest.fixture
    def jwt_secret(self):
        """Create JWT secret for testing."""
        return "test-secret-key"

    @pytest.fixture
    def tenant_middleware(self, jwt_secret):
        """Create TenantContextMiddleware instance."""
        return TenantContextMiddleware(jwt_secret)

    @pytest.mark.asyncio
    async def test_set_tenant_context_with_jwt_token(self, tenant_middleware, jwt_secret):
        """Test setting tenant context with valid JWT token."""
        tenant_id = "tenant_123"
        
        # Create JWT token
        token_payload = {
            "tenant_id": tenant_id,
            "user_id": "user_456",
            "exp": time.time() + 3600
        }
        token = jwt.encode(token_payload, jwt_secret, algorithm="HS256")
        
        # Mock request with JWT token
        request = Mock()
        request.headers = {"Authorization": f"Bearer {token}"}
        
        # Mock call_next
        call_next = AsyncMock()
        response = Mock()
        response.status_code = 200
        call_next.return_value = response
        
        result = await tenant_middleware.set_tenant_context(request, call_next)
        
        # Should set tenant context
        assert hasattr(request.state, "tenant_id")
        assert hasattr(request.state, "request_id")
        assert request.state.tenant_id == tenant_id
        assert request.state.request_id is not None
        
        # Should call next
        call_next.assert_called_once_with(request)
        assert result == response

    @pytest.mark.asyncio
    async def test_set_tenant_context_with_invalid_jwt_token(self, tenant_middleware):
        """Test setting tenant context with invalid JWT token."""
        # Mock request with invalid JWT token
        request = Mock()
        request.headers = {"Authorization": "Bearer invalid-token"}
        
        # Mock call_next
        call_next = AsyncMock()
        
        result = await tenant_middleware.set_tenant_context(request, call_next)
        
        # Should not set tenant context
        assert not hasattr(request.state, "tenant_id")
        
        # Should still call next (graceful degradation)
        call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_set_tenant_context_with_api_key(self, tenant_middleware):
        """Test setting tenant context with API key."""
        tenant_id = "tenant_789"
        api_key = "api_key_123"
        
        # Mock request with API key
        request = Mock()
        request.headers = {"X-API-Key": api_key}
        
        # Mock API key lookup
        with patch.object(tenant_middleware, "_lookup_tenant_from_api_key") as mock_lookup:
            mock_lookup.return_value = tenant_id
            
            # Mock call_next
            call_next = AsyncMock()
            response = Mock()
            response.status_code = 200
            call_next.return_value = response
            
            result = await tenant_middleware.set_tenant_context(request, call_next)
            
            # Should set tenant context
            assert hasattr(request.state, "tenant_id")
            assert request.state.tenant_id == tenant_id
            
            # Should call API key lookup
            mock_lookup.assert_called_once_with(api_key)
            
            # Should call next
            call_next.assert_called_once_with(request)
            assert result == response

    @pytest.mark.asyncio
    async def test_set_tenant_context_with_no_auth(self, tenant_middleware):
        """Test setting tenant context with no authentication."""
        # Mock request without authentication
        request = Mock()
        request.headers = {}
        
        # Mock call_next
        call_next = AsyncMock()
        response = Mock()
        response.status_code = 200
        call_next.return_value = response
        
        result = await tenant_middleware.set_tenant_context(request, call_next)
        
        # Should not set tenant context
        assert not hasattr(request.state, "tenant_id")
        
        # Should still call next
        call_next.assert_called_once_with(request)
        assert result == response

    @pytest.mark.asyncio
    async def test_set_tenant_context_error_handling(self, tenant_middleware):
        """Test error handling in tenant context middleware."""
        # Mock request that will cause an error
        request = Mock()
        request.headers = {"Authorization": "Bearer invalid-token"}
        
        # Mock call_next to raise exception
        call_next = AsyncMock()
        call_next.side_effect = Exception("Request processing error")
        
        result = await tenant_middleware.set_tenant_context(request, call_next)
        
        # Should return error response
        assert isinstance(result, JSONResponse)
        assert result.status_code == 401
        
        # Parse response body
        import json
        body = json.loads(result.body.decode())
        
        assert "success" in body
        assert body["success"] is False
        assert "error" in body
        assert body["error"]["error_type"] == "authentication_error"
        assert body["error"]["error_code"] == "TENANT_CONTEXT_ERROR"

    @pytest.mark.asyncio
    async def test_extract_tenant_id_from_jwt(self, tenant_middleware, jwt_secret):
        """Test extracting tenant ID from JWT token."""
        tenant_id = "tenant_456"
        
        # Create JWT token
        token_payload = {
            "tenant_id": tenant_id,
            "user_id": "user_789",
            "exp": time.time() + 3600
        }
        token = jwt.encode(token_payload, jwt_secret, algorithm="HS256")
        
        # Mock request
        request = Mock()
        request.headers = {"Authorization": f"Bearer {token}"}
        
        result = await tenant_middleware._extract_tenant_id(request)
        
        assert result == tenant_id

    @pytest.mark.asyncio
    async def test_extract_tenant_id_from_api_key(self, tenant_middleware):
        """Test extracting tenant ID from API key."""
        tenant_id = "tenant_789"
        api_key = "api_key_456"
        
        # Mock request
        request = Mock()
        request.headers = {"X-API-Key": api_key}
        
        # Mock API key lookup
        with patch.object(tenant_middleware, "_lookup_tenant_from_api_key") as mock_lookup:
            mock_lookup.return_value = tenant_id
            
            result = await tenant_middleware._extract_tenant_id(request)
            
            assert result == tenant_id
            mock_lookup.assert_called_once_with(api_key)

    @pytest.mark.asyncio
    async def test_extract_tenant_id_no_auth(self, tenant_middleware):
        """Test extracting tenant ID with no authentication."""
        # Mock request without authentication
        request = Mock()
        request.headers = {}
        
        result = await tenant_middleware._extract_tenant_id(request)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_tenant_from_api_key(self, tenant_middleware):
        """Test looking up tenant from API key."""
        api_key = "test_api_key"
        
        result = await tenant_middleware._lookup_tenant_from_api_key(api_key)
        
        # Should return None (not implemented yet)
        assert result is None

    @pytest.mark.asyncio
    async def test_set_db_tenant_context(self, tenant_middleware):
        """Test setting database tenant context."""
        tenant_id = "tenant_123"
        
        # Should not raise exception
        await tenant_middleware._set_db_tenant_context(tenant_id)

    @pytest.mark.asyncio
    async def test_reset_db_tenant_context(self, tenant_middleware):
        """Test resetting database tenant context."""
        # Should not raise exception
        await tenant_middleware._reset_db_tenant_context()

    @pytest.mark.asyncio
    async def test_jwt_token_expired(self, tenant_middleware, jwt_secret):
        """Test handling of expired JWT token."""
        tenant_id = "tenant_123"
        
        # Create expired JWT token
        token_payload = {
            "tenant_id": tenant_id,
            "user_id": "user_456",
            "exp": time.time() - 3600  # Expired
        }
        token = jwt.encode(token_payload, jwt_secret, algorithm="HS256")
        
        # Mock request with expired JWT token
        request = Mock()
        request.headers = {"Authorization": f"Bearer {token}"}
        
        result = await tenant_middleware._extract_tenant_id(request)
        
        # Should return None for expired token
        assert result is None

    @pytest.mark.asyncio
    async def test_jwt_token_wrong_secret(self, tenant_middleware):
        """Test handling of JWT token with wrong secret."""
        tenant_id = "tenant_123"
        
        # Create JWT token with wrong secret
        token_payload = {
            "tenant_id": tenant_id,
            "user_id": "user_456",
            "exp": time.time() + 3600
        }
        token = jwt.encode(token_payload, "wrong-secret", algorithm="HS256")
        
        # Mock request with JWT token
        request = Mock()
        request.headers = {"Authorization": f"Bearer {token}"}
        
        result = await tenant_middleware._extract_tenant_id(request)
        
        # Should return None for invalid token
        assert result is None

    @pytest.mark.asyncio
    async def test_malformed_authorization_header(self, tenant_middleware):
        """Test handling of malformed authorization header."""
        # Mock request with malformed authorization header
        request = Mock()
        request.headers = {"Authorization": "InvalidFormat"}
        
        result = await tenant_middleware._extract_tenant_id(request)
        
        # Should return None
        assert result is None

    @pytest.mark.asyncio
    async def test_bearer_token_without_space(self, tenant_middleware):
        """Test handling of Bearer token without space."""
        # Mock request with malformed Bearer token
        request = Mock()
        request.headers = {"Authorization": "Bearertoken123"}
        
        result = await tenant_middleware._extract_tenant_id(request)
        
        # Should return None
        assert result is None

    @pytest.mark.asyncio
    async def test_request_id_generation(self, tenant_middleware, jwt_secret):
        """Test that request ID is generated for each request."""
        tenant_id = "tenant_123"
        
        # Create JWT token
        token_payload = {
            "tenant_id": tenant_id,
            "user_id": "user_456",
            "exp": time.time() + 3600
        }
        token = jwt.encode(token_payload, jwt_secret, algorithm="HS256")
        
        # Mock request
        request = Mock()
        request.headers = {"Authorization": f"Bearer {token}"}
        
        # Mock call_next
        call_next = AsyncMock()
        response = Mock()
        response.status_code = 200
        call_next.return_value = response
        
        await tenant_middleware.set_tenant_context(request, call_next)
        
        # Should generate unique request ID
        assert hasattr(request.state, "request_id")
        assert request.state.request_id is not None
        assert isinstance(request.state.request_id, str)
        assert len(request.state.request_id) > 0

    @pytest.mark.asyncio
    async def test_multiple_requests_different_ids(self, tenant_middleware, jwt_secret):
        """Test that multiple requests get different request IDs."""
        tenant_id = "tenant_123"
        
        # Create JWT token
        token_payload = {
            "tenant_id": tenant_id,
            "user_id": "user_456",
            "exp": time.time() + 3600
        }
        token = jwt.encode(token_payload, jwt_secret, algorithm="HS256")
        
        request_ids = []
        
        for _ in range(3):
            # Mock request
            request = Mock()
            request.headers = {"Authorization": f"Bearer {token}"}
            
            # Mock call_next
            call_next = AsyncMock()
            response = Mock()
            response.status_code = 200
            call_next.return_value = response
            
            await tenant_middleware.set_tenant_context(request, call_next)
            
            request_ids.append(request.state.request_id)
        
        # All request IDs should be different
        assert len(set(request_ids)) == 3
