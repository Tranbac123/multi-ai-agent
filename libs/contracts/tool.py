"""Tool contracts and specifications."""

from datetime import datetime
from typing import Dict, Any, Optional, Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict


class ToolSpec(BaseModel):
    """Tool specification with capabilities and constraints."""
    model_config = ConfigDict(frozen=True)
    
    id: str = Field(description="Tool identifier")
    name: str = Field(description="Tool display name")
    description: str = Field(description="Tool description")
    request_schema: Dict[str, Any] = Field(description="JSONSchema for requests")
    response_schema: Dict[str, Any] = Field(description="JSONSchema for responses")
    error_schema: Dict[str, Any] = Field(description="JSONSchema for errors")
    timeout_ms: int = Field(ge=100, le=300000, description="Timeout in milliseconds")
    idempotent: bool = Field(default=False, description="Whether tool is idempotent")
    has_compensation: bool = Field(default=False, description="Whether tool has compensation")
    circuit_breaker_threshold: int = Field(default=5, ge=1, description="Circuit breaker failure threshold")
    bulkhead_max_concurrent: int = Field(default=10, ge=1, description="Bulkhead max concurrent calls")


class ToolCall(BaseModel):
    """Tool call request."""
    call_id: UUID = Field(default_factory=uuid4)
    tool_id: str = Field(description="Tool identifier")
    tenant_id: UUID = Field(description="Tenant identifier")
    run_id: UUID = Field(description="Agent run ID")
    step_id: UUID = Field(description="Agent step ID")
    request_data: Dict[str, Any] = Field(description="Tool request data")
    idempotency_key: Optional[str] = Field(default=None, description="Idempotency key")
    timeout_ms: int = Field(ge=100, le=300000, description="Call timeout")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ToolResult(BaseModel):
    """Tool call result."""
    call_id: UUID = Field(description="Tool call ID")
    status: Literal["success", "failure", "timeout", "circuit_open"] = Field(
        description="Call status"
    )
    response_data: Optional[Dict[str, Any]] = Field(default=None, description="Response data")
    error: Optional[str] = Field(default=None, description="Error message")
    duration_ms: int = Field(ge=0, description="Call duration in milliseconds")
    tokens_used: int = Field(default=0, ge=0, description="Tokens consumed")
    cost_usd: float = Field(default=0.0, ge=0.0, description="Cost in USD")
    completed_at: datetime = Field(default_factory=datetime.utcnow)
    retry_count: int = Field(default=0, ge=0, description="Number of retries")
    compensation_data: Optional[Dict[str, Any]] = Field(
        default=None, description="Compensation data for rollback"
    )
