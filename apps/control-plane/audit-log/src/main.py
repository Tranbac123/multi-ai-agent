from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from datetime import datetime
from .settings import settings
from .auth import enforce

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origins],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

@app.get("/healthz") 
def healthz(): return {"ok": True, "name": settings.app_name}

class AuditEvent(BaseModel):
    tenant_id: str
    actor: str
    action: str
    resource: str
    meta: Dict[str, Any] = {}
    ts: datetime | None = None

# Simple in-memory append-only store
_audit_store: List[AuditEvent] = []

@app.post("/v1/audit")
def log_audit(event: AuditEvent, tenant=enforce()):
    if not event.ts:
        event.ts = datetime.utcnow()
    _audit_store.append(event)
    return {"ok": True, "recorded_at": event.ts}

@app.get("/v1/audit")
def get_audit(
    tenant_id: str = Query(...), 
    actor: Optional[str] = Query(None),
    resource: Optional[str] = Query(None),
    tenant=enforce()
):
    # Filter audit logs by tenant and optional filters
    filtered_logs = [
        e for e in _audit_store 
        if e.tenant_id == tenant_id
        and (not actor or e.actor == actor)
        and (not resource or e.resource == resource)
    ]
    
    return {
        "tenant_id": tenant_id,
        "total_events": len(filtered_logs),
        "events": filtered_logs[-100:]  # Last 100 events
    }

