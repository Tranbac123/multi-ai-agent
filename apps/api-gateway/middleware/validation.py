"""Validation middleware for API Gateway."""

from typing import Any, Dict, List, Optional
from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
import time
import uuid

from libs.contracts.error import ErrorResponse, ServiceError, ValidationError
from libs.contracts.agent import AgentRequest, AgentResponse
from libs.contracts.tool import ToolCall, ToolResult
from libs.contracts.router_io import RouterDecisionRequest, RouterDecisionResponse


class ValidationMiddleware:
    """Middleware for request/response validation."""
    
    def __init__(self):
        self.validation_errors: List[ValidationError] = []
    
    async def validate_request(self, request: Request, model_class: type) -> Any:
        """Validate incoming request against Pydantic model."""
        try:
            body = await request.json()
            validated_data = model_class(**body)
            return validated_data
        except Exception as e:
            error_id = str(uuid.uuid4())
            error = ServiceError(
                error_id=error_id,
                error_type="validation_error",
                error_code="INVALID_REQUEST",
                message=f"Request validation failed: {str(e)}",
                timestamp=time.time(),
                service="api-gateway",
                tenant_id=getattr(request.state, 'tenant_id', None),
                request_id=getattr(request.state, 'request_id', None)
            )
            
            return ErrorResponse(
                success=False,
                error=error,
                validation_errors=self._extract_validation_errors(e)
            )
    
    def validate_response(self, response_data: Any, model_class: type) -> Any:
        """Validate outgoing response against Pydantic model."""
        try:
            if isinstance(response_data, dict):
                return model_class(**response_data)
            return response_data
        except Exception as e:
            error_id = str(uuid.uuid4())
            error = ServiceError(
                error_id=error_id,
                error_type="validation_error",
                error_code="INVALID_RESPONSE",
                message=f"Response validation failed: {str(e)}",
                timestamp=time.time(),
                service="api-gateway"
            )
            
            return ErrorResponse(
                success=False,
                error=error,
                validation_errors=self._extract_validation_errors(e)
            )
    
    def _extract_validation_errors(self, exception: Exception) -> List[ValidationError]:
        """Extract validation errors from Pydantic exception."""
        errors = []
        if hasattr(exception, 'errors'):
            for error in exception.errors():
                errors.append(ValidationError(
                    field=".".join(str(x) for x in error.get("loc", [])),
                    message=error.get("msg", "Validation error"),
                    value=error.get("input"),
                    error_type=error.get("type", "validation_error")
                ))
        return errors


def create_error_response(
    error_type: str,
    error_code: str,
    message: str,
    status_code: int = 400,
    details: Optional[Dict[str, Any]] = None,
    tenant_id: Optional[str] = None,
    request_id: Optional[str] = None
) -> JSONResponse:
    """Create standardized error response."""
    error_id = str(uuid.uuid4())
    error = ServiceError(
        error_id=error_id,
        error_type=error_type,
        error_code=error_code,
        message=message,
        details=details or {},
        timestamp=time.time(),
        service="api-gateway",
        tenant_id=tenant_id,
        request_id=request_id
    )
    
    response = ErrorResponse(
        success=False,
        error=error
    )
    
    return JSONResponse(
        status_code=status_code,
        content=response.dict()
    )
