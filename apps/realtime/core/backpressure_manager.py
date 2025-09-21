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
        
        # Drop old messages
        message_age = datetime.now() - message.timestamp
        if message_age > timedelta(minutes=self.max_queue_age_minutes):
            return True
        
        return False


@dataclass
class PerConnectionQueue:
    """Per-connection queue with Redis persistence."""
    
    connection_id: str
    tenant_id: str
    in_memory_queue: Deque[OutboundMessage] = field(default_factory=deque)
    redis_key: str = ""
    max_memory_size: int = 50  # Keep this many messages in memory
    sequence_counter: int = 0
    
    def __post_init__(self):
        """Initialize Redis key after object creation."""
        self.redis_key = f"realtime:queue:{self.tenant_id}:{self.connection_id}"


class BackpressureManager:
    """
    Advanced backpressure manager with Redis persistence and sophisticated policies.
    
    Features:
    - Per-connection Redis outbound queues with sticky sessions
    - Backpressure policies for dropping intermediate chunks when clients are slow
    - Support for resume on reconnect
    - Message sequence numbering and acknowledgments
    - Slow client detection and adaptive handling
    - Priority-based message queuing
    """
    
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.policy = BackpressurePolicy()
        
        # In-memory state
        self.connection_states: Dict[str, ConnectionState] = {}
        self.connection_queues: Dict[str, PerConnectionQueue] = {}
        
        # Metrics
        self.metrics = {
            "messages_queued": 0,
            "messages_sent": 0,
            "messages_dropped": 0,
            "slow_clients": 0,
            "queue_overflows": 0,
            "redis_operations": 0,
            "backpressure_drops": 0,
        }
        
        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        self._shutdown = False
        
        logger.info("BackpressureManager initialized")
    
    async def add_connection(self, connection_id: str, tenant_id: str) -> None:
        """Add a new connection to tracking."""
        
        # Create connection state
        self.connection_states[connection_id] = ConnectionState(
            connection_id=connection_id,
            tenant_id=tenant_id
        )
        
        # Create per-connection queue
        self.connection_queues[connection_id] = PerConnectionQueue(
            connection_id=connection_id,
            tenant_id=tenant_id
        )
        
        # Restore any persisted messages from Redis
        await self._restore_queue_from_redis(connection_id)
        
        logger.info(
            "Connection added to backpressure tracking",
            connection_id=connection_id,
            tenant_id=tenant_id
        )
    
    async def remove_connection(self, connection_id: str) -> None:
        """Remove a connection and persist its queue to Redis."""
        
        if connection_id in self.connection_queues:
            # Persist remaining messages to Redis before removal
            await self._persist_queue_to_redis(connection_id)
            
            # Clean up
            del self.connection_queues[connection_id]
            
        if connection_id in self.connection_states:
            del self.connection_states[connection_id]
        
        logger.info(
            "Connection removed from backpressure tracking",
            connection_id=connection_id
        )
    
    async def queue_message(
        self, 
        connection_id: str, 
        message: Dict[str, Any],
        message_type: MessageType = MessageType.INTERMEDIATE,
        is_final: bool = False,
        priority: int = 0
    ) -> bool:
        """
        Queue a message for delivery with backpressure handling.
        
        Returns True if message was queued, False if dropped.
        """
        
        if connection_id not in self.connection_states:
            logger.warning(
                "Attempted to queue message for unknown connection",
                connection_id=connection_id
            )
            return False
        
        connection_state = self.connection_states[connection_id]
        queue = self.connection_queues[connection_id]
        
        # Create outbound message
        outbound_message = OutboundMessage(
            message_id=f"{connection_id}_{queue.sequence_counter}",
            connection_id=connection_id,
            tenant_id=connection_state.tenant_id,
            message_type=message_type,
            content=message,
            priority=priority,
            sequence_number=queue.sequence_counter,
            is_final=is_final
        )
        
        queue.sequence_counter += 1
        
        # Apply backpressure policy
        if self.policy.should_drop_message(outbound_message, connection_state):
            connection_state.total_messages_dropped += 1
            self.metrics["messages_dropped"] += 1
            self.metrics["backpressure_drops"] += 1
            
            logger.debug(
                "Message dropped due to backpressure policy",
                connection_id=connection_id,
                message_type=message_type.value,
                queue_size=connection_state.queue_size
            )
            return False
        
        # Add to queue
        queue.in_memory_queue.append(outbound_message)
        connection_state.queue_size += 1
        self.metrics["messages_queued"] += 1
        
        # Persist to Redis if queue is getting large
        if len(queue.in_memory_queue) > queue.max_memory_size:
            await self._persist_overflow_to_redis(connection_id)
        
        logger.debug(
            "Message queued successfully",
            connection_id=connection_id,
            message_type=message_type.value,
            queue_size=connection_state.queue_size,
            sequence=outbound_message.sequence_number
        )
        
        return True
    
    async def get_next_message(self, connection_id: str) -> Optional[OutboundMessage]:
        """Get the next message for a connection."""
        
        if connection_id not in self.connection_queues:
            return None
        
        queue = self.connection_queues[connection_id]
        
        # Try in-memory queue first
        if queue.in_memory_queue:
            message = queue.in_memory_queue.popleft()
            self.connection_states[connection_id].queue_size -= 1
            return message
        
        # Try Redis if in-memory queue is empty
        message = await self._get_message_from_redis(connection_id)
        if message:
            self.connection_states[connection_id].queue_size -= 1
        
        return message
    
    async def acknowledge_message(
        self, 
        connection_id: str, 
        sequence_number: int
    ) -> None:
        """Acknowledge receipt of a message."""
        
        if connection_id not in self.connection_states:
            return
        
        connection_state = self.connection_states[connection_id]
        connection_state.last_acknowledged_sequence = sequence_number
        connection_state.last_activity = datetime.now()
        
        # Update slow client detection
        await self._update_slow_client_status(connection_id)
        
        logger.debug(
            "Message acknowledged",
            connection_id=connection_id,
            sequence=sequence_number
        )
    
    async def _restore_queue_from_redis(self, connection_id: str) -> None:
        """Restore messages from Redis for a reconnecting client."""
        
        if not self.redis:
            return
        
        try:
            queue = self.connection_queues[connection_id]
            messages_data = await self.redis.lrange(queue.redis_key, 0, -1)
            
            for message_data in messages_data:
                message_dict = json.loads(message_data)
                message = OutboundMessage(**message_dict)
                queue.in_memory_queue.append(message)
            
            # Clear Redis after restoring
            await self.redis.delete(queue.redis_key)
            self.metrics["redis_operations"] += 2
            
            logger.info(
                "Restored messages from Redis",
                connection_id=connection_id,
                message_count=len(messages_data)
            )
            
        except Exception as e:
            logger.error(
                "Failed to restore messages from Redis",
                connection_id=connection_id,
                error=str(e)
            )
    
    async def _persist_queue_to_redis(self, connection_id: str) -> None:
        """Persist remaining messages to Redis."""
        
        if not self.redis:
            return
        
        try:
            queue = self.connection_queues[connection_id]
            
            if queue.in_memory_queue:
                # Convert messages to JSON
                messages_data = []
                for message in queue.in_memory_queue:
                    message_dict = {
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
                    messages_data.append(json.dumps(message_dict))
                
                # Store in Redis with TTL
                await self.redis.rpush(queue.redis_key, *messages_data)
                await self.redis.expire(queue.redis_key, 3600)  # 1 hour TTL
                self.metrics["redis_operations"] += 2
                
                logger.info(
                    "Persisted messages to Redis",
                    connection_id=connection_id,
                    message_count=len(messages_data)
                )
                
        except Exception as e:
            logger.error(
                "Failed to persist messages to Redis",
                connection_id=connection_id,
                error=str(e)
            )
    
    async def _persist_overflow_to_redis(self, connection_id: str) -> None:
        """Move oldest messages from memory to Redis when queue overflows."""
        
        if not self.redis:
            return
        
        try:
            queue = self.connection_queues[connection_id]
            
            # Move half the messages to Redis
            messages_to_persist = len(queue.in_memory_queue) // 2
            
            messages_data = []
            for _ in range(messages_to_persist):
                if queue.in_memory_queue:
                    message = queue.in_memory_queue.popleft()
                    message_dict = {
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
                    messages_data.append(json.dumps(message_dict))
            
            if messages_data:
                await self.redis.lpush(queue.redis_key, *messages_data)
                await self.redis.expire(queue.redis_key, 3600)
                self.metrics["redis_operations"] += 2
                
                logger.debug(
                    "Moved overflow messages to Redis",
                    connection_id=connection_id,
                    message_count=len(messages_data)
                )
                
        except Exception as e:
            logger.error(
                "Failed to persist overflow to Redis",
                connection_id=connection_id,
                error=str(e)
            )
    
    async def _get_message_from_redis(self, connection_id: str) -> Optional[OutboundMessage]:
        """Get the next message from Redis."""
        
        if not self.redis:
            return None
        
        try:
            queue = self.connection_queues[connection_id]
            message_data = await self.redis.rpop(queue.redis_key)
            
            if message_data:
                message_dict = json.loads(message_data)
                # Restore datetime
                message_dict["timestamp"] = datetime.fromisoformat(message_dict["timestamp"])
                message_dict["message_type"] = MessageType(message_dict["message_type"])
                
                self.metrics["redis_operations"] += 1
                return OutboundMessage(**message_dict)
                
        except Exception as e:
            logger.error(
                "Failed to get message from Redis",
                connection_id=connection_id,
                error=str(e)
            )
        
        return None
    
    async def _update_slow_client_status(self, connection_id: str) -> None:
        """Update slow client detection."""
        
        connection_state = self.connection_states[connection_id]
        
        # Calculate time since last ack
        time_since_ack = datetime.now() - connection_state.last_activity
        
        # Update slow client status
        was_slow = connection_state.is_slow
        connection_state.is_slow = (
            time_since_ack.total_seconds() * 1000 > connection_state.slow_client_threshold_ms
        )
        
        # Update metrics
        if connection_state.is_slow and not was_slow:
            self.metrics["slow_clients"] += 1
        elif not connection_state.is_slow and was_slow:
            self.metrics["slow_clients"] -= 1
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive backpressure metrics."""
        
        # Calculate real-time metrics
        total_queue_size = sum(
            state.queue_size for state in self.connection_states.values()
        )
        
        active_connections = len(self.connection_states)
        slow_connections = sum(
            1 for state in self.connection_states.values() if state.is_slow
        )
        
        return {
            **self.metrics,
            "active_connections": active_connections,
            "total_queue_size": total_queue_size,
            "slow_connections": slow_connections,
            "connection_details": {
                conn_id: {
                    "tenant_id": state.tenant_id,
                    "queue_size": state.queue_size,
                    "is_slow": state.is_slow,
                    "dropped_messages": state.dropped_messages,
                    "total_sent": state.total_messages_sent
                }
                for conn_id, state in self.connection_states.items()
            }
        }
    
    async def cleanup_expired_connections(self) -> None:
        """Clean up expired connections and old Redis keys."""
        
        current_time = datetime.now()
        expired_connections = []
        
        for connection_id, state in self.connection_states.items():
            # Mark connections as expired if no activity for 30 minutes
            if (current_time - state.last_activity).total_seconds() > 1800:
                expired_connections.append(connection_id)
        
        for connection_id in expired_connections:
            await self.remove_connection(connection_id)
            
        logger.info(
            "Cleaned up expired connections",
            expired_count=len(expired_connections)
        )
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the backpressure manager."""
        
        self._shutdown = True
        
        # Persist all remaining queues to Redis
        for connection_id in list(self.connection_queues.keys()):
            await self._persist_queue_to_redis(connection_id)
        
        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()
        
        logger.info("BackpressureManager shutdown completed")
