"""Test strict JSON validation at service boundaries."""

import pytest
from pydantic import ValidationError
from libs.contracts.agent import AgentSpec, MessageSpec, AgentRequest, AgentResponse
from libs.contracts.router import RouterDecisionRequest, RouterDecisionResponse, TextFeatures
from libs.contracts.tool import ToolSpec, ToolCall, ToolResult
from libs.contracts.error import ErrorSpec, ValidationError as ContractValidationError


class TestStrictJSONValidation:
    """Test strict JSON validation for all contracts."""

    def test_agent_spec_forbids_extra_fields(self):
        """Test that AgentSpec forbids extra fields."""
        valid_data = {
            "id": "agent_123",
            "name": "Test Agent",
            "description": "A test agent",
            "version": "1.0.0",
            "capabilities": ["chat", "workflow"]
        }
        
        # Valid data should work
        agent = AgentSpec(**valid_data)
        assert agent.id == "agent_123"
        
        # Extra fields should be forbidden
        invalid_data = valid_data.copy()
        invalid_data["extra_field"] = "not_allowed"
        
        with pytest.raises(ValidationError) as exc_info:
            AgentSpec(**invalid_data)
        
        assert "extra_field" in str(exc_info.value)

    def test_message_spec_rejects_markdown_json(self):
        """Test that MessageSpec rejects markdown-wrapped JSON."""
        valid_data = {
            "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
            "content": "This is a normal message"
        }
        
        # Valid data should work
        message = MessageSpec(**valid_data)
        assert message.content == "This is a normal message"
        
        # Markdown-wrapped JSON should be rejected
        invalid_data = valid_data.copy()
        invalid_data["content"] = "```json\n{\"malicious\": \"injection\"}\n```"
        
        with pytest.raises(ValidationError) as exc_info:
            MessageSpec(**invalid_data)
        
        assert "Markdown-wrapped JSON is not allowed" in str(exc_info.value)

    def test_router_decision_request_rejects_markdown_json(self):
        """Test that RouterDecisionRequest rejects markdown-wrapped JSON."""
        valid_data = {
            "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
            "task_id": "550e8400-e29b-41d4-a716-446655440001",
            "requirement": "This is a normal requirement",
            "text_features": {
                "token_count": 100,
                "json_schema_strictness": 0.8,
                "domain_flags": {"customer_support": True},
                "novelty_score": 0.5,
                "historical_failure_rate": 0.1,
                "reasoning_keywords": ["help", "support"],
                "entity_count": 5,
                "format_strictness": 0.9
            },
            "history_stats": {
                "total_runs": 100,
                "success_rate": 0.95,
                "avg_latency_ms": 200,
                "avg_cost_usd": 0.01,
                "tier_distribution": {"SLM_A": 60, "SLM_B": 30, "LLM": 10}
            }
        }
        
        # Valid data should work
        request = RouterDecisionRequest(**valid_data)
        assert request.requirement == "This is a normal requirement"
        
        # Markdown-wrapped JSON should be rejected
        invalid_data = valid_data.copy()
        invalid_data["requirement"] = "```json\n{\"injection\": \"attempt\"}\n```"
        
        with pytest.raises(ValidationError) as exc_info:
            RouterDecisionRequest(**invalid_data)
        
        assert "Markdown-wrapped JSON is not allowed" in str(exc_info.value)

    def test_tool_spec_forbids_extra_fields(self):
        """Test that ToolSpec forbids extra fields."""
        valid_data = {
            "id": "tool_123",
            "name": "Test Tool",
            "description": "A test tool",
            "version": "1.0.0",
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object"},
            "capabilities": ["data_processing"]
        }
        
        # Valid data should work
        tool = ToolSpec(**valid_data)
        assert tool.id == "tool_123"
        
        # Extra fields should be forbidden
        invalid_data = valid_data.copy()
        invalid_data["malicious_field"] = "not_allowed"
        
        with pytest.raises(ValidationError) as exc_info:
            ToolSpec(**invalid_data)
        
        assert "malicious_field" in str(exc_info.value)

    def test_validation_error_forbids_extra_fields(self):
        """Test that ValidationError forbids extra fields."""
        valid_data = {
            "field": "test_field",
            "message": "Validation failed",
            "value": "invalid_value"
        }
        
        # Valid data should work
        error = ContractValidationError(**valid_data)
        assert error.field == "test_field"
        
        # Extra fields should be forbidden
        invalid_data = valid_data.copy()
        invalid_data["injection"] = "attempt"
        
        with pytest.raises(ValidationError) as exc_info:
            ContractValidationError(**invalid_data)
        
        assert "injection" in str(exc_info.value)

    def test_all_contracts_forbid_extra_fields(self):
        """Test that all contracts forbid extra fields."""
        contracts_to_test = [
            (AgentSpec, {"id": "test", "name": "Test", "description": "Test", "version": "1.0.0", "capabilities": ["test"]}),
            (MessageSpec, {"tenant_id": "550e8400-e29b-41d4-a716-446655440000", "content": "test"}),
            (AgentRequest, {
                "message": {"tenant_id": "550e8400-e29b-41d4-a716-446655440000", "content": "test"},
                "agent_id": "550e8400-e29b-41d4-a716-446655440001"
            }),
            (AgentResponse, {
                "message": {"tenant_id": "550e8400-e29b-41d4-a716-446655440000", "content": "test"},
                "agent_id": "550e8400-e29b-41d4-a716-446655440001",
                "status": "success",
                "tokens_used": 100,
                "cost_usd": 0.01,
                "duration_ms": 200
            }),
            (TextFeatures, {
                "token_count": 100,
                "json_schema_strictness": 0.8,
                "domain_flags": {},
                "novelty_score": 0.5,
                "historical_failure_rate": 0.1,
                "reasoning_keywords": [],
                "entity_count": 5,
                "format_strictness": 0.9
            }),
            (ToolCall, {
                "tool_id": "550e8400-e29b-41d4-a716-446655440000",
                "tenant_id": "550e8400-e29b-41d4-a716-446655440001",
                "input_data": {}
            }),
            (ToolResult, {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "tool_id": "550e8400-e29b-41d4-a716-446655440001",
                "tenant_id": "550e8400-e29b-41d4-a716-446655440002",
                "status": "success",
                "duration_ms": 100
            }),
            (ErrorSpec, {"error_type": "test", "error_code": "TEST_ERROR", "message": "Test error"}),
        ]
        
        for contract_class, valid_data in contracts_to_test:
            # Valid data should work
            instance = contract_class(**valid_data)
            assert instance is not None
            
            # Extra fields should be forbidden
            invalid_data = valid_data.copy()
            invalid_data["extra_field"] = "not_allowed"
            
            with pytest.raises(ValidationError) as exc_info:
                contract_class(**invalid_data)
            
            assert "extra_field" in str(exc_info.value)

    def test_field_validation_constraints(self):
        """Test field validation constraints."""
        # Test string length constraints
        with pytest.raises(ValidationError):
            AgentSpec(
                id="",  # Empty string should fail
                name="Test Agent",
                description="A test agent",
                version="1.0.0",
                capabilities=["chat"]
            )
        
        # Test version format constraint
        with pytest.raises(ValidationError):
            AgentSpec(
                id="agent_123",
                name="Test Agent",
                description="A test agent",
                version="invalid_version",  # Should be semantic version
                capabilities=["chat"]
            )
        
        # Test numeric constraints
        with pytest.raises(ValidationError):
            TextFeatures(
                token_count=-1,  # Should be >= 0
                json_schema_strictness=0.8,
                domain_flags={},
                novelty_score=0.5,
                historical_failure_rate=0.1,
                reasoning_keywords=[],
                entity_count=5,
                format_strictness=0.9
            )

    def test_required_fields_validation(self):
        """Test that required fields are enforced."""
        # Test missing required fields
        with pytest.raises(ValidationError):
            AgentSpec()  # Missing all required fields
        
        with pytest.raises(ValidationError):
            MessageSpec()  # Missing required fields
        
        with pytest.raises(ValidationError):
            ToolSpec()  # Missing required fields

    def test_enum_validation(self):
        """Test enum field validation."""
        # Test valid enum values
        response = RouterDecisionResponse(
            request_id="550e8400-e29b-41d4-a716-446655440000",
            tier="SLM_A",  # Valid enum value
            confidence=0.95,
            expected_cost_usd=0.01,
            expected_latency_ms=100,
            reasons=["Low complexity"]
        )
        assert response.tier.value == "SLM_A"
        
        # Test invalid enum values
        with pytest.raises(ValidationError):
            RouterDecisionResponse(
                request_id="550e8400-e29b-41d4-a716-446655440000",
                tier="INVALID_TIER",  # Invalid enum value
                confidence=0.95,
                expected_cost_usd=0.01,
                expected_latency_ms=100,
                reasons=["Low complexity"]
            )

    def test_uuid_validation(self):
        """Test UUID field validation."""
        # Test valid UUID
        message = MessageSpec(
            tenant_id="550e8400-e29b-41d4-a716-446655440000",  # Valid UUID
            content="test message"
        )
        assert str(message.tenant_id) == "550e8400-e29b-41d4-a716-446655440000"
        
        # Test invalid UUID
        with pytest.raises(ValidationError):
            MessageSpec(
                tenant_id="invalid-uuid",  # Invalid UUID format
                content="test message"
            )

    def test_datetime_validation(self):
        """Test datetime field validation."""
        from datetime import datetime
        
        # Test that datetime fields are automatically created
        error = ErrorSpec(
            error_type="test",
            error_code="TEST_ERROR",
            message="Test error"
        )
        assert isinstance(error.timestamp, datetime)
        
        # Test that custom datetime is accepted
        custom_time = datetime(2024, 1, 1, 12, 0, 0)
        error = ErrorSpec(
            error_type="test",
            error_code="TEST_ERROR",
            message="Test error",
            timestamp=custom_time
        )
        assert error.timestamp == custom_time
