"""Capacity monitoring service for peak traffic handling."""

import asyncio
import time
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import structlog
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from configs.capacity_config import CapacityConfigManager, Environment, DegradeMode

logger = structlog.get_logger(__name__)

# Pydantic models
class CapacityMetrics(BaseModel):
    """Capacity metrics model."""
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    active_connections: int
    request_rate: float
    response_time_p95: float
    error_rate: float
    queue_depth: int
    database_connections: int
    redis_connections: int
    nats_connections: int

class DegradeRequest(BaseModel):
    """Degrade mode request."""
    mode: str = Field(..., description="Degrade mode: normal, degraded, emergency")
    reason: str = Field(..., description="Reason for degrade mode")
    duration_minutes: Optional[int] = Field(None, description="Duration in minutes, None for indefinite")

class CapacityAlert(BaseModel):
    """Capacity alert model."""
    alert_id: str
    timestamp: datetime
    severity: str
    metric: str
    value: float
    threshold: float
    message: str
    resolved: bool = False

# Initialize FastAPI app
app = FastAPI(
    title="Capacity Monitor Service",
    description="Monitor and manage capacity for peak traffic handling",
    version="1.0.0"
)

# Global services
redis_client: Optional[redis.Redis] = None
config_manager: Optional[CapacityConfigManager] = None
current_metrics: Optional[CapacityMetrics] = None
active_alerts: List[CapacityAlert] = []
degrade_mode: DegradeMode = DegradeMode.NORMAL

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global redis_client, config_manager
    
    # Initialize Redis client
    redis_client = redis.from_url("redis://localhost:6379")
    
    # Initialize configuration manager
    config_manager = CapacityConfigManager()
    
    # Start monitoring task
    asyncio.create_task(monitoring_loop())
    
    logger.info("Capacity monitor service started")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    if redis_client:
        await redis_client.close()
    logger.info("Capacity monitor service stopped")

# Monitoring endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "degrade_mode": degrade_mode.value
    }

@app.get("/metrics")
async def get_metrics():
    """Get current capacity metrics."""
    if not current_metrics:
        raise HTTPException(status_code=404, detail="No metrics available")
    
    return current_metrics.dict()

@app.get("/alerts")
async def get_alerts():
    """Get active alerts."""
    return [alert.dict() for alert in active_alerts if not alert.resolved]

@app.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    """Resolve an alert."""
    for alert in active_alerts:
        if alert.alert_id == alert_id:
            alert.resolved = True
            logger.info("Alert resolved", alert_id=alert_id)
            return {"status": "resolved", "alert_id": alert_id}
    
    raise HTTPException(status_code=404, detail="Alert not found")

@app.post("/degrade")
async def set_degrade_mode(request: DegradeRequest, background_tasks: BackgroundTasks):
    """Set degrade mode."""
    global degrade_mode
    
    try:
        new_mode = DegradeMode(request.mode)
        old_mode = degrade_mode
        degrade_mode = new_mode
        
        # Apply degrade configuration
        await apply_degrade_configuration(new_mode)
        
        # Schedule automatic recovery if duration is specified
        if request.duration_minutes:
            background_tasks.add_task(
                schedule_degrade_recovery,
                old_mode,
                request.duration_minutes * 60
            )
        
        logger.info("Degrade mode changed", 
                   old_mode=old_mode.value,
                   new_mode=new_mode.value,
                   reason=request.reason)
        
        return {
            "status": "success",
            "degrade_mode": new_mode.value,
            "reason": request.reason,
            "duration_minutes": request.duration_minutes
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid degrade mode: {e}")

@app.get("/config")
async def get_config():
    """Get current capacity configuration."""
    if not config_manager:
        raise HTTPException(status_code=500, detail="Configuration manager not initialized")
    
    config = config_manager.get_config()
    return config.__dict__

@app.post("/config/reload")
async def reload_config():
    """Reload configuration."""
    if not config_manager:
        raise HTTPException(status_code=500, detail="Configuration manager not initialized")
    
    config_manager._load_configurations()
    
    logger.info("Configuration reloaded")
    return {"status": "success", "message": "Configuration reloaded"}

@app.get("/capacity/status")
async def get_capacity_status():
    """Get overall capacity status."""
    if not current_metrics:
        raise HTTPException(status_code=404, detail="No metrics available")
    
    # Calculate capacity status
    status = calculate_capacity_status(current_metrics)
    
    return {
        "status": status,
        "degrade_mode": degrade_mode.value,
        "metrics": current_metrics.dict(),
        "alerts": len([a for a in active_alerts if not a.resolved]),
        "recommendations": get_capacity_recommendations(current_metrics)
    }

# Background tasks
async def monitoring_loop():
    """Main monitoring loop."""
    while True:
        try:
            await collect_metrics()
            await check_thresholds()
            await cleanup_old_alerts()
            
            # Wait before next collection
            await asyncio.sleep(10)  # Collect metrics every 10 seconds
            
        except Exception as e:
            logger.error("Error in monitoring loop", error=str(e))
            await asyncio.sleep(30)  # Wait longer on error

async def collect_metrics():
    """Collect capacity metrics."""
    global current_metrics
    
    try:
        # Simulate metric collection (in real implementation, this would collect from actual sources)
        metrics = CapacityMetrics(
            timestamp=datetime.now(timezone.utc),
            cpu_usage=await get_cpu_usage(),
            memory_usage=await get_memory_usage(),
            active_connections=await get_active_connections(),
            request_rate=await get_request_rate(),
            response_time_p95=await get_response_time_p95(),
            error_rate=await get_error_rate(),
            queue_depth=await get_queue_depth(),
            database_connections=await get_database_connections(),
            redis_connections=await get_redis_connections(),
            nats_connections=await get_nats_connections()
        )
        
        current_metrics = metrics
        
        # Store metrics in Redis
        await store_metrics(metrics)
        
    except Exception as e:
        logger.error("Failed to collect metrics", error=str(e))

async def check_thresholds():
    """Check metrics against thresholds and create alerts."""
    if not current_metrics:
        return
    
    thresholds = {
        "cpu_usage": 80.0,
        "memory_usage": 85.0,
        "response_time_p95": 2000.0,
        "error_rate": 5.0,
        "queue_depth": 1000,
        "database_connections": 80,
        "redis_connections": 50,
        "nats_connections": 100
    }
    
    for metric, threshold in thresholds.items():
        value = getattr(current_metrics, metric)
        
        if value > threshold:
            await create_alert(metric, value, threshold)

async def create_alert(metric: str, value: float, threshold: float):
    """Create a capacity alert."""
    alert_id = f"alert_{int(time.time())}_{metric}"
    
    # Check if alert already exists
    existing_alert = next(
        (a for a in active_alerts if a.metric == metric and not a.resolved),
        None
    )
    
    if existing_alert:
        return  # Alert already exists
    
    severity = "high" if value > threshold * 1.5 else "medium"
    
    alert = CapacityAlert(
        alert_id=alert_id,
        timestamp=datetime.now(timezone.utc),
        severity=severity,
        metric=metric,
        value=value,
        threshold=threshold,
        message=f"{metric} exceeded threshold: {value:.2f} > {threshold:.2f}"
    )
    
    active_alerts.append(alert)
    
    logger.warning("Capacity alert created", 
                  alert_id=alert_id,
                  metric=metric,
                  value=value,
                  threshold=threshold)
    
    # Auto-trigger degrade mode for critical alerts
    if severity == "high" and metric in ["cpu_usage", "memory_usage", "error_rate"]:
        await auto_trigger_degrade_mode(alert)

async def auto_trigger_degrade_mode(alert: CapacityAlert):
    """Auto-trigger degrade mode for critical alerts."""
    global degrade_mode
    
    if degrade_mode == DegradeMode.NORMAL:
        degrade_mode = DegradeMode.DEGRADED
        await apply_degrade_configuration(DegradeMode.DEGRADED)
        
        logger.warning("Auto-triggered degrade mode", 
                      alert_id=alert.alert_id,
                      metric=alert.metric)

async def apply_degrade_configuration(mode: DegradeMode):
    """Apply degrade configuration."""
    if not config_manager:
        return
    
    if mode == DegradeMode.DEGRADED:
        config = config_manager.get_degraded_config()
    elif mode == DegradeMode.EMERGENCY:
        config = config_manager.get_emergency_config()
    else:
        config = config_manager.get_config()
    
    # Apply configuration (in real implementation, this would update actual services)
    logger.info("Applied degrade configuration", mode=mode.value)

async def schedule_degrade_recovery(original_mode: DegradeMode, delay_seconds: int):
    """Schedule automatic recovery from degrade mode."""
    await asyncio.sleep(delay_seconds)
    
    global degrade_mode
    degrade_mode = original_mode
    await apply_degrade_configuration(original_mode)
    
    logger.info("Degrade mode recovered", 
               original_mode=original_mode.value)

async def cleanup_old_alerts():
    """Cleanup old resolved alerts."""
    global active_alerts
    
    cutoff_time = datetime.now(timezone.utc).timestamp() - 3600  # 1 hour ago
    
    active_alerts = [
        alert for alert in active_alerts
        if not alert.resolved or alert.timestamp.timestamp() > cutoff_time
    ]

# Metric collection functions (simulated)
async def get_cpu_usage() -> float:
    """Get CPU usage percentage."""
    # Simulate CPU usage based on current load
    import psutil
    return psutil.cpu_percent()

async def get_memory_usage() -> float:
    """Get memory usage percentage."""
    import psutil
    return psutil.virtual_memory().percent

async def get_active_connections() -> int:
    """Get active connection count."""
    if not redis_client:
        return 0
    
    # Get from Redis counter
    count = await redis_client.get("active_connections")
    return int(count) if count else 0

async def get_request_rate() -> float:
    """Get request rate per second."""
    if not redis_client:
        return 0.0
    
    # Get from Redis counter
    rate = await redis_client.get("request_rate")
    return float(rate) if rate else 0.0

async def get_response_time_p95() -> float:
    """Get 95th percentile response time."""
    if not redis_client:
        return 0.0
    
    # Get from Redis
    p95 = await redis_client.get("response_time_p95")
    return float(p95) if p95 else 0.0

async def get_error_rate() -> float:
    """Get error rate percentage."""
    if not redis_client:
        return 0.0
    
    # Get from Redis
    rate = await redis_client.get("error_rate")
    return float(rate) if rate else 0.0

async def get_queue_depth() -> int:
    """Get queue depth."""
    if not redis_client:
        return 0
    
    # Get from Redis
    depth = await redis_client.get("queue_depth")
    return int(depth) if depth else 0

async def get_database_connections() -> int:
    """Get database connection count."""
    if not redis_client:
        return 0
    
    # Get from Redis
    count = await redis_client.get("database_connections")
    return int(count) if count else 0

async def get_redis_connections() -> int:
    """Get Redis connection count."""
    if not redis_client:
        return 0
    
    # Get from Redis
    count = await redis_client.get("redis_connections")
    return int(count) if count else 0

async def get_nats_connections() -> int:
    """Get NATS connection count."""
    if not redis_client:
        return 0
    
    # Get from Redis
    count = await redis_client.get("nats_connections")
    return int(count) if count else 0

async def store_metrics(metrics: CapacityMetrics):
    """Store metrics in Redis."""
    if not redis_client:
        return
    
    # Store current metrics
    await redis_client.setex(
        "current_metrics",
        60,  # 1 minute TTL
        json.dumps(metrics.dict(), default=str)
    )
    
    # Store historical metrics
    timestamp = int(metrics.timestamp.timestamp())
    await redis_client.zadd(
        "metrics_history",
        {json.dumps(metrics.dict(), default=str): timestamp}
    )
    
    # Keep only last 1000 entries
    await redis_client.zremrangebyrank("metrics_history", 0, -1001)

def calculate_capacity_status(metrics: CapacityMetrics) -> str:
    """Calculate overall capacity status."""
    if metrics.cpu_usage > 90 or metrics.memory_usage > 95 or metrics.error_rate > 10:
        return "critical"
    elif metrics.cpu_usage > 80 or metrics.memory_usage > 85 or metrics.error_rate > 5:
        return "warning"
    else:
        return "healthy"

def get_capacity_recommendations(metrics: CapacityMetrics) -> List[str]:
    """Get capacity recommendations based on metrics."""
    recommendations = []
    
    if metrics.cpu_usage > 80:
        recommendations.append("Consider scaling up CPU resources or reducing load")
    
    if metrics.memory_usage > 85:
        recommendations.append("Consider scaling up memory resources or optimizing memory usage")
    
    if metrics.response_time_p95 > 2000:
        recommendations.append("Response times are high, consider optimizing or scaling")
    
    if metrics.error_rate > 5:
        recommendations.append("Error rate is high, investigate and fix issues")
    
    if metrics.queue_depth > 1000:
        recommendations.append("Queue depth is high, consider increasing processing capacity")
    
    if metrics.database_connections > 80:
        recommendations.append("Database connection pool may be exhausted")
    
    return recommendations

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8004)
