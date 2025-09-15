"""Quota enforcement middleware for API Gateway."""

import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import structlog
import redis.asyncio as redis
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from apps.billing_service.core.usage_tracker import UsageTracker, UsageType

logger = structlog.get_logger(__name__)


class QuotaStatus(Enum):
    """Quota status."""
    WITHIN_LIMITS = "within_limits"
    APPROACHING_LIMIT = "approaching_limit"
    EXCEEDED = "exceeded"
    UNLIMITED = "unlimited"


@dataclass
class QuotaCheck:
    """Quota check result."""
    allowed: bool
    remaining_quota: float
    reset_time: float
    status: QuotaStatus
    message: str


class QuotaEnforcementMiddleware(BaseHTTPMiddleware):
    """Middleware for enforcing quota limits."""
    
    def __init__(self, app, redis_client: redis.Redis, usage_tracker: UsageTracker):
        super().__init__(app)
        self.redis_client = redis_client
        self.usage_tracker = usage_tracker
        
        # Default quota limits
        self.default_quotas = {
            UsageType.TOKENS: 1000000,  # 1M tokens per month
            UsageType.TOOL_CALLS: 10000,  # 10K tool calls per month
            UsageType.WS_CONNECTIONS: 1000,  # 1K minutes per month
            UsageType.STORAGE: 1000,  # 1GB per month
            UsageType.API_CALLS: 100000,  # 100K API calls per month
        }
    
    async def dispatch(self, request: Request, call_next):
        """Process request with quota enforcement."""
        # Skip quota enforcement for certain paths
        if self._should_skip_quota_check(request):
            return await call_next(request)
        
        # Extract tenant ID from request
        tenant_id = await self._extract_tenant_id(request)
        if not tenant_id:
            return await call_next(request)
        
        # Check quotas for the request
        quota_checks = await self._check_quotas(request, tenant_id)
        
        # Check if any quota is exceeded
        exceeded_quotas = [check for check in quota_checks if not check.allowed]
        
        if exceeded_quotas:
            return self._create_quota_exceeded_response(exceeded_quotas)
        
        # Process the request
        response = await call_next(request)
        
        # Record usage after successful request
        if response.status_code < 400:
            await self._record_usage(request, tenant_id, quota_checks)
        
        return response
    
    def _should_skip_quota_check(self, request: Request) -> bool:
        """Check if quota enforcement should be skipped for this request."""
        skip_paths = ["/health", "/metrics", "/docs", "/openapi.json"]
        return any(request.url.path.startswith(path) for path in skip_paths)
    
    async def _extract_tenant_id(self, request: Request) -> Optional[str]:
        """Extract tenant ID from request."""
        return request.headers.get("X-Tenant-ID") or request.query_params.get("tenant_id")
    
    async def _check_quotas(self, request: Request, tenant_id: str) -> List[QuotaCheck]:
        """Check quotas for the request."""
        checks = []
        
        # Check API calls quota
        api_check = await self._check_single_quota(tenant_id, UsageType.API_CALLS, 1.0)
        checks.append(api_check)
        
        # Check tokens quota if it's a chat/completion request
        if "/chat" in request.url.path or "/completion" in request.url.path:
            content_length = int(request.headers.get("content-length", 0))
            estimated_tokens = content_length / 4  # Rough estimate
            token_check = await self._check_single_quota(tenant_id, UsageType.TOKENS, estimated_tokens)
            checks.append(token_check)
        
        return checks
    
    async def _check_single_quota(self, tenant_id: str, usage_type: UsageType, requested_amount: float) -> QuotaCheck:
        """Check a single quota."""
        try:
            current_usage = await self.usage_tracker.get_current_usage(tenant_id, usage_type)
            quota_limit = await self._get_quota_limit(tenant_id, usage_type)
            
            if quota_limit is None:
                return QuotaCheck(
                    allowed=True,
                    remaining_quota=float('inf'),
                    reset_time=0,
                    status=QuotaStatus.UNLIMITED,
                    message="Unlimited quota"
                )
            
            if current_usage + requested_amount > quota_limit:
                return QuotaCheck(
                    allowed=False,
                    remaining_quota=max(0, quota_limit - current_usage),
                    reset_time=self._get_quota_reset_time(),
                    status=QuotaStatus.EXCEEDED,
                    message=f"Quota exceeded for {usage_type.value}"
                )
            
            return QuotaCheck(
                allowed=True,
                remaining_quota=quota_limit - current_usage - requested_amount,
                reset_time=self._get_quota_reset_time(),
                status=QuotaStatus.WITHIN_LIMITS,
                message="Within quota limits"
            )
            
        except Exception as e:
            logger.error("Quota check failed", tenant_id=tenant_id, usage_type=usage_type.value, error=str(e))
            return QuotaCheck(
                allowed=True,
                remaining_quota=0,
                reset_time=0,
                status=QuotaStatus.WITHIN_LIMITS,
                message="Quota check failed, allowing request"
            )
    
    async def _get_quota_limit(self, tenant_id: str, usage_type: UsageType) -> Optional[float]:
        """Get quota limit for tenant and usage type."""
        quota_key = f"quota:{tenant_id}:{usage_type.value}"
        quota_data = await self.redis_client.get(quota_key)
        
        if quota_data:
            return float(quota_data)
        
        return self.default_quotas.get(usage_type)
    
    def _get_quota_reset_time(self) -> float:
        """Get quota reset time as Unix timestamp."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            next_month = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
        
        return next_month.timestamp()
    
    def _create_quota_exceeded_response(self, exceeded_quotas: List[QuotaCheck]) -> JSONResponse:
        """Create quota exceeded response."""
        error_details = []
        for quota in exceeded_quotas:
            error_details.append({
                "message": quota.message,
                "remaining_quota": quota.remaining_quota,
                "reset_time": quota.reset_time
            })
        
        return JSONResponse(
            status_code=429,
            content={
                "error": "Quota Exceeded",
                "message": "Request blocked due to quota limits",
                "details": error_details,
                "retry_after": 3600
            },
            headers={"Retry-After": "3600"}
        )
    
    async def _record_usage(self, request: Request, tenant_id: str, quota_checks: List[QuotaCheck]) -> None:
        """Record usage after successful request."""
        try:
            # Record API call
            await self.usage_tracker.record_usage(
                tenant_id=tenant_id,
                usage_type=UsageType.API_CALLS,
                quantity=1.0,
                metadata={"request_path": request.url.path, "request_method": request.method}
            )
            
            # Record tokens if applicable
            if "/chat" in request.url.path or "/completion" in request.url.path:
                content_length = int(request.headers.get("content-length", 0))
                estimated_tokens = content_length / 4
                if estimated_tokens > 0:
                    await self.usage_tracker.record_usage(
                        tenant_id=tenant_id,
                        usage_type=UsageType.TOKENS,
                        quantity=estimated_tokens,
                        metadata={"request_path": request.url.path}
                    )
        except Exception as e:
            logger.error("Failed to record usage", tenant_id=tenant_id, error=str(e))