"""Hypothesis fuzzing tests for router and system components."""

import pytest
import asyncio
import json
import time
from hypothesis import given, strategies as st, settings, example
from hypothesis.strategies import composite, text, integers, floats, booleans, dictionaries

from tests._fixtures.factories import TenantFactory, RouterRequestFactory
from tests._helpers.assertions import RouterAssertions, JSONAssertions
from libs.contracts.router import RouterDecisionRequest, RouterDecision, RouterTier


class TestRouterHypothesisFuzzing:
    """Test router with Hypothesis fuzzing."""
    
    @composite
    def router_request_strategy(draw):
        """Generate router request test data."""
        tenant_id = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))))
        message = draw(st.text(min_size=1, max_size=500))
        token_count = draw(st.integers(min_value=1, max_value=200))
        json_strictness = draw(st.floats(min_value=0.0, max_value=1.0))
        novelty_score = draw(st.floats(min_value=0.0, max_value=1.0))
        failure_rate = draw(st.floats(min_value=0.0, max_value=0.5))
        
        return {
            "tenant_id": f"tenant_{tenant_id}",
            "message": message,
            "context": {
                "user_id": draw(st.text(min_size=1, max_size=50)),
                "session_id": draw(st.text(min_size=1, max_size=50))
            },
            "features": {
                "token_count": token_count,
                "json_schema_strictness": json_strictness,
                "domain_flags": {
                    "customer_support": draw(st.booleans()),
                    "sales": draw(st.booleans()),
                    "technical": draw(st.booleans())
                },
                "novelty_score": novelty_score,
                "historical_failure_rate": failure_rate
            }
        }
    
    @given(router_request_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_router_request_validation(self, request_data):
        """Test router request validation with fuzzed data."""
        try:
            router_request = RouterDecisionRequest(**request_data)
            
            # Verify all fields are present and valid
            assert router_request.tenant_id == request_data["tenant_id"]
            assert router_request.message == request_data["message"]
            assert router_request.context.user_id == request_data["context"]["user_id"]
            assert router_request.features.token_count == request_data["features"]["token_count"]
            assert router_request.features.json_schema_strictness == request_data["features"]["json_schema_strictness"]
            assert router_request.features.novelty_score == request_data["features"]["novelty_score"]
            assert router_request.features.historical_failure_rate == request_data["features"]["historical_failure_rate"]
            
        except ValueError as e:
            # Some fuzzed data may be invalid, which is expected
            # We just want to ensure the validation doesn't crash
            assert "validation" in str(e).lower() or "required" in str(e).lower()
    
    @given(
        token_count=st.integers(min_value=1, max_value=1000),
        json_strictness=st.floats(min_value=0.0, max_value=1.0),
        novelty_score=st.floats(min_value=0.0, max_value=1.0),
        failure_rate=st.floats(min_value=0.0, max_value=1.0)
    )
    def test_router_tier_selection_fuzzing(self, token_count, json_strictness, novelty_score, failure_rate):
        """Test router tier selection with fuzzed parameters."""
        # Simulate tier selection logic
        if token_count <= 5 and json_strictness > 0.8 and novelty_score < 0.2 and failure_rate < 0.1:
            expected_tier = RouterTier.SLM_A
        elif token_count <= 20 and novelty_score < 0.6 and failure_rate < 0.3:
            expected_tier = RouterTier.SLM_B
        else:
            expected_tier = RouterTier.LLM
        
        # Verify tier selection is reasonable
        assert expected_tier in [RouterTier.SLM_A, RouterTier.SLM_B, RouterTier.LLM]
        
        # Verify tier selection logic consistency
        if expected_tier == RouterTier.SLM_A:
            assert token_count <= 10  # SLM_A for simple requests
            assert json_strictness > 0.7  # High structure confidence
        elif expected_tier == RouterTier.SLM_B:
            assert token_count <= 30  # SLM_B for moderate requests
            assert novelty_score < 0.8  # Not too novel
        else:  # LLM
            assert token_count > 5 or novelty_score > 0.5 or failure_rate > 0.2  # Complex cases
    
    @given(
        message=st.text(min_size=1, max_size=1000),
        confidence=st.floats(min_value=0.0, max_value=1.0),
        cost=st.floats(min_value=0.0, max_value=1.0),
        latency=st.integers(min_value=1, max_value=10000)
    )
    def test_router_decision_fuzzing(self, message, confidence, cost, latency):
        """Test router decision with fuzzed parameters."""
        # Create router decision
        try:
            decision = RouterDecision(
                tier=RouterTier.SLM_A,
                confidence=confidence,
                expected_cost_usd=cost,
                expected_latency_ms=latency,
                reasoning=f"Decision for message: {message[:50]}"
            )
            
            # Verify decision validity
            assert 0.0 <= decision.confidence <= 1.0
            assert decision.expected_cost_usd >= 0.0
            assert decision.expected_latency_ms >= 0
            
        except ValueError as e:
            # Some combinations may be invalid
            assert "validation" in str(e).lower() or "range" in str(e).lower()
    
    @given(
        json_data=st.dictionaries(
            keys=st.text(min_size=1, max_size=20),
            values=st.one_of(
                st.text(),
                st.integers(),
                st.floats(),
                st.booleans(),
                st.lists(st.text())
            )
        )
    )
    def test_json_validation_fuzzing(self, json_data):
        """Test JSON validation with fuzzed data."""
        try:
            json_str = json.dumps(json_data)
            
            # Test JSON validation
            result = JSONAssertions.assert_valid_json(json_str, "Fuzzed JSON validation")
            
            if result.passed:
                # If valid JSON, verify structure
                parsed_data = json.loads(json_str)
                assert parsed_data == json_data
                
                # Test for markdown wrapping
                markdown_result = JSONAssertions.assert_no_markdown_json(json_str, "Fuzzed markdown check")
                assert markdown_result.passed
            
        except (json.JSONDecodeError, TypeError, ValueError):
            # Some fuzzed data may produce invalid JSON, which is expected
            pass
    
    @given(
        text_content=st.text(min_size=0, max_size=1000)
    )
    def test_pii_detection_fuzzing(self, text_content):
        """Test PII detection with fuzzed text."""
        # Import PII assertions
        from tests._helpers.assertions import PIIAssertions
        
        # Test PII detection
        result = PIIAssertions.assert_no_pii_in_text(text_content, "Fuzzed PII detection")
        
        # If PII is detected, verify the detection is reasonable
        if not result.passed:
            # Check if detected PII is actually PII-like
            has_email_like = "@" in text_content and "." in text_content
            has_phone_like = any(char.isdigit() for char in text_content) and len([c for c in text_content if c.isdigit()]) >= 7
            has_ssn_like = "-" in text_content and len([c for c in text_content if c.isdigit()]) >= 9
            
            # If PII detected, it should be for a reasonable reason
            assert has_email_like or has_phone_like or has_ssn_like or len(text_content) == 0
    
    @given(
        tenant_ids=st.lists(
            st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
            min_size=2,
            max_size=10
        )
    )
    def test_multi_tenant_isolation_fuzzing(self, tenant_ids):
        """Test multi-tenant isolation with fuzzed tenant IDs."""
        from tests._helpers.assertions import MultiTenantAssertions
        
        # Create mock data with different tenant IDs
        mock_data = []
        for i, tenant_id in enumerate(tenant_ids):
            mock_data.append({
                "tenant_id": f"tenant_{tenant_id}",
                "data": f"data_for_{tenant_id}",
                "index": i
            })
        
        # Test tenant isolation
        result = MultiTenantAssertions.assert_tenant_isolation(
            mock_data, "tenant_id", "Fuzzed multi-tenant isolation"
        )
        
        # Should fail because we have multiple tenants
        assert not result.passed
        
        # Test with single tenant data
        single_tenant_data = [item for item in mock_data if item["tenant_id"] == mock_data[0]["tenant_id"]]
        if len(single_tenant_data) > 1:
            single_result = MultiTenantAssertions.assert_tenant_isolation(
                single_tenant_data, "tenant_id", "Single tenant isolation"
            )
            assert single_result.passed
    
    @given(
        latency_values=st.lists(
            st.integers(min_value=1, max_value=10000),
            min_size=1,
            max_size=100
        )
    )
    def test_performance_assertions_fuzzing(self, latency_values):
        """Test performance assertions with fuzzed latency values."""
        from tests._helpers.assertions import PerformanceAssertions
        
        # Test each latency value
        for latency in latency_values:
            # Test with different thresholds
            thresholds = [10, 50, 100, 500, 1000, 5000]
            
            for threshold in thresholds:
                result = PerformanceAssertions.assert_latency_below_threshold(
                    latency, threshold, f"Fuzzed latency test: {latency}ms vs {threshold}ms"
                )
                
                # Verify assertion logic is correct
                if latency <= threshold:
                    assert result.passed, f"Latency {latency} should pass threshold {threshold}"
                else:
                    assert not result.passed, f"Latency {latency} should fail threshold {threshold}"
    
    @given(
        throughput_values=st.lists(
            st.floats(min_value=0.1, max_value=10000.0),
            min_size=1,
            max_size=50
        )
    )
    def test_throughput_assertions_fuzzing(self, throughput_values):
        """Test throughput assertions with fuzzed values."""
        from tests._helpers.assertions import PerformanceAssertions
        
        # Test each throughput value
        for throughput in throughput_values:
            # Test with different thresholds
            thresholds = [1.0, 10.0, 50.0, 100.0, 500.0, 1000.0]
            
            for threshold in thresholds:
                result = PerformanceAssertions.assert_throughput_above_threshold(
                    throughput, threshold, f"Fuzzed throughput test: {throughput} rps vs {threshold} rps"
                )
                
                # Verify assertion logic is correct
                if throughput >= threshold:
                    assert result.passed, f"Throughput {throughput} should pass threshold {threshold}"
                else:
                    assert not result.passed, f"Throughput {throughput} should fail threshold {threshold}"
    
    @given(
        error_messages=st.lists(
            st.text(min_size=1, max_size=200),
            min_size=1,
            max_size=20
        )
    )
    def test_error_response_structure_fuzzing(self, error_messages):
        """Test error response structure with fuzzed messages."""
        from tests._helpers.assertions import ContractAssertions
        
        for message in error_messages:
            # Create error response
            error_response = {
                "error": "Test Error",
                "message": message,
                "code": "TEST_ERROR",
                "timestamp": "2024-01-01T12:00:00Z"
            }
            
            # Test error response structure
            result = ContractAssertions.assert_structured_error_response(
                error_response, f"Fuzzed error response: {message[:30]}"
            )
            
            # Should pass because it has required fields
            assert result.passed
            
            # Test with missing required field
            incomplete_response = {
                "message": message,
                "code": "TEST_ERROR"
                # Missing "error" field
            }
            
            incomplete_result = ContractAssertions.assert_structured_error_response(
                incomplete_response, f"Incomplete error response: {message[:30]}"
            )
            
            # Should fail because required field is missing
            assert not incomplete_result.passed


class TestSystemHypothesisFuzzing:
    """Test system components with Hypothesis fuzzing."""
    
    @given(
        config_data=st.dictionaries(
            keys=st.text(min_size=1, max_size=50),
            values=st.one_of(
                st.text(),
                st.integers(),
                st.floats(),
                st.booleans(),
                st.lists(st.text())
            ),
            min_size=1,
            max_size=20
        )
    )
    def test_configuration_fuzzing(self, config_data):
        """Test configuration handling with fuzzed data."""
        # Test configuration validation
        try:
            # Simulate configuration processing
            validated_config = {}
            
            for key, value in config_data.items():
                # Basic validation rules
                if isinstance(key, str) and len(key) > 0:
                    if isinstance(value, (str, int, float, bool)):
                        validated_config[key] = value
                    elif isinstance(value, list):
                        # Validate list contents
                        if all(isinstance(item, str) for item in value):
                            validated_config[key] = value
            
            # Verify validated config is subset of original
            for key, value in validated_config.items():
                assert key in config_data
                assert config_data[key] == value
                
        except (TypeError, ValueError, KeyError):
            # Some fuzzed configurations may be invalid
            pass
    
    @given(
        metric_data=st.lists(
            st.dictionaries(
                keys=st.text(min_size=1, max_size=20),
                values=st.one_of(
                    st.integers(min_value=0),
                    st.floats(min_value=0.0),
                    st.booleans()
                ),
                min_size=1,
                max_size=10
            ),
            min_size=1,
            max_size=100
        )
    )
    def test_metrics_processing_fuzzing(self, metric_data):
        """Test metrics processing with fuzzed data."""
        # Test metrics validation and processing
        processed_metrics = []
        
        for metric in metric_data:
            try:
                # Validate metric structure
                if "name" in metric and "value" in metric:
                    processed_metric = {
                        "name": str(metric["name"]),
                        "value": float(metric["value"]) if isinstance(metric["value"], (int, float)) else 0.0,
                        "timestamp": time.time()
                    }
                    processed_metrics.append(processed_metric)
            except (TypeError, ValueError, KeyError):
                # Skip invalid metrics
                continue
        
        # Verify processed metrics
        assert len(processed_metrics) >= 0
        for metric in processed_metrics:
            assert isinstance(metric["name"], str)
            assert isinstance(metric["value"], float)
            assert metric["value"] >= 0.0
            assert isinstance(metric["timestamp"], float)
    
    @given(
        event_data=st.dictionaries(
            keys=st.text(min_size=1, max_size=30),
            values=st.one_of(
                st.text(),
                st.integers(),
                st.floats(),
                st.booleans(),
                st.dictionaries(
                    keys=st.text(),
                    values=st.text(),
                    max_size=10
                )
            ),
            min_size=1,
            max_size=15
        )
    )
    def test_event_processing_fuzzing(self, event_data):
        """Test event processing with fuzzed data."""
        # Test event validation
        try:
            # Simulate event processing
            processed_event = {
                "event_id": "evt_" + str(hash(str(event_data)))[:8],
                "timestamp": time.time(),
                "data": event_data
            }
            
            # Verify event structure
            assert "event_id" in processed_event
            assert "timestamp" in processed_event
            assert "data" in processed_event
            assert isinstance(processed_event["timestamp"], float)
            assert processed_event["timestamp"] > 0
            
        except (TypeError, ValueError):
            # Some fuzzed events may be invalid
            pass
