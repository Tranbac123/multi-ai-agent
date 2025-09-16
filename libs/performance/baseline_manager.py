"""
Performance Baseline Manager

Manages performance baselines, establishes benchmarks, and tracks performance
regressions with comprehensive monitoring and alerting capabilities.
"""

import asyncio
import json
import statistics
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import structlog
from datetime import datetime, timedelta
from sqlalchemy import text, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from collections import defaultdict, deque

logger = structlog.get_logger(__name__)


class BaselineType(Enum):
    """Types of performance baselines."""
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    COST = "cost"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"
    CUSTOM = "custom"


class MetricAggregation(Enum):
    """Metric aggregation methods."""
    MEAN = "mean"
    MEDIAN = "median"
    P95 = "p95"
    P99 = "p99"
    MIN = "min"
    MAX = "max"
    COUNT = "count"


@dataclass
class PerformanceMetric:
    """Performance metric data point."""
    
    metric_id: str
    baseline_id: str
    timestamp: datetime
    value: float
    unit: str
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceBaseline:
    """Performance baseline definition."""
    
    baseline_id: str
    name: str
    description: str
    baseline_type: BaselineType
    service: str
    endpoint: Optional[str] = None
    tenant_id: Optional[str] = None
    aggregation_method: MetricAggregation = MetricAggregation.P95
    window_size_hours: int = 24
    sample_size: int = 1000
    threshold_percentage: float = 10.0  # 10% regression threshold
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BaselineResult:
    """Baseline calculation result."""
    
    baseline_id: str
    calculated_value: float
    baseline_value: float
    regression_percentage: float
    is_regression: bool
    confidence_level: float
    sample_size: int
    window_start: datetime
    window_end: datetime
    calculated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceAlert:
    """Performance regression alert."""
    
    alert_id: str
    baseline_id: str
    alert_type: str
    severity: str
    regression_percentage: float
    current_value: float
    baseline_value: float
    threshold_percentage: float
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    is_resolved: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class PerformanceBaselineManager:
    """Manages performance baselines and regression detection."""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.baseline_cache: Dict[str, PerformanceBaseline] = {}
        self.metric_buffer: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        
        logger.info("Performance baseline manager initialized")
    
    async def create_baseline(
        self,
        name: str,
        description: str,
        baseline_type: BaselineType,
        service: str,
        endpoint: Optional[str] = None,
        tenant_id: Optional[str] = None,
        aggregation_method: MetricAggregation = MetricAggregation.P95,
        window_size_hours: int = 24,
        sample_size: int = 1000,
        threshold_percentage: float = 10.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PerformanceBaseline:
        """Create a new performance baseline."""
        
        baseline_id = f"baseline_{service}_{baseline_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        baseline = PerformanceBaseline(
            baseline_id=baseline_id,
            name=name,
            description=description,
            baseline_type=baseline_type,
            service=service,
            endpoint=endpoint,
            tenant_id=tenant_id,
            aggregation_method=aggregation_method,
            window_size_hours=window_size_hours,
            sample_size=sample_size,
            threshold_percentage=threshold_percentage,
            metadata=metadata or {}
        )
        
        await self._store_baseline(baseline)
        self.baseline_cache[baseline_id] = baseline
        
        logger.info("Performance baseline created", 
                   baseline_id=baseline_id,
                   name=name,
                   service=service,
                   baseline_type=baseline_type.value)
        
        return baseline
    
    async def _store_baseline(self, baseline: PerformanceBaseline):
        """Store baseline in database."""
        
        query = """
        INSERT INTO performance_baselines (
            baseline_id, name, description, baseline_type, service, endpoint,
            tenant_id, aggregation_method, window_size_hours, sample_size,
            threshold_percentage, is_active, created_at, updated_at, metadata
        ) VALUES (
            :baseline_id, :name, :description, :baseline_type, :service, :endpoint,
            :tenant_id, :aggregation_method, :window_size_hours, :sample_size,
            :threshold_percentage, :is_active, :created_at, :updated_at, :metadata
        )
        """
        
        await self.db_session.execute(text(query), {
            "baseline_id": baseline.baseline_id,
            "name": baseline.name,
            "description": baseline.description,
            "baseline_type": baseline.baseline_type.value,
            "service": baseline.service,
            "endpoint": baseline.endpoint,
            "tenant_id": baseline.tenant_id,
            "aggregation_method": baseline.aggregation_method.value,
            "window_size_hours": baseline.window_size_hours,
            "sample_size": baseline.sample_size,
            "threshold_percentage": baseline.threshold_percentage,
            "is_active": baseline.is_active,
            "created_at": baseline.created_at,
            "updated_at": baseline.updated_at,
            "metadata": json.dumps(baseline.metadata)
        })
        
        await self.db_session.commit()
    
    async def record_metric(
        self,
        baseline_id: str,
        value: float,
        unit: str,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record a performance metric."""
        
        metric_id = f"metric_{baseline_id}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        metric = PerformanceMetric(
            metric_id=metric_id,
            baseline_id=baseline_id,
            timestamp=datetime.now(),
            value=value,
            unit=unit,
            tags=tags or {},
            metadata=metadata or {}
        )
        
        # Add to buffer for real-time processing
        self.metric_buffer[baseline_id].append(metric)
        
        # Store in database
        await self._store_metric(metric)
        
        # Check for immediate regression if we have enough data
        await self._check_immediate_regression(baseline_id)
    
    async def _store_metric(self, metric: PerformanceMetric):
        """Store metric in database."""
        
        query = """
        INSERT INTO performance_metrics (
            metric_id, baseline_id, timestamp, value, unit, tags, metadata
        ) VALUES (
            :metric_id, :baseline_id, :timestamp, :value, :unit, :tags, :metadata
        )
        """
        
        await self.db_session.execute(text(query), {
            "metric_id": metric.metric_id,
            "baseline_id": metric.baseline_id,
            "timestamp": metric.timestamp,
            "value": metric.value,
            "unit": metric.unit,
            "tags": json.dumps(metric.tags),
            "metadata": json.dumps(metric.metadata)
        })
        
        await self.db_session.commit()
    
    async def calculate_baseline(
        self,
        baseline_id: str,
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None
    ) -> BaselineResult:
        """Calculate baseline from historical data."""
        
        baseline = await self.get_baseline(baseline_id)
        if not baseline:
            raise ValueError(f"Baseline not found: {baseline_id}")
        
        # Determine time window
        if not window_end:
            window_end = datetime.now()
        if not window_start:
            window_start = window_end - timedelta(hours=baseline.window_size_hours)
        
        # Get metrics for the window
        metrics = await self._get_metrics_for_window(
            baseline_id, window_start, window_end, baseline.sample_size
        )
        
        if not metrics:
            raise ValueError(f"No metrics found for baseline {baseline_id} in time window")
        
        # Calculate aggregated value
        values = [metric.value for metric in metrics]
        calculated_value = self._aggregate_values(values, baseline.aggregation_method)
        
        # Get stored baseline value (from previous calculation)
        stored_baseline_value = await self._get_stored_baseline_value(baseline_id)
        
        # Calculate regression percentage
        if stored_baseline_value > 0:
            regression_percentage = ((calculated_value - stored_baseline_value) / stored_baseline_value) * 100
        else:
            regression_percentage = 0.0
        
        # Determine if this is a regression
        is_regression = abs(regression_percentage) > baseline.threshold_percentage
        
        # Calculate confidence level based on sample size and variance
        confidence_level = self._calculate_confidence_level(values, len(metrics))
        
        result = BaselineResult(
            baseline_id=baseline_id,
            calculated_value=calculated_value,
            baseline_value=stored_baseline_value,
            regression_percentage=regression_percentage,
            is_regression=is_regression,
            confidence_level=confidence_level,
            sample_size=len(metrics),
            window_start=window_start,
            window_end=window_end
        )
        
        # Store the calculated baseline value
        await self._update_baseline_value(baseline_id, calculated_value)
        
        logger.info("Baseline calculated", 
                   baseline_id=baseline_id,
                   calculated_value=calculated_value,
                   regression_percentage=regression_percentage,
                   is_regression=is_regression,
                   confidence_level=confidence_level)
        
        return result
    
    def _aggregate_values(self, values: List[float], aggregation_method: MetricAggregation) -> float:
        """Aggregate values using the specified method."""
        
        if not values:
            return 0.0
        
        if aggregation_method == MetricAggregation.MEAN:
            return statistics.mean(values)
        elif aggregation_method == MetricAggregation.MEDIAN:
            return statistics.median(values)
        elif aggregation_method == MetricAggregation.P95:
            return self._percentile(values, 95)
        elif aggregation_method == MetricAggregation.P99:
            return self._percentile(values, 99)
        elif aggregation_method == MetricAggregation.MIN:
            return min(values)
        elif aggregation_method == MetricAggregation.MAX:
            return max(values)
        elif aggregation_method == MetricAggregation.COUNT:
            return len(values)
        else:
            return statistics.mean(values)  # Default to mean
    
    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile of values."""
        
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        index = min(index, len(sorted_values) - 1)
        
        return sorted_values[index]
    
    def _calculate_confidence_level(self, values: List[float], sample_size: int) -> float:
        """Calculate confidence level based on sample size and variance."""
        
        if sample_size < 10:
            return 0.5  # Low confidence for small samples
        
        if sample_size < 100:
            return 0.7  # Medium confidence
        
        # High confidence for large samples with low variance
        if len(values) > 1:
            variance = statistics.variance(values)
            mean_value = statistics.mean(values)
            coefficient_of_variation = variance / mean_value if mean_value > 0 else 1.0
            
            # Lower variance = higher confidence
            confidence = max(0.5, min(1.0, 1.0 - (coefficient_of_variation / 2)))
            return confidence
        
        return 0.8  # Default high confidence
    
    async def _get_metrics_for_window(
        self,
        baseline_id: str,
        window_start: datetime,
        window_end: datetime,
        limit: int
    ) -> List[PerformanceMetric]:
        """Get metrics for a time window."""
        
        query = """
        SELECT * FROM performance_metrics 
        WHERE baseline_id = :baseline_id 
        AND timestamp >= :window_start 
        AND timestamp <= :window_end
        ORDER BY timestamp DESC
        LIMIT :limit
        """
        
        result = await self.db_session.execute(text(query), {
            "baseline_id": baseline_id,
            "window_start": window_start,
            "window_end": window_end,
            "limit": limit
        })
        
        rows = result.fetchall()
        return [self._row_to_performance_metric(row) for row in rows]
    
    async def _get_stored_baseline_value(self, baseline_id: str) -> float:
        """Get stored baseline value from previous calculations."""
        
        query = """
        SELECT baseline_value FROM baseline_calculations 
        WHERE baseline_id = :baseline_id 
        ORDER BY calculated_at DESC 
        LIMIT 1
        """
        
        result = await self.db_session.execute(text(query), {"baseline_id": baseline_id})
        row = result.fetchone()
        
        return row.baseline_value if row else 0.0
    
    async def _update_baseline_value(self, baseline_id: str, value: float):
        """Update stored baseline value."""
        
        query = """
        INSERT INTO baseline_calculations (
            baseline_id, calculated_value, baseline_value, calculated_at
        ) VALUES (
            :baseline_id, :calculated_value, :baseline_value, :calculated_at
        )
        """
        
        await self.db_session.execute(text(query), {
            "baseline_id": baseline_id,
            "calculated_value": value,
            "baseline_value": value,
            "calculated_at": datetime.now()
        })
        
        await self.db_session.commit()
    
    async def _check_immediate_regression(self, baseline_id: str):
        """Check for immediate regression using buffered metrics."""
        
        baseline = self.baseline_cache.get(baseline_id)
        if not baseline:
            baseline = await self.get_baseline(baseline_id)
            if baseline:
                self.baseline_cache[baseline_id] = baseline
        
        if not baseline:
            return
        
        # Get recent metrics from buffer
        recent_metrics = list(self.metric_buffer[baseline_id])[-100:]  # Last 100 metrics
        
        if len(recent_metrics) < 10:  # Need minimum sample size
            return
        
        # Calculate current performance
        values = [metric.value for metric in recent_metrics]
        current_value = self._aggregate_values(values, baseline.aggregation_method)
        
        # Get baseline value
        baseline_value = await self._get_stored_baseline_value(baseline_id)
        
        if baseline_value > 0:
            regression_percentage = ((current_value - baseline_value) / baseline_value) * 100
            
            if abs(regression_percentage) > baseline.threshold_percentage:
                await self._trigger_regression_alert(
                    baseline_id, regression_percentage, current_value, baseline_value, baseline.threshold_percentage
                )
    
    async def _trigger_regression_alert(
        self,
        baseline_id: str,
        regression_percentage: float,
        current_value: float,
        baseline_value: float,
        threshold_percentage: float
    ):
        """Trigger performance regression alert."""
        
        alert_id = f"alert_{baseline_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        alert = PerformanceAlert(
            alert_id=alert_id,
            baseline_id=baseline_id,
            alert_type="performance_regression",
            severity="high" if abs(regression_percentage) > threshold_percentage * 2 else "medium",
            regression_percentage=regression_percentage,
            current_value=current_value,
            baseline_value=baseline_value,
            threshold_percentage=threshold_percentage,
            triggered_at=datetime.now()
        )
        
        await self._store_alert(alert)
        
        logger.warning("Performance regression detected", 
                      baseline_id=baseline_id,
                      regression_percentage=regression_percentage,
                      current_value=current_value,
                      baseline_value=baseline_value)
    
    async def _store_alert(self, alert: PerformanceAlert):
        """Store performance alert."""
        
        query = """
        INSERT INTO performance_alerts (
            alert_id, baseline_id, alert_type, severity, regression_percentage,
            current_value, baseline_value, threshold_percentage, triggered_at,
            resolved_at, is_resolved, metadata
        ) VALUES (
            :alert_id, :baseline_id, :alert_type, :severity, :regression_percentage,
            :current_value, :baseline_value, :threshold_percentage, :triggered_at,
            :resolved_at, :is_resolved, :metadata
        )
        """
        
        await self.db_session.execute(text(query), {
            "alert_id": alert.alert_id,
            "baseline_id": alert.baseline_id,
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "regression_percentage": alert.regression_percentage,
            "current_value": alert.current_value,
            "baseline_value": alert.baseline_value,
            "threshold_percentage": alert.threshold_percentage,
            "triggered_at": alert.triggered_at,
            "resolved_at": alert.resolved_at,
            "is_resolved": alert.is_resolved,
            "metadata": json.dumps(alert.metadata)
        })
        
        await self.db_session.commit()
    
    async def get_baseline(self, baseline_id: str) -> Optional[PerformanceBaseline]:
        """Get baseline by ID."""
        
        # Check cache first
        if baseline_id in self.baseline_cache:
            return self.baseline_cache[baseline_id]
        
        query = """
        SELECT * FROM performance_baselines 
        WHERE baseline_id = :baseline_id AND is_active = true
        """
        
        result = await self.db_session.execute(text(query), {"baseline_id": baseline_id})
        row = result.fetchone()
        
        if not row:
            return None
        
        baseline = self._row_to_performance_baseline(row)
        self.baseline_cache[baseline_id] = baseline
        
        return baseline
    
    async def get_baselines(
        self,
        service: Optional[str] = None,
        baseline_type: Optional[BaselineType] = None,
        tenant_id: Optional[str] = None,
        is_active: bool = True
    ) -> List[PerformanceBaseline]:
        """Get baselines with filters."""
        
        query = """
        SELECT * FROM performance_baselines 
        WHERE is_active = :is_active
        """
        
        params = {"is_active": is_active}
        
        if service:
            query += " AND service = :service"
            params["service"] = service
        
        if baseline_type:
            query += " AND baseline_type = :baseline_type"
            params["baseline_type"] = baseline_type.value
        
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = tenant_id
        
        query += " ORDER BY created_at DESC"
        
        result = await self.db_session.execute(text(query), params)
        rows = result.fetchall()
        
        return [self._row_to_performance_baseline(row) for row in rows]
    
    async def get_performance_alerts(
        self,
        baseline_id: Optional[str] = None,
        severity: Optional[str] = None,
        is_resolved: Optional[bool] = None,
        limit: int = 100
    ) -> List[PerformanceAlert]:
        """Get performance alerts with filters."""
        
        query = """
        SELECT * FROM performance_alerts 
        WHERE 1=1
        """
        
        params = {}
        
        if baseline_id:
            query += " AND baseline_id = :baseline_id"
            params["baseline_id"] = baseline_id
        
        if severity:
            query += " AND severity = :severity"
            params["severity"] = severity
        
        if is_resolved is not None:
            query += " AND is_resolved = :is_resolved"
            params["is_resolved"] = is_resolved
        
        query += " ORDER BY triggered_at DESC LIMIT :limit"
        params["limit"] = limit
        
        result = await self.db_session.execute(text(query), params)
        rows = result.fetchall()
        
        return [self._row_to_performance_alert(row) for row in rows]
    
    def _row_to_performance_baseline(self, row) -> PerformanceBaseline:
        """Convert database row to PerformanceBaseline object."""
        
        return PerformanceBaseline(
            baseline_id=row.baseline_id,
            name=row.name,
            description=row.description,
            baseline_type=BaselineType(row.baseline_type),
            service=row.service,
            endpoint=row.endpoint,
            tenant_id=row.tenant_id,
            aggregation_method=MetricAggregation(row.aggregation_method),
            window_size_hours=row.window_size_hours,
            sample_size=row.sample_size,
            threshold_percentage=row.threshold_percentage,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
            metadata=json.loads(row.metadata) if row.metadata else {}
        )
    
    def _row_to_performance_metric(self, row) -> PerformanceMetric:
        """Convert database row to PerformanceMetric object."""
        
        return PerformanceMetric(
            metric_id=row.metric_id,
            baseline_id=row.baseline_id,
            timestamp=row.timestamp,
            value=row.value,
            unit=row.unit,
            tags=json.loads(row.tags) if row.tags else {},
            metadata=json.loads(row.metadata) if row.metadata else {}
        )
    
    def _row_to_performance_alert(self, row) -> PerformanceAlert:
        """Convert database row to PerformanceAlert object."""
        
        return PerformanceAlert(
            alert_id=row.alert_id,
            baseline_id=row.baseline_id,
            alert_type=row.alert_type,
            severity=row.severity,
            regression_percentage=row.regression_percentage,
            current_value=row.current_value,
            baseline_value=row.baseline_value,
            threshold_percentage=row.threshold_percentage,
            triggered_at=row.triggered_at,
            resolved_at=row.resolved_at,
            is_resolved=row.is_resolved,
            metadata=json.loads(row.metadata) if row.metadata else {}
        )
    
    async def get_performance_statistics(self) -> Dict[str, Any]:
        """Get performance statistics."""
        
        # Baseline statistics
        baseline_query = """
        SELECT 
            COUNT(*) as total_baselines,
            COUNT(CASE WHEN is_active = true THEN 1 END) as active_baselines,
            COUNT(DISTINCT service) as services_monitored,
            COUNT(DISTINCT baseline_type) as baseline_types
        FROM performance_baselines
        """
        
        baseline_result = await self.db_session.execute(text(baseline_query))
        baseline_stats = baseline_result.fetchone()
        
        # Alert statistics
        alert_query = """
        SELECT 
            COUNT(*) as total_alerts,
            COUNT(CASE WHEN is_resolved = false THEN 1 END) as active_alerts,
            COUNT(CASE WHEN severity = 'high' THEN 1 END) as high_severity_alerts,
            COUNT(CASE WHEN severity = 'medium' THEN 1 END) as medium_severity_alerts
        FROM performance_alerts
        """
        
        alert_result = await self.db_session.execute(text(alert_query))
        alert_stats = alert_result.fetchone()
        
        return {
            "baseline_statistics": {
                "total_baselines": baseline_stats.total_baselines,
                "active_baselines": baseline_stats.active_baselines,
                "services_monitored": baseline_stats.services_monitored,
                "baseline_types": baseline_stats.baseline_types
            },
            "alert_statistics": {
                "total_alerts": alert_stats.total_alerts,
                "active_alerts": alert_stats.active_alerts,
                "high_severity_alerts": alert_stats.high_severity_alerts,
                "medium_severity_alerts": alert_stats.medium_severity_alerts
            },
            "timestamp": datetime.now().isoformat()
        }
