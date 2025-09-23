from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Any
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

class UsageEvent(BaseModel):
    tenant_id: str
    service: str
    route: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0
    cost_usd: float = 0
    ts: datetime | None = None

# Simple in-memory store
_usage_store: List[UsageEvent] = []

@app.post("/v1/usage")
def ingest_usage(event: UsageEvent, tenant=enforce()):
    if not event.ts:
        event.ts = datetime.utcnow()
    _usage_store.append(event)
    return {"ok": True, "recorded_at": event.ts}

@app.get("/v1/summary")
def get_summary(tenant_id: str = Query(...), tenant=enforce()):
    # Filter by tenant and summarize
    tenant_events = [e for e in _usage_store if e.tenant_id == tenant_id]
    
    total_tokens_in = sum(e.tokens_in for e in tenant_events)
    total_tokens_out = sum(e.tokens_out for e in tenant_events)
    total_cost = sum(e.cost_usd for e in tenant_events)
    avg_latency = sum(e.latency_ms for e in tenant_events) / len(tenant_events) if tenant_events else 0
    
    return {
        "tenant_id": tenant_id,
        "total_events": len(tenant_events),
        "total_tokens_in": total_tokens_in,
        "total_tokens_out": total_tokens_out,
        "total_cost_usd": total_cost,
        "avg_latency_ms": avg_latency
    }

