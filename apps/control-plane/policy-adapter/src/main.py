from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any
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

class AuthorizeRequest(BaseModel):
    resource: str
    action: str
    context: Dict[str, Any] = {}

@app.post("/v1/authorize")
def authorize(body: AuthorizeRequest, tenant=enforce()):
    # Simple allow-all stub with caching headers
    return {
        "allow": True,
        "ttl_s": settings.cache_ttl_s,
        "resource": body.resource,
        "action": body.action,
        "tenant": tenant
    }

