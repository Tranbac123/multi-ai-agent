"""Error contracts for service boundaries with strict JSON validation."""

from typing import Any, Dict, List, Optional, Literal
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from uuid import UUID


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
    """Error specification contract with strict JSON validation."""
    
    model_config = ConfigDict(
        extra="forbid",  # Forbid extra fields
        validate_assignment=True,
        str_strip_whitespace=True
    )

    error_type: str = Field(..., min_length=1, max_length=100, description="Error type")
    error_code: str = Field(..., min_length=1, max_length=50, description="Error code")
    message: str = Field(..., min_length=1, max_length=2000, description="Error message")
    details: Dict[str, Any] = Field(default_factory=dict, description="Error details")
    retryable: bool = Field(default=False, description="Whether error is retryable")
    status_code: int = Field(ge=100, le=599, default=500, description="HTTP status code")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    tenant_id: Optional[UUID] = Field(None, description="Tenant identifier")
    request_id: Optional[UUID] = Field(None, description="Request identifier")


class ValidationError(BaseModel):
    """Validation error details with strict JSON validation."""
    
    model_config = ConfigDict(
        extra="forbid",  # Forbid extra fields
        validate_assignment=True,
        str_strip_whitespace=True
    )

    field: str = Field(..., min_length=1, max_length=255, description="Field that failed validation")
    message: str = Field(..., min_length=1, max_length=1000, description="Validation message")
    value: Any = Field(..., description="Value that failed validation")
    error_type: Literal["validation_error"] = Field(default="validation_error", description="Error type")


class ServiceError(BaseModel):
    """Service error response with strict JSON validation."""
    
    model_config = ConfigDict(
        extra="forbid",  # Forbid extra fields
        validate_assignment=True,
        str_strip_whitespace=True
    )

    error_id: UUID = Field(..., description="Error identifier")
    error_type: str = Field(..., min_length=1, max_length=100, description="Error type")
    error_code: str = Field(..., min_length=1, max_length=50, description="Error code")
    message: str = Field(..., min_length=1, max_length=2000, description="Error message")
    details: Dict[str, Any] = Field(default_factory=dict, description="Error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    service: str = Field(..., min_length=1, max_length=100, description="Service name")
    tenant_id: Optional[UUID] = Field(None, description="Tenant identifier")
    request_id: Optional[UUID] = Field(None, description="Request identifier")


class ErrorResponse(BaseModel):
    """Standard error response format with strict JSON validation."""
    
    model_config = ConfigDict(
        extra="forbid",  # Forbid extra fields
        validate_assignment=True,
        str_strip_whitespace=True
    )

    success: Literal[False] = Field(default=False, description="Success status")
    error: ServiceError = Field(..., description="Service error")
    validation_errors: List[ValidationError] = Field(default_factory=list, description="Validation errors")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")
