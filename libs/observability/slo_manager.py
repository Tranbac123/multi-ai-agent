"""
SLO Manager for Service Level Objectives

Manages SLOs, error budgets, and alerting based on service level objectives
with comprehensive monitoring and alerting capabilities.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import structlog
from datetime import datetime, timedelta
from collections import deque

logger = structlog.get_logger(__name__)


class SLOTarget(Enum):
    """SLO target types."""
    AVAILABILITY = "availability"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"


class AlertSeverity(Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SLODefinition:
    """SLO definition with targets and windows."""
    
    name: str
    description: str
    target_type: SLOTarget
    target_value: float  # Target value (e.g., 99.9 for 99.9% availability)
    measurement_window: int  # Window in seconds (e.g., 3600 for 1 hour)
    evaluation_window: int  # Evaluation window in seconds (e.g., 86400 for 24 hours)
    error_budget_policy: float  # Error budget burn rate threshold (e.g., 0.1 for 10%)
    service: str
    tenant_id: Optional[str] = None  # None for global SLOs
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class SLOStatus:
    """Current SLO status and metrics."""
    
    slo_name: str
    current_value: float
    target_value: float
    error_budget_remaining: float
    error_budget_burn_rate: float
    is_healthy: bool
    last_evaluation: datetime
    alert_level: Optional[AlertSeverity] = None


@dataclass
class SLOMetric:
    """SLO metric data point."""
    
    timestamp: datetime
    value: float
    success: bool
    latency_ms: Optional[float] = None
    error_code: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)


class ErrorBudget:
    """Manages error budget calculations and burn rate analysis."""
    
    def __init__(self, slo_definition: SLODefinition):
        self.slo_definition = slo_definition
        self.metrics_window: deque = deque(maxlen=slo_definition.evaluation_window)
        self.error_budget = 100.0  # Start with 100% error budget
        
        logger.info("Error budget initialized", 
                   slo_name=slo_definition.name,
                   target_value=slo_definition.target_value)
    
    def add_metric(self, metric: SLOMetric):
        """Add a metric data point to the window."""
        
        self.metrics_window.append(metric)
        
        # Calculate current error budget
        self._calculate_error_budget()
    
    def _calculate_error_budget(self):
        """Calculate current error budget based on metrics window."""
        
        if not self.metrics_window:
            return
        
        # Calculate success rate in the measurement window
        window_start = datetime.now() - timedelta(seconds=self.slo_definition.measurement_window)
        window_metrics = [
            m for m in self.metrics_window 
            if m.timestamp >= window_start
        ]
        
        if not window_metrics:
            return
        
        success_count = sum(1 for m in window_metrics if m.success)
        total_count = len(window_metrics)
        success_rate = (success_count / total_count) * 100
        
        # Calculate error budget burn
        target_rate = self.slo_definition.target_value
        if self.slo_definition.target_type == SLOTarget.AVAILABILITY:
            # For availability, error budget = (target - actual) / target
            error_budget_used = max(0, target_rate - success_rate) / target_rate * 100
        elif self.slo_definition.target_type == SLOTarget.ERROR_RATE:
            # For error rate, error budget = (actual - target) / (100 - target)
            actual_error_rate = 100 - success_rate
            error_budget_used = max(0, actual_error_rate - target_rate) / (100 - target_rate) * 100
        else:
            # For other types, use simple difference
            error_budget_used = max(0, target_rate - success_rate) / target_rate * 100
        
        # Update error budget
        self.error_budget = max(0, 100 - error_budget_used)
    
    def get_burn_rate(self) -> float:
        """Calculate error budget burn rate."""
        
        if len(self.metrics_window) < 2:
            return 0.0
        
        # Calculate burn rate over the last hour
        hour_ago = datetime.now() - timedelta(hours=1)
        recent_metrics = [
            m for m in self.metrics_window 
            if m.timestamp >= hour_ago
        ]
        
        if not recent_metrics:
            return 0.0
        
        # Calculate current burn rate
        success_count = sum(1 for m in recent_metrics if m.success)
        total_count = len(recent_metrics)
        current_rate = (success_count / total_count) * 100 if total_count > 0 else 0
        
        target_rate = self.slo_definition.target_value
        
        if self.slo_definition.target_type == SLOTarget.AVAILABILITY:
            burn_rate = max(0, target_rate - current_rate) / target_rate
        elif self.slo_definition.target_type == SLOTarget.ERROR_RATE:
            actual_error_rate = 100 - current_rate
            burn_rate = max(0, actual_error_rate - target_rate) / (100 - target_rate)
        else:
            burn_rate = max(0, target_rate - current_rate) / target_rate
        
        return burn_rate
    
    def is_burn_rate_exceeded(self) -> bool:
        """Check if error budget burn rate exceeds threshold."""
        
        burn_rate = self.get_burn_rate()
        threshold = self.slo_definition.error_budget_policy
        
        return burn_rate > threshold
    
    def get_status(self) -> SLOStatus:
        """Get current SLO status."""
        
        if not self.metrics_window:
            return SLOStatus(
                slo_name=self.slo_definition.name,
                current_value=0.0,
                target_value=self.slo_definition.target_value,
                error_budget_remaining=self.error_budget,
                error_budget_burn_rate=0.0,
                is_healthy=True,
                last_evaluation=datetime.now()
            )
        
        # Calculate current value
        window_start = datetime.now() - timedelta(seconds=self.slo_definition.measurement_window)
        window_metrics = [
            m for m in self.metrics_window 
            if m.timestamp >= window_start
        ]
        
        if not window_metrics:
            current_value = 0.0
        else:
            success_count = sum(1 for m in window_metrics if m.success)
            total_count = len(window_metrics)
            
            if self.slo_definition.target_type == SLOTarget.AVAILABILITY:
                current_value = (success_count / total_count) * 100
            elif self.slo_definition.target_type == SLOTarget.ERROR_RATE:
                current_value = 100 - ((success_count / total_count) * 100)
            else:
                current_value = (success_count / total_count) * 100
        
        # Determine health status
        burn_rate = self.get_burn_rate()
        is_healthy = not self.is_burn_rate_exceeded() and self.error_budget > 10.0
        
        # Determine alert level
        alert_level = None
        if burn_rate > self.slo_definition.error_budget_policy * 2:
            alert_level = AlertSeverity.CRITICAL
        elif burn_rate > self.slo_definition.error_budget_policy * 1.5:
            alert_level = AlertSeverity.HIGH
        elif burn_rate > self.slo_definition.error_budget_policy:
            alert_level = AlertSeverity.MEDIUM
        elif burn_rate > self.slo_definition.error_budget_policy * 0.5:
            alert_level = AlertSeverity.LOW
        
        return SLOStatus(
            slo_name=self.slo_definition.name,
            current_value=current_value,
            target_value=self.slo_definition.target_value,
            error_budget_remaining=self.error_budget,
            error_budget_burn_rate=burn_rate,
            is_healthy=is_healthy,
            last_evaluation=datetime.now(),
            alert_level=alert_level
        )


class SLOManager:
    """Manages SLOs across the platform."""
    
    def __init__(self):
        self.slo_definitions: Dict[str, SLODefinition] = {}
        self.error_budgets: Dict[str, ErrorBudget] = {}
        self.alert_handlers: List[Callable] = []
        
        # Initialize default SLOs
        self._initialize_default_slos()
        
        logger.info("SLO manager initialized")
    
    def _initialize_default_slos(self):
        """Initialize default SLO definitions."""
        
        default_slos = [
            # API Gateway SLOs
            SLODefinition(
                name="api_availability",
                description="API Gateway availability",
                target_type=SLOTarget.AVAILABILITY,
                target_value=99.9,
                measurement_window=300,  # 5 minutes
                evaluation_window=3600,  # 1 hour
                error_budget_policy=0.1,  # 10% burn rate
                service="api_gateway"
            ),
            SLODefinition(
                name="api_latency_p95",
                description="API Gateway 95th percentile latency",
                target_type=SLOTarget.LATENCY,
                target_value=500.0,  # 500ms
                measurement_window=300,
                evaluation_window=3600,
                error_budget_policy=0.1,
                service="api_gateway"
            ),
            
            # Router SLOs
            SLODefinition(
                name="router_decision_latency",
                description="Router decision latency",
                target_type=SLOTarget.LATENCY,
                target_value=50.0,  # 50ms
                measurement_window=300,
                evaluation_window=3600,
                error_budget_policy=0.1,
                service="router"
            ),
            SLODefinition(
                name="router_misroute_rate",
                description="Router misroute rate",
                target_type=SLOTarget.ERROR_RATE,
                target_value=1.0,  # 1% misroute rate
                measurement_window=300,
                evaluation_window=3600,
                error_budget_policy=0.1,
                service="router"
            ),
            
            # Tool Service SLOs
            SLODefinition(
                name="tool_success_rate",
                description="Tool execution success rate",
                target_type=SLOTarget.AVAILABILITY,
                target_value=99.5,
                measurement_window=300,
                evaluation_window=3600,
                error_budget_policy=0.1,
                service="tool_service"
            ),
            
            # WebSocket SLOs
            SLODefinition(
                name="ws_connection_success_rate",
                description="WebSocket connection success rate",
                target_type=SLOTarget.AVAILABILITY,
                target_value=99.0,
                measurement_window=300,
                evaluation_window=3600,
                error_budget_policy=0.1,
                service="realtime"
            ),
            SLODefinition(
                name="ws_message_delivery_rate",
                description="WebSocket message delivery rate",
                target_type=SLOTarget.AVAILABILITY,
                target_value=99.5,
                measurement_window=300,
                evaluation_window=3600,
                error_budget_policy=0.1,
                service="realtime"
            )
        ]
        
        for slo in default_slos:
            self.add_slo(slo)
    
    def add_slo(self, slo_definition: SLODefinition):
        """Add a new SLO definition."""
        
        self.slo_definitions[slo_definition.name] = slo_definition
        self.error_budgets[slo_definition.name] = ErrorBudget(slo_definition)
        
        logger.info("SLO added", 
                   name=slo_definition.name,
                   service=slo_definition.service,
                   target_type=slo_definition.target_type.value)
    
    def record_metric(
        self, 
        slo_name: str, 
        success: bool, 
        latency_ms: Optional[float] = None,
        error_code: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None
    ):
        """Record a metric for an SLO."""
        
        if slo_name not in self.slo_definitions:
            logger.warning("Unknown SLO", slo_name=slo_name)
            return
        
        slo_def = self.slo_definitions[slo_name]
        
        # Create metric
        metric = SLOMetric(
            timestamp=datetime.now(),
            value=100.0 if success else 0.0,
            success=success,
            latency_ms=latency_ms,
            error_code=error_code,
            tags=tags or {}
        )
        
        # Add to error budget
        self.error_budgets[slo_name].add_metric(metric)
        
        # Check for alerts
        self._check_alerts(slo_name)
    
    def _check_alerts(self, slo_name: str):
        """Check if SLO needs alerting."""
        
        if slo_name not in self.error_budgets:
            return
        
        error_budget = self.error_budgets[slo_name]
        status = error_budget.get_status()
        
        if status.alert_level:
            self._trigger_alert(status)
    
    def _trigger_alert(self, status: SLOStatus):
        """Trigger an alert for SLO violation."""
        
        alert_data = {
            "slo_name": status.slo_name,
            "alert_level": status.alert_level.value,
            "current_value": status.current_value,
            "target_value": status.target_value,
            "error_budget_remaining": status.error_budget_remaining,
            "error_budget_burn_rate": status.error_budget_burn_rate,
            "timestamp": datetime.now().isoformat()
        }
        
        # Call alert handlers
        for handler in self.alert_handlers:
            try:
                handler(alert_data)
            except Exception as e:
                logger.error("Error in alert handler", error=str(e))
        
        logger.warning("SLO alert triggered", **alert_data)
    
    def add_alert_handler(self, handler: Callable):
        """Add an alert handler."""
        
        self.alert_handlers.append(handler)
    
    def get_slo_status(self, slo_name: str) -> Optional[SLOStatus]:
        """Get current status of an SLO."""
        
        if slo_name not in self.error_budgets:
            return None
        
        return self.error_budgets[slo_name].get_status()
    
    def get_all_slo_statuses(self) -> Dict[str, SLOStatus]:
        """Get status of all SLOs."""
        
        return {
            name: error_budget.get_status()
            for name, error_budget in self.error_budgets.items()
        }
    
    def get_service_slo_statuses(self, service: str) -> Dict[str, SLOStatus]:
        """Get SLO statuses for a specific service."""
        
        service_slos = {
            name: slo_def 
            for name, slo_def in self.slo_definitions.items()
            if slo_def.service == service
        }
        
        return {
            name: self.error_budgets[name].get_status()
            for name in service_slos.keys()
        }
    
    def get_tenant_slo_statuses(self, tenant_id: str) -> Dict[str, SLOStatus]:
        """Get SLO statuses for a specific tenant."""
        
        tenant_slos = {
            name: slo_def 
            for name, slo_def in self.slo_definitions.items()
            if slo_def.tenant_id == tenant_id
        }
        
        return {
            name: self.error_budgets[name].get_status()
            for name in tenant_slos.keys()
        }
    
    def get_slo_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of SLO metrics."""
        
        all_statuses = self.get_all_slo_statuses()
        
        summary = {
            "total_slos": len(all_statuses),
            "healthy_slos": sum(1 for status in all_statuses.values() if status.is_healthy),
            "unhealthy_slos": sum(1 for status in all_statuses.values() if not status.is_healthy),
            "critical_alerts": sum(1 for status in all_statuses.values() if status.alert_level == AlertSeverity.CRITICAL),
            "high_alerts": sum(1 for status in all_statuses.values() if status.alert_level == AlertSeverity.HIGH),
            "medium_alerts": sum(1 for status in all_statuses.values() if status.alert_level == AlertSeverity.MEDIUM),
            "low_alerts": sum(1 for status in all_statuses.values() if status.alert_level == AlertSeverity.LOW),
            "by_service": {},
            "timestamp": datetime.now().isoformat()
        }
        
        # Group by service
        for name, status in all_statuses.items():
            slo_def = self.slo_definitions[name]
            service = slo_def.service
            
            if service not in summary["by_service"]:
                summary["by_service"][service] = {
                    "total": 0,
                    "healthy": 0,
                    "unhealthy": 0,
                    "alerts": {"critical": 0, "high": 0, "medium": 0, "low": 0}
                }
            
            summary["by_service"][service]["total"] += 1
            
            if status.is_healthy:
                summary["by_service"][service]["healthy"] += 1
            else:
                summary["by_service"][service]["unhealthy"] += 1
            
            if status.alert_level:
                alert_key = status.alert_level.value
                summary["by_service"][service]["alerts"][alert_key] += 1
        
        return summary
    
    async def cleanup_old_metrics(self):
        """Clean up old metrics to prevent memory growth."""
        
        for error_budget in self.error_budgets.values():
            # The deque automatically maintains maxlen, so this is mostly for logging
            pass
        
        logger.debug("SLO metrics cleanup completed")


# Global SLO manager instance
slo_manager = SLOManager()


def record_slo_metric(
    slo_name: str, 
    success: bool, 
    latency_ms: Optional[float] = None,
    error_code: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None
):
    """Record a metric for an SLO (convenience function)."""
    
    slo_manager.record_metric(slo_name, success, latency_ms, error_code, tags)


def get_slo_status(slo_name: str) -> Optional[SLOStatus]:
    """Get SLO status (convenience function)."""
    
    return slo_manager.get_slo_status(slo_name)


def get_all_slo_statuses() -> Dict[str, SLOStatus]:
    """Get all SLO statuses (convenience function)."""
    
    return slo_manager.get_all_slo_statuses()
