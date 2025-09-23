import json
import httpx
from pathlib import Path
from pydantic import BaseModel
from typing import Any, Dict
from .settings import settings

try:
    from mcp.server.fastmcp import FastMCP
except Exception:
    raise SystemExit("mcp.fastmcp not found. Ensure dependency 'mcp' >= 1.13.0")

mcp = FastMCP("mcp-rag")


def _schema(name: str) -> Dict[str, Any]:
    p = Path(__file__).parent.parent / "contracts" / "tools" / name
    return json.loads(p.read_text())


class QueryIn(BaseModel):
    tenant_id: str
    query: str
    top_k: int | None = None
    filters: Dict[str, Any] | None = None
    hybrid_alpha: float | None = None
    reranker: str | None = None
    return_fields: Dict[str, Any] | None = None


class IndexIn(BaseModel):
    tenant_id: str
    doc: str
    meta: Dict[str, Any] | None = None


class DeleteIn(BaseModel):
    tenant_id: str
    doc_id: str


@mcp.tool(name="rag.query", description="Hybrid retrieval with optional rerank", schema=_schema("rag.query.json"))
def rag_query(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = QueryIn(**payload).model_dump()
    url = f"{settings.retrieval_base_url}/v1/query"
    r = httpx.post(url, json=data, timeout=30)
    return r.json()


@mcp.tool(name="rag.index", description="Index a document", schema=_schema("rag.index.json"))
def rag_index(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = IndexIn(**payload).model_dump()
    url = f"{settings.retrieval_base_url}/v1/index"
    r = httpx.post(url, json=data, timeout=30)
    return r.json()


@mcp.tool(name="rag.delete", description="Delete a document", schema=_schema("rag.delete.json"))
def rag_delete(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = DeleteIn(**payload).model_dump()
    url = f"{settings.retrieval_base_url}/v1/delete"
    r = httpx.post(url, json=data, timeout=30)
    return r.json()


if __name__ == "__main__":
    mcp.run(host=settings.host, port=settings.port)

