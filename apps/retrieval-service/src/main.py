from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .settings import settings
from .models import QueryRequest, QueryResponse, IndexRequest, IndexResponse, DeleteRequest, DeleteResponse
from .retriever import search
from .indexer import upsert, delete

app = FastAPI(title=settings.app_name, version="0.1.0")

if settings.enable_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.allowed_origins] if settings.allowed_origins else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/healthz")
def healthz():
    return {"ok": True, "name": settings.app_name}


@app.post("/v1/query", response_model=QueryResponse)
def query(req: QueryRequest):
    return search(req)


@app.post("/v1/index", response_model=IndexResponse)
def index_doc(req: IndexRequest):
    return upsert(req)


@app.post("/v1/delete", response_model=DeleteResponse)
def delete_doc(req: DeleteRequest):
    return delete(req)

