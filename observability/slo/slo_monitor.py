"""SLO monitoring and alerting."""

import asyncio
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import structlog
import redis.asyncio as redis

logger = structlog.get_logger(__name__)


class SLOStatus(Enum):
    """SLO status."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class SLOTarget:
    """SLO target definition."""
    service: str
    metric: str
    target: float
    window: str
    burn_rate_threshold: float


@dataclass
class SLOAlert:
    """SLO alert."""
    service: str
    metric: str
    current_value: float
    target_value: float
    burn_rate: float
    status: SLOStatus
    timestamp: datetime
    message: str


class SLOMonitor:
    """SLO monitoring and alerting."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.slo_targets = self._initialize_slo_targets()
        self.alert_thresholds = {
            'warning': 0.1,
            'critical': 0.5
        }
    
    def _initialize_slo_targets(self) -> List[SLOTarget]:
        """Initialize SLO targets for all services."""
        return [
            SLOTarget("api-gateway", "availability", 0.999, "30d", 0.1),
            SLOTarget("api-gateway", "p50_latency", 100.0, "30d", 0.1),
            SLOTarget("api-gateway", "p95_latency", 500.0, "30d", 0.1),
            SLOTarget("router-service", "availability", 0.999, "30d", 0.1),
            SLOTarget("router-service", "decision_latency_p50", 50.0, "30d", 0.1),
            SLOTarget("router-service", "misroute_rate", 0.05, "30d", 0.1),
            SLOTarget("orchestrator", "availability", 0.999, "30d", 0.1),
            SLOTarget("orchestrator", "workflow_completion_rate", 0.95, "30d", 0.1),
            SLOTarget("realtime", "availability", 0.999, "30d", 0.1),
            SLOTarget("realtime", "websocket_backpressure_drops", 0.01, "30d", 0.1),
            SLOTarget("analytics-service", "availability", 0.999, "30d", 0.1),
            SLOTarget("analytics-service", "query_latency_p95", 1000.0, "30d", 0.1),
            SLOTarget("billing-service", "availability", 0.999, "30d", 0.1),
            SLOTarget("billing-service", "invoice_accuracy", 0.999, "30d", 0.1)
        ]
    
    async def check_slo_status(self, service: str, metric: str) -> SLOAlert:
        """Check SLO status for specific service and metric."""
        try:
            target = self._find_slo_target(service, metric)
            if not target:
                return SLOAlert(
                    service=service, metric=metric, current_value=0.0, target_value=0.0,
                    burn_rate=0.0, status=SLOStatus.UNKNOWN, timestamp=datetime.utcnow(),
                    message=f"No SLO target found for {service}:{metric}"
                )
            
            current_value = await self._get_current_metric_value(service, metric)
            burn_rate = await self._calculate_burn_rate(service, metric, target)
            status = self._determine_slo_status(current_value, target, burn_rate)
            
            alert = SLOAlert(
                service=service, metric=metric, current_value=current_value,
                target_value=target.target, burn_rate=burn_rate, status=status,
                timestamp=datetime.utcnow(),
                message=self._generate_alert_message(service, metric, current_value, target.target, burn_rate, status)
            )
            
            await self._store_alert(alert)
            return alert
            
        except Exception as e:
            logger.error("Failed to check SLO status", error=str(e), service=service, metric=metric)
            return SLOAlert(
                service=service, metric=metric, current_value=0.0, target_value=0.0,
                burn_rate=0.0, status=SLOStatus.UNKNOWN, timestamp=datetime.utcnow(),
                message=f"Error checking SLO: {str(e)}"
            )
    
    async def check_all_slos(self) -> List[SLOAlert]:
        """Check all SLOs and return alerts."""
        try:
            alerts = []
            for target in self.slo_targets:
                alert = await self.check_slo_status(target.service, target.metric)
                alerts.append(alert)
            return alerts
        except Exception as e:
            logger.error("Failed to check all SLOs", error=str(e))
            return []
    
    def _find_slo_target(self, service: str, metric: str) -> Optional[SLOTarget]:
        """Find SLO target for service and metric."""
        for target in self.slo_targets:
            if target.service == service and target.metric == metric:
                return target
        return None
    
    async def _get_current_metric_value(self, service: str, metric: str) -> float:
        """Get current metric value from monitoring system."""
        try:
            mock_values = {
                "api-gateway": {"availability": 0.9995, "p50_latency": 85.0, "p95_latency": 450.0},
                "router-service": {"availability": 0.9998, "decision_latency_p50": 45.0, "misroute_rate": 0.03},
                "orchestrator": {"availability": 0.9992, "workflow_completion_rate": 0.96},
                "realtime": {"availability": 0.9999, "websocket_backpressure_drops": 0.005},
                "analytics-service": {"availability": 0.9997, "query_latency_p95": 800.0},
                "billing-service": {"availability": 0.9996, "invoice_accuracy": 0.9998}
            }
            return mock_values.get(service, {}).get(metric, 0.0)
        except Exception as e:
            logger.error("Failed to get current metric value", error=str(e))
            return 0.0
    
    async def _calculate_burn_rate(self, service: str, metric: str, target: SLOTarget) -> float:
        """Calculate SLO burn rate."""
        try:
            current_value = await self._get_current_metric_value(service, metric)
            
            if metric == "availability":
                burn_rate = max(0, target.target - current_value) / target.target
            elif metric in ["p50_latency", "p95_latency", "query_latency_p95"]:
                burn_rate = max(0, current_value - target.target) / target.target
            elif metric in ["misroute_rate", "websocket_backpressure_drops"]:
                burn_rate = max(0, current_value - target.target) / target.target
            else:
                burn_rate = abs(current_value - target.target) / target.target
            
            return min(1.0, burn_rate)
        except Exception as e:
            logger.error("Failed to calculate burn rate", error=str(e))
            return 0.0
    
    def _determine_slo_status(self, current_value: float, target: SLOTarget, burn_rate: float) -> SLOStatus:
        """Determine SLO status based on current value and burn rate."""
        try:
            if burn_rate >= self.alert_thresholds['critical']:
                return SLOStatus.CRITICAL
            elif burn_rate >= self.alert_thresholds['warning']:
                return SLOStatus.WARNING
            else:
                return SLOStatus.HEALTHY
        except Exception as e:
            logger.error("Failed to determine SLO status", error=str(e))
            return SLOStatus.UNKNOWN
    
    def _generate_alert_message(self, service: str, metric: str, current_value: float, target_value: float, burn_rate: float, status: SLOStatus) -> str:
        """Generate alert message."""
        try:
            if status == SLOStatus.HEALTHY:
                return f"SLO {service}:{metric} is healthy (current: {current_value:.3f}, target: {target_value:.3f})"
            elif status == SLOStatus.WARNING:
                return f"SLO {service}:{metric} is in warning state (current: {current_value:.3f}, target: {target_value:.3f}, burn rate: {burn_rate:.3f})"
            elif status == SLOStatus.CRITICAL:
                return f"SLO {service}:{metric} is in critical state (current: {current_value:.3f}, target: {target_value:.3f}, burn rate: {burn_rate:.3f})"
            else:
                return f"SLO {service}:{metric} status unknown"
        except Exception as e:
            logger.error("Failed to generate alert message", error=str(e))
            return f"SLO {service}:{metric} alert message generation failed"
    
    async def _store_alert(self, alert: SLOAlert) -> None:
        """Store SLO alert in Redis."""
        try:
            alert_key = f"slo_alert:{alert.service}:{alert.metric}:{int(alert.timestamp.timestamp())}"
            
            await self.redis.hset(alert_key, mapping={
                'service': alert.service,
                'metric': alert.metric,
                'current_value': alert.current_value,
                'target_value': alert.target_value,
                'burn_rate': alert.burn_rate,
                'status': alert.status.value,
                'timestamp': alert.timestamp.isoformat(),
                'message': alert.message
            })
            
            await self.redis.expire(alert_key, 86400 * 7)  # 7 days TTL
            
        except Exception as e:
            logger.error("Failed to store SLO alert", error=str(e))
    
    async def get_slo_summary(self) -> Dict[str, Any]:
        """Get SLO summary across all services."""
        try:
            alerts = await self.check_all_slos()
            
            summary = {
                'total_slos': len(self.slo_targets),
                'healthy': 0,
                'warning': 0,
                'critical': 0,
                'unknown': 0,
                'services': {}
            }
            
            for alert in alerts:
                summary[alert.status.value] += 1
                
                if alert.service not in summary['services']:
                    summary['services'][alert.service] = {
                        'healthy': 0, 'warning': 0, 'critical': 0, 'unknown': 0
                    }
                
                summary['services'][alert.service][alert.status.value] += 1
            
            return summary
            
        except Exception as e:
            logger.error("Failed to get SLO summary", error=str(e))
            return {'error': str(e)}