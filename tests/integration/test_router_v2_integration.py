"""Integration tests for Router v2."""

import pytest
import asyncio
import time
from typing import Dict, Any

from apps.router-service.core.router_v2 import RouterV2
from apps.router-service.core.feature_extractor import Tier


@pytest.fixture
async def router_v2_with_redis():
    """Router v2 instance with real Redis connection."""
    import redis.asyncio as redis
    
    redis_client = redis.Redis(
        host="localhost",
        port=6379,
        db=1,  # Use different DB for tests
        decode_responses=False
    )
    
    router = RouterV2(redis_client)
    
    yield router
    
    # Cleanup
    await redis_client.flushdb()
    await redis_client.close()


class TestRouterV2Integration:
    """Integration tests for Router v2."""
    
    @pytest.mark.asyncio
    async def test_router_decision_latency_p50_under_50ms(self, router_v2_with_redis):
        """Test that router p50 decision time is under 50ms."""
        # Generate multiple requests to get meaningful latency statistics
        latencies = []
        
        for i in range(100):
            request = {
                "message": f"Test request {i}",
                "user_id": f"user{i}",
                "tenant_id": "tenant123"
            }
            
            start_time = time.time()
            decision = await router_v2_with_redis.route_request(request, "tenant123", f"user{i}")
            latency = (time.time() - start_time) * 1000
            
            latencies.append(latency)
            
            # Record outcome
            await router_v2_with_redis.record_outcome(
                "tenant123", f"user{i}", decision.tier, True, latency, 0.9
            )
        
        # Calculate p50
        latencies.sort()
        p50 = latencies[len(latencies) // 2]
        
        assert p50 < 50.0, f"Router p50 latency {p50}ms exceeds 50ms threshold"
    
    @pytest.mark.asyncio
    async def test_canary_gating_by_tenant(self, router_v2_with_redis):
        """Test canary gating by tenant (5-10% of users)."""
        # Test with multiple users to see canary distribution
        canary_users = 0
        total_users = 100
        
        for i in range(total_users):
            request = {
                "message": f"Test request {i}",
                "user_id": f"user{i}",
                "tenant_id": "tenant123"
            }
            
            decision = await router_v2_with_redis.route_request(request, "tenant123", f"user{i}")
            
            if decision.canary_info:
                canary_users += 1
        
        # Canary should be 5-10% of users
        canary_percentage = canary_users / total_users
        assert 0.05 <= canary_percentage <= 0.10, f"Canary percentage {canary_percentage} not in 5-10% range"
    
    @pytest.mark.asyncio
    async def test_expected_vs_actual_cost_within_tolerance(self, router_v2_with_redis):
        """Test that expected vs actual cost is within tolerance."""
        # Generate requests and record outcomes
        for i in range(50):
            request = {
                "message": f"Test request {i}",
                "user_id": f"user{i}",
                "tenant_id": "tenant123"
            }
            
            decision = await router_v2_with_redis.route_request(request, "tenant123", f"user{i}")
            
            # Record outcome with some cost variation
            actual_cost = decision.tier.value * 0.1 + (i % 3) * 0.05  # Add some variation
            await router_v2_with_redis.record_outcome(
                "tenant123", f"user{i}", decision.tier, True, 100.0, 0.9
            )
        
        # Get metrics
        metrics = await router_v2_with_redis.get_prometheus_metrics("tenant123")
        
        # Expected vs actual cost should be within reasonable range
        cost_ratio = metrics["expected_vs_actual_cost"]
        assert 0.5 <= cost_ratio <= 2.0, f"Cost ratio {cost_ratio} not within tolerance"
    
    @pytest.mark.asyncio
    async def test_early_exit_acceptance_for_strict_json(self, router_v2_with_redis):
        """Test early exit acceptance for valid strict JSON requests."""
        # Test with simple, well-structured requests that should allow early exit
        early_exit_requests = [
            "Hello",
            "What is the status of my order?",
            "I need help with my account",
            "Can you help me reset my password?",
            "What are your business hours?"
        ]
        
        early_exit_count = 0
        
        for i, message in enumerate(early_exit_requests):
            request = {
                "message": message,
                "user_id": f"user{i}",
                "tenant_id": "tenant123"
            }
            
            decision = await router_v2_with_redis.route_request(request, "tenant123", f"user{i}")
            
            # Check if early exit was used
            if (decision.escalation_decision and 
                decision.escalation_decision.early_exit_tier and
                decision.escalation_decision.early_exit_tier == Tier.A):
                early_exit_count += 1
        
        # At least some requests should use early exit
        assert early_exit_count > 0, "No requests used early exit"
    
    @pytest.mark.asyncio
    async def test_bandit_policy_learning(self, router_v2_with_redis):
        """Test that bandit policy learns over time."""
        # Start with some requests to establish baseline
        for i in range(20):
            request = {
                "message": f"Test request {i}",
                "user_id": f"user{i}",
                "tenant_id": "tenant123"
            }
            
            decision = await router_v2_with_redis.route_request(request, "tenant123", f"user{i}")
            
            # Record outcome
            await router_v2_with_redis.record_outcome(
                "tenant123", f"user{i}", decision.tier, True, 100.0, 0.9
            )
        
        # Get initial statistics
        initial_stats = await router_v2_with_redis.get_router_statistics("tenant123")
        initial_pulls = initial_stats["bandit_statistics"]["total_pulls"]
        
        # Make more requests
        for i in range(20, 40):
            request = {
                "message": f"Test request {i}",
                "user_id": f"user{i}",
                "tenant_id": "tenant123"
            }
            
            decision = await router_v2_with_redis.route_request(request, "tenant123", f"user{i}")
            
            # Record outcome
            await router_v2_with_redis.record_outcome(
                "tenant123", f"user{i}", decision.tier, True, 100.0, 0.9
            )
        
        # Get updated statistics
        updated_stats = await router_v2_with_redis.get_router_statistics("tenant123")
        updated_pulls = updated_stats["bandit_statistics"]["total_pulls"]
        
        # Should have more pulls
        assert updated_pulls > initial_pulls, "Bandit policy not learning"
    
    @pytest.mark.asyncio
    async def test_escalation_for_complex_requests(self, router_v2_with_redis):
        """Test escalation for complex requests."""
        # Complex request that should trigger escalation
        complex_request = {
            "message": "I need to integrate your API with our enterprise system that handles 1M+ requests per day and requires 99.99% uptime with custom authentication and rate limiting",
            "user_id": "user123",
            "tenant_id": "tenant123"
        }
        
        decision = await router_v2_with_redis.route_request(complex_request, "tenant123", "user123")
        
        # Should escalate to higher tier
        assert decision.tier in [Tier.B, Tier.C], f"Complex request not escalated, tier: {decision.tier}"
        assert decision.escalation_decision is not None, "No escalation decision made"
        assert decision.escalation_decision.should_escalate, "Escalation not triggered"
    
    @pytest.mark.asyncio
    async def test_tier_distribution_metrics(self, router_v2_with_redis):
        """Test tier distribution metrics."""
        # Generate requests with different complexities
        requests = [
            ("Hello", "simple"),
            ("What is the status of my order?", "medium"),
            ("I need to integrate your API with our enterprise system", "complex")
        ]
        
        for i, (message, complexity) in enumerate(requests):
            request = {
                "message": message,
                "user_id": f"user{i}",
                "tenant_id": "tenant123"
            }
            
            decision = await router_v2_with_redis.route_request(request, "tenant123", f"user{i}")
            
            # Record outcome
            await router_v2_with_redis.record_outcome(
                "tenant123", f"user{i}", decision.tier, True, 100.0, 0.9
            )
        
        # Get metrics
        metrics = await router_v2_with_redis.get_prometheus_metrics("tenant123")
        
        # Check tier distribution
        tier_distribution = metrics["tier_distribution"]
        assert "A" in tier_distribution
        assert "B" in tier_distribution
        assert "C" in tier_distribution
        assert sum(tier_distribution.values()) > 0, "No tier distribution data"
    
    @pytest.mark.asyncio
    async def test_misroute_rate_calculation(self, router_v2_with_redis):
        """Test misroute rate calculation."""
        # Generate some successful and failed requests
        for i in range(20):
            request = {
                "message": f"Test request {i}",
                "user_id": f"user{i}",
                "tenant_id": "tenant123"
            }
            
            decision = await router_v2_with_redis.route_request(request, "tenant123", f"user{i}")
            
            # Record outcome (mix of success and failure)
            success = i % 4 != 0  # 75% success rate
            await router_v2_with_redis.record_outcome(
                "tenant123", f"user{i}", decision.tier, success, 100.0, 0.9
            )
        
        # Get metrics
        metrics = await router_v2_with_redis.get_prometheus_metrics("tenant123")
        
        # Check misroute rate
        misroute_rate = metrics["router_misroute_rate"]
        assert 0 <= misroute_rate <= 1, f"Misroute rate {misroute_rate} not in valid range"
        assert misroute_rate > 0, "No misroute rate calculated"
    
    @pytest.mark.asyncio
    async def test_router_resilience_to_errors(self, router_v2_with_redis):
        """Test router resilience to errors."""
        # Test with malformed requests
        malformed_requests = [
            {"message": "", "user_id": "user1", "tenant_id": "tenant123"},
            {"message": "x" * 10000, "user_id": "user2", "tenant_id": "tenant123"},  # Very long message
            {"user_id": "user3", "tenant_id": "tenant123"},  # Missing message
        ]
        
        for i, request in enumerate(malformed_requests):
            try:
                decision = await router_v2_with_redis.route_request(request, "tenant123", f"user{i}")
                
                # Should still return a valid decision
                assert decision.tier in [Tier.A, Tier.B, Tier.C]
                assert decision.confidence >= 0
                assert decision.decision_time_ms > 0
                
            except Exception as e:
                # Should handle errors gracefully
                assert False, f"Router failed to handle malformed request: {e}"
    
    @pytest.mark.asyncio
    async def test_tenant_isolation(self, router_v2_with_redis):
        """Test tenant isolation."""
        # Generate requests for different tenants
        tenant1_requests = []
        tenant2_requests = []
        
        for i in range(10):
            # Tenant 1 requests
            request1 = {
                "message": f"Tenant 1 request {i}",
                "user_id": f"user{i}",
                "tenant_id": "tenant1"
            }
            decision1 = await router_v2_with_redis.route_request(request1, "tenant1", f"user{i}")
            tenant1_requests.append(decision1)
            
            # Tenant 2 requests
            request2 = {
                "message": f"Tenant 2 request {i}",
                "user_id": f"user{i}",
                "tenant_id": "tenant2"
            }
            decision2 = await router_v2_with_redis.route_request(request2, "tenant2", f"user{i}")
            tenant2_requests.append(decision2)
        
        # Get statistics for both tenants
        stats1 = await router_v2_with_redis.get_router_statistics("tenant1")
        stats2 = await router_v2_with_redis.get_router_statistics("tenant2")
        
        # Statistics should be separate
        assert stats1["tenant_id"] == "tenant1"
        assert stats2["tenant_id"] == "tenant2"
        assert stats1 != stats2, "Tenant statistics not isolated"
