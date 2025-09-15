"""Tenant Service - Manages tenant onboarding, plan changes, and lifecycle events."""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
from fastapi import FastAPI, HTTPException, status, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text
import redis.asyncio as redis
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.semconv.resource import ResourceAttributes

from libs.clients.auth import AuthClient
from libs.clients.billing import BillingClient
from libs.clients.quota import QuotaClient
from libs.middleware.tenant_middleware import TenantMiddleware
from libs.middleware.rate_limiter import RateLimiterMiddleware
from apps.tenant-service.core.tenant_onboarding import TenantOnboardingManager
from apps.tenant-service.core.plan_upgrade_manager import PlanUpgradeManager
from apps.tenant-service.core.webhook_manager import WebhookManager, WebhookEvent


# Configure OpenTelemetry
resource = Resource.create({ResourceAttributes.SERVICE_NAME: "tenant-service"})
provider = TracerProvider(resource=resource)
processor = SimpleSpanProcessor(ConsoleSpanExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)
logger = structlog.get_logger(__name__)


# Pydantic Models
class TenantSignupRequest(BaseModel):
    """Tenant signup request."""
    name: str = Field(..., description="Tenant name")
    email: str = Field(..., description="Admin email")
    company_name: Optional[str] = Field(None, description="Company name")
    plan: str = Field(default="trial", description="Initial plan")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    @validator('email')
    def validate_email(cls, v):
        if '@' not in v:
            raise ValueError('Invalid email format')
        return v
    
    @validator('plan')
    def validate_plan(cls, v):
        valid_plans = ['trial', 'basic', 'pro', 'enterprise']
        if v not in valid_plans:
            raise ValueError(f'Invalid plan. Must be one of: {valid_plans}')
        return v


class PlanUpgradeRequest(BaseModel):
    """Plan upgrade request."""
    plan: str = Field(..., description="Target plan")
    billing_cycle: str = Field(default="monthly", description="Billing cycle")
    payment_method_id: Optional[str] = Field(None, description="Payment method ID")
    
    @validator('plan')
    def validate_plan(cls, v):
        valid_plans = ['trial', 'basic', 'pro', 'enterprise']
        if v not in valid_plans:
            raise ValueError(f'Invalid plan. Must be one of: {valid_plans}')
        return v
    
    @validator('billing_cycle')
    def validate_billing_cycle(cls, v):
        valid_cycles = ['monthly', 'yearly']
        if v not in valid_cycles:
            raise ValueError('Invalid billing cycle. Must be monthly or yearly')
        return v


class WebhookEndpointRequest(BaseModel):
    """Webhook endpoint request."""
    url: str = Field(..., description="Webhook URL")
    events: List[str] = Field(..., description="Events to subscribe to")
    secret: str = Field(..., description="Webhook secret")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    @validator('url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Invalid URL format')
        return v
    
    @validator('events')
    def validate_events(cls, v):
        valid_events = [
            'tenant.created', 'tenant.updated', 'tenant.deleted',
            'plan.upgraded', 'plan.downgraded',
            'payment.success', 'payment.failed',
            'trial.started', 'trial.ending', 'trial.ended',
            'quota.exceeded', 'billing.cycle_changed',
            'subscription.cancelled', 'subscription.reactivated'
        ]
        for event in v:
            if event not in valid_events:
                raise ValueError(f'Invalid event: {event}')
        return v


class TenantResponse(BaseModel):
    """Tenant response."""
    tenant_id: str
    name: str
    email: str
    company_name: Optional[str]
    plan: str
    status: str
    trial_ends_at: Optional[str]
    created_at: str
    updated_at: str
    metadata: Dict[str, Any]


class PlanUpgradeResponse(BaseModel):
    """Plan upgrade response."""
    tenant_id: str
    old_plan: str
    new_plan: str
    billing_cycle: str
    upgrade_date: str
    next_billing_date: str
    cost: Dict[str, Any]


class WebhookEndpointResponse(BaseModel):
    """Webhook endpoint response."""
    endpoint_id: str
    url: str
    events: List[str]
    enabled: bool
    created_at: str
    updated_at: str
    metadata: Dict[str, Any]


# FastAPI Application
def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="Tenant Service",
        description="Manages tenant onboarding, plan changes, and lifecycle events",
        version="1.0.0"
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app


app = create_app()


# Database and Redis setup
DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/multitenant"
REDIS_URL = "redis://localhost:6379"

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True, pool_recycle=300)
async_session = async_sessionmaker(engine, expire_on_commit=False)


# Global state
app.state.db_session = async_session
app.state.redis_client = None
app.state.auth_client = None
app.state.billing_client = None
app.state.quota_client = None
app.state.tenant_onboarding_manager = None
app.state.plan_upgrade_manager = None
app.state.webhook_manager = None


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    try:
        logger.info("Starting Tenant Service")
        
        # Initialize Redis
        app.state.redis_client = redis.from_url(REDIS_URL)
        await app.state.redis_client.ping()
        
        # Initialize clients
        app.state.auth_client = AuthClient()
        app.state.billing_client = BillingClient()
        app.state.quota_client = QuotaClient()
        
        # Initialize managers
        app.state.tenant_onboarding_manager = TenantOnboardingManager(
            app.state.db_session(),
            app.state.redis_client,
            app.state.auth_client,
            app.state.billing_client,
            app.state.quota_client
        )
        
        app.state.plan_upgrade_manager = PlanUpgradeManager(
            app.state.db_session(),
            app.state.redis_client,
            app.state.billing_client,
            app.state.quota_client
        )
        
        app.state.webhook_manager = WebhookManager(app.state.db_session())
        
        logger.info("Tenant Service started successfully")
        
    except Exception as e:
        logger.error("Failed to start Tenant Service", error=str(e))
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    try:
        logger.info("Shutting down Tenant Service")
        
        if app.state.redis_client:
            await app.state.redis_client.close()
        
        await engine.dispose()
        
        logger.info("Tenant Service shutdown complete")
        
    except Exception as e:
        logger.error("Error during shutdown", error=str(e))


# Dependency injection
async def get_db_session() -> AsyncSession:
    """Get database session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_tenant(tenant_id: str = Depends(lambda: "current-tenant")) -> str:
    """Get current tenant ID."""
    return tenant_id


# Routes
@app.post("/api/v1/tenants/signup", response_model=TenantResponse)
async def signup_tenant(
    request: TenantSignupRequest,
    background_tasks: BackgroundTasks,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Sign up a new tenant."""
    try:
        logger.info("Processing tenant signup", email=request.email, plan=request.plan)
        
        # Create tenant
        tenant = await app.state.tenant_onboarding_manager.create_tenant(
            name=request.name,
            email=request.email,
            company_name=request.company_name,
            plan=request.plan,
            metadata=request.metadata
        )
        
        # Trigger webhook event
        background_tasks.add_task(
            app.state.webhook_manager.trigger_webhook_event,
            WebhookEvent.TENANT_CREATED,
            tenant.tenant_id,
            tenant.to_dict()
        )
        
        logger.info("Tenant signup completed", tenant_id=tenant.tenant_id)
        
        return TenantResponse(
            tenant_id=tenant.tenant_id,
            name=tenant.name,
            email=tenant.email,
            company_name=tenant.company_name,
            plan=tenant.plan,
            status=tenant.status.value,
            trial_ends_at=tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None,
            created_at=tenant.created_at.isoformat(),
            updated_at=tenant.updated_at.isoformat(),
            metadata=tenant.metadata
        )
        
    except Exception as e:
        logger.error("Tenant signup failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tenant signup failed: {str(e)}"
        )


@app.post("/api/v1/tenants/{tenant_id}/upgrade", response_model=PlanUpgradeResponse)
async def upgrade_plan(
    tenant_id: str,
    request: PlanUpgradeRequest,
    background_tasks: BackgroundTasks,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Upgrade tenant plan."""
    try:
        logger.info("Processing plan upgrade", tenant_id=tenant_id, plan=request.plan)
        
        # Upgrade plan
        upgrade_result = await app.state.plan_upgrade_manager.upgrade_plan(
            tenant_id=tenant_id,
            new_plan=request.plan,
            billing_cycle=request.billing_cycle,
            payment_method_id=request.payment_method_id
        )
        
        # Trigger webhook event
        background_tasks.add_task(
            app.state.webhook_manager.trigger_webhook_event,
            WebhookEvent.PLAN_UPGRADED,
            tenant_id,
            upgrade_result.to_dict()
        )
        
        logger.info("Plan upgrade completed", tenant_id=tenant_id)
        
        return PlanUpgradeResponse(
            tenant_id=upgrade_result.tenant_id,
            old_plan=upgrade_result.old_plan,
            new_plan=upgrade_result.new_plan,
            billing_cycle=upgrade_result.billing_cycle,
            upgrade_date=upgrade_result.upgrade_date.isoformat(),
            next_billing_date=upgrade_result.next_billing_date.isoformat(),
            cost=upgrade_result.cost
        )
        
    except Exception as e:
        logger.error("Plan upgrade failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Plan upgrade failed: {str(e)}"
        )


@app.get("/api/v1/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Get tenant information."""
    try:
        logger.info("Getting tenant", tenant_id=tenant_id)
        
        # Get tenant
        tenant = await app.state.tenant_onboarding_manager.get_tenant(tenant_id)
        
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        return TenantResponse(
            tenant_id=tenant.tenant_id,
            name=tenant.name,
            email=tenant.email,
            company_name=tenant.company_name,
            plan=tenant.plan,
            status=tenant.status.value,
            trial_ends_at=tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None,
            created_at=tenant.created_at.isoformat(),
            updated_at=tenant.updated_at.isoformat(),
            metadata=tenant.metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get tenant", tenant_id=tenant_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tenant: {str(e)}"
        )


@app.post("/api/v1/tenants/{tenant_id}/webhooks", response_model=WebhookEndpointResponse)
async def create_webhook_endpoint(
    tenant_id: str,
    request: WebhookEndpointRequest,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Create webhook endpoint."""
    try:
        logger.info("Creating webhook endpoint", tenant_id=tenant_id)
        
        # Convert event strings to enums
        events = [WebhookEvent(event) for event in request.events]
        
        # Create webhook endpoint
        endpoint_id = await app.state.webhook_manager.create_webhook_endpoint(
            tenant_id=tenant_id,
            url=request.url,
            events=events,
            secret=request.secret,
            metadata=request.metadata
        )
        
        # Get created endpoint
        endpoints = await app.state.webhook_manager.get_webhook_endpoints(tenant_id)
        endpoint = next(e for e in endpoints if e["endpoint_id"] == endpoint_id)
        
        return WebhookEndpointResponse(
            endpoint_id=endpoint["endpoint_id"],
            url=endpoint["url"],
            events=endpoint["events"],
            enabled=endpoint["enabled"],
            created_at=endpoint["created_at"],
            updated_at=endpoint["updated_at"],
            metadata=endpoint["metadata"]
        )
        
    except Exception as e:
        logger.error("Failed to create webhook endpoint", tenant_id=tenant_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create webhook endpoint: {str(e)}"
        )


@app.get("/api/v1/tenants/{tenant_id}/webhooks", response_model=List[WebhookEndpointResponse])
async def get_webhook_endpoints(
    tenant_id: str,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Get webhook endpoints for tenant."""
    try:
        logger.info("Getting webhook endpoints", tenant_id=tenant_id)
        
        # Get webhook endpoints
        endpoints = await app.state.webhook_manager.get_webhook_endpoints(tenant_id)
        
        return [
            WebhookEndpointResponse(
                endpoint_id=endpoint["endpoint_id"],
                url=endpoint["url"],
                events=endpoint["events"],
                enabled=endpoint["enabled"],
                created_at=endpoint["created_at"],
                updated_at=endpoint["updated_at"],
                metadata=endpoint["metadata"]
            )
            for endpoint in endpoints
        ]
        
    except Exception as e:
        logger.error("Failed to get webhook endpoints", tenant_id=tenant_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get webhook endpoints: {str(e)}"
        )


@app.delete("/api/v1/tenants/{tenant_id}/webhooks/{endpoint_id}")
async def delete_webhook_endpoint(
    tenant_id: str,
    endpoint_id: str,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Delete webhook endpoint."""
    try:
        logger.info("Deleting webhook endpoint", tenant_id=tenant_id, endpoint_id=endpoint_id)
        
        # Delete webhook endpoint
        success = await app.state.webhook_manager.delete_webhook_endpoint(endpoint_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook endpoint not found"
            )
        
        return {"message": "Webhook endpoint deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete webhook endpoint", tenant_id=tenant_id, endpoint_id=endpoint_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete webhook endpoint: {str(e)}"
        )


@app.get("/api/v1/tenants/{tenant_id}/webhooks/{endpoint_id}/deliveries")
async def get_webhook_deliveries(
    tenant_id: str,
    endpoint_id: str,
    limit: int = 100,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Get webhook deliveries for endpoint."""
    try:
        logger.info("Getting webhook deliveries", tenant_id=tenant_id, endpoint_id=endpoint_id)
        
        # Get webhook deliveries
        deliveries = await app.state.webhook_manager.get_webhook_deliveries(endpoint_id, limit)
        
        return deliveries
        
    except Exception as e:
        logger.error("Failed to get webhook deliveries", tenant_id=tenant_id, endpoint_id=endpoint_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get webhook deliveries: {str(e)}"
        )


@app.post("/api/v1/tenants/{tenant_id}/webhooks/{endpoint_id}/retry")
async def retry_webhook_deliveries(
    tenant_id: str,
    endpoint_id: str,
    background_tasks: BackgroundTasks,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Retry failed webhook deliveries."""
    try:
        logger.info("Retrying webhook deliveries", tenant_id=tenant_id, endpoint_id=endpoint_id)
        
        # Retry failed deliveries
        background_tasks.add_task(
            app.state.webhook_manager.retry_failed_deliveries
        )
        
        return {"message": "Webhook delivery retry initiated"}
        
    except Exception as e:
        logger.error("Failed to retry webhook deliveries", tenant_id=tenant_id, endpoint_id=endpoint_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry webhook deliveries: {str(e)}"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "tenant-service"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
