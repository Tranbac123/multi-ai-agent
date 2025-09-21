"""FastAPI application factory with common configurations."""

from typing import Optional, Dict, Any, Callable
from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace

from .logging_config import configure_structured_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def create_lifespan_manager(
    service_name: str,
    startup_hook: Optional[Callable] = None,
    shutdown_hook: Optional[Callable] = None
):
    """Create a standardized lifespan manager for FastAPI apps."""
    # Startup
    logger.info(f"Starting {service_name}")
    
    if startup_hook:
        await startup_hook()
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {service_name}")
    
    if shutdown_hook:
        await shutdown_hook()


def create_fastapi_app(
    title: str,
    description: str,
    version: str,
    service_name: str,
    startup_hook: Optional[Callable] = None,
    shutdown_hook: Optional[Callable] = None,
    cors_origins: Optional[list] = None,
    additional_middleware: Optional[list] = None
) -> FastAPI:
    """Create a FastAPI application with standard configuration."""
    
    # Configure structured logging
    configure_structured_logging()
    
    # Create lifespan manager
    lifespan_manager = create_lifespan_manager(
        service_name=service_name,
        startup_hook=startup_hook,
        shutdown_hook=shutdown_hook
    )
    
    # Create FastAPI app
    app = FastAPI(
        title=title,
        description=description,
        version=version,
        lifespan=lifespan_manager
    )
    
    # Add CORS middleware
    if cors_origins is None:
        cors_origins = ["*"]  # Configure appropriately for production
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add additional middleware if provided
    if additional_middleware:
        for middleware in additional_middleware:
            app.add_middleware(middleware)
    
    # Add common route for health check
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "service": service_name}
    
    # Add common route for service info
    @app.get("/")
    async def service_info():
        """Service information endpoint."""
        return {
            "service": service_name,
            "title": title,
            "version": version,
            "docs": "/docs"
        }
    
    return app


def add_common_routes(app: FastAPI, service_name: str) -> None:
    """Add common routes to an existing FastAPI app."""
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "service": service_name}
    
    @app.get("/")
    async def service_info():
        """Service information endpoint."""
        return {
            "service": service_name,
            "title": app.title,
            "version": app.version,
            "docs": "/docs"
        }

