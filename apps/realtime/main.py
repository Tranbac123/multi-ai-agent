"""Realtime service with WebSocket backpressure handling."""

import asyncio
import json
import time
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, Set, List
from uuid import UUID, uuid4
import structlog
import redis.asyncio as redis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace

from libs.clients.database import get_db_session
from libs.clients.auth import get_current_tenant
from libs.clients.rate_limiter import RateLimiter
from libs.clients.event_bus import EventBus, EventProducer
from libs.utils.responses import success_response, error_response
from .core.connection_manager import ConnectionManager
from .core.backpressure_handler import BackpressureHandler
from .core.message_processor import MessageProcessor

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Realtime Service")
    
    # Initialize Redis client
    app.state.redis = redis.from_url("redis://localhost:6379")
    
    # Initialize components
    app.state.connection_manager = ConnectionManager(app.state.redis)
    app.state.backpressure_handler = BackpressureHandler(app.state.redis)
    app.state.message_processor = MessageProcessor()
    app.state.rate_limiter = RateLimiter(app.state.redis)
    app.state.event_bus = EventBus()
    app.state.event_producer = EventProducer(app.state.event_bus)
    
    # Start background tasks
    app.state.cleanup_task = asyncio.create_task(
        app.state.connection_manager.cleanup_stale_connections()
    )
    
    yield
    
    # Shutdown
    logger.info("Shutting down Realtime Service")
    app.state.cleanup_task.cancel()
    await app.state.redis.close()


def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="Realtime Service",
        version="2.0.0",
        description="WebSocket service with backpressure handling",
        lifespan=lifespan
    )
    
    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app


app = create_app()


# WebSocket endpoint
@app.websocket("/ws/{tenant_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    tenant_id: UUID,
    session_id: Optional[str] = None,
    user_id: Optional[UUID] = None
):
    """WebSocket endpoint with backpressure handling."""
    if not session_id:
        session_id = str(uuid4())
    
    connection_id = f"{tenant_id}:{session_id}"
    
    try:
        # Accept connection
        await websocket.accept()
        
        # Register connection
        await app.state.connection_manager.register_connection(
            connection_id, websocket, tenant_id, session_id, user_id
        )
        
        # Send welcome message
        welcome_message = {
            "type": "welcome",
            "connection_id": connection_id,
            "session_id": session_id,
            "tenant_id": str(tenant_id),
            "timestamp": time.time()
        }
        await app.state.connection_manager.send_message(connection_id, welcome_message)
        
        logger.info("WebSocket connected", 
                   connection_id=connection_id, 
                   tenant_id=tenant_id)
        
        # Listen for messages
        while True:
            try:
                # Receive message with timeout
                message_data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=30.0
                )
                
                # Parse message
                try:
                    message = json.loads(message_data)
                except json.JSONDecodeError:
                    await app.state.connection_manager.send_error(
                        connection_id, "Invalid JSON format"
                    )
                    continue
                
                # Process message
                await app.state.message_processor.process_message(
                    connection_id, message, app.state
                )
                
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                await app.state.connection_manager.send_ping(connection_id)
                
            except WebSocketDisconnect:
                break
                
    except Exception as e:
        logger.error("WebSocket error", 
                    connection_id=connection_id, 
                    error=str(e))
    finally:
        # Clean up connection
        await app.state.connection_manager.unregister_connection(connection_id)
        logger.info("WebSocket disconnected", connection_id=connection_id)


# HTTP endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "realtime-service"}


@app.get("/api/v1/connections/{tenant_id}")
async def get_connections(tenant_id: UUID):
    """Get active connections for tenant."""
    try:
        connections = await app.state.connection_manager.get_tenant_connections(tenant_id)
        return success_response(data=connections)
        
    except Exception as e:
        logger.error("Failed to get connections", tenant_id=tenant_id, error=str(e))
        return error_response("Failed to get connections")


@app.post("/api/v1/broadcast/{tenant_id}")
async def broadcast_message(
    tenant_id: UUID,
    message: Dict[str, Any],
    exclude_connections: Optional[List[str]] = None
):
    """Broadcast message to all tenant connections."""
    try:
        await app.state.connection_manager.broadcast_to_tenant(
            tenant_id, message, exclude_connections or []
        )
        return success_response(data={"status": "broadcasted"})
        
    except Exception as e:
        logger.error("Failed to broadcast message", tenant_id=tenant_id, error=str(e))
        return error_response("Failed to broadcast message")


@app.get("/api/v1/metrics")
async def get_metrics():
    """Get realtime service metrics."""
    try:
        metrics = await app.state.connection_manager.get_metrics()
        return success_response(data=metrics)
        
    except Exception as e:
        logger.error("Failed to get metrics", error=str(e))
        return error_response("Failed to get metrics")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "apps.realtime.main:app",
        host="0.0.0.0",
        port=8003,
        reload=True
    )
