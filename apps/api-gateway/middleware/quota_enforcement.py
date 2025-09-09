"""Quota enforcement middleware for API Gateway."""

import asyncio
from typing import Callable, Optional, Dict, Any
from fastapi import Request, HTTPException, Depends
from fastapi.responses import JSONResponse
import structlog

from libs.clients.rate_limiter import QuotaEnforcer
from libs.contracts.error import ErrorResponse, ServiceError
from apps.api_gateway.middleware.tenant_context import get_tenant_id

logger = structlog.get_logger(__name__)


class QuotaEnforcementMiddleware:
    """Middleware for enforcing quotas and rate limits."""
    
    def __init__(self, quota_enforcer: QuotaEnforcer):
        self.quota_enforcer = quota_enforcer
    
    def enforce_quota(
        self,
        plan: str,
        scope: str,
        usage_type: str = "api_calls"
    ):
        """Decorator to enforce quotas on API endpoints."""
        def decorator(func: Callable) -> Callable:
            async def wrapper(request: Request, *args, **kwargs):
                # Get tenant_id from request state
                tenant_id = getattr(request.state, 'tenant_id', None)
                if not tenant_id:
                    raise HTTPException(
                        status_code=401,
                        detail="Tenant context not found"
                    )
                
                # Check quota
                is_allowed, quota_info = await self.quota_enforcer.check_quota(
                    tenant_id, plan, scope, usage_type
                )
                
                if not is_allowed:
                    error_id = str(uuid.uuid4())
                    error = ServiceError(
                        error_id=error_id,
                        error_type="quota_exceeded",
                        error_code="QUOTA_EXCEEDED",
                        message="Quota limit exceeded",
                        details=quota_info,
                        timestamp=time.time(),
                        service="api-gateway",
                        tenant_id=tenant_id
                    )
                    
                    return JSONResponse(
                        status_code=429,
                        content=ErrorResponse(
                            success=False,
                            error=error
                        ).dict()
                    )
                
                # Execute the endpoint
                response = await func(request, *args, **kwargs)
                
                # Increment usage counter
                await self.quota_enforcer.increment_usage(tenant_id, usage_type, 1)
                
                return response
            
            return wrapper
        return decorator
    
    def enforce_rate_limit(
        self,
        plan: str,
        scope: str,
        capacity: int = 1000,
        tokens_per_interval: int = 100,
        interval_seconds: int = 60
    ):
        """Decorator to enforce rate limits on API endpoints."""
        def decorator(func: Callable) -> Callable:
            async def wrapper(request: Request, *args, **kwargs):
                # Get tenant_id from request state
                tenant_id = getattr(request.state, 'tenant_id', None)
                if not tenant_id:
                    raise HTTPException(
                        status_code=401,
                        detail="Tenant context not found"
                    )
                
                # Check rate limit
                is_allowed, remaining_tokens, capacity = await self.quota_enforcer.rate_limiter.is_allowed(
                    tenant_id, plan, scope, capacity, tokens_per_interval, interval_seconds
                )
                
                if not is_allowed:
                    error_id = str(uuid.uuid4())
                    error = ServiceError(
                        error_id=error_id,
                        error_type="rate_limit_exceeded",
                        error_code="RATE_LIMIT_EXCEEDED",
                        message="Rate limit exceeded",
                        details={
                            "remaining_tokens": remaining_tokens,
                            "capacity": capacity,
                            "retry_after": interval_seconds
                        },
                        timestamp=time.time(),
                        service="api-gateway",
                        tenant_id=tenant_id
                    )
                    
                    return JSONResponse(
                        status_code=429,
                        content=ErrorResponse(
                            success=False,
                            error=error
                        ).dict()
                    )
                
                # Execute the endpoint
                response = await func(request, *args, **kwargs)
                
                return response
            
            return wrapper
        return decorator


# Global quota enforcer instance
quota_enforcer: Optional[QuotaEnforcer] = None


def get_quota_enforcer() -> QuotaEnforcer:
    """Get global quota enforcer instance."""
    global quota_enforcer
    if quota_enforcer is None:
        raise RuntimeError("Quota enforcer not initialized")
    return quota_enforcer


def initialize_quota_enforcer(redis_client, db_client):
    """Initialize global quota enforcer."""
    global quota_enforcer
    quota_enforcer = QuotaEnforcer(redis_client, db_client)
    logger.info("Quota enforcer initialized")


# Convenience functions for common quota patterns
def enforce_chat_quota(plan: str = "free"):
    """Enforce chat quota for the given plan."""
    enforcer = get_quota_enforcer()
    return enforcer.enforce_quota(plan, "chat", "api_calls")


def enforce_router_quota(plan: str = "free"):
    """Enforce router quota for the given plan."""
    enforcer = get_quota_enforcer()
    return enforcer.enforce_quota(plan, "router", "api_calls")


def enforce_tool_quota(plan: str = "free"):
    """Enforce tool quota for the given plan."""
    enforcer = get_quota_enforcer()
    return enforcer.enforce_quota(plan, "tools", "tool_calls")


def enforce_websocket_quota(plan: str = "free"):
    """Enforce WebSocket quota for the given plan."""
    enforcer = get_quota_enforcer()
    return enforcer.enforce_quota(plan, "websocket", "ws_minutes")


def enforce_storage_quota(plan: str = "free"):
    """Enforce storage quota for the given plan."""
    enforcer = get_quota_enforcer()
    return enforcer.enforce_quota(plan, "storage", "storage_mb")
