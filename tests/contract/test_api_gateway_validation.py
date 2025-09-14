"""Test API Gateway validation middleware with strict JSON contracts."""

import pytest
from unittest.mock import Mock, AsyncMock
from fastapi import Request
from fastapi.responses import JSONResponse

from libs.contracts.agent import AgentRequest, MessageSpec
from libs.contracts.router import RouterDecisionRequest, TextFeatures, HistoryStats
from libs.contracts.error import ErrorResponse
from apps.api-gateway.middleware.validation import ValidationMiddleware, create_error_response


class TestAPIGatewayValidation:
    """Test API Gateway validation middleware."""

    @pytest.fixture
    def validation_middleware(self):
        """Create validation middleware instance."""
        return ValidationMiddleware()

    @pytest.fixture
    def mock_request(self):
        """Create mock request with state."""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.tenant_id = "550e8400-e29b-41d4-a716-446655440000"
        request.state.request_id = "550e8400-e29b-41d4-a716-446655440001"
        return request

    @pytest.mark.asyncio
    async def test_validate_valid_agent_request(self, validation_middleware, mock_request):
        """Test validation of valid agent request."""
        # Mock request.json() to return valid data
        mock_request.json = AsyncMock(return_value={
            "message": {
                "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
                "content": "Hello, I need help with my order"
            },
            "agent_id": "550e8400-e29b-41d4-a716-446655440002"
        })

        result = await validation_middleware.validate_request(mock_request, AgentRequest)

        assert isinstance(result, AgentRequest)
        assert result.message.content == "Hello, I need help with my order"
        assert str(result.agent_id) == "550e8400-e29b-41d4-a716-446655440002"

    @pytest.mark.asyncio
    async def test_validate_invalid_agent_request_missing_fields(self, validation_middleware, mock_request):
        """Test validation of invalid agent request with missing fields."""
        # Mock request.json() to return invalid data (missing required fields)
        mock_request.json = AsyncMock(return_value={
            "message": {
                "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
                # Missing 'content' field
            }
            # Missing 'agent_id' field
        })

        result = await validation_middleware.validate_request(mock_request, AgentRequest)

        assert isinstance(result, ErrorResponse)
        assert result.success is False
        assert result.error.error_code == "INVALID_REQUEST"
        assert len(result.validation_errors) > 0

    @pytest.mark.asyncio
    async def test_validate_markdown_json_injection(self, validation_middleware, mock_request):
        """Test validation rejects markdown-wrapped JSON injection."""
        # Mock request.json() to return data with markdown-wrapped JSON
        mock_request.json = AsyncMock(return_value={
            "message": {
                "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
                "content": "```json\n{\"malicious\": \"injection\"}\n```"
            },
            "agent_id": "550e8400-e29b-41d4-a716-446655440002"
        })

        result = await validation_middleware.validate_request(mock_request, AgentRequest)

        assert isinstance(result, ErrorResponse)
        assert result.success is False
        assert "Markdown-wrapped JSON detected" in result.error.message

    @pytest.mark.asyncio
    async def test_validate_extra_fields_rejected(self, validation_middleware, mock_request):
        """Test validation rejects extra fields."""
        # Mock request.json() to return data with extra fields
        mock_request.json = AsyncMock(return_value={
            "message": {
                "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
                "content": "Hello, I need help with my order"
            },
            "agent_id": "550e8400-e29b-41d4-a716-446655440002",
            "malicious_field": "not_allowed"  # Extra field
        })

        result = await validation_middleware.validate_request(mock_request, AgentRequest)

        assert isinstance(result, ErrorResponse)
        assert result.success is False
        assert result.error.error_code == "INVALID_REQUEST"

    @pytest.mark.asyncio
    async def test_validate_router_decision_request(self, validation_middleware, mock_request):
        """Test validation of router decision request."""
        # Mock request.json() to return valid router decision data
        mock_request.json = AsyncMock(return_value={
            "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
            "task_id": "550e8400-e29b-41d4-a716-446655440001",
            "requirement": "Process customer support request",
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
        })

        result = await validation_middleware.validate_request(mock_request, RouterDecisionRequest)

        assert isinstance(result, RouterDecisionRequest)
        assert result.requirement == "Process customer support request"
        assert result.text_features.token_count == 100

    @pytest.mark.asyncio
    async def test_validate_router_decision_markdown_json_rejected(self, validation_middleware, mock_request):
        """Test validation rejects markdown JSON in router decision requirement."""
        # Mock request.json() to return data with markdown-wrapped JSON in requirement
        mock_request.json = AsyncMock(return_value={
            "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
            "task_id": "550e8400-e29b-41d4-a716-446655440001",
            "requirement": "```json\n{\"injection\": \"attempt\"}\n```",
            "text_features": {
                "token_count": 100,
                "json_schema_strictness": 0.8,
                "domain_flags": {},
                "novelty_score": 0.5,
                "historical_failure_rate": 0.1,
                "reasoning_keywords": [],
                "entity_count": 5,
                "format_strictness": 0.9
            },
            "history_stats": {
                "total_runs": 100,
                "success_rate": 0.95,
                "avg_latency_ms": 200,
                "avg_cost_usd": 0.01,
                "tier_distribution": {}
            }
        })

        result = await validation_middleware.validate_request(mock_request, RouterDecisionRequest)

        assert isinstance(result, ErrorResponse)
        assert result.success is False
        assert "Markdown-wrapped JSON detected" in result.error.message

    def test_create_error_response(self):
        """Test creation of standardized error response."""
        error_response = create_error_response(
            error_type="validation_error",
            error_code="INVALID_REQUEST",
            message="Request validation failed",
            status_code=400,
            details={"field": "content"},
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            request_id="550e8400-e29b-41d4-a716-446655440001"
        )

        assert isinstance(error_response, JSONResponse)
        assert error_response.status_code == 400
        
        content = error_response.body.decode('utf-8')
        assert '"success":false' in content
        assert '"error_code":"INVALID_REQUEST"' in content
        assert '"message":"Request validation failed"' in content

    @pytest.mark.asyncio
    async def test_validation_error_extraction(self, validation_middleware):
        """Test extraction of validation errors from Pydantic exceptions."""
        from pydantic import ValidationError
        
        # Create a mock ValidationError
        mock_error = Mock(spec=ValidationError)
        mock_error.errors.return_value = [
            {
                "loc": ("field1",),
                "msg": "Field required",
                "input": None,
                "type": "missing"
            },
            {
                "loc": ("field2", "subfield"),
                "msg": "Invalid value",
                "input": "invalid",
                "type": "value_error"
            }
        ]

        errors = validation_middleware._extract_validation_errors(mock_error)

        assert len(errors) == 2
        assert errors[0].field == "field1"
        assert errors[0].message == "Field required"
        assert errors[1].field == "field2.subfield"
        assert errors[1].message == "Invalid value"

    @pytest.mark.asyncio
    async def test_validate_nested_markdown_json_injection(self, validation_middleware, mock_request):
        """Test validation rejects markdown JSON in nested structures."""
        # Mock request.json() to return data with markdown-wrapped JSON in nested field
        mock_request.json = AsyncMock(return_value={
            "message": {
                "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
                "content": "Hello",
                "metadata": {
                    "nested_field": "```json\n{\"injection\": \"attempt\"}\n```"
                }
            },
            "agent_id": "550e8400-e29b-41d4-a716-446655440002"
        })

        result = await validation_middleware.validate_request(mock_request, AgentRequest)

        assert isinstance(result, ErrorResponse)
        assert result.success is False
        assert "Markdown-wrapped JSON detected" in result.error.message

    @pytest.mark.asyncio
    async def test_validate_array_markdown_json_injection(self, validation_middleware, mock_request):
        """Test validation rejects markdown JSON in arrays."""
        # Mock request.json() to return data with markdown-wrapped JSON in array
        mock_request.json = AsyncMock(return_value={
            "message": {
                "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
                "content": "Hello",
                "metadata": {
                    "array_field": [
                        "normal_value",
                        "```json\n{\"injection\": \"attempt\"}\n```"
                    ]
                }
            },
            "agent_id": "550e8400-e29b-41d4-a716-446655440002"
        })

        result = await validation_middleware.validate_request(mock_request, AgentRequest)

        assert isinstance(result, ErrorResponse)
        assert result.success is False
        assert "Markdown-wrapped JSON detected" in result.error.message
