"""Custom exceptions for the AIaaS platform."""

from typing import Optional, Dict, Any
from libs.contracts.error_spec import ErrorSpec, ErrorCode, ErrorSeverity, ErrorCategory, ErrorDetails, ErrorContext


def create_error_spec(
    error_code: ErrorCode,
    message: str,
    severity: ErrorSeverity = ErrorSeverity.HIGH,
    retry_after_seconds: Optional[int] = None,
    diagnostics: Optional[Dict[str, Any]] = None
) -> ErrorSpec:
    """Helper function to create ErrorSpec instances."""
    # Determine category based on error code
    category_map = {
        ErrorCode.VALIDATION_ERROR: ErrorCategory.VALIDATION,
        ErrorCode.INVALID_INPUT: ErrorCategory.VALIDATION,
        ErrorCode.MISSING_REQUIRED_FIELD: ErrorCategory.VALIDATION,
        ErrorCode.INVALID_FORMAT: ErrorCategory.VALIDATION,
        ErrorCode.UNAUTHORIZED: ErrorCategory.AUTHENTICATION,
        ErrorCode.FORBIDDEN: ErrorCategory.AUTHORIZATION,
        ErrorCode.RESOURCE_NOT_FOUND: ErrorCategory.RESOURCE,
        ErrorCode.QUOTA_EXCEEDED: ErrorCategory.RESOURCE,
        ErrorCode.RATE_LIMIT_EXCEEDED: ErrorCategory.RESOURCE,
        ErrorCode.INTERNAL_ERROR: ErrorCategory.SYSTEM,
        ErrorCode.SERVICE_UNAVAILABLE: ErrorCategory.SYSTEM,
        ErrorCode.TIMEOUT: ErrorCategory.TIMEOUT,
        ErrorCode.NETWORK_ERROR: ErrorCategory.NETWORK,
        ErrorCode.BUSINESS_RULE_VIOLATION: ErrorCategory.BUSINESS,
        ErrorCode.WORKFLOW_ERROR: ErrorCategory.BUSINESS,
        ErrorCode.AGENT_ERROR: ErrorCategory.BUSINESS,
        ErrorCode.TOOL_ERROR: ErrorCategory.BUSINESS,
    }
    
    category = category_map.get(error_code, ErrorCategory.SYSTEM)
    
    # Create error details
    details = ErrorDetails(
        message=message,
        technical_message=str(diagnostics) if diagnostics else None,
        stack_trace=None,
        documentation_url=None,
        retry_after_seconds=retry_after_seconds
    )
    
    # Create error context (minimal for exceptions)
    context = ErrorContext(
        tenant_id=None,
        user_id=None,
        session_id=None,
        request_id=None,
        workflow_id=None,
        agent_id=None,
        tool_id=None,
        component=None,
        operation=None
    )
    
    return ErrorSpec(
        error_code=error_code,
        severity=severity,
        category=category,
        details=details,
        context=context,
        correlation_id=None,
        parent_error_id=None
    )


class APIException(Exception):
    """Base API exception."""

    def __init__(self, error_spec: ErrorSpec, status_code: int = 500):
        self.error_spec = error_spec
        self.status_code = status_code
        super().__init__(error_spec.details.message)


class ValidationError(APIException):
    """Validation error exception."""

    def __init__(self, message: str, field: Optional[str] = None):
        error_spec = create_error_spec(
            error_code=ErrorCode.VALIDATION_ERROR,
            message=message,
            diagnostics={"field": field} if field else {}
        )
        super().__init__(error_spec, status_code=422)


class AuthenticationError(APIException):
    """Authentication error exception."""

    def __init__(self, message: str = "Authentication failed"):
        error_spec = create_error_spec(
            error_code=ErrorCode.UNAUTHORIZED,
            message=message
        )
        super().__init__(error_spec, status_code=401)


class AuthorizationError(APIException):
    """Authorization error exception."""

    def __init__(self, message: str = "Authorization failed"):
        error_spec = create_error_spec(
            error_code=ErrorCode.FORBIDDEN,
            message=message
        )
        super().__init__(error_spec, status_code=403)
