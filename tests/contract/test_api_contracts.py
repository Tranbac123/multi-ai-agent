"""Contract tests for API service boundaries."""

import pytest
import json
from unittest.mock import AsyncMock
from hypothesis import given, strategies as st

from libs.contracts.api_contracts import (
    ChatRequest, ChatResponse, 
    WorkflowRequest, WorkflowResponse,
    RouterRequest, RouterResponse,
    ToolRequest, ToolResponse
)


class TestAPIContracts:
    """Test API contract validation."""

    def test_chat_request_validation(self):
        """Test chat request validation."""
        # Valid request
        valid_request = {
            "message": "Hello, I need help",
            "tenant_id": "tenant_001",
            "user_id": "user_001",
            "session_id": "session_001",
            "metadata": {"source": "web"}
        }
        
        chat_req = ChatRequest(**valid_request)
        assert chat_req.message == "Hello, I need help"
        assert chat_req.tenant_id == "tenant_001"
        assert chat_req.user_id == "user_001"

    def test_chat_request_invalid_tenant(self):
        """Test chat request with invalid tenant."""
        invalid_request = {
            "message": "Hello",
            "tenant_id": "",  # Empty tenant_id
            "user_id": "user_001"
        }
        
        with pytest.raises(ValueError, match="tenant_id cannot be empty"):
            ChatRequest(**invalid_request)

    def test_chat_response_validation(self):
        """Test chat response validation."""
        valid_response = {
            "response": "I can help you with that",
            "message_id": "msg_001",
            "tenant_id": "tenant_001",
            "user_id": "user_001",
            "session_id": "session_001",
            "metadata": {"model": "gpt-4", "tokens_used": 50}
        }
        
        chat_resp = ChatResponse(**valid_response)
        assert chat_resp.response == "I can help you with that"
        assert chat_resp.metadata["model"] == "gpt-4"

    def test_workflow_request_validation(self):
        """Test workflow request validation."""
        valid_request = {
            "workflow_name": "customer_support",
            "tenant_id": "tenant_001",
            "user_id": "user_001",
            "input_data": {"message": "Help me"},
            "context": {"priority": "high"}
        }
        
        workflow_req = WorkflowRequest(**valid_request)
        assert workflow_req.workflow_name == "customer_support"
        assert workflow_req.input_data["message"] == "Help me"

    def test_router_request_validation(self):
        """Test router request validation."""
        valid_request = {
            "message": "What is my order status?",
            "tenant_id": "tenant_001",
            "user_id": "user_001",
            "features": {"token_count": 10, "complexity": 0.5},
            "metadata": {"priority": "high"}
        }
        
        router_req = RouterRequest(**valid_request)
        assert router_req.message == "What is my order status?"
        assert router_req.features["token_count"] == 10

    def test_tool_request_validation(self):
        """Test tool request validation."""
        valid_request = {
            "tool_name": "order_lookup",
            "tenant_id": "tenant_001",
            "user_id": "user_001",
            "parameters": {"order_id": "12345"},
            "metadata": {"execution_time": 1.0}
        }
        
        tool_req = ToolRequest(**valid_request)
        assert tool_req.tool_name == "order_lookup"
        assert tool_req.parameters["order_id"] == "12345"

    def test_tool_response_validation(self):
        """Test tool response validation."""
        valid_response = {
            "success": True,
            "result": {"order_id": "12345", "status": "shipped"},
            "execution_time": 0.5,
            "cost": 0.01,
            "metadata": {"tool_version": "1.0.0"}
        }
        
        tool_resp = ToolResponse(**valid_response)
        assert tool_resp.success is True
        assert tool_resp.result["order_id"] == "12345"
        assert tool_resp.cost == 0.01

    @given(st.text(min_size=1, max_size=1000))
    def test_message_content_validation(self, message):
        """Test message content validation."""
        request = {
            "message": message,
            "tenant_id": "tenant_001",
            "user_id": "user_001"
        }
        
        chat_req = ChatRequest(**request)
        assert chat_req.message == message

    def test_error_mapping(self):
        """Test error mapping between services."""
        # API Gateway -> Orchestrator error mapping
        api_error = {
            "error": "validation_failed",
            "message": "Invalid request format",
            "status_code": 400
        }
        
        # Should map to orchestrator error format
        orchestrator_error = {
            "error_type": "validation_error",
            "error_message": "Invalid request format",
            "error_code": "INVALID_REQUEST"
        }
        
        # Test error mapping function
        mapped_error = self._map_api_to_orchestrator_error(api_error)
        assert mapped_error["error_type"] == "validation_error"
        assert mapped_error["error_message"] == "Invalid request format"

    def test_schema_rejection_invalid_payload(self):
        """Test schema rejection for invalid payloads."""
        # Invalid JSON structure
        invalid_payload = {
            "message": "Hello",
            "tenant_id": "tenant_001",
            "invalid_field": "should_not_be_here"
        }
        
        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            ChatRequest(**invalid_payload)

    def test_schema_rejection_missing_required(self):
        """Test schema rejection for missing required fields."""
        # Missing required tenant_id
        invalid_payload = {
            "message": "Hello",
            "user_id": "user_001"
        }
        
        with pytest.raises(ValueError, match="Field required"):
            ChatRequest(**invalid_payload)

    def test_schema_rejection_wrong_type(self):
        """Test schema rejection for wrong field types."""
        # tenant_id should be string, not int
        invalid_payload = {
            "message": "Hello",
            "tenant_id": 12345,  # Should be string
            "user_id": "user_001"
        }
        
        with pytest.raises(ValueError, match="Input should be a valid string"):
            ChatRequest(**invalid_payload)

    def _map_api_to_orchestrator_error(self, api_error):
        """Map API error to orchestrator error format."""
        error_mapping = {
            "validation_failed": "validation_error",
            "authentication_failed": "auth_error",
            "rate_limit_exceeded": "rate_limit_error",
            "internal_error": "system_error"
        }
        
        return {
            "error_type": error_mapping.get(api_error["error"], "unknown_error"),
            "error_message": api_error["message"],
            "error_code": api_error["error"].upper()
        }


class TestServiceBoundaries:
    """Test service boundary contracts."""

    def test_api_gateway_to_orchestrator(self):
        """Test API Gateway to Orchestrator contract."""
        # API Gateway sends chat request
        api_request = ChatRequest(
            message="Hello",
            tenant_id="tenant_001",
            user_id="user_001"
        )
        
        # Should be valid for orchestrator
        orchestrator_request = WorkflowRequest(
            workflow_name="chat_workflow",
            tenant_id=api_request.tenant_id,
            user_id=api_request.user_id,
            input_data={"message": api_request.message}
        )
        
        assert orchestrator_request.tenant_id == api_request.tenant_id
        assert orchestrator_request.user_id == api_request.user_id

    def test_orchestrator_to_router(self):
        """Test Orchestrator to Router contract."""
        # Orchestrator sends workflow request
        workflow_request = WorkflowRequest(
            workflow_name="order_workflow",
            tenant_id="tenant_001",
            user_id="user_001",
            input_data={"message": "Track my order"}
        )
        
        # Should be valid for router
        router_request = RouterRequest(
            message=workflow_request.input_data["message"],
            tenant_id=workflow_request.tenant_id,
            user_id=workflow_request.user_id,
            features={"workflow": workflow_request.workflow_name}
        )
        
        assert router_request.tenant_id == workflow_request.tenant_id
        assert router_request.user_id == workflow_request.user_id

    def test_router_to_tool(self):
        """Test Router to Tool contract."""
        # Router sends tool request
        router_request = RouterRequest(
            message="What is my order status?",
            tenant_id="tenant_001",
            user_id="user_001",
            features={"tool": "order_lookup"}
        )
        
        # Should be valid for tool
        tool_request = ToolRequest(
            tool_name="order_lookup",
            tenant_id=router_request.tenant_id,
            user_id=router_request.user_id,
            parameters={"query": router_request.message}
        )
        
        assert tool_request.tenant_id == router_request.tenant_id
        assert tool_request.user_id == router_request.user_id

    def test_response_chain_validation(self):
        """Test response chain validation."""
        # Tool response
        tool_response = ToolResponse(
            success=True,
            result={"order_id": "12345", "status": "shipped"},
            execution_time=0.5,
            cost=0.01
        )
        
        # Router response
        router_response = RouterResponse(
            model="gpt-4",
            response="Your order is shipped",
            cost=tool_response.cost,
            latency=tool_response.execution_time,
            success=tool_response.success
        )
        
        # Workflow response
        workflow_response = WorkflowResponse(
            workflow_name="order_workflow",
            result=router_response.response,
            success=router_response.success,
            execution_time=router_response.latency,
            cost=router_response.cost
        )
        
        # Chat response
        chat_response = ChatResponse(
            response=workflow_response.result,
            message_id="msg_001",
            tenant_id="tenant_001",
            user_id="user_001",
            session_id="session_001",
            metadata={
                "workflow": workflow_response.workflow_name,
                "model": router_response.model,
                "cost": workflow_response.cost
            }
        )
        
        # Verify chain integrity
        assert chat_response.response == workflow_response.result
        assert workflow_response.result == router_response.response
        assert router_response.cost == tool_response.cost
        assert router_response.latency == tool_response.execution_time
