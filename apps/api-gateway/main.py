"""API Gateway for multi-tenant AIaaS platform."""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text
import structlog
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

from libs.contracts import ErrorSpec, ErrorCode, ErrorResponse
from libs.clients.database import get_db_session
from libs.clients.auth import AuthClient, get_current_tenant
from libs.clients.rate_limiter import RateLimiter
from libs.clients.quota_enforcer import QuotaEnforcer
from libs.utils.middleware import TenantContextMiddleware, RequestLoggingMiddleware
from libs.utils.exceptions import APIException, ValidationError, AuthenticationError
from libs.utils.responses import success_response, error_response
from .websocket import websocket_endpoint

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
        structlog.processors.JSONRenderer()
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
    logger.info("Starting API Gateway")
    
    # Initialize database connection
    engine = create_async_engine(
        app.state.database_url,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=300,
    )
    app.state.db_engine = engine
    app.state.db_session = async_sessionmaker(engine, expire_on_commit=False)
    
    # Initialize clients
    app.state.auth_client = AuthClient()
    app.state.rate_limiter = RateLimiter()
    app.state.quota_enforcer = QuotaEnforcer()
    
    # Instrument SQLAlchemy
    SQLAlchemyInstrumentor().instrument(engine=engine)
    
    yield
    
    # Shutdown
    logger.info("Shutting down API Gateway")
    await engine.dispose()


def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="AIaaS API Gateway",
        version="2.0.0",
        description="Multi-tenant AI-as-a-Service API Gateway",
        lifespan=lifespan
    )
    
    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # Configure in production
    )
    
    app.add_middleware(TenantContextMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    
    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)
    
    return app


app = create_app()


@app.middleware("http")
async def tenant_context_middleware(request: Request, call_next):
    """Set tenant context for database queries."""
    tenant_id = getattr(request.state, "tenant_id", None)
    
    if tenant_id:
        # Set tenant context in database session
        async with app.state.db_session() as session:
            await session.execute(text("SELECT set_tenant_context(:tenant_id)"), 
                                {"tenant_id": tenant_id})
            request.state.db_session = session
    
    response = await call_next(request)
    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting based on tenant plan."""
    tenant_id = getattr(request.state, "tenant_id", None)
    
    if tenant_id:
        # Check rate limits
        if not await app.state.rate_limiter.check_rate_limit(tenant_id, request):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content=error_response(
                    ErrorSpec(
                        code=ErrorCode.RATE_LIMIT,
                        message="Rate limit exceeded",
                        retriable=True,
                        retry_after_ms=60000
                    )
                )
            )
    
    response = await call_next(request)
    return response


@app.middleware("http")
async def quota_enforcement_middleware(request: Request, call_next):
    """Enforce tenant quotas."""
    tenant_id = getattr(request.state, "tenant_id", None)
    
    if tenant_id:
        # Check quotas
        if not await app.state.quota_enforcer.check_quotas(tenant_id, request):
            return JSONResponse(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                content=error_response(
                    ErrorSpec(
                        code=ErrorCode.QUOTA_EXCEEDED,
                        message="Quota exceeded",
                        retriable=False
                    )
                )
            )
    
    response = await call_next(request)
    return response


@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    """Handle API exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(exc.error_spec)
    )


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    """Handle validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response(
            ErrorSpec(
                code=ErrorCode.VALIDATION_FAIL,
                message=str(exc),
                retriable=False
            )
        )
    )


@app.exception_handler(AuthenticationError)
async def auth_error_handler(request: Request, exc: AuthenticationError):
    """Handle authentication errors."""
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=error_response(
            ErrorSpec(
                code=ErrorCode.AUTHENTICATION_FAILED,
                message=str(exc),
                retriable=False
            )
        )
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error("Unexpected error", exc_info=exc, request_id=request.state.request_id)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response(
            ErrorSpec(
                code=ErrorCode.INTERNAL_ERROR,
                message="Internal server error",
                retriable=True
            )
        )
    )


# Health check endpoints
@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": time.time()}


@app.get("/readyz")
async def readiness_check():
    """Readiness check endpoint."""
    try:
        # Check database connectivity
        async with app.state.db_session() as session:
            await session.execute(text("SELECT 1"))
        
        return {"status": "ready", "timestamp": time.time()}
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not ready"
        )


# API routes
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "AIaaS API Gateway",
        "version": "2.0.0",
        "docs": "/docs"
    }
    
    # Add WebSocket endpoint
    app.add_websocket_route("/ws/chat", websocket_endpoint)


if __name__ == "__main__":
    uvicorn.run(
        "apps.api-gateway.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
