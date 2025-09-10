"""Error contracts for service boundaries."""

from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    """Standard error codes."""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    BAD_REQUEST = "BAD_REQUEST"


class ErrorSpec(BaseModel):
    """Error specification contract."""
    error_type: str
    error_code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    retryable: bool = False
    status_code: int = 500


class ValidationError(BaseModel):
    """Validation error details."""
    field: str
    message: str
    value: Any
    error_type: str = "validation_error"


class ServiceError(BaseModel):
    """Service error response."""
    error_id: str
    error_type: str
    error_code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float
    service: str
    tenant_id: Optional[str] = None
    request_id: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error response format."""
    success: bool = False
    error: ServiceError
    validation_errors: List[ValidationError] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)