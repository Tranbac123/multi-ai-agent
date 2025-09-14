"""Connection manager for WebSocket connections."""

import asyncio
import json
import time
from typing import Dict, List, Set, Optional, Any
from fastapi import WebSocket
import structlog
import redis.asyncio as redis

logger = structlog.get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections with Redis session store."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.connections: Dict[str, WebSocket] = {}  # session_id -> websocket
        self.tenant_connections: Dict[
            str, Set[str]
        ] = {}  # tenant_id -> set of session_ids
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> set of session_ids
        self._lock = asyncio.Lock()

    @property
    def active_connections(self) -> Dict[str, WebSocket]:
        """Get active connections."""
        return self.connections

    async def register_connection(
        self,
        websocket: WebSocket,
        tenant_id: str,
        user_id: Optional[str],
        session_id: str,
    ) -> None:
        """Register a new WebSocket connection."""
        async with self._lock:
            # Store connection
            self.connections[session_id] = websocket

            # Add to tenant connections
            if tenant_id not in self.tenant_connections:
                self.tenant_connections[tenant_id] = set()
            self.tenant_connections[tenant_id].add(session_id)

            # Add to user connections if user_id provided
            if user_id:
                if user_id not in self.user_connections:
                    self.user_connections[user_id] = set()
                self.user_connections[user_id].add(session_id)

            # Store session in Redis
            session_data = {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "session_id": session_id,
                "connected_at": time.time(),
                "last_activity": time.time(),
            }
            await self.redis.hset(f"session:{session_id}", mapping=session_data)
            await self.redis.expire(f"session:{session_id}", 3600)  # 1 hour TTL

            logger.info(
                "Connection registered",
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
            )

    async def unregister_connection(
        self, websocket: WebSocket, tenant_id: str, user_id: Optional[str]
    ) -> None:
        """Unregister a WebSocket connection."""
        async with self._lock:
            # Find session_id for this connection
            session_id = None
            for sid, ws in self.connections.items():
                if ws == websocket:
                    session_id = sid
                    break

            if not session_id:
                logger.warning("Connection not found for unregistration")
                return

            # Remove from connections
            self.connections.pop(session_id, None)

            # Remove from tenant connections
            if tenant_id in self.tenant_connections:
                self.tenant_connections[tenant_id].discard(session_id)
                if not self.tenant_connections[tenant_id]:
                    del self.tenant_connections[tenant_id]

            # Remove from user connections
            if user_id and user_id in self.user_connections:
                self.user_connections[user_id].discard(session_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]

            # Remove session from Redis
            await self.redis.delete(f"session:{session_id}")

            logger.info(
                "Connection unregistered",
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
            )

    async def get_connection(self, session_id: str) -> Optional[WebSocket]:
        """Get WebSocket connection by session ID."""
        return self.connections.get(session_id)

    async def get_tenant_connections(self, tenant_id: str) -> List[WebSocket]:
        """Get all connections for a tenant."""
        connections = []
        if tenant_id in self.tenant_connections:
            for session_id in self.tenant_connections[tenant_id]:
                websocket = self.connections.get(session_id)
                if websocket:
                    connections.append(websocket)
        return connections

    async def get_user_connections(self, user_id: str) -> List[WebSocket]:
        """Get all connections for a user."""
        connections = []
        if user_id in self.user_connections:
            for session_id in self.user_connections[user_id]:
                websocket = self.connections.get(session_id)
                if websocket:
                    connections.append(websocket)
        return connections

    async def broadcast_to_tenant(
        self,
        tenant_id: str,
        message: Dict[str, Any],
        exclude_session: Optional[str] = None,
    ) -> int:
        """Broadcast message to all connections in a tenant."""
        connections = await self.get_tenant_connections(tenant_id)
        sent_count = 0

        for websocket in connections:
            try:
                # Skip excluded session
                if exclude_session:
                    session_id = None
                    for sid, ws in self.connections.items():
                        if ws == websocket:
                            session_id = sid
                            break
                    if session_id == exclude_session:
                        continue

                await websocket.send_text(json.dumps(message))
                sent_count += 1

            except Exception as e:
                logger.error(
                    "Failed to send message to tenant connection",
                    error=str(e),
                    tenant_id=tenant_id,
                )

        logger.info(
            "Broadcast to tenant",
            tenant_id=tenant_id,
            sent_count=sent_count,
            total_connections=len(connections),
        )

        return sent_count

    async def broadcast_to_user(
        self,
        user_id: str,
        message: Dict[str, Any],
        exclude_session: Optional[str] = None,
    ) -> int:
        """Broadcast message to all connections for a user."""
        connections = await self.get_user_connections(user_id)
        sent_count = 0

        for websocket in connections:
            try:
                # Skip excluded session
                if exclude_session:
                    session_id = None
                    for sid, ws in self.connections.items():
                        if ws == websocket:
                            session_id = sid
                            break
                    if session_id == exclude_session:
                        continue

                await websocket.send_text(json.dumps(message))
                sent_count += 1

            except Exception as e:
                logger.error(
                    "Failed to send message to user connection",
                    error=str(e),
                    user_id=user_id,
                )

        logger.info(
            "Broadcast to user",
            user_id=user_id,
            sent_count=sent_count,
            total_connections=len(connections),
        )

        return sent_count

    async def send_to_session(self, session_id: str, message: Dict[str, Any]) -> bool:
        """Send message to specific session."""
        websocket = await self.get_connection(session_id)
        if not websocket:
            logger.warning("Session not found", session_id=session_id)
            return False

        try:
            await websocket.send_text(json.dumps(message))
            logger.info("Message sent to session", session_id=session_id)
            return True
        except Exception as e:
            logger.error(
                "Failed to send message to session", error=str(e), session_id=session_id
            )
            return False

    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        async with self._lock:
            return {
                "active_connections": len(self.connections),
                "tenant_connections": {
                    tenant_id: len(sessions)
                    for tenant_id, sessions in self.tenant_connections.items()
                },
                "user_connections": {
                    user_id: len(sessions)
                    for user_id, sessions in self.user_connections.items()
                },
                "total_tenants": len(self.tenant_connections),
                "total_users": len(self.user_connections),
            }

    async def cleanup_stale_connections(self) -> int:
        """Clean up stale connections."""
        stale_sessions = []

        async with self._lock:
            for session_id, websocket in self.connections.items():
                try:
                    # Try to send a ping to check if connection is alive
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    # Connection is stale
                    stale_sessions.append(session_id)

        # Remove stale connections
        for session_id in stale_sessions:
            websocket = self.connections.get(session_id)
            if websocket:
                # Get session data from Redis to determine tenant_id and user_id
                session_data = await self.redis.hgetall(f"session:{session_id}")
                tenant_id = session_data.get("tenant_id")
                user_id = session_data.get("user_id")

                await self.unregister_connection(websocket, tenant_id, user_id)

        logger.info("Cleaned up stale connections", count=len(stale_sessions))
        return len(stale_sessions)
