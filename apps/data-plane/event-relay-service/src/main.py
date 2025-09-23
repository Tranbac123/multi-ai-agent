import asyncio
import hmac
import hashlib
import base64
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List

app = FastAPI(title="event-relay-service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class EventRequest(BaseModel):
    event_type: str
    payload: Dict[str, Any]
    tenant_id: str

class RelayResponse(BaseModel):
    success: bool
    relayed_to: List[str]
    signature: str

def sign(key: str, payload: bytes) -> str:
    """Generate HMAC signature for webhook payload"""
    signature = hmac.new(
        key.encode('utf-8'),
        payload,
        hashlib.sha256
    ).digest()
    return f"sha256={base64.b64encode(signature).decode('utf-8')}"

@app.get("/healthz") 
def healthz(): 
    return {"ok": True, "name": "event-relay-service"}

@app.post("/v1/relay", response_model=RelayResponse)
def relay_event(request: EventRequest):
    """Relay an event to configured webhooks"""
    import json
    
    payload_bytes = json.dumps(request.payload).encode('utf-8')
    signature = sign("secret", payload_bytes)
    
    # Simulate webhook relay
    relayed_endpoints = [
        f"https://webhook.example.com/{request.event_type}",
        f"https://analytics.example.com/events"
    ]
    
    return RelayResponse(
        success=True,
        relayed_to=relayed_endpoints,
        signature=signature
    )

@app.get("/v1/webhooks")
def list_webhooks():
    """List configured webhook endpoints"""
    return {
        "webhooks": [
            {"url": "https://webhook.example.com", "events": ["user.created", "order.completed"]},
            {"url": "https://analytics.example.com/events", "events": ["*"]}
        ]
    }