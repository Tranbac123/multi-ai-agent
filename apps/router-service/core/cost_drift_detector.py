"""Cost Drift Detector for monitoring cost and latency drift."""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
import asyncio
import structlog
import statistics
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = structlog.get_logger(__name__)


class DriftType(Enum):
    """Types of cost/latency drift."""
    COST_DRIFT = "cost_drift"
    LATENCY_DRIFT = "latency_drift"
    BOTH = "both"


class DriftSeverity(Enum):
    """Drift severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DriftAlert:
    """Drift alert data."""
    tenant_id: str
    service_type: str
    drift_type: DriftType
    severity: DriftSeverity
    expected_value: float
    actual_value: float
    drift_percent: float
    threshold_percent: float
    message: str
    created_at: datetime


@dataclass
class CostLatencyMetrics:
    """Cost and latency metrics for analysis."""
    tenant_id: str
    service_type: str
    expected_cost_usd: float
    actual_cost_usd: float
    expected_latency_ms: float
    actual_latency_ms: float
    request_count: int
    timestamp: datetime


class CostDriftDetector:
    """Detects cost and latency drift from expected values."""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.drift_thresholds = {
            "cost_warning": 10.0,    # 10% cost increase
            "cost_critical": 25.0,   # 25% cost increase
            "latency_warning": 20.0, # 20% latency increase
            "latency_critical": 50.0 # 50% latency increase
        }
        self.drift_alerts: List[DriftAlert] = []
        self.monitoring_task: Optional[asyncio.Task] = None
        self._start_drift_monitoring()
    
    def _start_drift_monitoring(self):
        """Start background drift monitoring task."""
        self.monitoring_task = asyncio.create_task(self._monitor_drift())
    
    async def analyze_drift(self, tenant_id: str, service_type: str, 
                          time_window_hours: int = 24) -> Dict[str, Any]:
        """Analyze cost and latency drift for tenant service."""
        try:
            # Get metrics for analysis period
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=time_window_hours)
            
            # Get actual metrics
            actual_metrics = await self._get_actual_metrics(
                tenant_id, service_type, start_time, end_time
            )
            
            # Get expected metrics (from historical baseline)
            expected_metrics = await self._get_expected_metrics(
                tenant_id, service_type, start_time, end_time
            )
            
            if not actual_metrics or not expected_metrics:
                return {"drift_detected": False, "reason": "Insufficient data"}
            
            # Calculate drift
            cost_drift = self._calculate_cost_drift(actual_metrics, expected_metrics)
            latency_drift = self._calculate_latency_drift(actual_metrics, expected_metrics)
            
            # Determine if drift is significant
            drift_detected = (
                abs(cost_drift["drift_percent"]) > self.drift_thresholds["cost_warning"] or
                abs(latency_drift["drift_percent"]) > self.drift_thresholds["latency_warning"]
            )
            
            # Create drift alert if significant
            if drift_detected:
                await self._create_drift_alert(
                    tenant_id, service_type, cost_drift, latency_drift
                )
            
            return {
                "drift_detected": drift_detected,
                "cost_drift": cost_drift,
                "latency_drift": latency_drift,
                "analysis_period": {
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "duration_hours": time_window_hours
                }
            }
            
        except Exception as e:
            logger.error("Failed to analyze drift",
                        tenant_id=tenant_id,
                        service_type=service_type,
                        error=str(e))
            return {"drift_detected": False, "error": str(e)}
    
    async def _get_actual_metrics(self, tenant_id: str, service_type: str,
                                start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get actual cost and latency metrics from database."""
        try:
            query = text("""
                SELECT 
                    COUNT(*) as request_count,
                    AVG(cost_usd) as avg_cost_usd,
                    SUM(cost_usd) as total_cost_usd,
                    AVG(latency_ms) as avg_latency_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency_ms
                FROM request_metrics 
                WHERE tenant_id = :tenant_id 
                AND service_type = :service_type
                AND created_at >= :start_time 
                AND created_at < :end_time
            """)
            
            result = await self.db.execute(query, {
                "tenant_id": tenant_id,
                "service_type": service_type,
                "start_time": start_time,
                "end_time": end_time
            })
            
            row = result.fetchone()
            
            if not row or row.request_count == 0:
                return None
            
            return {
                "request_count": row.request_count,
                "avg_cost_usd": row.avg_cost_usd,
                "total_cost_usd": row.total_cost_usd,
                "avg_latency_ms": row.avg_latency_ms,
                "p95_latency_ms": row.p95_latency_ms
            }
            
        except Exception as e:
            logger.error("Failed to get actual metrics",
                        tenant_id=tenant_id,
                        service_type=service_type,
                        error=str(e))
            return None
    
    async def _get_expected_metrics(self, tenant_id: str, service_type: str,
                                  start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get expected metrics from historical baseline."""
        try:
            # Get historical data from the same time period (e.g., last week)
            historical_start = start_time - timedelta(days=7)
            historical_end = end_time - timedelta(days=7)
            
            query = text("""
                SELECT 
                    COUNT(*) as request_count,
                    AVG(cost_usd) as avg_cost_usd,
                    SUM(cost_usd) as total_cost_usd,
                    AVG(latency_ms) as avg_latency_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency_ms
                FROM request_metrics 
                WHERE tenant_id = :tenant_id 
                AND service_type = :service_type
                AND created_at >= :historical_start 
                AND created_at < :historical_end
            """)
            
            result = await self.db.execute(query, {
                "tenant_id": tenant_id,
                "service_type": service_type,
                "historical_start": historical_start,
                "historical_end": historical_end
            })
            
            row = result.fetchone()
            
            if not row or row.request_count == 0:
                # Fall back to global baseline if no historical data
                return await self._get_global_baseline(service_type)
            
            return {
                "request_count": row.request_count,
                "avg_cost_usd": row.avg_cost_usd,
                "total_cost_usd": row.total_cost_usd,
                "avg_latency_ms": row.avg_latency_ms,
                "p95_latency_ms": row.p95_latency_ms
            }
            
        except Exception as e:
            logger.error("Failed to get expected metrics",
                        tenant_id=tenant_id,
                        service_type=service_type,
                        error=str(e))
            return await self._get_global_baseline(service_type)
    
    async def _get_global_baseline(self, service_type: str) -> Dict[str, Any]:
        """Get global baseline metrics for service type."""
        try:
            # Get baseline from last 30 days
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=30)
            
            query = text("""
                SELECT 
                    COUNT(*) as request_count,
                    AVG(cost_usd) as avg_cost_usd,
                    AVG(latency_ms) as avg_latency_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency_ms
                FROM request_metrics 
                WHERE service_type = :service_type
                AND created_at >= :start_time 
                AND created_at < :end_time
            """)
            
            result = await self.db.execute(query, {
                "service_type": service_type,
                "start_time": start_time,
                "end_time": end_time
            })
            
            row = result.fetchone()
            
            if not row or row.request_count == 0:
                # Return default baseline
                return {
                    "request_count": 100,
                    "avg_cost_usd": 0.001,
                    "total_cost_usd": 0.1,
                    "avg_latency_ms": 100.0,
                    "p95_latency_ms": 200.0
                }
            
            return {
                "request_count": row.request_count,
                "avg_cost_usd": row.avg_cost_usd,
                "total_cost_usd": row.avg_cost_usd * 100,  # Estimate for comparison
                "avg_latency_ms": row.avg_latency_ms,
                "p95_latency_ms": row.p95_latency_ms
            }
            
        except Exception as e:
            logger.error("Failed to get global baseline",
                        service_type=service_type,
                        error=str(e))
            # Return default baseline
            return {
                "request_count": 100,
                "avg_cost_usd": 0.001,
                "total_cost_usd": 0.1,
                "avg_latency_ms": 100.0,
                "p95_latency_ms": 200.0
            }
    
    def _calculate_cost_drift(self, actual: Dict[str, Any], expected: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate cost drift between actual and expected metrics."""
        try:
            actual_cost = actual["avg_cost_usd"]
            expected_cost = expected["avg_cost_usd"]
            
            if expected_cost == 0:
                drift_percent = 0.0
            else:
                drift_percent = ((actual_cost - expected_cost) / expected_cost) * 100
            
            # Determine severity
            severity = self._determine_drift_severity(drift_percent, "cost")
            
            return {
                "expected_cost_usd": expected_cost,
                "actual_cost_usd": actual_cost,
                "drift_percent": drift_percent,
                "severity": severity.value,
                "threshold_exceeded": abs(drift_percent) > self.drift_thresholds["cost_warning"]
            }
            
        except Exception as e:
            logger.error("Failed to calculate cost drift", error=str(e))
            return {"drift_percent": 0.0, "severity": "low", "threshold_exceeded": False}
    
    def _calculate_latency_drift(self, actual: Dict[str, Any], expected: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate latency drift between actual and expected metrics."""
        try:
            actual_latency = actual["p95_latency_ms"]
            expected_latency = expected["p95_latency_ms"]
            
            if expected_latency == 0:
                drift_percent = 0.0
            else:
                drift_percent = ((actual_latency - expected_latency) / expected_latency) * 100
            
            # Determine severity
            severity = self._determine_drift_severity(drift_percent, "latency")
            
            return {
                "expected_latency_ms": expected_latency,
                "actual_latency_ms": actual_latency,
                "drift_percent": drift_percent,
                "severity": severity.value,
                "threshold_exceeded": abs(drift_percent) > self.drift_thresholds["latency_warning"]
            }
            
        except Exception as e:
            logger.error("Failed to calculate latency drift", error=str(e))
            return {"drift_percent": 0.0, "severity": "low", "threshold_exceeded": False}
    
    def _determine_drift_severity(self, drift_percent: float, metric_type: str) -> DriftSeverity:
        """Determine drift severity based on percentage and metric type."""
        abs_drift = abs(drift_percent)
        
        if metric_type == "cost":
            if abs_drift >= self.drift_thresholds["cost_critical"]:
                return DriftSeverity.CRITICAL
            elif abs_drift >= self.drift_thresholds["cost_warning"]:
                return DriftSeverity.HIGH
            elif abs_drift >= 5.0:
                return DriftSeverity.MEDIUM
            else:
                return DriftSeverity.LOW
        else:  # latency
            if abs_drift >= self.drift_thresholds["latency_critical"]:
                return DriftSeverity.CRITICAL
            elif abs_drift >= self.drift_thresholds["latency_warning"]:
                return DriftSeverity.HIGH
            elif abs_drift >= 10.0:
                return DriftSeverity.MEDIUM
            else:
                return DriftSeverity.LOW
    
    async def _create_drift_alert(self, tenant_id: str, service_type: str,
                                cost_drift: Dict[str, Any], latency_drift: Dict[str, Any]):
        """Create drift alert if significant drift is detected."""
        try:
            # Determine which metrics have significant drift
            cost_significant = cost_drift.get("threshold_exceeded", False)
            latency_significant = latency_drift.get("threshold_exceeded", False)
            
            if cost_significant and latency_significant:
                drift_type = DriftType.BOTH
                severity = max(
                    DriftSeverity(cost_drift["severity"]),
                    DriftSeverity(latency_drift["severity"])
                )
                message = f"Both cost ({cost_drift['drift_percent']:.1f}%) and latency ({latency_drift['drift_percent']:.1f}%) drift detected"
            elif cost_significant:
                drift_type = DriftType.COST_DRIFT
                severity = DriftSeverity(cost_drift["severity"])
                message = f"Cost drift detected: {cost_drift['drift_percent']:.1f}% increase"
            elif latency_significant:
                drift_type = DriftType.LATENCY_DRIFT
                severity = DriftSeverity(latency_drift["severity"])
                message = f"Latency drift detected: {latency_drift['drift_percent']:.1f}% increase"
            else:
                return  # No significant drift
            
            alert = DriftAlert(
                tenant_id=tenant_id,
                service_type=service_type,
                drift_type=drift_type,
                severity=severity,
                expected_value=cost_drift.get("expected_cost_usd", 0) if cost_significant else latency_drift.get("expected_latency_ms", 0),
                actual_value=cost_drift.get("actual_cost_usd", 0) if cost_significant else latency_drift.get("actual_latency_ms", 0),
                drift_percent=cost_drift.get("drift_percent", 0) if cost_significant else latency_drift.get("drift_percent", 0),
                threshold_percent=self.drift_thresholds["cost_warning"] if cost_significant else self.drift_thresholds["latency_warning"],
                message=message,
                created_at=datetime.now(timezone.utc)
            )
            
            self.drift_alerts.append(alert)
            
            logger.warning("Drift alert created",
                          tenant_id=tenant_id,
                          service_type=service_type,
                          drift_type=drift_type.value,
                          severity=severity.value,
                          drift_percent=alert.drift_percent)
            
        except Exception as e:
            logger.error("Failed to create drift alert",
                        tenant_id=tenant_id,
                        service_type=service_type,
                        error=str(e))
    
    async def _monitor_drift(self):
        """Background task to monitor drift across all tenants."""
        while True:
            try:
                await asyncio.sleep(3600)  # Check every hour
                
                # Get all active tenants and services
                tenants_services = await self._get_active_tenants_services()
                
                for tenant_id, service_types in tenants_services.items():
                    for service_type in service_types:
                        try:
                            await self.analyze_drift(tenant_id, service_type)
                        except Exception as e:
                            logger.error("Failed to analyze drift for tenant service",
                                        tenant_id=tenant_id,
                                        service_type=service_type,
                                        error=str(e))
                
            except Exception as e:
                logger.error("Error in drift monitoring", error=str(e))
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    async def _get_active_tenants_services(self) -> Dict[str, List[str]]:
        """Get active tenants and their services for drift monitoring."""
        try:
            # Get unique tenant-service combinations from last 24 hours
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=24)
            
            query = text("""
                SELECT DISTINCT tenant_id, service_type
                FROM request_metrics 
                WHERE created_at >= :start_time 
                AND created_at < :end_time
            """)
            
            result = await self.db.execute(query, {
                "start_time": start_time,
                "end_time": end_time
            })
            
            tenants_services = {}
            for row in result.fetchall():
                tenant_id = row.tenant_id
                service_type = row.service_type
                
                if tenant_id not in tenants_services:
                    tenants_services[tenant_id] = []
                tenants_services[tenant_id].append(service_type)
            
            return tenants_services
            
        except Exception as e:
            logger.error("Failed to get active tenants services", error=str(e))
            return {}
    
    async def get_drift_alerts(self, tenant_id: Optional[str] = None, 
                             limit: int = 100) -> List[DriftAlert]:
        """Get recent drift alerts."""
        try:
            alerts = self.drift_alerts
            
            if tenant_id:
                alerts = [alert for alert in alerts if alert.tenant_id == tenant_id]
            
            # Sort by creation time (newest first)
            alerts.sort(key=lambda x: x.created_at, reverse=True)
            
            return alerts[:limit]
            
        except Exception as e:
            logger.error("Failed to get drift alerts", error=str(e))
            return []
    
    async def shutdown(self):
        """Shutdown drift detector gracefully."""
        try:
            if self.monitoring_task:
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
            
            logger.info("Cost drift detector shutdown complete")
            
        except Exception as e:
            logger.error("Error during drift detector shutdown", error=str(e))
