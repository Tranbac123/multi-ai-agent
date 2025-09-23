import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

app = FastAPI(title="chat-adapters-service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AdapterRequest(BaseModel):
    message: str
    adapter_type: str = "default"
    metadata: Optional[Dict[str, Any]] = {}

class AdapterResponse(BaseModel):
    processed_message: str
    adapter_type: str
    processing_time_ms: int

@app.get("/healthz")
def healthz():
    return {"ok": True, "name": "chat-adapters-service"}

@app.get("/v1/adapters")
def list_adapters():
    """List available chat adapters"""
    return {
        "adapters": [
            {"name": "default", "description": "Default message processor"},
            {"name": "slack", "description": "Slack message adapter"},
            {"name": "discord", "description": "Discord message adapter"},
            {"name": "teams", "description": "Microsoft Teams adapter"}
        ]
    }

@app.post("/v1/adapters/process", response_model=AdapterResponse)
def process_message(request: AdapterRequest):
    """Process a message through the specified adapter"""
    start_time = time.time()
    
    # Simple message processing
    if request.adapter_type == "slack":
        processed = f"<slack>{request.message}</slack>"
    elif request.adapter_type == "discord":
        processed = f"```{request.message}```"
    elif request.adapter_type == "teams":
        processed = f"[Teams] {request.message}"
    else:
        processed = f"[{request.adapter_type.upper()}] {request.message}"
    
    processing_time = int((time.time() - start_time) * 1000)
    
    return AdapterResponse(
        processed_message=processed,
        adapter_type=request.adapter_type,
        processing_time_ms=processing_time
    )

@app.get("/v1/adapters/{adapter_type}/health")
def adapter_health(adapter_type: str):
    """Check health of a specific adapter"""
    return {
        "adapter": adapter_type,
        "status": "healthy",
        "uptime": "100%"
    }