"""Contract tests for Router ↔ Tool boundaries."""

import pytest
import json
from typing import Dict, Any, List
from unittest.mock import Mock, patch

from tests.contract.schemas import (
    ToolRequest, ToolResponse, ToolStatus,
    validate_strict_json, validate_no_pii
)
from tests.contract import ContractError, ContractResponse, ErrorCode
from tests._fixtures.factories import factory


class TestToolRequestContracts:
    """Test Tool request contract validation."""
    
    def test_valid_tool_request(self, sample_tenant, sample_user):
        """Test valid tool request passes validation."""
        request_data = {
            "tool_id": "tool_faq_search",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "request_id": "req_123456789",
            "parameters": {
                "query": "return policy",
                "limit": 5,
                "filters": {"category": "shipping"}
            },
            "timeout_ms": 30000,
            "retry_count": 0,
            "idempotency_key": "idem_123456789"
        }
        
        request = ToolRequest(**request_data)
        
        assert request.tool_id == "tool_faq_search"
        assert request.tenant_id == sample_tenant.tenant_id
        assert request.user_id == sample_user.user_id
        assert request.request_id == "req_123456789"
        assert request.parameters["query"] == "return policy"
        assert request.timeout_ms == 30000
        assert request.retry_count == 0
        assert request.idempotency_key == "idem_123456789"
    
    def test_tool_id_format_validation(self, sample_tenant, sample_user):
        """Test tool ID format validation."""
        # Valid tool IDs
        valid_tool_ids = [
            "tool_faq_search",
            "tool_order_create",
            "tool_payment_process",
            "tool_document_search",
            "tool_email_send"
        ]
        
        for tool_id in valid_tool_ids:
            request_data = {
                "tool_id": tool_id,
                "tenant_id": sample_tenant.tenant_id,
                "user_id": sample_user.user_id,
                "request_id": "req_123456789",
                "parameters": {}
            }
            
            request = ToolRequest(**request_data)
            assert request.tool_id == tool_id
        
        # Invalid tool IDs
        invalid_tool_ids = [
            "invalid_tool",  # Doesn't start with tool_
            "tool-123",      # Contains hyphens
            "tool_",         # Empty after tool_
            "tool_123ABC",   # Contains uppercase
            "Tool_faq"       # Starts with uppercase
        ]
        
        for tool_id in invalid_tool_ids:
            request_data = {
                "tool_id": tool_id,
                "tenant_id": sample_tenant.tenant_id,
                "user_id": sample_user.user_id,
                "request_id": "req_123456789",
                "parameters": {}
            }
            
            with pytest.raises(ValueError, match="string does not match regex"):
                ToolRequest(**request_data)
    
    def test_parameters_serialization_validation(self, sample_tenant, sample_user):
        """Test parameters must be JSON serializable."""
        # Valid parameters
        valid_parameters = {
            "query": "search term",
            "limit": 10,
            "filters": {"category": "faq"},
            "nested": {"deep": {"value": 42}}
        }
        
        request_data = {
            "tool_id": "tool_faq_search",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "request_id": "req_123456789",
            "parameters": valid_parameters
        }
        
        request = ToolRequest(**request_data)
        assert request.parameters == valid_parameters
        
        # Invalid parameters - non-serializable
        invalid_parameters = {
            "function": lambda x: x,  # Functions are not JSON serializable
            "data": "valid_data"
        }
        
        request_data["parameters"] = invalid_parameters
        
        with pytest.raises(ValueError, match="Parameters must be JSON serializable"):
            ToolRequest(**request_data)
    
    def test_timeout_range_validation(self, sample_tenant, sample_user):
        """Test timeout must be between 1000 and 300000 ms."""
        # Valid timeouts
        valid_timeouts = [1000, 5000, 30000, 60000, 300000]
        
        for timeout in valid_timeouts:
            request_data = {
                "tool_id": "tool_faq_search",
                "tenant_id": sample_tenant.tenant_id,
                "user_id": sample_user.user_id,
                "request_id": "req_123456789",
                "parameters": {},
                "timeout_ms": timeout
            }
            
            request = ToolRequest(**request_data)
            assert request.timeout_ms == timeout
        
        # Invalid timeouts
        invalid_timeouts = [500, 999, 300001, 600000]
        
        for timeout in invalid_timeouts:
            request_data = {
                "tool_id": "tool_faq_search",
                "tenant_id": sample_tenant.tenant_id,
                "user_id": sample_user.user_id,
                "request_id": "req_123456789",
                "parameters": {},
                "timeout_ms": timeout
            }
            
            with pytest.raises(ValueError, match="ensure this value is greater than or equal to 1000"):
                ToolRequest(**request_data)
    
    def test_retry_count_validation(self, sample_tenant, sample_user):
        """Test retry count must be between 0 and 3."""
        # Valid retry counts
        valid_retry_counts = [0, 1, 2, 3]
        
        for retry_count in valid_retry_counts:
            request_data = {
                "tool_id": "tool_faq_search",
                "tenant_id": sample_tenant.tenant_id,
                "user_id": sample_user.user_id,
                "request_id": "req_123456789",
                "parameters": {},
                "retry_count": retry_count
            }
            
            request = ToolRequest(**request_data)
            assert request.retry_count == retry_count
        
        # Invalid retry counts
        invalid_retry_counts = [-1, 4, 10]
        
        for retry_count in invalid_retry_counts:
            request_data = {
                "tool_id": "tool_faq_search",
                "tenant_id": sample_tenant.tenant_id,
                "user_id": sample_user.user_id,
                "request_id": "req_123456789",
                "parameters": {},
                "retry_count": retry_count
            }
            
            with pytest.raises(ValueError, match="ensure this value is greater than or equal to 0"):
                ToolRequest(**request_data)
    
    def test_idempotency_key_validation(self, sample_tenant, sample_user):
        """Test idempotency key format validation."""
        # Valid idempotency keys
        valid_keys = [
            "idem_123456789",
            "req_abc123def456",
            "tool_call_xyz789",
            None  # Optional field
        ]
        
        for key in valid_keys:
            request_data = {
                "tool_id": "tool_faq_search",
                "tenant_id": sample_tenant.tenant_id,
                "user_id": sample_user.user_id,
                "request_id": "req_123456789",
                "parameters": {},
                "idempotency_key": key
            }
            
            request = ToolRequest(**request_data)
            assert request.idempotency_key == key
        
        # Invalid idempotency keys
        invalid_keys = [
            "x" * 129,  # Too long (max 128)
            "",         # Empty string
            "key with spaces",  # Contains spaces
            "key-with-dashes"   # Contains dashes (if not allowed)
        ]
        
        for key in invalid_keys:
            request_data = {
                "tool_id": "tool_faq_search",
                "tenant_id": sample_tenant.tenant_id,
                "user_id": sample_user.user_id,
                "request_id": "req_123456789",
                "parameters": {},
                "idempotency_key": key
            }
            
            with pytest.raises(ValueError):
                ToolRequest(**request_data)


class TestToolResponseContracts:
    """Test Tool response contract validation."""
    
    def test_valid_tool_response(self):
        """Test valid tool response passes validation."""
        response_data = {
            "tool_id": "tool_faq_search",
            "request_id": "req_123456789",
            "status": ToolStatus.COMPLETED,
            "result": {
                "matches": [
                    {"id": "faq_1", "title": "Return Policy", "content": "30 day return policy"},
                    {"id": "faq_2", "title": "Shipping Info", "content": "Free shipping on orders over $50"}
                ],
                "total_count": 2
            },
            "execution_time_ms": 125.5,
            "cost_usd": 0.002,
            "metadata": {
                "search_terms": ["return", "policy"],
                "confidence": 0.95
            }
        }
        
        response = ToolResponse(**response_data)
        
        assert response.tool_id == "tool_faq_search"
        assert response.request_id == "req_123456789"
        assert response.status == ToolStatus.COMPLETED
        assert response.result["total_count"] == 2
        assert response.execution_time_ms == 125.5
        assert response.cost_usd == 0.002
        assert response.metadata["confidence"] == 0.95
    
    def test_failed_tool_response(self):
        """Test failed tool response validation."""
        response_data = {
            "tool_id": "tool_faq_search",
            "request_id": "req_123456789",
            "status": ToolStatus.FAILED,
            "error": "Database connection timeout",
            "execution_time_ms": 30000.0,  # Hit timeout
            "cost_usd": 0.001,  # Partial cost for failed execution
            "metadata": {
                "error_type": "timeout",
                "retry_attempts": 3
            }
        }
        
        response = ToolResponse(**response_data)
        
        assert response.status == ToolStatus.FAILED
        assert response.error == "Database connection timeout"
        assert response.result is None
        assert response.execution_time_ms == 30000.0
    
    def test_response_consistency_validation(self):
        """Test tool response consistency validation."""
        # Completed status with error should fail
        with pytest.raises(ValueError, match="Completed tool must have result and no error"):
            ToolResponse(
                tool_id="tool_faq_search",
                request_id="req_123456789",
                status=ToolStatus.COMPLETED,
                error="Some error"
            )
        
        # Completed status without result should fail
        with pytest.raises(ValueError, match="Completed tool must have result and no error"):
            ToolResponse(
                tool_id="tool_faq_search",
                request_id="req_123456789",
                status=ToolStatus.COMPLETED,
                result=None
            )
        
        # Failed status with result should fail
        with pytest.raises(ValueError, match="Failed tool must have error and no result"):
            ToolResponse(
                tool_id="tool_faq_search",
                request_id="req_123456789",
                status=ToolStatus.FAILED,
                result={"data": "some result"}
            )
        
        # Failed status without error should fail
        with pytest.raises(ValueError, match="Failed tool must have error and no result"):
            ToolResponse(
                tool_id="tool_faq_search",
                request_id="req_123456789",
                status=ToolStatus.FAILED,
                error=None
            )
    
    def test_execution_time_validation(self):
        """Test execution time must be non-negative."""
        # Valid execution times
        valid_times = [0.0, 10.5, 100.0, 30000.0]
        
        for time_ms in valid_times:
            response_data = {
                "tool_id": "tool_faq_search",
                "request_id": "req_123456789",
                "status": ToolStatus.COMPLETED,
                "result": {"data": "test"},
                "execution_time_ms": time_ms,
                "cost_usd": 0.002
            }
            
            response = ToolResponse(**response_data)
            assert response.execution_time_ms == time_ms
        
        # Invalid execution times
        invalid_times = [-1.0, -100.0]
        
        for time_ms in invalid_times:
            response_data = {
                "tool_id": "tool_faq_search",
                "request_id": "req_123456789",
                "status": ToolStatus.COMPLETED,
                "result": {"data": "test"},
                "execution_time_ms": time_ms,
                "cost_usd": 0.002
            }
            
            with pytest.raises(ValueError, match="ensure this value is greater than or equal to 0.0"):
                ToolResponse(**response_data)
    
    def test_cost_validation(self):
        """Test cost must be non-negative."""
        # Valid costs
        valid_costs = [0.0, 0.001, 0.01, 0.1, 1.0]
        
        for cost in valid_costs:
            response_data = {
                "tool_id": "tool_faq_search",
                "request_id": "req_123456789",
                "status": ToolStatus.COMPLETED,
                "result": {"data": "test"},
                "execution_time_ms": 100.0,
                "cost_usd": cost
            }
            
            response = ToolResponse(**response_data)
            assert response.cost_usd == cost
        
        # Invalid costs
        invalid_costs = [-0.001, -1.0]
        
        for cost in invalid_costs:
            response_data = {
                "tool_id": "tool_faq_search",
                "request_id": "req_123456789",
                "status": ToolStatus.COMPLETED,
                "result": {"data": "test"},
                "execution_time_ms": 100.0,
                "cost_usd": cost
            }
            
            with pytest.raises(ValueError, match="ensure this value is greater than or equal to 0.0"):
                ToolResponse(**response_data)


class TestToolStatusContracts:
    """Test tool status contract validation."""
    
    @pytest.mark.parametrize("status", [
        ToolStatus.PENDING,
        ToolStatus.RUNNING,
        ToolStatus.COMPLETED,
        ToolStatus.FAILED,
        ToolStatus.CANCELLED
    ])
    def test_all_tool_statuses_valid(self, status):
        """Test all tool statuses are valid in responses."""
        response_data = {
            "tool_id": "tool_faq_search",
            "request_id": "req_123456789",
            "status": status,
            "execution_time_ms": 100.0,
            "cost_usd": 0.002
        }
        
        # Add required fields based on status
        if status == ToolStatus.COMPLETED:
            response_data["result"] = {"data": "test"}
        elif status == ToolStatus.FAILED:
            response_data["error"] = "Test error"
        
        response = ToolResponse(**response_data)
        assert response.status == status
    
    def test_status_transition_validation(self):
        """Test tool status transition validation."""
        # Pending -> Running -> Completed (valid transition)
        statuses = [ToolStatus.PENDING, ToolStatus.RUNNING, ToolStatus.COMPLETED]
        
        for i, status in enumerate(statuses):
            response_data = {
                "tool_id": "tool_faq_search",
                "request_id": "req_123456789",
                "status": status,
                "execution_time_ms": 100.0,
                "cost_usd": 0.002
            }
            
            if status == ToolStatus.COMPLETED:
                response_data["result"] = {"data": "test"}
            
            response = ToolResponse(**response_data)
            assert response.status == status
        
        # Pending -> Failed (valid transition)
        response_data = {
            "tool_id": "tool_faq_search",
            "request_id": "req_123456789",
            "status": ToolStatus.FAILED,
            "error": "Connection failed",
            "execution_time_ms": 100.0,
            "cost_usd": 0.001
        }
        
        response = ToolResponse(**response_data)
        assert response.status == ToolStatus.FAILED


class TestToolContractIntegration:
    """Test tool contract integration scenarios."""
    
    def test_request_response_matching(self, sample_tenant, sample_user):
        """Test that tool request and response IDs match."""
        # Create tool request
        request_data = {
            "tool_id": "tool_faq_search",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "request_id": "req_123456789",
            "parameters": {
                "query": "return policy",
                "limit": 5
            },
            "timeout_ms": 30000,
            "retry_count": 0,
            "idempotency_key": "idem_123456789"
        }
        
        request = ToolRequest(**request_data)
        
        # Create matching response
        response_data = {
            "tool_id": request.tool_id,  # Must match
            "request_id": request.request_id,  # Must match
            "status": ToolStatus.COMPLETED,
            "result": {
                "matches": [
                    {"id": "faq_1", "title": "Return Policy", "content": "30 day return policy"}
                ],
                "total_count": 1
            },
            "execution_time_ms": 125.5,
            "cost_usd": 0.002,
            "metadata": {
                "search_terms": ["return", "policy"],
                "idempotency_key": request.idempotency_key
            }
        }
        
        response = ToolResponse(**response_data)
        
        # Validate matching
        assert response.tool_id == request.tool_id
        assert response.request_id == request.request_id
        assert response.metadata["idempotency_key"] == request.idempotency_key
    
    def test_tool_parameter_passthrough(self, sample_tenant, sample_user):
        """Test that tool parameters are correctly passed through."""
        # Create request with specific parameters
        parameters = {
            "query": "shipping information",
            "limit": 10,
            "filters": {
                "category": "shipping",
                "language": "en"
            },
            "sort_by": "relevance"
        }
        
        request_data = {
            "tool_id": "tool_faq_search",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "request_id": "req_123456789",
            "parameters": parameters
        }
        
        request = ToolRequest(**request_data)
        
        # Response should reflect the parameters used
        response_data = {
            "tool_id": request.tool_id,
            "request_id": request.request_id,
            "status": ToolStatus.COMPLETED,
            "result": {
                "matches": [
                    {"id": "faq_1", "title": "Shipping Info", "content": "Free shipping on orders over $50"}
                ],
                "total_count": 1,
                "search_params": parameters  # Echo back parameters used
            },
            "execution_time_ms": 125.5,
            "cost_usd": 0.002,
            "metadata": {
                "parameters_used": parameters,
                "search_effectiveness": 0.95
            }
        }
        
        response = ToolResponse(**response_data)
        
        # Validate parameter passthrough
        assert response.result["search_params"] == parameters
        assert response.metadata["parameters_used"] == parameters
    
    def test_tool_timeout_handling(self, sample_tenant, sample_user):
        """Test tool timeout handling in contracts."""
        # Request with short timeout
        request_data = {
            "tool_id": "tool_slow_operation",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "request_id": "req_123456789",
            "parameters": {"operation": "heavy_computation"},
            "timeout_ms": 5000  # 5 second timeout
        }
        
        request = ToolRequest(**request_data)
        
        # Response indicating timeout
        response_data = {
            "tool_id": request.tool_id,
            "request_id": request.request_id,
            "status": ToolStatus.FAILED,
            "error": f"Operation timed out after {request.timeout_ms}ms",
            "execution_time_ms": float(request.timeout_ms),  # Hit timeout
            "cost_usd": 0.001,  # Partial cost
            "metadata": {
                "timeout_occurred": True,
                "timeout_limit_ms": request.timeout_ms,
                "partial_result_available": False
            }
        }
        
        response = ToolResponse(**response_data)
        
        # Validate timeout handling
        assert response.status == ToolStatus.FAILED
        assert "timed out" in response.error
        assert response.execution_time_ms == float(request.timeout_ms)
        assert response.metadata["timeout_occurred"] is True
    
    def test_tool_retry_handling(self, sample_tenant, sample_user):
        """Test tool retry handling in contracts."""
        # Request with retry count
        request_data = {
            "tool_id": "tool_unreliable_service",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "request_id": "req_123456789",
            "parameters": {"service": "external_api"},
            "retry_count": 2
        }
        
        request = ToolRequest(**request_data)
        
        # Response after retries
        response_data = {
            "tool_id": request.tool_id,
            "request_id": request.request_id,
            "status": ToolStatus.COMPLETED,
            "result": {"data": "success after retries"},
            "execution_time_ms": 2500.0,  # Total time including retries
            "cost_usd": 0.003,  # Cost including retry attempts
            "metadata": {
                "retry_attempts": request.retry_count,
                "initial_failures": 2,
                "final_success": True,
                "total_attempts": 3  # Initial + 2 retries
            }
        }
        
        response = ToolResponse(**response_data)
        
        # Validate retry handling
        assert response.status == ToolStatus.COMPLETED
        assert response.metadata["retry_attempts"] == request.retry_count
        assert response.metadata["initial_failures"] == 2
        assert response.metadata["final_success"] is True
    
    def test_tool_idempotency_handling(self, sample_tenant, sample_user):
        """Test tool idempotency handling in contracts."""
        idempotency_key = "idem_unique_key_123"
        
        # First request
        request_data = {
            "tool_id": "tool_idempotent_operation",
            "tenant_id": sample_tenant.tenant_id,
            "user_id": sample_user.user_id,
            "request_id": "req_first",
            "parameters": {"operation": "create_order"},
            "idempotency_key": idempotency_key
        }
        
        request1 = ToolRequest(**request_data)
        
        # First response
        response1_data = {
            "tool_id": request1.tool_id,
            "request_id": request1.request_id,
            "status": ToolStatus.COMPLETED,
            "result": {"order_id": "order_123", "status": "created"},
            "execution_time_ms": 200.0,
            "cost_usd": 0.002,
            "metadata": {
                "idempotency_key": idempotency_key,
                "operation_type": "create",
                "duplicate_detected": False
            }
        }
        
        response1 = ToolResponse(**response1_data)
        
        # Second request with same idempotency key
        request_data["request_id"] = "req_second"
        request2 = ToolRequest(**request_data)
        
        # Second response (should detect duplicate)
        response2_data = {
            "tool_id": request2.tool_id,
            "request_id": request2.request_id,
            "status": ToolStatus.COMPLETED,
            "result": {"order_id": "order_123", "status": "created"},  # Same result
            "execution_time_ms": 5.0,  # Much faster due to idempotency
            "cost_usd": 0.0,  # No cost for duplicate
            "metadata": {
                "idempotency_key": idempotency_key,
                "operation_type": "duplicate_detected",
                "duplicate_detected": True,
                "original_request_id": "req_first"
            }
        }
        
        response2 = ToolResponse(**response2_data)
        
        # Validate idempotency handling
        assert response1.result == response2.result  # Same result
        assert response2.metadata["duplicate_detected"] is True
        assert response2.metadata["original_request_id"] == "req_first"
        assert response2.execution_time_ms < response1.execution_time_ms
        assert response2.cost_usd == 0.0  # No cost for duplicate
