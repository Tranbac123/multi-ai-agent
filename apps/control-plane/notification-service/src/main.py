import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum

app = FastAPI(title="notification-service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    DELIVERED = "delivered"

class NotificationRequest(BaseModel):
    tenant_id: str
    channels: List[str]
    subject: str
    body: str
    priority: str = "normal"
    metadata: Optional[Dict[str, Any]] = {}

class NotificationResponse(BaseModel):
    notification_id: str
    status: NotificationStatus
    queued_at: str
    channels: List[str]

# Simple in-memory notification queue
notification_queue = []
notification_counter = 0

@app.get("/healthz")
def healthz():
    return {"ok": True, "name": "notification-service"}

@app.post("/v1/notify", response_model=NotificationResponse)
def send_notification(request: NotificationRequest):
    """Send a notification to specified channels"""
    global notification_counter
    notification_counter += 1
    
    notification_id = f"notif_{notification_counter}_{int(time.time())}"
    
    notification = {
        "id": notification_id,
        "tenant_id": request.tenant_id,
        "channels": request.channels,
        "subject": request.subject,
        "body": request.body,
        "status": NotificationStatus.PENDING,
        "queued_at": time.time(),
        "priority": request.priority
    }
    
    notification_queue.append(notification)
    
    return NotificationResponse(
        notification_id=notification_id,
        status=NotificationStatus.PENDING,
        queued_at=str(notification["queued_at"]),
        channels=request.channels
    )

@app.get("/v1/notifications/{notification_id}")
def get_notification_status(notification_id: str):
    """Get the status of a specific notification"""
    for notif in notification_queue:
        if notif["id"] == notification_id:
            return {
                "notification_id": notification_id,
                "status": notif["status"],
                "queued_at": notif["queued_at"],
                "channels": notif["channels"]
            }
    
    raise HTTPException(status_code=404, detail="Notification not found")

@app.get("/v1/notifications")
def list_notifications(tenant_id: Optional[str] = None):
    """List notifications, optionally filtered by tenant"""
    if tenant_id:
        filtered = [n for n in notification_queue if n["tenant_id"] == tenant_id]
        return {"notifications": filtered}
    
    return {"notifications": notification_queue}

@app.get("/v1/channels")
def list_channels():
    """List available notification channels"""
    return {
        "channels": [
            {"name": "email", "enabled": True, "description": "Email notifications"},
            {"name": "slack", "enabled": True, "description": "Slack messages"},
            {"name": "sms", "enabled": False, "description": "SMS notifications"},
            {"name": "push", "enabled": True, "description": "Push notifications"}
        ]
    }