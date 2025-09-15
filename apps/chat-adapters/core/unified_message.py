"""Unified Message Format for Multi-Channel Chat Integration."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
import uuid


class MessageType(Enum):
    """Supported message types across all channels."""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    FILE = "file"
    LOCATION = "location"
    CONTACT = "contact"
    STICKER = "sticker"
    QUICK_REPLY = "quick_reply"
    POSTBACK = "postback"


class Channel(Enum):
    """Supported chat channels."""
    FACEBOOK = "facebook"
    ZALO = "zalo"
    TIKTOK = "tiktok"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    SLACK = "slack"
    WEB = "web"
    API = "api"


@dataclass
class UserProfile:
    """Cross-platform user profile."""
    user_id: str
    platform_user_id: str
    channel: Channel
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MessageContent:
    """Message content with rich media support."""
    text: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    location: Optional[Dict[str, float]] = None  # {"lat": 0.0, "lng": 0.0}
    contact: Optional[Dict[str, str]] = None
    quick_replies: Optional[List[Dict[str, str]]] = None
    buttons: Optional[List[Dict[str, str]]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UnifiedMessage:
    """Unified message format for cross-platform communication."""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    channel: Channel = Channel.WEB
    user_profile: UserProfile = None
    tenant_id: str = "default"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    message_type: MessageType = MessageType.TEXT
    content: MessageContent = field(default_factory=MessageContent)
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    reply_to: Optional[str] = None
    thread_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "message_id": self.message_id,
            "channel": self.channel.value,
            "user_profile": {
                "user_id": self.user_profile.user_id,
                "platform_user_id": self.user_profile.platform_user_id,
                "channel": self.user_profile.channel.value,
                "name": self.user_profile.name,
                "email": self.user_profile.email,
                "phone": self.user_profile.phone,
                "avatar_url": self.user_profile.avatar_url,
                "language": self.user_profile.language,
                "timezone": self.user_profile.timezone,
                "metadata": self.user_profile.metadata,
            },
            "tenant_id": self.tenant_id,
            "timestamp": self.timestamp.isoformat(),
            "message_type": self.message_type.value,
            "content": {
                "text": self.content.text,
                "media_url": self.content.media_url,
                "media_type": self.content.media_type,
                "file_name": self.content.file_name,
                "file_size": self.content.file_size,
                "location": self.content.location,
                "contact": self.content.contact,
                "quick_replies": self.content.quick_replies,
                "buttons": self.content.buttons,
                "metadata": self.content.metadata,
            },
            "context": self.context,
            "metadata": self.metadata,
            "reply_to": self.reply_to,
            "thread_id": self.thread_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UnifiedMessage":
        """Create from dictionary."""
        user_profile_data = data.get("user_profile", {})
        user_profile = UserProfile(
            user_id=user_profile_data.get("user_id", ""),
            platform_user_id=user_profile_data.get("platform_user_id", ""),
            channel=Channel(user_profile_data.get("channel", "web")),
            name=user_profile_data.get("name"),
            email=user_profile_data.get("email"),
            phone=user_profile_data.get("phone"),
            avatar_url=user_profile_data.get("avatar_url"),
            language=user_profile_data.get("language"),
            timezone=user_profile_data.get("timezone"),
            metadata=user_profile_data.get("metadata", {}),
        )

        content_data = data.get("content", {})
        content = MessageContent(
            text=content_data.get("text"),
            media_url=content_data.get("media_url"),
            media_type=content_data.get("media_type"),
            file_name=content_data.get("file_name"),
            file_size=content_data.get("file_size"),
            location=content_data.get("location"),
            contact=content_data.get("contact"),
            quick_replies=content_data.get("quick_replies"),
            buttons=content_data.get("buttons"),
            metadata=content_data.get("metadata", {}),
        )

        return cls(
            message_id=data.get("message_id", str(uuid.uuid4())),
            channel=Channel(data.get("channel", "web")),
            user_profile=user_profile,
            tenant_id=data.get("tenant_id", "default"),
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.utcnow().isoformat())),
            message_type=MessageType(data.get("message_type", "text")),
            content=content,
            context=data.get("context", {}),
            metadata=data.get("metadata", {}),
            reply_to=data.get("reply_to"),
            thread_id=data.get("thread_id"),
        )


@dataclass
class UnifiedResponse:
    """Unified response format for cross-platform communication."""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    channel: Channel = Channel.WEB
    recipient_id: str = ""
    content: MessageContent = field(default_factory=MessageContent)
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    reply_to: Optional[str] = None
    thread_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "message_id": self.message_id,
            "channel": self.channel.value,
            "recipient_id": self.recipient_id,
            "content": {
                "text": self.content.text,
                "media_url": self.content.media_url,
                "media_type": self.content.media_type,
                "file_name": self.content.file_name,
                "file_size": self.content.file_size,
                "location": self.content.location,
                "contact": self.content.contact,
                "quick_replies": self.content.quick_replies,
                "buttons": self.content.buttons,
                "metadata": self.content.metadata,
            },
            "context": self.context,
            "metadata": self.metadata,
            "reply_to": self.reply_to,
            "thread_id": self.thread_id,
        }
