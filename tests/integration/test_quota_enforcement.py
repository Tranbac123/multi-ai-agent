"""Integration tests for quota enforcement and rate limiting."""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch
import redis.asyncio as redis

from libs.clients.rate_limiter import TokenBucketRateLimiter, QuotaEnforcer
from apps.api_gateway.middleware.quota_enforcement import QuotaEnforcementMiddleware


class TestTokenBucketRateLimiter:
    """Test token bucket rate limiter."""
    
    @pytest.fixture
    async def redis_client(self):
        """Create Redis client for testing."""
        client = redis.Redis(host='localhost', port=6379, db=1)
        yield client
        await client.flushdb()
        await client.close()
    
    @pytest.fixture
    def rate_limiter(self, redis_client):
        """Create rate limiter instance."""
        return TokenBucketRateLimiter(redis_client)
    
    async def test_rate_limiter_allows_requests_within_limit(self, rate_limiter):
        """Test that rate limiter allows requests within limit."""
        tenant_id = "test-tenant"
        plan = "free"
        scope = "api"
        capacity = 10
        tokens_per_interval = 5
        interval_seconds = 60
        
        # Should allow first 10 requests
        for i in range(10):
            is_allowed, remaining, cap = await rate_limiter.is_allowed(
                tenant_id, plan, scope, capacity, tokens_per_interval, interval_seconds
            )
            assert is_allowed is True
            assert remaining == 9 - i
            assert cap == capacity
        
        # 11th request should be denied
        is_allowed, remaining, cap = await rate_limiter.is_allowed(
            tenant_id, plan, scope, capacity, tokens_per_interval, interval_seconds
        )
        assert is_allowed is False
        assert remaining == 0
        assert cap == capacity
    
    async def test_rate_limiter_refills_tokens_over_time(self, rate_limiter):
        """Test that rate limiter refills tokens over time."""
        tenant_id = "test-tenant"
        plan = "free"
        scope = "api"
        capacity = 5
        tokens_per_interval = 2
        interval_seconds = 1  # 1 second interval for testing
        
        # Exhaust all tokens
        for i in range(5):
            is_allowed, remaining, cap = await rate_limiter.is_allowed(
                tenant_id, plan, scope, capacity, tokens_per_interval, interval_seconds
            )
            assert is_allowed is True
        
        # Next request should be denied
        is_allowed, remaining, cap = await rate_limiter.is_allowed(
            tenant_id, plan, scope, capacity, tokens_per_interval, interval_seconds
        )
        assert is_allowed is False
        
        # Wait for refill
        await asyncio.sleep(1.1)
        
        # Should allow 2 more requests (tokens_per_interval)
        for i in range(2):
            is_allowed, remaining, cap = await rate_limiter.is_allowed(
                tenant_id, plan, scope, capacity, tokens_per_interval, interval_seconds
            )
            assert is_allowed is True
    
    async def test_rate_limiter_different_tenants_isolated(self, rate_limiter):
        """Test that different tenants have isolated rate limits."""
        tenant1 = "tenant-1"
        tenant2 = "tenant-2"
        plan = "free"
        scope = "api"
        capacity = 5
        tokens_per_interval = 2
        interval_seconds = 60
        
        # Exhaust tenant1's tokens
        for i in range(5):
            is_allowed, remaining, cap = await rate_limiter.is_allowed(
                tenant1, plan, scope, capacity, tokens_per_interval, interval_seconds
            )
            assert is_allowed is True
        
        # Tenant1 should be denied
        is_allowed, remaining, cap = await rate_limiter.is_allowed(
            tenant1, plan, scope, capacity, tokens_per_interval, interval_seconds
        )
        assert is_allowed is False
        
        # Tenant2 should still be allowed
        is_allowed, remaining, cap = await rate_limiter.is_allowed(
            tenant2, plan, scope, capacity, tokens_per_interval, interval_seconds
        )
        assert is_allowed is True
        assert remaining == 4


class TestQuotaEnforcer:
    """Test quota enforcer."""
    
    @pytest.fixture
    async def redis_client(self):
        """Create Redis client for testing."""
        client = redis.Redis(host='localhost', port=6379, db=2)
        yield client
        await client.flushdb()
        await client.close()
    
    @pytest.fixture
    def mock_db_client(self):
        """Create mock database client."""
        mock_client = AsyncMock()
        mock_session = AsyncMock()
        mock_client.get_session.return_value.__aenter__.return_value = mock_session
        return mock_client
    
    @pytest.fixture
    def quota_enforcer(self, redis_client, mock_db_client):
        """Create quota enforcer instance."""
        return QuotaEnforcer(redis_client, mock_db_client)
    
    async def test_quota_check_within_limits(self, quota_enforcer, mock_db_client):
        """Test quota check when within limits."""
        # Mock plan quotas
        mock_db_client.get_session.return_value.__aenter__.return_value.execute.return_value.fetchone.return_value = [
            {
                "api_calls": 1000,
                "tokens_in": 100000,
                "tokens_out": 100000,
                "tool_calls": 500,
                "ws_minutes": 1000,
                "storage_mb": 1000,
                "rate_limits": {
                    "api": {
                        "capacity": 100,
                        "tokens_per_interval": 10,
                        "interval_seconds": 60
                    }
                }
            }
        ]
        
        # Mock current usage
        mock_db_client.get_session.return_value.__aenter__.return_value.execute.return_value.fetchone.return_value = [
            100,  # tokens_in
            50,   # tokens_out
            10,   # tool_calls
            5,    # ws_minutes
            100   # storage_mb
        ]
        
        is_allowed, quota_info = await quota_enforcer.check_quota(
            "test-tenant", "pro", "api", "api_calls"
        )
        
        assert is_allowed is True
        assert quota_info["plan"] == "pro"
        assert quota_info["scope"] == "api"
        assert quota_info["usage_type"] == "api_calls"
    
    async def test_quota_check_exceeds_limits(self, quota_enforcer, mock_db_client):
        """Test quota check when limits are exceeded."""
        # Mock plan quotas with low limits
        mock_db_client.get_session.return_value.__aenter__.return_value.execute.return_value.fetchone.return_value = [
            {
                "api_calls": 10,
                "tokens_in": 1000,
                "tokens_out": 1000,
                "tool_calls": 50,
                "ws_minutes": 100,
                "storage_mb": 100,
                "rate_limits": {
                    "api": {
                        "capacity": 5,
                        "tokens_per_interval": 1,
                        "interval_seconds": 60
                    }
                }
            }
        ]
        
        # Mock current usage that exceeds limits
        mock_db_client.get_session.return_value.__aenter__.return_value.execute.return_value.fetchone.return_value = [
            2000,  # tokens_in (exceeds 1000)
            50,    # tokens_out
            10,    # tool_calls
            5,     # ws_minutes
            100    # storage_mb
        ]
        
        is_allowed, quota_info = await quota_enforcer.check_quota(
            "test-tenant", "free", "api", "api_calls"
        )
        
        assert is_allowed is False
        assert quota_info["plan"] == "free"
        assert "remaining" in quota_info
        assert quota_info["remaining"]["tokens_in"] == 0  # Exceeded limit
    
    async def test_usage_increment(self, quota_enforcer, mock_db_client):
        """Test usage increment functionality."""
        # Mock successful database update
        mock_db_client.get_session.return_value.__aenter__.return_value.execute.return_value = None
        mock_db_client.get_session.return_value.__aenter__.return_value.commit.return_value = None
        
        result = await quota_enforcer.increment_usage(
            "test-tenant", "api_calls", 1
        )
        
        assert result is True
        mock_db_client.get_session.assert_called_once()
        mock_db_client.get_session.return_value.__aenter__.return_value.execute.assert_called_once()
        mock_db_client.get_session.return_value.__aenter__.return_value.commit.assert_called_once()


class TestQuotaEnforcementMiddleware:
    """Test quota enforcement middleware."""
    
    @pytest.fixture
    def mock_quota_enforcer(self):
        """Create mock quota enforcer."""
        return AsyncMock()
    
    @pytest.fixture
    def middleware(self, mock_quota_enforcer):
        """Create quota enforcement middleware."""
        return QuotaEnforcementMiddleware(mock_quota_enforcer)
    
    async def test_quota_enforcement_decorator_allows_request(self, middleware, mock_quota_enforcer):
        """Test quota enforcement decorator allows request when within limits."""
        # Mock quota check to allow request
        mock_quota_enforcer.check_quota.return_value = (True, {"remaining": {"api_calls": 100}})
        mock_quota_enforcer.increment_usage.return_value = True
        
        # Create mock request
        request = AsyncMock()
        request.state.tenant_id = "test-tenant"
        
        # Create decorated function
        @middleware.enforce_quota("free", "api", "api_calls")
        async def test_endpoint(request):
            return {"status": "success"}
        
        # Test the decorated function
        response = await test_endpoint(request)
        
        assert response["status"] == "success"
        mock_quota_enforcer.check_quota.assert_called_once_with(
            "test-tenant", "free", "api", "api_calls"
        )
        mock_quota_enforcer.increment_usage.assert_called_once_with(
            "test-tenant", "api_calls", 1
        )
    
    async def test_quota_enforcement_decorator_denies_request(self, middleware, mock_quota_enforcer):
        """Test quota enforcement decorator denies request when limits exceeded."""
        # Mock quota check to deny request
        mock_quota_enforcer.check_quota.return_value = (False, {"remaining": {"api_calls": 0}})
        
        # Create mock request
        request = AsyncMock()
        request.state.tenant_id = "test-tenant"
        
        # Create decorated function
        @middleware.enforce_quota("free", "api", "api_calls")
        async def test_endpoint(request):
            return {"status": "success"}
        
        # Test the decorated function
        response = await test_endpoint(request)
        
        assert response.status_code == 429
        mock_quota_enforcer.check_quota.assert_called_once_with(
            "test-tenant", "free", "api", "api_calls"
        )
        mock_quota_enforcer.increment_usage.assert_not_called()
    
    async def test_rate_limit_enforcement_decorator(self, middleware, mock_quota_enforcer):
        """Test rate limit enforcement decorator."""
        # Mock rate limiter to allow request
        mock_quota_enforcer.rate_limiter.is_allowed.return_value = (True, 5, 10)
        
        # Create mock request
        request = AsyncMock()
        request.state.tenant_id = "test-tenant"
        
        # Create decorated function
        @middleware.enforce_rate_limit("free", "api", 10, 5, 60)
        async def test_endpoint(request):
            return {"status": "success"}
        
        # Test the decorated function
        response = await test_endpoint(request)
        
        assert response["status"] == "success"
        mock_quota_enforcer.rate_limiter.is_allowed.assert_called_once_with(
            "test-tenant", "free", "api", 10, 5, 60
        )
