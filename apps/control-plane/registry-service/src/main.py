from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Tuple
from .models import AgentManifest, ToolManifest
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

Agents: Dict[Tuple[str,str], AgentManifest] = {}
Tools:  Dict[Tuple[str,str], ToolManifest]  = {}

@app.post("/v1/agents")
def upsert_agent(m: AgentManifest, tenant=enforce()):
    Agents[(m.name,m.version)] = m
    return {"ok": True}

@app.get("/v1/agents")
def get_agent(name: str, version: str | None = None, tenant=enforce()):
    if version:
        m = Agents.get((name,version))
        if not m: raise HTTPException(404, "not found")
        return m
    # latest by version string (simple)
    cand = sorted([k for k in Agents if k[0]==name], key=lambda x: x[1], reverse=True)
    if not cand: raise HTTPException(404, "not found")
    return Agents[cand[0]]

@app.post("/v1/tools")
def upsert_tool(m: ToolManifest, tenant=enforce()):
    Tools[(m.name,m.version)] = m
    return {"ok": True}

@app.get("/v1/tools")
def get_tool(name: str, version: str | None = None, tenant=enforce()):
    if version:
        m = Tools.get((name,version))
        if not m: raise HTTPException(404, "not found")
        return m
    cand = sorted([k for k in Tools if k[0]==name], key=lambda x: x[1], reverse=True)
    if not cand: raise HTTPException(404, "not found")
    return Tools[cand[0]]

