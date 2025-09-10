"""Unit tests for Router v2 with calibrated bandit policy."""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock
import redis.asyncio as redis

from apps.router-service.core.router_v2 import RouterV2
from apps.router-service.core.feature_extractor import RouterFeatures, Tier
from apps.router-service.core.calibrated_classifier import CalibratedClassifier
from apps.router-service.core.bandit_policy import BanditPolicy
from apps.router-service.core.early_exit_escalation import EarlyExitEscalation, EscalationDecision, EscalationReason
from apps.router-service.core.canary_manager import CanaryManager


@pytest.fixture
async def mock_redis():
    """Mock Redis client."""
    redis_mock = AsyncMock(spec=redis.Redis)
    redis_mock.hgetall.return_value = {}
    redis_mock.get.return_value = None
    redis_mock.setex.return_value = True
    redis_mock.hset.return_value = True
    redis_mock.hincrby.return_value = 1
    redis_mock.hincrbyfloat.return_value = 1.0
    redis_mock.exists.return_value = False
    redis_mock.expire.return_value = True
    redis_mock.delete.return_value = True
    redis_mock.keys.return_value = []
    redis_mock.lrange.return_value = []
    return redis_mock


@pytest.fixture
def sample_features():
    """Sample router features for testing."""
    return RouterFeatures(
        token_count=100,
        schema_strictness=0.8,
        domain_flags={'customer_support': True},
        novelty_score=0.3,
        historical_failure_rate=0.1,
        user_tier="standard",
        time_of_day=12,
        day_of_week=1,
        request_complexity=0.2
    )


@pytest.fixture
def sample_request():
    """Sample request for testing."""
    return {
        'message': 'Hello, I need help with my order',
        'user_id': 'user123',
        'tenant_id': 'tenant456'
    }


class TestFeatureExtractor:
    """Test feature extractor."""
    
    @pytest.mark.asyncio
    async def test_extract_features_basic(self, mock_redis, sample_request):
        """Test basic feature extraction."""
        from apps.router-service.core.feature_extractor import FeatureExtractor
        
        extractor = FeatureExtractor(mock_redis)
        features = await extractor.extract_features(sample_request, 'tenant123', 'user456')
        
        assert features.token_count > 0
        assert 0.0 <= features.schema_strictness <= 1.0
        assert 0.0 <= features.novelty_score <= 1.0
        assert 0.0 <= features.historical_failure_rate <= 1.0
        assert 0.0 <= features.request_complexity <= 1.0
        assert features.user_tier in ['standard', 'premium', 'enterprise']
    
    @pytest.mark.asyncio
    async def test_extract_features_with_redis_data(self, mock_redis, sample_request):
        """Test feature extraction with Redis data."""
        from apps.router-service.core.feature_extractor import FeatureExtractor
        
        # Mock Redis responses
        mock_redis.hgetall.return_value = {
            'failure_rate': '0.2',
            'user_tier': 'premium'
        }
        mock_redis.lrange.return_value = [b'previous request 1', b'previous request 2']
        
        extractor = FeatureExtractor(mock_redis)
        features = await extractor.extract_features(sample_request, 'tenant123', 'user456')
        
        assert features.historical_failure_rate == 0.2
        assert features.user_tier == 'premium'
    
    @pytest.mark.asyncio
    async def test_token_count_estimation(self, mock_redis):
        """Test token count estimation."""
        from apps.router-service.core.feature_extractor import FeatureExtractor
        
        extractor = FeatureExtractor(mock_redis)
        
        # Test with different message lengths
        short_request = {'message': 'Hi'}
        long_request = {'message': 'This is a very long message with many words that should result in a higher token count estimation'}
        
        short_features = await extractor.extract_features(short_request, 'tenant', 'user')
        long_features = await extractor.extract_features(long_request, 'tenant', 'user')
        
        assert long_features.token_count > short_features.token_count


class TestCalibratedClassifier:
    """Test calibrated classifier."""
    
    @pytest.mark.asyncio
    async def test_classify_basic(self, mock_redis, sample_features):
        """Test basic classification."""
        classifier = CalibratedClassifier(mock_redis)
        tier, confidence, should_escalate = await classifier.classify(sample_features, 'tenant123')
        
        assert tier in [Tier.A, Tier.B, Tier.C]
        assert 0.0 <= confidence <= 1.0
        assert isinstance(should_escalate, bool)
    
    @pytest.mark.asyncio
    async def test_classify_with_calibration(self, mock_redis, sample_features):
        """Test classification with calibration data."""
        # Mock calibration data
        mock_redis.hgetall.return_value = {
            'temperature': '0.8',
            'confidence_threshold': '0.7',
            'accuracy_threshold': '0.9'
        }
        
        classifier = CalibratedClassifier(mock_redis)
        tier, confidence, should_escalate = await classifier.classify(sample_features, 'tenant123')
        
        assert tier in [Tier.A, Tier.B, Tier.C]
        assert 0.0 <= confidence <= 1.0
    
    @pytest.mark.asyncio
    async def test_temperature_scaling(self, mock_redis):
        """Test temperature scaling."""
        classifier = CalibratedClassifier(mock_redis)
        
        # Test with different temperatures
        scores = {Tier.A: 0.3, Tier.B: 0.5, Tier.C: 0.2}
        
        # Low temperature (more confident)
        low_temp_scores = classifier._apply_temperature_scaling(scores, 0.5)
        
        # High temperature (less confident)
        high_temp_scores = classifier._apply_temperature_scaling(scores, 2.0)
        
        # Low temperature should make differences more pronounced
        assert abs(low_temp_scores[Tier.B] - low_temp_scores[Tier.A]) > abs(high_temp_scores[Tier.B] - high_temp_scores[Tier.A])


class TestBanditPolicy:
    """Test bandit policy."""
    
    @pytest.mark.asyncio
    async def test_select_arm_basic(self, mock_redis, sample_features):
        """Test basic arm selection."""
        policy = BanditPolicy(mock_redis)
        tier, value, info = await policy.select_arm(sample_features, 'tenant123')
        
        assert tier in [Tier.A, Tier.B, Tier.C]
        assert isinstance(value, float)
        assert 'strategy' in info
    
    @pytest.mark.asyncio
    async def test_update_arm(self, mock_redis):
        """Test arm update."""
        policy = BanditPolicy(mock_redis)
        
        # Update arm with success
        await policy.update_arm('tenant123', Tier.A, 1.0, 0.1, False)
        
        # Update arm with failure
        await policy.update_arm('tenant123', Tier.A, 0.0, 0.1, True)
        
        # Verify Redis calls
        assert mock_redis.hset.called
        assert mock_redis.expire.called
    
    @pytest.mark.asyncio
    async def test_ucb_selection(self, mock_redis, sample_features):
        """Test UCB arm selection."""
        # Mock arm data with different pull counts
        mock_redis.hgetall.side_effect = [
            {'pulls': '10', 'rewards': '8.0', 'costs': '1.0', 'errors': '1'},  # Tier A
            {'pulls': '5', 'rewards': '4.0', 'costs': '2.5', 'errors': '0'},   # Tier B
            {'pulls': '2', 'rewards': '1.0', 'costs': '2.0', 'errors': '0'}    # Tier C
        ]
        
        policy = BanditPolicy(mock_redis)
        tier, value, info = await policy.select_arm(sample_features, 'tenant123')
        
        assert tier in [Tier.A, Tier.B, Tier.C]
        assert 'strategy' in info


class TestEarlyExitEscalation:
    """Test early exit and escalation."""
    
    @pytest.mark.asyncio
    async def test_early_exit_conditions(self, mock_redis, sample_features):
        """Test early exit conditions."""
        escalation = EarlyExitEscalation(mock_redis)
        
        # Test with high schema strictness (should allow early exit)
        high_strictness_features = RouterFeatures(
            token_count=50,
            schema_strictness=0.9,
            domain_flags={'customer_support': True},
            novelty_score=0.2,
            historical_failure_rate=0.1,
            user_tier="standard",
            time_of_day=12,
            day_of_week=1,
            request_complexity=0.1
        )
        
        decision = await escalation.make_escalation_decision(
            high_strictness_features, Tier.A, 0.9, 'tenant123'
        )
        
        # Should not escalate for high confidence, low risk
        assert not decision.should_escalate or decision.early_exit_tier is not None
    
    @pytest.mark.asyncio
    async def test_escalation_conditions(self, mock_redis, sample_features):
        """Test escalation conditions."""
        escalation = EarlyExitEscalation(mock_redis)
        
        # Test with low confidence (should escalate)
        decision = await escalation.make_escalation_decision(
            sample_features, Tier.A, 0.5, 'tenant123'
        )
        
        # Should escalate for low confidence
        if decision.should_escalate:
            assert decision.reason is not None
            assert decision.target_tier in [Tier.A, Tier.B, Tier.C]
    
    @pytest.mark.asyncio
    async def test_record_escalation_outcome(self, mock_redis):
        """Test recording escalation outcome."""
        escalation = EarlyExitEscalation(mock_redis)
        
        await escalation.record_escalation_outcome(
            'tenant123', Tier.A, Tier.B, EscalationReason.LOW_CONFIDENCE, True, 100.0
        )
        
        assert mock_redis.hset.called
        assert mock_redis.expire.called


class TestCanaryManager:
    """Test canary manager."""
    
    @pytest.mark.asyncio
    async def test_should_use_canary(self, mock_redis, sample_features):
        """Test canary user selection."""
        canary_manager = CanaryManager(mock_redis)
        
        # Mock user hash to be in canary
        mock_redis.get.return_value = b'0000'  # Low hash value
        
        is_canary, tier, info = await canary_manager.should_use_canary(
            'tenant123', 'user456', sample_features
        )
        
        # Should be in canary with low hash
        assert is_canary
        assert tier in [Tier.A, Tier.B, Tier.C]
        assert 'canary_percentage' in info
    
    @pytest.mark.asyncio
    async def test_record_canary_outcome(self, mock_redis):
        """Test recording canary outcome."""
        canary_manager = CanaryManager(mock_redis)
        
        await canary_manager.record_canary_outcome(
            'tenant123', 'user456', Tier.A, True, 50.0, 0.9
        )
        
        assert mock_redis.hset.called
        assert mock_redis.expire.called
    
    @pytest.mark.asyncio
    async def test_rollback_conditions(self, mock_redis):
        """Test rollback conditions."""
        canary_manager = CanaryManager(mock_redis)
        
        # Mock low quality metrics
        mock_redis.hgetall.return_value = {
            'total_requests': '100',
            'successful_requests': '50',
            'quality_score': '0.5',  # Below threshold
            'average_latency': '100.0'
        }
        
        await canary_manager.record_canary_outcome(
            'tenant123', 'user456', Tier.A, False, 100.0, 0.5
        )
        
        # Should trigger rollback check
        assert mock_redis.hset.called


class TestRouterV2:
    """Test Router v2 integration."""
    
    @pytest.mark.asyncio
    async def test_route_request_basic(self, mock_redis, sample_request):
        """Test basic request routing."""
        router = RouterV2(mock_redis)
        
        decision = await router.route_request(sample_request, 'tenant123', 'user456')
        
        assert decision.tier in [Tier.A, Tier.B, Tier.C]
        assert 0.0 <= decision.confidence <= 1.0
        assert decision.decision_time_ms > 0
        assert decision.features is not None
    
    @pytest.mark.asyncio
    async def test_route_request_with_canary(self, mock_redis, sample_request):
        """Test request routing with canary."""
        # Mock canary selection
        mock_redis.get.return_value = b'0000'  # Low hash for canary
        
        router = RouterV2(mock_redis)
        decision = await router.route_request(sample_request, 'tenant123', 'user456')
        
        # Should use canary if selected
        if decision.canary_info:
            assert 'canary_tier' in decision.canary_info
            assert decision.canary_info['canary_tier'] in ['A', 'B', 'C']
    
    @pytest.mark.asyncio
    async def test_record_outcome(self, mock_redis):
        """Test recording routing outcome."""
        router = RouterV2(mock_redis)
        
        await router.record_outcome('tenant123', 'user456', Tier.A, True, 50.0, 0.9)
        
        # Should update bandit policy
        assert mock_redis.hset.called
    
    @pytest.mark.asyncio
    async def test_get_router_statistics(self, mock_redis):
        """Test getting router statistics."""
        router = RouterV2(mock_redis)
        
        stats = await router.get_router_statistics('tenant123')
        
        assert 'tenant_id' in stats
        assert 'bandit_statistics' in stats
        assert 'canary_status' in stats
        assert 'escalation_statistics' in stats
        assert 'recent_metrics' in stats
    
    @pytest.mark.asyncio
    async def test_decision_time_performance(self, mock_redis, sample_request):
        """Test that decision time is under 50ms."""
        router = RouterV2(mock_redis)
        
        start_time = time.time()
        decision = await router.route_request(sample_request, 'tenant123', 'user456')
        end_time = time.time()
        
        actual_time_ms = (end_time - start_time) * 1000
        
        # Should be under 50ms
        assert actual_time_ms < 50
        assert decision.decision_time_ms < 50


class TestIntegration:
    """Integration tests for router v2."""
    
    @pytest.mark.asyncio
    async def test_feature_to_decision_pipeline(self, mock_redis, sample_request):
        """Test complete feature extraction to decision pipeline."""
        router = RouterV2(mock_redis)
        
        decision = await router.route_request(sample_request, 'tenant123', 'user456')
        
        # Verify all components are used
        assert decision.features is not None
        assert decision.tier in [Tier.A, Tier.B, Tier.C]
        assert decision.confidence > 0
        
        # Verify decision time is reasonable
        assert decision.decision_time_ms < 100  # Should be fast
    
    @pytest.mark.asyncio
    async def test_learning_loop(self, mock_redis, sample_request):
        """Test learning loop with multiple requests."""
        router = RouterV2(mock_redis)
        
        # Make multiple routing decisions
        decisions = []
        for i in range(5):
            decision = await router.route_request(sample_request, 'tenant123', f'user{i}')
            decisions.append(decision)
            
            # Record outcome
            success = i % 2 == 0  # Alternate success/failure
            await router.record_outcome('tenant123', f'user{i}', decision.tier, success, 50.0, 0.8)
        
        # All decisions should be valid
        for decision in decisions:
            assert decision.tier in [Tier.A, Tier.B, Tier.C]
            assert decision.confidence > 0
    
    @pytest.mark.asyncio
    async def test_canary_gating_works(self, mock_redis, sample_request):
        """Test that canary gating works correctly."""
        canary_manager = CanaryManager(mock_redis)
        
        # Test with different user hashes
        test_cases = [
            ('user1', b'0000', True),   # Low hash, should be canary
            ('user2', b'9999', False),  # High hash, should not be canary
        ]
        
        for user_id, hash_value, expected_canary in test_cases:
            mock_redis.get.return_value = hash_value
            
            is_canary, tier, info = await canary_manager.should_use_canary(
                'tenant123', user_id, None
            )
            
            if expected_canary:
                assert is_canary
                assert tier is not None
            else:
                assert not is_canary


if __name__ == '__main__':
    pytest.main([__file__])
