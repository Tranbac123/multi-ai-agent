from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from enum import Enum

class Platform(str, Enum):
    DISCORD = "discord"
    SLACK = "slack"
    TELEGRAM = "telegram"
    TEAMS = "teams"

class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    COMMAND = "command"

class ChatMessage(BaseModel):
    platform: Platform
    channel_id: str
    user_id: str
    username: str
    content: str
    message_type: MessageType = MessageType.TEXT
    timestamp: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ChatResponse(BaseModel):
    platform: Platform
    channel_id: str
    content: str
    message_type: MessageType = MessageType.TEXT
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AdapterRequest(BaseModel):
    tenant_id: str
    platform: Platform
    channel_id: str
    user_id: str
    username: str
    content: str
    context: Optional[Dict[str, Any]] = None

class AdapterResponse(BaseModel):
    success: bool
    response: Optional[ChatResponse] = None
    error: Optional[str] = None
    processing_time_ms: int

class PlatformConfig(BaseModel):
    platform: Platform
    enabled: bool
    webhook_url: Optional[str] = None
    token: Optional[str] = None
    signing_secret: Optional[str] = None
    rate_limit: int = 100  # messages per minute

class HealthCheck(BaseModel):
    status: str
    platforms: Dict[Platform, Dict[str, Any]]
    last_check: str

