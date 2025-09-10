"""Realtime Service - WebSocket service with backpressure handling."""

import asyncio
import json
import time
import uuid
from typing import Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
import structlog
import redis.asyncio as redis

from apps.realtime.core.connection_manager import ConnectionManager
from apps.realtime.core.backpressure_handler import BackpressureHandler
from libs.contracts.error import ErrorResponse, ServiceError

logger = structlog.get_logger(__name__)

app = FastAPI(title="Realtime Service", version="1.0.0")

# Global instances
connection_manager: Optional[ConnectionManager] = None
backpressure_handler: Optional[BackpressureHandler] = None
redis_client: Optional[redis.Redis] = None


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup."""
    global connection_manager, backpressure_handler, redis_client
    
    # Initialize Redis client
    redis_client = redis.Redis(host="localhost", port=6379, db=3)
    await redis_client.ping()
    
    # Initialize connection manager
    connection_manager = ConnectionManager(redis_client)
    
    # Initialize backpressure handler
    backpressure_handler = BackpressureHandler(
        connection_manager=connection_manager,
        max_queue_size=1000,
        drop_policy="intermediate"
    )
    
    logger.info("Realtime service started")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global redis_client
    
    if redis_client:
        await redis_client.close()
    
    logger.info("Realtime service stopped")


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket, tenant_id: str, user_id: Optional[str] = None):
    """WebSocket endpoint for chat with backpressure handling."""
    if not connection_manager or not backpressure_handler:
        raise HTTPException(status_code=500, detail="Service not initialized")
    
    # Accept connection
    await websocket.accept()
    
    # Generate session ID
    session_id = str(uuid.uuid4())
    
    # Register connection
    await connection_manager.register_connection(
        websocket, tenant_id, user_id, session_id
    )
    
    try:
        # Send welcome message
        welcome_message = {
            "type": "welcome",
            "session_id": session_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "timestamp": time.time()
        }
        await websocket.send_text(json.dumps(welcome_message))
        
        # Handle messages
        while True:
            try:
                # Receive message
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Process message
                await _process_message(websocket, tenant_id, user_id, session_id, message)
                
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected", tenant_id=tenant_id, user_id=user_id)
                break
            except json.JSONDecodeError:
                error_message = {
                    "type": "error",
                    "message": "Invalid JSON format",
                    "timestamp": time.time()
                }
                await websocket.send_text(json.dumps(error_message))
            except Exception as e:
                logger.error("WebSocket error", error=str(e), tenant_id=tenant_id)
                error_message = {
                    "type": "error",
                    "message": "Internal server error",
                    "timestamp": time.time()
                }
                await websocket.send_text(json.dumps(error_message))
    
    finally:
        # Unregister connection
        await connection_manager.unregister_connection(websocket, tenant_id, user_id)


async def _process_message(
    websocket: WebSocket,
    tenant_id: str,
    user_id: Optional[str],
    session_id: str,
    message: Dict[str, Any]
):
    """Process incoming WebSocket message."""
    message_type = message.get("type", "unknown")
    
    if message_type == "ping":
        # Handle ping
        pong_message = {
            "type": "pong",
            "timestamp": time.time()
        }
        await websocket.send_text(json.dumps(pong_message))
    
    elif message_type == "chat":
        # Handle chat message
        await _handle_chat_message(websocket, tenant_id, user_id, session_id, message)
    
    elif message_type == "typing":
        # Handle typing indicator
        await _handle_typing_indicator(websocket, tenant_id, user_id, session_id, message)
    
    else:
        # Unknown message type
        error_message = {
            "type": "error",
            "message": f"Unknown message type: {message_type}",
            "timestamp": time.time()
        }
        await websocket.send_text(json.dumps(error_message))


async def _handle_chat_message(
    websocket: WebSocket,
    tenant_id: str,
    user_id: Optional[str],
    session_id: str,
    message: Dict[str, Any]
):
    """Handle chat message with backpressure."""
    if not backpressure_handler:
        return
    
    # Create response message
    response_message = {
        "type": "response",
        "content": f"Echo: {message.get('content', '')}",
        "timestamp": time.time(),
        "session_id": session_id
    }
    
    # Send with backpressure handling
    await backpressure_handler.send_message(
        websocket, tenant_id, user_id, session_id, response_message
    )


async def _handle_typing_indicator(
    websocket: WebSocket,
    tenant_id: str,
    user_id: Optional[str],
    session_id: str,
    message: Dict[str, Any]
):
    """Handle typing indicator."""
    # Broadcast typing indicator to other connections in the same tenant
    if connection_manager:
        await connection_manager.broadcast_to_tenant(
            tenant_id, {
                "type": "typing",
                "user_id": user_id,
                "is_typing": message.get("is_typing", False),
                "timestamp": time.time()
            },
            exclude_session=session_id
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if not connection_manager or not backpressure_handler:
        raise HTTPException(status_code=500, detail="Service not initialized")
    
    # Get connection stats
    stats = await connection_manager.get_connection_stats()
    
    return {
        "status": "healthy",
        "active_connections": stats["active_connections"],
        "tenant_connections": stats["tenant_connections"],
        "timestamp": time.time()
    }


@app.get("/metrics")
async def get_metrics():
    """Get service metrics."""
    if not connection_manager or not backpressure_handler:
        raise HTTPException(status_code=500, detail="Service not initialized")
    
    # Get connection stats
    connection_stats = await connection_manager.get_connection_stats()
    
    # Get backpressure stats
    backpressure_stats = await backpressure_handler.get_stats()
    
    # Calculate required metrics
    ws_active_connections = connection_stats.get("active_connections", 0)
    ws_backpressure_drops = backpressure_stats.get("messages_dropped", 0)
    ws_send_errors = backpressure_stats.get("queue_overflows", 0)
    
    return {
        "ws_active_connections": ws_active_connections,
        "ws_backpressure_drops": ws_backpressure_drops,
        "ws_send_errors": ws_send_errors,
        "connections": connection_stats,
        "backpressure": backpressure_stats,
        "timestamp": time.time()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)