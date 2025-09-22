"""Realtime service with enhanced backpressure handling and Redis session storage."""

import asyncio
import json
import time
from typing import Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.responses import JSONResponse
import structlog
import redis.asyncio as redis
from contextlib import asynccontextmanager

from src.core.backpressure_handler import BackpressureHandler, BackpressureMetrics
from src.core.connection_manager import ConnectionManager
from src.core.backpressure_manager import BackpressureManager, MessageType
from src.core.websocket_manager import WebSocketManager

logger = structlog.get_logger(__name__)

# Global variables for Redis and handlers
redis_client: Optional[redis.Redis] = None
connection_manager: Optional[ConnectionManager] = None
backpressure_handler: Optional[BackpressureHandler] = None
metrics_collector: Optional[BackpressureMetrics] = None

# Enhanced components
backpressure_manager: Optional[BackpressureManager] = None
websocket_manager: Optional[WebSocketManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global redis_client, connection_manager, backpressure_handler, metrics_collector

    # Initialize Redis connection
    redis_client = redis.Redis(
        host="localhost",
        port=6379,
        db=0,
        decode_responses=False,  # Keep as bytes for JSON serialization
    )

    # Initialize connection manager
    connection_manager = ConnectionManager(redis_client)

    # Initialize backpressure handler with Redis
    backpressure_handler = BackpressureHandler(
        connection_manager=connection_manager,
        redis_client=redis_client,
        max_queue_size=1000,
        drop_policy="intermediate",
        session_ttl=3600,
    )

    # Initialize metrics collector
    metrics_collector = BackpressureMetrics(redis_client)

    # Start cleanup task
    await backpressure_handler.start_cleanup_task()

    logger.info("Realtime service started with Redis session storage")

    yield

    # Cleanup
    if backpressure_handler:
        await backpressure_handler.shutdown()

    if redis_client:
        await redis_client.close()

    logger.info("Realtime service shutdown")


app = FastAPI(
    title="Realtime Service",
    description="WebSocket service with backpressure handling and Redis session storage",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "realtime"}


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    try:
        # Check Redis connection
        await redis_client.ping()
        return {"status": "ready", "service": "realtime"}
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service not ready")


@app.get("/metrics")
async def get_metrics():
    """Get realtime service metrics."""
    try:
        if not backpressure_handler:
            raise HTTPException(status_code=503, detail="Service not ready")

        stats = await backpressure_handler.get_stats()

        # Add additional metrics
        stats.update(
            {"timestamp": time.time(), "service": "realtime", "version": "2.0.0"}
        )

        return JSONResponse(content=stats)

    except Exception as e:
        logger.error("Failed to get metrics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get metrics")


@app.websocket("/ws/{tenant_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    tenant_id: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
):
    """WebSocket endpoint with backpressure handling."""
    if not connection_manager or not backpressure_handler:
        await websocket.close(code=1011, reason="Service not ready")
        return

    # Generate session ID if not provided
    if not session_id:
        session_id = f"{tenant_id}_{user_id}_{int(time.time())}"

    # Accept connection
    await connection_manager.register_connection(websocket, tenant_id, user_id, session_id)

    # Update active connections count
    if backpressure_handler and hasattr(connection_manager, 'active_connections'):
        backpressure_handler.stats["active_connections"] = len(
            connection_manager.active_connections
        )

    try:
        # Send welcome message
        welcome_message = {
            "type": "welcome",
            "session_id": session_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "timestamp": time.time(),
        }

        await backpressure_handler.send_message(
            websocket, tenant_id, user_id, session_id, welcome_message
        )

        # Retrieve any pending messages from Redis
        await _deliver_pending_messages(websocket, session_id, tenant_id)

        # Main message loop
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                message = json.loads(data)

                # Process message
                await _process_client_message(
                    websocket, tenant_id, user_id, session_id, message
                )

            except WebSocketDisconnect:
                logger.info(
                    "WebSocket disconnected", session_id=session_id, tenant_id=tenant_id
                )
                break
            except json.JSONDecodeError:
                logger.warning("Invalid JSON received", session_id=session_id)
                await _send_error_message(websocket, session_id, "Invalid JSON format")
            except Exception as e:
                logger.error(
                    "Error processing message", error=str(e), session_id=session_id
                )
                await _send_error_message(websocket, session_id, "Internal error")

    except Exception as e:
        logger.error(
            "WebSocket error", error=str(e), session_id=session_id, tenant_id=tenant_id
        )
    finally:
        # Disconnect and cleanup
        await connection_manager.unregister_connection(websocket, tenant_id, user_id)

        # Update active connections count
        if backpressure_handler and hasattr(connection_manager, 'active_connections'):
            backpressure_handler.stats["active_connections"] = len(
                connection_manager.active_connections
            )


async def _deliver_pending_messages(
    websocket: WebSocket, session_id: str, tenant_id: str
):
    """Deliver any pending messages from Redis."""
    try:
        if not backpressure_handler:
            return

        # Retrieve messages from Redis
        redis_messages = await backpressure_handler._retrieve_messages_from_redis(
            session_id
        )

        if redis_messages:
            logger.info(
                "Delivering pending messages",
                session_id=session_id,
                count=len(redis_messages),
            )

            # Send each message
            for message in redis_messages:
                await backpressure_handler.send_message(
                    websocket, tenant_id, None, session_id, message
                )

    except Exception as e:
        logger.error(
            "Failed to deliver pending messages", error=str(e), session_id=session_id
        )


async def _process_client_message(
    websocket: WebSocket,
    tenant_id: str,
    user_id: Optional[str],
    session_id: str,
    message: Dict[str, Any],
):
    """Process message from client."""
    try:
        message_type = message.get("type", "unknown")

        if message_type == "ping":
            # Respond to ping
            pong_message = {
                "type": "pong",
                "timestamp": time.time(),
                "session_id": session_id,
            }
            await backpressure_handler.send_message(
                websocket, tenant_id, user_id, session_id, pong_message
            )

        elif message_type == "subscribe":
            # Handle subscription requests
            await _handle_subscription(
                websocket, tenant_id, user_id, session_id, message
            )

        elif message_type == "unsubscribe":
            # Handle unsubscription requests
            await _handle_unsubscription(
                websocket, tenant_id, user_id, session_id, message
            )

        else:
            # Echo message back (for testing)
            echo_message = {
                "type": "echo",
                "original_message": message,
                "timestamp": time.time(),
                "session_id": session_id,
            }
            await backpressure_handler.send_message(
                websocket, tenant_id, user_id, session_id, echo_message
            )

    except Exception as e:
        logger.error(
            "Failed to process client message", error=str(e), session_id=session_id
        )
        await _send_error_message(websocket, session_id, "Failed to process message")


async def _handle_subscription(
    websocket: WebSocket,
    tenant_id: str,
    user_id: Optional[str],
    session_id: str,
    message: Dict[str, Any],
):
    """Handle subscription requests."""
    try:
        topic = message.get("topic", "default")

        # Store subscription in Redis
        subscription_key = f"subscription:{session_id}:{topic}"
        await redis_client.setex(
            subscription_key,
            3600,
            json.dumps(
                {
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "session_id": session_id,
                    "topic": topic,
                    "timestamp": time.time(),
                }
            ),
        )

        # Send confirmation
        confirm_message = {
            "type": "subscription_confirmed",
            "topic": topic,
            "timestamp": time.time(),
            "session_id": session_id,
        }
        await backpressure_handler.send_message(
            websocket, tenant_id, user_id, session_id, confirm_message
        )

    except Exception as e:
        logger.error(
            "Failed to handle subscription", error=str(e), session_id=session_id
        )


async def _handle_unsubscription(
    websocket: WebSocket,
    tenant_id: str,
    user_id: Optional[str],
    session_id: str,
    message: Dict[str, Any],
):
    """Handle unsubscription requests."""
    try:
        topic = message.get("topic", "default")

        # Remove subscription from Redis
        subscription_key = f"subscription:{session_id}:{topic}"
        await redis_client.delete(subscription_key)

        # Send confirmation
        confirm_message = {
            "type": "unsubscription_confirmed",
            "topic": topic,
            "timestamp": time.time(),
            "session_id": session_id,
        }
        await backpressure_handler.send_message(
            websocket, tenant_id, user_id, session_id, confirm_message
        )

    except Exception as e:
        logger.error(
            "Failed to handle unsubscription", error=str(e), session_id=session_id
        )


async def _send_error_message(
    websocket: WebSocket, session_id: str, error_message: str
):
    """Send error message to client."""
    try:
        error_response = {
            "type": "error",
            "message": error_message,
            "timestamp": time.time(),
            "session_id": session_id,
        }
        await websocket.send_text(json.dumps(error_response))
    except Exception as e:
        logger.error(
            "Failed to send error message", error=str(e), session_id=session_id
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8003)
