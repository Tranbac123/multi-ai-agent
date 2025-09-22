"""API Gateway for multi-tenant AIaaS platform."""

import asyncio
import time
from typing import Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

from libs.contracts import ErrorSpec, ErrorCode, ErrorResponse
from libs.clients.database import get_db_session
from libs.clients.auth import AuthClient, get_current_tenant
from libs.clients.rate_limiter import RateLimiter
from libs.clients.quota_enforcer import QuotaEnforcer
from libs.utils.middleware import TenantContextMiddleware, RequestLoggingMiddleware
from libs.middleware.regional_middleware import RegionalAccessValidator, RegionalMetricsCollector
# from apps.api-gateway.src.core.region_router import RegionRouter
from apps.api_gateway.core.concurrency_manager import ConcurrencyManager
from apps.api_gateway.core.fair_scheduler import WeightedFairScheduler
from apps.api_gateway.middleware.admission_control import AdmissionControlMiddleware
from libs.utils.exceptions import APIException, ValidationError, AuthenticationError
from libs.utils.responses import success_response, error_response
from libs.utils.logging_config import configure_structured_logging, get_logger
from libs.utils.otel_config import configure_otel_tracing, get_tracer
from libs.utils.database_config import initialize_database
from libs.utils.redis_config import initialize_redis
from libs.utils.fastapi_app_factory import create_lifespan_manager
# from src.websocket import websocket_endpoint

# Configure structured logging
configure_structured_logging()
logger = get_logger(__name__)

# Configure OpenTelemetry
configure_otel_tracing("api-gateway")
tracer = get_tracer(__name__)


async def startup_hook(app: FastAPI):
    """API Gateway startup hook."""
    # Initialize database
    db_config = initialize_database(app.state.database_url)
    await db_config.initialize()
    app.state.db_config = db_config

    # Initialize Redis
    redis_config = initialize_redis()
    await redis_config.initialize()
    app.state.redis_config = redis_config

    # Initialize clients
    app.state.auth_client = AuthClient()
    app.state.rate_limiter = RateLimiter()
    app.state.quota_enforcer = QuotaEnforcer()

    # Initialize regional components
    app.state.region_router = RegionRouter(app.state.db_config.get_session)
    app.state.regional_access_validator = RegionalAccessValidator(app.state.region_router)
    app.state.regional_metrics_collector = RegionalMetricsCollector()
    
    # Initialize fairness and concurrency components
    app.state.concurrency_manager = ConcurrencyManager(app.state.redis_config.client)
    app.state.fair_scheduler = WeightedFairScheduler()
    app.state.admission_control = AdmissionControlMiddleware(
        app.state.concurrency_manager,
        app.state.fair_scheduler,
        app.state.quota_enforcer,
        app.state.billing_client
    )

    # Instrument SQLAlchemy
    SQLAlchemyInstrumentor().instrument(engine=db_config.engine)


async def shutdown_hook(app: FastAPI):
    """API Gateway shutdown hook."""
    # Close database connection
    if hasattr(app.state, 'db_config'):
        await app.state.db_config.close()
    
    # Close Redis connection
    if hasattr(app.state, 'redis_config'):
        await app.state.redis_config.close()


def create_app() -> FastAPI:
    """Create FastAPI application."""
    # Create lifespan manager
    lifespan_manager = create_lifespan_manager(
        service_name="API Gateway",
        startup_hook=startup_hook,
        shutdown_hook=shutdown_hook
    )
    
    # Create FastAPI app with shared factory
    app = FastAPI(
        title="AIaaS API Gateway",
        version="2.0.0",
        description="Multi-tenant AI-as-a-Service API Gateway",
        lifespan=lifespan_manager,
    )

    # Add additional middleware
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["*"]  # Configure in production
    )

    app.add_middleware(TenantContextMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)

    return app


app = create_app()


# Add middleware after app creation
@app.middleware("http")
async def tenant_context_middleware(request: Request, call_next):
    """Set tenant context for database queries."""
    tenant_id = getattr(request.state, "tenant_id", None)

    if tenant_id and hasattr(app.state, 'db_config'):
        # Set tenant context in database session
        async with app.state.db_config.get_session() as session:
            await session.execute(
                text("SELECT set_tenant_context(:tenant_id)"), {"tenant_id": tenant_id}
            )
            request.state.db_session = session

    response = await call_next(request)
    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting based on tenant plan."""
    tenant_id = getattr(request.state, "tenant_id", None)

    if tenant_id and hasattr(app.state, 'rate_limiter'):
        # Check rate limits
        if not await app.state.rate_limiter.check_rate_limit(tenant_id, request):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content=error_response(
                    ErrorSpec(
                        code=ErrorCode.RATE_LIMIT,
                        message="Rate limit exceeded",
                        retriable=True,
                        retry_after_ms=60000,
                    )
                ),
            )

    response = await call_next(request)
    return response


@app.middleware("http")
async def quota_enforcement_middleware(request: Request, call_next):
    """Enforce tenant quotas."""
    tenant_id = getattr(request.state, "tenant_id", None)

    if tenant_id and hasattr(app.state, 'quota_enforcer'):
        # Check quotas
        if not await app.state.quota_enforcer.check_quotas(tenant_id, request):
            return JSONResponse(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                content=error_response(
                    ErrorSpec(
                        code=ErrorCode.QUOTA_EXCEEDED,
                        message="Quota exceeded",
                        retriable=False,
                    )
                ),
            )

    response = await call_next(request)
    return response


@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    """Handle API exceptions."""
    return JSONResponse(
        status_code=exc.status_code, content=error_response(exc.error_spec)
    )


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    """Handle validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response(
            ErrorSpec(code=ErrorCode.VALIDATION_FAIL, message=str(exc), retriable=False)
        ),
    )


@app.exception_handler(AuthenticationError)
async def auth_error_handler(request: Request, exc: AuthenticationError):
    """Handle authentication errors."""
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=error_response(
            ErrorSpec(
                code=ErrorCode.AUTHENTICATION_FAILED, message=str(exc), retriable=False
            )
        ),
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
                retriable=True,
            )
        ),
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
        if hasattr(app.state, 'db_config'):
            is_healthy = await app.state.db_config.health_check()
            if not is_healthy:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not ready"
                )

        return {"status": "ready", "timestamp": time.time()}
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service not ready"
        )


# API routes
@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "AIaaS API Gateway", "version": "2.0.0", "docs": "/docs"}


if __name__ == "__main__":
    uvicorn.run("apps.api-gateway.main:app", host="0.0.0.0", port=8000, reload=True)
