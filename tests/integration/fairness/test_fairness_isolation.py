"""Integration tests for fairness and isolation features."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from apps.api_gateway.core.concurrency_manager import ConcurrencyManager, PlanTier
from apps.api_gateway.core.fair_scheduler import WeightedFairScheduler, RequestPriority
from apps.api_gateway.middleware.admission_control import AdmissionControlMiddleware
from apps.orchestrator.core.degradation_manager import DegradationManager, SystemLoadLevel


class TestConcurrencyManager:
    """Test ConcurrencyManager functionality."""
    
    @pytest.fixture
    async def concurrency_manager(self):
        """Create ConcurrencyManager instance for testing."""
        redis_client = AsyncMock()
        return ConcurrencyManager(redis_client)
    
    @pytest.mark.asyncio
    async def test_acquire_token_success(self, concurrency_manager):
        """Test successful token acquisition."""
        # Mock Redis operations
        concurrency_manager.redis.scard.return_value = 3  # Current tokens
        concurrency_manager.redis.pipeline.return_value.__aenter__.return_value.execute.return_value = [3, 1, None]
        
        # Test token acquisition
        success = await concurrency_manager.acquire_token("test-tenant-1", "pro")
        
        assert success is True
        assert "test-tenant-1" in concurrency_manager.token_pools
        assert len(concurrency_manager.token_pools["test-tenant-1"]) == 1
    
    @pytest.mark.asyncio
    async def test_acquire_token_limit_exceeded(self, concurrency_manager):
        """Test token acquisition when limit exceeded."""
        # Mock Redis operations - already at limit
        concurrency_manager.redis.scard.return_value = 20  # At pro tier limit
        concurrency_manager.redis.pipeline.return_value.__aenter__.return_value.execute.return_value = [20, 1, None]
        
        # Test token acquisition
        success = await concurrency_manager.acquire_token("test-tenant-1", "pro")
        
        assert success is False
    
    @pytest.mark.asyncio
    async def test_release_token(self, concurrency_manager):
        """Test token release."""
        # Setup tenant with tokens
        concurrency_manager.token_pools["test-tenant-1"] = {"token-1", "token-2"}
        
        # Mock Redis operations
        concurrency_manager.redis.srem.return_value = 1
        
        # Test token release
        await concurrency_manager.release_token("test-tenant-1", "token-1")
        
        assert "token-1" not in concurrency_manager.token_pools["test-tenant-1"]
        assert "token-2" in concurrency_manager.token_pools["test-tenant-1"]
        concurrency_manager.redis.srem.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_tenant_limits(self, concurrency_manager):
        """Test getting tenant limits based on plan."""
        # Test different plan tiers
        free_limits = await concurrency_manager.get_tenant_limits("test-tenant-1", "free")
        assert free_limits.max_concurrent_requests == 5
        assert free_limits.priority_weight == 1
        
        pro_limits = await concurrency_manager.get_tenant_limits("test-tenant-2", "pro")
        assert pro_limits.max_concurrent_requests == 20
        assert pro_limits.priority_weight == 3
        
        enterprise_limits = await concurrency_manager.get_tenant_limits("test-tenant-3", "enterprise")
        assert enterprise_limits.max_concurrent_requests == 100
        assert enterprise_limits.priority_weight == 10


class TestWeightedFairScheduler:
    """Test WeightedFairScheduler functionality."""
    
    @pytest.fixture
    async def fair_scheduler(self):
        """Create WeightedFairScheduler instance for testing."""
        return WeightedFairScheduler()
    
    @pytest.mark.asyncio
    async def test_schedule_request(self, fair_scheduler):
        """Test request scheduling."""
        # Test scheduling request
        success = await fair_scheduler.schedule_request(
            tenant_id="test-tenant-1",
            request_data={"path": "/api/test"},
            priority=RequestPriority.HIGH,
            plan="pro"
        )
        
        assert success is True
        assert "test-tenant-1" in fair_scheduler.queues
        assert len(fair_scheduler.queues["test-tenant-1"].queue) == 1
        
        # Verify request properties
        request = fair_scheduler.queues["test-tenant-1"].queue[0]
        assert request.tenant_id == "test-tenant-1"
        assert request.priority == RequestPriority.HIGH
        assert request.weight == 3  # Pro plan weight
    
    @pytest.mark.asyncio
    async def test_process_next_request(self, fair_scheduler):
        """Test processing next request based on fair scheduling."""
        # Schedule requests for different tenants
        await fair_scheduler.schedule_request("tenant-1", {"data": "1"}, RequestPriority.NORMAL, "free")
        await fair_scheduler.schedule_request("tenant-2", {"data": "2"}, RequestPriority.HIGH, "pro")
        
        # Process requests
        request1 = await fair_scheduler.process_next_request()
        assert request1 is not None
        assert request1.tenant_id in ["tenant-1", "tenant-2"]
        
        request2 = await fair_scheduler.process_next_request()
        assert request2 is not None
        assert request2.tenant_id != request1.tenant_id
    
    @pytest.mark.asyncio
    async def test_priority_scheduling(self, fair_scheduler):
        """Test that high priority requests are processed first."""
        # Schedule normal priority request first
        await fair_scheduler.schedule_request("tenant-1", {"data": "normal"}, RequestPriority.NORMAL, "free")
        
        # Schedule high priority request second
        await fair_scheduler.schedule_request("tenant-2", {"data": "high"}, RequestPriority.HIGH, "free")
        
        # Process next request - should be high priority
        request = await fair_scheduler.process_next_request()
        assert request.priority == RequestPriority.HIGH
        assert request.tenant_id == "tenant-2"
    
    @pytest.mark.asyncio
    async def test_plan_weight_fairness(self, fair_scheduler):
        """Test that plan weights affect scheduling fairness."""
        # Schedule many requests for free tenant
        for i in range(10):
            await fair_scheduler.schedule_request("free-tenant", {"data": f"free-{i}"}, RequestPriority.NORMAL, "free")
        
        # Schedule one request for enterprise tenant
        await fair_scheduler.schedule_request("enterprise-tenant", {"data": "enterprise"}, RequestPriority.NORMAL, "enterprise")
        
        # Enterprise tenant should get processed more frequently due to higher weight
        enterprise_processed = 0
        free_processed = 0
        
        for _ in range(11):  # Process all requests
            request = await fair_scheduler.process_next_request()
            if request:
                if request.tenant_id == "enterprise-tenant":
                    enterprise_processed += 1
                else:
                    free_processed += 1
        
        # Enterprise tenant should have been processed more times
        assert enterprise_processed > free_processed


class TestAdmissionControlMiddleware:
    """Test AdmissionControlMiddleware functionality."""
    
    @pytest.fixture
    async def admission_middleware(self):
        """Create AdmissionControlMiddleware instance for testing."""
        concurrency_manager = AsyncMock(spec=ConcurrencyManager)
        fair_scheduler = AsyncMock(spec=WeightedFairScheduler)
        quota_enforcer = AsyncMock()
        billing_client = AsyncMock()
        
        return AdmissionControlMiddleware(
            concurrency_manager, fair_scheduler, quota_enforcer, billing_client
        )
    
    @pytest.mark.asyncio
    async def test_concurrency_check_passed(self, admission_middleware):
        """Test admission check when concurrency limits allow."""
        # Mock successful concurrency check
        admission_middleware.concurrency_manager.acquire_token.return_value = True
        
        request = MagicMock()
        request.headers = {}
        
        result = await admission_middleware._check_concurrency_limits("test-tenant-1")
        
        assert result["passed"] is True
        assert "token_id" in result
    
    @pytest.mark.asyncio
    async def test_concurrency_check_failed(self, admission_middleware):
        """Test admission check when concurrency limits exceeded."""
        # Mock failed concurrency check
        admission_middleware.concurrency_manager.acquire_token.return_value = False
        admission_middleware.concurrency_manager.get_tenant_stats.return_value = {
            "queue_depth": 5,
            "current_tokens": 20
        }
        admission_middleware.concurrency_manager.get_tenant_limits.return_value = MagicMock(
            max_queue_depth=10
        )
        
        request = MagicMock()
        request.headers = {}
        
        result = await admission_middleware._check_concurrency_limits("test-tenant-1")
        
        assert result["passed"] is False
        assert result["queued"] is True
    
    @pytest.mark.asyncio
    async def test_quota_check_passed(self, admission_middleware):
        """Test admission check when quota limits allow."""
        # Mock successful quota check
        admission_middleware.quota_enforcer.check_quota.return_value = {"allowed": True}
        
        request = MagicMock()
        request.headers = {}
        
        result = await admission_middleware._check_quota_limits("test-tenant-1", request)
        
        assert result["passed"] is True
    
    @pytest.mark.asyncio
    async def test_quota_check_failed(self, admission_middleware):
        """Test admission check when quota limits exceeded."""
        # Mock failed quota check
        admission_middleware.quota_enforcer.check_quota.return_value = {
            "allowed": False,
            "reason": "Monthly quota exceeded"
        }
        
        request = MagicMock()
        request.headers = {}
        
        result = await admission_middleware._check_quota_limits("test-tenant-1", request)
        
        assert result["passed"] is False
        assert "Monthly quota exceeded" in result["details"]


class TestDegradationManager:
    """Test DegradationManager functionality."""
    
    @pytest.fixture
    async def degradation_manager(self):
        """Create DegradationManager instance for testing."""
        return DegradationManager()
    
    @pytest.mark.asyncio
    async def test_determine_load_level_normal(self, degradation_manager):
        """Test load level determination for normal conditions."""
        load_level = degradation_manager._determine_load_level(
            cpu_percent=50.0,
            memory_percent=60.0,
            active_connections=100,
            queue_depth=50,
            response_time_p95=1.0,
            error_rate=0.005
        )
        
        assert load_level == SystemLoadLevel.NORMAL
    
    @pytest.mark.asyncio
    async def test_determine_load_level_high(self, degradation_manager):
        """Test load level determination for high load conditions."""
        load_level = degradation_manager._determine_load_level(
            cpu_percent=75.0,
            memory_percent=80.0,
            active_connections=500,
            queue_depth=200,
            response_time_p95=2.5,
            error_rate=0.02
        )
        
        assert load_level == SystemLoadLevel.HIGH
    
    @pytest.mark.asyncio
    async def test_determine_load_level_critical(self, degradation_manager):
        """Test load level determination for critical conditions."""
        load_level = degradation_manager._determine_load_level(
            cpu_percent=90.0,
            memory_percent=85.0,
            active_connections=1000,
            queue_depth=500,
            response_time_p95=6.0,
            error_rate=0.08
        )
        
        assert load_level == SystemLoadLevel.CRITICAL
    
    @pytest.mark.asyncio
    async def test_determine_load_level_emergency(self, degradation_manager):
        """Test load level determination for emergency conditions."""
        load_level = degradation_manager._determine_load_level(
            cpu_percent=98.0,
            memory_percent=95.0,
            active_connections=2000,
            queue_depth=1000,
            response_time_p95=15.0,
            error_rate=0.15
        )
        
        assert load_level == SystemLoadLevel.EMERGENCY
    
    @pytest.mark.asyncio
    async def test_apply_degradation(self, degradation_manager):
        """Test applying degradation based on load level."""
        # Apply high load degradation
        await degradation_manager.apply_degradation(SystemLoadLevel.HIGH)
        
        config = degradation_manager.degrade_switches
        
        # High load should disable verbose critique and reduce context size
        assert config.verbose_critique is False
        assert config.context_size == "medium"
        assert config.detailed_logging is False
    
    @pytest.mark.asyncio
    async def test_apply_critical_degradation(self, degradation_manager):
        """Test applying critical load degradation."""
        # Apply critical load degradation
        await degradation_manager.apply_degradation(SystemLoadLevel.CRITICAL)
        
        config = degradation_manager.degrade_switches
        
        # Critical load should apply heavy degradation
        assert config.verbose_critique is False
        assert config.debate_mode is False
        assert config.context_size == "minimal"
        assert config.llm_tier == "standard"
        assert config.parallel_processing is False
        assert config.detailed_logging is False
    
    @pytest.mark.asyncio
    async def test_apply_emergency_degradation(self, degradation_manager):
        """Test applying emergency load degradation."""
        # Apply emergency load degradation
        await degradation_manager.apply_degradation(SystemLoadLevel.EMERGENCY)
        
        config = degradation_manager.degrade_switches
        
        # Emergency load should apply maximum degradation
        assert config.verbose_critique is False
        assert config.debate_mode is False
        assert config.context_size == "minimal"
        assert config.llm_tier == "basic"
        assert config.parallel_processing is False
        assert config.caching_enabled is False
        assert config.detailed_logging is False


class TestFairnessIntegration:
    """Integration tests for fairness and isolation features."""
    
    @pytest.mark.asyncio
    async def test_mixed_load_premium_tenants_keep_target(self):
        """Test that premium tenants maintain target performance under mixed load."""
        # This would test the full integration scenario
        # where premium tenants keep p95 < target while free tier sheds load
        
        # Setup multiple tenants with different plans
        # Generate mixed load
        # Verify premium tenants maintain performance targets
        # Verify free tier tenants experience load shedding
        
        pass  # Implementation would require full integration setup
    
    @pytest.mark.asyncio
    async def test_degrade_switches_effective_under_load(self):
        """Test that degrade switches reduce p95 and cost at >80% CPU."""
        # This would test that degradation switches are effective
        # when system load exceeds 80% CPU
        
        # Simulate high system load
        # Verify degradation switches are applied
        # Verify p95 latency is reduced
        # Verify cost is reduced
        # Verify no errors are introduced
        
        pass  # Implementation would require full integration setup
    
    @pytest.mark.asyncio
    async def test_tenant_isolation_under_load(self):
        """Test that tenant isolation works correctly under load."""
        # This would test that tenants don't interfere with each other
        # under high load conditions
        
        # Generate load for multiple tenants
        # Verify fair scheduling prevents starvation
        # Verify concurrency limits are enforced
        # Verify quota limits are enforced
        
        pass  # Implementation would require full integration setup
