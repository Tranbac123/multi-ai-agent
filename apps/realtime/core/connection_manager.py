"""Connection manager for WebSocket connections with Redis session store."""

import asyncio
import json
import time
from typing import Dict, Any, Optional, Set, List
from uuid import UUID
import structlog
import redis.asyncio as redis

logger = structlog.get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections with Redis session store."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.active_connections: Dict[str, Any] = {}
        self.tenant_connections: Dict[UUID, Set[str]] = {}
        self.user_connections: Dict[UUID, Set[str]] = {}
        self.session_ttl = 3600  # 1 hour
    
    async def register_connection(
        self,
        connection_id: str,
        websocket: Any,
        tenant_id: UUID,
        session_id: str,
        user_id: Optional[UUID] = None
    ):
        """Register new WebSocket connection."""
        try:
            # Store connection info
            connection_info = {
                "websocket": websocket,
                "tenant_id": str(tenant_id),
                "session_id": session_id,
                "user_id": str(user_id) if user_id else None,
                "connected_at": time.time(),
                "last_ping": time.time()
            }
            
            self.active_connections[connection_id] = connection_info
            
            # Add to tenant connections
            if tenant_id not in self.tenant_connections:
                self.tenant_connections[tenant_id] = set()
            self.tenant_connections[tenant_id].add(connection_id)
            
            # Add to user connections if user_id provided
            if user_id:
                if user_id not in self.user_connections:
                    self.user_connections[user_id] = set()
                self.user_connections[user_id].add(connection_id)
            
            # Store in Redis for persistence
            await self.redis.hset(
                f"ws_session:{connection_id}",
                mapping={
                    "tenant_id": str(tenant_id),
                    "session_id": session_id,
                    "user_id": str(user_id) if user_id else "",
                    "connected_at": str(time.time())
                }
            )
            await self.redis.expire(f"ws_session:{connection_id}", self.session_ttl)
            
            logger.info("Connection registered", 
                       connection_id=connection_id, 
                       tenant_id=tenant_id,
                       user_id=user_id)
            
        except Exception as e:
            logger.error("Failed to register connection", 
                        connection_id=connection_id, 
                        error=str(e))
    
    async def unregister_connection(self, connection_id: str):
        """Unregister WebSocket connection."""
        try:
            if connection_id not in self.active_connections:
                return
            
            connection_info = self.active_connections[connection_id]
            tenant_id = UUID(connection_info["tenant_id"])
            user_id = connection_info.get("user_id")
            
            # Remove from active connections
            del self.active_connections[connection_id]
            
            # Remove from tenant connections
            if tenant_id in self.tenant_connections:
                self.tenant_connections[tenant_id].discard(connection_id)
                if not self.tenant_connections[tenant_id]:
                    del self.tenant_connections[tenant_id]
            
            # Remove from user connections
            if user_id:
                user_uuid = UUID(user_id)
                if user_uuid in self.user_connections:
                    self.user_connections[user_uuid].discard(connection_id)
                    if not self.user_connections[user_uuid]:
                        del self.user_connections[user_uuid]
            
            # Remove from Redis
            await self.redis.delete(f"ws_session:{connection_id}")
            
            logger.info("Connection unregistered", connection_id=connection_id)
            
        except Exception as e:
            logger.error("Failed to unregister connection", 
                        connection_id=connection_id, 
                        error=str(e))
    
    async def send_message(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """Send message to specific connection."""
        try:
            if connection_id not in self.active_connections:
                logger.warning("Connection not found", connection_id=connection_id)
                return False
            
            websocket = self.active_connections[connection_id]["websocket"]
            await websocket.send_text(json.dumps(message))
            
            # Update last ping time
            self.active_connections[connection_id]["last_ping"] = time.time()
            
            return True
            
        except Exception as e:
            logger.error("Failed to send message", 
                        connection_id=connection_id, 
                        error=str(e))
            return False
    
    async def send_error(self, connection_id: str, error_message: str):
        """Send error message to connection."""
        error_msg = {
            "type": "error",
            "message": error_message,
            "timestamp": time.time()
        }
        await self.send_message(connection_id, error_msg)
    
    async def send_ping(self, connection_id: str):
        """Send ping message to connection."""
        ping_msg = {
            "type": "ping",
            "timestamp": time.time()
        }
        await self.send_message(connection_id, ping_msg)
    
    async def broadcast_to_tenant(
        self, 
        tenant_id: UUID, 
        message: Dict[str, Any], 
        exclude_connections: List[str] = None
    ):
        """Broadcast message to all tenant connections."""
        try:
            if tenant_id not in self.tenant_connections:
                return
            
            exclude_set = set(exclude_connections or [])
            connections = self.tenant_connections[tenant_id] - exclude_set
            
            for connection_id in connections:
                await self.send_message(connection_id, message)
            
            logger.info("Message broadcasted to tenant", 
                       tenant_id=tenant_id, 
                       connection_count=len(connections))
            
        except Exception as e:
            logger.error("Failed to broadcast to tenant", 
                        tenant_id=tenant_id, 
                        error=str(e))
    
    async def broadcast_to_user(
        self, 
        user_id: UUID, 
        message: Dict[str, Any], 
        exclude_connections: List[str] = None
    ):
        """Broadcast message to all user connections."""
        try:
            if user_id not in self.user_connections:
                return
            
            exclude_set = set(exclude_connections or [])
            connections = self.user_connections[user_id] - exclude_set
            
            for connection_id in connections:
                await self.send_message(connection_id, message)
            
            logger.info("Message broadcasted to user", 
                       user_id=user_id, 
                       connection_count=len(connections))
            
        except Exception as e:
            logger.error("Failed to broadcast to user", 
                        user_id=user_id, 
                        error=str(e))
    
    async def get_tenant_connections(self, tenant_id: UUID) -> List[Dict[str, Any]]:
        """Get all connections for tenant."""
        try:
            if tenant_id not in self.tenant_connections:
                return []
            
            connections = []
            for connection_id in self.tenant_connections[tenant_id]:
                if connection_id in self.active_connections:
                    conn_info = self.active_connections[connection_id]
                    connections.append({
                        "connection_id": connection_id,
                        "session_id": conn_info["session_id"],
                        "user_id": conn_info.get("user_id"),
                        "connected_at": conn_info["connected_at"],
                        "last_ping": conn_info["last_ping"]
                    })
            
            return connections
            
        except Exception as e:
            logger.error("Failed to get tenant connections", 
                        tenant_id=tenant_id, 
                        error=str(e))
            return []
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get connection metrics."""
        try:
            total_connections = len(self.active_connections)
            tenant_count = len(self.tenant_connections)
            user_count = len(self.user_connections)
            
            # Calculate connections per tenant
            tenant_connection_counts = {
                str(tenant_id): len(connections)
                for tenant_id, connections in self.tenant_connections.items()
            }
            
            return {
                "total_connections": total_connections,
                "tenant_count": tenant_count,
                "user_count": user_count,
                "tenant_connection_counts": tenant_connection_counts,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error("Failed to get metrics", error=str(e))
            return {}
    
    async def cleanup_stale_connections(self):
        """Clean up stale connections (runs in background)."""
        while True:
            try:
                current_time = time.time()
                stale_connections = []
                
                for connection_id, conn_info in self.active_connections.items():
                    # Consider connection stale if no ping for 5 minutes
                    if current_time - conn_info["last_ping"] > 300:
                        stale_connections.append(connection_id)
                
                for connection_id in stale_connections:
                    await self.unregister_connection(connection_id)
                    logger.info("Stale connection cleaned up", connection_id=connection_id)
                
                # Wait 60 seconds before next cleanup
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error("Connection cleanup error", error=str(e))
                await asyncio.sleep(60)
