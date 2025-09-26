"""
API Gateway Service

Main entry point for the API Gateway service.
Handles routing, authentication, rate limiting, and request/response processing.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

import uvicorn
from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import httpx
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.asyncio import AsyncioInstrumentor

from .config import Settings
from .middleware import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    CorrelationIdMiddleware,
    IdempotencyMiddleware
)
from .auth import AuthService
from .router import ServiceRouter
from .health import health_check, readiness_check

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    'api_gateway_requests_total',
    'Total number of requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'api_gateway_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint']
)

# Settings
settings = Settings()

# OpenTelemetry setup
def setup_tracing():
    """Initialize OpenTelemetry tracing"""
    if settings.enable_tracing:
        trace.set_tracer_provider(TracerProvider())
        tracer = trace.get_tracer(__name__)
        
        otlp_exporter = OTLPSpanExporter(
            endpoint=settings.otel_exporter_otlp_endpoint,
            insecure=True
        )
        span_processor = BatchSpanProcessor(otlp_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)
        
        # Instrument FastAPI
        FastAPIInstrumentor.instrument_app(app)
        
        # Instrument HTTP client
        HTTPXClientInstrumentor().instrument()
        
        # Instrument asyncio
        AsyncioInstrumentor().instrument()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Starting API Gateway service...")
    
    # Setup tracing
    setup_tracing()
    
    # Initialize services
    auth_service = AuthService(settings)
    service_router = ServiceRouter(settings)
    
    # Store services in app state
    app.state.auth_service = auth_service
    app.state.service_router = service_router
    
    logger.info("API Gateway service started successfully")
    
    yield
    
    logger.info("Shutting down API Gateway service...")

# Create FastAPI app
app = FastAPI(
    title="API Gateway",
    description="Multi-AI-Agent Platform API Gateway",
    version="1.0.0",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(IdempotencyMiddleware)

# Health check endpoints
@app.get("/healthz")
async def health():
    """Health check endpoint"""
    return await health_check()

@app.get("/readyz")
async def readiness():
    """Readiness check endpoint"""
    return await readiness_check(app.state)

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# API routes
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_request(
    request: Request,
    path: str,
    auth_service: AuthService = Depends(lambda: app.state.auth_service),
    service_router: ServiceRouter = Depends(lambda: app.state.service_router)
):
    """Proxy requests to appropriate services"""
    try:
        # Get correlation ID
        correlation_id = getattr(request.state, 'correlation_id', None)
        
        # Authenticate request
        user = await auth_service.authenticate_request(request)
        
        # Route to appropriate service
        target_service = service_router.get_target_service(path, request.method)
        
        if not target_service:
            raise HTTPException(status_code=404, detail="Service not found")
        
        # Forward request
        async with httpx.AsyncClient() as client:
            # Prepare headers
            headers = dict(request.headers)
            headers["X-Correlation-ID"] = correlation_id
            headers["X-User-ID"] = str(user.id) if user else "anonymous"
            headers["X-Tenant-ID"] = str(user.tenant_id) if user and user.tenant_id else "default"
            
            # Make request
            response = await client.request(
                method=request.method,
                url=f"{target_service.base_url}/{path}",
                headers=headers,
                content=await request.body(),
                params=request.query_params,
                timeout=30.0
            )
            
            # Update metrics
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=path,
                status_code=response.status_code
            ).inc()
            
            # Return response
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers)
            )
            
    except httpx.TimeoutException:
        logger.error(f"Request timeout for {path}")
        raise HTTPException(status_code=504, detail="Gateway timeout")
    except httpx.ConnectError:
        logger.error(f"Connection error for {path}")
        raise HTTPException(status_code=503, detail="Service unavailable")
    except Exception as e:
        logger.error(f"Error processing request {path}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info"
    )
