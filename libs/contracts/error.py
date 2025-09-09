"""Error contracts and specifications."""

from datetime import datetime
from typing import Dict, Any, Optional, Literal
from uuid import UUID, uuid4
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class ErrorCode(str, Enum):
    """Error code enumeration."""
    TIMEOUT = "TIMEOUT"
    TOOL_DOWN = "TOOL_DOWN"
    VALIDATION_FAIL = "VALIDATION_FAIL"
    POLICY_BLOCK = "POLICY_BLOCK"
    RATE_LIMIT = "RATE_LIMIT"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    BULKHEAD_FULL = "BULKHEAD_FULL"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    AUTHORIZATION_FAILED = "AUTHORIZATION_FAILED"
    TENANT_NOT_FOUND = "TENANT_NOT_FOUND"
    AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    INVALID_SCHEMA = "INVALID_SCHEMA"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorSpec(BaseModel):
    """Error specification with diagnostics."""
    model_config = ConfigDict(frozen=True)
    
    error_id: UUID = Field(default_factory=uuid4)
    code: ErrorCode = Field(description="Error code")
    message: str = Field(description="Human-readable error message")
    retriable: bool = Field(description="Whether error is retriable")
    diagnostics: Dict[str, Any] = Field(default_factory=dict, description="Error diagnostics")
    context: Dict[str, Any] = Field(default_factory=dict, description="Error context")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Optional fields for specific error types
    retry_after_ms: Optional[int] = Field(default=None, ge=0, description="Retry after delay")
    quota_reset_at: Optional[datetime] = Field(default=None, description="Quota reset time")
    circuit_reset_at: Optional[datetime] = Field(default=None, description="Circuit reset time")


class ErrorResponse(BaseModel):
    """Error response for API consumers."""
    error: ErrorSpec = Field(description="Error specification")
    trace_id: Optional[str] = Field(default=None, description="OpenTelemetry trace ID")
    request_id: Optional[str] = Field(default=None, description="Request identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
