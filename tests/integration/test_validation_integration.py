"""Integration tests for validation across service boundaries."""

import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from apps.api_gateway.main import app
from libs.contracts.agent import AgentRequest, AgentResponse
from libs.contracts.tool import ToolCall, ToolResult
from libs.contracts.router_io import RouterDecisionRequest, RouterDecisionResponse


client = TestClient(app)


class TestAPIValidation:
    """Test API validation integration."""
    
    def test_invalid_agent_request_returns_400(self):
        """Test that invalid agent request returns 400 with clear error."""
        invalid_payload = {
            "message": {
                "id": "msg-123",
                "tenant_id": "tenant-456",
                "content": "Hello world",
                "timestamp": "invalid_timestamp"  # Should be float
            },
            "agent_id": "test-agent"
        }
        
        response = client.post("/api/v1/agent/execute", json=invalid_payload)
        
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "validation_error" in data["error"]["error_type"]
        assert "INVALID_REQUEST" in data["error"]["error_code"]
    
    def test_invalid_tool_call_returns_400(self):
        """Test that invalid tool call returns 400 with clear error."""
        invalid_payload = {
            "id": "call-123",
            "tool_id": "test-tool",
            "tenant_id": "tenant-456",
            "input_data": "not_a_dict"  # Should be dict
        }
        
        response = client.post("/api/v1/tool/call", json=invalid_payload)
        
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "validation_error" in data["error"]["error_type"]
    
    def test_invalid_router_request_returns_400(self):
        """Test that invalid router request returns 400 with clear error."""
        invalid_payload = {
            "message": "Hello world",
            "tenant_id": 123  # Should be string
        }
        
        response = client.post("/api/v1/router/decide", json=invalid_payload)
        
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "validation_error" in data["error"]["error_type"]
    
    def test_missing_required_fields_returns_400(self):
        """Test that missing required fields return 400 with clear error."""
        incomplete_payload = {
            "message": "Hello world"
            # Missing tenant_id
        }
        
        response = client.post("/api/v1/router/decide", json=incomplete_payload)
        
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "validation_error" in data["error"]["error_type"]
        assert len(data["validation_errors"]) > 0
    
    def test_valid_request_returns_200(self):
        """Test that valid request returns 200."""
        valid_payload = {
            "message": "Hello world",
            "tenant_id": "tenant-456"
        }
        
        with patch('apps.router_service.main.router_service') as mock_router:
            mock_router.decide.return_value = RouterDecisionResponse(
                agent_id="test-agent",
                tier="A",
                confidence=0.95,
                reasoning="High confidence match",
                cost_estimate=0.01,
                latency_estimate_ms=100
            )
            
            response = client.post("/api/v1/router/decide", json=valid_payload)
            
            assert response.status_code == 200
            data = response.json()
            assert data["agent_id"] == "test-agent"
            assert data["tier"] == "A"


class TestServiceBoundaryValidation:
    """Test validation at service boundaries."""
    
    def test_orchestrator_agent_request_validation(self):
        """Test orchestrator validates agent requests."""
        from apps.orchestrator.core.orchestrator import OrchestratorService
        
        orchestrator = OrchestratorService()
        
        # Valid request
        valid_request = AgentRequest(
            message={
                "id": "msg-123",
                "tenant_id": "tenant-456",
                "content": "Hello world",
                "timestamp": 1234567890.0
            },
            agent_id="test-agent"
        )
        
        # This should not raise validation error
        assert valid_request.agent_id == "test-agent"
    
    def test_router_decision_validation(self):
        """Test router validates decision requests."""
        from apps.router_service.core.router import RouterService
        
        router = RouterService()
        
        # Valid request
        valid_request = RouterDecisionRequest(
            message="Hello world",
            tenant_id="tenant-456"
        )
        
        # This should not raise validation error
        assert valid_request.tenant_id == "tenant-456"
    
    def test_tool_adapter_validation(self):
        """Test tool adapters validate tool calls."""
        from apps.orchestrator.core.tools import CRMTool
        
        tool = CRMTool()
        
        # Valid tool call
        valid_call = ToolCall(
            id="call-123",
            tool_id="crm-tool",
            tenant_id="tenant-456",
            input_data={"action": "search", "query": "test"}
        )
        
        # This should not raise validation error
        assert valid_call.tool_id == "crm-tool"


class TestErrorResponseFormat:
    """Test error response format consistency."""
    
    def test_error_response_structure(self):
        """Test that error responses have consistent structure."""
        invalid_payload = {
            "message": "Hello world"
            # Missing tenant_id
        }
        
        response = client.post("/api/v1/router/decide", json=invalid_payload)
        
        assert response.status_code == 400
        data = response.json()
        
        # Check required fields
        assert "success" in data
        assert "error" in data
        assert "validation_errors" in data
        
        # Check error structure
        error = data["error"]
        assert "error_id" in error
        assert "error_type" in error
        assert "error_code" in error
        assert "message" in error
        assert "timestamp" in error
        assert "service" in error
    
    def test_validation_errors_structure(self):
        """Test that validation errors have consistent structure."""
        invalid_payload = {
            "message": "Hello world"
            # Missing tenant_id
        }
        
        response = client.post("/api/v1/router/decide", json=invalid_payload)
        
        assert response.status_code == 400
        data = response.json()
        
        validation_errors = data["validation_errors"]
        assert len(validation_errors) > 0
        
        for error in validation_errors:
            assert "field" in error
            assert "message" in error
            assert "value" in error
            assert "error_type" in error
