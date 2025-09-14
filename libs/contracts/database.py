"""Database models and contracts for multi-tenant AIaaS platform."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
from decimal import Decimal


class UserRole(str, Enum):
    """User roles in the system."""

    ADMIN = "admin"
    AGENT = "agent"
    VIEWER = "viewer"


class OrderStatus(str, Enum):
    """Order status enumeration."""

    DRAFT = "draft"
    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"


class UserProfile(BaseModel):
    """User profile information."""

    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None
    role: UserRole = UserRole.VIEWER
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        else:
            return self.email.split("@")[0]


class CustomerProfile(BaseModel):
    """Customer profile information."""

    id: int
    name: str
    email: str
    phone: Optional[str] = None
    company: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class ProductInfo(BaseModel):
    """Product information."""

    id: int
    name: str
    description: Optional[str] = None
    price: Decimal
    currency: str = "USD"
    category: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None


class OrderItem(BaseModel):
    """Order item information."""

    id: int
    product_id: int
    product: Optional[ProductInfo] = None
    quantity: int
    unit_price: Decimal
    created_at: datetime


class OrderInfo(BaseModel):
    """Order information."""

    id: int
    customer_id: int
    customer: Optional[CustomerProfile] = None
    status: OrderStatus
    total_amount: Decimal
    currency: str = "USD"
    payment_link: Optional[str] = None
    shipping_address: Optional[Dict[str, Any]] = None
    items: List[OrderItem] = []
    created_at: datetime
    updated_at: Optional[datetime] = None


class ServicePackage(BaseModel):
    """Service package information."""

    id: int
    name: str
    description: str
    price: Decimal
    currency: str = "USD"
    features: List[str] = []
    max_requests: Optional[int] = None
    max_storage_mb: Optional[int] = None
    is_active: bool = True
    created_at: datetime


class UserSubscription(BaseModel):
    """User subscription information."""

    id: int
    user_id: int
    package_id: int
    package: Optional[ServicePackage] = None
    is_active: bool = True
    started_at: datetime
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class MessageInfo(BaseModel):
    """Message information."""

    id: int
    session_id: str
    customer_id: Optional[int] = None
    content: str
    role: str  # 'user' or 'assistant'
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


class FAQEntry(BaseModel):
    """FAQ entry information."""

    id: int
    question: str
    answer: str
    category: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None


class LeadInfo(BaseModel):
    """Lead information."""

    id: int
    name: str
    email: str
    phone: Optional[str] = None
    company: Optional[str] = None
    source: Optional[str] = None
    status: str = "new"
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class AuditLog(BaseModel):
    """Audit log entry."""

    id: int
    user_id: Optional[int] = None
    action: str
    resource_type: str
    resource_id: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime


# Event-related models
class AgentRun(BaseModel):
    """Agent run event data."""

    id: str
    tenant_id: str
    agent_id: str
    user_id: Optional[str] = None
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


class ToolCall(BaseModel):
    """Tool call event data."""

    id: str
    run_id: str
    tenant_id: str
    tool_name: str
    tool_input: Dict[str, Any]
    tool_output: Optional[Dict[str, Any]] = None
    status: str  # "started", "completed", "failed"
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentIngestion(BaseModel):
    """Document ingestion event data."""

    id: str
    tenant_id: str
    user_id: Optional[str] = None
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


class UsageMetered(BaseModel):
    """Usage metering event data."""

    id: str
    tenant_id: str
    user_id: Optional[str] = None
    resource_type: str  # "api_call", "agent_run", "tool_call", "storage"
    resource_id: str
    quantity: int
    unit: str  # "requests", "tokens", "bytes", "minutes"
    timestamp: float
    cost_usd: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RouterDecision(BaseModel):
    """Router decision event data."""

    id: str
    tenant_id: str
    user_id: Optional[str] = None
    input_text: str
    selected_agent: str
    confidence: float
    reasoning: str
    features: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WebSocketMessage(BaseModel):
    """WebSocket message event data."""

    id: str
    tenant_id: str
    user_id: Optional[str] = None
    session_id: str
    message_type: str  # "text", "file", "command"
    content: str
    timestamp: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BillingEvent(BaseModel):
    """Billing event data."""

    id: str
    tenant_id: str
    event_type: str  # "usage_accumulated", "invoice_generated", "payment_processed"
    amount_usd: float
    currency: str = "USD"
    timestamp: float
    description: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PermanentFailure(BaseModel):
    """Permanent failure record."""

    id: str
    tenant_id: str
    event_type: str
    original_subject: str
    original_data: str
    original_headers: Dict[str, Any] = Field(default_factory=dict)
    error: str
    failed_at: float
    retry_count: int
    created_at: float


class DLQProcessingError(BaseModel):
    """DLQ processing error record."""

    id: str
    tenant_id: str
    dlq_data: Dict[str, Any] = Field(default_factory=dict)
    error: str
    created_at: float
