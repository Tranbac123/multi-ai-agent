"""Enhanced WebSocket support for API Gateway."""

from fastapi import WebSocket, WebSocketDisconnect, Depends
from typing import Dict, List, Optional, Set
import json
import asyncio
import uuid
from datetime import datetime
import structlog
from libs.clients.auth import get_current_tenant
from libs.clients.rate_limiter import RateLimiter
from libs.utils.exceptions import APIException
from libs.contracts.message import MessageSpec, MessageRole

logger = structlog.get_logger(__name__)


class ConnectionManager:
    """Enhanced connection manager with tenant isolation and rate limiting."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.tenant_connections: Dict[
            str, Set[str]
        ] = {}  # tenant_id -> set of session_ids
        self.user_sessions: Dict[str, str] = {}  # user_id -> session_id
        self.rate_limiter = RateLimiter()

    async def connect(
        self,
        websocket: WebSocket,
        session_id: str,
        tenant_id: str,
        user_id: Optional[str] = None,
    ):
        """Connect WebSocket with tenant isolation."""
        await websocket.accept()
        self.active_connections[session_id] = websocket

        # Add to tenant connections
        if tenant_id not in self.tenant_connections:
            self.tenant_connections[tenant_id] = set()
        self.tenant_connections[tenant_id].add(session_id)

        if user_id:
            self.user_sessions[user_id] = session_id

        logger.info(
            "WebSocket connected",
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )

    def disconnect(self, session_id: str, tenant_id: str):
        """Disconnect WebSocket and clean up."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]

        # Remove from tenant connections
        if tenant_id in self.tenant_connections:
            self.tenant_connections[tenant_id].discard(session_id)
            if not self.tenant_connections[tenant_id]:
                del self.tenant_connections[tenant_id]

        # Remove from user sessions
        user_id = next(
            (uid for uid, sid in self.user_sessions.items() if sid == session_id), None
        )
        if user_id:
            del self.user_sessions[user_id]

        logger.info(
            "WebSocket disconnected", session_id=session_id, tenant_id=tenant_id
        )

    async def send_personal_message(
        self, message: dict, session_id: str, tenant_id: str
    ):
        """Send message to specific session with tenant validation."""
        if session_id not in self.active_connections:
            logger.warning(
                "Attempted to send message to non-existent session",
                session_id=session_id,
                tenant_id=tenant_id,
            )
            return

        # Verify tenant access
        if (
            tenant_id not in self.tenant_connections
            or session_id not in self.tenant_connections[tenant_id]
        ):
            logger.warning(
                "Unauthorized tenant access attempt",
                session_id=session_id,
                tenant_id=tenant_id,
            )
            return

        try:
            await self.active_connections[session_id].send_text(json.dumps(message))
        except Exception as e:
            logger.error(
                "Failed to send message",
                session_id=session_id,
                tenant_id=tenant_id,
                error=str(e),
            )

    async def send_typing_indicator(
        self, session_id: str, tenant_id: str, is_typing: bool = True
    ):
        """Send typing indicator with tenant validation."""
        message = {
            "type": "typing",
            "is_typing": is_typing,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.send_personal_message(message, session_id, tenant_id)

    async def broadcast_to_tenant(
        self, message: dict, tenant_id: str, exclude_session: Optional[str] = None
    ):
        """Broadcast message to all connections in a tenant."""
        if tenant_id not in self.tenant_connections:
            return

        for session_id in self.tenant_connections[tenant_id]:
            if session_id != exclude_session:
                try:
                    await self.active_connections[session_id].send_text(
                        json.dumps(message)
                    )
                except Exception as e:
                    logger.error(
                        "Failed to broadcast message",
                        session_id=session_id,
                        tenant_id=tenant_id,
                        error=str(e),
                    )

    async def check_rate_limit(self, session_id: str, tenant_id: str) -> bool:
        """Check if session is within rate limits."""
        return await self.rate_limiter.is_allowed(f"websocket:{tenant_id}:{session_id}")


manager = ConnectionManager()


class WebSocketHandler:
    """Enhanced WebSocket handler with YAML workflow integration."""

    def __init__(self):
        self.workflow_loader = None  # Will be initialized with workflow loader

    async def handle_message(
        self, websocket: WebSocket, session_id: str, tenant_id: str, data: dict
    ):
        """Handle incoming WebSocket message with enhanced processing."""
        try:
            # Check rate limits
            if not await manager.check_rate_limit(session_id, tenant_id):
                await self._send_error(
                    websocket,
                    session_id,
                    tenant_id,
                    "Rate limit exceeded. Please slow down.",
                )
                return

            message_type = data.get("type", "message")

            if message_type == "message":
                await self._handle_chat_message(websocket, session_id, tenant_id, data)
            elif message_type == "typing":
                await self._handle_typing(websocket, session_id, tenant_id, data)
            elif message_type == "ping":
                await self._handle_ping(websocket, session_id, tenant_id, data)
            elif message_type == "workflow_request":
                await self._handle_workflow_request(
                    websocket, session_id, tenant_id, data
                )
            else:
                await self._send_error(
                    websocket,
                    session_id,
                    tenant_id,
                    f"Unknown message type: {message_type}",
                )

        except Exception as e:
            logger.error(
                "Error handling WebSocket message",
                session_id=session_id,
                tenant_id=tenant_id,
                error=str(e),
            )
            await self._send_error(
                websocket, session_id, tenant_id, "Internal server error"
            )

    async def _handle_chat_message(
        self, websocket: WebSocket, session_id: str, tenant_id: str, data: dict
    ):
        """Handle chat message with YAML workflow integration."""
        text = data.get("text", "").strip()
        if not text:
            await self._send_error(websocket, session_id, tenant_id, "Empty message")
            return

        # Send typing indicator
        await manager.send_typing_indicator(session_id, tenant_id, True)

        try:
            # Process message through YAML workflow system
            response = await self._process_message_with_workflows(
                text, data.get("context", {}), tenant_id
            )

            # Send response
            await self._send_response(websocket, session_id, tenant_id, response)

        except Exception as e:
            logger.error(
                "Error processing message",
                session_id=session_id,
                tenant_id=tenant_id,
                error=str(e),
            )
            await self._send_error(
                websocket, session_id, tenant_id, "Failed to process message"
            )
        finally:
            # Stop typing indicator
            await manager.send_typing_indicator(session_id, tenant_id, False)

    async def _process_message_with_workflows(
        self, text: str, context: dict, tenant_id: str
    ) -> dict:
        """Process message through YAML workflow system."""
        # This would integrate with the orchestrator service
        # For now, return a mock response
        return {
            "type": "message",
            "text": f"Processed message: {text} (tenant: {tenant_id})",
            "metadata": {
                "workflow": "customer_support_workflow",
                "tenant_id": tenant_id,
                "timestamp": datetime.utcnow().isoformat(),
            },
        }

    async def _handle_workflow_request(
        self, websocket: WebSocket, session_id: str, tenant_id: str, data: dict
    ):
        """Handle workflow-specific requests."""
        workflow_name = data.get("workflow")
        workflow_data = data.get("data", {})

        try:
            # Process workflow request
            result = await self._execute_workflow(
                workflow_name, workflow_data, tenant_id
            )

            response = {
                "type": "workflow_response",
                "workflow": workflow_name,
                "result": result,
                "timestamp": datetime.utcnow().isoformat(),
            }

            await self._send_response(websocket, session_id, tenant_id, response)

        except Exception as e:
            logger.error(
                "Workflow execution failed",
                workflow=workflow_name,
                tenant_id=tenant_id,
                error=str(e),
            )
            await self._send_error(
                websocket, session_id, tenant_id, f"Workflow execution failed: {str(e)}"
            )

    async def _execute_workflow(
        self, workflow_name: str, workflow_data: dict, tenant_id: str
    ) -> dict:
        """Execute YAML workflow."""
        # This would integrate with the orchestrator service
        # For now, return mock data
        return {
            "workflow": workflow_name,
            "status": "completed",
            "result": f"Workflow {workflow_name} executed successfully",
            "tenant_id": tenant_id,
        }

    async def _send_response(
        self, websocket: WebSocket, session_id: str, tenant_id: str, response: dict
    ):
        """Send response to client."""
        message = {
            "type": "response",
            "data": response,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await manager.send_personal_message(message, session_id, tenant_id)

    async def _send_error(
        self, websocket: WebSocket, session_id: str, tenant_id: str, error_message: str
    ):
        """Send error message to client."""
        message = {
            "type": "error",
            "message": error_message,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await manager.send_personal_message(message, session_id, tenant_id)

    async def _handle_typing(
        self, websocket: WebSocket, session_id: str, tenant_id: str, data: dict
    ):
        """Handle typing indicator."""
        is_typing = data.get("is_typing", False)
        await manager.send_typing_indicator(session_id, tenant_id, is_typing)

    async def _handle_ping(
        self, websocket: WebSocket, session_id: str, tenant_id: str, data: dict
    ):
        """Handle ping message."""
        pong_message = {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
        await manager.send_personal_message(pong_message, session_id, tenant_id)


async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str = None,
    tenant_id: str = None,
    user_id: str = None,
):
    """Enhanced WebSocket endpoint with tenant isolation."""
    if not session_id:
        session_id = str(uuid.uuid4())

    if not tenant_id:
        tenant_id = "default"  # In production, this should come from auth

    handler = WebSocketHandler()

    try:
        await manager.connect(websocket, session_id, tenant_id, user_id)

        # Send welcome message
        welcome_message = {
            "type": "welcome",
            "session_id": session_id,
            "tenant_id": tenant_id,
            "message": "Connected to AI Customer Agent",
            "timestamp": datetime.utcnow().isoformat(),
        }
        await manager.send_personal_message(welcome_message, session_id, tenant_id)

        # Listen for messages
        while True:
            data = await websocket.receive_text()
            try:
                message_data = json.loads(data)
                await handler.handle_message(
                    websocket, session_id, tenant_id, message_data
                )
            except json.JSONDecodeError:
                await handler._send_error(
                    websocket, session_id, tenant_id, "Invalid JSON format"
                )

    except WebSocketDisconnect:
        manager.disconnect(session_id, tenant_id)
        logger.info(
            "WebSocket disconnected", session_id=session_id, tenant_id=tenant_id
        )
    except Exception as e:
        logger.error(
            "WebSocket error", session_id=session_id, tenant_id=tenant_id, error=str(e)
        )
        manager.disconnect(session_id, tenant_id)
