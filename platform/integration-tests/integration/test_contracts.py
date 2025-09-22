"""
Integration tests for strict contract validation.

Tests contract validation, error handling, and PII redaction across all boundaries.
"""

import pytest
import json
from unittest.mock import Mock, patch

from libs.contracts import (
    AgentSpec, AgentCapabilities, AgentMetadata,
    MessageSpec, MessageType, MessagePriority,
    ToolSpec, ToolInput, ToolOutput, ToolStatus,
    ErrorSpec, ErrorCode, ErrorSeverity,
    RouterDecisionRequest, RouterDecisionResponse, RouterTier,
    validate_contract, ContractValidationError
)
from libs.contracts.validation import (
    sanitize_for_logging, validate_api_request, 
    validate_api_response, create_error_response
)


class TestAgentContracts:
    """Test agent specification contracts."""
    
    def test_valid_agent_spec(self):
        """Test valid agent specification."""
        capabilities = AgentCapabilities(
            capabilities=["text_processing", "reasoning"],
            max_context_length=4000,
            max_output_length=1000,
            supported_languages=["en", "es"],
            requires_tools=True
        )
        
        metadata = AgentMetadata(
            name="test_agent",
            version="1.0.0",
            description="Test agent for validation",
            author="test_author"
        )
        
        agent = AgentSpec(
            tenant_id="tenant_123",
            metadata=metadata,
            capabilities=capabilities,
            configuration={"temperature": 0.7},
            performance_metrics={"accuracy": 0.95, "latency_ms": 150}
        )
        
        assert agent.tenant_id == "tenant_123"
        assert agent.metadata.name == "test_agent"
        assert len(agent.capabilities.capabilities) == 2
    
    def test_invalid_agent_id_format(self):
        """Test invalid agent ID format."""
        with pytest.raises(ContractValidationError) as exc_info:
            AgentSpec(
                agent_id="invalid-uuid",
                tenant_id="tenant_123",
                metadata=AgentMetadata(name="test", version="1.0.0", description="test", author="test"),
                capabilities=AgentCapabilities(capabilities=["text_processing"], max_context_length=1000, max_output_length=100)
            )
        
        assert "agent_id must be a valid UUID" in str(exc_info.value)
    
    def test_missing_required_fields(self):
        """Test missing required fields."""
        with pytest.raises(ContractValidationError) as exc_info:
            AgentSpec(
                tenant_id="tenant_123",
                # Missing metadata and capabilities
            )
        
        assert "field required" in str(exc_info.value)
    
    def test_extra_fields_forbidden(self):
        """Test that extra fields are forbidden."""
        with pytest.raises(ContractValidationError) as exc_info:
            AgentSpec(
                tenant_id="tenant_123",
                metadata=AgentMetadata(name="test", version="1.0.0", description="test", author="test"),
                capabilities=AgentCapabilities(capabilities=["text_processing"], max_context_length=1000, max_output_length=100),
                extra_field="not_allowed"  # This should be forbidden
            )
        
        assert "extra fields not permitted" in str(exc_info.value)


class TestMessageContracts:
    """Test message specification contracts."""
    
    def test_valid_message_spec(self):
        """Test valid message specification."""
        from libs.contracts.message_spec import MessageContent, MessageMetadata
        
        content = MessageContent(
            text="Hello, world!",
            data={"key": "value"},
            attachments=[]
        )
        
        metadata = MessageMetadata(
            source="user_123",
            target="agent_456",
            correlation_id="corr_789"
        )
        
        message = MessageSpec(
            tenant_id="tenant_123",
            message_type=MessageType.USER_INPUT,
            priority=MessagePriority.NORMAL,
            content=content,
            metadata=metadata,
            tags=["urgent", "customer"]
        )
        
        assert message.tenant_id == "tenant_123"
        assert message.message_type == MessageType.USER_INPUT
        assert message.content.text == "Hello, world!"
    
    def test_invalid_message_type_content(self):
        """Test invalid message type and content combination."""
        from libs.contracts.message_spec import MessageContent, MessageMetadata
        
        content = MessageContent(text=None, data=None, attachments=[])  # No content
        
        metadata = MessageMetadata(source="user_123")
        
        with pytest.raises(ContractValidationError) as exc_info:
            MessageSpec(
                tenant_id="tenant_123",
                message_type=MessageType.USER_INPUT,
                content=content,
                metadata=metadata
            )
        
        assert "At least one content type must be provided" in str(exc_info.value)
    
    def test_invalid_tag_format(self):
        """Test invalid tag format."""
        from libs.contracts.message_spec import MessageContent, MessageMetadata
        
        content = MessageContent(text="Test message")
        metadata = MessageMetadata(source="user_123")
        
        with pytest.raises(ContractValidationError) as exc_info:
            MessageSpec(
                tenant_id="tenant_123",
                message_type=MessageType.USER_INPUT,
                content=content,
                metadata=metadata,
                tags=["", "valid_tag"]  # Empty tag
            )
        
        assert "cannot be empty" in str(exc_info.value)


class TestToolContracts:
    """Test tool specification contracts."""
    
    def test_valid_tool_spec(self):
        """Test valid tool specification."""
        from libs.contracts.tool_spec import ToolParameter, ToolType
        
        parameter = ToolParameter(
            name="input_text",
            type="string",
            description="Input text to process",
            required=True,
            default_value=""
        )
        
        tool = ToolSpec(
            tenant_id="tenant_123",
            name="test_tool",
            description="Test tool for validation",
            tool_type=ToolType.API_CALL,
            parameters=[parameter],
            version="1.0.0"
        )
        
        assert tool.tenant_id == "tenant_123"
        assert tool.name == "test_tool"
        assert len(tool.parameters) == 1
    
    def test_tool_input_output_validation(self):
        """Test tool input and output validation."""
        # Valid tool input
        tool_input = ToolInput(
            tool_id="tool_123",
            parameters={"text": "Hello"},
            context={"user_id": "user_123"},
            timeout_seconds=30,
            retry_count=2,
            idempotency_key="key_123"
        )
        
        assert tool_input.tool_id == "tool_123"
        assert tool_input.parameters["text"] == "Hello"
        
        # Valid tool output
        tool_output = ToolOutput(
            tool_id="tool_123",
            status=ToolStatus.COMPLETED,
            result={"output": "Processed"},
            execution_time_ms=150.5,
            cost_usd=0.001,
            tokens_used=50
        )
        
        assert tool_output.status == ToolStatus.COMPLETED
        assert tool_output.result["output"] == "Processed"
    
    def test_tool_output_error_required(self):
        """Test that error message is required for failed status."""
        with pytest.raises(ContractValidationError) as exc_info:
            ToolOutput(
                tool_id="tool_123",
                status=ToolStatus.FAILED,
                result=None,
                execution_time_ms=100.0
                # Missing error_message for failed status
            )
        
        assert "error_message is required for failed status" in str(exc_info.value)
    
    def test_tool_output_result_required(self):
        """Test that result is required for completed status."""
        with pytest.raises(ContractValidationError) as exc_info:
            ToolOutput(
                tool_id="tool_123",
                status=ToolStatus.COMPLETED,
                result=None,  # Missing result for completed status
                execution_time_ms=100.0
            )
        
        assert "result is required for completed status" in str(exc_info.value)


class TestErrorContracts:
    """Test error specification contracts."""
    
    def test_valid_error_spec(self):
        """Test valid error specification."""
        from libs.contracts.error_spec import ErrorContext, ErrorDetails
        
        context = ErrorContext(
            tenant_id="tenant_123",
            user_id="user_456",
            component="test_component",
            operation="test_operation"
        )
        
        details = ErrorDetails(
            message="Test error message",
            technical_message="Technical details",
            suggestions=["Retry the operation", "Check input parameters"]
        )
        
        error = ErrorSpec(
            error_code=ErrorCode.VALIDATION_ERROR,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.VALIDATION,
            details=details,
            context=context
        )
        
        assert error.error_code == ErrorCode.VALIDATION_ERROR
        assert error.severity == ErrorSeverity.MEDIUM
        assert len(error.details.suggestions) == 2
    
    def test_error_code_category_consistency(self):
        """Test error code and category consistency."""
        from libs.contracts.error_spec import ErrorContext, ErrorDetails
        
        context = ErrorContext(tenant_id="tenant_123")
        details = ErrorDetails(message="Test error")
        
        # Valid combination
        error = ErrorSpec(
            error_code=ErrorCode.VALIDATION_ERROR,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.VALIDATION,  # Matches error code
            details=details,
            context=context
        )
        
        assert error.category == ErrorCategory.VALIDATION
        
        # Invalid combination should raise validation error
        with pytest.raises(ContractValidationError) as exc_info:
            ErrorSpec(
                error_code=ErrorCode.VALIDATION_ERROR,
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.AUTHENTICATION,  # Doesn't match error code
                details=details,
                context=context
            )
        
        assert "should have category" in str(exc_info.value)


class TestRouterContracts:
    """Test router specification contracts."""
    
    def test_valid_router_decision_request(self):
        """Test valid router decision request."""
        from libs.contracts.router_spec import FeatureVector, RoutingContext
        
        features = FeatureVector(
            token_count=100,
            json_schema_strictness=0.8,
            domain_flags=["customer_service", "billing"],
            novelty=0.3,
            historical_failure_rate=0.05,
            complexity_score=0.6,
            urgency_score=0.7,
            cost_sensitivity=0.4
        )
        
        context = RoutingContext(
            tenant_id="tenant_123",
            user_id="user_456",
            tenant_tier="premium",
            cost_budget_remaining=0.8,
            latency_budget_ms=3000
        )
        
        request = RouterDecisionRequest(
            input_text="Help me with my billing question",
            features=features,
            context=context,
            available_tiers=[RouterTier.SLM_A, RouterTier.LLM_A, RouterTier.HUMAN],
            early_exit_threshold=0.9,
            max_cost_usd=0.05,
            max_latency_ms=2000
        )
        
        assert request.tenant_id == "tenant_123"
        assert len(request.available_tiers) == 3
    
    def test_valid_router_decision_response(self):
        """Test valid router decision response."""
        response = RouterDecisionResponse(
            selected_tier=RouterTier.LLM_A,
            confidence=0.85,
            confidence_level=RouterConfidence.HIGH,
            reasoning="Complex billing question requires LLM processing",
            expected_cost_usd=0.02,
            expected_latency_ms=1500,
            early_exit=False,
            alternative_tiers=[RouterTier.SLM_A, RouterTier.HUMAN],
            decision_metadata={"model_version": "gpt-4"}
        )
        
        assert response.selected_tier == RouterTier.LLM_A
        assert response.confidence == 0.85
        assert not response.early_exit
    
    def test_router_cost_budget_validation(self):
        """Test router cost budget validation."""
        from libs.contracts.router_spec import FeatureVector, RoutingContext
        
        features = FeatureVector(
            token_count=100,
            json_schema_strictness=0.8,
            domain_flags=["test"],
            novelty=0.3,
            historical_failure_rate=0.05,
            complexity_score=0.6,
            urgency_score=0.7,
            cost_sensitivity=0.4
        )
        
        context = RoutingContext(
            tenant_id="tenant_123",
            cost_budget_remaining=0.8
        )
        
        with pytest.raises(ContractValidationError) as exc_info:
            RouterDecisionRequest(
                input_text="Test input",
                features=features,
                context=context,
                available_tiers=[RouterTier.SLM_A],
                max_cost_usd=0.5  # Less than cost_budget_remaining
            )
        
        assert "cost_budget_remaining cannot exceed max_cost_usd" in str(exc_info.value)


class TestContractValidation:
    """Test contract validation utilities."""
    
    def test_validate_contract_success(self):
        """Test successful contract validation."""
        data = {
            "tenant_id": "tenant_123",
            "metadata": {
                "name": "test_agent",
                "version": "1.0.0",
                "description": "Test agent",
                "author": "test_author"
            },
            "capabilities": {
                "capabilities": ["text_processing"],
                "max_context_length": 4000,
                "max_output_length": 1000
            }
        }
        
        agent = validate_contract(data, AgentSpec, strict=True, forbid_extra=True)
        assert agent.tenant_id == "tenant_123"
    
    def test_validate_contract_invalid_json(self):
        """Test contract validation with invalid JSON."""
        with pytest.raises(ContractValidationError) as exc_info:
            validate_contract('{"invalid": json}', AgentSpec)
        
        assert "Invalid JSON" in str(exc_info.value)
    
    def test_validate_contract_markdown_json_detection(self):
        """Test detection of markdown-wrapped JSON."""
        data = {
            "tenant_id": "tenant_123",
            "metadata": {
                "name": "test_agent",
                "version": "1.0.0",
                "description": "Test agent with ```json{\"key\": \"value\"}``` markdown",
                "author": "test_author"
            },
            "capabilities": {
                "capabilities": ["text_processing"],
                "max_context_length": 4000,
                "max_output_length": 1000
            }
        }
        
        with pytest.raises(ContractValidationError) as exc_info:
            validate_contract(data, AgentSpec, strict=True, forbid_extra=True)
        
        assert "contains markdown-JSON" in str(exc_info.value)
    
    def test_sanitize_for_logging(self):
        """Test data sanitization for logging."""
        data = {
            "user_id": "user_123",
            "password": "secret123",
            "email": "user@example.com",
            "phone": "555-123-4567",
            "normal_field": "normal_value",
            "nested": {
                "token": "abc123",
                "safe_field": "safe_value"
            }
        }
        
        sanitized = sanitize_for_logging(data)
        
        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["email"] == "[REDACTED]"
        assert sanitized["phone"] == "[REDACTED]"
        assert sanitized["normal_field"] == "normal_value"
        assert sanitized["nested"]["token"] == "[REDACTED]"
        assert sanitized["nested"]["safe_field"] == "safe_value"
    
    def test_validate_api_request(self):
        """Test API request validation."""
        request_data = {
            "tenant_id": "tenant_123",
            "metadata": {
                "name": "test_agent",
                "version": "1.0.0",
                "description": "Test agent",
                "author": "test_author"
            },
            "capabilities": {
                "capabilities": ["text_processing"],
                "max_context_length": 4000,
                "max_output_length": 1000
            }
        }
        
        with patch('libs.contracts.validation.logger') as mock_logger:
            agent = validate_api_request(request_data, AgentSpec, "test_endpoint")
            assert agent.tenant_id == "tenant_123"
            mock_logger.info.assert_called()
    
    def test_validate_api_request_failure(self):
        """Test API request validation failure."""
        request_data = {
            "tenant_id": "",  # Invalid empty tenant_id
            "metadata": {
                "name": "test_agent",
                "version": "1.0.0",
                "description": "Test agent",
                "author": "test_author"
            },
            "capabilities": {
                "capabilities": ["text_processing"],
                "max_context_length": 4000,
                "max_output_length": 1000
            }
        }
        
        with patch('libs.contracts.validation.logger') as mock_logger:
            with pytest.raises(ContractValidationError):
                validate_api_request(request_data, AgentSpec, "test_endpoint")
            mock_logger.error.assert_called()
    
    def test_create_error_response(self):
        """Test error response creation."""
        error = ContractValidationError("Test error", [{"field": "test", "message": "error"}])
        response = create_error_response(error, 400)
        
        assert response["error"]["type"] == "contract_validation_error"
        assert response["error"]["message"] == "Test error"
        assert response["error"]["status_code"] == 400
        assert len(response["error"]["details"]) == 1


class TestContractEnforcement:
    """Test contract enforcement at service boundaries."""
    
    def test_api_gateway_contract_enforcement(self):
        """Test API Gateway contract enforcement."""
        # This would be tested with actual API Gateway endpoints
        # For now, we test the validation functions
        
        request_data = {
            "tenant_id": "tenant_123",
            "input_text": "Test input",
            "features": {
                "token_count": 50,
                "json_schema_strictness": 0.9,
                "domain_flags": ["test"],
                "novelty": 0.1,
                "historical_failure_rate": 0.02,
                "complexity_score": 0.3,
                "urgency_score": 0.5,
                "cost_sensitivity": 0.2
            },
            "context": {
                "tenant_id": "tenant_123",
                "tenant_tier": "standard"
            },
            "available_tiers": ["slm_a", "llm_a"]
        }
        
        # This should validate successfully
        router_request = validate_contract(request_data, RouterDecisionRequest, strict=True)
        assert router_request.tenant_id == "tenant_123"
    
    def test_orchestrator_contract_enforcement(self):
        """Test Orchestrator contract enforcement."""
        message_data = {
            "tenant_id": "tenant_123",
            "message_type": "user_input",
            "priority": "normal",
            "content": {
                "text": "Process this request",
                "data": None,
                "attachments": []
            },
            "metadata": {
                "source": "user_123",
                "target": "orchestrator"
            }
        }
        
        # This should validate successfully
        message = validate_contract(message_data, MessageSpec, strict=True)
        assert message.message_type == MessageType.USER_INPUT
    
    def test_tool_adapter_contract_enforcement(self):
        """Test Tool Adapter contract enforcement."""
        tool_input_data = {
            "tool_id": "tool_123",
            "parameters": {"input": "test"},
            "context": {"user_id": "user_123"},
            "timeout_seconds": 30,
            "retry_count": 2,
            "idempotency_key": "key_123"
        }
        
        # This should validate successfully
        tool_input = validate_contract(tool_input_data, ToolInput, strict=True)
        assert tool_input.tool_id == "tool_123"
        assert tool_input.parameters["input"] == "test"


@pytest.mark.asyncio
async def test_contract_validation_in_async_context():
    """Test contract validation in async context."""
    import asyncio
    
    async def async_validation():
        data = {
            "tenant_id": "tenant_123",
            "metadata": {
                "name": "async_agent",
                "version": "1.0.0",
                "description": "Async test agent",
                "author": "async_author"
            },
            "capabilities": {
                "capabilities": ["text_processing"],
                "max_context_length": 4000,
                "max_output_length": 1000
            }
        }
        
        agent = validate_contract(data, AgentSpec, strict=True, forbid_extra=True)
        return agent
    
    agent = await async_validation()
    assert agent.tenant_id == "tenant_123"
    assert agent.metadata.name == "async_agent"
