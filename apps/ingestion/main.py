"""Ingestion service for document processing and knowledge indexing."""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List
from uuid import UUID, uuid4

import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
from opentelemetry import trace

from libs.clients.database import get_db_session
from libs.clients.auth import get_current_tenant
from libs.clients.event_bus import EventBus, EventProducer
from libs.utils.responses import success_response, error_response
from .core.document_processor import DocumentProcessor
from .core.embedding_service import EmbeddingService
from .core.vector_indexer import VectorIndexer

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Ingestion Service")

    # Initialize services
    app.state.document_processor = DocumentProcessor()
    app.state.embedding_service = EmbeddingService()
    app.state.vector_indexer = VectorIndexer()
    app.state.event_bus = EventBus()
    app.state.event_producer = EventProducer(app.state.event_bus)

    yield

    # Shutdown
    logger.info("Shutting down Ingestion Service")


def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="Ingestion Service",
        version="2.0.0",
        description="Document processing and knowledge indexing service",
        lifespan=lifespan,
    )

    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


app = create_app()


# API Routes
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "ingestion-service"}


@app.post("/api/v1/ingest/document")
async def ingest_document(
    file: UploadFile = File(...),
    tenant_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db_session),
):
    """Ingest document for processing."""
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        # Read file content
        content = await file.read()

        # Process document
        doc_id = str(uuid4())
        result = await app.state.document_processor.process_document(
            doc_id, file.filename, content, tenant_id, db
        )

        # Publish ingestion event
        await app.state.event_producer.publish(
            "ingest.doc.requested",
            {
                "doc_id": doc_id,
                "tenant_id": str(tenant_id),
                "filename": file.filename,
                "size": len(content),
                "timestamp": time.time(),
            },
        )

        return success_response(data=result)

    except Exception as e:
        logger.error("Document ingestion failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to ingest document")


@app.post("/api/v1/ingest/url")
async def ingest_url(
    url: str,
    tenant_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db_session),
):
    """Ingest content from URL."""
    try:
        doc_id = str(uuid4())
        result = await app.state.document_processor.process_url(
            doc_id, url, tenant_id, db
        )

        # Publish ingestion event
        await app.state.event_producer.publish(
            "ingest.doc.requested",
            {
                "doc_id": doc_id,
                "tenant_id": str(tenant_id),
                "url": url,
                "timestamp": time.time(),
            },
        )

        return success_response(data=result)

    except Exception as e:
        logger.error("URL ingestion failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to ingest URL")


@app.get("/api/v1/documents/{tenant_id}")
async def get_documents(
    tenant_id: UUID,
    limit: int = 10,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_session),
):
    """Get documents for tenant."""
    try:
        documents = await app.state.document_processor.get_documents(
            tenant_id, limit, offset, db
        )
        return success_response(data=documents)

    except Exception as e:
        logger.error("Failed to get documents", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get documents")


@app.delete("/api/v1/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    tenant_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db_session),
):
    """Delete document."""
    try:
        await app.state.document_processor.delete_document(doc_id, tenant_id, db)
        return success_response(data={"status": "deleted"})

    except Exception as e:
        logger.error("Failed to delete document", doc_id=doc_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete document")


if __name__ == "__main__":
    uvicorn.run("apps.ingestion.main:app", host="0.0.0.0", port=8004, reload=True)
