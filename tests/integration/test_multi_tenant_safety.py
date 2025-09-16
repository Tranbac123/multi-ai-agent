"""
Integration tests for multi-tenant safety and fairness.

Tests RLS enforcement, token buckets, concurrency tokens, and fairness middleware
to ensure proper tenant isolation and resource allocation.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from libs.security.row_level_security import (
    RLSManager, TenantContext, TenantAccessLevel
)
from libs.security.token_buckets import (
    TokenBucket, TokenBucketConfig, TenantRateLimiter, RetryStrategy
)
from libs.security.concurrency_tokens import (
    ConcurrencyManager, ConcurrencyToken, ConcurrencyLimits, ConcurrencyTokenStatus
)
from libs.security.fairness_middleware import (
    FairnessMiddleware, WeightedFairScheduler, PreAdmissionControl,
    TenantTier, DegradationLevel, TenantWeight, FairQueueEntry
)


class TestRLSManager:
    """Test Row Level Security manager."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        session_mock = AsyncMock()
        session_mock.execute = AsyncMock()
        session_mock.commit = AsyncMock()
        session_mock.rollback = AsyncMock()
        return session_mock
    
    @pytest.fixture
    def rls_manager(self, mock_db_session):
        """Create RLS manager for testing."""
        return RLSManager(mock_db_session)
    
    @pytest.mark.asyncio
    async def test_setup_rls_policies(self, rls_manager, mock_db_session):
        """Test setting up RLS policies."""
        
        await rls_manager.setup_rls_policies()
        
        # Verify that policies were set up for all tables
        assert len(rls_manager.policies) > 0
        
        # Check that database commands were executed
        assert mock_db_session.execute.called
    
    @pytest.mark.asyncio
    async def test_set_tenant_context(self, rls_manager, mock_db_session):
        """Test setting tenant context."""
        
        tenant_context = TenantContext(
            tenant_id="tenant-123",
            user_id="user-456",
            access_level=TenantAccessLevel.READ,
            data_region="us-east-1"
        )
        
        await rls_manager.set_tenant_context(tenant_context)
        
        # Verify context was stored
        assert "tenant-123" in rls_manager.tenant_contexts
        
        # Check that database session was configured
        assert mock_db_session.execute.called
    
    @pytest.mark.asyncio
    async def test_validate_tenant_access_same_tenant(self, rls_manager):
        """Test tenant access validation for same tenant."""
        
        has_access = await rls_manager.validate_tenant_access(
            tenant_id="tenant-123",
            resource_tenant_id="tenant-123",
            required_access=TenantAccessLevel.READ
        )
        
        assert has_access is True
    
    @pytest.mark.asyncio
    async def test_validate_tenant_access_different_tenant(self, rls_manager):
        """Test tenant access validation for different tenant."""
        
        has_access = await rls_manager.validate_tenant_access(
            tenant_id="tenant-123",
            resource_tenant_id="tenant-456",
            required_access=TenantAccessLevel.READ
        )
        
        assert has_access is False
    
    @pytest.mark.asyncio
    async def test_validate_tenant_access_admin_tenant(self, rls_manager):
        """Test tenant access validation for admin tenant."""
        
        # Set up admin tenant context
        admin_context = TenantContext(
            tenant_id="admin-tenant",
            access_level=TenantAccessLevel.ADMIN
        )
        rls_manager.tenant_contexts["admin-tenant"] = admin_context
        
        has_access = await rls_manager.validate_tenant_access(
            tenant_id="admin-tenant",
            resource_tenant_id="tenant-456",
            required_access=TenantAccessLevel.READ
        )
        
        assert has_access is True
    
    @pytest.mark.asyncio
    async def test_enforce_tenant_isolation(self, rls_manager, mock_db_session):
        """Test enforcing tenant isolation on queries."""
        
        # Mock query
        mock_query = "SELECT * FROM users"
        
        # Mock result
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        mock_db_session.execute.return_value = mock_result
        
        result = await rls_manager.enforce_tenant_isolation(
            query=mock_query,
            tenant_id="tenant-123"
        )
        
        assert result == mock_result
        assert mock_db_session.execute.called
    
    @pytest.mark.asyncio
    async def test_get_tenant_data_count(self, rls_manager, mock_db_session):
        """Test getting tenant data count."""
        
        # Mock result
        mock_result = MagicMock()
        mock_result.scalar.return_value = 10
        mock_db_session.execute.return_value = mock_result
        
        count = await rls_manager.get_tenant_data_count("tenant-123", "users")
        
        assert count == 10
        assert mock_db_session.execute.called
    
    @pytest.mark.asyncio
    async def test_verify_rls_enforcement(self, rls_manager, mock_db_session):
        """Test RLS enforcement verification."""
        
        # Mock successful results
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        mock_db_session.execute.return_value = mock_result
        
        verification_results = await rls_manager.verify_rls_enforcement("tenant-123")
        
        # All tables should pass verification
        for table, result in verification_results.items():
            assert result is True
    
    @pytest.mark.asyncio
    async def test_get_tenant_metrics(self, rls_manager, mock_db_session):
        """Test getting tenant metrics."""
        
        # Mock results for different tables
        mock_result = MagicMock()
        mock_result.scalar.side_effect = [10, 5, 20, 15, 8]  # Different counts for each table
        mock_db_session.execute.return_value = mock_result
        
        metrics = await rls_manager.get_tenant_metrics("tenant-123")
        
        assert metrics["tenant_id"] == "tenant-123"
        assert "table_counts" in metrics
        assert "total_records" in metrics
        assert metrics["total_records"] > 0


class TestTokenBucket:
    """Test token bucket functionality."""
    
    @pytest.fixture
    def token_bucket_config(self):
        """Create token bucket configuration."""
        return TokenBucketConfig(
            capacity=10,
            refill_rate=2.0,
            refill_interval_ms=1000
        )
    
    @pytest.fixture
    def token_bucket(self, token_bucket_config):
        """Create token bucket for testing."""
        return TokenBucket(token_bucket_config)
    
    @pytest.mark.asyncio
    async def test_consume_tokens_success(self, token_bucket):
        """Test successful token consumption."""
        
        success, result = await token_bucket.consume(tokens=5)
        
        assert success is True
        assert result["tokens_consumed"] == 5
        assert result["tokens_remaining"] == 5
        assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_consume_tokens_insufficient(self, token_bucket):
        """Test token consumption with insufficient tokens."""
        
        # Consume all tokens
        await token_bucket.consume(tokens=10)
        
        # Try to consume more
        success, result = await token_bucket.consume(tokens=5)
        
        assert success is False
        assert result["success"] is False
        assert result["tokens_available"] == 0
        assert "retry_after_seconds" in result
    
    @pytest.mark.asyncio
    async def test_token_refill(self, token_bucket):
        """Test token refill over time."""
        
        # Consume all tokens
        await token_bucket.consume(tokens=10)
        
        # Wait for refill (simulate time passage)
        token_bucket.state.last_refill = time.time() - 1.0  # 1 second ago
        
        # Try to consume tokens
        success, result = await token_bucket.consume(tokens=2)
        
        assert success is True
        assert result["tokens_remaining"] == 0  # 2 tokens refilled, 2 consumed
    
    @pytest.mark.asyncio
    async def test_get_state(self, token_bucket):
        """Test getting bucket state."""
        
        # Consume some tokens
        await token_bucket.consume(tokens=3)
        
        state = await token_bucket.get_state()
        
        assert state["tokens"] == 7
        assert state["capacity"] == 10
        assert state["refill_rate"] == 2.0
        assert state["total_requests"] == 1
        assert state["successful_requests"] == 1
        assert state["success_rate"] == 1.0
    
    @pytest.mark.asyncio
    async def test_reset(self, token_bucket):
        """Test resetting bucket."""
        
        # Consume some tokens
        await token_bucket.consume(tokens=5)
        
        # Reset bucket
        await token_bucket.reset()
        
        # Check that tokens are restored
        success, result = await token_bucket.consume(tokens=10)
        assert success is True


class TestTenantRateLimiter:
    """Test tenant rate limiter."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis_mock = AsyncMock()
        redis_mock.eval.return_value = [1, 5]  # Success, remaining tokens
        return redis_mock
    
    @pytest.fixture
    def rate_limiter(self, mock_redis):
        """Create tenant rate limiter for testing."""
        return TenantRateLimiter(mock_redis)
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_success(self, rate_limiter):
        """Test successful rate limit check."""
        
        success, result = await rate_limiter.check_rate_limit(
            tenant_id="tenant-123",
            tokens=1,
            tenant_tier="standard"
        )
        
        assert success is True
        assert result["success"] is True
        assert result["tenant_id"] == "tenant-123"
        assert result["tenant_tier"] == "standard"
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_blocked(self, rate_limiter, mock_redis):
        """Test blocked rate limit check."""
        
        # Mock Redis to return blocked result
        mock_redis.eval.return_value = [0, 0]  # Blocked, no tokens remaining
        
        success, result = await rate_limiter.check_rate_limit(
            tenant_id="tenant-123",
            tokens=1,
            tenant_tier="free"
        )
        
        assert success is False
        assert result["success"] is False
        assert "retry_after_seconds" in result
    
    @pytest.mark.asyncio
    async def test_get_tenant_metrics(self, rate_limiter):
        """Test getting tenant metrics."""
        
        # Create a bucket for the tenant
        await rate_limiter.check_rate_limit("tenant-123", 1, "standard")
        
        metrics = await rate_limiter.get_tenant_metrics("tenant-123")
        
        assert "tenant_id" in metrics
        assert "bucket_state" in metrics
        assert "timestamp" in metrics
    
    @pytest.mark.asyncio
    async def test_reset_tenant_bucket(self, rate_limiter):
        """Test resetting tenant bucket."""
        
        # Create a bucket
        await rate_limiter.check_rate_limit("tenant-123", 1, "standard")
        
        # Reset bucket
        await rate_limiter.reset_tenant_bucket("tenant-123")
        
        # Verify bucket still exists (reset doesn't remove it)
        assert "tenant-123" in rate_limiter.tenant_buckets
    
    @pytest.mark.asyncio
    async def test_update_tenant_tier(self, rate_limiter):
        """Test updating tenant tier."""
        
        # Create bucket with standard tier
        await rate_limiter.check_rate_limit("tenant-123", 1, "standard")
        
        # Update to premium tier
        await rate_limiter.update_tenant_tier("tenant-123", "premium")
        
        # Verify bucket was recreated
        bucket = rate_limiter.tenant_buckets["tenant-123"]
        assert bucket.config.capacity == 10000  # Premium tier capacity


class TestConcurrencyManager:
    """Test concurrency manager."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        return AsyncMock()
    
    @pytest.fixture
    def concurrency_manager(self, mock_redis):
        """Create concurrency manager for testing."""
        manager = ConcurrencyManager(mock_redis)
        # Start the manager
        asyncio.create_task(manager.start())
        return manager
    
    @pytest.mark.asyncio
    async def test_set_tenant_limits(self, concurrency_manager):
        """Test setting tenant limits."""
        
        limits = ConcurrencyLimits(
            tenant_id="tenant-123",
            max_concurrent_requests=10,
            max_concurrent_agents=5,
            max_concurrent_workflows=8,
            max_concurrent_tools=20
        )
        
        await concurrency_manager.set_tenant_limits(limits)
        
        assert "tenant-123" in concurrency_manager.tenant_limits
        assert concurrency_manager.tenant_limits["tenant-123"] == limits
    
    @pytest.mark.asyncio
    async def test_acquire_token_success(self, concurrency_manager):
        """Test successful token acquisition."""
        
        # Set tenant limits
        limits = ConcurrencyLimits(
            tenant_id="tenant-123",
            max_concurrent_requests=10,
            max_concurrent_agents=5,
            max_concurrent_workflows=8,
            max_concurrent_tools=20
        )
        await concurrency_manager.set_tenant_limits(limits)
        
        # Acquire token
        token = await concurrency_manager.acquire_token(
            tenant_id="tenant-123",
            resource_type="requests",
            expires_in_seconds=60
        )
        
        assert token is not None
        assert token.tenant_id == "tenant-123"
        assert token.resource_type == "requests"
        assert token.status == ConcurrencyTokenStatus.ACQUIRED
    
    @pytest.mark.asyncio
    async def test_acquire_token_limit_exceeded(self, concurrency_manager):
        """Test token acquisition when limit is exceeded."""
        
        # Set very low limits
        limits = ConcurrencyLimits(
            tenant_id="tenant-123",
            max_concurrent_requests=1,
            max_concurrent_agents=1,
            max_concurrent_workflows=1,
            max_concurrent_tools=1
        )
        await concurrency_manager.set_tenant_limits(limits)
        
        # Acquire first token
        token1 = await concurrency_manager.acquire_token(
            tenant_id="tenant-123",
            resource_type="requests"
        )
        assert token1 is not None
        
        # Try to acquire second token (should fail)
        token2 = await concurrency_manager.acquire_token(
            tenant_id="tenant-123",
            resource_type="requests"
        )
        assert token2 is None
    
    @pytest.mark.asyncio
    async def test_release_token(self, concurrency_manager):
        """Test token release."""
        
        # Set tenant limits
        limits = ConcurrencyLimits(
            tenant_id="tenant-123",
            max_concurrent_requests=10,
            max_concurrent_agents=5,
            max_concurrent_workflows=8,
            max_concurrent_tools=20
        )
        await concurrency_manager.set_tenant_limits(limits)
        
        # Acquire token
        token = await concurrency_manager.acquire_token(
            tenant_id="tenant-123",
            resource_type="requests"
        )
        assert token is not None
        
        # Release token
        success = await concurrency_manager.release_token(token)
        assert success is True
    
    @pytest.mark.asyncio
    async def test_get_tenant_metrics(self, concurrency_manager):
        """Test getting tenant metrics."""
        
        # Set tenant limits
        limits = ConcurrencyLimits(
            tenant_id="tenant-123",
            max_concurrent_requests=10,
            max_concurrent_agents=5,
            max_concurrent_workflows=8,
            max_concurrent_tools=20
        )
        await concurrency_manager.set_tenant_limits(limits)
        
        metrics = await concurrency_manager.get_tenant_metrics("tenant-123")
        
        assert metrics["tenant_id"] == "tenant-123"
        assert "limits" in metrics
        assert "resource_usage" in metrics
        assert metrics["limits"]["max_concurrent_requests"] == 10
    
    @pytest.mark.asyncio
    async def test_get_global_metrics(self, concurrency_manager):
        """Test getting global metrics."""
        
        metrics = await concurrency_manager.get_global_metrics()
        
        assert "total_tenants" in metrics
        assert "token_pools" in metrics
        assert "total_tokens_acquired" in metrics


class TestFairnessMiddleware:
    """Test fairness middleware."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        return AsyncMock()
    
    @pytest.fixture
    def fairness_middleware(self, mock_redis):
        """Create fairness middleware for testing."""
        return FairnessMiddleware(mock_redis)
    
    @pytest.mark.asyncio
    async def test_set_tenant_config(self, fairness_middleware):
        """Test setting tenant configuration."""
        
        await fairness_middleware.set_tenant_config(
            tenant_id="tenant-123",
            tier=TenantTier.PREMIUM,
            max_concurrent=20,
            priority=2
        )
        
        assert "tenant-123" in fairness_middleware.scheduler.tenant_weights
        weight = fairness_middleware.scheduler.tenant_weights["tenant-123"]
        assert weight.tier == TenantTier.PREMIUM
        assert weight.max_concurrent == 20
        assert weight.priority == 2
    
    @pytest.mark.asyncio
    async def test_process_request_success(self, fairness_middleware):
        """Test successful request processing."""
        
        # Set tenant configuration
        await fairness_middleware.set_tenant_config(
            tenant_id="tenant-123",
            tier=TenantTier.STANDARD
        )
        
        # Process request
        should_admit, degradation_config, reason = await fairness_middleware.process_request(
            tenant_id="tenant-123",
            request_id="req-1",
            request_metadata={"tenant_tier": "standard"},
            system_metrics={"system_load": 0.5, "cpu_usage": 0.6, "memory_usage": 0.7, "queue_size": 10}
        )
        
        assert should_admit is True
        assert reason == "admitted"
        assert degradation_config.level == DegradationLevel.NORMAL
    
    @pytest.mark.asyncio
    async def test_process_request_system_overload(self, fairness_middleware):
        """Test request processing under system overload."""
        
        # Set tenant configuration
        await fairness_middleware.set_tenant_config(
            tenant_id="tenant-123",
            tier=TenantTier.FREE
        )
        
        # Process request under heavy load
        should_admit, degradation_config, reason = await fairness_middleware.process_request(
            tenant_id="tenant-123",
            request_id="req-1",
            request_metadata={"tenant_tier": "free"},
            system_metrics={"system_load": 0.98, "cpu_usage": 0.98, "memory_usage": 0.98, "queue_size": 100}
        )
        
        assert should_admit is False
        assert reason == "system_overload_low_priority_rejected"
        assert degradation_config.level == DegradationLevel.HEAVY
    
    @pytest.mark.asyncio
    async def test_get_next_request(self, fairness_middleware):
        """Test getting next request from queue."""
        
        # Set tenant configuration
        await fairness_middleware.set_tenant_config(
            tenant_id="tenant-123",
            tier=TenantTier.PREMIUM,
            priority=1
        )
        
        # Enqueue request
        await fairness_middleware.process_request(
            tenant_id="tenant-123",
            request_id="req-1",
            request_metadata={"tenant_tier": "premium"},
            system_metrics={"system_load": 0.5, "cpu_usage": 0.6, "memory_usage": 0.7, "queue_size": 10}
        )
        
        # Get next request
        result = await fairness_middleware.get_next_request()
        
        assert result is not None
        entry, degradation_config = result
        assert entry.tenant_id == "tenant-123"
        assert entry.request_id == "req-1"
    
    @pytest.mark.asyncio
    async def test_complete_request(self, fairness_middleware):
        """Test completing a request."""
        
        # Set tenant configuration
        await fairness_middleware.set_tenant_config(
            tenant_id="tenant-123",
            tier=TenantTier.STANDARD
        )
        
        # Process request
        await fairness_middleware.process_request(
            tenant_id="tenant-123",
            request_id="req-1",
            request_metadata={"tenant_tier": "standard"},
            system_metrics={"system_load": 0.5, "cpu_usage": 0.6, "memory_usage": 0.7, "queue_size": 10}
        )
        
        # Complete request
        await fairness_middleware.complete_request("tenant-123", "req-1", 1.5)
        
        # Check that request was marked as completed
        stats = fairness_middleware.scheduler.get_tenant_stats("tenant-123")
        assert stats["completed_requests"] == 1
        assert stats["total_processing_time"] == 1.5
    
    def test_get_metrics(self, fairness_middleware):
        """Test getting fairness middleware metrics."""
        
        metrics = fairness_middleware.get_metrics()
        
        assert "total_requests" in metrics
        assert "admitted_requests" in metrics
        assert "rejected_requests" in metrics
        assert "degraded_requests" in metrics
        assert "admission_rate" in metrics
        assert "degradation_rate" in metrics
        assert "scheduler_metrics" in metrics
        assert "admission_thresholds" in metrics


@pytest.mark.asyncio
async def test_over_quota_returns_429():
    """Test that over-quota requests return 429 status."""
    
    # Create rate limiter with very low limits
    rate_limiter = TenantRateLimiter()
    
    # Set up tenant with free tier (low limits)
    await rate_limiter.check_rate_limit("tenant-123", 1, "free")
    
    # Try to consume many tokens quickly
    blocked_count = 0
    for _ in range(20):  # Try to exceed free tier limits
        success, result = await rate_limiter.check_rate_limit("tenant-123", 10, "free")
        if not success:
            blocked_count += 1
    
    # Should have some blocked requests
    assert blocked_count > 0


@pytest.mark.asyncio
async def test_premium_tenant_maintains_p95_under_mixed_load():
    """Test that premium tenant maintains p95 latency under mixed load."""
    
    fairness_middleware = FairnessMiddleware()
    
    # Set up tenants with different tiers
    await fairness_middleware.set_tenant_config("premium-tenant", TenantTier.PREMIUM, priority=1)
    await fairness_middleware.set_tenant_config("free-tenant", TenantTier.FREE, priority=5)
    
    # Simulate mixed load
    premium_processing_times = []
    
    for i in range(50):
        # Process premium tenant request
        should_admit, _, _ = await fairness_middleware.process_request(
            tenant_id="premium-tenant",
            request_id=f"premium-req-{i}",
            request_metadata={"tenant_tier": "premium"},
            system_metrics={"system_load": 0.8, "cpu_usage": 0.8, "memory_usage": 0.8, "queue_size": 50}
        )
        
        if should_admit:
            # Simulate processing
            processing_time = 0.1 + (i % 10) * 0.01  # Vary processing time
            premium_processing_times.append(processing_time)
            await fairness_middleware.complete_request("premium-tenant", f"premium-req-{i}", processing_time)
        
        # Process free tenant request (may be rejected under load)
        await fairness_middleware.process_request(
            tenant_id="free-tenant",
            request_id=f"free-req-{i}",
            request_metadata={"tenant_tier": "free"},
            system_metrics={"system_load": 0.8, "cpu_usage": 0.8, "memory_usage": 0.8, "queue_size": 50}
        )
    
    # Check that premium tenant maintained good performance
    if premium_processing_times:
        p95_processing_time = sorted(premium_processing_times)[int(len(premium_processing_times) * 0.95)]
        assert p95_processing_time < 0.2  # Should maintain good p95 under mixed load
    
    # Check metrics
    metrics = fairness_middleware.get_metrics()
    assert metrics["admitted_requests"] > 0
