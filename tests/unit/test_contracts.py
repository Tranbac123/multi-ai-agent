"""Unit tests for contract validation."""

import pytest
from pydantic import ValidationError
from libs.contracts.agent import AgentSpec, MessageSpec, AgentRequest, AgentResponse
from libs.contracts.tool import ToolSpec, ToolCall, ToolResult
from libs.contracts.error import ErrorSpec, ServiceError, ErrorResponse
from libs.contracts.router_io import RouterDecisionRequest, RouterDecisionResponse


class TestAgentContracts:
    """Test agent contract validation."""
    
    def test_agent_spec_valid(self):
        """Test valid agent spec."""
        spec = AgentSpec(
            id="test-agent",
            name="Test Agent",
            description="Test agent for validation",
            version="1.0.0",
            capabilities=["chat", "search"]
        )
        assert spec.id == "test-agent"
        assert spec.name == "Test Agent"
        assert spec.capabilities == ["chat", "search"]
    
    def test_agent_spec_invalid_missing_required(self):
        """Test agent spec with missing required fields."""
        with pytest.raises(ValidationError):
            AgentSpec(
                name="Test Agent",
                description="Test agent"
                # Missing id, version, capabilities
            )
    
    def test_message_spec_valid(self):
        """Test valid message spec."""
        message = MessageSpec(
            id="msg-123",
            tenant_id="tenant-456",
            content="Hello world",
            timestamp=1234567890.0
        )
        assert message.id == "msg-123"
        assert message.tenant_id == "tenant-456"
        assert message.content == "Hello world"
    
    def test_agent_request_valid(self):
        """Test valid agent request."""
        message = MessageSpec(
            id="msg-123",
            tenant_id="tenant-456",
            content="Hello world",
            timestamp=1234567890.0
        )
        request = AgentRequest(
            message=message,
            agent_id="test-agent"
        )
        assert request.agent_id == "test-agent"
        assert request.message.id == "msg-123"


class TestToolContracts:
    """Test tool contract validation."""
    
    def test_tool_spec_valid(self):
        """Test valid tool spec."""
        spec = ToolSpec(
            id="test-tool",
            name="Test Tool",
            description="Test tool for validation",
            version="1.0.0",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            capabilities=["search", "update"]
        )
        assert spec.id == "test-tool"
        assert spec.input_schema == {"type": "object"}
    
    def test_tool_call_valid(self):
        """Test valid tool call."""
        call = ToolCall(
            id="call-123",
            tool_id="test-tool",
            tenant_id="tenant-456",
            input_data={"query": "test"}
        )
        assert call.id == "call-123"
        assert call.tool_id == "test-tool"
        assert call.input_data == {"query": "test"}


class TestErrorContracts:
    """Test error contract validation."""
    
    def test_error_spec_valid(self):
        """Test valid error spec."""
        error = ErrorSpec(
            error_type="validation_error",
            error_code="INVALID_INPUT",
            message="Invalid input provided",
            status_code=400
        )
        assert error.error_type == "validation_error"
        assert error.status_code == 400
    
    def test_service_error_valid(self):
        """Test valid service error."""
        error = ServiceError(
            error_id="error-123",
            error_type="validation_error",
            error_code="INVALID_REQUEST",
            message="Request validation failed",
            timestamp=1234567890.0,
            service="api-gateway"
        )
        assert error.error_id == "error-123"
        assert error.service == "api-gateway"


class TestRouterContracts:
    """Test router contract validation."""
    
    def test_router_request_valid(self):
        """Test valid router request."""
        request = RouterDecisionRequest(
            message="Hello world",
            tenant_id="tenant-456"
        )
        assert request.message == "Hello world"
        assert request.tenant_id == "tenant-456"
    
    def test_router_response_valid(self):
        """Test valid router response."""
        response = RouterDecisionResponse(
            agent_id="test-agent",
            tier="A",
            confidence=0.95,
            reasoning="High confidence match",
            cost_estimate=0.01,
            latency_estimate_ms=100
        )
        assert response.agent_id == "test-agent"
        assert response.tier == "A"
        assert response.confidence == 0.95


class TestContractValidation:
    """Test contract validation edge cases."""
    
    def test_invalid_payload_rejection(self):
        """Test that invalid payloads are rejected."""
        # Test with completely invalid data
        with pytest.raises(ValidationError):
            AgentSpec(
                id=123,  # Should be string
                name=None,  # Should not be None
                description="Test",
                version="1.0.0",
                capabilities="not_a_list"  # Should be list
            )
    
    def test_missing_optional_fields(self):
        """Test that missing optional fields are handled correctly."""
        message = MessageSpec(
            id="msg-123",
            tenant_id="tenant-456",
            content="Hello world",
            timestamp=1234567890.0
            # user_id and session_id are optional
        )
        assert message.user_id is None
        assert message.session_id is None
    
    def test_default_values(self):
        """Test that default values are applied correctly."""
        spec = AgentSpec(
            id="test-agent",
            name="Test Agent",
            description="Test agent",
            version="1.0.0",
            capabilities=["chat"]
            # config and metadata should default to empty dict
        )
        assert spec.config == {}
        assert spec.metadata == {}