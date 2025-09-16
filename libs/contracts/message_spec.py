"""
Message Specification Contract

Strict Pydantic models for message-related data structures.
No markdown-JSON tolerated, strict validation enforced.
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator, root_validator
from enum import Enum
import uuid
from datetime import datetime, timezone


class MessageType(Enum):
    """Message type enumeration."""
    USER_INPUT = "user_input"
    AGENT_RESPONSE = "agent_response"
    SYSTEM_MESSAGE = "system_message"
    TOOL_REQUEST = "tool_request"
    TOOL_RESPONSE = "tool_response"
    ERROR_MESSAGE = "error_message"
    STATUS_UPDATE = "status_update"
    WORKFLOW_EVENT = "workflow_event"


class MessagePriority(Enum):
    """Message priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class MessageContent(BaseModel):
    """Message content specification."""
    
    text: Optional[str] = Field(
        None,
        description="Text content",
        max_length=100000
    )
    data: Optional[Dict[str, Any]] = Field(
        None,
        description="Structured data content"
    )
    attachments: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Message attachments"
    )
    
    @validator('text')
    def validate_text(cls, v):
        """Validate text content."""
        if v is not None and not v.strip():
            return None
        return v
    
    @validator('data')
    def validate_data(cls, v):
        """Validate structured data."""
        if v is not None and not isinstance(v, dict):
            raise ValueError('data must be a dictionary or None')
        return v
    
    @validator('attachments')
    def validate_attachments(cls, v):
        """Validate attachments."""
        if not isinstance(v, list):
            raise ValueError('attachments must be a list')
        
        for i, attachment in enumerate(v):
            if not isinstance(attachment, dict):
                raise ValueError(f'attachment {i} must be a dictionary')
            
            required_fields = ['type', 'content']
            for field in required_fields:
                if field not in attachment:
                    raise ValueError(f'attachment {i} missing required field: {field}')
        
        return v
    
    @root_validator
    def validate_content_presence(cls, values):
        """Ensure at least one content type is present."""
        text = values.get('text')
        data = values.get('data')
        attachments = values.get('attachments', [])
        
        if not text and not data and not attachments:
            raise ValueError('At least one content type must be provided')
        
        return values


class MessageMetadata(BaseModel):
    """Message metadata specification."""
    
    source: str = Field(
        ..., 
        description="Message source identifier",
        min_length=1,
        max_length=100
    )
    target: Optional[str] = Field(
        None,
        description="Message target identifier",
        max_length=100
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID for message tracing"
    )
    session_id: Optional[str] = Field(
        None,
        description="Session identifier"
    )
    user_id: Optional[str] = Field(
        None,
        description="User identifier"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Message timestamp"
    )
    
    class Config:
        strict = True
        forbid_extra = True


class MessageSpec(BaseModel):
    """Complete message specification."""
    
    message_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique message identifier"
    )
    tenant_id: str = Field(
        ..., 
        description="Tenant identifier",
        min_length=1
    )
    message_type: MessageType = Field(
        ..., 
        description="Message type"
    )
    priority: MessagePriority = Field(
        default=MessagePriority.NORMAL,
        description="Message priority"
    )
    content: MessageContent = Field(
        ..., 
        description="Message content"
    )
    metadata: MessageMetadata = Field(
        ..., 
        description="Message metadata"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Message tags"
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="Message expiration timestamp"
    )
    
    @validator('message_id')
    def validate_message_id(cls, v):
        """Validate message ID format."""
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError('message_id must be a valid UUID')
    
    @validator('tenant_id')
    def validate_tenant_id(cls, v):
        """Validate tenant ID format."""
        if not v or not v.strip():
            raise ValueError('tenant_id cannot be empty')
        return v.strip()
    
    @validator('tags')
    def validate_tags(cls, v):
        """Validate message tags."""
        if not isinstance(v, list):
            raise ValueError('tags must be a list')
        
        for i, tag in enumerate(v):
            if not isinstance(tag, str):
                raise ValueError(f'tag {i} must be a string')
            if not tag.strip():
                raise ValueError(f'tag {i} cannot be empty')
            if len(tag) > 50:
                raise ValueError(f'tag {i} cannot exceed 50 characters')
        
        return [tag.strip() for tag in v]
    
    @validator('expires_at')
    def validate_expires_at(cls, v):
        """Validate expiration timestamp."""
        if v is not None:
            now = datetime.now(timezone.utc)
            if v <= now:
                raise ValueError('expires_at must be in the future')
        return v
    
    @root_validator
    def validate_message_consistency(cls, values):
        """Validate message specification consistency."""
        message_type = values.get('message_type')
        content = values.get('content')
        metadata = values.get('metadata')
        
        if message_type and content:
            # Validate content based on message type
            if message_type == MessageType.USER_INPUT:
                if not content.text and not content.data:
                    raise ValueError('user_input messages must have text or data content')
            
            elif message_type == MessageType.TOOL_REQUEST:
                if not content.data:
                    raise ValueError('tool_request messages must have data content')
            
            elif message_type == MessageType.ERROR_MESSAGE:
                if not content.text:
                    raise ValueError('error_message must have text content')
        
        if metadata and metadata.timestamp:
            expires_at = values.get('expires_at')
            if expires_at and expires_at <= metadata.timestamp:
                raise ValueError('expires_at must be after message timestamp')
        
        return values
    
    class Config:
        strict = True
        forbid_extra = True
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
