"""Agent contracts for service boundaries."""

from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime
from uuid import UUID, uuid4


class AgentSpec(BaseModel):
    """Agent specification contract with strict JSON validation."""
    
    model_config = ConfigDict(
        extra="forbid",  # Forbid extra fields
        validate_assignment=True,
        str_strip_whitespace=True
    )

    id: str = Field(..., min_length=1, max_length=255, description="Agent identifier")
    name: str = Field(..., min_length=1, max_length=255, description="Agent name")
    description: str = Field(..., min_length=1, max_length=1000, description="Agent description")
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$", description="Semantic version")
    capabilities: List[str] = Field(..., min_length=1, description="Agent capabilities")
    config: Dict[str, Any] = Field(default_factory=dict, description="Agent configuration")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Agent metadata")

    @field_validator('capabilities')
    @classmethod
    def validate_capabilities(cls, v):
        """Validate capabilities list."""
        if not v:
            raise ValueError("At least one capability must be specified")
        return v


class MessageSpec(BaseModel):
    """Message specification contract with strict JSON validation."""
    
    model_config = ConfigDict(
        extra="forbid",  # Forbid extra fields
        validate_assignment=True,
        str_strip_whitespace=True
    )

    id: UUID = Field(default_factory=uuid4, description="Message identifier")
    tenant_id: UUID = Field(..., description="Tenant identifier")
    user_id: Optional[UUID] = Field(None, description="User identifier")
    session_id: Optional[UUID] = Field(None, description="Session identifier")
    content: str = Field(..., min_length=1, max_length=10000, description="Message content")
    message_type: Literal["user", "assistant", "system"] = Field(
        default="user", description="Message type"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Message metadata")

    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        """Validate message content is not markdown-wrapped JSON."""
        if v.strip().startswith('```json') and v.strip().endswith('```'):
            raise ValueError("Markdown-wrapped JSON is not allowed")
        return v


class AgentRequest(BaseModel):
    """Agent execution request with strict JSON validation."""
    
    model_config = ConfigDict(
        extra="forbid",  # Forbid extra fields
        validate_assignment=True,
        str_strip_whitespace=True
    )

    message: MessageSpec = Field(..., description="Message specification")
    agent_id: UUID = Field(..., description="Agent identifier")
    workflow_id: Optional[UUID] = Field(None, description="Workflow identifier")
    context: Dict[str, Any] = Field(default_factory=dict, description="Request context")
    idempotency_key: Optional[str] = Field(None, max_length=255, description="Idempotency key")


class AgentResponse(BaseModel):
    """Agent execution response with strict JSON validation."""
    
    model_config = ConfigDict(
        extra="forbid",  # Forbid extra fields
        validate_assignment=True,
        str_strip_whitespace=True
    )

    message: MessageSpec = Field(..., description="Response message")
    agent_id: UUID = Field(..., description="Agent identifier")
    workflow_id: Optional[UUID] = Field(None, description="Workflow identifier")
    status: Literal["success", "error", "partial"] = Field(..., description="Execution status")
    tokens_used: int = Field(ge=0, description="Tokens used")
    cost_usd: float = Field(ge=0.0, description="Cost in USD")
    duration_ms: int = Field(ge=0, description="Duration in milliseconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")
    run_id: UUID = Field(default_factory=uuid4, description="Execution run identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
