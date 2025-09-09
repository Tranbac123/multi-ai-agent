"""Billing contracts and specifications."""

from datetime import datetime, date
from typing import Dict, Any, Optional, Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict


class UsageCounter(BaseModel):
    """Usage counter for billing."""
    tenant_id: UUID = Field(description="Tenant identifier")
    day: date = Field(description="Usage day")
    tokens_in: int = Field(default=0, ge=0, description="Input tokens")
    tokens_out: int = Field(default=0, ge=0, description="Output tokens")
    tool_calls: int = Field(default=0, ge=0, description="Tool calls")
    ws_minutes: int = Field(default=0, ge=0, description="WebSocket minutes")
    storage_mb: int = Field(default=0, ge=0, description="Storage in MB")
    cost_usd: float = Field(default=0.0, ge=0.0, description="Cost in USD")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BillingEvent(BaseModel):
    """Billing event for metering."""
    event_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(description="Tenant identifier")
    event_type: Literal["tokens", "tool_calls", "ws_minutes", "storage"] = Field(
        description="Event type"
    )
    quantity: int = Field(ge=0, description="Event quantity")
    unit_cost_usd: float = Field(ge=0.0, description="Unit cost in USD")
    total_cost_usd: float = Field(ge=0.0, description="Total cost in USD")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Event metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Invoice(BaseModel):
    """Invoice for billing."""
    invoice_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(description="Tenant identifier")
    period_start: date = Field(description="Billing period start")
    period_end: date = Field(description="Billing period end")
    subtotal_usd: float = Field(ge=0.0, description="Subtotal in USD")
    tax_usd: float = Field(ge=0.0, description="Tax in USD")
    total_usd: float = Field(ge=0.0, description="Total in USD")
    status: Literal["draft", "sent", "paid", "overdue"] = Field(default="draft")
    usage_breakdown: Dict[str, Any] = Field(default_factory=dict, description="Usage breakdown")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    due_at: Optional[datetime] = Field(default=None, description="Due date")
    paid_at: Optional[datetime] = Field(default=None, description="Payment date")
