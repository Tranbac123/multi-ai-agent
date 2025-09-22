"""
WebSocket Manager with Backpressure Integration

Manages WebSocket connections with integrated backpressure handling,
sticky sessions, and resume capabilities.
"""

import asyncio
import json
import uuid
from typing import Dict, List, Optional, Any, Set, Callable
from dataclasses import dataclass
import structlog
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from opentelemetry import trace

from src.backpressure_manager import BackpressureManager, OutboundMessage, MessageType

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


@dataclass
class WebSocketConnection:
    """WebSocket connection with metadata."""
    
    connection_id: str
    tenant_id: str
    websocket: WebSocket
    is_connected: bool = True
    created_at: datetime
    last_ping: Optional[datetime] = None
    last_pong: Optional[datetime] = None
    message_count: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0


class WebSocketManager:
    """Manages WebSocket connections with backpressure."""
    
    def __init__(self, backpressure_manager: BackpressureManager):
        self.backpressure_manager = backpressure_manager
        self.connections: Dict[str, WebSocketConnection] = {}
        self.tenant_connections: Dict[str, Set[str]] = {}  # tenant_id -> connection_ids
        
        # Enhanced metrics
        self.ws_active_connections = 0
        self.ws_backpressure_drops = 0
        self.ws_send_errors = 0
        self.total_connections = 0
        self.active_connections = 0
        
        # Backpressure policy configuration
        self.backpressure_policy = {
            "max_queue_size": 1000,
            "drop_threshold": 0.8,
            "rate_limit_per_connection": 100,  # messages per minute
            "burst_limit": 50,  # messages in burst
        }
        
        # Background task for processing messages
        self._processing_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        logger.info("WebSocketManager initialized with backpressure support")
    
    async def connect(self, websocket: WebSocket, tenant_id: str) -> str:
        """Accept a new WebSocket connection."""
        
        connection_id = str(uuid.uuid4())
        
        # Accept the WebSocket connection
        await websocket.accept()
        
        # Create connection tracking
        connection = WebSocketConnection(
            connection_id=connection_id,
            tenant_id=tenant_id,
            websocket=websocket,
            created_at=datetime.now()
        )
        
        self.connections[connection_id] = connection
        
        # Track by tenant
        if tenant_id not in self.tenant_connections:
            self.tenant_connections[tenant_id] = set()
        self.tenant_connections[tenant_id].add(connection_id)
        
        # Add to backpressure manager
        await self.backpressure_manager.add_connection(connection_id, tenant_id)
        
        # Update metrics
        self.total_connections += 1
        self.ws_active_connections += 1
        self.active_connections = len(self.connections)
        
        # Start message processing if not already running
        if not self._processing_task:
            self._processing_task = asyncio.create_task(self._message_processor())
        
        logger.info(
            "WebSocket connection established",
            connection_id=connection_id,
            tenant_id=tenant_id,
            total_connections=self.active_connections
        )
        
        return connection_id
    
    async def disconnect(self, connection_id: str) -> None:
        """Handle WebSocket disconnection."""
        
        if connection_id not in self.connections:
            return
        
        connection = self.connections[connection_id]
        connection.is_connected = False
        
        # Remove from tenant tracking
        if connection.tenant_id in self.tenant_connections:
            self.tenant_connections[connection.tenant_id].discard(connection_id)
            if not self.tenant_connections[connection.tenant_id]:
                del self.tenant_connections[connection.tenant_id]
        
        # Remove from backpressure manager
        await self.backpressure_manager.remove_connection(connection_id)
        
        # Remove from connections
        del self.connections[connection_id]
        
        # Update metrics
        self.ws_active_connections -= 1
        self.active_connections = len(self.connections)
        
        logger.info(
            "WebSocket connection closed",
            connection_id=connection_id,
            tenant_id=connection.tenant_id,
            remaining_connections=self.active_connections
        )
    
    async def send_to_connection(
        self, 
        connection_id: str, 
        message: Dict[str, Any],
        message_type: MessageType = MessageType.INTERMEDIATE,
        is_final: bool = False,
        priority: int = 0
    ) -> bool:
        """Send a message to a specific connection with backpressure handling."""
        
        if connection_id not in self.connections:
            logger.warning(
                "Attempted to send to non-existent connection",
                connection_id=connection_id
            )
            return False
        
        # Queue message with backpressure manager
        queued = await self.backpressure_manager.queue_message(
            connection_id=connection_id,
            message=message,
            message_type=message_type,
            is_final=is_final,
            priority=priority
        )
        
        if not queued:
            self.ws_backpressure_drops += 1
            logger.debug(
                "Message dropped due to backpressure",
                connection_id=connection_id,
                message_type=message_type.value
            )
        
        return queued
    
    async def send_to_tenant(
        self, 
        tenant_id: str, 
        message: Dict[str, Any],
        message_type: MessageType = MessageType.INTERMEDIATE,
        exclude_connection: Optional[str] = None
    ) -> int:
        """Send a message to all connections for a tenant."""
        
        if tenant_id not in self.tenant_connections:
            return 0
        
        connection_ids = self.tenant_connections[tenant_id].copy()
        if exclude_connection:
            connection_ids.discard(exclude_connection)
        
        successful_sends = 0
        for connection_id in connection_ids:
            if await self.send_to_connection(
                connection_id, message, message_type
            ):
                successful_sends += 1
        
        logger.debug(
            "Broadcast message to tenant",
            tenant_id=tenant_id,
            total_connections=len(connection_ids),
            successful_sends=successful_sends
        )
        
        return successful_sends
    
    async def _message_processor(self) -> None:
        """Background task to process outbound message queues."""
        
        logger.info("Message processor started")
        
        while not self._shutdown_event.is_set():
            try:
                # Process messages for all active connections
                for connection_id in list(self.connections.keys()):
                    await self._process_connection_queue(connection_id)
                
                # Brief pause to prevent tight loop
                await asyncio.sleep(0.01)  # 10ms
                
            except Exception as e:
                logger.error(
                    "Error in message processor",
                    error=str(e),
                    exc_info=True
                )
                await asyncio.sleep(1)  # Longer pause on error
        
        logger.info("Message processor stopped")
    
    async def _process_connection_queue(self, connection_id: str) -> None:
        """Process the message queue for a specific connection."""
        
        if connection_id not in self.connections:
            return
        
        connection = self.connections[connection_id]
        
        if not connection.is_connected:
            return
        
        # Process up to 10 messages at once to avoid blocking
        for _ in range(10):
            message = await self.backpressure_manager.get_next_message(connection_id)
            
            if not message:
                break  # No more messages
            
            success = await self._send_websocket_message(connection, message)
            
            if success:
                # Acknowledge successful delivery
                await self.backpressure_manager.acknowledge_message(
                    connection_id, message.sequence_number
                )
            else:
                # Connection is likely broken, will be cleaned up
                break
    
    async def _send_websocket_message(
        self, 
        connection: WebSocketConnection, 
        message: OutboundMessage
    ) -> bool:
        """Send a message via WebSocket with error handling."""
        
        try:
            # Prepare message envelope
            envelope = {
                "id": message.message_id,
                "type": message.message_type.value,
                "sequence": message.sequence_number,
                "timestamp": message.timestamp.isoformat(),
                "data": message.content,
                "is_final": message.is_final,
                "tenant_id": message.tenant_id
            }
            
            # Send via WebSocket
            await connection.websocket.send_text(json.dumps(envelope))
            
            # Update connection stats
            connection.message_count += 1
            connection.bytes_sent += len(json.dumps(envelope))
            
            logger.debug(
                "Message sent successfully",
                connection_id=connection.connection_id,
                message_id=message.message_id,
                sequence=message.sequence_number
            )
            
            return True
            
        except WebSocketDisconnect:
            logger.info(
                "WebSocket disconnected during send",
                connection_id=connection.connection_id
            )
            connection.is_connected = False
            await self.disconnect(connection.connection_id)
            return False
            
        except Exception as e:
            logger.error(
                "Failed to send WebSocket message",
                connection_id=connection.connection_id,
                message_id=message.message_id,
                error=str(e)
            )
            self.ws_send_errors += 1
            connection.is_connected = False
            await self.disconnect(connection.connection_id)
            return False
    
    async def handle_incoming_message(
        self, 
        connection_id: str, 
        message: str
    ) -> Optional[Dict[str, Any]]:
        """Handle incoming WebSocket message."""
        
        if connection_id not in self.connections:
            return None
        
        connection = self.connections[connection_id]
        
        try:
            data = json.loads(message)
            connection.bytes_received += len(message)
            
            # Handle acknowledgments
            if data.get("type") == "ack":
                sequence = data.get("sequence")
                if sequence is not None:
                    await self.backpressure_manager.acknowledge_message(
                        connection_id, sequence
                    )
                return None
            
            # Handle ping/pong
            if data.get("type") == "ping":
                connection.last_ping = datetime.now()
                await self.send_to_connection(
                    connection_id,
                    {"type": "pong", "timestamp": datetime.now().isoformat()},
                    MessageType.HEARTBEAT
                )
                return None
            
            if data.get("type") == "pong":
                connection.last_pong = datetime.now()
                return None
            
            # Return processed message for further handling
            return {
                "connection_id": connection_id,
                "tenant_id": connection.tenant_id,
                "data": data,
                "timestamp": datetime.now()
            }
            
        except json.JSONDecodeError:
            logger.warning(
                "Invalid JSON received",
                connection_id=connection_id,
                message_preview=message[:100]
            )
            return None
        except Exception as e:
            logger.error(
                "Error handling incoming message",
                connection_id=connection_id,
                error=str(e)
            )
            return None
    
    async def get_connection_stats(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific connection."""
        
        if connection_id not in self.connections:
            return None
        
        connection = self.connections[connection_id]
        
        return {
            "connection_id": connection_id,
            "tenant_id": connection.tenant_id,
            "is_connected": connection.is_connected,
            "created_at": connection.created_at.isoformat(),
            "message_count": connection.message_count,
            "bytes_sent": connection.bytes_sent,
            "bytes_received": connection.bytes_received,
            "last_ping": connection.last_ping.isoformat() if connection.last_ping else None,
            "last_pong": connection.last_pong.isoformat() if connection.last_pong else None
        }
    
    async def get_tenant_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get statistics for all connections of a tenant."""
        
        if tenant_id not in self.tenant_connections:
            return {
                "tenant_id": tenant_id,
                "connection_count": 0,
                "connections": []
            }
        
        connection_ids = self.tenant_connections[tenant_id]
        connections_stats = []
        
        for connection_id in connection_ids:
            stats = await self.get_connection_stats(connection_id)
            if stats:
                connections_stats.append(stats)
        
        return {
            "tenant_id": tenant_id,
            "connection_count": len(connections_stats),
            "connections": connections_stats
        }
    
    async def get_overall_stats(self) -> Dict[str, Any]:
        """Get overall WebSocket manager statistics."""
        
        # Get backpressure metrics
        backpressure_metrics = await self.backpressure_manager.get_metrics()
        
        # Calculate tenant stats
        tenant_stats = {}
        for tenant_id in self.tenant_connections:
            tenant_stats[tenant_id] = await self.get_tenant_stats(tenant_id)
        
        return {
            "websocket_manager": {
                "total_connections": self.total_connections,
                "active_connections": self.active_connections,
                "ws_backpressure_drops": self.ws_backpressure_drops,
                "ws_send_errors": self.ws_send_errors,
                "tenant_count": len(self.tenant_connections)
            },
            "backpressure": backpressure_metrics,
            "tenants": tenant_stats,
            "policy": self.backpressure_policy
        }
    
    async def _ping_monitor(self) -> None:
        """Monitor connection health with ping/pong."""
        
        while not self._shutdown_event.is_set():
            try:
                current_time = datetime.now()
                
                for connection_id, connection in list(self.connections.items()):
                    # Send ping if no activity for 30 seconds
                    if (connection.last_ping is None or 
                        (current_time - connection.last_ping).total_seconds() > 30):
                        
                        await self.send_to_connection(
                            connection_id,
                            {"type": "ping", "timestamp": current_time.isoformat()},
                            MessageType.HEARTBEAT
                        )
                        connection.last_ping = current_time
                    
                    # Check for stale connections (no pong for 60 seconds)
                    if (connection.last_pong and 
                        (current_time - connection.last_pong).total_seconds() > 60):
                        
                        logger.warning(
                            "Connection appears stale, disconnecting",
                            connection_id=connection_id
                        )
                        await self.disconnect(connection_id)
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(
                    "Error in ping monitor",
                    error=str(e),
                    exc_info=True
                )
                await asyncio.sleep(30)  # Longer pause on error
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the WebSocket manager."""
        
        logger.info("Shutting down WebSocket manager")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Close all active connections
        for connection_id in list(self.connections.keys()):
            await self.disconnect(connection_id)
        
        # Cancel background tasks
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        
        # Shutdown backpressure manager
        await self.backpressure_manager.shutdown()
        
        logger.info("WebSocket manager shutdown completed")
