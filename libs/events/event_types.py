"""Event type definitions and models."""

from typing import Dict, Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from enum import Enum


class EventType(str, Enum):
    """Event type enumeration."""

    AGENT_RUN = "agent_run"
    TOOL_CALL = "tool_call"
    INGEST_DOC = "ingest_doc"
    USAGE_METERED = "usage_metered"
    ROUTER_DECISION = "router_decision"
    WEBSOCKET_MESSAGE = "websocket_message"
    BILLING_EVENT = "billing_event"
    AUDIT_LOG = "audit_log"


class AgentRunEvent(BaseModel):
    """Agent run event data."""

    run_id: str
    tenant_id: UUID
    agent_id: str
    user_id: Optional[UUID] = None
    session_id: Optional[str] = None
    input_text: str
    output_text: Optional[str] = None
    status: str  # "started", "completed", "failed"
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[int] = None
    tokens_used: Optional[int] = None
    cost_usd: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolCallEvent(BaseModel):
    """Tool call event data."""

    call_id: str
    run_id: str
    tenant_id: UUID
    tool_name: str
    tool_input: Dict[str, Any]
    tool_output: Optional[Dict[str, Any]] = None
    status: str  # "started", "completed", "failed"
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IngestDocEvent(BaseModel):
    """Document ingestion event data."""

    doc_id: str
    tenant_id: UUID
    user_id: Optional[UUID] = None
    filename: str
    content_type: str
    file_size: int
    status: str  # "started", "processing", "completed", "failed"
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[int] = None
    chunks_created: Optional[int] = None
    embeddings_generated: Optional[int] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UsageMeteredEvent(BaseModel):
    """Usage metering event data."""

    usage_id: str
    tenant_id: UUID
    user_id: Optional[UUID] = None
    resource_type: str  # "api_call", "agent_run", "tool_call", "storage"
    resource_id: str
    quantity: int
    unit: str  # "requests", "tokens", "bytes", "minutes"
    timestamp: float
    cost_usd: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RouterDecisionEvent(BaseModel):
    """Router decision event data."""

    decision_id: str
    tenant_id: UUID
    user_id: Optional[UUID] = None
    input_text: str
    selected_agent: str
    confidence: float
    reasoning: str
    features: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WebSocketMessageEvent(BaseModel):
    """WebSocket message event data."""

    message_id: str
    tenant_id: UUID
    user_id: Optional[UUID] = None
    session_id: str
    message_type: str  # "text", "file", "command"
    content: str
    timestamp: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BillingEvent(BaseModel):
    """Billing event data."""

    billing_id: str
    tenant_id: UUID
    event_type: str  # "usage_accumulated", "invoice_generated", "payment_processed"
    amount_usd: float
    currency: str = "USD"
    timestamp: float
    description: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AuditLogEvent(BaseModel):
    """Audit log event data."""

    log_id: str
    tenant_id: UUID
    user_id: Optional[UUID] = None
    action: str
    resource_type: str
    resource_id: str
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    timestamp: float
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Event type to model mapping
EVENT_MODELS = {
    EventType.AGENT_RUN: AgentRunEvent,
    EventType.TOOL_CALL: ToolCallEvent,
    EventType.INGEST_DOC: IngestDocEvent,
    EventType.USAGE_METERED: UsageMeteredEvent,
    EventType.ROUTER_DECISION: RouterDecisionEvent,
    EventType.WEBSOCKET_MESSAGE: WebSocketMessageEvent,
    EventType.BILLING_EVENT: BillingEvent,
    EventType.AUDIT_LOG: AuditLogEvent,
}
