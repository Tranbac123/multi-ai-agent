import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional

app = FastAPI(title="semantic-cache-service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple in-memory cache
cache_store = {}

class CacheRequest(BaseModel):
    key: str
    value: str
    ttl_s: int = 60

class CacheResponse(BaseModel):
    hit: bool
    value: Optional[str] = None
    ttl_remaining: Optional[int] = None

@app.get("/healthz")
def healthz():
    return {"ok": True, "name": "semantic-cache-service"}

@app.post("/v1/cache/put")
def put_cache(request: CacheRequest):
    """Store a value in the cache"""
    cache_store[request.key] = {
        "value": request.value,
        "expires_at": time.time() + request.ttl_s
    }
    return {"ok": True, "key": request.key}

@app.get("/v1/cache/get", response_model=CacheResponse)
def get_cache(key: str):
    """Retrieve a value from the cache"""
    if key not in cache_store:
        return CacheResponse(hit=False)
    
    entry = cache_store[key]
    if time.time() > entry["expires_at"]:
        del cache_store[key]
        return CacheResponse(hit=False)
    
    ttl_remaining = int(entry["expires_at"] - time.time())
    return CacheResponse(
        hit=True, 
        value=entry["value"],
        ttl_remaining=ttl_remaining
    )

@app.delete("/v1/cache/del")
def delete_cache(key: str):
    """Delete a value from the cache"""
    if key in cache_store:
        del cache_store[key]
    return {"ok": True, "key": key}

@app.get("/v1/cache/stats")
def get_stats():
    """Get cache statistics"""
    return {
        "total_entries": len(cache_store),
        "memory_usage": len(str(cache_store))
    }