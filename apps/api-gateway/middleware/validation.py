"""Validation middleware for API Gateway with strict JSON validation."""

from typing import Any, Dict, List, Optional
from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from datetime import datetime
from uuid import uuid4
import structlog

from libs.contracts.error import ErrorResponse, ServiceError, ValidationError
from libs.contracts.agent import MessageSpec
from libs.contracts.tool import ToolCall, ToolResult, ToolSpec
from libs.contracts.router import RouterDecisionRequest, RouterDecisionResponse

logger = structlog.get_logger(__name__)


class ValidationMiddleware:
    """Middleware for request/response validation."""

    def __init__(self):
        self.validation_errors: List[ValidationError] = []

    async def validate_request(self, request: Request, model_class: type) -> Any:
        """Validate incoming request against Pydantic model with strict JSON validation."""
        try:
            body = await request.json()
            
            # Check for markdown-wrapped JSON in request body
            await self._check_markdown_json_injection(request, body)
            
            validated_data = model_class(**body)
            
            logger.info(
                "Request validation successful",
                model_class=model_class.__name__,
                request_id=getattr(request.state, "request_id", None),
                tenant_id=getattr(request.state, "tenant_id", None)
            )
            
            return validated_data
            
        except ValidationError as e:
            error_id = uuid4()
            error = ServiceError(
                error_id=error_id,
                error_type="validation_error",
                error_code="INVALID_REQUEST",
                message=f"Request validation failed: {str(e)}",
                timestamp=datetime.utcnow(),
                service="api-gateway",
                tenant_id=getattr(request.state, "tenant_id", None),
                request_id=getattr(request.state, "request_id", None),
            )

            logger.warning(
                "Request validation failed",
                error_id=error_id,
                validation_errors=str(e.errors()),
                request_id=getattr(request.state, "request_id", None),
                tenant_id=getattr(request.state, "tenant_id", None)
            )

            return ErrorResponse(
                success=False,
                error=error,
                validation_errors=self._extract_validation_errors(e),
            )
        except Exception as e:
            error_id = uuid4()
            error = ServiceError(
                error_id=error_id,
                error_type="internal_error",
                error_code="VALIDATION_ERROR",
                message=f"Unexpected validation error: {str(e)}",
                timestamp=datetime.utcnow(),
                service="api-gateway",
                tenant_id=getattr(request.state, "tenant_id", None),
                request_id=getattr(request.state, "request_id", None),
            )

            logger.error(
                "Unexpected validation error",
                error_id=error_id,
                error=str(e),
                request_id=getattr(request.state, "request_id", None),
                tenant_id=getattr(request.state, "tenant_id", None)
            )

            return ErrorResponse(
                success=False,
                error=error,
                validation_errors=[],
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
                service="api-gateway",
            )

            return ErrorResponse(
                success=False,
                error=error,
                validation_errors=self._extract_validation_errors(e),
            )

    async def _check_markdown_json_injection(self, request: Request, body: Any) -> None:
        """Check for markdown-wrapped JSON injection attempts."""
        def check_value(value: Any, path: str = "") -> None:
            """Recursively check for markdown JSON in nested structures."""
            if isinstance(value, str):
                if value.strip().startswith('```json') and value.strip().endswith('```'):
                    logger.warning(
                        "Markdown JSON injection attempt detected",
                        path=path,
                        value=value[:100] + "..." if len(value) > 100 else value,
                        request_id=getattr(request.state, "request_id", None),
                        tenant_id=getattr(request.state, "tenant_id", None)
                    )
                    raise ValueError(f"Markdown-wrapped JSON detected in {path}: not allowed")
            elif isinstance(value, dict):
                for key, val in value.items():
                    check_value(val, f"{path}.{key}" if path else key)
            elif isinstance(value, list):
                for i, val in enumerate(value):
                    check_value(val, f"{path}[{i}]" if path else f"[{i}]")
        
        check_value(body, "request_body")

    def _extract_validation_errors(self, exception: Exception) -> List[ValidationError]:
        """Extract validation errors from Pydantic exception."""
        errors = []
        if hasattr(exception, "errors"):
            for error in exception.errors():
                errors.append(
                    ValidationError(
                        field=".".join(str(x) for x in error.get("loc", [])),
                        message=error.get("msg", "Validation error"),
                        value=error.get("input"),
                        error_type=error.get("type", "validation_error"),
                    )
                )
        return errors


def create_error_response(
    error_type: str,
    error_code: str,
    message: str,
    status_code: int = 400,
    details: Optional[Dict[str, Any]] = None,
    tenant_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> JSONResponse:
    """Create standardized error response with strict JSON validation."""
    error_id = uuid4()
    error = ServiceError(
        error_id=error_id,
        error_type=error_type,
        error_code=error_code,
        message=message,
        details=details or {},
        timestamp=datetime.utcnow(),
        service="api-gateway",
        tenant_id=tenant_id,
        request_id=request_id,
    )

    response = ErrorResponse(success=False, error=error)

    logger.info(
        "Error response created",
        error_id=error_id,
        error_type=error_type,
        error_code=error_code,
        status_code=status_code,
        tenant_id=tenant_id,
        request_id=request_id
    )

    return JSONResponse(status_code=status_code, content=response.dict())
