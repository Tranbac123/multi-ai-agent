"""Coordinated Cancellation Manager for managing request cancellation across services."""

import asyncio
import uuid
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from enum import Enum
import structlog
from datetime import datetime, timezone

logger = structlog.get_logger(__name__)


class CancellationReason(Enum):
    """Reasons for request cancellation."""
    USER_REQUESTED = "user_requested"
    TIMEOUT = "timeout"
    ERROR = "error"
    CIRCUIT_BREAKER = "circuit_breaker"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    HEDGE_WIN = "hedge_win"
    WORKFLOW_COMPLETED = "workflow_completed"


class CancellationStatus(Enum):
    """Cancellation status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CancellationRequest:
    """Request cancellation data."""
    cancellation_id: str
    request_id: str
    tenant_id: str
    reason: CancellationReason
    initiated_by: str
    initiated_at: datetime
    status: CancellationStatus = CancellationStatus.PENDING
    services_to_cancel: List[str] = None
    cancelled_services: List[str] = None
    error_services: List[str] = None
    metadata: Dict[str, Any] = None


@dataclass
class ServiceCancellation:
    """Service-specific cancellation data."""
    service_name: str
    request_id: str
    cancellation_token: asyncio.CancelledError
    cancelled: bool = False
    cancelled_at: Optional[datetime] = None
    error: Optional[str] = None


class CoordinatedCancellationManager:
    """Manages coordinated cancellation of requests across multiple services."""
    
    def __init__(self):
        self.active_cancellations: Dict[str, CancellationRequest] = {}
        self.service_cancellations: Dict[str, List[ServiceCancellation]] = {}
        self.cancellation_stats = {
            "total_cancellations": 0,
            "successful_cancellations": 0,
            "failed_cancellations": 0,
            "cancellations_by_reason": {},
            "cancellations_by_service": {}
        }
    
    async def initiate_cancellation(self, request_id: str, tenant_id: str,
                                  reason: CancellationReason, initiated_by: str,
                                  services_to_cancel: List[str],
                                  metadata: Optional[Dict[str, Any]] = None) -> str:
        """Initiate coordinated cancellation across services."""
        try:
            cancellation_id = str(uuid.uuid4())
            
            cancellation_request = CancellationRequest(
                cancellation_id=cancellation_id,
                request_id=request_id,
                tenant_id=tenant_id,
                reason=reason,
                initiated_by=initiated_by,
                initiated_at=datetime.now(timezone.utc),
                status=CancellationStatus.PENDING,
                services_to_cancel=services_to_cancel,
                cancelled_services=[],
                error_services=[],
                metadata=metadata or {}
            )
            
            # Store cancellation request
            self.active_cancellations[cancellation_id] = cancellation_request
            
            logger.info("Cancellation initiated",
                       cancellation_id=cancellation_id,
                       request_id=request_id,
                       tenant_id=tenant_id,
                       reason=reason.value,
                       services_count=len(services_to_cancel))
            
            # Start coordinated cancellation
            asyncio.create_task(self._execute_coordinated_cancellation(cancellation_id))
            
            return cancellation_id
            
        except Exception as e:
            logger.error("Failed to initiate cancellation",
                        request_id=request_id,
                        tenant_id=tenant_id,
                        error=str(e))
            raise
    
    async def _execute_coordinated_cancellation(self, cancellation_id: str):
        """Execute coordinated cancellation across all services."""
        try:
            cancellation_request = self.active_cancellations.get(cancellation_id)
            if not cancellation_request:
                logger.error("Cancellation request not found", cancellation_id=cancellation_id)
                return
            
            # Update status
            cancellation_request.status = CancellationStatus.IN_PROGRESS
            
            logger.info("Starting coordinated cancellation",
                       cancellation_id=cancellation_id,
                       services_to_cancel=cancellation_request.services_to_cancel)
            
            # Create cancellation tasks for each service
            cancellation_tasks = []
            for service_name in cancellation_request.services_to_cancel:
                task = asyncio.create_task(
                    self._cancel_service_request(
                        service_name,
                        cancellation_request.request_id,
                        cancellation_id
                    )
                )
                cancellation_tasks.append(task)
            
            # Wait for all cancellations to complete
            if cancellation_tasks:
                results = await asyncio.gather(*cancellation_tasks, return_exceptions=True)
                
                # Process results
                for i, result in enumerate(results):
                    service_name = cancellation_request.services_to_cancel[i]
                    
                    if isinstance(result, Exception):
                        cancellation_request.error_services.append(service_name)
                        logger.error("Service cancellation failed",
                                   cancellation_id=cancellation_id,
                                   service_name=service_name,
                                   error=str(result))
                    else:
                        cancellation_request.cancelled_services.append(service_name)
                        logger.info("Service cancelled successfully",
                                  cancellation_id=cancellation_id,
                                  service_name=service_name)
            
            # Update final status
            if cancellation_request.error_services:
                if cancellation_request.cancelled_services:
                    cancellation_request.status = CancellationStatus.COMPLETED  # Partial success
                else:
                    cancellation_request.status = CancellationStatus.FAILED
            else:
                cancellation_request.status = CancellationStatus.COMPLETED
            
            # Update statistics
            self._update_cancellation_stats(cancellation_request)
            
            logger.info("Coordinated cancellation completed",
                       cancellation_id=cancellation_id,
                       status=cancellation_request.status.value,
                       cancelled_services=len(cancellation_request.cancelled_services),
                       error_services=len(cancellation_request.error_services))
            
        except Exception as e:
            logger.error("Coordinated cancellation failed",
                        cancellation_id=cancellation_id,
                        error=str(e))
            
            if cancellation_id in self.active_cancellations:
                self.active_cancellations[cancellation_id].status = CancellationStatus.FAILED
    
    async def _cancel_service_request(self, service_name: str, request_id: str,
                                    cancellation_id: str) -> bool:
        """Cancel request in a specific service."""
        try:
            logger.info("Cancelling service request",
                       service_name=service_name,
                       request_id=request_id,
                       cancellation_id=cancellation_id)
            
            # Create cancellation token
            cancellation_token = asyncio.CancelledError()
            
            # Store service cancellation
            service_cancellation = ServiceCancellation(
                service_name=service_name,
                request_id=request_id,
                cancellation_token=cancellation_token
            )
            
            if service_name not in self.service_cancellations:
                self.service_cancellations[service_name] = []
            self.service_cancellations[service_name].append(service_cancellation)
            
            # In production, this would send cancellation signal to the service
            # For now, we'll simulate the cancellation
            await self._send_cancellation_signal(service_name, request_id, cancellation_id)
            
            # Mark as cancelled
            service_cancellation.cancelled = True
            service_cancellation.cancelled_at = datetime.now(timezone.utc)
            
            return True
            
        except Exception as e:
            logger.error("Failed to cancel service request",
                        service_name=service_name,
                        request_id=request_id,
                        error=str(e))
            
            # Mark as error
            if service_name in self.service_cancellations:
                for sc in self.service_cancellations[service_name]:
                    if sc.request_id == request_id:
                        sc.error = str(e)
                        break
            
            return False
    
    async def _send_cancellation_signal(self, service_name: str, request_id: str,
                                      cancellation_id: str):
        """Send cancellation signal to service."""
        try:
            # In production, this would:
            # 1. Send HTTP request to service's cancellation endpoint
            # 2. Send message via NATS
            # 3. Update service's internal cancellation registry
            
            logger.info("Sending cancellation signal",
                       service_name=service_name,
                       request_id=request_id,
                       cancellation_id=cancellation_id)
            
            # Simulate network delay
            await asyncio.sleep(0.1)
            
            # Simulate success/failure based on service type
            if service_name in ["llm_service", "vector_service"]:
                # These services might take longer to cancel
                await asyncio.sleep(0.2)
            
        except Exception as e:
            logger.error("Failed to send cancellation signal",
                        service_name=service_name,
                        request_id=request_id,
                        error=str(e))
            raise
    
    async def get_cancellation_status(self, cancellation_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a cancellation request."""
        try:
            cancellation_request = self.active_cancellations.get(cancellation_id)
            if not cancellation_request:
                return None
            
            return {
                "cancellation_id": cancellation_id,
                "request_id": cancellation_request.request_id,
                "tenant_id": cancellation_request.tenant_id,
                "reason": cancellation_request.reason.value,
                "status": cancellation_request.status.value,
                "initiated_by": cancellation_request.initiated_by,
                "initiated_at": cancellation_request.initiated_at.isoformat(),
                "services_to_cancel": cancellation_request.services_to_cancel,
                "cancelled_services": cancellation_request.cancelled_services,
                "error_services": cancellation_request.error_services,
                "success_rate": (
                    len(cancellation_request.cancelled_services) / 
                    len(cancellation_request.services_to_cancel) * 100
                ) if cancellation_request.services_to_cancel else 0,
                "metadata": cancellation_request.metadata
            }
            
        except Exception as e:
            logger.error("Failed to get cancellation status",
                        cancellation_id=cancellation_id,
                        error=str(e))
            return None
    
    async def cancel_request_by_id(self, request_id: str, tenant_id: str,
                                 reason: CancellationReason = CancellationReason.USER_REQUESTED,
                                 initiated_by: str = "system") -> Optional[str]:
        """Cancel request by request ID."""
        try:
            # Find active cancellations for this request
            active_cancellations = [
                c for c in self.active_cancellations.values()
                if c.request_id == request_id and c.tenant_id == tenant_id
            ]
            
            if active_cancellations:
                logger.warning("Request already has active cancellation",
                             request_id=request_id,
                             existing_cancellations=len(active_cancellations))
                return active_cancellations[0].cancellation_id
            
            # Determine services to cancel based on request type
            services_to_cancel = await self._determine_services_to_cancel(request_id, tenant_id)
            
            if not services_to_cancel:
                logger.warning("No services found to cancel",
                             request_id=request_id,
                             tenant_id=tenant_id)
                return None
            
            # Initiate cancellation
            cancellation_id = await self.initiate_cancellation(
                request_id=request_id,
                tenant_id=tenant_id,
                reason=reason,
                initiated_by=initiated_by,
                services_to_cancel=services_to_cancel,
                metadata={"auto_determined_services": True}
            )
            
            return cancellation_id
            
        except Exception as e:
            logger.error("Failed to cancel request by ID",
                        request_id=request_id,
                        tenant_id=tenant_id,
                        error=str(e))
            return None
    
    async def _determine_services_to_cancel(self, request_id: str, tenant_id: str) -> List[str]:
        """Determine which services need to be cancelled for a request."""
        try:
            # In production, this would query the request tracking system
            # to determine which services are currently processing the request
            
            # For now, return common services that might be involved
            common_services = [
                "api_gateway",
                "router_service",
                "llm_service",
                "vector_service",
                "billing_service"
            ]
            
            # Filter based on request type or other criteria
            # This is a simplified implementation
            return common_services
            
        except Exception as e:
            logger.error("Failed to determine services to cancel",
                        request_id=request_id,
                        error=str(e))
            return []
    
    def _update_cancellation_stats(self, cancellation_request: CancellationRequest):
        """Update cancellation statistics."""
        try:
            self.cancellation_stats["total_cancellations"] += 1
            
            if cancellation_request.status == CancellationStatus.COMPLETED:
                self.cancellation_stats["successful_cancellations"] += 1
            elif cancellation_request.status == CancellationStatus.FAILED:
                self.cancellation_stats["failed_cancellations"] += 1
            
            # Count by reason
            reason = cancellation_request.reason.value
            if reason not in self.cancellation_stats["cancellations_by_reason"]:
                self.cancellation_stats["cancellations_by_reason"][reason] = 0
            self.cancellation_stats["cancellations_by_reason"][reason] += 1
            
            # Count by service
            for service_name in cancellation_request.cancelled_services:
                if service_name not in self.cancellation_stats["cancellations_by_service"]:
                    self.cancellation_stats["cancellations_by_service"][service_name] = 0
                self.cancellation_stats["cancellations_by_service"][service_name] += 1
            
        except Exception as e:
            logger.error("Failed to update cancellation stats", error=str(e))
    
    def get_cancellation_stats(self) -> Dict[str, Any]:
        """Get cancellation statistics."""
        try:
            total = self.cancellation_stats["total_cancellations"]
            
            stats = {
                "total_cancellations": total,
                "successful_cancellations": self.cancellation_stats["successful_cancellations"],
                "failed_cancellations": self.cancellation_stats["failed_cancellations"],
                "success_rate": (
                    self.cancellation_stats["successful_cancellations"] / total * 100
                ) if total > 0 else 0,
                "cancellations_by_reason": self.cancellation_stats["cancellations_by_reason"].copy(),
                "cancellations_by_service": self.cancellation_stats["cancellations_by_service"].copy(),
                "active_cancellations": len(self.active_cancellations)
            }
            
            return stats
            
        except Exception as e:
            logger.error("Failed to get cancellation stats", error=str(e))
            return {}
    
    async def cleanup_completed_cancellations(self, max_age_hours: int = 24):
        """Clean up completed cancellation requests."""
        try:
            current_time = datetime.now(timezone.utc)
            max_age = timedelta(hours=max_age_hours)
            
            completed_cancellations = [
                cid for cid, req in self.active_cancellations.items()
                if req.status in [CancellationStatus.COMPLETED, CancellationStatus.FAILED]
                and current_time - req.initiated_at > max_age
            ]
            
            # Remove completed cancellations
            for cancellation_id in completed_cancellations:
                del self.active_cancellations[cancellation_id]
            
            if completed_cancellations:
                logger.info("Cleaned up completed cancellations",
                           count=len(completed_cancellations))
            
        except Exception as e:
            logger.error("Failed to cleanup completed cancellations", error=str(e))
    
    async def cancel_all_tenant_requests(self, tenant_id: str,
                                       reason: CancellationReason = CancellationReason.RESOURCE_EXHAUSTED,
                                       initiated_by: str = "system") -> List[str]:
        """Cancel all active requests for a tenant."""
        try:
            # Find all active cancellations for tenant
            tenant_cancellations = [
                c for c in self.active_cancellations.values()
                if c.tenant_id == tenant_id
            ]
            
            if not tenant_cancellations:
                logger.info("No active cancellations found for tenant", tenant_id=tenant_id)
                return []
            
            # Cancel each request
            cancellation_ids = []
            for cancellation in tenant_cancellations:
                if cancellation.status == CancellationStatus.PENDING:
                    # Update reason and reinitiate
                    cancellation.reason = reason
                    cancellation.initiated_by = initiated_by
                    
                    # Restart cancellation process
                    asyncio.create_task(self._execute_coordinated_cancellation(cancellation.cancellation_id))
                    cancellation_ids.append(cancellation.cancellation_id)
            
            logger.info("Cancelled all tenant requests",
                       tenant_id=tenant_id,
                       cancellation_count=len(cancellation_ids))
            
            return cancellation_ids
            
        except Exception as e:
            logger.error("Failed to cancel all tenant requests",
                        tenant_id=tenant_id,
                        error=str(e))
            return []
