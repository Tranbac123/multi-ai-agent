"""
Realtime Backpressure Manager

Implements per-connection Redis outbound queues with sticky sessions,
backpressure policies for dropping intermediate chunks when clients are slow,
and support for resume on reconnect.
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Set, Deque
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import structlog
from datetime import datetime, timedelta
import hashlib

logger = structlog.get_logger(__name__)


class MessageType(Enum):
    """Message types for backpressure management."""
    INTERMEDIATE = "intermediate"
    FINAL = "final"
    HEARTBEAT = "heartbeat"
    RESUME = "resume"


@dataclass
class OutboundMessage:
    """Outbound message with backpressure metadata."""
    
    message_id: str
    connection_id: str
    tenant_id: str
    message_type: MessageType
    content: Any
    priority: int = 0  # Higher number = higher priority
    timestamp: datetime = field(default_factory=datetime.now)
    sequence_number: int = 0
    is_final: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectionState:
    """Connection state for backpressure management."""
    
    connection_id: str
    tenant_id: str
    is_active: bool = True
    last_activity: datetime = field(default_factory=datetime.now)
    queue_size: int = 0
    max_queue_size: int = 100
    drop_threshold: int = 80  # Drop messages when queue exceeds this
    last_sent_sequence: int = 0
    last_acknowledged_sequence: int = 0
    slow_client_threshold_ms: int = 1000  # Consider client slow if no ack in this time
    is_slow: bool = False
    dropped_messages: int = 0
    total_messages_sent: int = 0
    total_messages_dropped: int = 0


class BackpressurePolicy:
    """Backpressure policy implementation."""
    
    def __init__(self):
        self.drop_intermediate_when_slow = True
        self.drop_intermediate_when_queue_full = True
        self.always_deliver_final = True
        self.max_queue_age_minutes = 5
        
        logger.info("Backpressure policy initialized")
    
    def should_drop_message(
        self, 
        message: OutboundMessage, 
        connection_state: ConnectionState
    ) -> bool:
        """Determine if a message should be dropped based on backpressure policy."""
        
        # Always deliver final messages
        if message.is_final or message.message_type == MessageType.FINAL:
            return False
        
        # Drop intermediate messages if client is slow
        if (self.drop_intermediate_when_slow and 
            connection_state.is_slow and 
            message.message_type == MessageType.INTERMEDIATE):
            return True
        
        # Drop intermediate messages if queue is full
        if (self.drop_intermediate_when_queue_full and 
            connection_state.queue_size > connection_state.drop_threshold and 
            message.message_type == MessageType.INTERMEDIATE):
            return True
        
        return False
    
    def should_drop_old_messages(
        self, 
        message: OutboundMessage, 
        connection_state: ConnectionState
    ) -> bool:
        """Determine if a message should be dropped due to age."""
        
        age_minutes = (datetime.now() - message.timestamp).total_seconds() / 60
        return age_minutes > self.max_queue_age_minutes


class PerConnectionQueue:
    """Per-connection outbound queue with Redis backing."""
    
    def __init__(self, redis_client, connection_id: str, tenant_id: str):
        self.redis_client = redis_client
        self.connection_id = connection_id
        self.tenant_id = tenant_id
        
        # Local queue for fast access
        self.local_queue: Deque[OutboundMessage] = deque()
        self.max_local_size = 50
        
        # Connection state
        self.connection_state = ConnectionState(
            connection_id=connection_id,
            tenant_id=tenant_id
        )
        
        # Backpressure policy
        self.backpressure_policy = BackpressurePolicy()
        
        # Metrics
        self.total_enqueued = 0
        self.total_dequeued = 0
        self.total_dropped = 0
        
        logger.info("Per-connection queue initialized", 
                   connection_id=connection_id,
                   tenant_id=tenant_id)
    
    async def enqueue_message(self, message: OutboundMessage) -> bool:
        """Enqueue a message with backpressure handling."""
        
        # Check if message should be dropped
        if self.backpressure_policy.should_drop_message(message, self.connection_state):
            self.total_dropped += 1
            self.connection_state.total_messages_dropped += 1
            logger.debug("Message dropped due to backpressure", 
                        message_id=message.message_id,
                        connection_id=self.connection_id,
                        reason="backpressure_policy")
            return False
        
        # Check if old messages should be dropped
        if self.backpressure_policy.should_drop_old_messages(message, self.connection_state):
            self.total_dropped += 1
            self.connection_state.total_messages_dropped += 1
            logger.debug("Message dropped due to age", 
                        message_id=message.message_id,
                        connection_id=self.connection_id)
            return False
        
        # Add to local queue
        self.local_queue.append(message)
        self.total_enqueued += 1
        self.connection_state.queue_size += 1
        
        # Store in Redis for persistence
        await self._store_in_redis(message)
        
        # Trim local queue if too large
        while len(self.local_queue) > self.max_local_size:
            old_message = self.local_queue.popleft()
            self.connection_state.queue_size -= 1
        
        logger.debug("Message enqueued", 
                    message_id=message.message_id,
                    connection_id=self.connection_id,
                    queue_size=self.connection_state.queue_size)
        
        return True
    
    async def dequeue_message(self) -> Optional[OutboundMessage]:
        """Dequeue the next message from the queue."""
        
        # Try local queue first
        if self.local_queue:
            message = self.local_queue.popleft()
            self.connection_state.queue_size -= 1
            self.total_dequeued += 1
            return message
        
        # Load from Redis if local queue is empty
        message = await self._load_from_redis()
        if message:
            self.total_dequeued += 1
        
        return message
    
    async def peek_message(self) -> Optional[OutboundMessage]:
        """Peek at the next message without removing it."""
        
        if self.local_queue:
            return self.local_queue[0]
        
        # Check Redis
        return await self._peek_from_redis()
    
    async def acknowledge_message(self, message_id: str, sequence_number: int):
        """Acknowledge receipt of a message."""
        
        self.connection_state.last_acknowledged_sequence = sequence_number
        self.connection_state.last_activity = datetime.now()
        
        # Remove from Redis
        await self._remove_from_redis(message_id)
        
        logger.debug("Message acknowledged", 
                    message_id=message_id,
                    connection_id=self.connection_id,
                    sequence_number=sequence_number)
    
    async def _store_in_redis(self, message: OutboundMessage):
        """Store message in Redis for persistence."""
        
        try:
            key = f"queue:{self.connection_id}:{message.message_id}"
            data = {
                "message_id": message.message_id,
                "connection_id": message.connection_id,
                "tenant_id": message.tenant_id,
                "message_type": message.message_type.value,
                "content": message.content,
                "priority": message.priority,
                "timestamp": message.timestamp.isoformat(),
                "sequence_number": message.sequence_number,
                "is_final": message.is_final,
                "metadata": message.metadata
            }
            
            await self.redis_client.setex(
                key,
                3600,  # 1 hour TTL
                json.dumps(data, default=str)
            )
            
        except Exception as e:
            logger.error("Failed to store message in Redis", 
                        message_id=message.message_id,
                        error=str(e))
    
    async def _load_from_redis(self) -> Optional[OutboundMessage]:
        """Load message from Redis."""
        
        try:
            # Get all message keys for this connection
            pattern = f"queue:{self.connection_id}:*"
            keys = await self.redis_client.keys(pattern)
            
            if not keys:
                return None
            
            # Load the oldest message (simplified - in production, use sorted sets)
            for key in sorted(keys):
                data_str = await self.redis_client.get(key)
                if data_str:
                    data = json.loads(data_str)
                    
                    message = OutboundMessage(
                        message_id=data["message_id"],
                        connection_id=data["connection_id"],
                        tenant_id=data["tenant_id"],
                        message_type=MessageType(data["message_type"]),
                        content=data["content"],
                        priority=data["priority"],
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                        sequence_number=data["sequence_number"],
                        is_final=data["is_final"],
                        metadata=data["metadata"]
                    )
                    
                    # Remove from Redis
                    await self.redis_client.delete(key)
                    
                    return message
            
            return None
            
        except Exception as e:
            logger.error("Failed to load message from Redis", 
                        connection_id=self.connection_id,
                        error=str(e))
            return None
    
    async def _peek_from_redis(self) -> Optional[OutboundMessage]:
        """Peek at message in Redis without removing it."""
        
        try:
            pattern = f"queue:{self.connection_id}:*"
            keys = await self.redis_client.keys(pattern)
            
            if not keys:
                return None
            
            # Get the oldest message
            key = sorted(keys)[0]
            data_str = await self.redis_client.get(key)
            
            if data_str:
                data = json.loads(data_str)
                
                return OutboundMessage(
                    message_id=data["message_id"],
                    connection_id=data["connection_id"],
                    tenant_id=data["tenant_id"],
                    message_type=MessageType(data["message_type"]),
                    content=data["content"],
                    priority=data["priority"],
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                    sequence_number=data["sequence_number"],
                    is_final=data["is_final"],
                    metadata=data["metadata"]
                )
            
            return None
            
        except Exception as e:
            logger.error("Failed to peek message from Redis", 
                        connection_id=self.connection_id,
                        error=str(e))
            return None
    
    async def _remove_from_redis(self, message_id: str):
        """Remove message from Redis."""
        
        try:
            key = f"queue:{self.connection_id}:{message_id}"
            await self.redis_client.delete(key)
            
        except Exception as e:
            logger.error("Failed to remove message from Redis", 
                        message_id=message_id,
                        error=str(e))
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get queue metrics."""
        return {
            "connection_id": self.connection_id,
            "tenant_id": self.tenant_id,
            "queue_size": self.connection_state.queue_size,
            "is_active": self.connection_state.is_active,
            "is_slow": self.connection_state.is_slow,
            "total_enqueued": self.total_enqueued,
            "total_dequeued": self.total_dequeued,
            "total_dropped": self.total_dropped,
            "dropped_messages": self.connection_state.dropped_messages,
            "total_messages_sent": self.connection_state.total_messages_sent,
            "total_messages_dropped": self.connection_state.total_messages_dropped,
            "last_activity": self.connection_state.last_activity.isoformat(),
            "last_sent_sequence": self.connection_state.last_sent_sequence,
            "last_acknowledged_sequence": self.connection_state.last_acknowledged_sequence
        }


class BackpressureManager:
    """Manages backpressure across all connections."""
    
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.connections: Dict[str, PerConnectionQueue] = {}
        self.active_connections: Set[str] = set()
        
        # Metrics
        self.total_connections = 0
        self.total_messages_sent = 0
        self.total_messages_dropped = 0
        self.total_send_errors = 0
        
        logger.info("Backpressure manager initialized")
    
    async def create_connection(self, connection_id: str, tenant_id: str) -> PerConnectionQueue:
        """Create a new connection queue."""
        
        if connection_id in self.connections:
            return self.connections[connection_id]
        
        queue = PerConnectionQueue(self.redis_client, connection_id, tenant_id)
        self.connections[connection_id] = queue
        self.active_connections.add(connection_id)
        self.total_connections += 1
        
        logger.info("Connection created", 
                   connection_id=connection_id,
                   tenant_id=tenant_id)
        
        return queue
    
    async def remove_connection(self, connection_id: str):
        """Remove a connection and clean up its queue."""
        
        if connection_id in self.connections:
            queue = self.connections[connection_id]
            queue.connection_state.is_active = False
            
            # Clean up Redis keys
            try:
                pattern = f"queue:{connection_id}:*"
                keys = await self.redis_client.keys(pattern)
                if keys:
                    await self.redis_client.delete(*keys)
            except Exception as e:
                logger.error("Failed to clean up Redis keys", 
                            connection_id=connection_id,
                            error=str(e))
            
            del self.connections[connection_id]
            self.active_connections.discard(connection_id)
            
            logger.info("Connection removed", connection_id=connection_id)
    
    async def send_message(
        self, 
        connection_id: str, 
        content: Any, 
        message_type: MessageType = MessageType.INTERMEDIATE,
        priority: int = 0,
        is_final: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send a message to a connection with backpressure handling."""
        
        if connection_id not in self.connections:
            logger.warning("Connection not found", connection_id=connection_id)
            return False
        
        queue = self.connections[connection_id]
        
        # Create message
        message_id = self._generate_message_id()
        sequence_number = queue.connection_state.last_sent_sequence + 1
        
        message = OutboundMessage(
            message_id=message_id,
            connection_id=connection_id,
            tenant_id=queue.tenant_id,
            message_type=message_type,
            content=content,
            priority=priority,
            sequence_number=sequence_number,
            is_final=is_final,
            metadata=metadata or {}
        )
        
        # Enqueue message
        success = await queue.enqueue_message(message)
        
        if success:
            queue.connection_state.last_sent_sequence = sequence_number
            queue.connection_state.total_messages_sent += 1
            self.total_messages_sent += 1
            
            # Update slow client detection
            self._update_slow_client_detection(queue)
            
            logger.debug("Message sent", 
                        message_id=message_id,
                        connection_id=connection_id,
                        message_type=message_type.value,
                        is_final=is_final)
        else:
            queue.connection_state.total_messages_dropped += 1
            self.total_messages_dropped += 1
            
            logger.debug("Message dropped", 
                        message_id=message_id,
                        connection_id=connection_id,
                        message_type=message_type.value)
        
        return success
    
    async def acknowledge_message(self, connection_id: str, message_id: str, sequence_number: int):
        """Acknowledge receipt of a message."""
        
        if connection_id not in self.connections:
            return
        
        queue = self.connections[connection_id]
        await queue.acknowledge_message(message_id, sequence_number)
        
        # Update slow client detection
        self._update_slow_client_detection(queue)
    
    def _update_slow_client_detection(self, queue: PerConnectionQueue):
        """Update slow client detection based on acknowledgment timing."""
        
        connection_state = queue.connection_state
        
        # Check if client is slow based on last activity
        time_since_last_activity = (datetime.now() - connection_state.last_activity).total_seconds() * 1000
        
        was_slow = connection_state.is_slow
        connection_state.is_slow = time_since_last_activity > connection_state.slow_client_threshold_ms
        
        if was_slow != connection_state.is_slow:
            logger.info("Slow client status changed", 
                       connection_id=connection_state.connection_id,
                       is_slow=connection_state.is_slow,
                       time_since_last_activity_ms=time_since_last_activity)
    
    async def resume_connection(self, connection_id: str, from_sequence: int = 0):
        """Resume a connection from a specific sequence number."""
        
        if connection_id not in self.connections:
            logger.warning("Cannot resume unknown connection", connection_id=connection_id)
            return False
        
        queue = self.connections[connection_id]
        connection_state = queue.connection_state
        
        # Update connection state
        connection_state.is_active = True
        connection_state.last_activity = datetime.now()
        connection_state.is_slow = False
        
        # Send resume message
        resume_metadata = {
            "resume_from_sequence": from_sequence,
            "last_acknowledged_sequence": connection_state.last_acknowledged_sequence,
            "total_messages_sent": connection_state.total_messages_sent,
            "total_messages_dropped": connection_state.total_messages_dropped
        }
        
        success = await self.send_message(
            connection_id=connection_id,
            content={"resume": True, "from_sequence": from_sequence},
            message_type=MessageType.RESUME,
            priority=10,  # High priority for resume messages
            metadata=resume_metadata
        )
        
        logger.info("Connection resumed", 
                   connection_id=connection_id,
                   from_sequence=from_sequence,
                   success=success)
        
        return success
    
    def _generate_message_id(self) -> str:
        """Generate unique message ID."""
        timestamp = str(int(time.time() * 1000))
        random_part = hashlib.md5(timestamp.encode()).hexdigest()[:8]
        return f"msg_{timestamp}_{random_part}"
    
    def get_connection_metrics(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a specific connection."""
        
        if connection_id not in self.connections:
            return None
        
        return self.connections[connection_id].get_metrics()
    
    def get_global_metrics(self) -> Dict[str, Any]:
        """Get global backpressure metrics."""
        
        active_connections = len(self.active_connections)
        total_queue_size = sum(
            queue.connection_state.queue_size 
            for queue in self.connections.values()
        )
        
        slow_connections = sum(
            1 for queue in self.connections.values() 
            if queue.connection_state.is_slow
        )
        
        return {
            "total_connections": self.total_connections,
            "active_connections": active_connections,
            "total_queue_size": total_queue_size,
            "slow_connections": slow_connections,
            "total_messages_sent": self.total_messages_sent,
            "total_messages_dropped": self.total_messages_dropped,
            "total_send_errors": self.total_send_errors,
            "drop_rate": self.total_messages_dropped / max(1, self.total_messages_sent),
            "connections": {
                conn_id: queue.get_metrics() 
                for conn_id, queue in self.connections.items()
            }
        }
    
    async def cleanup_inactive_connections(self, max_inactive_minutes: int = 30):
        """Clean up inactive connections."""
        
        cutoff_time = datetime.now() - timedelta(minutes=max_inactive_minutes)
        connections_to_remove = []
        
        for connection_id, queue in self.connections.items():
            if queue.connection_state.last_activity < cutoff_time:
                connections_to_remove.append(connection_id)
        
        for connection_id in connections_to_remove:
            await self.remove_connection(connection_id)
        
        if connections_to_remove:
            logger.info("Cleaned up inactive connections", 
                       removed_count=len(connections_to_remove),
                       remaining_count=len(self.connections))
