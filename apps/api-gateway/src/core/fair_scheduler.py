"""Weighted Fair Scheduler for per-tenant request scheduling."""

from typing import Dict, List, Optional, Deque
from dataclasses import dataclass
from collections import deque
import asyncio
import time
# import heapq
import structlog
from enum import Enum

logger = structlog.get_logger(__name__)


class RequestPriority(Enum):
    """Request priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class ScheduledRequest:
    """Represents a scheduled request with priority and timing."""
    request_id: str
    tenant_id: str
    priority: RequestPriority
    weight: int
    scheduled_time: float
    request_data: any
    deadline: Optional[float] = None


@dataclass
class TenantQueue:
    """Queue for a specific tenant with weight and statistics."""
    tenant_id: str
    plan_weight: int
    queue: Deque[ScheduledRequest]
    last_served_time: float
    tokens_consumed: int
    total_requests: int


class WeightedFairScheduler:
    """Weighted fair scheduler that prevents tenant starvation."""
    
    def __init__(self):
        self.queues: Dict[str, TenantQueue] = {}
        self.weights = {"free": 1, "pro": 3, "enterprise": 10}
        self.max_queue_depth = 1000
        self.scheduling_interval = 0.1  # 100ms
        self._scheduler_task: Optional[asyncio.Task] = None
        self._start_scheduler()
    
    def _start_scheduler(self):
        """Start the background scheduler task."""
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
    
    async def schedule_request(self, tenant_id: str, request_data: any, 
                             priority: RequestPriority = RequestPriority.NORMAL,
                             deadline: Optional[float] = None,
                             plan: str = "free") -> bool:
        """Schedule request with weighted fair queuing."""
        try:
            # Get or create tenant queue
            if tenant_id not in self.queues:
                weight = self.weights.get(plan, 1)
                self.queues[tenant_id] = TenantQueue(
                    tenant_id=tenant_id,
                    plan_weight=weight,
                    queue=deque(),
                    last_served_time=time.time(),
                    tokens_consumed=0,
                    total_requests=0
                )
            
            tenant_queue = self.queues[tenant_id]
            
            # Check queue depth limit
            if len(tenant_queue.queue) >= self.max_queue_depth:
                logger.warning("Tenant queue depth exceeded, dropping request",
                             tenant_id=tenant_id,
                             queue_depth=len(tenant_queue.queue))
                return False
            
            # Create scheduled request
            request_id = f"{tenant_id}:{int(time.time() * 1000000)}"
            scheduled_request = ScheduledRequest(
                request_id=request_id,
                tenant_id=tenant_id,
                priority=priority,
                weight=tenant_queue.plan_weight,
                scheduled_time=time.time(),
                request_data=request_data,
                deadline=deadline
            )
            
            # Add to queue
            tenant_queue.queue.append(scheduled_request)
            tenant_queue.total_requests += 1
            
            logger.info("Request scheduled",
                       tenant_id=tenant_id,
                       request_id=request_id,
                       priority=priority.name,
                       queue_depth=len(tenant_queue.queue))
            
            return True
            
        except Exception as e:
            logger.error("Failed to schedule request",
                        tenant_id=tenant_id,
                        error=str(e))
            return False
    
    async def process_next_request(self) -> Optional[ScheduledRequest]:
        """Process next request based on weighted scheduling."""
        try:
            if not self.queues:
                return None
            
            # Find next tenant to serve using weighted fair queuing
            next_tenant = self._select_next_tenant()
            if not next_tenant:
                return None
            
            tenant_queue = self.queues[next_tenant]
            
            # Get next request from queue
            if not tenant_queue.queue:
                return None
            
            request = tenant_queue.queue.popleft()
            
            # Update tenant statistics
            tenant_queue.last_served_time = time.time()
            tenant_queue.tokens_consumed += request.weight
            
            # Check for deadline violations
            if request.deadline and time.time() > request.deadline:
                logger.warning("Request deadline violated",
                             tenant_id=request.tenant_id,
                             request_id=request.request_id,
                             deadline=request.deadline)
            
            logger.info("Request processed",
                       tenant_id=request.tenant_id,
                       request_id=request.request_id,
                       priority=request.priority.name,
                       weight=request.weight)
            
            return request
            
        except Exception as e:
            logger.error("Failed to process next request", error=str(e))
            return None
    
    def _select_next_tenant(self) -> Optional[str]:
        """Select next tenant to serve using weighted fair queuing algorithm."""
        try:
            current_time = time.time()
            best_tenant = None
            best_score = float('inf')
            
            for tenant_id, tenant_queue in self.queues.items():
                if not tenant_queue.queue:
                    continue
                
                # Calculate fair share score
                # Lower score means higher priority
                time_since_last_served = current_time - tenant_queue.last_served_time
                
                # Weighted fair queuing formula
                # Score = (tokens_consumed / weight) - time_since_last_served
                fair_share_score = (tenant_queue.tokens_consumed / tenant_queue.plan_weight) - time_since_last_served
                
                # Add priority boost for high-priority requests
                next_request = tenant_queue.queue[0]
                priority_boost = next_request.priority.value * 0.1
                fair_share_score -= priority_boost
                
                # Check deadline urgency
                if next_request.deadline:
                    time_to_deadline = next_request.deadline - current_time
                    if time_to_deadline < 1.0:  # Less than 1 second to deadline
                        fair_share_score -= 10.0  # High urgency boost
                
                if fair_share_score < best_score:
                    best_score = fair_share_score
                    best_tenant = tenant_id
            
            return best_tenant
            
        except Exception as e:
            logger.error("Failed to select next tenant", error=str(e))
            return None
    
    async def _scheduler_loop(self):
        """Background scheduler loop."""
        while True:
            try:
                await asyncio.sleep(self.scheduling_interval)
                
                # Process requests
                request = await self.process_next_request()
                if request:
                    # Here we would typically dispatch the request to a worker
                    # For now, we'll just log it
                    logger.debug("Request dispatched from scheduler",
                               tenant_id=request.tenant_id,
                               request_id=request.request_id)
                
            except Exception as e:
                logger.error("Error in scheduler loop", error=str(e))
                await asyncio.sleep(1.0)
    
    async def get_queue_stats(self, tenant_id: str) -> Optional[Dict[str, any]]:
        """Get queue statistics for a specific tenant."""
        try:
            if tenant_id not in self.queues:
                return None
            
            tenant_queue = self.queues[tenant_id]
            current_time = time.time()
            
            return {
                "tenant_id": tenant_id,
                "queue_depth": len(tenant_queue.queue),
                "plan_weight": tenant_queue.plan_weight,
                "tokens_consumed": tenant_queue.tokens_consumed,
                "total_requests": tenant_queue.total_requests,
                "last_served_time": tenant_queue.last_served_time,
                "time_since_last_served": current_time - tenant_queue.last_served_time,
                "fair_share_score": (tenant_queue.tokens_consumed / tenant_queue.plan_weight) - (current_time - tenant_queue.last_served_time)
            }
            
        except Exception as e:
            logger.error("Failed to get queue stats", tenant_id=tenant_id, error=str(e))
            return None
    
    async def get_system_stats(self) -> Dict[str, any]:
        """Get system-wide scheduling statistics."""
        try:
            stats = {
                "total_queues": len(self.queues),
                "total_queued_requests": sum(len(q.queue) for q in self.queues.values()),
                "tenant_stats": {},
                "weight_distribution": {}
            }
            
            # Calculate weight distribution
            weight_counts = {}
            for tenant_queue in self.queues.values():
                weight = tenant_queue.plan_weight
                weight_counts[weight] = weight_counts.get(weight, 0) + 1
            stats["weight_distribution"] = weight_counts
            
            # Get individual tenant stats
            for tenant_id, tenant_queue in self.queues.items():
                tenant_stats = await self.get_queue_stats(tenant_id)
                if tenant_stats:
                    stats["tenant_stats"][tenant_id] = tenant_stats
            
            return stats
            
        except Exception as e:
            logger.error("Failed to get system stats", error=str(e))
            return {}
    
    async def clear_tenant_queue(self, tenant_id: str) -> int:
        """Clear all requests for a specific tenant."""
        try:
            if tenant_id not in self.queues:
                return 0
            
            tenant_queue = self.queues[tenant_id]
            cleared_count = len(tenant_queue.queue)
            tenant_queue.queue.clear()
            
            logger.info("Tenant queue cleared",
                       tenant_id=tenant_id,
                       cleared_requests=cleared_count)
            
            return cleared_count
            
        except Exception as e:
            logger.error("Failed to clear tenant queue", tenant_id=tenant_id, error=str(e))
            return 0
    
    async def shutdown(self):
        """Shutdown the scheduler gracefully."""
        try:
            if self._scheduler_task:
                self._scheduler_task.cancel()
                try:
                    await self._scheduler_task
                except asyncio.CancelledError:
                    pass
            
            logger.info("Weighted fair scheduler shutdown complete")
            
        except Exception as e:
            logger.error("Error during scheduler shutdown", error=str(e))
