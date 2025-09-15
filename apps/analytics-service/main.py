"""Analytics service for CQRS read-only analytics."""

import asyncio
import time
from typing import Dict, Any, Optional
import structlog
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from apps.analytics_service.core.analytics_engine import AnalyticsEngine, KPIMetrics
from apps.analytics_service.core.dashboard_generator import DashboardGenerator

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


# Pydantic models
class KPIMetricsResponse(BaseModel):
    """Response model for KPI metrics."""

    tenant_id: str = Field(..., description="Tenant ID")
    time_window: str = Field(..., description="Time window")
    success_rate: float = Field(..., description="Success rate (0.0 to 1.0)")
    p50_latency: float = Field(..., description="P50 latency in milliseconds")
    p95_latency: float = Field(..., description="P95 latency in milliseconds")
    tokens_in: int = Field(..., description="Total tokens in")
    tokens_out: int = Field(..., description="Total tokens out")
    cost_per_run: float = Field(..., description="Average cost per run")
    tier_distribution: Dict[str, int] = Field(..., description="Tier distribution")
    router_misroute_rate: float = Field(..., description="Router misroute rate")
    expected_vs_actual_cost: float = Field(
        ..., description="Expected vs actual cost ratio"
    )
    expected_vs_actual_latency: float = Field(
        ..., description="Expected vs actual latency ratio"
    )
    timestamp: str = Field(..., description="Timestamp")


class DashboardResponse(BaseModel):
    """Response model for dashboard."""

    dashboard: Dict[str, Any] = Field(..., description="Grafana dashboard JSON")
    filepath: str = Field(..., description="File path where dashboard was saved")


# Global instances
analytics_engine: AnalyticsEngine = None
dashboard_generator: DashboardGenerator = None
redis_client: redis.Redis = None

# FastAPI app
app = FastAPI(
    title="Analytics Service",
    description="CQRS read-only analytics service for KPIs and dashboards",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_analytics_engine() -> AnalyticsEngine:
    """Get analytics engine instance."""
    if analytics_engine is None:
        raise HTTPException(status_code=503, detail="Analytics engine not initialized")
    return analytics_engine


async def get_dashboard_generator() -> DashboardGenerator:
    """Get dashboard generator instance."""
    if dashboard_generator is None:
        raise HTTPException(
            status_code=503, detail="Dashboard generator not initialized"
        )
    return dashboard_generator


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global analytics_engine, dashboard_generator, redis_client

    try:
        # Initialize Redis client
        redis_client = redis.Redis(
            host="localhost",
            port=6379,
            db=0,
            decode_responses=False,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )

        # Test Redis connection
        await redis_client.ping()
        logger.info("Redis connection established")

        # Initialize analytics engine
        analytics_engine = AnalyticsEngine(redis_client)
        logger.info("Analytics engine initialized")

        # Initialize dashboard generator
        dashboard_generator = DashboardGenerator()
        logger.info("Dashboard generator initialized")

    except Exception as e:
        logger.error("Failed to initialize services", error=str(e))
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global redis_client

    if redis_client:
        await redis_client.close()
        logger.info("Redis connection closed")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check Redis connection
        if redis_client:
            await redis_client.ping()

        return {
            "status": "healthy",
            "timestamp": time.time(),
            "service": "analytics-service",
        }
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service unhealthy")


@app.get("/kpi/{tenant_id}", response_model=KPIMetricsResponse)
async def get_kpi_metrics(
    tenant_id: str,
    time_window: str = Query("1h", description="Time window (1h, 24h, 7d, 30d)"),
    engine: AnalyticsEngine = Depends(get_analytics_engine),
) -> KPIMetricsResponse:
    """Get KPI metrics for tenant."""
    try:
        # Validate time window
        valid_windows = ["1h", "24h", "7d", "30d"]
        if time_window not in valid_windows:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid time window. Must be one of: {valid_windows}",
            )

        # Get metrics
        metrics: KPIMetrics = await engine.get_kpi_metrics(tenant_id, time_window)

        # Convert to response model
        response = KPIMetricsResponse(
            tenant_id=metrics.tenant_id,
            time_window=metrics.time_window,
            success_rate=metrics.success_rate,
            p50_latency=metrics.p50_latency,
            p95_latency=metrics.p95_latency,
            tokens_in=metrics.tokens_in,
            tokens_out=metrics.tokens_out,
            cost_per_run=metrics.cost_per_run,
            tier_distribution=metrics.tier_distribution,
            router_misroute_rate=metrics.router_misroute_rate,
            expected_vs_actual_cost=metrics.expected_vs_actual_cost,
            expected_vs_actual_latency=metrics.expected_vs_actual_latency,
            timestamp=metrics.timestamp.isoformat(),
        )

        logger.info(
            "KPI metrics retrieved",
            tenant_id=tenant_id,
            time_window=time_window,
            success_rate=metrics.success_rate,
            p50_latency=metrics.p50_latency,
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get KPI metrics", error=str(e), tenant_id=tenant_id)
        raise HTTPException(
            status_code=500, detail=f"Failed to get KPI metrics: {str(e)}"
        )


@app.get("/dashboard/{tenant_id}", response_model=DashboardResponse)
async def get_dashboard(
    tenant_id: str, generator: DashboardGenerator = Depends(get_dashboard_generator)
) -> DashboardResponse:
    """Generate Grafana dashboard for tenant."""
    try:
        # Generate dashboard
        dashboard = generator.generate_router_dashboard(tenant_id)

        if not dashboard:
            raise HTTPException(status_code=500, detail="Failed to generate dashboard")

        # Save dashboard to file
        filepath = f"observability/dashboards/router_analytics_{tenant_id}.json"
        generator.save_dashboard_json(dashboard, filepath)

        response = DashboardResponse(dashboard=dashboard, filepath=filepath)

        logger.info("Dashboard generated", tenant_id=tenant_id, filepath=filepath)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate dashboard", error=str(e), tenant_id=tenant_id)
        raise HTTPException(
            status_code=500, detail=f"Failed to generate dashboard: {str(e)}"
        )


@app.get("/dashboards")
async def list_dashboards():
    """List available dashboards."""
    try:
        import os

        dashboard_dir = "observability/dashboards"
        dashboards = []

        if os.path.exists(dashboard_dir):
            for filename in os.listdir(dashboard_dir):
                if filename.endswith(".json"):
                    dashboards.append(
                        {
                            "name": filename,
                            "path": f"{dashboard_dir}/{filename}",
                            "type": "router_analytics",
                        }
                    )

        return {"dashboards": dashboards, "count": len(dashboards)}

    except Exception as e:
        logger.error("Failed to list dashboards", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to list dashboards: {str(e)}"
        )


@app.get("/metrics")
async def get_metrics():
    """Get Prometheus metrics."""
    try:
        # Basic metrics for now
        metrics = {
            "analytics_requests_total": 0,
            "analytics_cache_hits": 0,
            "analytics_cache_misses": 0,
            "dashboard_generations_total": 0,
        }

        return metrics

    except Exception as e:
        logger.error("Failed to get metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8005, reload=True, log_level="info")
