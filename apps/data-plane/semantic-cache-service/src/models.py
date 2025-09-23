from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime

class CacheRequest(BaseModel):
    tenant_id: str
    cache_key: str
    content: str
    ttl_seconds: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class CacheResponse(BaseModel):
    found: bool
    content: Optional[str] = None
    similarity_score: Optional[float] = None
    cache_key: Optional[str] = None
    cached_at: Optional[str] = None
    expires_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class CacheEntry(BaseModel):
    cache_key: str
    tenant_id: str
    content: str
    embedding: List[float]
    similarity_score: Optional[float] = None
    cached_at: datetime
    expires_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)
    hit_count: int = 0

class SemanticSearchRequest(BaseModel):
    tenant_id: str
    query: str
    similarity_threshold: Optional[float] = None
    max_results: int = 10

class SemanticSearchResponse(BaseModel):
    results: List[CacheResponse]
    query_embedding: Optional[List[float]] = None
    search_time_ms: int

class CacheStats(BaseModel):
    tenant_id: str
    total_entries: int
    hit_rate: float
    avg_similarity: float
    cache_size_mb: float
    oldest_entry: Optional[str] = None
    newest_entry: Optional[str] = None

class CacheMetrics(BaseModel):
    total_requests: int
    cache_hits: int
    cache_misses: int
    hit_rate: float
    avg_response_time_ms: float
    total_entries: int
    cache_size_mb: float
    tenants_count: int

