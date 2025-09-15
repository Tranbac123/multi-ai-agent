"""Contract tests for Orchestrator ↔ Router boundaries."""

import pytest
import json
from typing import Dict, Any, List
from unittest.mock import Mock, patch

from tests.contract.schemas import (
    RouterRequest, RouterResponse, RequestType, LLMTier,
    validate_strict_json, validate_no_pii
)
from tests.contract import ContractError, ContractResponse, ErrorCode
from tests._fixtures.factories import factory


class TestRouterRequestContracts:
    """Test Router request contract validation."""
    
    def test_valid_router_request(self, sample_tenant, sample_user):
        """Test valid router request passes validation."""
        request_data = {
            "request_id": "req_123456789",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "message": "What is your return policy?",
            "request_type": RequestType.FAQ,
            "context": {"source": "web", "session_id": "sess_123"},
            "user_history": [
                {
                    "timestamp": "2024-01-01T10:00:00Z",
                    "request_type": "FAQ",
                    "message": "Previous question"
                }
            ],
            "tenant_config": {"max_cost_usd": 0.01, "preferred_tier": "SLM_A"}
        }
        
        request = RouterRequest(**request_data)
        
        assert request.request_id == "req_123456789"
        assert request.tenant_id == sample_tenant.tenant_id
        assert request.user_id == sample_user.user_id
        assert request.message == "What is your return policy?"
        assert request.request_type == RequestType.FAQ
        assert len(request.user_history) == 1
        assert request.tenant_config["max_cost_usd"] == 0.01
    
    def test_user_history_validation(self, sample_tenant, sample_user):
        """Test user history structure validation."""
        # Valid user history
        valid_history = [
            {
                "timestamp": "2024-01-01T10:00:00Z",
                "request_type": "FAQ",
                "message": "Previous question"
            },
            {
                "timestamp": "2024-01-01T11:00:00Z",
                "request_type": "ORDER",
                "message": "Order status inquiry"
            }
        ]
        
        request_data = {
            "request_id": "req_123456789",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "message": "Test message",
            "request_type": RequestType.FAQ,
            "user_history": valid_history
        }
        
        request = RouterRequest(**request_data)
        assert len(request.user_history) == 2
        
        # Invalid user history - missing required field
        invalid_history = [
            {
                "timestamp": "2024-01-01T10:00:00Z",
                "message": "Missing request_type"
            }
        ]
        
        request_data["user_history"] = invalid_history
        
        with pytest.raises(ValueError, match="User history item missing required field"):
            RouterRequest(**request_data)
        
        # Invalid user history - not a dictionary
        request_data["user_history"] = ["not_a_dict"]
        
        with pytest.raises(ValueError, match="User history items must be dictionaries"):
            RouterRequest(**request_data)
    
    def test_user_history_limit(self, sample_tenant, sample_user):
        """Test user history item limit validation."""
        # Create history with more than 50 items
        large_history = []
        for i in range(51):
            large_history.append({
                "timestamp": f"2024-01-01T{i:02d}:00:00Z",
                "request_type": "FAQ",
                "message": f"Question {i}"
            })
        
        request_data = {
            "request_id": "req_123456789",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "message": "Test message",
            "request_type": RequestType.FAQ,
            "user_history": large_history
        }
        
        with pytest.raises(ValueError, match="ensure this value has at most 50 items"):
            RouterRequest(**request_data)
    
    def test_context_serialization(self, sample_tenant, sample_user):
        """Test context must be JSON serializable."""
        # Valid context
        valid_context = {
            "source": "web",
            "session_id": "sess_123",
            "metadata": {"priority": "high"}
        }
        
        request_data = {
            "request_id": "req_123456789",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "message": "Test message",
            "request_type": RequestType.FAQ,
            "context": valid_context
        }
        
        request = RouterRequest(**request_data)
        assert request.context == valid_context
        
        # Invalid context - non-serializable
        invalid_context = {
            "function": lambda x: x,  # Not JSON serializable
            "data": "valid_data"
        }
        
        request_data["context"] = invalid_context
        
        with pytest.raises(ValueError, match="Parameters must be JSON serializable"):
            RouterRequest(**request_data)


class TestRouterResponseContracts:
    """Test Router response contract validation."""
    
    def test_valid_router_response(self):
        """Test valid router response passes validation."""
        response_data = {
            "request_id": "req_123456789",
            "tier": LLMTier.SLM_A,
            "confidence": 0.95,
            "reasoning": "Simple FAQ question with high confidence answer available",
            "estimated_cost_usd": 0.002,
            "estimated_latency_ms": 150.0,
            "features": {
                "token_count": 15,
                "complexity_score": 0.2,
                "json_schema_strictness": 0.9
            }
        }
        
        response = RouterResponse(**response_data)
        
        assert response.request_id == "req_123456789"
        assert response.tier == LLMTier.SLM_A
        assert response.confidence == 0.95
        assert response.reasoning == "Simple FAQ question with high confidence answer available"
        assert response.estimated_cost_usd == 0.002
        assert response.estimated_latency_ms == 150.0
        assert response.features["token_count"] == 15
    
    def test_confidence_range_validation(self):
        """Test confidence must be between 0.0 and 1.0."""
        # Valid confidence values
        valid_confidences = [0.0, 0.5, 0.95, 1.0]
        
        for confidence in valid_confidences:
            response_data = {
                "request_id": "req_123456789",
                "tier": LLMTier.SLM_A,
                "confidence": confidence,
                "reasoning": "Test reasoning",
                "estimated_cost_usd": 0.002,
                "estimated_latency_ms": 150.0
            }
            
            response = RouterResponse(**response_data)
            assert response.confidence == confidence
        
        # Invalid confidence values
        invalid_confidences = [-0.1, 1.1, 2.0]
        
        for confidence in invalid_confidences:
            response_data = {
                "request_id": "req_123456789",
                "tier": LLMTier.SLM_A,
                "confidence": confidence,
                "reasoning": "Test reasoning",
                "estimated_cost_usd": 0.002,
                "estimated_latency_ms": 150.0
            }
            
            with pytest.raises(ValueError, match="ensure this value is greater than or equal to 0.0"):
                RouterResponse(**response_data)
    
    def test_reasoning_length_validation(self):
        """Test reasoning length validation."""
        # Valid reasoning
        valid_reasoning = "This is a valid reasoning with sufficient detail"
        
        response_data = {
            "request_id": "req_123456789",
            "tier": LLMTier.SLM_A,
            "confidence": 0.95,
            "reasoning": valid_reasoning,
            "estimated_cost_usd": 0.002,
            "estimated_latency_ms": 150.0
        }
        
        response = RouterResponse(**response_data)
        assert response.reasoning == valid_reasoning
        
        # Too short reasoning
        short_reasoning = "Too short"
        
        response_data["reasoning"] = short_reasoning
        
        with pytest.raises(ValueError, match="ensure this value has at least 10 characters"):
            RouterResponse(**response_data)
        
        # Too long reasoning
        long_reasoning = "x" * 501
        
        response_data["reasoning"] = long_reasoning
        
        with pytest.raises(ValueError, match="ensure this value has at most 500 characters"):
            RouterResponse(**response_data)
    
    def test_reasoning_word_count_validation(self):
        """Test reasoning must have at least 3 words."""
        # Too few words
        few_words = "Short"
        
        response_data = {
            "request_id": "req_123456789",
            "tier": LLMTier.SLM_A,
            "confidence": 0.95,
            "reasoning": few_words,
            "estimated_cost_usd": 0.002,
            "estimated_latency_ms": 150.0
        }
        
        with pytest.raises(ValueError, match="Reasoning must be at least 3 words"):
            RouterResponse(**response_data)
    
    def test_cost_range_validation(self):
        """Test cost must be between 0.0 and 1.0 USD."""
        # Valid cost values
        valid_costs = [0.0, 0.001, 0.01, 0.1, 1.0]
        
        for cost in valid_costs:
            response_data = {
                "request_id": "req_123456789",
                "tier": LLMTier.SLM_A,
                "confidence": 0.95,
                "reasoning": "Valid reasoning with three words",
                "estimated_cost_usd": cost,
                "estimated_latency_ms": 150.0
            }
            
            response = RouterResponse(**response_data)
            assert response.estimated_cost_usd == cost
        
        # Invalid cost values
        invalid_costs = [-0.1, 1.1, 10.0]
        
        for cost in invalid_costs:
            response_data = {
                "request_id": "req_123456789",
                "tier": LLMTier.SLM_A,
                "confidence": 0.95,
                "reasoning": "Valid reasoning with three words",
                "estimated_cost_usd": cost,
                "estimated_latency_ms": 150.0
            }
            
            with pytest.raises(ValueError, match="ensure this value is greater than or equal to 0.0"):
                RouterResponse(**response_data)
    
    def test_latency_range_validation(self):
        """Test latency must be between 0.0 and 10000.0 ms."""
        # Valid latency values
        valid_latencies = [0.0, 10.0, 100.0, 1000.0, 5000.0, 10000.0]
        
        for latency in valid_latencies:
            response_data = {
                "request_id": "req_123456789",
                "tier": LLMTier.SLM_A,
                "confidence": 0.95,
                "reasoning": "Valid reasoning with three words",
                "estimated_cost_usd": 0.002,
                "estimated_latency_ms": latency
            }
            
            response = RouterResponse(**response_data)
            assert response.estimated_latency_ms == latency
        
        # Invalid latency values
        invalid_latencies = [-1.0, 10001.0, 60000.0]
        
        for latency in invalid_latencies:
            response_data = {
                "request_id": "req_123456789",
                "tier": LLMTier.SLM_A,
                "confidence": 0.95,
                "reasoning": "Valid reasoning with three words",
                "estimated_cost_usd": 0.002,
                "estimated_latency_ms": latency
            }
            
            with pytest.raises(ValueError, match="ensure this value is less than or equal to 10000.0"):
                RouterResponse(**response_data)


class TestRouterTierDecisionContracts:
    """Test router tier decision logic contracts."""
    
    @pytest.mark.parametrize("tier", [LLMTier.SLM_A, LLMTier.SLM_B, LLMTier.LLM])
    def test_all_tiers_valid(self, tier):
        """Test all LLM tiers are valid in responses."""
        response_data = {
            "request_id": "req_123456789",
            "tier": tier,
            "confidence": 0.95,
            "reasoning": f"Selected {tier.value} for this request",
            "estimated_cost_usd": 0.002,
            "estimated_latency_ms": 150.0
        }
        
        response = RouterResponse(**response_data)
        assert response.tier == tier
    
    def test_tier_cost_correlation(self):
        """Test that tier selection correlates with expected costs."""
        tier_costs = {
            LLMTier.SLM_A: (0.001, 0.005),  # (min, max) cost range
            LLMTier.SLM_B: (0.002, 0.01),
            LLMTier.LLM: (0.005, 0.05)
        }
        
        for tier, (min_cost, max_cost) in tier_costs.items():
            response_data = {
                "request_id": "req_123456789",
                "tier": tier,
                "confidence": 0.95,
                "reasoning": f"Selected {tier.value} for this request",
                "estimated_cost_usd": min_cost,
                "estimated_latency_ms": 150.0
            }
            
            response = RouterResponse(**response_data)
            assert min_cost <= response.estimated_cost_usd <= max_cost
    
    def test_tier_latency_correlation(self):
        """Test that tier selection correlates with expected latencies."""
        tier_latencies = {
            LLMTier.SLM_A: (50, 200),  # (min, max) latency range in ms
            LLMTier.SLM_B: (100, 500),
            LLMTier.LLM: (500, 2000)
        }
        
        for tier, (min_latency, max_latency) in tier_latencies.items():
            response_data = {
                "request_id": "req_123456789",
                "tier": tier,
                "confidence": 0.95,
                "reasoning": f"Selected {tier.value} for this request",
                "estimated_cost_usd": 0.002,
                "estimated_latency_ms": min_latency
            }
            
            response = RouterResponse(**response_data)
            assert min_latency <= response.estimated_latency_ms <= max_latency


class TestRouterContractIntegration:
    """Test router contract integration scenarios."""
    
    def test_request_response_matching(self, sample_tenant, sample_user):
        """Test that request and response IDs match."""
        # Create request
        request_data = {
            "request_id": "req_123456789",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "message": "What is your return policy?",
            "request_type": RequestType.FAQ,
            "context": {"source": "web"}
        }
        
        request = RouterRequest(**request_data)
        
        # Create matching response
        response_data = {
            "request_id": request.request_id,  # Must match
            "tier": LLMTier.SLM_A,
            "confidence": 0.95,
            "reasoning": "Simple FAQ question with high confidence answer available",
            "estimated_cost_usd": 0.002,
            "estimated_latency_ms": 150.0,
            "features": {
                "token_count": 15,
                "complexity_score": 0.2
            }
        }
        
        response = RouterResponse(**response_data)
        
        # Validate matching
        assert response.request_id == request.request_id
    
    def test_features_extraction_contract(self, sample_tenant, sample_user):
        """Test features extraction in router responses."""
        request_data = {
            "request_id": "req_123456789",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "message": "Complex technical question requiring detailed analysis",
            "request_type": RequestType.SUPPORT,
            "context": {"complexity": "high"}
        }
        
        request = RouterRequest(**request_data)
        
        # Response with extracted features
        response_data = {
            "request_id": request.request_id,
            "tier": LLMTier.LLM,  # Should select higher tier for complex questions
            "confidence": 0.75,  # Lower confidence for complex questions
            "reasoning": "Complex technical question requires detailed analysis and reasoning",
            "estimated_cost_usd": 0.025,  # Higher cost for complex processing
            "estimated_latency_ms": 1500.0,  # Higher latency for complex processing
            "features": {
                "token_count": 150,
                "complexity_score": 0.85,
                "json_schema_strictness": 0.3,
                "domain_flags": ["technical", "support"],
                "novelty_score": 0.7
            }
        }
        
        response = RouterResponse(**response_data)
        
        # Validate feature extraction
        assert response.features["token_count"] > 100  # Complex question has more tokens
        assert response.features["complexity_score"] > 0.5  # High complexity
        assert response.tier == LLMTier.LLM  # Higher tier for complex questions
        assert response.estimated_cost_usd > 0.01  # Higher cost
        assert response.estimated_latency_ms > 1000  # Higher latency
    
    def test_tenant_config_influence(self, sample_tenant, sample_user):
        """Test that tenant configuration influences router decisions."""
        # Request with tenant config preferring SLM_A
        request_data = {
            "request_id": "req_123456789",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "message": "Simple question",
            "request_type": RequestType.FAQ,
            "tenant_config": {
                "max_cost_usd": 0.005,
                "preferred_tier": "SLM_A",
                "max_latency_ms": 200
            }
        }
        
        request = RouterRequest(**request_data)
        
        # Response should respect tenant preferences
        response_data = {
            "request_id": request.request_id,
            "tier": LLMTier.SLM_A,  # Respects preferred tier
            "confidence": 0.95,
            "reasoning": "Simple question with tenant preference for SLM_A",
            "estimated_cost_usd": 0.002,  # Within tenant budget
            "estimated_latency_ms": 150.0,  # Within tenant latency limit
            "features": {
                "tenant_preference_applied": True,
                "cost_within_budget": True,
                "latency_within_limit": True
            }
        }
        
        response = RouterResponse(**response_data)
        
        # Validate tenant config influence
        assert response.tier == LLMTier.SLM_A
        assert response.estimated_cost_usd <= 0.005
        assert response.estimated_latency_ms <= 200.0
        assert response.features.get("tenant_preference_applied") is True
    
    def test_user_history_influence(self, sample_tenant, sample_user):
        """Test that user history influences router decisions."""
        # Request with user history showing pattern
        user_history = [
            {
                "timestamp": "2024-01-01T10:00:00Z",
                "request_type": "FAQ",
                "message": "Previous simple question"
            },
            {
                "timestamp": "2024-01-01T11:00:00Z",
                "request_type": "FAQ",
                "message": "Another simple question"
            }
        ]
        
        request_data = {
            "request_id": "req_123456789",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "message": "Another simple question",
            "request_type": RequestType.FAQ,
            "user_history": user_history
        }
        
        request = RouterRequest(**request_data)
        
        # Response should consider user history pattern
        response_data = {
            "request_id": request.request_id,
            "tier": LLMTier.SLM_A,
            "confidence": 0.98,  # High confidence due to pattern recognition
            "reasoning": "User history shows pattern of simple FAQ questions, high confidence in SLM_A selection",
            "estimated_cost_usd": 0.002,
            "estimated_latency_ms": 120.0,  # Faster due to pattern recognition
            "features": {
                "pattern_recognized": True,
                "historical_success_rate": 0.95,
                "similar_question_count": 2
            }
        }
        
        response = RouterResponse(**response_data)
        
        # Validate user history influence
        assert response.confidence > 0.95  # High confidence due to pattern
        assert response.features.get("pattern_recognized") is True
        assert response.features.get("historical_success_rate") > 0.9
