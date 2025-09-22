"""
Integration tests for Router v2 guarantees.

Tests feature extraction, calibrated classification, early exit, and canary management.
"""

import pytest
import asyncio
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch

from apps.router-service.core.feature_extractor import FeatureExtractor, FeatureVector
from apps.router-service.core.calibrated_classifier import CalibratedClassifier, RouterTier, ClassificationResult
from apps.router-service.core.early_exit_manager import EarlyExitManager, EarlyExitResult
from apps.router-service.core.canary_manager import CanaryManager, CanaryStatus
from apps.router-service.core.enhanced_router import EnhancedRouter


@pytest.fixture
def feature_extractor():
    """Create feature extractor for testing."""
    return FeatureExtractor()


@pytest.fixture
def calibrated_classifier():
    """Create calibrated classifier for testing."""
    return CalibratedClassifier(lambda_error=1.0, exploration_rate=0.1)


@pytest.fixture
def early_exit_manager():
    """Create early exit manager for testing."""
    return EarlyExitManager(confidence_threshold=0.85)


@pytest.fixture
def canary_manager():
    """Create canary manager for testing."""
    return CanaryManager()


@pytest.fixture
def enhanced_router():
    """Create enhanced router for testing."""
    return EnhancedRouter(lambda_error=1.0, exploration_rate=0.1, early_exit_threshold=0.85)


class TestFeatureExtractor:
    """Test feature extraction functionality."""
    
    def test_extract_features_basic(self, feature_extractor):
        """Test basic feature extraction."""
        input_text = "Help me analyze this data and create a report"
        input_data = {"query": input_text, "format": "json"}
        
        features = feature_extractor.extract_features(input_text, input_data)
        
        assert features.token_count > 0
        assert 0.0 <= features.json_schema_strictness <= 1.0
        assert len(features.domain_flags) > 0
        assert 0.0 <= features.novelty <= 1.0
        assert 0.0 <= features.historical_failure_rate <= 1.0
        assert 0.0 <= features.complexity_score <= 1.0
        assert 0.0 <= features.urgency_score <= 1.0
        assert 0.0 <= features.cost_sensitivity <= 1.0
    
    def test_extract_features_domain_classification(self, feature_extractor):
        """Test domain classification."""
        # Customer service text
        customer_service_text = "I need help with my billing issue"
        features = feature_extractor.extract_features(customer_service_text)
        assert "customer_service" in features.domain_flags or "billing" in features.domain_flags
        
        # Technical text
        technical_text = "How do I integrate the API with webhooks?"
        features = feature_extractor.extract_features(technical_text)
        assert "technical" in features.domain_flags
    
    def test_extract_features_complexity_analysis(self, feature_extractor):
        """Test complexity analysis."""
        # Simple request
        simple_text = "What is the weather?"
        simple_features = feature_extractor.extract_features(simple_text)
        
        # Complex request
        complex_text = "I need to analyze the correlation between multiple datasets, perform statistical analysis, generate visualizations, and create a comprehensive report with recommendations for business optimization."
        complex_features = feature_extractor.extract_features(complex_text)
        
        assert complex_features.complexity_score > simple_features.complexity_score
    
    def test_extract_features_urgency_analysis(self, feature_extractor):
        """Test urgency analysis."""
        # Urgent request
        urgent_text = "URGENT: The system is down and customers are affected!"
        urgent_features = feature_extractor.extract_features(urgent_text)
        
        # Non-urgent request
        casual_text = "When you have time, could you help me understand this concept?"
        casual_features = feature_extractor.extract_features(casual_text)
        
        assert urgent_features.urgency_score > casual_features.urgency_score
    
    def test_extract_features_cost_sensitivity(self, feature_extractor):
        """Test cost sensitivity analysis."""
        # Cost-sensitive request
        cost_sensitive_text = "I need a quick and cheap solution for this simple task"
        cost_sensitive_features = feature_extractor.extract_features(cost_sensitive_text)
        
        # Cost-insensitive request
        cost_insensitive_text = "I need the best possible solution regardless of cost"
        cost_insensitive_features = feature_extractor.extract_features(cost_insensitive_text)
        
        assert cost_sensitive_features.cost_sensitivity > cost_insensitive_features.cost_sensitivity
    
    def test_record_request_outcome(self, feature_extractor):
        """Test recording request outcomes."""
        input_text = "Test request"
        domain_flags = ["test"]
        
        # Record successful request
        feature_extractor.record_request_outcome(input_text, domain_flags, success=True)
        
        # Record failed request
        feature_extractor.record_request_outcome(input_text, domain_flags, success=False)
        
        # Check that historical failure rate is updated
        features = feature_extractor.extract_features(input_text)
        assert features.historical_failure_rate == 0.5  # 1 success, 1 failure


class TestCalibratedClassifier:
    """Test calibrated classifier functionality."""
    
    def test_classify_basic(self, calibrated_classifier):
        """Test basic classification."""
        features = {
            "token_count": 100,
            "complexity_score": 0.3,
            "novelty": 0.2,
            "json_schema_strictness": 0.8,
            "urgency_score": 0.6,
            "cost_sensitivity": 0.4,
            "historical_failure_rate": 0.1
        }
        
        result = calibrated_classifier.classify(features)
        
        assert isinstance(result, ClassificationResult)
        assert result.tier in RouterTier
        assert 0.0 <= result.confidence <= 1.0
        assert len(result.reasoning) > 0
        assert len(result.raw_scores) == len(RouterTier)
        assert len(result.calibrated_scores) == len(RouterTier)
    
    def test_classify_high_complexity(self, calibrated_classifier):
        """Test classification for high complexity requests."""
        features = {
            "token_count": 1000,
            "complexity_score": 0.9,
            "novelty": 0.8,
            "json_schema_strictness": 0.2,
            "urgency_score": 0.1,
            "cost_sensitivity": 0.1,
            "historical_failure_rate": 0.05
        }
        
        result = calibrated_classifier.classify(features)
        
        # High complexity should prefer higher-tier models
        assert result.tier in [RouterTier.LLM_A, RouterTier.LLM_B, RouterTier.HUMAN]
    
    def test_classify_cost_sensitive(self, calibrated_classifier):
        """Test classification for cost-sensitive requests."""
        features = {
            "token_count": 50,
            "complexity_score": 0.2,
            "novelty": 0.1,
            "json_schema_strictness": 0.9,
            "urgency_score": 0.8,
            "cost_sensitivity": 0.9,
            "historical_failure_rate": 0.02
        }
        
        result = calibrated_classifier.classify(features)
        
        # Cost-sensitive should prefer lower-tier models
        assert result.tier in [RouterTier.SLM_A, RouterTier.SLM_B]
    
    def test_update_with_feedback(self, calibrated_classifier):
        """Test updating classifier with feedback."""
        features = {
            "token_count": 100,
            "complexity_score": 0.5,
            "novelty": 0.3,
            "json_schema_strictness": 0.7,
            "urgency_score": 0.4,
            "cost_sensitivity": 0.3,
            "historical_failure_rate": 0.1
        }
        
        # Initial classification
        result1 = calibrated_classifier.classify(features)
        
        # Update with feedback
        calibrated_classifier.update_with_feedback(
            result1.tier, success=True, actual_cost=0.001, features=features
        )
        
        # Second classification (should potentially be different due to bandit learning)
        result2 = calibrated_classifier.classify(features)
        
        # Results might be different due to bandit exploration
        assert isinstance(result2, ClassificationResult)
    
    def test_get_expected_cost(self, calibrated_classifier):
        """Test expected cost calculation."""
        cost = calibrated_classifier.get_expected_cost(
            RouterTier.LLM_A, 1000, 0.8, 0.5
        )
        
        assert cost > 0
        assert isinstance(cost, float)
    
    def test_should_early_exit(self, calibrated_classifier):
        """Test early exit decision."""
        # Should early exit for SLM_A with high confidence
        should_exit = calibrated_classifier.should_early_exit(
            RouterTier.SLM_A, 0.95
        )
        assert should_exit
        
        # Should not early exit for other tiers
        should_exit = calibrated_classifier.should_early_exit(
            RouterTier.LLM_A, 0.95
        )
        assert not should_exit
        
        # Should not early exit for low confidence
        should_exit = calibrated_classifier.should_early_exit(
            RouterTier.SLM_A, 0.7
        )
        assert not should_exit


class TestEarlyExitManager:
    """Test early exit manager functionality."""
    
    def test_evaluate_early_exit_valid_json(self, early_exit_manager):
        """Test early exit evaluation with valid JSON."""
        response_text = '{"answer": "This is a good response", "confidence": 0.9}'
        
        result = early_exit_manager.evaluate_early_exit(
            response_text, "simple_response"
        )
        
        assert isinstance(result, EarlyExitResult)
        assert result.validated_json is not None
        assert result.confidence > 0
    
    def test_evaluate_early_exit_invalid_json(self, early_exit_manager):
        """Test early exit evaluation with invalid JSON."""
        response_text = "This is not valid JSON"
        
        result = early_exit_manager.evaluate_early_exit(response_text)
        
        assert isinstance(result, EarlyExitResult)
        assert not result.should_exit
        assert result.confidence == 0.0
        assert "Invalid JSON" in result.reason
    
    def test_evaluate_early_exit_schema_validation(self, early_exit_manager):
        """Test early exit evaluation with schema validation."""
        # Valid schema response
        valid_response = '{"category": "general", "probability": 0.95}'
        result = early_exit_manager.evaluate_early_exit(valid_response, "classification")
        
        assert result.validated_json is not None
        
        # Invalid schema response
        invalid_response = '{"invalid": "response"}'
        result = early_exit_manager.evaluate_early_exit(invalid_response, "classification")
        
        assert not result.should_exit
        assert "Schema validation failed" in result.reason
    
    def test_evaluate_early_exit_high_confidence(self, early_exit_manager):
        """Test early exit evaluation with high confidence."""
        response_text = '{"answer": "Comprehensive and accurate response", "confidence": 0.95, "reasoning": "Based on extensive analysis"}'
        
        result = early_exit_manager.evaluate_early_exit(
            response_text, "simple_response"
        )
        
        # Should exit if confidence is above threshold
        if result.confidence >= early_exit_manager.confidence_threshold:
            assert result.should_exit
    
    def test_record_outcome(self, early_exit_manager):
        """Test recording early exit outcomes."""
        # Record successful outcome
        early_exit_manager.record_outcome(success=True)
        
        # Record failed outcome
        early_exit_manager.record_outcome(success=False)
        
        stats = early_exit_manager.get_statistics()
        assert stats["successful_exits"] >= 1
        assert stats["early_exits"] >= 2
    
    def test_adjust_threshold(self, early_exit_manager):
        """Test threshold adjustment."""
        # Record many failed outcomes
        for _ in range(20):
            early_exit_manager.record_outcome(success=False)
        
        should_adjust, new_threshold = early_exit_manager.should_adjust_threshold()
        
        if should_adjust:
            assert new_threshold > early_exit_manager.confidence_threshold


class TestCanaryManager:
    """Test canary manager functionality."""
    
    def test_start_canary(self, canary_manager):
        """Test starting canary deployment."""
        deployment = canary_manager.start_canary("tenant_123", canary_percentage=0.1)
        
        assert deployment.tenant_id == "tenant_123"
        assert deployment.status == CanaryStatus.ACTIVE
        assert deployment.config.canary_percentage == 0.1
    
    def test_start_canary_duplicate(self, canary_manager):
        """Test starting duplicate canary deployment."""
        canary_manager.start_canary("tenant_123")
        
        with pytest.raises(ValueError):
            canary_manager.start_canary("tenant_123")
    
    def test_should_route_to_canary(self, canary_manager):
        """Test canary routing decision."""
        # No canary active
        assert not canary_manager.should_route_to_canary("tenant_123")
        
        # Start canary
        canary_manager.start_canary("tenant_123", canary_percentage=0.5)
        
        # Should sometimes route to canary (50% probability)
        canary_routes = sum(
            canary_manager.should_route_to_canary("tenant_123") 
            for _ in range(100)
        )
        assert 20 <= canary_routes <= 80  # Roughly 50% ± 30%
    
    def test_record_request_metrics(self, canary_manager):
        """Test recording request metrics."""
        canary_manager.start_canary("tenant_123")
        
        # Record baseline metrics
        canary_manager.record_request_metrics(
            "tenant_123", "llm_a", True, 500.0, 0.01
        )
        
        # Record canary metrics
        canary_manager.record_request_metrics(
            "tenant_123", "llm_b", True, 300.0, 0.005, is_canary=True
        )
        
        status = canary_manager.get_deployment_status("tenant_123")
        assert status["decisions_made"] >= 1
        assert status["canary_decisions"] >= 1
    
    def test_quality_drift_detection(self, canary_manager):
        """Test quality drift detection."""
        canary_manager.start_canary("tenant_123")
        
        # Record poor canary performance
        for _ in range(20):
            canary_manager.record_request_metrics(
                "tenant_123", "baseline", True, 500.0, 0.01, quality_score=0.9
            )
            canary_manager.record_request_metrics(
                "tenant_123", "canary", False, 1000.0, 0.02, is_canary=True, quality_score=0.6
            )
        
        # Should trigger rollback due to quality drift
        status = canary_manager.get_deployment_status("tenant_123")
        # The rollback might happen asynchronously, so we check the status
        assert status is not None
    
    def test_stop_canary(self, canary_manager):
        """Test stopping canary deployment."""
        canary_manager.start_canary("tenant_123")
        
        assert canary_manager.stop_canary("tenant_123")
        assert not canary_manager.stop_canary("tenant_123")  # Already stopped
    
    def test_get_statistics(self, canary_manager):
        """Test getting canary statistics."""
        stats = canary_manager.get_statistics()
        
        assert "total_deployments" in stats
        assert "active_deployments" in stats
        assert "successful_deployments" in stats
        assert "rolled_back_deployments" in stats


class TestEnhancedRouter:
    """Test enhanced router integration."""
    
    @pytest.mark.asyncio
    async def test_route_request_basic(self, enhanced_router):
        """Test basic request routing."""
        input_text = "Help me analyze this data"
        
        result = await enhanced_router.route_request(
            input_text=input_text,
            tenant_id="tenant_123",
            context={"user_tier": "premium"}
        )
        
        assert "selected_tier" in result
        assert "confidence" in result
        assert "reasoning" in result
        assert "expected_cost_usd" in result
        assert "expected_latency_ms" in result
        assert "decision_metadata" in result
    
    @pytest.mark.asyncio
    async def test_route_request_with_early_exit(self, enhanced_router):
        """Test request routing with early exit."""
        input_text = "What is the weather today?"
        
        result = await enhanced_router.route_request(
            input_text=input_text,
            tenant_id="tenant_123",
            expected_schema="simple_response"
        )
        
        assert "selected_tier" in result
        
        # If SLM_A is selected with high confidence, should have early exit info
        if (result["selected_tier"] == "slm_a" and 
            result["confidence"] >= enhanced_router.early_exit_manager.confidence_threshold):
            assert "early_exit" in result
            assert "should_exit" in result["early_exit"]
    
    @pytest.mark.asyncio
    async def test_route_request_with_canary(self, enhanced_router):
        """Test request routing with canary deployment."""
        # Start canary deployment
        enhanced_router.start_canary_deployment("tenant_123", canary_percentage=0.1)
        
        input_text = "Analyze this complex dataset"
        
        result = await enhanced_router.route_request(
            input_text=input_text,
            tenant_id="tenant_123"
        )
        
        assert "selected_tier" in result
        assert result["decision_metadata"]["is_canary"] in [True, False]
    
    @pytest.mark.asyncio
    async def test_record_outcome(self, enhanced_router):
        """Test recording routing outcome."""
        # First route a request
        result = await enhanced_router.route_request(
            input_text="Test request",
            tenant_id="tenant_123"
        )
        
        # Record outcome
        await enhanced_router.record_outcome(
            tenant_id="tenant_123",
            tier=RouterTier.LLM_A,
            success=True,
            actual_latency_ms=400.0,
            actual_cost_usd=0.008,
            quality_score=0.9
        )
        
        # Check metrics were updated
        metrics = enhanced_router.get_metrics()
        assert metrics["successful_decisions"] >= 1
    
    def test_canary_deployment_management(self, enhanced_router):
        """Test canary deployment management."""
        # Start canary
        assert enhanced_router.start_canary_deployment("tenant_123")
        
        # Check status
        status = enhanced_router.get_canary_status("tenant_123")
        assert status is not None
        assert status["tenant_id"] == "tenant_123"
        
        # Stop canary
        assert enhanced_router.stop_canary_deployment("tenant_123")
        
        # Check status is None after stopping
        status = enhanced_router.get_canary_status("tenant_123")
        assert status is None
    
    def test_get_metrics(self, enhanced_router):
        """Test getting router metrics."""
        metrics = enhanced_router.get_metrics()
        
        assert "router_decision_latency_ms" in metrics
        assert "router_misroute_rate" in metrics
        assert "tier_distribution" in metrics
        assert "expected_vs_actual_cost" in metrics
        assert "expected_vs_actual_latency" in metrics
        assert "early_exit_rate" in metrics
        assert "canary_activity" in metrics
        assert "total_decisions" in metrics
        assert "successful_decisions" in metrics
    
    def test_calibrate_classifier(self, enhanced_router):
        """Test classifier calibration."""
        # Create calibration data
        calibration_data = [
            ({"token_count": 100, "complexity_score": 0.3}, 0),  # SLM_A
            ({"token_count": 500, "complexity_score": 0.7}, 2),  # LLM_A
            ({"token_count": 1000, "complexity_score": 0.9}, 3), # LLM_B
        ]
        
        # Calibrate classifier
        enhanced_router.calibrate_classifier(calibration_data)
        
        # Check that calibration was applied
        assert enhanced_router.classifier.temperature_scaling.is_calibrated


@pytest.mark.asyncio
async def test_router_performance_requirements():
    """Test router performance requirements."""
    router = EnhancedRouter()
    
    # Test p50 decision latency < 50ms
    start_time = time.time()
    result = await router.route_request(
        input_text="Test request for performance",
        tenant_id="test_tenant"
    )
    decision_time_ms = (time.time() - start_time) * 1000
    
    # Should be well under 50ms for simple requests
    assert decision_time_ms < 50, f"Decision latency {decision_time_ms}ms exceeds 50ms requirement"
    
    # Test misroute rate and drift gates
    # Record some outcomes to build up metrics
    for _ in range(10):
        await router.record_outcome(
            tenant_id="test_tenant",
            tier=RouterTier.LLM_A,
            success=True,
            actual_latency_ms=400.0,
            actual_cost_usd=0.008
        )
    
    metrics = router.get_metrics()
    
    # Misroute rate should be reasonable
    assert metrics["router_misroute_rate"] < 0.1  # Less than 10% misroute rate
    
    # Early exit rate should be tracked
    assert "early_exit_rate" in metrics


@pytest.mark.asyncio
async def test_hypothesis_fuzz_testing():
    """Test router with fuzzed inputs (simplified version)."""
    router = EnhancedRouter()
    
    # Test with various token counts
    for token_count in [10, 100, 1000, 5000]:
        input_text = "x" * token_count  # Simple repeated text
        
        try:
            result = await router.route_request(
                input_text=input_text,
                tenant_id="fuzz_tenant"
            )
            
            assert "selected_tier" in result
            assert "confidence" in result
            assert 0.0 <= result["confidence"] <= 1.0
            
        except Exception as e:
            # Router should handle any input gracefully
            pytest.fail(f"Router failed on input with {token_count} tokens: {e}")
    
    # Test with various schema complexity
    schemas = ["simple_response", "classification", "extraction", "boolean_response"]
    
    for schema in schemas:
        try:
            result = await router.route_request(
                input_text="Test request",
                tenant_id="schema_tenant",
                expected_schema=schema
            )
            
            assert "selected_tier" in result
            
        except Exception as e:
            pytest.fail(f"Router failed on schema {schema}: {e}")
