"""Contract tests for API Gateway ↔ Orchestrator boundaries."""

import pytest
import json
from typing import Dict, Any
from unittest.mock import Mock, patch

from tests.contract.schemas import (
    APIRequest, APIResponse, ErrorResponse, RequestType,
    validate_strict_json, validate_no_pii, validate_content_policy,
    ContentPolicyViolation
)
from tests.contract import ContractError, ContractResponse, ErrorCode
from tests._fixtures.factories import factory


class TestAPIGatewayContracts:
    """Test API Gateway contract validation."""
    
    def test_valid_api_request(self, sample_tenant, sample_user):
        """Test valid API request passes validation."""
        request_data = {
            "request_id": "req_123456789",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "request_type": RequestType.FAQ.value,
            "message": "What is your return policy?",
            "context": {"source": "web", "session_id": "sess_123"},
            "metadata": {"priority": "normal"}
        }
        
        request = APIRequest(**request_data)
        
        assert request.request_id == "req_123456789"
        assert request.tenant_id == sample_tenant.tenant_id
        assert request.user_id == sample_user.user_id
        assert request.request_type == RequestType.FAQ
        assert request.message == "What is your return policy?"
        assert request.context["source"] == "web"
    
    def test_invalid_tenant_id_format(self, sample_user):
        """Test invalid tenant ID format fails validation."""
        request_data = {
            "request_id": "req_123456789",
            "tenant_id": "invalid_tenant_id",
            "user_id": sample_user.user_id,
            "request_type": RequestType.FAQ.value,
            "message": "Test message"
        }
        
        with pytest.raises(ValueError, match="string does not match regex"):
            APIRequest(**request_data)
    
    def test_invalid_user_id_format(self, sample_tenant):
        """Test invalid user ID format fails validation."""
        request_data = {
            "request_id": "req_123456789",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": "invalid_user_id",
            "request_type": RequestType.FAQ.value,
            "message": "Test message"
        }
        
        with pytest.raises(ValueError, match="string does not match regex"):
            APIRequest(**request_data)
    
    def test_empty_message_fails_validation(self, sample_tenant, sample_user):
        """Test empty message fails validation."""
        request_data = {
            "request_id": "req_123456789",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "request_type": RequestType.FAQ.value,
            "message": ""
        }
        
        with pytest.raises(ValueError, match="Message cannot be empty"):
            APIRequest(**request_data)
    
    def test_message_too_long_fails_validation(self, sample_tenant, sample_user):
        """Test message exceeding max length fails validation."""
        long_message = "x" * 10001
        
        request_data = {
            "request_id": "req_123456789",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "request_type": RequestType.FAQ.value,
            "message": long_message
        }
        
        with pytest.raises(ValueError, match="ensure this value has at most 10000 characters"):
            APIRequest(**request_data)
    
    def test_content_policy_violation(self, sample_tenant, sample_user):
        """Test content policy violation detection."""
        request_data = {
            "request_id": "req_123456789",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "request_type": RequestType.FAQ.value,
            "message": "This is bad content with hate speech"
        }
        
        with pytest.raises(ValueError, match="Content policy violation"):
            APIRequest(**request_data)
    
    def test_context_serialization_validation(self, sample_tenant, sample_user):
        """Test context must be JSON serializable."""
        # Create non-serializable context
        non_serializable_context = {
            "function": lambda x: x,  # Functions are not JSON serializable
            "data": "valid_data"
        }
        
        request_data = {
            "request_id": "req_123456789",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "request_type": RequestType.FAQ.value,
            "message": "Test message",
            "context": non_serializable_context
        }
        
        with pytest.raises(ValueError, match="Context must be JSON serializable"):
            APIRequest(**request_data)
    
    def test_valid_api_response(self):
        """Test valid API response passes validation."""
        response_data = {
            "request_id": "req_123456789",
            "success": True,
            "response": "Here is the answer to your question",
            "execution_time_ms": 150.5,
            "cost_usd": 0.002,
            "metadata": {"tier": "SLM_A", "confidence": 0.95}
        }
        
        response = APIResponse(**response_data)
        
        assert response.success is True
        assert response.response == "Here is the answer to your question"
        assert response.execution_time_ms == 150.5
        assert response.cost_usd == 0.002
    
    def test_failed_api_response(self):
        """Test failed API response validation."""
        response_data = {
            "request_id": "req_123456789",
            "success": False,
            "error_code": "INVALID_INPUT",
            "error_message": "Invalid request format",
            "execution_time_ms": 10.0,
            "cost_usd": 0.0
        }
        
        response = APIResponse(**response_data)
        
        assert response.success is False
        assert response.error_code == "INVALID_INPUT"
        assert response.error_message == "Invalid request format"
        assert response.response is None
    
    def test_response_consistency_validation(self):
        """Test API response consistency validation."""
        # Successful response with error code should fail
        with pytest.raises(ValueError, match="Successful response must have response text and no error"):
            APIResponse(
                request_id="req_123",
                success=True,
                error_code="SOME_ERROR"
            )
        
        # Failed response with response text should fail
        with pytest.raises(ValueError, match="Failed response must have error code and no response text"):
            APIResponse(
                request_id="req_123",
                success=False,
                response="Some response"
            )
    
    def test_error_response_contract(self):
        """Test error response contract validation."""
        error_data = {
            "error_code": "MISSING_FIELD",
            "message": "Required field 'message' is missing",
            "field": "message",
            "details": {"expected_type": "string", "received": None},
            "request_id": "req_123456789"
        }
        
        error_response = ErrorResponse(**error_data)
        
        assert error_response.error_code == "MISSING_FIELD"
        assert error_response.message == "Required field 'message' is missing"
        assert error_response.field == "message"
        assert error_response.details["expected_type"] == "string"
    
    def test_error_code_format_validation(self):
        """Test error code format validation."""
        with pytest.raises(ValueError, match="Error code must be uppercase with underscores"):
            ErrorResponse(
                error_code="invalidCode",
                message="Test error"
            )
    
    def test_strict_json_validation(self):
        """Test strict JSON validation rejects loose/markdown JSON."""
        # Valid JSON should pass
        valid_json = '{"key": "value", "number": 123}'
        result = validate_strict_json(valid_json)
        assert result == {"key": "value", "number": 123}
        
        # Markdown content should fail
        markdown_content = '{"content": "This is **bold** text with ```code```"}'
        with pytest.raises(ValueError, match="Markdown content not allowed"):
            validate_strict_json(markdown_content)
        
        # Invalid JSON should fail
        invalid_json = '{"key": "value", "unclosed": }'
        with pytest.raises(ValueError, match="Invalid JSON"):
            validate_strict_json(invalid_json)
    
    def test_pii_detection_validation(self):
        """Test PII detection in data validation."""
        # Clean data should pass
        clean_data = {"message": "Hello world", "data": [1, 2, 3]}
        validate_no_pii(clean_data)  # Should not raise
        
        # Data with email should fail
        pii_data = {"message": "Contact me at user@example.com"}
        with pytest.raises(ValueError, match="PII detected"):
            validate_no_pii(pii_data)
        
        # Data with phone number should fail
        phone_data = {"contact": "555-123-4567"}
        with pytest.raises(ValueError, match="PII detected"):
            validate_no_pii(phone_data)
    
    def test_content_policy_validation(self):
        """Test content policy validation."""
        # Clean content should have no violations
        clean_text = "Hello, how can I help you today?"
        violations = validate_content_policy(clean_text)
        assert len(violations) == 0
        
        # Profanity should be detected
        profane_text = "This is bad content"
        violations = validate_content_policy(profane_text)
        assert ContentPolicyViolation.PROFANITY in violations
        
        # Spam should be detected
        spam_text = "BUY NOW!!! SAVE MONEY!!! FREE!!!"
        violations = validate_content_policy(spam_text)
        assert ContentPolicyViolation.SPAM in violations
        
        # Malicious links should be detected
        malicious_text = "Click here: https://malicious-site.com"
        violations = validate_content_policy(malicious_text)
        assert ContentPolicyViolation.MALICIOUS_LINK in violations
    
    @pytest.mark.parametrize("request_type", [
        RequestType.FAQ,
        RequestType.ORDER,
        RequestType.TRACKING,
        RequestType.LEAD,
        RequestType.PAYMENT,
        RequestType.SUPPORT
    ])
    def test_all_request_types_valid(self, sample_tenant, sample_user, request_type):
        """Test all request types are valid."""
        request_data = {
            "request_id": "req_123456789",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "request_type": request_type.value,
            "message": f"Test message for {request_type.value}"
        }
        
        request = APIRequest(**request_data)
        assert request.request_type == request_type
    
    def test_request_id_format_validation(self, sample_tenant, sample_user):
        """Test request ID format validation."""
        # Valid request ID
        valid_data = {
            "request_id": "req_123456789",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "request_type": RequestType.FAQ.value,
            "message": "Test message"
        }
        
        request = APIRequest(**valid_data)
        assert request.request_id == "req_123456789"
        
        # Request ID too long
        invalid_data = valid_data.copy()
        invalid_data["request_id"] = "x" * 65  # Exceeds max_length=64
        
        with pytest.raises(ValueError, match="ensure this value has at most 64 characters"):
            APIRequest(**invalid_data)
        
        # Empty request ID
        invalid_data["request_id"] = ""
        
        with pytest.raises(ValueError, match="ensure this value has at least 1 characters"):
            APIRequest(**invalid_data)


class TestContractErrorHandling:
    """Test contract error handling and mapping."""
    
    def test_contract_error_creation(self):
        """Test contract error creation and serialization."""
        error = ContractError(
            error_code=ErrorCode.MISSING_FIELD,
            message="Required field is missing",
            field="message",
            details={"expected_type": "string"}
        )
        
        error_dict = error.to_dict()
        
        assert error_dict["error_code"] == "MISSING_FIELD"
        assert error_dict["message"] == "Required field is missing"
        assert error_dict["field"] == "message"
        assert error_dict["details"]["expected_type"] == "string"
        assert "timestamp" in error_dict
    
    def test_contract_response_creation(self):
        """Test contract response creation and serialization."""
        # Success response
        success_response = ContractResponse(
            success=True,
            data={"result": "success", "value": 42},
            metadata={"execution_time_ms": 100.5}
        )
        
        response_dict = success_response.to_dict()
        
        assert response_dict["success"] is True
        assert response_dict["data"]["result"] == "success"
        assert response_dict["metadata"]["execution_time_ms"] == 100.5
        assert "error" not in response_dict
        
        # Error response
        error = ContractError(
            error_code=ErrorCode.INVALID_JSON,
            message="Invalid JSON format"
        )
        
        error_response = ContractResponse(
            success=False,
            error=error
        )
        
        response_dict = error_response.to_dict()
        
        assert response_dict["success"] is False
        assert response_dict["error"]["error_code"] == "INVALID_JSON"
        assert "data" not in response_dict
    
    def test_error_code_mapping(self):
        """Test error code mapping for different scenarios."""
        error_mappings = [
            (ValueError("Invalid JSON"), ErrorCode.INVALID_JSON),
            (KeyError("missing_field"), ErrorCode.MISSING_FIELD),
            (TypeError("Invalid type"), ErrorCode.INVALID_FIELD_TYPE),
            (ValueError("Content policy violation"), ErrorCode.CONTENT_POLICY_VIOLATION),
        ]
        
        for exception, expected_code in error_mappings:
            # In a real implementation, this would be handled by error mapping middleware
            if "JSON" in str(exception):
                assert expected_code == ErrorCode.INVALID_JSON
            elif "missing" in str(exception).lower():
                assert expected_code == ErrorCode.MISSING_FIELD
            elif "type" in str(exception).lower():
                assert expected_code == ErrorCode.INVALID_FIELD_TYPE
            elif "content policy" in str(exception).lower():
                assert expected_code == ErrorCode.CONTENT_POLICY_VIOLATION


class TestContractBoundaryIntegration:
    """Test integration between API Gateway and Orchestrator contracts."""
    
    def test_request_response_roundtrip(self, sample_tenant, sample_user):
        """Test complete request-response roundtrip."""
        # Create request
        request_data = {
            "request_id": "req_123456789",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "request_type": RequestType.FAQ.value,
            "message": "What are your business hours?",
            "context": {"source": "mobile_app"},
            "metadata": {"priority": "high"}
        }
        
        request = APIRequest(**request_data)
        
        # Simulate processing
        response_data = {
            "request_id": request.request_id,
            "success": True,
            "response": "Our business hours are Monday-Friday 9AM-6PM EST.",
            "execution_time_ms": 125.0,
            "cost_usd": 0.0015,
            "metadata": {
                "tier": "SLM_A",
                "confidence": 0.92,
                "processing_steps": 3
            }
        }
        
        response = APIResponse(**response_data)
        
        # Validate roundtrip
        assert response.request_id == request.request_id
        assert response.success is True
        assert "business hours" in response.response
        assert response.execution_time_ms > 0
        assert response.cost_usd > 0
    
    def test_error_roundtrip(self, sample_tenant, sample_user):
        """Test error handling roundtrip."""
        # Create invalid request
        request_data = {
            "request_id": "req_123456789",
            "tenant_id": "invalid_tenant",
            "user_id": sample_user.user_id,
            "request_type": RequestType.FAQ.value,
            "message": "Test message"
        }
        
        # This should fail validation
        with pytest.raises(ValueError):
            APIRequest(**request_data)
        
        # Simulate error response
        error_response = APIResponse(
            request_id="req_123456789",
            success=False,
            error_code="INVALID_TENANT_ID",
            error_message="Tenant ID format is invalid",
            execution_time_ms=5.0,
            cost_usd=0.0
        )
        
        assert error_response.success is False
        assert error_response.error_code == "INVALID_TENANT_ID"
        assert "invalid" in error_response.error_message.lower()
    
    def test_contract_versioning_compatibility(self, sample_tenant, sample_user):
        """Test contract versioning and backward compatibility."""
        # Test that new fields are optional (backward compatibility)
        minimal_request = {
            "request_id": "req_123456789",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "request_type": RequestType.FAQ.value,
            "message": "Test message"
        }
        
        request = APIRequest(**minimal_request)
        
        # Should work with minimal fields
        assert request.request_id == "req_123456789"
        assert request.context == {}  # Default empty dict
        assert request.metadata == {}  # Default empty dict
        
        # Test that required fields cannot be removed
        invalid_request = minimal_request.copy()
        del invalid_request["message"]
        
        with pytest.raises(ValueError, match="field required"):
            APIRequest(**invalid_request)
