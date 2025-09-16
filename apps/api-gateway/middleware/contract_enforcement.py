"""
Contract Enforcement for API Gateway

Enforces strict contracts at API Gateway boundaries with structured error responses.
"""

from typing import Dict, Any, Optional, List
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
import structlog

from libs.contracts.validation import ContractValidationError, create_error_response
from libs.contracts import (
    AgentSpec, MessageSpec, ToolInput, RouterDecisionRequest,
    RouterDecisionResponse, ErrorSpec
)

logger = structlog.get_logger(__name__)


class APIGatewayContractEnforcer:
    """Enforces contracts at API Gateway boundaries."""
    
    def __init__(self):
        self.request_contracts = self._initialize_request_contracts()
        self.response_contracts = self._initialize_response_contracts()
        
        logger.info("API Gateway contract enforcer initialized",
                   request_endpoints=len(self.request_contracts),
                   response_endpoints=len(self.response_contracts))
    
    def _initialize_request_contracts(self) -> Dict[str, Any]:
        """Initialize request contracts for API endpoints."""
        return {
            "POST:/api/v1/agents": AgentSpec,
            "PUT:/api/v1/agents/{agent_id}": AgentSpec,
            "POST:/api/v1/messages": MessageSpec,
            "POST:/api/v1/tools/execute": ToolInput,
            "POST:/api/v1/router/decide": RouterDecisionRequest,
            "POST:/api/v1/workflows/execute": MessageSpec,
            "POST:/api/v1/analytics/query": MessageSpec,
            "POST:/api/v1/chat/send": MessageSpec,
        }
    
    def _initialize_response_contracts(self) -> Dict[str, Any]:
        """Initialize response contracts for API endpoints."""
        return {
            "POST:/api/v1/router/decide": RouterDecisionResponse,
            "POST:/api/v1/tools/execute": "ToolOutput",
            "GET:/api/v1/agents/{agent_id}": AgentSpec,
            "GET:/api/v1/messages/{message_id}": MessageSpec,
            "POST:/api/v1/workflows/execute": "WorkflowResult",
            "POST:/api/v1/analytics/query": "AnalyticsResult",
            "POST:/api/v1/chat/send": "ChatResponse",
        }
    
    def validate_request(self, method: str, path: str, data: Dict[str, Any]) -> Any:
        """Validate request data against contract."""
        endpoint_key = f"{method}:{path}"
        
        if endpoint_key not in self.request_contracts:
            logger.warning("No contract defined for endpoint", endpoint=endpoint_key)
            return data
        
        contract_class = self.request_contracts[endpoint_key]
        
        try:
            from libs.contracts.validation import validate_contract
            validated_data = validate_contract(data, contract_class, strict=True, forbid_extra=True)
            
            logger.info("Request validation successful", 
                       endpoint=endpoint_key,
                       contract_class=contract_class.__name__)
            
            return validated_data
            
        except ContractValidationError as e:
            logger.error("Request validation failed", 
                        endpoint=endpoint_key,
                        contract_class=contract_class.__name__,
                        errors=e.errors)
            
            # Return structured error response
            error_response = create_error_response(e, status.HTTP_422_UNPROCESSABLE_ENTITY)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=error_response
            )
        
        except Exception as e:
            logger.error("Unexpected validation error", 
                        endpoint=endpoint_key,
                        error=str(e))
            
            error_spec = ErrorSpec(
                error_code="VALIDATION_ERROR",
                severity="HIGH",
                category="VALIDATION",
                details={
                    "message": f"Unexpected validation error: {str(e)}",
                    "technical_message": str(e)
                },
                context={
                    "component": "api_gateway",
                    "operation": "request_validation"
                }
            )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": {
                        "type": "internal_validation_error",
                        "message": "Internal validation error occurred",
                        "status_code": 500,
                        "details": error_spec.dict()
                    }
                }
            )
    
    def validate_response(self, method: str, path: str, data: Any) -> Any:
        """Validate response data against contract."""
        endpoint_key = f"{method}:{path}"
        
        if endpoint_key not in self.response_contracts:
            return data
        
        contract_class = self.response_contracts[endpoint_key]
        
        try:
            from libs.contracts.validation import validate_contract
            
            # Handle string contract references
            if isinstance(contract_class, str):
                if contract_class == "ToolOutput":
                    from libs.contracts.tool_spec import ToolOutput
                    contract_class = ToolOutput
                elif contract_class == "WorkflowResult":
                    # Define WorkflowResult contract inline for now
                    contract_class = type('WorkflowResult', (), {})
                # Add other string-based contract mappings as needed
            
            validated_data = validate_contract(data, contract_class, strict=True, forbid_extra=True)
            
            logger.info("Response validation successful", 
                       endpoint=endpoint_key,
                       contract_class=contract_class.__name__)
            
            return validated_data
            
        except ContractValidationError as e:
            logger.error("Response validation failed", 
                        endpoint=endpoint_key,
                        contract_class=contract_class.__name__,
                        errors=e.errors)
            
            # Don't fail the response, just log the error
            # In production, you might want to fail fast on response validation errors
            return data
        
        except Exception as e:
            logger.error("Unexpected response validation error", 
                        endpoint=endpoint_key,
                        error=str(e))
            
            return data
    
    def create_validation_error_response(self, error: ContractValidationError) -> JSONResponse:
        """Create standardized validation error response."""
        error_response = create_error_response(error, status.HTTP_422_UNPROCESSABLE_ENTITY)
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response
        )
    
    def create_pii_redaction_error_response(self, field_name: str) -> JSONResponse:
        """Create error response for PII detection."""
        error_spec = ErrorSpec(
            error_code="VALIDATION_ERROR",
            severity="HIGH",
            category="VALIDATION",
            details={
                "message": f"PII detected in field: {field_name}",
                "technical_message": "Personal identifiable information detected in request",
                "suggestions": [
                    "Remove or redact PII from the request",
                    "Use appropriate data anonymization techniques"
                ]
            },
            context={
                "component": "api_gateway",
                "operation": "pii_detection"
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "type": "pii_detection_error",
                    "message": "PII detected in request",
                    "status_code": 422,
                    "details": error_spec.dict()
                }
            }
        )
    
    def validate_extra_fields(self, data: Dict[str, Any], allowed_fields: List[str]) -> None:
        """Validate that no extra fields are present."""
        extra_fields = set(data.keys()) - set(allowed_fields)
        
        if extra_fields:
            error_spec = ErrorSpec(
                error_code="VALIDATION_ERROR",
                severity="MEDIUM",
                category="VALIDATION",
                details={
                    "message": f"Extra fields not allowed: {', '.join(extra_fields)}",
                    "technical_message": "Request contains fields that are not permitted",
                    "suggestions": [
                        "Remove extra fields from the request",
                        "Check API documentation for allowed fields"
                    ]
                },
                context={
                    "component": "api_gateway",
                    "operation": "extra_field_validation"
                }
            )
            
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": {
                        "type": "extra_fields_error",
                        "message": "Extra fields not allowed",
                        "status_code": 422,
                        "details": error_spec.dict()
                    }
                }
            )
    
    def validate_markdown_json(self, data: Any, path: str = "") -> None:
        """Validate that no markdown-JSON is present in data."""
        from libs.contracts.validation import _contains_markdown_json, _check_dict_for_markdown_json
        
        if isinstance(data, str):
            if _contains_markdown_json(data):
                error_spec = ErrorSpec(
                    error_code="VALIDATION_ERROR",
                    severity="HIGH",
                    category="VALIDATION",
                    details={
                        "message": f"Markdown-JSON detected in field: {path}",
                        "technical_message": "Markdown-wrapped JSON is not allowed in strict mode",
                        "suggestions": [
                            "Remove markdown formatting from JSON",
                            "Use plain JSON format"
                        ]
                    },
                    context={
                        "component": "api_gateway",
                        "operation": "markdown_json_validation"
                    }
                )
                
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": {
                            "type": "markdown_json_error",
                            "message": "Markdown-JSON not allowed",
                            "status_code": 422,
                            "details": error_spec.dict()
                        }
                    }
                )
        
        elif isinstance(data, dict):
            try:
                _check_dict_for_markdown_json(data, path)
            except ContractValidationError as e:
                error_spec = ErrorSpec(
                    error_code="VALIDATION_ERROR",
                    severity="HIGH",
                    category="VALIDATION",
                    details={
                        "message": str(e),
                        "technical_message": "Markdown-wrapped JSON detected in nested data"
                    },
                    context={
                        "component": "api_gateway",
                        "operation": "markdown_json_validation"
                    }
                )
                
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": {
                            "type": "markdown_json_error",
                            "message": "Markdown-JSON not allowed",
                            "status_code": 422,
                            "details": error_spec.dict()
                        }
                    }
                )


# Global contract enforcer instance
contract_enforcer = APIGatewayContractEnforcer()


def get_contract_enforcer() -> APIGatewayContractEnforcer:
    """Get the global contract enforcer instance."""
    return contract_enforcer
