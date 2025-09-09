"""Tool contracts for service boundaries."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    """Tool specification contract."""
    id: str
    name: str
    description: str
    version: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    capabilities: List[str]
    config: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """Tool call request."""
    id: str
    tool_id: str
    tenant_id: str
    input_data: Dict[str, Any]
    context: Dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int = 30000
    retry_count: int = 0


class ToolResult(BaseModel):
    """Tool call result."""
    id: str
    tool_id: str
    tenant_id: str
    status: str  # success, error, timeout
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    duration_ms: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolError(BaseModel):
    """Tool error details."""
    tool_id: str
    error_type: str
    error_message: str
    error_code: Optional[str] = None
    retryable: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)