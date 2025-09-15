"""Billing middleware for API Gateway."""

import asyncio
import time
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import structlog
import redis.asyncio as redis
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse

from apps.billing_service.core.usage_tracker import UsageTracker, UsageType
from apps.billing_service.core.webhook_aggregator import WebhookAggregator

logger = structlog.get_logger(__name__)


class BillingAction(Enum):
    """Billing actions."""
    ALLOW = "allow"
    BLOCK = "block"
    THROTTLE = "throttle"
    WARN = "warn"


@dataclass
class BillingDecision:
    """Billing decision."""
    action: BillingAction
    status_code: int
    message: str
    usage_data: Dict[str, Any]
    metadata: Dict[str, Any] = None


@dataclass
class BillingConfig:
    """Billing configuration."""
    enforce_limits: bool = True
    throttle_threshold: float = 0.8  # 80% of limit
    block_threshold: float = 1.0  # 100% of limit
    warn_threshold: float = 0.7  # 70% of limit
    rate_limit_window: int = 60  # 1 minute
    rate_limit_requests: int = 100  # 100 requests per minute


class BillingMiddleware:
    """Billing middleware for API Gateway."""

    def __init__(
        self,
        redis_client: redis.Redis,
        usage_tracker: UsageTracker,
        webhook_aggregator: WebhookAggregator,
        config: BillingConfig = None
    ):
        self.redis = redis_client
        self.usage_tracker = usage_tracker
        self.webhook_aggregator = webhook_aggregator
        self.config = config or BillingConfig()
        self.rate_limit_cache = {}

    async def __call__(self, request: Request, call_next) -> Response:
        """Process request through billing middleware."""
        try:
            # Extract tenant information
            tenant_id = await self._extract_tenant_id(request)
            if not tenant_id:
                # If no tenant ID, allow request to proceed
                return await call_next(request)

            # Check billing limits
            billing_decision = await self._check_billing_limits(request, tenant_id)
            
            if billing_decision.action == BillingAction.BLOCK:
                return JSONResponse(
                    status_code=billing_decision.status_code,
                    content={
                        "error": "Usage limit exceeded",
                        "message": billing_decision.message,
                        "usage_data": billing_decision.usage_data
                    }
                )
            
            elif billing_decision.action == BillingAction.THROTTLE:
                # Add delay to throttle request
                await asyncio.sleep(0.1)
            
            elif billing_decision.action == BillingAction.WARN:
                # Log warning but allow request
                logger.warning(
                    "Usage approaching limit",
                    tenant_id=tenant_id,
                    usage_data=billing_decision.usage_data
                )

            # Process request
            response = await call_next(request)

            # Record usage after successful request
            if response.status_code < 400:
                await self._record_usage(request, tenant_id, response)

            return response

        except Exception as e:
            logger.error("Billing middleware error", error=str(e))
            # On error, allow request to proceed
            return await call_next(request)

    async def _extract_tenant_id(self, request: Request) -> Optional[str]:
        """Extract tenant ID from request."""
        try:
            # Try to get tenant ID from headers
            tenant_id = request.headers.get("X-Tenant-ID")
            if tenant_id:
                return tenant_id

            # Try to get tenant ID from query parameters
            tenant_id = request.query_params.get("tenant_id")
            if tenant_id:
                return tenant_id

            # Try to get tenant ID from path parameters
            if hasattr(request, "path_params") and "tenant_id" in request.path_params:
                return request.path_params["tenant_id"]

            # Try to get tenant ID from JWT token (if available)
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                # In a real implementation, you would decode the JWT token
                # For now, we'll return None
                pass

            return None

        except Exception as e:
            logger.error("Failed to extract tenant ID", error=str(e))
            return None

    async def _check_billing_limits(self, request: Request, tenant_id: str) -> BillingDecision:
        """Check billing limits for tenant."""
        try:
            # Determine usage type based on request
            usage_type = await self._determine_usage_type(request)
            if not usage_type:
                return BillingDecision(
                    action=BillingAction.ALLOW,
                    status_code=200,
                    message="No usage tracking required",
                    usage_data={}
                )

            # Check rate limiting
            rate_limit_decision = await self._check_rate_limit(request, tenant_id)
            if rate_limit_decision.action == BillingAction.BLOCK:
                return rate_limit_decision

            # Check usage limits
            usage_limit_decision = await self._check_usage_limits(tenant_id, usage_type)
            if usage_limit_decision.action == BillingAction.BLOCK:
                return usage_limit_decision

            # Return the most restrictive decision
            if rate_limit_decision.action == BillingAction.THROTTLE:
                return rate_limit_decision
            elif usage_limit_decision.action == BillingAction.THROTTLE:
                return usage_limit_decision
            elif usage_limit_decision.action == BillingAction.WARN:
                return usage_limit_decision

            return BillingDecision(
                action=BillingAction.ALLOW,
                status_code=200,
                message="Usage within limits",
                usage_data=usage_limit_decision.usage_data
            )

        except Exception as e:
            logger.error("Failed to check billing limits", error=str(e))
            return BillingDecision(
                action=BillingAction.ALLOW,
                status_code=200,
                message="Error checking limits, allowing request",
                usage_data={}
            )

    async def _determine_usage_type(self, request: Request) -> Optional[UsageType]:
        """Determine usage type based on request."""
        try:
            path = request.url.path
            method = request.method

            # API calls
            if path.startswith("/api/"):
                return UsageType.API_CALLS

            # WebSocket connections
            if path.startswith("/ws/"):
                return UsageType.WS_MINUTES

            # Tool calls
            if path.startswith("/tools/"):
                return UsageType.TOOL_CALLS

            # Storage operations
            if path.startswith("/storage/"):
                return UsageType.STORAGE_MB

            # Chat/completion endpoints (tokens)
            if path.startswith("/chat/") or path.startswith("/completion/"):
                return UsageType.TOKENS_IN

            return None

        except Exception as e:
            logger.error("Failed to determine usage type", error=str(e))
            return None

    async def _check_rate_limit(self, request: Request, tenant_id: str) -> BillingDecision:
        """Check rate limiting for tenant."""
        try:
            if not self.config.enforce_limits:
                return BillingDecision(
                    action=BillingAction.ALLOW,
                    status_code=200,
                    message="Rate limiting disabled",
                    usage_data={}
                )

            # Get current time window
            current_window = int(time.time() // self.config.rate_limit_window)
            rate_key = f"rate_limit:{tenant_id}:{current_window}"

            # Get current request count
            current_count = await self.redis.get(rate_key)
            current_count = int(current_count) if current_count else 0

            # Check if limit would be exceeded
            if current_count >= self.config.rate_limit_requests:
                return BillingDecision(
                    action=BillingAction.BLOCK,
                    status_code=429,
                    message="Rate limit exceeded",
                    usage_data={
                        "current_requests": current_count,
                        "rate_limit": self.config.rate_limit_requests,
                        "window_seconds": self.config.rate_limit_window
                    }
                )

            # Increment counter
            await self.redis.incr(rate_key)
            await self.redis.expire(rate_key, self.config.rate_limit_window)

            return BillingDecision(
                action=BillingAction.ALLOW,
                status_code=200,
                message="Rate limit OK",
                usage_data={
                    "current_requests": current_count + 1,
                    "rate_limit": self.config.rate_limit_requests,
                    "window_seconds": self.config.rate_limit_window
                }
            )

        except Exception as e:
            logger.error("Failed to check rate limit", error=str(e))
            return BillingDecision(
                action=BillingAction.ALLOW,
                status_code=200,
                message="Rate limit check failed, allowing request",
                usage_data={}
            )

    async def _check_usage_limits(self, tenant_id: str, usage_type: UsageType) -> BillingDecision:
        """Check usage limits for tenant."""
        try:
            if not self.config.enforce_limits:
                return BillingDecision(
                    action=BillingAction.ALLOW,
                    status_code=200,
                    message="Usage limits disabled",
                    usage_data={}
                )

            # Get current usage
            current_usage = await self.usage_tracker._get_current_usage(tenant_id, usage_type)

            # Get usage limit
            limit_key = f"usage_limit:{tenant_id}:{usage_type.value}"
            usage_limit = self.usage_tracker.usage_limits.get(limit_key)

            if not usage_limit:
                return BillingDecision(
                    action=BillingAction.ALLOW,
                    status_code=200,
                    message="No usage limit set",
                    usage_data={
                        "current_usage": current_usage,
                        "usage_limit": None
                    }
                )

            # Calculate usage percentage
            usage_percentage = current_usage / usage_limit.limit if usage_limit.limit > 0 else 0

            # Determine action based on thresholds
            if usage_percentage >= self.config.block_threshold:
                return BillingDecision(
                    action=BillingAction.BLOCK,
                    status_code=429,
                    message="Usage limit exceeded",
                    usage_data={
                        "current_usage": current_usage,
                        "usage_limit": usage_limit.limit,
                        "usage_percentage": usage_percentage,
                        "usage_type": usage_type.value
                    }
                )
            elif usage_percentage >= self.config.throttle_threshold:
                return BillingDecision(
                    action=BillingAction.THROTTLE,
                    status_code=200,
                    message="Usage approaching limit, throttling",
                    usage_data={
                        "current_usage": current_usage,
                        "usage_limit": usage_limit.limit,
                        "usage_percentage": usage_percentage,
                        "usage_type": usage_type.value
                    }
                )
            elif usage_percentage >= self.config.warn_threshold:
                return BillingDecision(
                    action=BillingAction.WARN,
                    status_code=200,
                    message="Usage approaching limit, warning",
                    usage_data={
                        "current_usage": current_usage,
                        "usage_limit": usage_limit.limit,
                        "usage_percentage": usage_percentage,
                        "usage_type": usage_type.value
                    }
                )

            return BillingDecision(
                action=BillingAction.ALLOW,
                status_code=200,
                message="Usage within limits",
                usage_data={
                    "current_usage": current_usage,
                    "usage_limit": usage_limit.limit,
                    "usage_percentage": usage_percentage,
                    "usage_type": usage_type.value
                }
            )

        except Exception as e:
            logger.error("Failed to check usage limits", error=str(e))
            return BillingDecision(
                action=BillingAction.ALLOW,
                status_code=200,
                message="Usage limit check failed, allowing request",
                usage_data={}
            )

    async def _record_usage(self, request: Request, tenant_id: str, response: Response) -> None:
        """Record usage after successful request."""
        try:
            # Determine usage type
            usage_type = await self._determine_usage_type(request)
            if not usage_type:
                return

            # Calculate usage quantity
            quantity = await self._calculate_usage_quantity(request, response, usage_type)
            if quantity <= 0:
                return

            # Record usage
            await self.usage_tracker.record_usage(
                tenant_id=tenant_id,
                usage_type=usage_type,
                quantity=quantity,
                metadata={
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": response.status_code,
                    "user_agent": request.headers.get("User-Agent", ""),
                    "ip_address": request.client.host if request.client else None
                }
            )

            # Send webhook event
            webhook_data = {
                "event_type": "usage_recorded",
                "tenant_id": tenant_id,
                "data": {
                    "usage_type": usage_type.value,
                    "quantity": quantity,
                    "metadata": {
                        "path": request.url.path,
                        "method": request.method,
                        "status_code": response.status_code
                    }
                }
            }

            await self.webhook_aggregator.process_webhook(webhook_data)

        except Exception as e:
            logger.error("Failed to record usage", error=str(e))

    async def _calculate_usage_quantity(self, request: Request, response: Response, usage_type: UsageType) -> float:
        """Calculate usage quantity based on request and response."""
        try:
            if usage_type == UsageType.API_CALLS:
                return 1.0

            elif usage_type == UsageType.TOKENS_IN:
                # Try to get token count from response headers
                token_count = response.headers.get("X-Token-Count")
                if token_count:
                    return float(token_count)
                
                # Estimate based on content length
                content_length = response.headers.get("Content-Length")
                if content_length:
                    # Rough estimate: 1 token per 4 characters
                    return float(content_length) / 4.0
                
                return 1.0  # Default to 1 token

            elif usage_type == UsageType.TOKENS_OUT:
                # Try to get token count from response headers
                token_count = response.headers.get("X-Output-Token-Count")
                if token_count:
                    return float(token_count)
                
                # Estimate based on content length
                content_length = response.headers.get("Content-Length")
                if content_length:
                    # Rough estimate: 1 token per 4 characters
                    return float(content_length) / 4.0
                
                return 1.0  # Default to 1 token

            elif usage_type == UsageType.TOOL_CALLS:
                # Try to get tool call count from response headers
                tool_count = response.headers.get("X-Tool-Call-Count")
                if tool_count:
                    return float(tool_count)
                
                return 1.0  # Default to 1 tool call

            elif usage_type == UsageType.WS_MINUTES:
                # For WebSocket connections, we'll need to track connection duration
                # This would typically be handled by a separate WebSocket middleware
                return 1.0  # Default to 1 minute

            elif usage_type == UsageType.STORAGE_MB:
                # Try to get storage size from response headers
                storage_size = response.headers.get("X-Storage-Size")
                if storage_size:
                    # Convert bytes to MB
                    return float(storage_size) / (1024 * 1024)
                
                return 0.0  # Default to 0 MB

            return 1.0  # Default quantity

        except Exception as e:
            logger.error("Failed to calculate usage quantity", error=str(e))
            return 1.0

    async def get_tenant_usage_summary(self, tenant_id: str) -> Dict[str, Any]:
        """Get usage summary for a tenant."""
        try:
            summary = await self.usage_tracker.get_all_usage_summary(tenant_id)
            return summary

        except Exception as e:
            logger.error("Failed to get tenant usage summary", error=str(e))
            return {"error": str(e)}

    async def get_tenant_billing_status(self, tenant_id: str) -> Dict[str, Any]:
        """Get billing status for a tenant."""
        try:
            # Get usage summary
            usage_summary = await self.get_tenant_usage_summary(tenant_id)
            
            # Check if any limits are exceeded
            limits_exceeded = []
            warnings = []
            
            for usage_type, usage_data in usage_summary.get("usage_types", {}).items():
                usage_percentage = usage_data.get("usage_percentage", 0)
                
                if usage_percentage >= self.config.block_threshold:
                    limits_exceeded.append({
                        "usage_type": usage_type,
                        "current_usage": usage_data.get("total_usage", 0),
                        "usage_limit": usage_data.get("usage_limit"),
                        "usage_percentage": usage_percentage
                    })
                elif usage_percentage >= self.config.warn_threshold:
                    warnings.append({
                        "usage_type": usage_type,
                        "current_usage": usage_data.get("total_usage", 0),
                        "usage_limit": usage_data.get("usage_limit"),
                        "usage_percentage": usage_percentage
                    })
            
            return {
                "tenant_id": tenant_id,
                "usage_summary": usage_summary,
                "limits_exceeded": limits_exceeded,
                "warnings": warnings,
                "billing_status": "blocked" if limits_exceeded else "active"
            }

        except Exception as e:
            logger.error("Failed to get tenant billing status", error=str(e))
            return {"error": str(e)}
