from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from enum import Enum

class NotificationType(str, Enum):
    EMAIL = "email"
    SLACK = "slack"
    TEAMS = "teams"
    WEBHOOK = "webhook"

class NotificationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class NotificationRequest(BaseModel):
    tenant_id: str
    notification_type: NotificationType
    recipients: List[str]
    subject: Optional[str] = None
    message: str
    priority: NotificationPriority = NotificationPriority.MEDIUM
    template: Optional[str] = None
    template_vars: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class NotificationResponse(BaseModel):
    success: bool
    notification_id: str
    sent_to: List[str]
    failed_recipients: List[str] = Field(default_factory=list)
    processing_time_ms: int
    error: Optional[str] = None

class NotificationStatus(BaseModel):
    notification_id: str
    tenant_id: str
    notification_type: NotificationType
    status: str  # sent, failed, pending
    recipients: List[str]
    sent_at: Optional[str] = None
    error: Optional[str] = None

class ChannelConfig(BaseModel):
    channel_type: NotificationType
    enabled: bool
    config: Dict[str, Any] = Field(default_factory=dict)

class HealthCheck(BaseModel):
    status: str
    channels: Dict[NotificationType, Dict[str, Any]]
    last_check: str

