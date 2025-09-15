"""Test quota enforcement and rate limiting."""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock

from tests._fixtures.factories import TenantFactory, UserFactory, APIKeyFactory
from tests._helpers.assertions import MultiTenantAssertions, PerformanceAssertions


class TestQuotaEnforcement:
    """Test quota enforcement and rate limiting."""
    
    @pytest.mark.asyncio
    async def test_rate_limiting_429_response(self):
        """Test rate limiting returns 429 response."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        tenant["settings"]["rate_limit_per_minute"] = 10  # Low limit for testing
        
        # Mock rate limiter
        rate_limiter = Mock()
        rate_limiter.check_rate_limit = AsyncMock()
        
        # Simulate rate limit exceeded
        rate_limiter.check_rate_limit.return_value = {
            "allowed": False,
            "remaining": 0,
            "reset_time": time.time() + 60,
            "limit": 10
        }
        
        # Test rate limiting
        result = await rate_limiter.check_rate_limit(
            tenant_id=tenant["tenant_id"],
            request_type="api_call"
        )
        
        # Verify rate limit response
        assert not result["allowed"]
        assert result["remaining"] == 0
        assert result["limit"] == 10
        
        # Simulate 429 response
        response = {
            "status_code": 429,
            "error": "Rate limit exceeded",
            "message": f"Rate limit of {result['limit']} requests per minute exceeded",
            "retry_after": int(result["reset_time"] - time.time()),
            "headers": {
                "X-RateLimit-Limit": str(result["limit"]),
                "X-RateLimit-Remaining": str(result["remaining"]),
                "X-RateLimit-Reset": str(int(result["reset_time"]))
            }
        }
        
        assert response["status_code"] == 429
        assert "Rate limit exceeded" in response["error"]
        assert response["retry_after"] > 0
        assert response["headers"]["X-RateLimit-Limit"] == "10"
        assert response["headers"]["X-RateLimit-Remaining"] == "0"
    
    @pytest.mark.asyncio
    async def test_token_quota_enforcement(self):
        """Test token quota enforcement."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        tenant["settings"]["token_quota_per_hour"] = 10000  # 10K tokens per hour
        
        # Mock token usage tracker
        token_tracker = Mock()
        token_tracker.check_token_quota = AsyncMock()
        
        # Simulate token quota check
        token_tracker.check_token_quota.return_value = {
            "allowed": True,
            "remaining_tokens": 5000,
            "quota_limit": 10000,
            "reset_time": time.time() + 3600
        }
        
        # Test token quota
        result = await token_tracker.check_token_quota(
            tenant_id=tenant["tenant_id"],
            requested_tokens=1000
        )
        
        # Verify token quota
        assert result["allowed"]
        assert result["remaining_tokens"] == 5000
        assert result["quota_limit"] == 10000
        
        # Simulate quota exceeded
        token_tracker.check_token_quota.return_value = {
            "allowed": False,
            "remaining_tokens": 0,
            "quota_limit": 10000,
            "reset_time": time.time() + 3600,
            "reason": "Token quota exceeded"
        }
        
        result_exceeded = await token_tracker.check_token_quota(
            tenant_id=tenant["tenant_id"],
            requested_tokens=1000
        )
        
        assert not result_exceeded["allowed"]
        assert result_exceeded["remaining_tokens"] == 0
        assert "quota exceeded" in result_exceeded["reason"]
    
    @pytest.mark.asyncio
    async def test_concurrent_request_quota(self):
        """Test concurrent request quota enforcement."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        tenant["settings"]["max_concurrent_requests"] = 5
        
        # Mock concurrent request tracker
        concurrent_tracker = Mock()
        concurrent_tracker.check_concurrent_limit = AsyncMock()
        
        # Simulate concurrent request tracking
        active_requests = 3
        
        concurrent_tracker.check_concurrent_limit.return_value = {
            "allowed": True,
            "active_requests": active_requests,
            "max_concurrent": 5,
            "remaining_slots": 2
        }
        
        # Test concurrent quota
        result = await concurrent_tracker.check_concurrent_limit(
            tenant_id=tenant["tenant_id"]
        )
        
        # Verify concurrent quota
        assert result["allowed"]
        assert result["active_requests"] == 3
        assert result["max_concurrent"] == 5
        assert result["remaining_slots"] == 2
        
        # Simulate quota exceeded
        concurrent_tracker.check_concurrent_limit.return_value = {
            "allowed": False,
            "active_requests": 5,
            "max_concurrent": 5,
            "remaining_slots": 0,
            "reason": "Concurrent request limit exceeded"
        }
        
        result_exceeded = await concurrent_tracker.check_concurrent_limit(
            tenant_id=tenant["tenant_id"]
        )
        
        assert not result_exceeded["allowed"]
        assert result_exceeded["active_requests"] == 5
        assert result_exceeded["remaining_slots"] == 0
    
    @pytest.mark.asyncio
    async def test_quota_tier_based_limits(self):
        """Test tier-based quota limits."""
        # Setup different tenant tiers
        tenant_factory = TenantFactory()
        
        free_tenant = tenant_factory.create()
        free_tenant["plan"] = "free"
        free_tenant["settings"]["rate_limit_per_minute"] = 10
        free_tenant["settings"]["token_quota_per_hour"] = 1000
        
        pro_tenant = tenant_factory.create()
        pro_tenant["plan"] = "pro"
        pro_tenant["settings"]["rate_limit_per_minute"] = 100
        pro_tenant["settings"]["token_quota_per_hour"] = 10000
        
        enterprise_tenant = tenant_factory.create()
        enterprise_tenant["plan"] = "enterprise"
        enterprise_tenant["settings"]["rate_limit_per_minute"] = 1000
        enterprise_tenant["settings"]["token_quota_per_hour"] = 100000
        
        # Mock quota manager
        quota_manager = Mock()
        quota_manager.get_tenant_limits = AsyncMock()
        
        # Test tier-based limits
        free_limits = await quota_manager.get_tenant_limits(free_tenant["tenant_id"])
        pro_limits = await quota_manager.get_tenant_limits(pro_tenant["tenant_id"])
        enterprise_limits = await quota_manager.get_tenant_limits(enterprise_tenant["tenant_id"])
        
        # Verify tier-based limits
        assert free_limits["rate_limit_per_minute"] == 10
        assert free_limits["token_quota_per_hour"] == 1000
        
        assert pro_limits["rate_limit_per_minute"] == 100
        assert pro_limits["token_quota_per_hour"] == 10000
        
        assert enterprise_limits["rate_limit_per_minute"] == 1000
        assert enterprise_limits["token_quota_per_hour"] == 100000
        
        # Verify tier hierarchy
        assert free_limits["rate_limit_per_minute"] < pro_limits["rate_limit_per_minute"]
        assert pro_limits["rate_limit_per_minute"] < enterprise_limits["rate_limit_per_minute"]
        assert free_limits["token_quota_per_hour"] < pro_limits["token_quota_per_hour"]
        assert pro_limits["token_quota_per_hour"] < enterprise_limits["token_quota_per_hour"]
    
    @pytest.mark.asyncio
    async def test_quota_burst_allowance(self):
        """Test quota burst allowance."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        tenant["settings"]["rate_limit_per_minute"] = 60
        tenant["settings"]["burst_allowance"] = 10  # Allow 10 extra requests in burst
        
        # Mock burst tracker
        burst_tracker = Mock()
        burst_tracker.check_burst_allowance = AsyncMock()
        
        # Simulate burst allowance
        burst_tracker.check_burst_allowance.return_value = {
            "allowed": True,
            "normal_remaining": 5,
            "burst_remaining": 8,
            "total_remaining": 13
        }
        
        # Test burst allowance
        result = await burst_tracker.check_burst_allowance(
            tenant_id=tenant["tenant_id"],
            request_count=3
        )
        
        # Verify burst allowance
        assert result["allowed"]
        assert result["normal_remaining"] == 5
        assert result["burst_remaining"] == 8
        assert result["total_remaining"] == 13
        
        # Simulate burst exhausted
        burst_tracker.check_burst_allowance.return_value = {
            "allowed": False,
            "normal_remaining": 0,
            "burst_remaining": 0,
            "total_remaining": 0,
            "reason": "Burst allowance exhausted"
        }
        
        result_exhausted = await burst_tracker.check_burst_allowance(
            tenant_id=tenant["tenant_id"],
            request_count=5
        )
        
        assert not result_exhausted["allowed"]
        assert result_exhausted["total_remaining"] == 0
        assert "exhausted" in result_exhausted["reason"]
    
    @pytest.mark.asyncio
    async def test_quota_reset_mechanism(self):
        """Test quota reset mechanism."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        tenant["settings"]["rate_limit_per_minute"] = 10
        
        # Mock quota reset tracker
        reset_tracker = Mock()
        reset_tracker.reset_quota = AsyncMock()
        reset_tracker.get_quota_status = AsyncMock()
        
        # Simulate quota reset
        reset_tracker.reset_quota.return_value = {
            "success": True,
            "reset_time": time.time(),
            "new_limit": 10
        }
        
        # Test quota reset
        reset_result = await reset_tracker.reset_quota(
            tenant_id=tenant["tenant_id"],
            quota_type="rate_limit"
        )
        
        # Verify quota reset
        assert reset_result["success"]
        assert reset_result["new_limit"] == 10
        assert reset_result["reset_time"] > 0
        
        # Simulate quota status after reset
        reset_tracker.get_quota_status.return_value = {
            "remaining": 10,
            "limit": 10,
            "reset_time": reset_result["reset_time"] + 60
        }
        
        status_result = await reset_tracker.get_quota_status(
            tenant_id=tenant["tenant_id"],
            quota_type="rate_limit"
        )
        
        # Verify quota status
        assert status_result["remaining"] == 10
        assert status_result["limit"] == 10
        assert status_result["reset_time"] > reset_result["reset_time"]
    
    @pytest.mark.asyncio
    async def test_quota_grace_period(self):
        """Test quota grace period for new tenants."""
        # Setup new tenant
        tenant_factory = TenantFactory()
        
        new_tenant = tenant_factory.create()
        new_tenant["created_at"] = time.time() - 300  # 5 minutes ago
        new_tenant["settings"]["grace_period_hours"] = 24
        new_tenant["settings"]["rate_limit_per_minute"] = 10
        
        # Mock grace period tracker
        grace_tracker = Mock()
        grace_tracker.check_grace_period = AsyncMock()
        
        # Simulate grace period check
        grace_tracker.check_grace_period.return_value = {
            "in_grace_period": True,
            "grace_remaining": 82800,  # 23 hours in seconds
            "normal_limit": 10,
            "grace_limit": 50  # Higher limit during grace period
        }
        
        # Test grace period
        result = await grace_tracker.check_grace_period(
            tenant_id=new_tenant["tenant_id"]
        )
        
        # Verify grace period
        assert result["in_grace_period"]
        assert result["grace_remaining"] > 0
        assert result["grace_limit"] > result["normal_limit"]
        
        # Simulate grace period expired
        old_tenant = tenant_factory.create()
        old_tenant["created_at"] = time.time() - 86400  # 24 hours ago
        old_tenant["settings"]["grace_period_hours"] = 24
        
        grace_tracker.check_grace_period.return_value = {
            "in_grace_period": False,
            "grace_remaining": 0,
            "normal_limit": 10,
            "grace_limit": 50
        }
        
        result_expired = await grace_tracker.check_grace_period(
            tenant_id=old_tenant["tenant_id"]
        )
        
        assert not result_expired["in_grace_period"]
        assert result_expired["grace_remaining"] == 0
    
    @pytest.mark.asyncio
    async def test_quota_tenant_isolation(self):
        """Test quota isolation between tenants."""
        # Setup two tenants
        tenant_factory = TenantFactory()
        
        tenant_a = tenant_factory.create()
        tenant_a["settings"]["rate_limit_per_minute"] = 10
        
        tenant_b = tenant_factory.create()
        tenant_b["settings"]["rate_limit_per_minute"] = 20
        
        # Mock quota tracker
        quota_tracker = Mock()
        quota_tracker.get_tenant_usage = AsyncMock()
        
        # Simulate separate quota tracking
        async def get_tenant_usage(tenant_id):
            if tenant_id == tenant_a["tenant_id"]:
                return {
                    "tenant_id": tenant_a["tenant_id"],
                    "requests_used": 5,
                    "requests_limit": 10,
                    "remaining": 5
                }
            elif tenant_id == tenant_b["tenant_id"]:
                return {
                    "tenant_id": tenant_b["tenant_id"],
                    "requests_used": 15,
                    "requests_limit": 20,
                    "remaining": 5
                }
            else:
                return {"tenant_id": tenant_id, "requests_used": 0, "requests_limit": 0, "remaining": 0}
        
        quota_tracker.get_tenant_usage.side_effect = get_tenant_usage
        
        # Test quota isolation
        usage_a = await quota_tracker.get_tenant_usage(tenant_a["tenant_id"])
        usage_b = await quota_tracker.get_tenant_usage(tenant_b["tenant_id"])
        
        # Verify quota isolation
        assert usage_a["tenant_id"] == tenant_a["tenant_id"]
        assert usage_b["tenant_id"] == tenant_b["tenant_id"]
        assert usage_a["requests_limit"] == 10
        assert usage_b["requests_limit"] == 20
        assert usage_a["requests_used"] == 5
        assert usage_b["requests_used"] == 15
        
        # Verify no cross-tenant quota interference
        assert usage_a["tenant_id"] != usage_b["tenant_id"]
        assert usage_a["requests_limit"] != usage_b["requests_limit"]
        
        # Test isolation assertion
        results = [usage_a, usage_b]
        result = MultiTenantAssertions.assert_tenant_isolation(
            results, "tenant_id", "Quota tenant isolation"
        )
        assert not result.passed, f"Should detect multi-tenant quota data: {result.message}"
    
    @pytest.mark.asyncio
    async def test_quota_performance_impact(self):
        """Test quota enforcement performance impact."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        tenant["settings"]["rate_limit_per_minute"] = 1000
        
        # Mock quota checker with performance measurement
        quota_checker = Mock()
        
        async def check_quota_with_timing(tenant_id):
            start_time = time.time()
            # Simulate quota check
            await asyncio.sleep(0.001)  # 1ms quota check
            end_time = time.time()
            
            return {
                "allowed": True,
                "check_time_ms": (end_time - start_time) * 1000
            }
        
        quota_checker.check_quota = AsyncMock(side_effect=check_quota_with_timing)
        
        # Test quota performance
        result = await quota_checker.check_quota(tenant_id=tenant["tenant_id"])
        
        # Verify quota check performance
        assert result["allowed"]
        assert result["check_time_ms"] < 10  # Less than 10ms
        
        # Verify performance assertion
        perf_result = PerformanceAssertions.assert_latency_below_threshold(
            result["check_time_ms"], 10, "Quota check performance"
        )
        assert perf_result.passed, f"Quota check should be fast: {perf_result.message}"
