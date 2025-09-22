"""Orchestrator service for multi-tenant AIaaS platform."""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
from opentelemetry import trace

from libs.contracts.agent import AgentRun, AgentSpec
from libs.contracts.tool import ToolCall, ToolResult
from libs.contracts.message import MessageSpec, MessageRole
from libs.contracts.error import ErrorSpec, ErrorCode
from libs.clients.database import get_db_session
from libs.clients.auth import get_current_tenant
from libs.clients.event_bus import EventBus, EventProducer
from libs.utils.responses import success_response, error_response
from libs.utils.exceptions import APIException, ValidationError
from src.core.orchestrator import OrchestratorEngine
from src.core.workflow import WorkflowEngine
from src.core.saga import SagaManager

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
    logger.info("Starting Orchestrator Service")

    # Initialize components
    app.state.event_bus = EventBus()
    app.state.event_producer = EventProducer(app.state.event_bus)
    app.state.workflow_engine = WorkflowEngine()
    app.state.saga_manager = SagaManager()
    app.state.orchestrator = OrchestratorEngine(
        event_producer=app.state.event_producer,
        workflow_engine=app.state.workflow_engine,
        saga_manager=app.state.saga_manager,
    )

    yield

    # Shutdown
    logger.info("Shutting down Orchestrator Service")


def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="AIaaS Orchestrator",
        version="2.0.0",
        description="LangGraph-based orchestrator for multi-tenant AI platform",
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
        # Check if all components are ready
        if not app.state.orchestrator.is_ready():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Orchestrator not ready",
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
    return {"message": "AIaaS Orchestrator", "version": "2.0.0", "docs": "/docs"}


@app.post("/v1/runs", response_model=AgentRun)
async def create_run(
    agent_spec: AgentSpec,
    context: Dict[str, Any],
    tenant_id: str = Depends(get_current_tenant),
):
    """Create new agent run."""
    with tracer.start_as_current_span("create_run") as span:
        span.set_attribute("tenant_id", str(tenant_id))
        span.set_attribute("agent_name", agent_spec.name)

        try:
            # Create agent run
            run = await app.state.orchestrator.create_run(
                tenant_id=tenant_id, agent_spec=agent_spec, context=context
            )

            # Emit event
            await app.state.event_producer.emit(
                "agent.run.requested",
                {
                    "run_id": str(run.run_id),
                    "tenant_id": str(tenant_id),
                    "agent_name": agent_spec.name,
                },
            )

            logger.info(
                "Agent run created",
                run_id=str(run.run_id),
                tenant_id=str(tenant_id),
                agent_name=agent_spec.name,
            )

            return run

        except Exception as e:
            logger.error(
                "Failed to create run",
                tenant_id=str(tenant_id),
                agent_name=agent_spec.name,
                error=str(e),
            )
            raise


@app.post("/v1/runs/{run_id}/start")
async def start_run(run_id: str, tenant_id: str = Depends(get_current_tenant)):
    """Start agent run execution."""
    with tracer.start_as_current_span("start_run") as span:
        span.set_attribute("tenant_id", str(tenant_id))
        span.set_attribute("run_id", run_id)

        try:
            # Start run
            await app.state.orchestrator.start_run(run_id, tenant_id)

            # Emit event
            await app.state.event_producer.emit(
                "agent.run.started", {"run_id": run_id, "tenant_id": str(tenant_id)}
            )

            logger.info("Agent run started", run_id=run_id, tenant_id=str(tenant_id))

            return success_response(None, "Run started successfully")

        except Exception as e:
            logger.error(
                "Failed to start run",
                run_id=run_id,
                tenant_id=str(tenant_id),
                error=str(e),
            )
            raise


@app.get("/v1/runs/{run_id}", response_model=AgentRun)
async def get_run(run_id: str, tenant_id: str = Depends(get_current_tenant)):
    """Get agent run status."""
    with tracer.start_as_current_span("get_run") as span:
        span.set_attribute("tenant_id", str(tenant_id))
        span.set_attribute("run_id", run_id)

        try:
            # Get run
            run = await app.state.orchestrator.get_run(run_id, tenant_id)

            return run

        except Exception as e:
            logger.error(
                "Failed to get run",
                run_id=run_id,
                tenant_id=str(tenant_id),
                error=str(e),
            )
            raise


@app.post("/v1/runs/{run_id}/cancel")
async def cancel_run(run_id: str, tenant_id: str = Depends(get_current_tenant)):
    """Cancel agent run."""
    with tracer.start_as_current_span("cancel_run") as span:
        span.set_attribute("tenant_id", str(tenant_id))
        span.set_attribute("run_id", run_id)

        try:
            # Cancel run
            await app.state.orchestrator.cancel_run(run_id, tenant_id)

            # Emit event
            await app.state.event_producer.emit(
                "agent.run.cancelled", {"run_id": run_id, "tenant_id": str(tenant_id)}
            )

            logger.info("Agent run cancelled", run_id=run_id, tenant_id=str(tenant_id))

            return success_response(None, "Run cancelled successfully")

        except Exception as e:
            logger.error(
                "Failed to cancel run",
                run_id=run_id,
                tenant_id=str(tenant_id),
                error=str(e),
            )
            raise


if __name__ == "__main__":
    uvicorn.run("apps.orchestrator.main:app", host="0.0.0.0", port=8081, reload=True)
