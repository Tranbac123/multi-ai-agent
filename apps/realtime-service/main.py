"""
Realtime Service with Backpressure Management

FastAPI application for real-time communication with WebSocket support,
integrated backpressure handling, and comprehensive metrics.
"""

import asyncio
from typing import Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import HTMLResponse
import structlog
from opentelemetry import trace

from .core.backpressure_manager import BackpressureManager, MessageType
from .core.websocket_manager import WebSocketManager

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)

# Global instances (in production, use dependency injection)
redis_client = None  # Would be initialized with actual Redis client
backpressure_manager = BackpressureManager(redis_client)
websocket_manager = WebSocketManager(backpressure_manager)

app = FastAPI(
    title="Realtime Service",
    description="Real-time communication with backpressure management",
    version="1.0.0"
)


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup."""
    logger.info("Realtime service starting up")
    
    # Start background tasks
    asyncio.create_task(cleanup_inactive_connections())


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    logger.info("Realtime service shutting down")


async def cleanup_inactive_connections():
    """Background task to clean up inactive connections."""
    while True:
        try:
            await backpressure_manager.cleanup_inactive_connections(max_inactive_minutes=30)
            await asyncio.sleep(300)  # Run every 5 minutes
        except Exception as e:
            logger.error("Error in cleanup task", error=str(e))
            await asyncio.sleep(60)


@app.websocket("/ws/{tenant_id}")
async def websocket_endpoint(websocket: WebSocket, tenant_id: str):
    """WebSocket endpoint with backpressure handling."""
    
    connection_id = None
    
    try:
        # Connect WebSocket
        connection_id = await websocket_manager.connect(websocket, tenant_id)
        
        logger.info("WebSocket connection established", 
                   connection_id=connection_id,
                   tenant_id=tenant_id)
        
        # Handle messages
        while True:
            try:
                message = await websocket.receive_text()
                await websocket_manager.handle_message(connection_id, message)
                
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected", 
                           connection_id=connection_id,
                           tenant_id=tenant_id)
                break
            except Exception as e:
                logger.error("Error handling WebSocket message", 
                           connection_id=connection_id,
                           error=str(e))
                break
                
    except Exception as e:
        logger.error("WebSocket connection error", 
                    tenant_id=tenant_id,
                    error=str(e))
    finally:
        if connection_id:
            await websocket_manager.disconnect(connection_id, "connection_closed")


@app.post("/send/{tenant_id}")
async def send_message_to_tenant(
    tenant_id: str,
    content: Dict[str, Any],
    message_type: str = "intermediate",
    priority: int = 0,
    is_final: bool = False
):
    """Send message to all connections for a tenant."""
    
    try:
        # Convert message type string to enum
        msg_type = MessageType(message_type)
        
        sent_count = await websocket_manager.send_to_tenant(
            tenant_id=tenant_id,
            content=content,
            message_type=msg_type,
            priority=priority,
            is_final=is_final
        )
        
        return {
            "success": True,
            "tenant_id": tenant_id,
            "sent_count": sent_count,
            "message_type": message_type,
            "is_final": is_final
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid message type: {e}")
    except Exception as e:
        logger.error("Error sending message to tenant", 
                    tenant_id=tenant_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/send/connection/{connection_id}")
async def send_message_to_connection(
    connection_id: str,
    content: Dict[str, Any],
    message_type: str = "intermediate",
    priority: int = 0,
    is_final: bool = False
):
    """Send message to specific connection."""
    
    try:
        # Convert message type string to enum
        msg_type = MessageType(message_type)
        
        success = await websocket_manager.send_message(
            connection_id=connection_id,
            content=content,
            message_type=msg_type,
            priority=priority,
            is_final=is_final
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Connection not found or inactive")
        
        return {
            "success": True,
            "connection_id": connection_id,
            "message_type": message_type,
            "is_final": is_final
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid message type: {e}")
    except Exception as e:
        logger.error("Error sending message to connection", 
                    connection_id=connection_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/connections/{tenant_id}")
async def get_tenant_connections(tenant_id: str):
    """Get all connections for a tenant."""
    
    connection_ids = websocket_manager.get_tenant_connections(tenant_id)
    
    # Get detailed information for each connection
    connections = []
    for connection_id in connection_ids:
        info = await websocket_manager.get_connection_info(connection_id)
        if info:
            connections.append(info)
    
    return {
        "tenant_id": tenant_id,
        "connection_count": len(connections),
        "connections": connections
    }


@app.get("/connection/{connection_id}")
async def get_connection_info(connection_id: str):
    """Get information about a specific connection."""
    
    info = await websocket_manager.get_connection_info(connection_id)
    
    if not info:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    return info


@app.post("/connection/{connection_id}/resume")
async def resume_connection(
    connection_id: str,
    from_sequence: int = 0
):
    """Resume a connection from a specific sequence number."""
    
    success = await backpressure_manager.resume_connection(connection_id, from_sequence)
    
    if not success:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    return {
        "success": True,
        "connection_id": connection_id,
        "from_sequence": from_sequence
    }


@app.get("/metrics")
async def get_metrics():
    """Get comprehensive service metrics."""
    
    websocket_metrics = websocket_manager.get_metrics()
    backpressure_metrics = backpressure_manager.get_global_metrics()
    
    return {
        "websocket_metrics": websocket_metrics,
        "backpressure_metrics": backpressure_metrics,
        "timestamp": asyncio.get_event_loop().time()
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    
    return {
        "status": "healthy",
        "active_connections": websocket_manager.active_connections,
        "total_connections": websocket_manager.total_connections
    }


@app.get("/", response_class=HTMLResponse)
async def get_websocket_test_page():
    """Simple WebSocket test page."""
    
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>WebSocket Test</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .container { max-width: 800px; }
            .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
            .connected { background-color: #d4edda; color: #155724; }
            .disconnected { background-color: #f8d7da; color: #721c24; }
            .messages { height: 300px; overflow-y: auto; border: 1px solid #ccc; padding: 10px; }
            .message { margin: 5px 0; padding: 5px; background-color: #f8f9fa; }
            .controls { margin: 20px 0; }
            .controls input, .controls button { margin: 5px; padding: 8px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>WebSocket Test Page</h1>
            
            <div class="controls">
                <input type="text" id="tenantId" placeholder="Tenant ID" value="test-tenant">
                <button onclick="connect()">Connect</button>
                <button onclick="disconnect()">Disconnect</button>
                <button onclick="sendPing()">Send Ping</button>
                <button onclick="sendResume()">Send Resume</button>
            </div>
            
            <div id="status" class="status disconnected">Disconnected</div>
            
            <div class="controls">
                <input type="text" id="messageContent" placeholder="Message content" value="Hello, WebSocket!">
                <button onclick="sendMessage()">Send Message</button>
            </div>
            
            <h3>Messages:</h3>
            <div id="messages" class="messages"></div>
        </div>
        
        <script>
            let ws = null;
            let connectionId = null;
            let lastSequence = 0;
            
            function connect() {
                const tenantId = document.getElementById('tenantId').value;
                if (!tenantId) {
                    alert('Please enter a tenant ID');
                    return;
                }
                
                ws = new WebSocket(`ws://localhost:8000/ws/${tenantId}`);
                
                ws.onopen = function(event) {
                    updateStatus('Connected', true);
                    addMessage('Connected to WebSocket');
                };
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    addMessage(`Received: ${JSON.stringify(data, null, 2)}`);
                    
                    if (data.sequence_number) {
                        lastSequence = data.sequence_number;
                    }
                    
                    // Auto-acknowledge messages
                    if (data.message_id && data.sequence_number) {
                        ws.send(JSON.stringify({
                            type: 'ack',
                            message_id: data.message_id,
                            sequence_number: data.sequence_number
                        }));
                    }
                };
                
                ws.onclose = function(event) {
                    updateStatus('Disconnected', false);
                    addMessage('WebSocket connection closed');
                };
                
                ws.onerror = function(error) {
                    addMessage(`Error: ${error}`);
                };
            }
            
            function disconnect() {
                if (ws) {
                    ws.close();
                    ws = null;
                }
            }
            
            function sendMessage() {
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    alert('WebSocket is not connected');
                    return;
                }
                
                const content = document.getElementById('messageContent').value;
                ws.send(JSON.stringify({
                    type: 'message',
                    content: content
                }));
                
                addMessage(`Sent: ${content}`);
            }
            
            function sendPing() {
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    alert('WebSocket is not connected');
                    return;
                }
                
                ws.send(JSON.stringify({
                    type: 'ping',
                    timestamp: new Date().toISOString()
                }));
                
                addMessage('Sent ping');
            }
            
            function sendResume() {
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    alert('WebSocket is not connected');
                    return;
                }
                
                ws.send(JSON.stringify({
                    type: 'resume',
                    from_sequence: lastSequence
                }));
                
                addMessage(`Sent resume from sequence ${lastSequence}`);
            }
            
            function updateStatus(text, connected) {
                const status = document.getElementById('status');
                status.textContent = text;
                status.className = `status ${connected ? 'connected' : 'disconnected'}`;
            }
            
            function addMessage(text) {
                const messages = document.getElementById('messages');
                const message = document.createElement('div');
                message.className = 'message';
                message.textContent = `${new Date().toLocaleTimeString()}: ${text}`;
                messages.appendChild(message);
                messages.scrollTop = messages.scrollHeight;
            }
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
