import asyncio
from fastapi import FastAPI
from .settings import settings
from .relay import run_relay

app = FastAPI(title=settings.app_name, version="0.1.0")

@app.get("/healthz") 
def healthz(): 
    return {"ok": True, "name": settings.app_name}

_stop = asyncio.Event()

@app.on_event("startup")
async def _start():
    asyncio.create_task(run_relay(settings, _stop))

@app.on_event("shutdown")
async def _shutdown():
    _stop.set()

