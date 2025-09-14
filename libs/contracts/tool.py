"""Tool contracts for service boundaries with strict JSON validation."""

from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime
from uuid import UUID, uuid4


class ToolSpec(BaseModel):
    """Tool specification contract with strict JSON validation."""
    
    model_config = ConfigDict(
        extra="forbid",  # Forbid extra fields
        validate_assignment=True,
        str_strip_whitespace=True
    )

    id: str = Field(..., min_length=1, max_length=255, description="Tool identifier")
    name: str = Field(..., min_length=1, max_length=255, description="Tool name")
    description: str = Field(..., min_length=1, max_length=1000, description="Tool description")
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$", description="Semantic version")
    input_schema: Dict[str, Any] = Field(..., description="Input JSON schema")
    output_schema: Dict[str, Any] = Field(..., description="Output JSON schema")
    capabilities: List[str] = Field(..., min_length=1, description="Tool capabilities")
    config: Dict[str, Any] = Field(default_factory=dict, description="Tool configuration")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Tool metadata")

    @field_validator('capabilities')
    @classmethod
    def validate_capabilities(cls, v):
        """Validate capabilities list."""
        if not v:
            raise ValueError("At least one capability must be specified")
        return v


class ToolCall(BaseModel):
    """Tool call request with strict JSON validation."""
    
    model_config = ConfigDict(
        extra="forbid",  # Forbid extra fields
        validate_assignment=True,
        str_strip_whitespace=True
    )

    id: UUID = Field(default_factory=uuid4, description="Call identifier")
    tool_id: UUID = Field(..., description="Tool identifier")
    tenant_id: UUID = Field(..., description="Tenant identifier")
    input_data: Dict[str, Any] = Field(..., description="Input data")
    context: Dict[str, Any] = Field(default_factory=dict, description="Call context")
    timeout_ms: int = Field(ge=1000, le=300000, default=30000, description="Timeout in milliseconds")
    retry_count: int = Field(ge=0, le=10, default=0, description="Retry count")
    idempotency_key: Optional[str] = Field(None, max_length=255, description="Idempotency key")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Call timestamp")


class ToolResult(BaseModel):
    """Tool call result with strict JSON validation."""
    
    model_config = ConfigDict(
        extra="forbid",  # Forbid extra fields
        validate_assignment=True,
        str_strip_whitespace=True
    )

    id: UUID = Field(..., description="Result identifier")
    tool_id: UUID = Field(..., description="Tool identifier")
    tenant_id: UUID = Field(..., description="Tenant identifier")
    status: Literal["success", "error", "timeout"] = Field(..., description="Execution status")
    output_data: Optional[Dict[str, Any]] = Field(None, description="Output data")
    error_message: Optional[str] = Field(None, max_length=2000, description="Error message")
    duration_ms: int = Field(ge=0, le=300000, description="Duration in milliseconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Result metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Result timestamp")


class ToolError(BaseModel):
    """Tool error details with strict JSON validation."""
    
    model_config = ConfigDict(
        extra="forbid",  # Forbid extra fields
        validate_assignment=True,
        str_strip_whitespace=True
    )

    tool_id: UUID = Field(..., description="Tool identifier")
    error_type: str = Field(..., min_length=1, max_length=100, description="Error type")
    error_message: str = Field(..., min_length=1, max_length=2000, description="Error message")
    error_code: Optional[str] = Field(None, max_length=50, description="Error code")
    retryable: bool = Field(default=True, description="Whether error is retryable")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Error metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
