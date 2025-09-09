"""Message contracts and specifications."""

from datetime import datetime
from typing import Dict, Any, Optional, Literal, List
from uuid import UUID, uuid4
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class MessageRole(str, Enum):
    """Message role enumeration."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"
    CRITIC = "critic"
    VERIFIER = "verifier"


class MessageSpec(BaseModel):
    """Message specification with metadata."""
    model_config = ConfigDict(frozen=True)
    
    message_id: UUID = Field(default_factory=uuid4)
    run_id: UUID = Field(description="Agent run ID")
    step_id: Optional[UUID] = Field(default=None, description="Agent step ID")
    tenant_id: UUID = Field(description="Tenant identifier")
    role: MessageRole = Field(description="Message role")
    payload: Dict[str, Any] = Field(description="Message payload")
    schema_version: str = Field(default="1.0", description="Schema version")
    trace_id: Optional[str] = Field(default=None, description="OpenTelemetry trace ID")
    parent_message_id: Optional[UUID] = Field(default=None, description="Parent message ID")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ConversationContext(BaseModel):
    """Conversation context for agents."""
    conversation_id: UUID = Field(description="Conversation identifier")
    tenant_id: UUID = Field(description="Tenant identifier")
    messages: List[MessageSpec] = Field(description="Message history")
    context_window: int = Field(default=4000, ge=100, le=32000, description="Context window size")
    max_messages: int = Field(default=50, ge=1, le=1000, description="Maximum messages to keep")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
