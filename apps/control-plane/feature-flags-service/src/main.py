from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict
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

class FlagSet(BaseModel):
    name: str
    on: bool = False
    rollout: int = 0  # 0-100
    tenant_overrides: Dict[str, bool] = {}

_db: Dict[str, FlagSet] = {}

@app.post("/v1/flags") 
def upsert_flag(body: FlagSet, tenant=enforce()):
    _db[body.name] = body
    return {"ok": True}

@app.get("/v1/flags/eval")
def eval_flag(name: str, user_id: str | None = None, tenant=enforce()):
    fs = _db.get(name)
    if not fs: raise HTTPException(404, "flag not found")
    if tenant in fs.tenant_overrides: return {"enabled": fs.tenant_overrides[tenant]}
    if not fs.on: return {"enabled": False}
    if fs.rollout >= 100: return {"enabled": True}
    # simple deterministic hash
    bucket = (hash(user_id or tenant) % 100)
    return {"enabled": bucket < fs.rollout}

