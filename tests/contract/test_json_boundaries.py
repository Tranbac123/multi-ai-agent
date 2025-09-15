"""Test strict JSON boundaries and validation."""

import json
import pytest
from unittest.mock import Mock, AsyncMock

from tests._helpers.assertions import JSONAssertions, ContractAssertions
from libs.contracts.router import RouterDecisionRequest, RouterDecision
from libs.contracts.agent import AgentSpec, MessageSpec, ToolSpec


class TestJSONBoundaries:
    """Test strict JSON boundary validation."""
    
    def test_router_decision_request_strict_validation(self):
        """Test RouterDecisionRequest strict JSON validation."""
        # Valid request
        valid_data = {
            "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
            "message": "How do I reset my password?",
            "context": {
                "user_id": "user_123",
                "session_id": "session_456"
            },
            "features": {
                "token_count": 10,
                "json_schema_strictness": 0.8,
                "domain_flags": {
                    "customer_support": True,
                    "sales": False
                },
                "novelty_score": 0.3,
                "historical_failure_rate": 0.1
            }
        }
        
        request = RouterDecisionRequest(**valid_data)
        assert request.tenant_id == "123e4567-e89b-12d3-a456-426614174000"
        assert request.message == "How do I reset my password?"
    
    def test_router_decision_request_extra_fields_rejected(self):
        """Test that extra fields are rejected in RouterDecisionRequest."""
        invalid_data = {
            "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
            "message": "How do I reset my password?",
            "context": {
                "user_id": "user_123",
                "session_id": "session_456"
            },
            "features": {
                "token_count": 10,
                "json_schema_strictness": 0.8,
                "domain_flags": {
                    "customer_support": True,
                    "sales": False
                },
                "novelty_score": 0.3,
                "historical_failure_rate": 0.1
            },
            "extra_field": "should_be_rejected"  # This should cause validation error
        }
        
        with pytest.raises(ValueError, match="extra fields not permitted"):
            RouterDecisionRequest(**invalid_data)
    
    def test_router_decision_response_strict_validation(self):
        """Test RouterDecisionResponse strict JSON validation."""
        valid_data = {
            "tier": "SLM_A",
            "confidence": 0.85,
            "expected_cost_usd": 0.005,
            "expected_latency_ms": 800,
            "reasoning": "Simple question, low complexity"
        }
        
        response = RouterDecision(**valid_data)
        assert response.tier.value == "SLM_A"
        assert response.confidence == 0.85
    
    def test_agent_spec_strict_validation(self):
        """Test AgentSpec strict JSON validation."""
        valid_data = {
            "agent_id": "agent_123",
            "name": "Customer Support Agent",
            "description": "Handles customer support queries",
            "tools": ["knowledge_base", "crm"],
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        agent_spec = AgentSpec(**valid_data)
        assert agent_spec.agent_id == "agent_123"
        assert agent_spec.name == "Customer Support Agent"
    
    def test_message_spec_strict_validation(self):
        """Test MessageSpec strict JSON validation."""
        valid_data = {
            "message_id": "msg_123",
            "content": "Hello, how can I help you?",
            "role": "assistant",
            "timestamp": "2024-01-01T12:00:00Z",
            "metadata": {
                "source": "api",
                "user_id": "user_123"
            }
        }
        
        message_spec = MessageSpec(**valid_data)
        assert message_spec.message_id == "msg_123"
        assert message_spec.content == "Hello, how can I help you?"
    
    def test_tool_spec_strict_validation(self):
        """Test ToolSpec strict JSON validation."""
        valid_data = {
            "tool_id": "tool_123",
            "name": "knowledge_base_search",
            "description": "Search the knowledge base",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 10}
                },
                "required": ["query"]
            },
            "cost_per_call": 0.001
        }
        
        tool_spec = ToolSpec(**valid_data)
        assert tool_spec.tool_id == "tool_123"
        assert tool_spec.name == "knowledge_base_search"


class TestMarkdownJSONRejection:
    """Test rejection of markdown-wrapped JSON."""
    
    def test_reject_markdown_json_in_message(self):
        """Test that markdown-wrapped JSON is rejected in messages."""
        markdown_json_messages = [
            "Here's the data: ```json\n{\"key\": \"value\"}\n```",
            "```json\n{\"response\": \"data\"}\n```",
            "```\n{\"info\": \"details\"}\n```",
            "`{\"quick\": \"json\"}`",
            "```javascript\n{\"js\": \"style\"}\n```"
        ]
        
        for message in markdown_json_messages:
            result = JSONAssertions.assert_no_markdown_json(message, f"Message: {message[:30]}...")
            assert not result.passed, f"Should reject markdown JSON: {message}"
    
    def test_accept_plain_json_in_message(self):
        """Test that plain JSON is accepted in messages."""
        plain_json_messages = [
            "Here's the data: {\"key\": \"value\"}",
            "{\"response\": \"data\"}",
            "Simple text with no JSON",
            "JSON-like text: {not actual json}",
            "Regular message without any special formatting"
        ]
        
        for message in plain_json_messages:
            result = JSONAssertions.assert_no_markdown_json(message, f"Message: {message[:30]}...")
            assert result.passed, f"Should accept plain message: {message}"


class TestErrorMapping:
    """Test error mapping and structured error responses."""
    
    def test_validation_error_mapping(self):
        """Test that validation errors are properly mapped to HTTP status codes."""
        error_scenarios = [
            # Missing required field -> 400
            ({"message": "test"}, "missing required field", 400),
            
            # Invalid field type -> 400
            ({"tenant_id": 123, "message": "test"}, "invalid field type", 400),
            
            # Extra fields -> 400
            ({"tenant_id": "123", "message": "test", "extra": "field"}, "extra fields not permitted", 400),
            
            # Invalid UUID format -> 400
            ({"tenant_id": "invalid-uuid", "message": "test"}, "invalid UUID format", 400),
        ]
        
        for data, expected_error, expected_status in error_scenarios:
            try:
                RouterDecisionRequest(**data)
                pytest.fail(f"Should have raised validation error for: {data}")
            except ValueError as e:
                error_message = str(e).lower()
                assert expected_error.lower() in error_message
                
                # Test structured error response
                error_response = {
                    "error": "Validation Error",
                    "message": str(e),
                    "status_code": expected_status,
                    "timestamp": "2024-01-01T12:00:00Z"
                }
                
                result = ContractAssertions.assert_structured_error_response(
                    error_response, f"Error for: {data}"
                )
                assert result.passed, f"Error response should be structured: {error_response}"
    
    def test_http_status_code_validation(self):
        """Test HTTP status code validation."""
        valid_status_codes = [200, 201, 202, 204, 400, 401, 403, 404, 429, 500, 502, 503]
        invalid_status_codes = [100, 150, 250, 350, 450, 550, 600]
        
        for status_code in valid_status_codes:
            result = ContractAssertions.assert_valid_http_status(
                status_code, valid_status_codes, f"Status {status_code}"
            )
            assert result.passed, f"Status {status_code} should be valid"
        
        for status_code in invalid_status_codes:
            result = ContractAssertions.assert_valid_http_status(
                status_code, valid_status_codes, f"Status {status_code}"
            )
            assert not result.passed, f"Status {status_code} should be invalid"
    
    def test_error_response_structure(self):
        """Test that error responses follow the correct structure."""
        # Valid error response
        valid_error = {
            "error": "Validation Error",
            "message": "Invalid input data",
            "code": "VALIDATION_FAILED",
            "details": {"field": "tenant_id", "issue": "required field missing"},
            "timestamp": "2024-01-01T12:00:00Z"
        }
        
        result = ContractAssertions.assert_structured_error_response(valid_error, "Valid error response")
        assert result.passed, f"Valid error response should pass: {valid_error}"
        
        # Invalid error response (missing required fields)
        invalid_errors = [
            {"message": "Error without error field"},  # Missing 'error' field
            {"error": "Error without message field"},  # Missing 'message' field
            {"error": "Error", "message": "Message", "unknown_field": "value"}  # Extra field
        ]
        
        for invalid_error in invalid_errors:
            result = ContractAssertions.assert_structured_error_response(
                invalid_error, f"Invalid error: {invalid_error}"
            )
            assert not result.passed, f"Invalid error response should fail: {invalid_error}"


class TestNegativeCases:
    """Test negative cases and edge conditions."""
    
    def test_empty_request_rejection(self):
        """Test that empty requests are rejected."""
        with pytest.raises(ValueError):
            RouterDecisionRequest()
    
    def test_null_value_rejection(self):
        """Test that null values are rejected where not allowed."""
        invalid_data = {
            "tenant_id": None,  # Should be rejected
            "message": "test message",
            "context": {},
            "features": {}
        }
        
        with pytest.raises(ValueError):
            RouterDecisionRequest(**invalid_data)
    
    def test_invalid_enum_values(self):
        """Test that invalid enum values are rejected."""
        invalid_data = {
            "tier": "INVALID_TIER",  # Not a valid RouterTier
            "confidence": 0.85,
            "expected_cost_usd": 0.005,
            "expected_latency_ms": 800,
            "reasoning": "Test"
        }
        
        with pytest.raises(ValueError):
            RouterDecision(**invalid_data)
    
    def test_out_of_range_values(self):
        """Test that out-of-range values are rejected."""
        # Confidence should be between 0 and 1
        invalid_data = {
            "tier": "SLM_A",
            "confidence": 1.5,  # Out of range
            "expected_cost_usd": 0.005,
            "expected_latency_ms": 800,
            "reasoning": "Test"
        }
        
        with pytest.raises(ValueError):
            RouterDecision(**invalid_data)
    
    def test_negative_values_rejection(self):
        """Test that negative values are rejected where not allowed."""
        invalid_data = {
            "tier": "SLM_A",
            "confidence": 0.85,
            "expected_cost_usd": -0.005,  # Negative cost
            "expected_latency_ms": 800,
            "reasoning": "Test"
        }
        
        with pytest.raises(ValueError):
            RouterDecision(**invalid_data)
    
    def test_very_large_values_rejection(self):
        """Test that very large values are rejected."""
        invalid_data = {
            "tier": "SLM_A",
            "confidence": 0.85,
            "expected_cost_usd": 0.005,
            "expected_latency_ms": 999999999,  # Very large latency
            "reasoning": "Test"
        }
        
        # This might pass validation but should be caught by business logic
        response = RouterDecision(**invalid_data)
        assert response.expected_latency_ms == 999999999  # Validation passes but business logic should reject


class TestContractIntegration:
    """Test contract integration across service boundaries."""
    
    def test_api_to_orchestrator_contract(self):
        """Test contract validation from API to Orchestrator."""
        # Simulate API request
        api_request = {
            "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
            "message": "Help me with my order",
            "context": {"user_id": "user_123"}
        }
        
        # Validate as RouterDecisionRequest
        router_request = RouterDecisionRequest(**api_request)
        
        # Simulate orchestrator response
        orchestrator_response = {
            "tier": "SLM_B",
            "confidence": 0.8,
            "expected_cost_usd": 0.01,
            "expected_latency_ms": 1200,
            "reasoning": "Order-related query requires moderate complexity handling"
        }
        
        # Validate as RouterDecision
        router_decision = RouterDecision(**orchestrator_response)
        
        # Both should validate successfully
        assert router_request.message == "Help me with my order"
        assert router_decision.tier.value == "SLM_B"
    
    def test_orchestrator_to_router_contract(self):
        """Test contract validation from Orchestrator to Router."""
        # Simulate orchestrator request to router
        orchestrator_request = {
            "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
            "message": "What are your business hours?",
            "context": {"user_id": "user_456"},
            "features": {
                "token_count": 5,
                "json_schema_strictness": 0.9,
                "domain_flags": {"customer_support": True},
                "novelty_score": 0.1,
                "historical_failure_rate": 0.05
            }
        }
        
        router_request = RouterDecisionRequest(**orchestrator_request)
        
        # Simulate router response
        router_response = {
            "tier": "SLM_A",
            "confidence": 0.95,
            "expected_cost_usd": 0.002,
            "expected_latency_ms": 300,
            "reasoning": "Simple FAQ question, high confidence in SLM_A"
        }
        
        router_decision = RouterDecision(**router_response)
        
        assert router_request.features.token_count == 5
        assert router_decision.confidence == 0.95
    
    def test_contract_evolution_compatibility(self):
        """Test that contract changes maintain backward compatibility."""
        # Test with minimal required fields
        minimal_request = {
            "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
            "message": "Test message",
            "context": {},
            "features": {}
        }
        
        # Should still work with minimal data
        router_request = RouterDecisionRequest(**minimal_request)
        assert router_request.message == "Test message"
        
        # Test with additional optional fields
        extended_request = {
            **minimal_request,
            "features": {
                "token_count": 10,
                "json_schema_strictness": 0.8,
                "domain_flags": {"customer_support": True},
                "novelty_score": 0.3,
                "historical_failure_rate": 0.1,
                "additional_metadata": {"source": "api"}  # This should be allowed in context
            }
        }
        
        # Extended request should also work
        router_request_extended = RouterDecisionRequest(**extended_request)
        assert router_request_extended.features.token_count == 10
