"""Billing contracts and specifications."""

from datetime import datetime, date
from typing import Dict, Any, Optional, Literal, List
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


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
    usage_breakdown: Dict[str, Any] = Field(
        default_factory=dict, description="Usage breakdown"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    due_at: Optional[datetime] = Field(default=None, description="Due date")
    paid_at: Optional[datetime] = Field(default=None, description="Payment date")


class BillingPlan(BaseModel):
    """Billing plan for tenants."""

    plan_id: UUID = Field(default_factory=uuid4)
    name: str = Field(description="Plan name")
    description: str = Field(description="Plan description")
    price_usd: float = Field(ge=0.0, description="Monthly price in USD")
    usage_limits: Dict[str, int] = Field(
        default_factory=dict, description="Usage limits per type"
    )
    features: List[str] = Field(default_factory=list, description="Plan features")
    is_active: bool = Field(default=True, description="Whether plan is active")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PaymentMethod(BaseModel):
    """Payment method for tenants."""

    method_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(description="Tenant identifier")
    method_type: Literal["credit_card", "bank_account", "paypal"] = Field(
        description="Payment method type"
    )
    provider: str = Field(description="Payment provider")
    provider_id: str = Field(description="Provider-specific ID")
    is_default: bool = Field(
        default=False, description="Whether this is the default payment method"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UsageReport(BaseModel):
    """Usage report for tenants."""

    report_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(description="Tenant identifier")
    period_start: date = Field(description="Report period start")
    period_end: date = Field(description="Report period end")
    usage_summary: Dict[str, Any] = Field(
        default_factory=dict, description="Usage summary"
    )
    cost_breakdown: Dict[str, float] = Field(
        default_factory=dict, description="Cost breakdown"
    )
    total_cost_usd: float = Field(ge=0.0, description="Total cost in USD")
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class MeteredUsage(BaseModel):
    """Metered usage record."""

    usage_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(description="Tenant identifier")
    usage_type: Literal[
        "tokens", "tool_calls", "ws_minutes", "storage", "api_calls"
    ] = Field(description="Usage type")
    amount: int = Field(ge=0, description="Usage amount")
    cost_usd: float = Field(ge=0.0, description="Cost in USD")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
