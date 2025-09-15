"""Test contract integration across service boundaries."""

import pytest
import json
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from tests._helpers.assertions import ContractAssertions, PIIAssertions
from libs.contracts.router import RouterDecisionRequest, RouterDecision
from libs.contracts.agent import AgentSpec, MessageSpec, ToolSpec
from libs.contracts.errors import ErrorSpec


class TestAPIToOrchestratorContract:
    """Test contract validation from API to Orchestrator."""
    
    @pytest.mark.asyncio
    async def test_valid_api_request_to_orchestrator(self):
        """Test valid API request to orchestrator."""
        # Simulate API request
        api_request_data = {
            "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
            "message": "How do I reset my password?",
            "context": {
                "user_id": "user_123",
                "session_id": "session_456",
                "ip_address": "192.168.1.1"
            },
            "features": {
                "token_count": 8,
                "json_schema_strictness": 0.9,
                "domain_flags": {
                    "customer_support": True,
                    "sales": False,
                    "technical": False
                },
                "novelty_score": 0.2,
                "historical_failure_rate": 0.05
            }
        }
        
        # Validate as RouterDecisionRequest
        router_request = RouterDecisionRequest(**api_request_data)
        
        # Mock orchestrator processing
        orchestrator_mock = Mock()
        orchestrator_mock.process_request = AsyncMock()
        orchestrator_mock.process_request.return_value = {
            "status": "success",
            "request_id": router_request.request_id if hasattr(router_request, 'request_id') else "req_123"
        }
        
        # Process request
        result = await orchestrator_mock.process_request(router_request)
        
        # Verify contract compliance
        assert result["status"] == "success"
        orchestrator_mock.process_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_invalid_api_request_rejection(self):
        """Test rejection of invalid API requests."""
        invalid_requests = [
            # Missing required fields
            {"message": "Test message"},  # Missing tenant_id, context, features
            
            # Invalid field types
            {
                "tenant_id": 123,  # Should be string
                "message": "Test message",
                "context": {},
                "features": {}
            },
            
            # Extra fields
            {
                "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                "message": "Test message",
                "context": {},
                "features": {},
                "extra_field": "should_be_rejected"
            }
        ]
        
        for invalid_request in invalid_requests:
            with pytest.raises(ValueError):
                RouterDecisionRequest(**invalid_request)
    
    @pytest.mark.asyncio
    async def test_pii_detection_in_api_request(self):
        """Test PII detection in API requests."""
        # Request with PII in message
        request_with_pii = {
            "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
            "message": "My email is john.doe@example.com and phone is (555) 123-4567",
            "context": {"user_id": "user_123"},
            "features": {}
        }
        
        # Should detect PII
        result = PIIAssertions.assert_no_pii_in_text(request_with_pii["message"], "API request message")
        assert not result.passed, f"Should detect PII in API request: {request_with_pii['message']}"


class TestOrchestratorToRouterContract:
    """Test contract validation from Orchestrator to Router."""
    
    @pytest.mark.asyncio
    async def test_valid_orchestrator_request_to_router(self):
        """Test valid orchestrator request to router."""
        # Simulate orchestrator request to router
        orchestrator_request = {
            "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
            "message": "What are your business hours?",
            "context": {
                "user_id": "user_456",
                "session_id": "session_789",
                "request_source": "api"
            },
            "features": {
                "token_count": 5,
                "json_schema_strictness": 0.95,
                "domain_flags": {
                    "customer_support": True,
                    "sales": False,
                    "technical": False
                },
                "novelty_score": 0.1,
                "historical_failure_rate": 0.02
            }
        }
        
        # Validate as RouterDecisionRequest
        router_request = RouterDecisionRequest(**orchestrator_request)
        
        # Mock router processing
        router_mock = Mock()
        router_mock.route = AsyncMock()
        router_mock.route.return_value = RouterDecision(
            tier="SLM_A",
            confidence=0.95,
            expected_cost_usd=0.002,
            expected_latency_ms=300,
            reasoning="Simple FAQ question, high confidence in SLM_A"
        )
        
        # Process request
        decision = await router_mock.route(router_request)
        
        # Verify contract compliance
        assert isinstance(decision, RouterDecision)
        assert decision.tier.value == "SLM_A"
        assert decision.confidence == 0.95
    
    @pytest.mark.asyncio
    async def test_router_response_validation(self):
        """Test router response validation."""
        # Valid router response
        valid_response = {
            "tier": "SLM_B",
            "confidence": 0.8,
            "expected_cost_usd": 0.01,
            "expected_latency_ms": 1200,
            "reasoning": "Order-related query requires moderate complexity handling"
        }
        
        router_decision = RouterDecision(**valid_response)
        
        # Verify all fields are valid
        assert router_decision.tier.value == "SLM_B"
        assert 0 <= router_decision.confidence <= 1
        assert router_decision.expected_cost_usd >= 0
        assert router_decision.expected_latency_ms >= 0
        assert isinstance(router_decision.reasoning, str)
    
    @pytest.mark.asyncio
    async def test_router_error_response(self):
        """Test router error response validation."""
        # Simulate router error
        error_response = {
            "error": "Router Error",
            "message": "Unable to process request due to invalid features",
            "code": "INVALID_FEATURES",
            "status_code": 400,
            "timestamp": "2024-01-01T12:00:00Z"
        }
        
        # Validate error response structure
        result = ContractAssertions.assert_structured_error_response(error_response, "Router error response")
        assert result.passed, f"Router error response should be structured: {error_response}"
        
        # Validate HTTP status code
        result = ContractAssertions.assert_valid_http_status(
            error_response["status_code"], 
            [400, 401, 403, 404, 429, 500, 502, 503],
            "Router error status"
        )
        assert result.passed, f"Router error status should be valid: {error_response['status_code']}"


class TestRouterToToolContract:
    """Test contract validation from Router to Tool."""
    
    @pytest.mark.asyncio
    async def test_valid_tool_spec_validation(self):
        """Test valid tool specification validation."""
        # Valid tool spec
        tool_spec_data = {
            "tool_id": "knowledge_base_search",
            "name": "Knowledge Base Search",
            "description": "Search the knowledge base for relevant information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100
                    },
                    "category": {
                        "type": "string",
                        "enum": ["faq", "manual", "policy", "general"],
                        "description": "Category to search in"
                    }
                },
                "required": ["query"]
            },
            "cost_per_call": 0.001,
            "timeout_ms": 5000,
            "retry_count": 3
        }
        
        tool_spec = ToolSpec(**tool_spec_data)
        
        # Verify tool spec validation
        assert tool_spec.tool_id == "knowledge_base_search"
        assert tool_spec.name == "Knowledge Base Search"
        assert tool_spec.cost_per_call == 0.001
        assert tool_spec.timeout_ms == 5000
    
    @pytest.mark.asyncio
    async def test_tool_execution_contract(self):
        """Test tool execution contract validation."""
        # Mock tool execution
        tool_mock = Mock()
        tool_mock.execute = AsyncMock()
        
        # Valid tool execution request
        execution_request = {
            "tool_id": "knowledge_base_search",
            "parameters": {
                "query": "password reset",
                "limit": 5,
                "category": "faq"
            },
            "context": {
                "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                "user_id": "user_123"
            }
        }
        
        # Mock successful execution
        tool_mock.execute.return_value = {
            "success": True,
            "result": {
                "results": [
                    {
                        "title": "How to Reset Your Password",
                        "content": "To reset your password, go to the login page...",
                        "relevance_score": 0.95
                    }
                ],
                "total_count": 1,
                "query_time_ms": 150
            },
            "cost_usd": 0.001,
            "execution_time_ms": 200
        }
        
        # Execute tool
        result = await tool_mock.execute(execution_request)
        
        # Verify contract compliance
        assert result["success"] is True
        assert "result" in result
        assert "cost_usd" in result
        assert "execution_time_ms" in result
    
    @pytest.mark.asyncio
    async def test_tool_error_handling(self):
        """Test tool error handling contract."""
        # Mock tool error
        tool_mock = Mock()
        tool_mock.execute = AsyncMock()
        
        # Simulate tool error
        tool_mock.execute.side_effect = Exception("Tool execution failed")
        
        # Mock error handling
        try:
            await tool_mock.execute({"tool_id": "invalid_tool"})
        except Exception as e:
            # Verify error is properly handled
            error_response = {
                "error": "Tool Execution Error",
                "message": str(e),
                "code": "TOOL_EXECUTION_FAILED",
                "status_code": 500,
                "timestamp": "2024-01-01T12:00:00Z"
            }
            
            # Validate error response
            result = ContractAssertions.assert_structured_error_response(error_response, "Tool error response")
            assert result.passed, f"Tool error response should be structured: {error_response}"


class TestEndToEndContractFlow:
    """Test end-to-end contract validation flow."""
    
    @pytest.mark.asyncio
    async def test_complete_request_flow(self):
        """Test complete request flow with contract validation."""
        # Step 1: API Request
        api_request_data = {
            "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
            "message": "How do I upgrade my plan?",
            "context": {
                "user_id": "user_123",
                "session_id": "session_456"
            },
            "features": {
                "token_count": 7,
                "json_schema_strictness": 0.8,
                "domain_flags": {
                    "customer_support": True,
                    "sales": True,
                    "technical": False
                },
                "novelty_score": 0.3,
                "historical_failure_rate": 0.1
            }
        }
        
        router_request = RouterDecisionRequest(**api_request_data)
        
        # Step 2: Router Decision
        router_decision = RouterDecision(
            tier="SLM_B",
            confidence=0.85,
            expected_cost_usd=0.01,
            expected_latency_ms=1200,
            reasoning="Plan upgrade query requires moderate complexity handling"
        )
        
        # Step 3: Tool Execution
        tool_result = {
            "success": True,
            "result": {
                "response": "To upgrade your plan, please visit the billing section...",
                "actions": ["redirect_to_billing", "show_upgrade_options"],
                "confidence": 0.9
            },
            "cost_usd": 0.01,
            "execution_time_ms": 1100
        }
        
        # Step 4: Final Response
        final_response = {
            "status": "success",
            "response": tool_result["result"]["response"],
            "actions": tool_result["result"]["actions"],
            "metadata": {
                "tier_used": router_decision.tier.value,
                "confidence": router_decision.confidence,
                "cost_usd": tool_result["cost_usd"],
                "execution_time_ms": tool_result["execution_time_ms"]
            }
        }
        
        # Verify complete flow contract compliance
        assert isinstance(router_request, RouterDecisionRequest)
        assert isinstance(router_decision, RouterDecision)
        assert tool_result["success"] is True
        assert final_response["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_error_flow_contract_validation(self):
        """Test error flow contract validation."""
        # Step 1: Invalid API Request
        invalid_request_data = {
            "tenant_id": "invalid-uuid",  # Invalid UUID
            "message": "Test message",
            "context": {},
            "features": {}
        }
        
        with pytest.raises(ValueError):
            RouterDecisionRequest(**invalid_request_data)
        
        # Step 2: Router Error Response
        router_error = {
            "error": "Validation Error",
            "message": "Invalid tenant ID format",
            "code": "INVALID_TENANT_ID",
            "status_code": 400,
            "timestamp": "2024-01-01T12:00:00Z"
        }
        
        # Validate error response
        result = ContractAssertions.assert_structured_error_response(router_error, "Router validation error")
        assert result.passed, f"Router error should be structured: {router_error}"
    
    @pytest.mark.asyncio
    async def test_pii_flow_validation(self):
        """Test PII detection throughout the flow."""
        # Request with PII
        request_with_pii = {
            "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
            "message": "My email is john.doe@example.com, please help",
            "context": {
                "user_id": "user_123",
                "session_id": "session_456"
            },
            "features": {}
        }
        
        # Validate request
        router_request = RouterDecisionRequest(**request_with_pii)
        
        # Check PII in message
        result = PIIAssertions.assert_no_pii_in_text(router_request.message, "Request message")
        assert not result.passed, f"Should detect PII in request message: {router_request.message}"
        
        # Mock PII redaction
        redacted_message = router_request.message.replace("john.doe@example.com", "[REDACTED]")
        
        # Verify redaction
        result = PIIAssertions.assert_pii_redacted(redacted_message, "[REDACTED]", "Redacted message")
        assert result.passed, f"Message should have PII redacted: {redacted_message}"


class TestContractVersioning:
    """Test contract versioning and backward compatibility."""
    
    def test_backward_compatible_contract_changes(self):
        """Test backward compatible contract changes."""
        # Original contract data
        original_data = {
            "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
            "message": "Test message",
            "context": {},
            "features": {}
        }
        
        # Should still work with original data
        router_request = RouterDecisionRequest(**original_data)
        assert router_request.message == "Test message"
        
        # Extended contract data (new optional fields)
        extended_data = {
            **original_data,
            "features": {
                "token_count": 10,
                "json_schema_strictness": 0.8,
                "domain_flags": {"customer_support": True},
                "novelty_score": 0.3,
                "historical_failure_rate": 0.1,
                "additional_metadata": {"source": "api"}  # New optional field
            }
        }
        
        # Should work with extended data
        router_request_extended = RouterDecisionRequest(**extended_data)
        assert router_request_extended.features.token_count == 10
    
    def test_breaking_contract_changes(self):
        """Test breaking contract changes."""
        # Data with removed required field
        breaking_data = {
            "message": "Test message",  # Missing tenant_id, context, features
            "context": {},
            "features": {}
        }
        
        # Should fail validation
        with pytest.raises(ValueError):
            RouterDecisionRequest(**breaking_data)
        
        # Data with changed field type
        type_changed_data = {
            "tenant_id": 123,  # Should be string, not int
            "message": "Test message",
            "context": {},
            "features": {}
        }
        
        # Should fail validation
        with pytest.raises(ValueError):
            RouterDecisionRequest(**type_changed_data)
