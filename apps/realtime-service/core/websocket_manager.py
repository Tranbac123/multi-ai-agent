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

from .backpressure_manager import BackpressureManager, OutboundMessage, MessageType, PerConnectionQueue

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
            "circuit_breaker_threshold": 10  # consecutive failures
        }
        self.total_messages_sent = 0
        self.total_messages_received = 0
        self.total_bytes_sent = 0
        self.total_bytes_received = 0
        self.total_send_errors = 0
        self.total_receive_errors = 0
        
        # Ping/pong settings
        self.ping_interval_seconds = 30
        self.pong_timeout_seconds = 10
        self.max_ping_failures = 3
        
        logger.info("WebSocket manager initialized")
    
    async def connect(self, websocket: WebSocket, tenant_id: str) -> str:
        """Accept WebSocket connection and set up backpressure."""
        
        await websocket.accept()
        
        connection_id = str(uuid.uuid4())
        
        # Create connection
        connection = WebSocketConnection(
            connection_id=connection_id,
            tenant_id=tenant_id,
            websocket=websocket,
            created_at=datetime.now()
        )
        
        self.connections[connection_id] = connection
        self.total_connections += 1
        self.active_connections += 1
        self.ws_active_connections += 1
        
        # Add to tenant connections
        if tenant_id not in self.tenant_connections:
            self.tenant_connections[tenant_id] = set()
        self.tenant_connections[tenant_id].add(connection_id)
        
        # Create backpressure queue
        await self.backpressure_manager.create_connection(connection_id, tenant_id)
        
        # Start ping/pong monitoring
        asyncio.create_task(self._ping_monitor(connection_id))
        
        logger.info("WebSocket connection established", 
                   connection_id=connection_id,
                   tenant_id=tenant_id)
        
        return connection_id
    
    async def disconnect(self, connection_id: str, reason: str = "client_disconnect"):
        """Disconnect WebSocket and clean up."""
        
        if connection_id not in self.connections:
            return
        
        connection = self.connections[connection_id]
        connection.is_connected = False
        
        # Remove from tenant connections
        if connection.tenant_id in self.tenant_connections:
            self.tenant_connections[connection.tenant_id].discard(connection_id)
            if not self.tenant_connections[connection.tenant_id]:
                del self.tenant_connections[connection.tenant_id]
        
        # Clean up backpressure queue
        await self.backpressure_manager.remove_connection(connection_id)
        
        # Close WebSocket
        try:
            await connection.websocket.close()
        except Exception as e:
            logger.warning("Error closing WebSocket", 
                          connection_id=connection_id,
                          error=str(e))
        
        del self.connections[connection_id]
        self.active_connections -= 1
        self.ws_active_connections -= 1
        
        logger.info("WebSocket connection closed", 
                   connection_id=connection_id,
                   tenant_id=connection.tenant_id,
                   reason=reason)
    
    async def send_message(
        self, 
        connection_id: str, 
        content: Any, 
        message_type: MessageType = MessageType.INTERMEDIATE,
        priority: int = 0,
        is_final: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send message via WebSocket with backpressure handling."""
        
        if connection_id not in self.connections:
            logger.warning("Connection not found", connection_id=connection_id)
            return False
        
        connection = self.connections[connection_id]
        
        if not connection.is_connected:
            logger.warning("Connection is not active", connection_id=connection_id)
            return False
        
        # Check backpressure policy before sending
        if not self._check_backpressure_policy(connection_id):
            self.ws_backpressure_drops += 1
            logger.warning("Message dropped due to backpressure policy", 
                          connection_id=connection_id)
            return False
        
        # Use backpressure manager to send
        try:
            success = await self.backpressure_manager.send_message(
                connection_id=connection_id,
                content=content,
                message_type=message_type,
                priority=priority,
                is_final=is_final,
                metadata=metadata
            )
            
            if not success:
                self.ws_send_errors += 1
            
            return success
            
        except Exception as e:
            self.ws_send_errors += 1
            logger.error("Error sending message", 
                        connection_id=connection_id,
                        error=str(e))
            return False
    
    def _check_backpressure_policy(self, connection_id: str) -> bool:
        """Check if message sending is allowed based on backpressure policy."""
        if connection_id not in self.connections:
            return False
        
        connection = self.connections[connection_id]
        
        # Check rate limiting
        # This is a simplified implementation - in production you'd use a proper rate limiter
        current_time = datetime.now()
        if not hasattr(connection, 'message_history'):
            connection.message_history = []
        
        # Clean old messages (older than 1 minute)
        connection.message_history = [
            msg_time for msg_time in connection.message_history
            if (current_time - msg_time).total_seconds() < 60
        ]
        
        # Check rate limit
        if len(connection.message_history) >= self.backpressure_policy["rate_limit_per_connection"]:
            return False
        
        # Check burst limit (last 10 seconds)
        recent_messages = [
            msg_time for msg_time in connection.message_history
            if (current_time - msg_time).total_seconds() < 10
        ]
        
        if len(recent_messages) >= self.backpressure_policy["burst_limit"]:
            return False
        
        # Add current message to history
        connection.message_history.append(current_time)
        
        return True
    
    async def send_to_tenant(
        self, 
        tenant_id: str, 
        content: Any, 
        message_type: MessageType = MessageType.INTERMEDIATE,
        priority: int = 0,
        is_final: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Send message to all connections for a tenant."""
        
        if tenant_id not in self.tenant_connections:
            return 0
        
        sent_count = 0
        connection_ids = list(self.tenant_connections[tenant_id])
        
        for connection_id in connection_ids:
            success = await self.send_message(
                connection_id=connection_id,
                content=content,
                message_type=message_type,
                priority=priority,
                is_final=is_final,
                metadata=metadata
            )
            if success:
                sent_count += 1
        
        logger.debug("Message sent to tenant", 
                    tenant_id=tenant_id,
                    sent_count=sent_count,
                    total_connections=len(connection_ids))
        
        return sent_count
    
    async def _flush_connection_queue(self, connection_id: str):
        """Flush queued messages for a connection."""
        
        if connection_id not in self.connections:
            return
        
        connection = self.connections[connection_id]
        queue = self.backpressure_manager.connections.get(connection_id)
        
        if not queue:
            return
        
        # Send messages from queue
        while True:
            message = await queue.dequeue_message()
            if not message:
                break
            
            try:
                # Prepare message for WebSocket
                ws_message = {
                    "message_id": message.message_id,
                    "sequence_number": message.sequence_number,
                    "message_type": message.message_type.value,
                    "content": message.content,
                    "is_final": message.is_final,
                    "metadata": message.metadata,
                    "timestamp": message.timestamp.isoformat()
                }
                
                # Send via WebSocket
                await connection.websocket.send_text(json.dumps(ws_message))
                
                # Update metrics
                connection.message_count += 1
                connection.bytes_sent += len(json.dumps(ws_message))
                self.total_bytes_sent += len(json.dumps(ws_message))
                
                logger.debug("Message sent via WebSocket", 
                           message_id=message.message_id,
                           connection_id=connection_id)
                
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected during send", 
                           connection_id=connection_id)
                await self.disconnect(connection_id, "websocket_disconnect")
                break
            except Exception as e:
                logger.error("Error sending message via WebSocket", 
                           message_id=message.message_id,
                           connection_id=connection_id,
                           error=str(e))
                self.total_send_errors += 1
                break
    
    async def handle_message(self, connection_id: str, message: str):
        """Handle incoming WebSocket message."""
        
        if connection_id not in self.connections:
            return
        
        connection = self.connections[connection_id]
        connection.bytes_received += len(message)
        self.total_bytes_received += len(message)
        
        try:
            data = json.loads(message)
            
            # Handle different message types
            if data.get("type") == "ack":
                # Acknowledge message receipt
                await self._handle_acknowledgment(connection_id, data)
            elif data.get("type") == "pong":
                # Handle pong response
                await self._handle_pong(connection_id)
            elif data.get("type") == "resume":
                # Handle connection resume
                await self._handle_resume(connection_id, data)
            else:
                # Handle regular message
                await self._handle_regular_message(connection_id, data)
            
            self.total_messages_received += 1
            
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in WebSocket message", 
                        connection_id=connection_id,
                        error=str(e))
            self.total_receive_errors += 1
        except Exception as e:
            logger.error("Error handling WebSocket message", 
                        connection_id=connection_id,
                        error=str(e))
            self.total_receive_errors += 1
    
    async def _handle_acknowledgment(self, connection_id: str, data: Dict[str, Any]):
        """Handle message acknowledgment."""
        
        message_id = data.get("message_id")
        sequence_number = data.get("sequence_number")
        
        if message_id and sequence_number:
            await self.backpressure_manager.acknowledge_message(
                connection_id, message_id, sequence_number
            )
            
            logger.debug("Message acknowledged", 
                        connection_id=connection_id,
                        message_id=message_id,
                        sequence_number=sequence_number)
    
    async def _handle_pong(self, connection_id: str):
        """Handle pong response."""
        
        if connection_id in self.connections:
            connection = self.connections[connection_id]
            connection.last_pong = datetime.now()
            
            logger.debug("Pong received", connection_id=connection_id)
    
    async def _handle_resume(self, connection_id: str, data: Dict[str, Any]):
        """Handle connection resume request."""
        
        from_sequence = data.get("from_sequence", 0)
        
        success = await self.backpressure_manager.resume_connection(
            connection_id, from_sequence
        )
        
        logger.info("Connection resume handled", 
                   connection_id=connection_id,
                   from_sequence=from_sequence,
                   success=success)
    
    async def _handle_regular_message(self, connection_id: str, data: Dict[str, Any]):
        """Handle regular WebSocket message."""
        
        # This would typically route to message handlers
        # For now, just log the message
        logger.debug("Regular message received", 
                    connection_id=connection_id,
                    message_type=data.get("type"))
    
    async def _ping_monitor(self, connection_id: str):
        """Monitor connection with ping/pong."""
        
        connection = self.connections.get(connection_id)
        if not connection:
            return
        
        ping_failures = 0
        
        while connection.is_connected and connection_id in self.connections:
            try:
                # Send ping
                ping_message = {
                    "type": "ping",
                    "timestamp": datetime.now().isoformat()
                }
                
                await connection.websocket.send_text(json.dumps(ping_message))
                connection.last_ping = datetime.now()
                
                # Wait for pong
                await asyncio.sleep(self.pong_timeout_seconds)
                
                # Check if pong was received
                if connection.last_pong and connection.last_ping:
                    if connection.last_pong < connection.last_ping:
                        ping_failures += 1
                        logger.warning("Ping timeout", 
                                     connection_id=connection_id,
                                     failures=ping_failures)
                    else:
                        ping_failures = 0
                
                # Disconnect if too many ping failures
                if ping_failures >= self.max_ping_failures:
                    logger.warning("Too many ping failures, disconnecting", 
                                 connection_id=connection_id)
                    await self.disconnect(connection_id, "ping_timeout")
                    break
                
                # Wait before next ping
                await asyncio.sleep(self.ping_interval_seconds)
                
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected during ping", 
                           connection_id=connection_id)
                await self.disconnect(connection_id, "websocket_disconnect")
                break
            except Exception as e:
                logger.error("Error in ping monitor", 
                           connection_id=connection_id,
                           error=str(e))
                ping_failures += 1
                
                if ping_failures >= self.max_ping_failures:
                    await self.disconnect(connection_id, "ping_error")
                    break
    
    async def get_connection_info(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a connection."""
        
        if connection_id not in self.connections:
            return None
        
        connection = self.connections[connection_id]
        backpressure_metrics = self.backpressure_manager.get_connection_metrics(connection_id)
        
        return {
            "connection_id": connection_id,
            "tenant_id": connection.tenant_id,
            "is_connected": connection.is_connected,
            "created_at": connection.created_at.isoformat(),
            "last_ping": connection.last_ping.isoformat() if connection.last_ping else None,
            "last_pong": connection.last_pong.isoformat() if connection.last_pong else None,
            "message_count": connection.message_count,
            "bytes_sent": connection.bytes_sent,
            "bytes_received": connection.bytes_received,
            "backpressure_metrics": backpressure_metrics
        }
    
    def get_tenant_connections(self, tenant_id: str) -> List[str]:
        """Get all connection IDs for a tenant."""
        
        return list(self.tenant_connections.get(tenant_id, []))
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get WebSocket manager metrics."""
        
        backpressure_metrics = self.backpressure_manager.get_global_metrics()
        
        return {
            "total_connections": self.total_connections,
            "active_connections": self.active_connections,
            "ws_active_connections": self.ws_active_connections,
            "ws_backpressure_drops": self.ws_backpressure_drops,
            "ws_send_errors": self.ws_send_errors,
            "total_messages_sent": self.total_messages_sent,
            "total_messages_received": self.total_messages_received,
            "total_bytes_sent": self.total_bytes_sent,
            "total_bytes_received": self.total_bytes_received,
            "total_send_errors": self.total_send_errors,
            "total_receive_errors": self.total_receive_errors,
            "tenants_count": len(self.tenant_connections),
            "backpressure_policy": self.backpressure_policy,
            "backpressure_metrics": backpressure_metrics
        }
