"""Admin Portal - Self-service portal for tenant management and plan administration."""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
from fastapi import FastAPI, HTTPException, status, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
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
# from libs.middleware.tenant_middleware import TenantMiddleware
# from libs.middleware.rate_limiter import RateLimiterMiddleware


# Configure OpenTelemetry
resource = Resource.create({ResourceAttributes.SERVICE_NAME: "admin-portal"})
provider = TracerProvider(resource=resource)
processor = SimpleSpanProcessor(ConsoleSpanExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)
logger = structlog.get_logger(__name__)


# Pydantic Models
class TenantSearchRequest(BaseModel):
    """Tenant search request."""
    query: Optional[str] = Field(None, description="Search query")
    plan: Optional[str] = Field(None, description="Filter by plan")
    status: Optional[str] = Field(None, description="Filter by status")
    created_after: Optional[str] = Field(None, description="Created after date")
    created_before: Optional[str] = Field(None, description="Created before date")
    limit: int = Field(default=50, description="Result limit")
    offset: int = Field(default=0, description="Result offset")


class TenantUpdateRequest(BaseModel):
    """Tenant update request."""
    name: Optional[str] = Field(None, description="Tenant name")
    email: Optional[str] = Field(None, description="Admin email")
    company_name: Optional[str] = Field(None, description="Company name")
    plan: Optional[str] = Field(None, description="Plan")
    status: Optional[str] = Field(None, description="Status")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class PlanConfigRequest(BaseModel):
    """Plan configuration request."""
    plan_name: str = Field(..., description="Plan name")
    display_name: str = Field(..., description="Display name")
    description: str = Field(..., description="Plan description")
    price_monthly: float = Field(..., description="Monthly price")
    price_yearly: float = Field(..., description="Yearly price")
    features: List[str] = Field(..., description="Plan features")
    limits: Dict[str, Any] = Field(..., description="Plan limits")
    enabled: bool = Field(default=True, description="Plan enabled")


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


class PlanConfigResponse(BaseModel):
    """Plan configuration response."""
    plan_name: str
    display_name: str
    description: str
    price_monthly: float
    price_yearly: float
    features: List[str]
    limits: Dict[str, Any]
    enabled: bool
    created_at: str
    updated_at: str


# FastAPI Application
def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="Admin Portal",
        description="Self-service portal for tenant management and plan administration",
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
    
    # Mount static files
    app.mount("/static", StaticFiles(directory="static"), name="static")
    
    # Templates
    templates = Jinja2Templates(directory="templates")
    app.state.templates = templates
    
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


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    try:
        logger.info("Starting Admin Portal")
        
        # Initialize Redis
        app.state.redis_client = redis.from_url(REDIS_URL)
        await app.state.redis_client.ping()
        
        # Initialize clients
        app.state.auth_client = AuthClient()
        app.state.billing_client = BillingClient()
        app.state.quota_client = QuotaClient()
        
        logger.info("Admin Portal started successfully")
        
    except Exception as e:
        logger.error("Failed to start Admin Portal", error=str(e))
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    try:
        logger.info("Shutting down Admin Portal")
        
        if app.state.redis_client:
            await app.state.redis_client.close()
        
        await engine.dispose()
        
        logger.info("Admin Portal shutdown complete")
        
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


async def get_current_admin(admin_id: str = Depends(lambda: "admin-user")) -> str:
    """Get current admin user ID."""
    return admin_id


# Web Routes
@app.get("/", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Admin dashboard."""
    try:
        # Get dashboard statistics
        stats = await get_dashboard_statistics()
        
        return app.state.templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "stats": stats,
                "title": "Admin Dashboard"
            }
        )
        
    except Exception as e:
        logger.error("Failed to load admin dashboard", error=str(e))
        return app.state.templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Failed to load dashboard",
                "title": "Error"
            }
        )


@app.get("/tenants", response_class=HTMLResponse)
async def tenants_page(request: Request, query: Optional[str] = None, 
                      plan: Optional[str] = None, status: Optional[str] = None,
                      page: int = 1, limit: int = 50):
    """Tenants management page."""
    try:
        # Search tenants
        search_request = TenantSearchRequest(
            query=query,
            plan=plan,
            status=status,
            limit=limit,
            offset=(page - 1) * limit
        )
        
        tenants = await search_tenants(search_request)
        total_count = await get_tenant_count(search_request)
        
        # Calculate pagination
        total_pages = (total_count + limit - 1) // limit
        has_prev = page > 1
        has_next = page < total_pages
        
        return app.state.templates.TemplateResponse(
            "tenants.html",
            {
                "request": request,
                "tenants": tenants,
                "query": query,
                "plan": plan,
                "status": status,
                "page": page,
                "limit": limit,
                "total_count": total_count,
                "total_pages": total_pages,
                "has_prev": has_prev,
                "has_next": has_next,
                "title": "Tenants"
            }
        )
        
    except Exception as e:
        logger.error("Failed to load tenants page", error=str(e))
        return app.state.templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Failed to load tenants",
                "title": "Error"
            }
        )


@app.get("/tenants/{tenant_id}", response_class=HTMLResponse)
async def tenant_detail(request: Request, tenant_id: str):
    """Tenant detail page."""
    try:
        # Get tenant details
        tenant = await get_tenant_details(tenant_id)
        
        if not tenant:
            return app.state.templates.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "error": "Tenant not found",
                    "title": "Error"
                }
            )
        
        # Get tenant usage statistics
        usage_stats = await get_tenant_usage_stats(tenant_id)
        
        # Get tenant billing history
        billing_history = await get_tenant_billing_history(tenant_id)
        
        return app.state.templates.TemplateResponse(
            "tenant_detail.html",
            {
                "request": request,
                "tenant": tenant,
                "usage_stats": usage_stats,
                "billing_history": billing_history,
                "title": f"Tenant: {tenant['name']}"
            }
        )
        
    except Exception as e:
        logger.error("Failed to load tenant detail", tenant_id=tenant_id, error=str(e))
        return app.state.templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Failed to load tenant details",
                "title": "Error"
            }
        )


@app.get("/plans", response_class=HTMLResponse)
async def plans_page(request: Request):
    """Plans management page."""
    try:
        # Get plan configurations
        plans = await get_plan_configurations()
        
        return app.state.templates.TemplateResponse(
            "plans.html",
            {
                "request": request,
                "plans": plans,
                "title": "Plans"
            }
        )
        
    except Exception as e:
        logger.error("Failed to load plans page", error=str(e))
        return app.state.templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Failed to load plans",
                "title": "Error"
            }
        )


@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    """Analytics page."""
    try:
        # Get analytics data
        analytics_data = await get_analytics_data()
        
        return app.state.templates.TemplateResponse(
            "analytics.html",
            {
                "request": request,
                "analytics": analytics_data,
                "title": "Analytics"
            }
        )
        
    except Exception as e:
        logger.error("Failed to load analytics page", error=str(e))
        return app.state.templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Failed to load analytics",
                "title": "Error"
            }
        )


# API Routes
@app.post("/api/v1/tenants/search", response_model=List[TenantResponse])
async def search_tenants(
    request: TenantSearchRequest,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Search tenants."""
    try:
        logger.info("Searching tenants", query=request.query, plan=request.plan)
        
        # Build search query
        query = text("""
            SELECT tenant_id, name, email, company_name, plan, status,
                   trial_ends_at, created_at, updated_at, metadata
            FROM tenants
            WHERE 1=1
        """)
        
        params = {}
        
        if request.query:
            query = text(str(query) + " AND (name ILIKE :query OR email ILIKE :query OR company_name ILIKE :query)")
            params["query"] = f"%{request.query}%"
        
        if request.plan:
            query = text(str(query) + " AND plan = :plan")
            params["plan"] = request.plan
        
        if request.status:
            query = text(str(query) + " AND status = :status")
            params["status"] = request.status
        
        if request.created_after:
            query = text(str(query) + " AND created_at >= :created_after")
            params["created_after"] = request.created_after
        
        if request.created_before:
            query = text(str(query) + " AND created_at <= :created_before")
            params["created_before"] = request.created_before
        
        query = text(str(query) + " ORDER BY created_at DESC LIMIT :limit OFFSET :offset")
        params["limit"] = request.limit
        params["offset"] = request.offset
        
        # Execute query
        result = await db_session.execute(query, params)
        rows = result.fetchall()
        
        # Convert to response format
        tenants = []
        for row in rows:
            tenants.append(TenantResponse(
                tenant_id=row.tenant_id,
                name=row.name,
                email=row.email,
                company_name=row.company_name,
                plan=row.plan,
                status=row.status,
                trial_ends_at=row.trial_ends_at.isoformat() if row.trial_ends_at else None,
                created_at=row.created_at.isoformat(),
                updated_at=row.updated_at.isoformat(),
                metadata=row.metadata or {}
            ))
        
        return tenants
        
    except Exception as e:
        logger.error("Failed to search tenants", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search tenants: {str(e)}"
        )


@app.get("/api/v1/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant_details(
    tenant_id: str,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Get tenant details."""
    try:
        logger.info("Getting tenant details", tenant_id=tenant_id)
        
        # Get tenant
        query = text("""
            SELECT tenant_id, name, email, company_name, plan, status,
                   trial_ends_at, created_at, updated_at, metadata
            FROM tenants
            WHERE tenant_id = :tenant_id
        """)
        
        result = await db_session.execute(query, {"tenant_id": tenant_id})
        row = result.fetchone()
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        return TenantResponse(
            tenant_id=row.tenant_id,
            name=row.name,
            email=row.email,
            company_name=row.company_name,
            plan=row.plan,
            status=row.status,
            trial_ends_at=row.trial_ends_at.isoformat() if row.trial_ends_at else None,
            created_at=row.created_at.isoformat(),
            updated_at=row.updated_at.isoformat(),
            metadata=row.metadata or {}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get tenant details", tenant_id=tenant_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tenant details: {str(e)}"
        )


@app.put("/api/v1/tenants/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str,
    request: TenantUpdateRequest,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Update tenant."""
    try:
        logger.info("Updating tenant", tenant_id=tenant_id)
        
        # Build update query
        update_fields = []
        params = {"tenant_id": tenant_id}
        
        if request.name is not None:
            update_fields.append("name = :name")
            params["name"] = request.name
        
        if request.email is not None:
            update_fields.append("email = :email")
            params["email"] = request.email
        
        if request.company_name is not None:
            update_fields.append("company_name = :company_name")
            params["company_name"] = request.company_name
        
        if request.plan is not None:
            update_fields.append("plan = :plan")
            params["plan"] = request.plan
        
        if request.status is not None:
            update_fields.append("status = :status")
            params["status"] = request.status
        
        if request.metadata is not None:
            update_fields.append("metadata = :metadata")
            params["metadata"] = request.metadata
        
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        update_fields.append("updated_at = :updated_at")
        params["updated_at"] = datetime.now(timezone.utc)
        
        query = text(f"""
            UPDATE tenants
            SET {', '.join(update_fields)}
            WHERE tenant_id = :tenant_id
            RETURNING tenant_id, name, email, company_name, plan, status,
                      trial_ends_at, created_at, updated_at, metadata
        """)
        
        result = await db_session.execute(query, params)
        row = result.fetchone()
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        await db_session.commit()
        
        return TenantResponse(
            tenant_id=row.tenant_id,
            name=row.name,
            email=row.email,
            company_name=row.company_name,
            plan=row.plan,
            status=row.status,
            trial_ends_at=row.trial_ends_at.isoformat() if row.trial_ends_at else None,
            created_at=row.created_at.isoformat(),
            updated_at=row.updated_at.isoformat(),
            metadata=row.metadata or {}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update tenant", tenant_id=tenant_id, error=str(e))
        await db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update tenant: {str(e)}"
        )


@app.post("/api/v1/plans", response_model=PlanConfigResponse)
async def create_plan_config(
    request: PlanConfigRequest,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Create plan configuration."""
    try:
        logger.info("Creating plan configuration", plan_name=request.plan_name)
        
        # Create plan configuration
        query = text("""
            INSERT INTO plan_configurations (
                plan_name, display_name, description, price_monthly, price_yearly,
                features, limits, enabled, created_at, updated_at
            ) VALUES (
                :plan_name, :display_name, :description, :price_monthly, :price_yearly,
                :features, :limits, :enabled, :created_at, :updated_at
            )
            RETURNING plan_name, display_name, description, price_monthly, price_yearly,
                      features, limits, enabled, created_at, updated_at
        """)
        
        params = {
            "plan_name": request.plan_name,
            "display_name": request.display_name,
            "description": request.description,
            "price_monthly": request.price_monthly,
            "price_yearly": request.price_yearly,
            "features": request.features,
            "limits": request.limits,
            "enabled": request.enabled,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        result = await db_session.execute(query, params)
        row = result.fetchone()
        
        await db_session.commit()
        
        return PlanConfigResponse(
            plan_name=row.plan_name,
            display_name=row.display_name,
            description=row.description,
            price_monthly=row.price_monthly,
            price_yearly=row.price_yearly,
            features=row.features,
            limits=row.limits,
            enabled=row.enabled,
            created_at=row.created_at.isoformat(),
            updated_at=row.updated_at.isoformat()
        )
        
    except Exception as e:
        logger.error("Failed to create plan configuration", error=str(e))
        await db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create plan configuration: {str(e)}"
        )


@app.get("/api/v1/plans", response_model=List[PlanConfigResponse])
async def get_plan_configurations(
    db_session: AsyncSession = Depends(get_db_session)
):
    """Get plan configurations."""
    try:
        logger.info("Getting plan configurations")
        
        # Get plan configurations
        query = text("""
            SELECT plan_name, display_name, description, price_monthly, price_yearly,
                   features, limits, enabled, created_at, updated_at
            FROM plan_configurations
            ORDER BY created_at DESC
        """)
        
        result = await db_session.execute(query)
        rows = result.fetchall()
        
        # Convert to response format
        plans = []
        for row in rows:
            plans.append(PlanConfigResponse(
                plan_name=row.plan_name,
                display_name=row.display_name,
                description=row.description,
                price_monthly=row.price_monthly,
                price_yearly=row.price_yearly,
                features=row.features,
                limits=row.limits,
                enabled=row.enabled,
                created_at=row.created_at.isoformat(),
                updated_at=row.updated_at.isoformat()
            ))
        
        return plans
        
    except Exception as e:
        logger.error("Failed to get plan configurations", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get plan configurations: {str(e)}"
        )


# Helper functions
async def get_dashboard_statistics() -> Dict[str, Any]:
    """Get dashboard statistics."""
    try:
        # This would typically query the database for real statistics
        # For now, we'll return mock data
        
        return {
            "total_tenants": 1250,
            "active_tenants": 1180,
            "trial_tenants": 70,
            "monthly_revenue": 45000.0,
            "plan_distribution": {
                "trial": 70,
                "basic": 450,
                "pro": 520,
                "enterprise": 210
            },
            "recent_signups": 45,
            "churn_rate": 2.3
        }
        
    except Exception as e:
        logger.error("Failed to get dashboard statistics", error=str(e))
        return {}


async def get_tenant_count(search_request: TenantSearchRequest) -> int:
    """Get tenant count for search."""
    try:
        # This would typically query the database
        # For now, we'll return a mock count
        return 1250
        
    except Exception as e:
        logger.error("Failed to get tenant count", error=str(e))
        return 0


async def get_tenant_usage_stats(tenant_id: str) -> Dict[str, Any]:
    """Get tenant usage statistics."""
    try:
        # This would typically query usage data
        # For now, we'll return mock data
        
        return {
            "api_calls": 12500,
            "storage_used": "2.5 GB",
            "bandwidth_used": "15.2 GB",
            "active_users": 25,
            "last_activity": "2024-01-15T10:30:00Z"
        }
        
    except Exception as e:
        logger.error("Failed to get tenant usage stats", tenant_id=tenant_id, error=str(e))
        return {}


async def get_tenant_billing_history(tenant_id: str) -> List[Dict[str, Any]]:
    """Get tenant billing history."""
    try:
        # This would typically query billing data
        # For now, we'll return mock data
        
        return [
            {
                "date": "2024-01-01",
                "amount": 99.0,
                "plan": "pro",
                "status": "paid"
            },
            {
                "date": "2023-12-01",
                "amount": 99.0,
                "plan": "pro",
                "status": "paid"
            }
        ]
        
    except Exception as e:
        logger.error("Failed to get tenant billing history", tenant_id=tenant_id, error=str(e))
        return []


async def get_analytics_data() -> Dict[str, Any]:
    """Get analytics data."""
    try:
        # This would typically query analytics data
        # For now, we'll return mock data
        
        return {
            "revenue_trend": [
                {"month": "2023-10", "revenue": 42000},
                {"month": "2023-11", "revenue": 43500},
                {"month": "2023-12", "revenue": 44800},
                {"month": "2024-01", "revenue": 45000}
            ],
            "tenant_growth": [
                {"month": "2023-10", "tenants": 1100},
                {"month": "2023-11", "tenants": 1150},
                {"month": "2023-12", "tenants": 1200},
                {"month": "2024-01", "tenants": 1250}
            ],
            "plan_conversion": {
                "trial_to_basic": 35.2,
                "basic_to_pro": 28.7,
                "pro_to_enterprise": 15.3
            }
        }
        
    except Exception as e:
        logger.error("Failed to get analytics data", error=str(e))
        return {}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "admin-portal"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)
