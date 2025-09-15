"""Realtime tests for WebSocket backpressure and session management."""

from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

class BackpressureStatus(Enum):
    """Backpressure status levels."""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    OVERFLOW = "overflow"

class ConnectionStatus(Enum):
    """WebSocket connection status."""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    BACKPRESSURE = "backpressure"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"

@dataclass
class WebSocketMessage:
    """WebSocket message structure."""
    message_id: str
    timestamp: datetime
    content: str
    message_type: str
    priority: int
    size_bytes: int
    
@dataclass
class BackpressureMetrics:
    """Backpressure monitoring metrics."""
    queue_size: int
    dropped_messages: int
    sent_messages: int
    backpressure_level: BackpressureStatus
    avg_processing_time_ms: float
    connection_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'queue_size': self.queue_size,
            'dropped_messages': self.dropped_messages,
            'sent_messages': self.sent_messages,
            'backpressure_level': self.backpressure_level.value,
            'avg_processing_time_ms': self.avg_processing_time_ms,
            'connection_count': self.connection_count
        }