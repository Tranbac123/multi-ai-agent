from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class ReturnFields(BaseModel):
    chunks: bool = True
    citations: bool = True


class QueryRequest(BaseModel):
    tenant_id: str
    query: str
    top_k: int = 8
    filters: Dict[str, Any] | None = None
    hybrid_alpha: Optional[float] = None
    reranker: Optional[str] = None
    return_fields: ReturnFields = Field(default_factory=ReturnFields)


class ResultItem(BaseModel):
    doc_id: str
    score: float
    chunk: str
    meta: Dict[str, Any] = {}


class QueryUsage(BaseModel):
    retrieval_ms: int = 0
    rerank_ms: int = 0


class QueryResponse(BaseModel):
    results: List[ResultItem]
    usage: QueryUsage = Field(default_factory=QueryUsage)


class IndexRequest(BaseModel):
    tenant_id: str
    doc: str
    meta: Dict[str, Any] = {}


class DeleteRequest(BaseModel):
    tenant_id: str
    doc_id: str


class IndexResponse(BaseModel):
    ok: bool


class DeleteResponse(BaseModel):
    ok: bool

