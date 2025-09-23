from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
import time

app = FastAPI(title="router-service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RouteRequest(BaseModel):
    task: str
    tenant_id: str
    context: Optional[Dict[str, Any]] = {}

class RouteResponse(BaseModel):
    model: str
    endpoint: str
    routing_time_ms: int
    confidence: float

@app.get("/healthz")
def healthz():
    return {"ok": True, "name": "router-service"}

@app.post("/v1/route", response_model=RouteResponse)
def route_request(request: RouteRequest):
    """Route a task to the appropriate model/endpoint"""
    start_time = time.time()
    
    # Simple routing logic based on task type
    if request.task == "chat":
        model = "gpt-4o-mini"
        endpoint = "https://api.openai.com/v1/chat/completions"
        confidence = 0.95
    elif request.task == "embedding":
        model = "text-embedding-ada-002"
        endpoint = "https://api.openai.com/v1/embeddings"
        confidence = 0.90
    elif request.task == "image":
        model = "dall-e-3"
        endpoint = "https://api.openai.com/v1/images/generations"
        confidence = 0.85
    else:
        # Default fallback
        model = "gpt-3.5-turbo"
        endpoint = "https://api.openai.com/v1/chat/completions"
        confidence = 0.70
    
    routing_time = int((time.time() - start_time) * 1000)
    
    return RouteResponse(
        model=model,
        endpoint=endpoint,
        routing_time_ms=routing_time,
        confidence=confidence
    )

@app.get("/v1/models")
def list_models():
    """List available models and their routing rules"""
    return {
        "models": [
            {"name": "gpt-4o-mini", "task": "chat", "confidence": 0.95},
            {"name": "text-embedding-ada-002", "task": "embedding", "confidence": 0.90},
            {"name": "dall-e-3", "task": "image", "confidence": 0.85},
            {"name": "gpt-3.5-turbo", "task": "chat", "confidence": 0.70}
        ]
    }
