from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .settings import settings
from .auth import enforce
from . import storage

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origins],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

class GetIn(BaseModel):
    env: str = "production"
    key: str

class SetIn(BaseModel):
    env: str = "production"
    key: str
    value: dict | str | int | float | bool | None

@app.get("/healthz")
def healthz(): return {"ok": True, "name": settings.app_name}

@app.get("/v1/config")
def get_config(env: str = Query("production"), key: str = Query(...), tenant= enforce()):
    v = storage.get(env, key)
    if v is None: raise HTTPException(404, "not found")
    return {"env": env, "key": key, "value": v, "max_age": settings.cache_ttl_s}

@app.post("/v1/config")
def set_config(body: SetIn, tenant = enforce()):
    storage.set(body.env, body.key, body.value)
    return {"ok": True}

