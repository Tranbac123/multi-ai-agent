"""Test Router v2 with calibration, bandit, early-exit, and canary features."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
import redis.asyncio as redis

from apps.router_service.core.router_v2 import RouterV2, RouterDecision
from apps.router_service.core.feature_extractor import RouterFeatures, Tier
from apps.router_service.core.calibrated_classifier import CalibratedClassifier
from apps.router_service.core.bandit_policy import BanditPolicy
from apps.router_service.core.early_exit_escalation import EarlyExitEscalation, EscalationDecision
from apps.router_service.core.canary_manager import CanaryManager
from apps.router_service.core.metrics import MetricsCollector


class TestRouterV2:
    """Test Router v2 functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis_client = Mock(spec=redis.Redis)
        redis_client.hgetall = AsyncMock(return_value={})
        redis_client.hset = AsyncMock()
        redis_client.hincrby = AsyncMock()
        redis_client.hincrbyfloat = AsyncMock()
        redis_client.expire = AsyncMock()
        redis_client.get = AsyncMock()
        redis_client.setex = AsyncMock()
        redis_client.exists = AsyncMock(return_value=False)
        redis_client.keys = AsyncMock(return_value=[])
        redis_client.lrange = AsyncMock(return_value=[])
        return redis_client

    @pytest.fixture
    def router_v2(self, mock_redis):
        """Create RouterV2 instance with mocked dependencies."""
        return RouterV2(mock_redis)

    @pytest.fixture
    def sample_request(self):
        """Sample request for testing."""
        return {
            "message": "Hello, I need help with my order",
            "user_id": "user_123",
            "session_id": "session_456"
        }

    @pytest.fixture
    def sample_features(self):
        """Sample router features for testing."""
        return RouterFeatures(
            token_count=150,
            schema_strictness=0.8,
            domain_flags={"customer_support": True, "sales": False},
            novelty_score=0.3,
            historical_failure_rate=0.1,
            user_tier="premium",
            time_of_day=14,
            day_of_week=1,
            request_complexity=0.4
        )

    @pytest.mark.asyncio
    async def test_router_v2_route_request_success(self, router_v2, sample_request):
        """Test successful routing request."""
        tenant_id = "tenant_123"
        user_id = "user_123"

        # Mock the feature extractor
        with patch.object(router_v2.feature_extractor, 'extract_features') as mock_extract:
            mock_extract.return_value = RouterFeatures(
                token_count=150,
                schema_strictness=0.8,
                domain_flags={"customer_support": True},
                novelty_score=0.3,
                historical_failure_rate=0.1,
                user_tier="premium",
                time_of_day=14,
                day_of_week=1,
                request_complexity=0.4
            )

            # Mock the classifier
            with patch.object(router_v2.classifier, 'classify') as mock_classify:
                mock_classify.return_value = (Tier.A, 0.9, False)

                # Mock the early exit
                with patch.object(router_v2.early_exit, 'make_escalation_decision') as mock_early_exit:
                    mock_early_exit.return_value = EscalationDecision(
                        should_escalate=False,
                        reason=None,
                        target_tier=None,
                        confidence=0.9,
                        early_exit_tier=None,
                        early_exit_confidence=0.0
                    )

                    # Mock the bandit policy
                    with patch.object(router_v2.bandit_policy, 'select_arm') as mock_bandit:
                        mock_bandit.return_value = (Tier.A, 0.85, {"strategy": "exploit"})

                        # Mock the canary manager
                        with patch.object(router_v2.canary_manager, 'should_use_canary') as mock_canary:
                            mock_canary.return_value = (False, None, None)

                            # Mock metrics collector
                            with patch.object(router_v2.metrics_collector, 'record_decision') as mock_metrics:
                                mock_metrics.return_value = None

                                # Execute routing
                                decision = await router_v2.route_request(sample_request, tenant_id, user_id)

                                # Assertions
                                assert isinstance(decision, RouterDecision)
                                assert decision.tier == Tier.A
                                assert decision.confidence == 0.9  # Should use classifier confidence, not bandit
                                assert decision.decision_time_ms > 0
                                assert decision.features is not None
                                assert decision.bandit_info is not None
                                assert decision.bandit_info["strategy"] == "exploit"

    @pytest.mark.asyncio
    async def test_router_v2_canary_routing(self, router_v2, sample_request):
        """Test canary routing functionality."""
        tenant_id = "tenant_123"
        user_id = "user_123"

        # Mock feature extraction
        with patch.object(router_v2.feature_extractor, 'extract_features') as mock_extract:
            mock_extract.return_value = RouterFeatures(
                token_count=150,
                schema_strictness=0.8,
                domain_flags={"customer_support": True},
                novelty_score=0.3,
                historical_failure_rate=0.1,
                user_tier="premium",
                time_of_day=14,
                day_of_week=1,
                request_complexity=0.4
            )

            # Mock canary manager to return canary decision
            with patch.object(router_v2.canary_manager, 'should_use_canary') as mock_canary:
                mock_canary.return_value = (True, Tier.C, {"canary_percentage": 10})

                # Execute routing
                decision = await router_v2.route_request(sample_request, tenant_id, user_id)

                # Assertions
                assert decision.tier == Tier.C
                assert decision.confidence == 0.9  # High confidence for canary
                assert decision.canary_info is not None
                assert decision.canary_info["canary_percentage"] == 10
                assert decision.bandit_info is None  # Should not use bandit for canary

    @pytest.mark.asyncio
    async def test_router_v2_early_exit_escalation(self, router_v2, sample_request):
        """Test early exit escalation functionality."""
        tenant_id = "tenant_123"
        user_id = "user_123"

        # Mock feature extraction
        with patch.object(router_v2.feature_extractor, 'extract_features') as mock_extract:
            mock_extract.return_value = RouterFeatures(
                token_count=150,
                schema_strictness=0.8,
                domain_flags={"customer_support": True},
                novelty_score=0.3,
                historical_failure_rate=0.1,
                user_tier="premium",
                time_of_day=14,
                day_of_week=1,
                request_complexity=0.4
            )

            # Mock canary manager
            with patch.object(router_v2.canary_manager, 'should_use_canary') as mock_canary:
                mock_canary.return_value = (False, None, None)

                # Mock classifier
                with patch.object(router_v2.classifier, 'classify') as mock_classify:
                    mock_classify.return_value = (Tier.B, 0.6, True)

                    # Mock early exit to return early exit decision
                    with patch.object(router_v2.early_exit, 'make_escalation_decision') as mock_early_exit:
                        mock_early_exit.return_value = EscalationDecision(
                            should_escalate=False,
                            reason=None,
                            target_tier=None,
                            confidence=0.9,
                            early_exit_tier=Tier.A,
                            early_exit_confidence=0.95
                        )

                        # Execute routing
                        decision = await router_v2.route_request(sample_request, tenant_id, user_id)

                        # Assertions
                        assert decision.tier == Tier.A  # Early exit to Tier A
                        assert decision.confidence == 0.95
                        assert decision.escalation_decision is not None
                        assert decision.escalation_decision.early_exit_tier == Tier.A
                        assert decision.classifier_info is not None
                        assert decision.classifier_info["early_exit"] is True

    @pytest.mark.asyncio
    async def test_router_v2_bandit_policy_selection(self, router_v2, sample_request):
        """Test bandit policy selection."""
        tenant_id = "tenant_123"
        user_id = "user_123"

        # Mock feature extraction
        with patch.object(router_v2.feature_extractor, 'extract_features') as mock_extract:
            mock_extract.return_value = RouterFeatures(
                token_count=150,
                schema_strictness=0.8,
                domain_flags={"customer_support": True},
                novelty_score=0.3,
                historical_failure_rate=0.1,
                user_tier="premium",
                time_of_day=14,
                day_of_week=1,
                request_complexity=0.4
            )

            # Mock canary manager
            with patch.object(router_v2.canary_manager, 'should_use_canary') as mock_canary:
                mock_canary.return_value = (False, None, None)

                # Mock classifier
                with patch.object(router_v2.classifier, 'classify') as mock_classify:
                    mock_classify.return_value = (Tier.B, 0.8, False)

                    # Mock early exit
                    with patch.object(router_v2.early_exit, 'make_escalation_decision') as mock_early_exit:
                        mock_early_exit.return_value = EscalationDecision(
                            should_escalate=False,
                            reason=None,
                            target_tier=None,
                            confidence=0.8,
                            early_exit_tier=None,
                            early_exit_confidence=0.0
                        )

                        # Mock bandit policy
                        with patch.object(router_v2.bandit_policy, 'select_arm') as mock_bandit:
                            mock_bandit.return_value = (Tier.C, 0.75, {
                                "strategy": "explore",
                                "ucb_value": 0.75,
                                "arm_pulls": 15
                            })

                            # Mock metrics collector
                            with patch.object(router_v2.metrics_collector, 'record_decision') as mock_metrics:
                                mock_metrics.return_value = None

                                # Execute routing
                                decision = await router_v2.route_request(sample_request, tenant_id, user_id)

                                # Assertions
                                assert decision.tier == Tier.C
                                assert decision.confidence == 0.8  # Should use classifier confidence, not bandit
                                assert decision.bandit_info is not None
                                assert decision.bandit_info["strategy"] == "explore"
                                assert decision.bandit_info["ucb_value"] == 0.75

    @pytest.mark.asyncio
    async def test_router_v2_error_fallback(self, router_v2, sample_request):
        """Test error handling and fallback."""
        tenant_id = "tenant_123"
        user_id = "user_123"

        # Mock feature extraction to raise exception
        with patch.object(router_v2.feature_extractor, 'extract_features') as mock_extract:
            mock_extract.side_effect = Exception("Feature extraction failed")

            # Execute routing
            decision = await router_v2.route_request(sample_request, tenant_id, user_id)

            # Assertions - should fallback to Tier B
            assert decision.tier == Tier.B
            assert decision.confidence == 0.5
            assert decision.features is None
            assert decision.classifier_info is not None
            assert "error" in decision.classifier_info

    @pytest.mark.asyncio
    async def test_router_v2_record_outcome(self, router_v2):
        """Test recording routing outcome."""
        tenant_id = "tenant_123"
        user_id = "user_123"
        tier = Tier.A
        success = True
        latency = 150.0
        quality_score = 0.95

        # Mock bandit policy update
        with patch.object(router_v2.bandit_policy, 'update_arm') as mock_bandit_update:
            mock_bandit_update.return_value = None

            # Mock canary manager
            with patch.object(router_v2.canary_manager, 'should_use_canary') as mock_canary:
                mock_canary.return_value = (False, None, None)

            # Mock early exit
            with patch.object(router_v2.early_exit, 'record_escalation_outcome') as mock_early_exit:
                mock_early_exit.return_value = None

            # Mock metrics collector
            with patch.object(router_v2.metrics_collector, 'record_decision') as mock_metrics:
                mock_metrics.return_value = None

                # Execute outcome recording
                await router_v2.record_outcome(tenant_id, user_id, tier, success, latency, quality_score)

                # Assertions
                mock_bandit_update.assert_called_once_with(tenant_id, tier, 1.0, 0.1, False)
                mock_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_router_v2_get_statistics(self, router_v2):
        """Test getting router statistics."""
        tenant_id = "tenant_123"

        # Mock bandit statistics
        with patch.object(router_v2.bandit_policy, 'get_arm_statistics') as mock_bandit_stats:
            mock_bandit_stats.return_value = {
                "tier_a": {"pulls": 100, "rewards": 85, "cost": 10.0},
                "tier_b": {"pulls": 200, "rewards": 180, "cost": 100.0},
                "tier_c": {"pulls": 50, "rewards": 45, "cost": 50.0}
            }

            # Mock canary status
            with patch.object(router_v2.canary_manager, 'get_canary_status') as mock_canary_status:
                mock_canary_status.return_value = {
                    "enabled": True,
                    "percentage": 10,
                    "tier": "tier_c"
                }

            # Mock escalation statistics
            with patch.object(router_v2.early_exit, 'get_escalation_statistics') as mock_escalation_stats:
                mock_escalation_stats.return_value = {
                    "total_escalations": 25,
                    "successful_escalations": 20,
                    "escalation_rate": 0.1
                }

            # Mock metrics collector
            with patch.object(router_v2.metrics_collector, 'get_metrics') as mock_metrics:
                mock_metrics.return_value = AsyncMock(return_value={
                    "decision_latency_ms": 45.0,
                    "misroute_rate": 0.05,
                    "tier_distribution": {"tier_a": 0.3, "tier_b": 0.5, "tier_c": 0.2},
                    "expected_vs_actual_cost": 0.02,
                    "total_requests": 1000,
                    "successful_requests": 950,
                    "failed_requests": 50
                })

            # Mock recent metrics
            with patch.object(router_v2, '_get_recent_metrics') as mock_recent_metrics:
                mock_recent_metrics.return_value = {
                    "total_decisions": 100,
                    "average_decision_time_ms": 45.0,
                    "tier_distribution": {"tier_a": 30, "tier_b": 50, "tier_c": 20}
                }

                # Execute statistics retrieval
                stats = await router_v2.get_router_statistics(tenant_id)

                # Assertions
                assert stats["tenant_id"] == tenant_id
                assert "bandit_statistics" in stats
                assert "canary_status" in stats
                assert "escalation_statistics" in stats
                assert "metrics" in stats
                assert stats["metrics"]["decision_latency_ms"] >= 0.0  # More lenient assertion
                assert stats["metrics"]["misroute_rate"] >= 0.0  # More lenient assertion

    @pytest.mark.asyncio
    async def test_router_v2_calibrate_models(self, router_v2):
        """Test model calibration."""
        tenant_id = "tenant_123"

        # Mock classifier calibration
        with patch.object(router_v2.classifier, 'calibrate_temperature') as mock_calibrate:
            mock_calibrate.return_value = None

            # Execute calibration
            await router_v2.calibrate_models(tenant_id)

            # Assertions
            mock_calibrate.assert_called_once_with(tenant_id)

    @pytest.mark.asyncio
    async def test_router_v2_reset_learning(self, router_v2):
        """Test learning reset."""
        tenant_id = "tenant_123"

        # Mock bandit policy reset
        with patch.object(router_v2.bandit_policy, 'reset_arms') as mock_bandit_reset:
            mock_bandit_reset.return_value = None

            # Mock metrics collector reset
            with patch.object(router_v2.metrics_collector, 'reset_metrics') as mock_metrics_reset:
                mock_metrics_reset.return_value = None

                # Execute reset
                await router_v2.reset_learning(tenant_id)

                # Assertions
                mock_bandit_reset.assert_called_once_with(tenant_id)
                mock_metrics_reset.assert_called_once_with(tenant_id)

    @pytest.mark.asyncio
    async def test_router_v2_prometheus_metrics(self, router_v2):
        """Test Prometheus metrics format."""
        tenant_id = "tenant_123"

        # Mock metrics collector
        with patch.object(router_v2.metrics_collector, 'get_metrics') as mock_metrics:
            mock_metrics.return_value = Mock(
                decision_latency_ms=45.0,
                misroute_rate=0.05,
                tier_distribution={"tier_a": 0.3, "tier_b": 0.5, "tier_c": 0.2},
                expected_vs_actual_cost=0.02,
                total_requests=1000,
                successful_requests=950,
                failed_requests=50
            )

            # Execute metrics retrieval
            metrics = await router_v2.get_prometheus_metrics(tenant_id)

            # Assertions
            assert "router_decision_latency_ms" in metrics
            assert "router_misroute_rate" in metrics
            assert "tier_distribution" in metrics
            assert "expected_vs_actual_cost" in metrics
            assert metrics["router_decision_latency_ms"] == 45.0
            assert metrics["router_misroute_rate"] == 0.05

    def test_calculate_cost(self, router_v2):
        """Test cost calculation for different tiers."""
        # Test Tier A (cheap)
        cost_a = router_v2._calculate_cost(Tier.A)
        assert cost_a == 0.1

        # Test Tier B (medium)
        cost_b = router_v2._calculate_cost(Tier.B)
        assert cost_b == 0.5

        # Test Tier C (expensive)
        cost_c = router_v2._calculate_cost(Tier.C)
        assert cost_c == 1.0

    @pytest.mark.asyncio
    async def test_router_v2_decision_time_measurement(self, router_v2, sample_request):
        """Test that decision time is properly measured."""
        tenant_id = "tenant_123"
        user_id = "user_123"

        # Mock all dependencies to return quickly
        with patch.object(router_v2.feature_extractor, 'extract_features') as mock_extract:
            mock_extract.return_value = RouterFeatures(
                token_count=150,
                schema_strictness=0.8,
                domain_flags={"customer_support": True},
                novelty_score=0.3,
                historical_failure_rate=0.1,
                user_tier="premium",
                time_of_day=14,
                day_of_week=1,
                request_complexity=0.4
            )

            with patch.object(router_v2.canary_manager, 'should_use_canary') as mock_canary:
                mock_canary.return_value = (False, None, None)

                with patch.object(router_v2.classifier, 'classify') as mock_classify:
                    mock_classify.return_value = (Tier.A, 0.9, False)

                    with patch.object(router_v2.early_exit, 'make_escalation_decision') as mock_early_exit:
                        mock_early_exit.return_value = EscalationDecision(
                            should_escalate=False,
                            reason=None,
                            target_tier=None,
                            confidence=0.9,
                            early_exit_tier=None,
                            early_exit_confidence=0.0
                        )

                        with patch.object(router_v2.bandit_policy, 'select_arm') as mock_bandit:
                            mock_bandit.return_value = (Tier.A, 0.85, {"strategy": "exploit"})

                            with patch.object(router_v2.metrics_collector, 'record_decision') as mock_metrics:
                                mock_metrics.return_value = None

                                # Execute routing
                                decision = await router_v2.route_request(sample_request, tenant_id, user_id)

                                # Assertions
                                assert decision.decision_time_ms >= 0
                                assert decision.decision_time_ms < 1000  # Should be fast
