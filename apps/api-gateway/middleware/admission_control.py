"""Admission Control Middleware for pre-request validation."""

from typing import Optional
import structlog
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
import time

from apps.api_gateway.core.concurrency_manager import ConcurrencyManager
from apps.api-gateway.core.fair_scheduler import WeightedFairScheduler, RequestPriority
from libs.clients.quota_enforcer import QuotaEnforcer
from libs.clients.billing import BillingClient
from libs.utils.auth import get_tenant_from_jwt

logger = structlog.get_logger(__name__)


class AdmissionControlMiddleware:
    """Middleware for pre-admission checks and request validation."""
    
    def __init__(self, concurrency_manager: ConcurrencyManager, 
                 fair_scheduler: WeightedFairScheduler,
                 quota_enforcer: QuotaEnforcer,
                 billing_client: BillingClient):
        self.concurrency_manager = concurrency_manager
        self.fair_scheduler = fair_scheduler
        self.quota_enforcer = quota_enforcer
        self.billing_client = billing_client
        self.admission_stats = {
            "total_requests": 0,
            "admitted_requests": 0,
            "rejected_requests": 0,
            "rejection_reasons": {}
        }
    
    async def __call__(self, request: Request, call_next) -> Response:
        """Process request with admission control."""
        start_time = time.time()
        
        try:
            self.admission_stats["total_requests"] += 1
            
            # Extract tenant information
            tenant_id = await self._extract_tenant_id(request)
            if not tenant_id:
                # Allow public endpoints without admission control
                response = await call_next(request)
                return self._add_admission_headers(response, True, "public")
            
            # Perform admission checks
            admission_result = await self._check_admission(request, tenant_id)
            
            if not admission_result["admitted"]:
                # Request rejected
                self.admission_stats["rejected_requests"] += 1
                reason = admission_result["reason"]
                self.admission_stats["rejection_reasons"][reason] = \
                    self.admission_stats["rejection_reasons"].get(reason, 0) + 1
                
                return self._create_rejection_response(reason, admission_result.get("details"))
            
            # Request admitted
            self.admission_stats["admitted_requests"] += 1
            
            # Schedule request if needed
            if admission_result.get("queued"):
                await self._queue_request(request, tenant_id, admission_result)
            
            # Continue with request processing
            response = await call_next(request)
            
            # Release resources after processing
            await self._release_resources(tenant_id, request)
            
            processing_time = time.time() - start_time
            return self._add_admission_headers(response, True, "admitted", processing_time)
            
        except Exception as e:
            logger.error("Admission control error",
                        error=str(e),
                        path=request.url.path,
                        method=request.method)
            
            # Continue with request even if admission control fails
            response = await call_next(request)
            return self._add_admission_headers(response, False, "error")
    
    async def _extract_tenant_id(self, request: Request) -> Optional[str]:
        """Extract tenant ID from request."""
        try:
            tenant_id = await get_tenant_from_jwt(request)
            return tenant_id
        except Exception as e:
            logger.debug("Could not extract tenant from JWT", error=str(e))
            return None
    
    async def _check_admission(self, request: Request, tenant_id: str) -> dict:
        """Perform comprehensive admission checks."""
        try:
            # 1. Check concurrency limits
            concurrency_check = await self._check_concurrency_limits(tenant_id)
            if not concurrency_check["passed"]:
                return {
                    "admitted": False,
                    "reason": "concurrency_limit_exceeded",
                    "details": concurrency_check["details"]
                }
            
            # 2. Check quota limits
            quota_check = await self._check_quota_limits(tenant_id, request)
            if not quota_check["passed"]:
                return {
                    "admitted": False,
                    "reason": "quota_exceeded",
                    "details": quota_check["details"]
                }
            
            # 3. Check budget limits
            budget_check = await self._check_budget_limits(tenant_id, request)
            if not budget_check["passed"]:
                return {
                    "admitted": False,
                    "reason": "budget_exceeded",
                    "details": budget_check["details"]
                }
            
            # 4. Check system load
            load_check = await self._check_system_load()
            if not load_check["passed"]:
                return {
                    "admitted": False,
                    "reason": "system_overloaded",
                    "details": load_check["details"]
                }
            
            # All checks passed
            return {
                "admitted": True,
                "reason": "admitted",
                "concurrency_token": concurrency_check.get("token_id")
            }
            
        except Exception as e:
            logger.error("Error in admission checks", tenant_id=tenant_id, error=str(e))
            return {
                "admitted": True,  # Fail open
                "reason": "admission_check_error"
            }
    
    async def _check_concurrency_limits(self, tenant_id: str) -> dict:
        """Check tenant's concurrency limits."""
        try:
            # Get tenant plan (this would typically come from database)
            plan = "free"  # Default plan
            
            # Try to acquire concurrency token
            token_acquired = await self.concurrency_manager.acquire_token(tenant_id, plan)
            
            if not token_acquired:
                # Check if we can queue the request
                tenant_stats = await self.concurrency_manager.get_tenant_stats(tenant_id)
                limits = await self.concurrency_manager.get_tenant_limits(tenant_id, plan)
                
                if tenant_stats["queue_depth"] >= limits.max_queue_depth:
                    return {
                        "passed": False,
                        "details": f"Queue depth exceeded: {tenant_stats['queue_depth']}/{limits.max_queue_depth}"
                    }
                
                return {
                    "passed": False,
                    "queued": True,
                    "details": f"Concurrency limit exceeded, queuing request"
                }
            
            return {
                "passed": True,
                "token_id": f"{tenant_id}:{int(time.time() * 1000000)}"
            }
            
        except Exception as e:
            logger.error("Error checking concurrency limits", tenant_id=tenant_id, error=str(e))
            return {"passed": True}  # Fail open
    
    async def _check_quota_limits(self, tenant_id: str, request: Request) -> dict:
        """Check tenant's quota limits."""
        try:
            # Check quota enforcement
            quota_check = await self.quota_enforcer.check_quota(tenant_id, request)
            
            if not quota_check.get("allowed", True):
                return {
                    "passed": False,
                    "details": f"Quota exceeded: {quota_check.get('reason', 'Unknown')}"
                }
            
            return {"passed": True}
            
        except Exception as e:
            logger.error("Error checking quota limits", tenant_id=tenant_id, error=str(e))
            return {"passed": True}  # Fail open
    
    async def _check_budget_limits(self, tenant_id: str, request: Request) -> dict:
        """Check tenant's budget limits."""
        try:
            # Check budget limits
            budget_check = await self.billing_client.check_budget_limits(tenant_id, request)
            
            if not budget_check.get("allowed", True):
                return {
                    "passed": False,
                    "details": f"Budget exceeded: {budget_check.get('reason', 'Unknown')}"
                }
            
            return {"passed": True}
            
        except Exception as e:
            logger.error("Error checking budget limits", tenant_id=tenant_id, error=str(e))
            return {"passed": True}  # Fail open
    
    async def _check_system_load(self) -> dict:
        """Check overall system load."""
        try:
            # Get system-wide concurrency stats
            system_stats = await self.concurrency_manager.get_system_stats()
            scheduler_stats = await self.fair_scheduler.get_system_stats()
            
            # Check if system is overloaded
            total_active_requests = system_stats.get("total_active_tokens", 0)
            total_queued_requests = scheduler_stats.get("total_queued_requests", 0)
            
            # Simple overload detection
            if total_active_requests > 1000 or total_queued_requests > 5000:
                return {
                    "passed": False,
                    "details": f"System overloaded: {total_active_requests} active, {total_queued_requests} queued"
                }
            
            return {"passed": True}
            
        except Exception as e:
            logger.error("Error checking system load", error=str(e))
            return {"passed": True}  # Fail open
    
    async def _queue_request(self, request: Request, tenant_id: str, admission_result: dict):
        """Queue request for later processing."""
        try:
            # Determine request priority
            priority = self._determine_request_priority(request)
            
            # Schedule request
            queued = await self.fair_scheduler.schedule_request(
                tenant_id=tenant_id,
                request_data=request,
                priority=priority,
                plan="free"  # This would come from tenant config
            )
            
            if queued:
                logger.info("Request queued for processing",
                           tenant_id=tenant_id,
                           priority=priority.name)
            else:
                logger.warning("Failed to queue request",
                             tenant_id=tenant_id)
                
        except Exception as e:
            logger.error("Error queueing request", tenant_id=tenant_id, error=str(e))
    
    def _determine_request_priority(self, request: Request) -> RequestPriority:
        """Determine request priority based on various factors."""
        try:
            # Check for priority headers
            priority_header = request.headers.get("X-Request-Priority", "").lower()
            
            if priority_header == "critical":
                return RequestPriority.CRITICAL
            elif priority_header == "high":
                return RequestPriority.HIGH
            elif priority_header == "low":
                return RequestPriority.LOW
            else:
                return RequestPriority.NORMAL
                
        except Exception as e:
            logger.error("Error determining request priority", error=str(e))
            return RequestPriority.NORMAL
    
    async def _release_resources(self, tenant_id: str, request: Request):
        """Release resources after request processing."""
        try:
            # Release concurrency token
            await self.concurrency_manager.release_token(tenant_id)
            
            # Update quota usage
            await self.quota_enforcer.update_usage(tenant_id, request)
            
            # Update billing usage
            await self.billing_client.update_usage(tenant_id, request)
            
        except Exception as e:
            logger.error("Error releasing resources", tenant_id=tenant_id, error=str(e))
    
    def _create_rejection_response(self, reason: str, details: Optional[str] = None) -> JSONResponse:
        """Create rejection response with appropriate status code."""
        status_code_map = {
            "concurrency_limit_exceeded": status.HTTP_429_TOO_MANY_REQUESTS,
            "quota_exceeded": status.HTTP_429_TOO_MANY_REQUESTS,
            "budget_exceeded": status.HTTP_402_PAYMENT_REQUIRED,
            "system_overloaded": status.HTTP_503_SERVICE_UNAVAILABLE
        }
        
        status_code = status_code_map.get(reason, status.HTTP_429_TOO_MANY_REQUESTS)
        
        response_data = {
            "error": reason.replace("_", " ").title(),
            "reason": reason
        }
        
        if details:
            response_data["details"] = details
        
        return JSONResponse(
            status_code=status_code,
            content=response_data
        )
    
    def _add_admission_headers(self, response: Response, admitted: bool, 
                             reason: str, processing_time: Optional[float] = None) -> Response:
        """Add admission control headers to response."""
        try:
            response.headers["X-Admission-Status"] = "admitted" if admitted else "rejected"
            response.headers["X-Admission-Reason"] = reason
            
            if processing_time:
                response.headers["X-Processing-Time"] = str(round(processing_time * 1000, 2))
            
            return response
            
        except Exception as e:
            logger.error("Error adding admission headers", error=str(e))
            return response
    
    def get_admission_stats(self) -> dict:
        """Get admission control statistics."""
        try:
            total = self.admission_stats["total_requests"]
            admitted = self.admission_stats["admitted_requests"]
            rejected = self.admission_stats["rejected_requests"]
            
            stats = {
                "total_requests": total,
                "admitted_requests": admitted,
                "rejected_requests": rejected,
                "admission_rate": (admitted / total * 100) if total > 0 else 0,
                "rejection_reasons": self.admission_stats["rejection_reasons"].copy()
            }
            
            return stats
            
        except Exception as e:
            logger.error("Error getting admission stats", error=str(e))
            return {}
