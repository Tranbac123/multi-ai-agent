"""Tests for Router v2 hardening with high-concurrency optimizations."""

import pytest
import asyncio
import time
import json
from unittest.mock import AsyncMock, MagicMock
from apps.router-service.core.feature_extractor import (
    FeatureExtractor,
    RouterFeatures,
    Tier,
)
from apps.router-service.core.calibrated_classifier import CalibratedClassifier
from apps.router-service.core.early_exit_escalation import (
    EarlyExitEscalation,
    EscalationReason,
)
from apps.router-service.core.router_v2 import RouterV2


class TestFeatureExtractorHardening:
    """Test feature extractor with high-concurrency optimizations."""

    @pytest.fixture
    def feature_extractor(self):
        """Create feature extractor with mock Redis."""
        redis_mock = AsyncMock()
        return FeatureExtractor(redis_mock)

    @pytest.mark.asyncio
    async def test_feature_extraction_caching(self, feature_extractor):
        """Test that feature extraction uses caching for performance."""
        # Mock Redis responses
        feature_extractor.redis.get.return_value = None  # No cache hit
        feature_extractor.redis.setex.return_value = True

        request = {"message": "Test request", "user_id": "user123"}
        tenant_id = "tenant123"
        user_id = "user123"

        # First call should extract features
        features1 = await feature_extractor.extract_features(
            request, tenant_id, user_id
        )
        assert features1 is not None
        assert features1.token_count > 0

        # Verify caching was attempted
        feature_extractor.redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_feature_extraction_parallel(self, feature_extractor):
        """Test parallel feature extraction for better performance."""
        # Mock Redis responses
        feature_extractor.redis.get.return_value = None
        feature_extractor.redis.setex.return_value = True
        feature_extractor.redis.lrange.return_value = []
        feature_extractor.redis.hgetall.return_value = {}

        requests = [
            ({"message": f"Test request {i}"}, f"tenant{i}", f"user{i}")
            for i in range(10)
        ]

        # Extract features in batch
        features_list = await feature_extractor.batch_extract_features(requests)

        assert len(features_list) == 10
        for features in features_list:
            assert features is not None
            assert features.token_count > 0

    @pytest.mark.asyncio
    async def test_deterministic_feature_extraction(self, feature_extractor):
        """Test that identical requests produce identical features."""
        # Mock Redis responses
        feature_extractor.redis.get.return_value = None
        feature_extractor.redis.setex.return_value = True
        feature_extractor.redis.lrange.return_value = []
        feature_extractor.redis.hgetall.return_value = {}

        request = {"message": "Identical test request", "user_id": "user123"}
        tenant_id = "tenant123"
        user_id = "user123"

        # Extract features twice
        features1 = await feature_extractor.extract_features(
            request, tenant_id, user_id
        )
        features2 = await feature_extractor.extract_features(
            request, tenant_id, user_id
        )

        # Should be identical (deterministic)
        assert features1.token_count == features2.token_count
        assert features1.schema_strictness == features2.schema_strictness
        assert features1.request_complexity == features2.request_complexity


class TestCalibratedClassifierHardening:
    """Test calibrated classifier with deterministic fallback."""

    @pytest.fixture
    def classifier(self):
        """Create classifier with mock Redis."""
        redis_mock = AsyncMock()
        return CalibratedClassifier(redis_mock)

    @pytest.mark.asyncio
    async def test_deterministic_fallback(self, classifier):
        """Test deterministic fallback produces consistent results."""
        features = RouterFeatures(
            token_count=50,
            schema_strictness=0.9,
            domain_flags={},
            novelty_score=0.1,
            historical_failure_rate=0.05,
            user_tier="standard",
            time_of_day=12,
            day_of_week=1,
            request_complexity=0.2,
        )

        # Test deterministic fallback multiple times
        results = []
        for _ in range(5):
            (
                tier,
                confidence,
                should_escalate,
            ) = await classifier._deterministic_fallback(features)
            results.append((tier, confidence, should_escalate))

        # All results should be identical
        first_result = results[0]
        for result in results[1:]:
            assert result == first_result

    @pytest.mark.asyncio
    async def test_deterministic_fallback_tie_breaking(self, classifier):
        """Test deterministic fallback handles tie-breaking consistently."""
        features = RouterFeatures(
            token_count=500,  # Middle ground
            schema_strictness=0.5,
            domain_flags={},
            novelty_score=0.5,
            historical_failure_rate=0.3,
            user_tier="standard",
            time_of_day=12,
            day_of_week=1,
            request_complexity=0.5,
        )

        # Test multiple times to ensure consistent tie-breaking
        results = []
        for _ in range(10):
            (
                tier,
                confidence,
                should_escalate,
            ) = await classifier._deterministic_fallback(features)
            results.append(tier)

        # Should be consistent (all same tier)
        assert all(tier == results[0] for tier in results)

    @pytest.mark.asyncio
    async def test_feature_hash_consistency(self, classifier):
        """Test that feature hashing is consistent."""
        features = RouterFeatures(
            token_count=100,
            schema_strictness=0.8,
            domain_flags={},
            novelty_score=0.3,
            historical_failure_rate=0.1,
            user_tier="premium",
            time_of_day=14,
            day_of_week=2,
            request_complexity=0.4,
        )

        # Generate hash multiple times
        hashes = [classifier._create_feature_hash(features) for _ in range(5)]

        # All hashes should be identical
        assert all(hash_val == hashes[0] for hash_val in hashes)
        assert len(hashes[0]) == 8  # Should be 8 characters


class TestEarlyExitEscalationHardening:
    """Test early exit escalation with strict JSON validation."""

    @pytest.fixture
    def early_exit(self):
        """Create early exit with mock Redis."""
        redis_mock = AsyncMock()
        return EarlyExitEscalation(redis_mock)

    @pytest.mark.asyncio
    async def test_strict_json_validation_early_exit(self, early_exit):
        """Test that early exit requires strict JSON validation."""
        # High schema strictness, low complexity - should pass
        features_good = RouterFeatures(
            token_count=100,
            schema_strictness=0.95,
            domain_flags={},
            novelty_score=0.1,
            historical_failure_rate=0.05,
            user_tier="standard",
            time_of_day=12,
            day_of_week=1,
            request_complexity=0.15,
        )

        # Low schema strictness - should fail
        features_bad = RouterFeatures(
            token_count=100,
            schema_strictness=0.7,  # Too low
            domain_flags={},
            novelty_score=0.1,
            historical_failure_rate=0.05,
            user_tier="standard",
            time_of_day=12,
            day_of_week=1,
            request_complexity=0.15,
        )

        # Mock Redis responses
        early_exit.redis.hgetall.return_value = {}

        # Test good features
        result_good = await early_exit._check_early_exit(features_good, "tenant123")
        assert result_good["can_exit"] is True
        assert result_good["tier"] == Tier.A
        assert result_good["confidence"] >= 0.9

        # Test bad features
        result_bad = await early_exit._check_early_exit(features_bad, "tenant123")
        assert result_bad["can_exit"] is False

    @pytest.mark.asyncio
    async def test_tenant_json_requirements(self, early_exit):
        """Test tenant-specific JSON requirements."""
        # Mock tenant requirements
        early_exit.redis.hgetall.return_value = {
            "min_schema_strictness": "0.95",
            "max_complexity": "0.15",
            "max_token_count": "100",
            "require_validation": "true",
        }

        # Features that meet requirements
        features_good = RouterFeatures(
            token_count=80,
            schema_strictness=0.96,
            domain_flags={},
            novelty_score=0.1,
            historical_failure_rate=0.05,
            user_tier="standard",
            time_of_day=12,
            day_of_week=1,
            request_complexity=0.12,
        )

        # Features that don't meet requirements
        features_bad = RouterFeatures(
            token_count=120,  # Too high
            schema_strictness=0.96,
            domain_flags={},
            novelty_score=0.1,
            historical_failure_rate=0.05,
            user_tier="standard",
            time_of_day=12,
            day_of_week=1,
            request_complexity=0.12,
        )

        # Test good features
        requirements = await early_exit._get_tenant_json_requirements("tenant123")
        assert (
            early_exit._meets_tenant_requirements(features_good, requirements) is True
        )
        assert (
            early_exit._meets_tenant_requirements(features_bad, requirements) is False
        )


class TestRouterV2Integration:
    """Test Router v2 integration with all components."""

    @pytest.fixture
    def router_v2(self):
        """Create Router v2 with mock Redis."""
        redis_mock = AsyncMock()
        return RouterV2(redis_mock)

    @pytest.mark.asyncio
    async def test_router_decision_latency(self, router_v2):
        """Test that router decisions are fast (p50 < 50ms)."""
        # Mock all Redis responses
        router_v2.redis.hgetall.return_value = {}
        router_v2.redis.get.return_value = None
        router_v2.redis.setex.return_value = True
        router_v2.redis.lrange.return_value = []
        router_v2.redis.hincrby.return_value = 1
        router_v2.redis.hincrbyfloat.return_value = 1.0
        router_v2.redis.expire.return_value = True

        request = {"message": "Test request for latency", "user_id": "user123"}
        tenant_id = "tenant123"
        user_id = "user123"

        # Measure decision time
        start_time = time.time()
        decision = await router_v2.route_request(request, tenant_id, user_id)
        decision_time = (time.time() - start_time) * 1000

        assert decision_time < 50  # Should be under 50ms
        assert decision.decision_time_ms < 50
        assert decision.tier is not None
        assert decision.confidence > 0

    @pytest.mark.asyncio
    async def test_router_consistency(self, router_v2):
        """Test that identical requests produce consistent routing decisions."""
        # Mock all Redis responses
        router_v2.redis.hgetall.return_value = {}
        router_v2.redis.get.return_value = None
        router_v2.redis.setex.return_value = True
        router_v2.redis.lrange.return_value = []
        router_v2.redis.hincrby.return_value = 1
        router_v2.redis.hincrbyfloat.return_value = 1.0
        router_v2.redis.expire.return_value = True

        request = {"message": "Consistent test request", "user_id": "user123"}
        tenant_id = "tenant123"
        user_id = "user123"

        # Route the same request multiple times
        decisions = []
        for _ in range(5):
            decision = await router_v2.route_request(request, tenant_id, user_id)
            decisions.append(decision)

        # All decisions should be identical
        first_decision = decisions[0]
        for decision in decisions[1:]:
            assert decision.tier == first_decision.tier
            assert decision.confidence == first_decision.confidence
            assert decision.escalation_decision == first_decision.escalation_decision

    @pytest.mark.asyncio
    async def test_router_metrics_collection(self, router_v2):
        """Test that router collects proper metrics."""
        # Mock all Redis responses
        router_v2.redis.hgetall.return_value = {}
        router_v2.redis.get.return_value = None
        router_v2.redis.setex.return_value = True
        router_v2.redis.lrange.return_value = []
        router_v2.redis.hincrby.return_value = 1
        router_v2.redis.hincrbyfloat.return_value = 1.0
        router_v2.redis.expire.return_value = True

        request = {"message": "Metrics test request", "user_id": "user123"}
        tenant_id = "tenant123"
        user_id = "user123"

        # Route request
        decision = await router_v2.route_request(request, tenant_id, user_id)

        # Verify metrics were recorded
        assert router_v2.redis.hincrby.called
        assert router_v2.redis.hincrbyfloat.called
        assert router_v2.redis.expire.called

        # Test metrics retrieval
        stats = await router_v2.get_router_statistics(tenant_id)
        assert "tenant_id" in stats
        assert "metrics" in stats
        assert "decision_latency_ms" in stats["metrics"]


class TestRouterV2Performance:
    """Test Router v2 performance under high concurrency."""

    @pytest.fixture
    def router_v2(self):
        """Create Router v2 with mock Redis."""
        redis_mock = AsyncMock()
        return RouterV2(redis_mock)

    @pytest.mark.asyncio
    async def test_high_concurrency_routing(self, router_v2):
        """Test router performance under high concurrency."""
        # Mock all Redis responses
        router_v2.redis.hgetall.return_value = {}
        router_v2.redis.get.return_value = None
        router_v2.redis.setex.return_value = True
        router_v2.redis.lrange.return_value = []
        router_v2.redis.hincrby.return_value = 1
        router_v2.redis.hincrbyfloat.return_value = 1.0
        router_v2.redis.expire.return_value = True

        # Create many concurrent requests
        num_requests = 100
        requests = [
            (
                {"message": f"Concurrent request {i}", "user_id": f"user{i}"},
                f"tenant{i % 10}",
                f"user{i}",
            )
            for i in range(num_requests)
        ]

        # Route all requests concurrently
        start_time = time.time()
        tasks = [
            router_v2.route_request(request, tenant_id, user_id)
            for request, tenant_id, user_id in requests
        ]
        decisions = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        # Verify all requests were processed
        assert len(decisions) == num_requests
        for decision in decisions:
            assert decision.tier is not None
            assert decision.confidence > 0
            # Under high concurrency, some decisions may take longer due to Redis calls
            assert (
                decision.decision_time_ms < 300
            )  # More realistic threshold for high concurrency

        # Verify total throughput is reasonable
        throughput = num_requests / total_time
        assert throughput > 50  # Should handle at least 50 requests/second

    @pytest.mark.asyncio
    async def test_router_error_handling(self, router_v2):
        """Test router handles errors gracefully."""
        # Mock Redis to raise exception for all calls
        router_v2.redis.hgetall.side_effect = Exception("Redis error")
        router_v2.redis.get.side_effect = Exception("Redis error")
        router_v2.redis.setex.side_effect = Exception("Redis error")
        router_v2.redis.lrange.side_effect = Exception("Redis error")
        router_v2.redis.hincrby.side_effect = Exception("Redis error")
        router_v2.redis.hincrbyfloat.side_effect = Exception("Redis error")
        router_v2.redis.expire.side_effect = Exception("Redis error")

        request = {"message": "Error test request", "user_id": "user123"}
        tenant_id = "tenant123"
        user_id = "user123"

        # Should not raise exception, should return fallback decision
        decision = await router_v2.route_request(request, tenant_id, user_id)

        # Router should handle errors gracefully and return a decision
        assert decision.tier is not None  # Should have a tier (could be B or C)
        assert decision.confidence > 0  # Should have some confidence
        assert decision.classifier_info is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
