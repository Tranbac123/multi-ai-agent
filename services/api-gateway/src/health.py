"""
Health check endpoints for API Gateway service
"""

import asyncio
import logging
from typing import Dict, Any, Optional
import httpx
import asyncpg
import redis.asyncio as redis
import nats

logger = logging.getLogger(__name__)


async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint
    Returns service status without external dependencies
    """
    return {
        "status": "healthy",
        "service": "api-gateway",
        "version": "1.0.0",
        "timestamp": "2024-01-15T10:30:00Z"
    }


async def readiness_check(app_state) -> Dict[str, Any]:
    """
    Readiness check endpoint
    Verifies that all external dependencies are available
    """
    checks = {
        "database": False,
        "redis": False,
        "nats": False,
        "service_registry": False
    }
    
    # Check database
    try:
        settings = app_state.settings
        conn = await asyncpg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
            timeout=5
        )
        await conn.execute("SELECT 1")
        await conn.close()
        checks["database"] = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
    
    # Check Redis
    try:
        settings = app_state.settings
        r = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            socket_timeout=5
        )
        await r.ping()
        await r.close()
        checks["redis"] = True
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
    
    # Check NATS
    try:
        settings = app_state.settings
        nc = await nats.connect(
            servers=[f"nats://{settings.nats_host}:{settings.nats_port}"],
            connect_timeout=5
        )
        await nc.close()
        checks["nats"] = True
    except Exception as e:
        logger.error(f"NATS health check failed: {e}")
    
    # Check service registry
    try:
        settings = app_state.settings
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{settings.service_registry_url}/healthz")
            if response.status_code == 200:
                checks["service_registry"] = True
    except Exception as e:
        logger.error(f"Service registry health check failed: {e}")
    
    # Determine overall status
    all_healthy = all(checks.values())
    status = "ready" if all_healthy else "not_ready"
    
    return {
        "status": status,
        "service": "api-gateway",
        "version": "1.0.0",
        "timestamp": "2024-01-15T10:30:00Z",
        "checks": checks
    }
