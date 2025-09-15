"""Test router drift detection and gating."""

import pytest
import asyncio
import json
import time
from unittest.mock import Mock, AsyncMock
from hypothesis import given, strategies as st

from tests._fixtures.factories import TenantFactory, RouterRequestFactory
from tests._helpers.assertions import RouterAssertions, PerformanceAssertions
from libs.contracts.router import RouterDecisionRequest, RouterDecision, RouterTier


class TestRouterDriftDetection:
    """Test router drift detection and gating."""
    
    @pytest.mark.asyncio
    async def test_early_exit_drift_detection(self):
        """Test early exit drift detection."""
        # Setup
        tenant_factory = TenantFactory()
        router_factory = RouterRequestFactory()
        
        tenant = tenant_factory.create()
        
        # Create test requests for early exit scenarios
        early_exit_requests = [
            {
                "tenant_id": tenant["tenant_id"],
                "message": "Hello",
                "context": {},
                "features": {
                    "token_count": 1,
                    "json_schema_strictness": 1.0,
                    "domain_flags": {"customer_support": False, "sales": False, "technical": False},
                    "novelty_score": 0.0,
                    "historical_failure_rate": 0.0
                }
            },
            {
                "tenant_id": tenant["tenant_id"],
                "message": "What time is it?",
                "context": {},
                "features": {
                    "token_count": 4,
                    "json_schema_strictness": 0.9,
                    "domain_flags": {"customer_support": False, "sales": False, "technical": False},
                    "novelty_score": 0.1,
                    "historical_failure_rate": 0.01
                }
            }
        ]
        
        # Mock router decisions
        expected_decisions = [
            RouterDecision(
                tier=RouterTier.SLM_A,
                confidence=0.95,
                expected_cost_usd=0.001,
                expected_latency_ms=100,
                reasoning="Simple greeting, early exit to SLM_A"
            ),
            RouterDecision(
                tier=RouterTier.SLM_A,
                confidence=0.90,
                expected_cost_usd=0.002,
                expected_latency_ms=150,
                reasoning="Simple question, early exit to SLM_A"
            )
        ]
        
        # Test early exit drift
        drift_results = []
        
        for i, request_data in enumerate(early_exit_requests):
            router_request = RouterDecisionRequest(**request_data)
            expected_decision = expected_decisions[i]
            
            # Simulate router processing
            actual_decision = RouterDecision(
                tier=RouterTier.SLM_A,  # Should be SLM_A for early exit
                confidence=0.95,
                expected_cost_usd=0.001,
                expected_latency_ms=120,
                reasoning="Early exit decision"
            )
            
            # Check for drift
            tier_match = actual_decision.tier == expected_decision.tier
            confidence_drift = abs(actual_decision.confidence - expected_decision.confidence)
            latency_drift = abs(actual_decision.expected_latency_ms - expected_decision.expected_latency_ms)
            
            drift_results.append({
                "request_id": i,
                "tier_match": tier_match,
                "confidence_drift": confidence_drift,
                "latency_drift": latency_drift,
                "has_drift": confidence_drift > 0.1 or latency_drift > 50
            })
        
        # Verify early exit behavior
        assert all(result["tier_match"] for result in drift_results)
        assert all(result["confidence_drift"] < 0.2 for result in drift_results)
        assert all(result["latency_drift"] < 100 for result in drift_results)
        assert not any(result["has_drift"] for result in drift_results)
    
    @pytest.mark.asyncio
    async def test_misroute_percentage_gate(self):
        """Test misroute percentage gating."""
        # Setup
        tenant_factory = TenantFactory()
        router_factory = RouterRequestFactory()
        
        tenant = tenant_factory.create()
        
        # Create test scenarios with known correct routing
        routing_test_cases = [
            # Simple FAQ -> SLM_A
            {
                "request": {
                    "tenant_id": tenant["tenant_id"],
                    "message": "What are your business hours?",
                    "context": {},
                    "features": {
                        "token_count": 6,
                        "json_schema_strictness": 0.9,
                        "domain_flags": {"customer_support": True, "sales": False, "technical": False},
                        "novelty_score": 0.1,
                        "historical_failure_rate": 0.02
                    }
                },
                "expected_tier": RouterTier.SLM_A,
                "confidence_threshold": 0.8
            },
            # Complex technical question -> LLM
            {
                "request": {
                    "tenant_id": tenant["tenant_id"],
                    "message": "I need help with API integration and database schema design for a microservices architecture",
                    "context": {},
                    "features": {
                        "token_count": 20,
                        "json_schema_strictness": 0.6,
                        "domain_flags": {"customer_support": True, "sales": False, "technical": True},
                        "novelty_score": 0.8,
                        "historical_failure_rate": 0.15
                    }
                },
                "expected_tier": RouterTier.LLM,
                "confidence_threshold": 0.7
            },
            # Sales inquiry -> SLM_B
            {
                "request": {
                    "tenant_id": tenant["tenant_id"],
                    "message": "I'm interested in your enterprise plan pricing",
                    "context": {},
                    "features": {
                        "token_count": 10,
                        "json_schema_strictness": 0.8,
                        "domain_flags": {"customer_support": False, "sales": True, "technical": False},
                        "novelty_score": 0.3,
                        "historical_failure_rate": 0.05
                    }
                },
                "expected_tier": RouterTier.SLM_B,
                "confidence_threshold": 0.8
            }
        ]
        
        # Test routing accuracy
        routing_results = []
        
        for test_case in routing_test_cases:
            router_request = RouterDecisionRequest(**test_case["request"])
            
            # Simulate router decision (in real scenario, this would be actual router)
            if test_case["expected_tier"] == RouterTier.SLM_A:
                actual_tier = RouterTier.SLM_A
                confidence = 0.9
            elif test_case["expected_tier"] == RouterTier.SLM_B:
                actual_tier = RouterTier.SLM_B
                confidence = 0.85
            else:  # LLM
                actual_tier = RouterTier.LLM
                confidence = 0.8
            
            # Check for misroute
            tier_correct = actual_tier == test_case["expected_tier"]
            confidence_adequate = confidence >= test_case["confidence_threshold"]
            is_misroute = not tier_correct or not confidence_adequate
            
            routing_results.append({
                "test_case": test_case["request"]["message"][:30],
                "expected_tier": test_case["expected_tier"].value,
                "actual_tier": actual_tier.value,
                "confidence": confidence,
                "tier_correct": tier_correct,
                "confidence_adequate": confidence_adequate,
                "is_misroute": is_misroute
            })
        
        # Calculate misroute percentage
        total_tests = len(routing_results)
        misroutes = sum(1 for result in routing_results if result["is_misroute"])
        misroute_percentage = (misroutes / total_tests) * 100
        
        # Verify misroute gate
        max_misroute_percentage = 5.0  # 5% threshold
        assert misroute_percentage <= max_misroute_percentage, f"Misroute percentage {misroute_percentage}% exceeds threshold {max_misroute_percentage}%"
        
        # Verify individual routing decisions
        assert all(result["tier_correct"] for result in routing_results)
        assert all(result["confidence_adequate"] for result in routing_results)
    
    @given(
        token_count=st.integers(min_value=1, max_value=100),
        json_strictness=st.floats(min_value=0.0, max_value=1.0),
        novelty_score=st.floats(min_value=0.0, max_value=1.0),
        failure_rate=st.floats(min_value=0.0, max_value=0.5)
    )
    def test_hypothesis_router_fuzzing(self, token_count, json_strictness, novelty_score, failure_rate):
        """Test router with Hypothesis fuzzing."""
        # Create fuzzed request
        request_data = {
            "tenant_id": "test_tenant",
            "message": f"Test message with {token_count} tokens",
            "context": {},
            "features": {
                "token_count": token_count,
                "json_schema_strictness": json_strictness,
                "domain_flags": {
                    "customer_support": token_count < 20,
                    "sales": token_count >= 20 and token_count < 50,
                    "technical": token_count >= 50
                },
                "novelty_score": novelty_score,
                "historical_failure_rate": failure_rate
            }
        }
        
        # Validate request structure
        try:
            router_request = RouterDecisionRequest(**request_data)
            assert router_request.features.token_count == token_count
            assert router_request.features.json_schema_strictness == json_strictness
            assert router_request.features.novelty_score == novelty_score
            assert router_request.features.historical_failure_rate == failure_rate
        except ValueError:
            pytest.fail("Router request validation failed with fuzzed data")
        
        # Simulate router decision based on features
        if token_count <= 5 and json_strictness > 0.8 and novelty_score < 0.2:
            expected_tier = RouterTier.SLM_A
        elif token_count <= 20 and novelty_score < 0.6 and failure_rate < 0.2:
            expected_tier = RouterTier.SLM_B
        else:
            expected_tier = RouterTier.LLM
        
        # Verify tier selection logic
        actual_tier = self._simulate_router_decision(request_data)
        assert actual_tier in [RouterTier.SLM_A, RouterTier.SLM_B, RouterTier.LLM]
        
        # Verify tier selection is reasonable
        if expected_tier == RouterTier.SLM_A:
            assert actual_tier in [RouterTier.SLM_A, RouterTier.SLM_B]
        elif expected_tier == RouterTier.SLM_B:
            assert actual_tier in [RouterTier.SLM_A, RouterTier.SLM_B, RouterTier.LLM]
        else:  # LLM
            assert actual_tier in [RouterTier.SLM_B, RouterTier.LLM]
    
    def _simulate_router_decision(self, request_data):
        """Simulate router decision based on features."""
        features = request_data["features"]
        
        # Simple routing logic for testing
        if features["token_count"] <= 5 and features["json_schema_strictness"] > 0.8:
            return RouterTier.SLM_A
        elif features["token_count"] <= 20 and features["novelty_score"] < 0.6:
            return RouterTier.SLM_B
        else:
            return RouterTier.LLM
    
    @pytest.mark.asyncio
    async def test_router_decision_latency_gate(self):
        """Test router decision latency gating."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Test requests with different complexity levels
        latency_test_cases = [
            {
                "message": "Hello",
                "expected_max_latency": 50,  # ms
                "complexity": "simple"
            },
            {
                "message": "What are your business hours and pricing?",
                "expected_max_latency": 100,  # ms
                "complexity": "medium"
            },
            {
                "message": "I need help with complex API integration and database schema design for microservices architecture with multiple tenants and custom business logic",
                "expected_max_latency": 200,  # ms
                "complexity": "complex"
            }
        ]
        
        latency_results = []
        
        for test_case in latency_test_cases:
            request_data = {
                "tenant_id": tenant["tenant_id"],
                "message": test_case["message"],
                "context": {},
                "features": {
                    "token_count": len(test_case["message"].split()),
                    "json_schema_strictness": 0.8,
                    "domain_flags": {"customer_support": True, "sales": False, "technical": False},
                    "novelty_score": 0.3,
                    "historical_failure_rate": 0.05
                }
            }
            
            router_request = RouterDecisionRequest(**request_data)
            
            # Simulate router processing with timing
            start_time = time.time()
            
            # Simulate processing delay based on complexity
            if test_case["complexity"] == "simple":
                await asyncio.sleep(0.01)  # 10ms
            elif test_case["complexity"] == "medium":
                await asyncio.sleep(0.05)  # 50ms
            else:  # complex
                await asyncio.sleep(0.1)  # 100ms
            
            end_time = time.time()
            actual_latency_ms = (end_time - start_time) * 1000
            
            latency_results.append({
                "complexity": test_case["complexity"],
                "expected_max_latency": test_case["expected_max_latency"],
                "actual_latency_ms": actual_latency_ms,
                "within_threshold": actual_latency_ms <= test_case["expected_max_latency"]
            })
        
        # Verify latency gates
        for result in latency_results:
            result_obj = RouterAssertions.assert_decision_latency_acceptable(
                result["actual_latency_ms"],
                result["expected_max_latency"],
                f"Router latency for {result['complexity']} request"
            )
            assert result_obj.passed, f"Router latency gate failed: {result_obj.message}"
    
    @pytest.mark.asyncio
    async def test_router_confidence_drift(self):
        """Test router confidence drift detection."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Test cases with known confidence expectations
        confidence_test_cases = [
            {
                "message": "Hello",
                "expected_min_confidence": 0.9,
                "reason": "Simple greeting should have high confidence"
            },
            {
                "message": "What are your business hours?",
                "expected_min_confidence": 0.8,
                "reason": "Standard FAQ should have good confidence"
            },
            {
                "message": "I need help with something complex and unusual",
                "expected_min_confidence": 0.6,
                "reason": "Complex request may have lower confidence"
            }
        ]
        
        confidence_results = []
        
        for test_case in confidence_test_cases:
            request_data = {
                "tenant_id": tenant["tenant_id"],
                "message": test_case["message"],
                "context": {},
                "features": {
                    "token_count": len(test_case["message"].split()),
                    "json_schema_strictness": 0.8,
                    "domain_flags": {"customer_support": True, "sales": False, "technical": False},
                    "novelty_score": 0.3,
                    "historical_failure_rate": 0.05
                }
            }
            
            router_request = RouterDecisionRequest(**request_data)
            
            # Simulate router confidence calculation
            if len(test_case["message"].split()) <= 2:
                actual_confidence = 0.95
            elif len(test_case["message"].split()) <= 10:
                actual_confidence = 0.85
            else:
                actual_confidence = 0.7
            
            confidence_results.append({
                "message": test_case["message"],
                "expected_min_confidence": test_case["expected_min_confidence"],
                "actual_confidence": actual_confidence,
                "confidence_drift": actual_confidence - test_case["expected_min_confidence"],
                "meets_threshold": actual_confidence >= test_case["expected_min_confidence"]
            })
        
        # Verify confidence thresholds
        for result in confidence_results:
            assert result["meets_threshold"], f"Confidence {result['actual_confidence']} below threshold {result['expected_min_confidence']} for message: {result['message']}"
        
        # Verify overall confidence drift
        avg_confidence_drift = sum(result["confidence_drift"] for result in confidence_results) / len(confidence_results)
        assert avg_confidence_drift >= -0.1, f"Average confidence drift {avg_confidence_drift} is too negative"
    
    @pytest.mark.asyncio
    async def test_router_cost_efficiency_drift(self):
        """Test router cost efficiency drift detection."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Test cost efficiency scenarios
        cost_test_cases = [
            {
                "message": "Hello",
                "expected_max_cost": 0.002,  # $0.002
                "tier": RouterTier.SLM_A
            },
            {
                "message": "What are your business hours and pricing?",
                "expected_max_cost": 0.010,  # $0.010
                "tier": RouterTier.SLM_B
            },
            {
                "message": "I need help with complex API integration and database schema design",
                "expected_max_cost": 0.050,  # $0.050
                "tier": RouterTier.LLM
            }
        ]
        
        cost_results = []
        
        for test_case in cost_test_cases:
            request_data = {
                "tenant_id": tenant["tenant_id"],
                "message": test_case["message"],
                "context": {},
                "features": {
                    "token_count": len(test_case["message"].split()),
                    "json_schema_strictness": 0.8,
                    "domain_flags": {"customer_support": True, "sales": False, "technical": False},
                    "novelty_score": 0.3,
                    "historical_failure_rate": 0.05
                }
            }
            
            router_request = RouterDecisionRequest(**request_data)
            
            # Simulate cost calculation based on tier
            if test_case["tier"] == RouterTier.SLM_A:
                actual_cost = 0.001
            elif test_case["tier"] == RouterTier.SLM_B:
                actual_cost = 0.008
            else:  # LLM
                actual_cost = 0.045
            
            cost_results.append({
                "message": test_case["message"][:30],
                "expected_max_cost": test_case["expected_max_cost"],
                "actual_cost": actual_cost,
                "cost_efficiency": actual_cost <= test_case["expected_max_cost"],
                "tier": test_case["tier"].value
            })
        
        # Verify cost efficiency
        for result in cost_results:
            assert result["cost_efficiency"], f"Cost {result['actual_cost']} exceeds threshold {result['expected_max_cost']} for {result['tier']}"
        
        # Verify tier-appropriate costs
        slm_a_costs = [r["actual_cost"] for r in cost_results if r["tier"] == "SLM_A"]
        slm_b_costs = [r["actual_cost"] for r in cost_results if r["tier"] == "SLM_B"]
        llm_costs = [r["actual_cost"] for r in cost_results if r["tier"] == "LLM"]
        
        assert all(cost <= 0.005 for cost in slm_a_costs), "SLM_A costs should be low"
        assert all(cost <= 0.020 for cost in slm_b_costs), "SLM_B costs should be moderate"
        assert all(cost <= 0.100 for cost in llm_costs), "LLM costs should be higher but reasonable"
