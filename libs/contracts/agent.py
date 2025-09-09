"""Agent contracts for service boundaries."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentSpec(BaseModel):
    """Agent specification contract."""
    id: str
    name: str
    description: str
    version: str
    capabilities: List[str]
    config: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MessageSpec(BaseModel):
    """Message specification contract."""
    id: str
    tenant_id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    content: str
    message_type: str = "user"  # user, assistant, system
    timestamp: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentRequest(BaseModel):
    """Agent execution request."""
    message: MessageSpec
    agent_id: str
    workflow_id: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    """Agent execution response."""
    message: MessageSpec
    agent_id: str
    workflow_id: Optional[str] = None
    status: str  # success, error, partial
    tokens_used: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)