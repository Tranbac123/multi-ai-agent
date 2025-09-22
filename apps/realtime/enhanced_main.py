"""
Enhanced Realtime Service with Advanced Backpressure Management

FastAPI application combining the best features from both implementations:
- Advanced backpressure management with Redis persistence
- WebSocket connection management with sticky sessions  
- Comprehensive metrics and monitoring
- Production-ready error handling and graceful shutdown
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.responses import JSONResponse
import structlog
import redis.asyncio as redis
from contextlib import asynccontextmanager

from src.core.backpressure_manager import BackpressureManager, MessageType
from src.core.websocket_manager import WebSocketManager
from src.core.backpressure_handler import BackpressureHandler, BackpressureMetrics
from src.core.connection_manager import ConnectionManager

logger = structlog.get_logger(__name__)

# Global instances
redis_client: Optional[redis.Redis] = None
backpressure_manager: Optional[BackpressureManager] = None
websocket_manager: Optional[WebSocketManager] = None
connection_manager: Optional[ConnectionManager] = None
backpressure_handler: Optional[BackpressureHandler] = None
metrics_collector: Optional[BackpressureMetrics] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with proper initialization and cleanup."""
    global redis_client, backpressure_manager, websocket_manager
    global connection_manager, backpressure_handler, metrics_collector

    try:
        logger.info("Initializing Enhanced Realtime Service")
        
        # Initialize Redis connection
        redis_client = redis.Redis(
            host="localhost",
            port=6379,
            db=0,
            decode_responses=False,
            max_connections=20,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True
        )
        
        # Test Redis connection
        await redis_client.ping()
        logger.info("Redis connection established")
        
        # Initialize advanced backpressure manager
        backpressure_manager = BackpressureManager(redis_client)
        
        # Initialize WebSocket manager with backpressure
        websocket_manager = WebSocketManager(backpressure_manager)
        
        # Initialize legacy connection manager for backward compatibility
        connection_manager = ConnectionManager(redis_client)
        
        # Initialize legacy backpressure handler for existing tests
        backpressure_handler = BackpressureHandler(
            connection_manager=connection_manager,
            redis_client=redis_client,
            max_queue_size=1000,
            drop_policy="intermediate",
            session_ttl=3600,
        )
        
        # Initialize metrics collector
        metrics_collector = BackpressureMetrics()
        await backpressure_handler.start_cleanup_task()
        
        # Start background monitoring tasks
        asyncio.create_task(connection_health_monitor())
        asyncio.create_task(metrics_collector_task())
        
        logger.info("Enhanced Realtime Service initialized successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize service: {e}", exc_info=True)
        raise
    finally:
        # Graceful shutdown
        logger.info("Shutting down Enhanced Realtime Service")
        
        if websocket_manager:
            await websocket_manager.shutdown()
        
        if backpressure_manager:
            await backpressure_manager.shutdown()
        
        if backpressure_handler:
            await backpressure_handler.stop_cleanup_task()
        
        if redis_client:
            await redis_client.close()
        
        logger.info("Enhanced Realtime Service shutdown completed")


app = FastAPI(
    title="Enhanced Realtime Service",
    description="Real-time communication with advanced backpressure management and Redis persistence",
    version="2.0.0",
    lifespan=lifespan
)


# WebSocket endpoint with enhanced features
@app.websocket("/ws/{tenant_id}")
async def websocket_endpoint(websocket: WebSocket, tenant_id: str):
    """Enhanced WebSocket endpoint with backpressure management."""
    
    connection_id = None
    
    try:
        # Connect using advanced WebSocket manager
        connection_id = await websocket_manager.connect(websocket, tenant_id)
        
        logger.info(
            "WebSocket connection established",
            connection_id=connection_id,
            tenant_id=tenant_id
        )
        
        # Send welcome message
        await websocket_manager.send_to_connection(
            connection_id,
            {
                "type": "welcome",
                "connection_id": connection_id,
                "tenant_id": tenant_id,
                "timestamp": time.time(),
                "features": {
                    "backpressure": True,
                    "persistence": True,
                    "resume": True
                }
            },
            MessageType.FINAL
        )
        
        # Message handling loop
        while True:
            try:
                # Receive message from client
                message = await websocket.receive_text()
                
                # Process with enhanced manager
                processed_message = await websocket_manager.handle_incoming_message(
                    connection_id, message
                )
                
                if processed_message:
                    # Handle different message types
                    await handle_client_message(processed_message)
                
            except WebSocketDisconnect:
                logger.info(
                    "WebSocket disconnected by client",
                    connection_id=connection_id,
                    tenant_id=tenant_id
                )
                break
            except Exception as e:
                logger.error(
                    "Error in WebSocket message loop",
                    connection_id=connection_id,
                    error=str(e),
                    exc_info=True
                )
                break
                
    except Exception as e:
        logger.error(
            "Error in WebSocket endpoint",
            connection_id=connection_id,
            tenant_id=tenant_id,
            error=str(e),
            exc_info=True
        )
    finally:
        if connection_id:
            await websocket_manager.disconnect(connection_id)


async def handle_client_message(processed_message: Dict[str, Any]) -> None:
    """Handle processed client messages."""
    
    connection_id = processed_message["connection_id"]
    tenant_id = processed_message["tenant_id"]
    data = processed_message["data"]
    
    message_type = data.get("type", "unknown")
    
    if message_type == "chat":
        # Handle chat message
        response = {
            "type": "chat_response",
            "message": f"Echo: {data.get('message', '')}",
            "timestamp": time.time()
        }
        
        await websocket_manager.send_to_connection(
            connection_id, response, MessageType.FINAL
        )
        
    elif message_type == "broadcast":
        # Broadcast to all tenant connections
        broadcast_data = {
            "type": "broadcast",
            "from": connection_id,
            "message": data.get("message", ""),
            "timestamp": time.time()
        }
        
        await websocket_manager.send_to_tenant(
            tenant_id, broadcast_data, MessageType.INTERMEDIATE, connection_id
        )
        
    elif message_type == "status":
        # Send connection status
        stats = await websocket_manager.get_connection_stats(connection_id)
        if stats:
            await websocket_manager.send_to_connection(
                connection_id, {"type": "status", "stats": stats}, MessageType.FINAL
            )


# REST API endpoints
@app.get("/health")
async def health_check():
    """Enhanced health check with component status."""
    
    try:
        # Check Redis connection
        await redis_client.ping()
        redis_status = "healthy"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"
    
    # Get service metrics
    ws_stats = await websocket_manager.get_overall_stats()
    
    return {
        "status": "healthy" if redis_status == "healthy" else "degraded",
        "timestamp": time.time(),
        "components": {
            "redis": redis_status,
            "websocket_manager": "healthy",
            "backpressure_manager": "healthy"
        },
        "metrics": {
            "active_connections": ws_stats["websocket_manager"]["active_connections"],
            "total_connections": ws_stats["websocket_manager"]["total_connections"],
            "tenant_count": ws_stats["websocket_manager"]["tenant_count"]
        },
        "version": "2.0.0"
    }


@app.get("/metrics")
async def get_metrics():
    """Get comprehensive service metrics."""
    
    # Get WebSocket manager stats
    ws_stats = await websocket_manager.get_overall_stats()
    
    # Get legacy backpressure stats for compatibility
    legacy_stats = backpressure_handler.get_metrics()
    
    return {
        "timestamp": time.time(),
        "enhanced_websocket": ws_stats,
        "legacy_backpressure": legacy_stats,
        "redis_info": {
            "connected": True if redis_client else False
        }
    }


@app.get("/connections")
async def get_connections():
    """Get information about active connections."""
    
    stats = await websocket_manager.get_overall_stats()
    return {
        "active_connections": stats["websocket_manager"]["active_connections"],
        "tenants": stats["tenants"]
    }


@app.get("/connections/{connection_id}")
async def get_connection_details(connection_id: str):
    """Get details for a specific connection."""
    
    stats = await websocket_manager.get_connection_stats(connection_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    return stats


@app.post("/broadcast/{tenant_id}")
async def broadcast_to_tenant(tenant_id: str, message: Dict[str, Any]):
    """Broadcast a message to all connections of a tenant."""
    
    broadcast_data = {
        "type": "admin_broadcast",
        "message": message,
        "timestamp": time.time()
    }
    
    sent_count = await websocket_manager.send_to_tenant(
        tenant_id, broadcast_data, MessageType.INTERMEDIATE
    )
    
    return {
        "tenant_id": tenant_id,
        "connections_reached": sent_count,
        "timestamp": time.time()
    }


# Background monitoring tasks
async def connection_health_monitor():
    """Monitor connection health and cleanup stale connections."""
    
    while True:
        try:
            # Cleanup expired connections in backpressure manager
            await backpressure_manager.cleanup_expired_connections()
            
            # Wait 5 minutes between cleanups
            await asyncio.sleep(300)
            
        except Exception as e:
            logger.error(
                "Error in connection health monitor",
                error=str(e),
                exc_info=True
            )
            await asyncio.sleep(60)  # Shorter wait on error


async def metrics_collector_task():
    """Collect and log metrics periodically."""
    
    while True:
        try:
            # Get current metrics
            ws_stats = await websocket_manager.get_overall_stats()
            
            # Log key metrics
            logger.info(
                "Realtime service metrics",
                active_connections=ws_stats["websocket_manager"]["active_connections"],
                total_connections=ws_stats["websocket_manager"]["total_connections"],
                backpressure_drops=ws_stats["websocket_manager"]["ws_backpressure_drops"],
                send_errors=ws_stats["websocket_manager"]["ws_send_errors"],
                tenant_count=ws_stats["websocket_manager"]["tenant_count"]
            )
            
            # Wait 1 minute between metric collections
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(
                "Error in metrics collector",
                error=str(e),
                exc_info=True
            )
            await asyncio.sleep(60)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
