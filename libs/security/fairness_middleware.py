"""
Fairness Middleware for Multi-Tenant Resource Allocation

Implements weighted fair queuing, pre-admission control, and degradation
switches for ensuring fair resource allocation across tenants.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import structlog
from datetime import datetime, timedelta
# import heapq
from collections import defaultdict, deque

logger = structlog.get_logger(__name__)


class TenantTier(Enum):
    """Tenant tier for fairness calculations."""
    FREE = "free"
    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class DegradationLevel(Enum):
    """Degradation levels for resource management."""
    NORMAL = "normal"
    LIGHT = "light"
    MODERATE = "moderate"
    HEAVY = "heavy"


@dataclass
class TenantWeight:
    """Tenant weight configuration for fair queuing."""
    
    tenant_id: str
    tier: TenantTier
    weight: float
    priority: int  # Higher number = higher priority
    max_concurrent: int
    burst_capacity: int = 0


@dataclass
class FairQueueEntry:
    """Entry in the fair queue."""
    
    tenant_id: str
    request_id: str
    priority: int
    weight: float
    arrival_time: float
    processing_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other):
        """Comparison for priority queue (min heap)."""
        # Higher priority (lower number) first, then by arrival time
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.arrival_time < other.arrival_time


@dataclass
class DegradationConfig:
    """Configuration for degradation switches."""
    
    level: DegradationLevel
    disable_critique: bool = False
    disable_debate: bool = False
    shrink_context: bool = False
    prefer_slm: bool = False
    reduce_parallelism: bool = False
    limit_tool_calls: bool = False


class WeightedFairScheduler:
    """Weighted fair scheduler for tenant requests."""
    
    def __init__(self):
        self.tenant_weights: Dict[str, TenantWeight] = {}
        self.request_queue: List[FairQueueEntry] = []
        self.tenant_queues: Dict[str, deque] = defaultdict(deque)
        self.active_requests: Dict[str, Set[str]] = defaultdict(set)  # tenant_id -> request_ids
        self.tenant_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "total_requests": 0,
            "completed_requests": 0,
            "total_processing_time": 0.0,
            "average_processing_time": 0.0,
            "last_request_time": None
        })
        
        logger.info("Weighted fair scheduler initialized")
    
    def set_tenant_weight(self, weight: TenantWeight):
        """Set weight configuration for a tenant."""
        
        self.tenant_weights[weight.tenant_id] = weight
        
        logger.info("Tenant weight set", 
                   tenant_id=weight.tenant_id,
                   tier=weight.tier.value,
                   weight=weight.weight,
                   priority=weight.priority)
    
    async def enqueue_request(
        self, 
        tenant_id: str, 
        request_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Enqueue a request for processing."""
        
        # Check if tenant has weight configuration
        if tenant_id not in self.tenant_weights:
            logger.warning("Tenant not configured", tenant_id=tenant_id)
            return False
        
        weight_config = self.tenant_weights[tenant_id]
        
        # Check if tenant has reached max concurrent requests
        if len(self.active_requests[tenant_id]) >= weight_config.max_concurrent:
            logger.warning("Tenant max concurrent exceeded", 
                          tenant_id=tenant_id,
                          current=len(self.active_requests[tenant_id]),
                          max=weight_config.max_concurrent)
            return False
        
        # Create queue entry
        entry = FairQueueEntry(
            tenant_id=tenant_id,
            request_id=request_id,
            priority=weight_config.priority,
            weight=weight_config.weight,
            arrival_time=time.time(),
            metadata=metadata or {}
        )
        
        # Add to tenant queue
        self.tenant_queues[tenant_id].append(entry)
        
        # Update stats
        self.tenant_stats[tenant_id]["total_requests"] += 1
        self.tenant_stats[tenant_id]["last_request_time"] = datetime.now()
        
        logger.debug("Request enqueued", 
                    tenant_id=tenant_id,
                    request_id=request_id,
                    queue_size=len(self.tenant_queues[tenant_id]))
        
        return True
    
    async def dequeue_request(self) -> Optional[FairQueueEntry]:
        """Dequeue the next request to process using weighted fair queuing."""
        
        # Find the tenant with the highest priority and lowest virtual time
        best_entry = None
        best_tenant = None
        best_virtual_time = float('inf')
        
        for tenant_id, queue in self.tenant_queues.items():
            if not queue:
                continue
            
            weight_config = self.tenant_weights.get(tenant_id)
            if not weight_config:
                continue
            
            # Calculate virtual time for this tenant
            tenant_stats = self.tenant_stats[tenant_id]
            virtual_time = (
                tenant_stats["total_processing_time"] / weight_config.weight
            )
            
            # Check if this tenant has higher priority or lower virtual time
            if (virtual_time < best_virtual_time or 
                (virtual_time == best_virtual_time and 
                 weight_config.priority < self.tenant_weights.get(best_tenant, TenantWeight("", TenantTier.FREE, 0, 0, 0)).priority)):
                best_virtual_time = virtual_time
                best_entry = queue[0]  # First in queue
                best_tenant = tenant_id
        
        if best_entry:
            # Remove from queue
            self.tenant_queues[best_tenant].popleft()
            
            # Mark as active
            self.active_requests[best_tenant].add(best_entry.request_id)
            
            logger.debug("Request dequeued", 
                        tenant_id=best_tenant,
                        request_id=best_entry.request_id,
                        virtual_time=best_virtual_time)
        
        return best_entry
    
    async def complete_request(self, tenant_id: str, request_id: str, processing_time: float):
        """Mark a request as completed."""
        
        if request_id in self.active_requests[tenant_id]:
            self.active_requests[tenant_id].remove(request_id)
        
        # Update tenant stats
        stats = self.tenant_stats[tenant_id]
        stats["completed_requests"] += 1
        stats["total_processing_time"] += processing_time
        stats["average_processing_time"] = (
            stats["total_processing_time"] / stats["completed_requests"]
        )
        
        logger.debug("Request completed", 
                    tenant_id=tenant_id,
                    request_id=request_id,
                    processing_time=processing_time)
    
    def get_tenant_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get statistics for a tenant."""
        
        weight_config = self.tenant_weights.get(tenant_id)
        stats = self.tenant_stats[tenant_id].copy()
        
        if weight_config:
            stats.update({
                "tier": weight_config.tier.value,
                "weight": weight_config.weight,
                "priority": weight_config.priority,
                "max_concurrent": weight_config.max_concurrent,
                "current_active": len(self.active_requests[tenant_id]),
                "queue_size": len(self.tenant_queues[tenant_id])
            })
        
        return stats
    
    def get_scheduler_metrics(self) -> Dict[str, Any]:
        """Get overall scheduler metrics."""
        
        total_requests = sum(
            stats["total_requests"] 
            for stats in self.tenant_stats.values()
        )
        
        total_completed = sum(
            stats["completed_requests"] 
            for stats in self.tenant_stats.values()
        )
        
        total_active = sum(
            len(active_requests) 
            for active_requests in self.active_requests.values()
        )
        
        total_queued = sum(
            len(queue) 
            for queue in self.tenant_queues.values()
        )
        
        return {
            "total_tenants": len(self.tenant_weights),
            "total_requests": total_requests,
            "total_completed": total_completed,
            "total_active": total_active,
            "total_queued": total_queued,
            "tenant_stats": {
                tenant_id: self.get_tenant_stats(tenant_id)
                for tenant_id in self.tenant_weights.keys()
            }
        }


class PreAdmissionControl:
    """Pre-admission control for system overload protection."""
    
    def __init__(self):
        self.system_load_threshold = 0.8  # 80% system load threshold
        self.cpu_threshold = 0.85  # 85% CPU threshold
        self.memory_threshold = 0.9  # 90% memory threshold
        self.queue_size_threshold = 1000  # Max queue size
        self.degradation_configs = self._get_degradation_configs()
        
        logger.info("Pre-admission control initialized")
    
    def _get_degradation_configs(self) -> Dict[DegradationLevel, DegradationConfig]:
        """Get degradation configurations."""
        
        return {
            DegradationLevel.NORMAL: DegradationConfig(
                level=DegradationLevel.NORMAL
            ),
            DegradationLevel.LIGHT: DegradationConfig(
                level=DegradationLevel.LIGHT,
                prefer_slm=True,
                reduce_parallelism=True
            ),
            DegradationLevel.MODERATE: DegradationConfig(
                level=DegradationLevel.MODERATE,
                disable_critique=True,
                shrink_context=True,
                prefer_slm=True,
                reduce_parallelism=True
            ),
            DegradationLevel.HEAVY: DegradationConfig(
                level=DegradationLevel.HEAVY,
                disable_critique=True,
                disable_debate=True,
                shrink_context=True,
                prefer_slm=True,
                reduce_parallelism=True,
                limit_tool_calls=True
            )
        }
    
    async def check_admission(
        self, 
        tenant_id: str, 
        request_metadata: Dict[str, Any],
        system_metrics: Dict[str, float]
    ) -> Tuple[bool, DegradationConfig, str]:
        """Check if request should be admitted and what degradation to apply."""
        
        # Check system load
        system_load = system_metrics.get("system_load", 0.0)
        cpu_usage = system_metrics.get("cpu_usage", 0.0)
        memory_usage = system_metrics.get("memory_usage", 0.0)
        queue_size = system_metrics.get("queue_size", 0)
        
        # Determine degradation level based on system metrics
        if (system_load > self.system_load_threshold or 
            cpu_usage > self.cpu_threshold or 
            memory_usage > self.memory_threshold):
            
            if system_load > 0.95 or cpu_usage > 0.95 or memory_usage > 0.95:
                degradation_level = DegradationLevel.HEAVY
            elif system_load > 0.9 or cpu_usage > 0.9 or memory_usage > 0.95:
                degradation_level = DegradationLevel.MODERATE
            else:
                degradation_level = DegradationLevel.LIGHT
        else:
            degradation_level = DegradationLevel.NORMAL
        
        # Check queue size
        if queue_size > self.queue_size_threshold:
            if degradation_level == DegradationLevel.NORMAL:
                degradation_level = DegradationLevel.LIGHT
            elif degradation_level == DegradationLevel.LIGHT:
                degradation_level = DegradationLevel.MODERATE
        
        # Get degradation configuration
        degradation_config = self.degradation_configs[degradation_level]
        
        # Determine if request should be admitted
        should_admit = True
        reason = "admitted"
        
        # Heavy degradation might reject some requests
        if degradation_level == DegradationLevel.HEAVY:
            # Reject low-priority requests during heavy degradation
            tenant_tier = request_metadata.get("tenant_tier", "free")
            if tenant_tier in ["free", "standard"]:
                should_admit = False
                reason = "system_overload_low_priority_rejected"
        
        # Check if queue is completely full
        if queue_size > self.queue_size_threshold * 1.5:
            should_admit = False
            reason = "queue_full"
        
        logger.debug("Admission control decision", 
                    tenant_id=tenant_id,
                    should_admit=should_admit,
                    degradation_level=degradation_level.value,
                    reason=reason,
                    system_load=system_load,
                    cpu_usage=cpu_usage,
                    memory_usage=memory_usage)
        
        return should_admit, degradation_config, reason
    
    def update_thresholds(
        self, 
        system_load_threshold: Optional[float] = None,
        cpu_threshold: Optional[float] = None,
        memory_threshold: Optional[float] = None,
        queue_size_threshold: Optional[int] = None
    ):
        """Update admission control thresholds."""
        
        if system_load_threshold is not None:
            self.system_load_threshold = system_load_threshold
        if cpu_threshold is not None:
            self.cpu_threshold = cpu_threshold
        if memory_threshold is not None:
            self.memory_threshold = memory_threshold
        if queue_size_threshold is not None:
            self.queue_size_threshold = queue_size_threshold
        
        logger.info("Admission control thresholds updated", 
                   system_load_threshold=self.system_load_threshold,
                   cpu_threshold=self.cpu_threshold,
                   memory_threshold=self.memory_threshold,
                   queue_size_threshold=self.queue_size_threshold)


class FairnessMiddleware:
    """Main fairness middleware combining all components."""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.scheduler = WeightedFairScheduler()
        self.admission_control = PreAdmissionControl()
        self.degradation_switches: Dict[str, DegradationConfig] = {}
        
        # Metrics
        self.total_requests = 0
        self.admitted_requests = 0
        self.rejected_requests = 0
        self.degraded_requests = 0
        
        logger.info("Fairness middleware initialized")
    
    async def set_tenant_config(
        self, 
        tenant_id: str, 
        tier: TenantTier,
        max_concurrent: int = 10,
        priority: int = 5
    ):
        """Set configuration for a tenant."""
        
        # Calculate weight based on tier
        tier_weights = {
            TenantTier.FREE: 1.0,
            TenantTier.STANDARD: 2.0,
            TenantTier.PREMIUM: 4.0,
            TenantTier.ENTERPRISE: 8.0
        }
        
        weight = TenantWeight(
            tenant_id=tenant_id,
            tier=tier,
            weight=tier_weights[tier],
            priority=priority,
            max_concurrent=max_concurrent
        )
        
        self.scheduler.set_tenant_weight(weight)
        
        logger.info("Tenant configuration set", 
                   tenant_id=tenant_id,
                   tier=tier.value,
                   weight=weight.weight,
                   max_concurrent=max_concurrent)
    
    async def process_request(
        self, 
        tenant_id: str, 
        request_id: str,
        request_metadata: Dict[str, Any],
        system_metrics: Dict[str, float]
    ) -> Tuple[bool, DegradationConfig, str]:
        """Process a request through fairness middleware."""
        
        self.total_requests += 1
        
        # Check admission control
        should_admit, degradation_config, reason = await self.admission_control.check_admission(
            tenant_id, request_metadata, system_metrics
        )
        
        if not should_admit:
            self.rejected_requests += 1
            logger.warning("Request rejected by admission control", 
                          tenant_id=tenant_id,
                          request_id=request_id,
                          reason=reason)
            return False, degradation_config, reason
        
        # Enqueue request in fair scheduler
        enqueued = await self.scheduler.enqueue_request(
            tenant_id, request_id, request_metadata
        )
        
        if not enqueued:
            self.rejected_requests += 1
            reason = "tenant_limit_exceeded"
            logger.warning("Request rejected by tenant limits", 
                          tenant_id=tenant_id,
                          request_id=request_id)
            return False, degradation_config, reason
        
        self.admitted_requests += 1
        
        # Apply degradation if needed
        if degradation_config.level != DegradationLevel.NORMAL:
            self.degraded_requests += 1
            self.degradation_switches[request_id] = degradation_config
        
        logger.debug("Request processed by fairness middleware", 
                    tenant_id=tenant_id,
                    request_id=request_id,
                    admitted=should_admit,
                    degradation_level=degradation_config.level.value)
        
        return True, degradation_config, reason
    
    async def get_next_request(self) -> Optional[Tuple[FairQueueEntry, DegradationConfig]]:
        """Get the next request to process."""
        
        entry = await self.scheduler.dequeue_request()
        if not entry:
            return None
        
        # Get degradation config for this request
        degradation_config = self.degradation_switches.pop(
            entry.request_id, 
            self.admission_control.degradation_configs[DegradationLevel.NORMAL]
        )
        
        return entry, degradation_config
    
    async def complete_request(self, tenant_id: str, request_id: str, processing_time: float):
        """Mark a request as completed."""
        
        await self.scheduler.complete_request(tenant_id, request_id, processing_time)
        
        # Remove degradation config if it exists
        self.degradation_switches.pop(request_id, None)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get fairness middleware metrics."""
        
        scheduler_metrics = self.scheduler.get_scheduler_metrics()
        
        return {
            "total_requests": self.total_requests,
            "admitted_requests": self.admitted_requests,
            "rejected_requests": self.rejected_requests,
            "degraded_requests": self.degraded_requests,
            "admission_rate": self.admitted_requests / max(1, self.total_requests),
            "degradation_rate": self.degraded_requests / max(1, self.total_requests),
            "scheduler_metrics": scheduler_metrics,
            "admission_thresholds": {
                "system_load_threshold": self.admission_control.system_load_threshold,
                "cpu_threshold": self.admission_control.cpu_threshold,
                "memory_threshold": self.admission_control.memory_threshold,
                "queue_size_threshold": self.admission_control.queue_size_threshold
            }
        }
