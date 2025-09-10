"""Analytics service with CQRS read-only API and Grafana dashboards."""

import asyncio
import time
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
import structlog
import redis.asyncio as redis
from contextlib import asynccontextmanager

from .core.analytics_engine import AnalyticsEngine, DataSource, TenantAnalytics
from .core.dashboard_generator import GrafanaDashboardGenerator

logger = structlog.get_logger(__name__)

# Global variables
redis_client: Optional[redis.Redis] = None
analytics_engine: Optional[AnalyticsEngine] = None
dashboard_generator: Optional[GrafanaDashboardGenerator] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global redis_client, analytics_engine, dashboard_generator
    
    # Initialize Redis connection
    redis_client = redis.Redis(
        host="localhost",
        port=6379,
        db=0,
        decode_responses=False
    )
    
    # Initialize analytics engine with warehouse support
    warehouse_config = {
        "host": "localhost",
        "port": 9000,
        "project_id": "ai-agent-analytics"
    }
    
    analytics_engine = AnalyticsEngine(
        redis_client=redis_client,
        data_source=DataSource.CLICKHOUSE,  # Use ClickHouse for analytics
        warehouse_config=warehouse_config
    )
    
    # Initialize dashboard generator
    dashboard_generator = GrafanaDashboardGenerator()
    
    # Generate dashboards
    dashboard_generator.generate_all_dashboards("observability/dashboards")
    
    logger.info("Analytics service started with warehouse support")
    
    yield
    
    # Cleanup
    if redis_client:
        await redis_client.close()
    
    logger.info("Analytics service shutdown")


app = FastAPI(
    title="Analytics Service",
    description="CQRS read-only analytics service with warehouse support",
    version="2.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "analytics"}


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    try:
        # Check Redis connection
        await redis_client.ping()
        return {"status": "ready", "service": "analytics"}
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service not ready")


@app.get("/analytics/kpi/{tenant_id}")
async def get_kpi_metrics(
    tenant_id: str,
    time_window: str = Query("1h", description="Time window: 1h, 24h, 7d, 30d")
):
    """Get KPI metrics for tenant."""
    try:
        if not analytics_engine:
            raise HTTPException(status_code=503, detail="Service not ready")
        
        metrics = await analytics_engine.get_kpi_metrics(tenant_id, time_window)
        
        return JSONResponse(content={
            "tenant_id": tenant_id,
            "time_window": time_window,
            "metrics": {
                "success_rate": metrics.success_rate,
                "p50_latency": metrics.p50_latency,
                "p95_latency": metrics.p95_latency,
                "p99_latency": metrics.p99_latency,
                "tokens_in": metrics.tokens_in,
                "tokens_out": metrics.tokens_out,
                "cost_per_run": metrics.cost_per_run,
                "total_cost": metrics.total_cost,
                "tier_distribution": metrics.tier_distribution,
                "router_misroute_rate": metrics.router_misroute_rate,
                "expected_vs_actual_cost": metrics.expected_vs_actual_cost,
                "expected_vs_actual_latency": metrics.expected_vs_actual_latency,
                "total_requests": metrics.total_requests,
                "successful_requests": metrics.successful_requests,
                "failed_requests": metrics.failed_requests,
                "avg_tokens_per_request": metrics.avg_tokens_per_request,
                "cost_efficiency": metrics.cost_efficiency,
                "latency_efficiency": metrics.latency_efficiency,
                "data_source": metrics.data_source,
                "timestamp": metrics.timestamp.isoformat()
            }
        })
        
    except Exception as e:
        logger.error("Failed to get KPI metrics", error=str(e), tenant_id=tenant_id)
        raise HTTPException(status_code=500, detail="Failed to get KPI metrics")


@app.get("/analytics/comprehensive/{tenant_id}")
async def get_comprehensive_analytics(
    tenant_id: str,
    time_window: str = Query("1h", description="Time window: 1h, 24h, 7d, 30d")
):
    """Get comprehensive analytics for tenant."""
    try:
        if not analytics_engine:
            raise HTTPException(status_code=503, detail="Service not ready")
        
        analytics = await analytics_engine.get_comprehensive_analytics(tenant_id, time_window)
        
        return JSONResponse(content={
            "tenant_id": tenant_id,
            "time_window": time_window,
            "kpi_metrics": {
                "success_rate": analytics.kpi_metrics.success_rate,
                "p50_latency": analytics.kpi_metrics.p50_latency,
                "p95_latency": analytics.kpi_metrics.p95_latency,
                "p99_latency": analytics.kpi_metrics.p99_latency,
                "tokens_in": analytics.kpi_metrics.tokens_in,
                "tokens_out": analytics.kpi_metrics.tokens_out,
                "cost_per_run": analytics.kpi_metrics.cost_per_run,
                "total_cost": analytics.kpi_metrics.total_cost,
                "tier_distribution": analytics.kpi_metrics.tier_distribution,
                "router_misroute_rate": analytics.kpi_metrics.router_misroute_rate,
                "expected_vs_actual_cost": analytics.kpi_metrics.expected_vs_actual_cost,
                "expected_vs_actual_latency": analytics.kpi_metrics.expected_vs_actual_latency,
                "total_requests": analytics.kpi_metrics.total_requests,
                "successful_requests": analytics.kpi_metrics.successful_requests,
                "failed_requests": analytics.kpi_metrics.failed_requests,
                "avg_tokens_per_request": analytics.kpi_metrics.avg_tokens_per_request,
                "cost_efficiency": analytics.kpi_metrics.cost_efficiency,
                "latency_efficiency": analytics.kpi_metrics.latency_efficiency,
                "data_source": analytics.kpi_metrics.data_source,
                "timestamp": analytics.kpi_metrics.timestamp.isoformat()
            },
            "usage_trends": analytics.usage_trends,
            "performance_insights": analytics.performance_insights,
            "cost_analysis": analytics.cost_analysis,
            "reliability_metrics": analytics.reliability_metrics,
            "data_source": analytics.data_source,
            "generated_at": analytics.generated_at.isoformat()
        })
        
    except Exception as e:
        logger.error("Failed to get comprehensive analytics", error=str(e), tenant_id=tenant_id)
        raise HTTPException(status_code=500, detail="Failed to get comprehensive analytics")


@app.get("/analytics/tenants")
async def list_tenants():
    """List all tenants with analytics data."""
    try:
        if not redis_client:
            raise HTTPException(status_code=503, detail="Service not ready")
        
        # Get all tenant keys from Redis
        pattern = "kpi_metrics:*"
        keys = await redis_client.keys(pattern)
        
        tenants = []
        for key in keys:
            # Extract tenant_id from key format: kpi_metrics:tenant_id:time_window
            key_parts = key.decode().split(":")
            if len(key_parts) >= 3:
                tenant_id = key_parts[1]
                if tenant_id not in tenants:
                    tenants.append(tenant_id)
        
        return JSONResponse(content={
            "tenants": tenants,
            "total_count": len(tenants)
        })
        
    except Exception as e:
        logger.error("Failed to list tenants", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list tenants")


@app.get("/analytics/dashboards")
async def list_dashboards():
    """List available Grafana dashboards."""
    try:
        if not dashboard_generator:
            raise HTTPException(status_code=503, detail="Service not ready")
        
        return JSONResponse(content={
            "dashboards": [
                {
                    "name": "Router Analytics",
                    "description": "Router v2 performance and decision metrics",
                    "file": "router_analytics.json"
                },
                {
                    "name": "Realtime Analytics", 
                    "description": "WebSocket service and backpressure metrics",
                    "file": "realtime_analytics.json"
                },
                {
                    "name": "Comprehensive Analytics",
                    "description": "Complete system overview and SLO compliance",
                    "file": "comprehensive_analytics.json"
                }
            ],
            "location": "observability/dashboards/"
        })
        
    except Exception as e:
        logger.error("Failed to list dashboards", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list dashboards")


@app.get("/analytics/dashboards/{dashboard_name}")
async def get_dashboard(dashboard_name: str):
    """Get specific Grafana dashboard JSON."""
    try:
        if not dashboard_generator:
            raise HTTPException(status_code=503, detail="Service not ready")
        
        dashboard_map = {
            "router": dashboard_generator.generate_router_analytics_dashboard(),
            "realtime": dashboard_generator.generate_realtime_analytics_dashboard(),
            "comprehensive": dashboard_generator.generate_comprehensive_analytics_dashboard()
        }
        
        if dashboard_name not in dashboard_map:
            raise HTTPException(status_code=404, detail="Dashboard not found")
        
        return JSONResponse(content=dashboard_map[dashboard_name])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get dashboard", error=str(e), dashboard_name=dashboard_name)
        raise HTTPException(status_code=500, detail="Failed to get dashboard")


@app.get("/analytics/metrics/prometheus")
async def get_prometheus_metrics():
    """Get metrics in Prometheus format."""
    try:
        if not analytics_engine:
            raise HTTPException(status_code=503, detail="Service not ready")
        
        # This would return actual Prometheus metrics in production
        # For now, return a sample format
        prometheus_metrics = """# HELP analytics_requests_total Total number of analytics requests
# TYPE analytics_requests_total counter
analytics_requests_total{service="analytics"} 1000

# HELP analytics_cache_hits_total Total number of cache hits
# TYPE analytics_cache_hits_total counter
analytics_cache_hits_total{service="analytics"} 750

# HELP analytics_warehouse_queries_total Total number of warehouse queries
# TYPE analytics_warehouse_queries_total counter
analytics_warehouse_queries_total{service="analytics",source="clickhouse"} 250
"""
        
        return prometheus_metrics
        
    except Exception as e:
        logger.error("Failed to get Prometheus metrics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get Prometheus metrics")


@app.post("/analytics/refresh/{tenant_id}")
async def refresh_analytics(tenant_id: str):
    """Refresh analytics data for tenant (clear cache)."""
    try:
        if not analytics_engine:
            raise HTTPException(status_code=503, detail="Service not ready")
        
        # Clear cache for tenant
        pattern = f"kpi_metrics:{tenant_id}:*"
        keys = await redis_client.keys(pattern)
        
        if keys:
            await redis_client.delete(*keys)
        
        logger.info("Analytics cache cleared", tenant_id=tenant_id)
        
        return JSONResponse(content={
            "message": f"Analytics cache cleared for tenant {tenant_id}",
            "cleared_keys": len(keys)
        })
        
    except Exception as e:
        logger.error("Failed to refresh analytics", error=str(e), tenant_id=tenant_id)
        raise HTTPException(status_code=500, detail="Failed to refresh analytics")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)