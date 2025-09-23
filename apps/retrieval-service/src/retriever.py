from .models import QueryRequest, QueryResponse, ResultItem, QueryUsage
import time


def search(req: QueryRequest) -> QueryResponse:
    t0 = time.time()
    items = [
        ResultItem(
            doc_id="d1",
            score=0.87,
            chunk="Example chunk",
            meta={"source": "demo", "tenant_id": req.tenant_id},
        )
    ]
    usage = QueryUsage(retrieval_ms=int((time.time() - t0) * 1000), rerank_ms=0)
    return QueryResponse(results=items, usage=usage)

