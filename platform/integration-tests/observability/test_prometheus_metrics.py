"""
Tests for Prometheus metrics assertions and SLO monitoring.

This module tests:
- SLO metric calculations and thresholds
- Error rate monitoring
- Latency percentile tracking
- Custom metric assertions in E2E tests
- Grafana dashboard metric validation
"""

import time
import pytest
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
from unittest.mock import Mock, AsyncMock


class MetricType(Enum):
    """Types of Prometheus metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class SLOTarget:
    """SLO target configuration."""
    name: str
    target_value: float
    measurement_window_minutes: int
    error_budget_percentage: float


@dataclass
class SLOStatus:
    """Current SLO status."""
    name: str
    current_value: float
    target_value: float
    status: str  # "healthy", "warning", "critical"
    error_budget_remaining: float
    measurement_window_minutes: int


@dataclass
class MetricSample:
    """Individual metric sample."""
    name: str
    value: float
    labels: Dict[str, str]
    timestamp: float


@dataclass
class SLOMonitor:
    """SLO monitoring service."""
    targets: Dict[str, SLOTarget]
    current_metrics: Dict[str, List[MetricSample]]
    
    def __post_init__(self):
        if not hasattr(self, 'current_metrics'):
            self.current_metrics = {}


class PrometheusMetricsCollector:
    """Mock Prometheus metrics collector."""
    
    def __init__(self):
        self.metrics: Dict[str, List[MetricSample]] = {}
        self.slo_monitor = SLOMonitor(targets={}, current_metrics={})
        self._setup_default_slos()
    
    def _setup_default_slos(self):
        """Setup default SLO targets."""
        self.slo_monitor.targets = {
            "error_rate": SLOTarget(
                name="error_rate",
                target_value=1.0,  # 1% error rate
                measurement_window_minutes=5,
                error_budget_percentage=5.0
            ),
            "avg_latency": SLOTarget(
                name="avg_latency",
                target_value=200.0,  # 200ms average latency
                measurement_window_minutes=5,
                error_budget_percentage=10.0
            ),
            "p95_latency": SLOTarget(
                name="p95_latency",
                target_value=500.0,  # 500ms p95 latency
                measurement_window_minutes=5,
                error_budget_percentage=10.0
            )
        }
    
    def record_request(self, endpoint: str, response_time_ms: float, 
                      status_code: int, method: str = "GET"):
        """Record a request metric."""
        timestamp = time.time()
        
        # Record response time
        if "response_time" not in self.metrics:
            self.metrics["response_time"] = []
        self.metrics["response_time"].append(MetricSample(
            name="response_time",
            value=response_time_ms,
            labels={
                "endpoint": endpoint,
                "method": method,
                "status_code": str(status_code)
            },
            timestamp=timestamp
        ))
        
        # Record error if status >= 400
        if status_code >= 400:
            if "error_count" not in self.metrics:
                self.metrics["error_count"] = []
            self.metrics["error_count"].append(MetricSample(
                name="error_count",
                value=1.0,
                labels={
                    "endpoint": endpoint,
                    "method": method,
                    "status_code": str(status_code)
                },
                timestamp=timestamp
            ))
        
        # Record total requests
        if "total_requests" not in self.metrics:
            self.metrics["total_requests"] = []
        self.metrics["total_requests"].append(MetricSample(
            name="total_requests",
            value=1.0,
            labels={
                "endpoint": endpoint,
                "method": method
            },
            timestamp=timestamp
        ))
    
    def calculate_error_rate(self, endpoint: str = None, 
                           window_minutes: int = 5) -> float:
        """Calculate error rate for an endpoint or globally."""
        now = time.time()
        window_start = now - (window_minutes * 60)
        
        total_requests = 0
        errors = 0
        
        # Count total requests
        if "total_requests" in self.metrics:
            for sample in self.metrics["total_requests"]:
                if sample.timestamp >= window_start:
                    if endpoint is None or sample.labels.get("endpoint") == endpoint:
                        total_requests += 1
        
        # Count errors
        if "error_count" in self.metrics:
            for sample in self.metrics["error_count"]:
                if sample.timestamp >= window_start:
                    if endpoint is None or sample.labels.get("endpoint") == endpoint:
                        errors += 1
        
        return (errors / total_requests * 100) if total_requests > 0 else 0.0
    
    def calculate_avg_latency(self, endpoint: str = None,
                            window_minutes: int = 5) -> float:
        """Calculate average latency for an endpoint or globally."""
        now = time.time()
        window_start = now - (window_minutes * 60)
        
        latencies = []
        if "response_time" in self.metrics:
            for sample in self.metrics["response_time"]:
                if sample.timestamp >= window_start:
                    if endpoint is None or sample.labels.get("endpoint") == endpoint:
                        latencies.append(sample.value)
        
        return sum(latencies) / len(latencies) if latencies else 0.0
    
    def calculate_p95_latency(self, endpoint: str = None,
                            window_minutes: int = 5) -> float:
        """Calculate p95 latency for an endpoint or globally."""
        now = time.time()
        window_start = now - (window_minutes * 60)
        
        latencies = []
        if "response_time" in self.metrics:
            for sample in self.metrics["response_time"]:
                if sample.timestamp >= window_start:
                    if endpoint is None or sample.labels.get("endpoint") == endpoint:
                        latencies.append(sample.value)
        
        if not latencies:
            return 0.0
        
        latencies.sort()
        p95_index = int(len(latencies) * 0.95)
        return latencies[p95_index] if p95_index < len(latencies) else latencies[-1]
    
    def check_slo_status(self, slo_name: str) -> SLOStatus:
        """Check current SLO status."""
        if slo_name not in self.slo_monitor.targets:
            raise ValueError(f"SLO target '{slo_name}' not found")
        
        target = self.slo_monitor.targets[slo_name]
        
        if slo_name == "error_rate":
            current_value = self.calculate_error_rate()
        elif slo_name == "avg_latency":
            current_value = self.calculate_avg_latency()
        elif slo_name == "p95_latency":
            current_value = self.calculate_p95_latency()
        else:
            current_value = 0.0
        
        # Determine status
        if current_value <= target.target_value:
            status = "healthy"
        elif current_value <= target.target_value * 1.5:
            status = "warning"
        else:
            status = "critical"
        
        # Calculate error budget (simplified)
        error_budget_remaining = max(0, target.error_budget_percentage - 
                                   abs(current_value - target.target_value))
        
        return SLOStatus(
            name=slo_name,
            current_value=current_value,
            target_value=target.target_value,
            status=status,
            error_budget_remaining=error_budget_remaining,
            measurement_window_minutes=target.measurement_window_minutes
        )
    
    def assert_slo_healthy(self, slo_name: str):
        """Assert that an SLO is healthy."""
        status = self.check_slo_status(slo_name)
        assert status.status == "healthy", \
            f"SLO '{slo_name}' is {status.status}: {status.current_value} vs target {status.target_value}"
    
    def assert_error_rate_below(self, threshold: float, endpoint: str = None):
        """Assert error rate is below threshold."""
        error_rate = self.calculate_error_rate(endpoint)
        assert error_rate < threshold, \
            f"Error rate {error_rate}% exceeds threshold {threshold}%"
    
    def assert_latency_below(self, threshold: float, percentile: str = "avg", 
                           endpoint: str = None):
        """Assert latency is below threshold."""
        if percentile == "avg":
            latency = self.calculate_avg_latency(endpoint)
        elif percentile == "p95":
            latency = self.calculate_p95_latency(endpoint)
        else:
            raise ValueError(f"Unsupported percentile: {percentile}")
        
        assert latency < threshold, \
            f"{percentile} latency {latency}ms exceeds threshold {threshold}ms"


class GrafanaDashboardValidator:
    """Mock Grafana dashboard validator."""
    
    def __init__(self, metrics_collector: PrometheusMetricsCollector):
        self.metrics_collector = metrics_collector
        self.dashboard_configs = {}
        self._setup_default_dashboards()
    
    def _setup_default_dashboards(self):
        """Setup default dashboard configurations."""
        self.dashboard_configs = {
            "api_performance": {
                "panels": [
                    {
                        "title": "Error Rate",
                        "metric": "error_rate",
                        "threshold": 1.0,
                        "unit": "%"
                    },
                    {
                        "title": "Average Latency",
                        "metric": "avg_latency",
                        "threshold": 200.0,
                        "unit": "ms"
                    },
                    {
                        "title": "P95 Latency",
                        "metric": "p95_latency",
                        "threshold": 500.0,
                        "unit": "ms"
                    }
                ]
            }
        }
    
    def validate_dashboard_metrics(self, dashboard_name: str) -> Dict[str, Any]:
        """Validate that dashboard metrics are within thresholds."""
        if dashboard_name not in self.dashboard_configs:
            raise ValueError(f"Dashboard '{dashboard_name}' not found")
        
        dashboard = self.dashboard_configs[dashboard_name]
        results = {
            "dashboard": dashboard_name,
            "panels": [],
            "overall_status": "healthy"
        }
        
        for panel in dashboard["panels"]:
            metric = panel["metric"]
            threshold = panel["threshold"]
            
            if metric == "error_rate":
                current_value = self.metrics_collector.calculate_error_rate()
            elif metric == "avg_latency":
                current_value = self.metrics_collector.calculate_avg_latency()
            elif metric == "p95_latency":
                current_value = self.metrics_collector.calculate_p95_latency()
            else:
                current_value = 0.0
            
            panel_status = "healthy" if current_value <= threshold else "warning"
            if current_value > threshold * 1.5:
                panel_status = "critical"
                results["overall_status"] = "critical"
            elif current_value > threshold and results["overall_status"] == "healthy":
                results["overall_status"] = "warning"
            
            results["panels"].append({
                "title": panel["title"],
                "metric": metric,
                "current_value": current_value,
                "threshold": threshold,
                "status": panel_status
            })
        
        return results


@pytest.fixture
def metrics_collector():
    """Fixture for Prometheus metrics collector."""
    return PrometheusMetricsCollector()


@pytest.fixture
def dashboard_validator(metrics_collector):
    """Fixture for Grafana dashboard validator."""
    return GrafanaDashboardValidator(metrics_collector)


class TestPrometheusMetrics:
    """Test Prometheus metrics collection and SLO monitoring."""
    
    def test_metrics_collection(self, metrics_collector):
        """Test basic metrics collection."""
        # Record some requests
        metrics_collector.record_request("/api/query", 150.0, 200, "GET")
        metrics_collector.record_request("/api/query", 250.0, 200, "GET")
        metrics_collector.record_request("/api/query", 100.0, 500, "GET")  # Error
        
        # Check metrics were recorded
        assert "response_time" in metrics_collector.metrics
        assert "error_count" in metrics_collector.metrics
        assert "total_requests" in metrics_collector.metrics
        
        # Check counts
        assert len(metrics_collector.metrics["response_time"]) == 3
        assert len(metrics_collector.metrics["error_count"]) == 1
        assert len(metrics_collector.metrics["total_requests"]) == 3
    
    def test_error_rate_calculation(self, metrics_collector):
        """Test error rate calculation."""
        # Record requests with different status codes
        for i in range(10):
            status_code = 500 if i < 2 else 200  # 20% error rate
            metrics_collector.record_request("/api/query", 150.0, status_code)
        
        error_rate = metrics_collector.calculate_error_rate("/api/query")
        assert error_rate == 20.0  # 2 errors out of 10 requests
    
    def test_latency_calculation(self, metrics_collector):
        """Test latency calculation."""
        # Record requests with different latencies
        latencies = [100.0, 200.0, 300.0, 400.0, 500.0]
        for latency in latencies:
            metrics_collector.record_request("/api/query", latency, 200)
        
        avg_latency = metrics_collector.calculate_avg_latency("/api/query")
        p95_latency = metrics_collector.calculate_p95_latency("/api/query")
        
        assert avg_latency == 300.0  # Average of latencies
        assert p95_latency == 500.0  # 95th percentile
    
    def test_slo_status_healthy(self, metrics_collector):
        """Test SLO status when healthy."""
        # Record healthy requests
        for i in range(100):
            metrics_collector.record_request("/api/query", 150.0, 200)
        
        error_rate_status = metrics_collector.check_slo_status("error_rate")
        latency_status = metrics_collector.check_slo_status("avg_latency")
        
        assert error_rate_status.status == "healthy"
        assert error_rate_status.current_value == 0.0  # No errors
        assert latency_status.status == "healthy"
        assert latency_status.current_value == 150.0
    
    def test_slo_status_warning(self, metrics_collector):
        """Test SLO status when in warning."""
        # Record requests that exceed latency target
        for i in range(100):
            latency = 300.0  # Exceeds 200ms target
            metrics_collector.record_request("/api/query", latency, 200)
        
        latency_status = metrics_collector.check_slo_status("avg_latency")
        assert latency_status.status == "warning"
        assert latency_status.current_value == 300.0
    
    def test_slo_status_critical(self, metrics_collector):
        """Test SLO status when critical."""
        # Record high error rate
        for i in range(100):
            status_code = 500 if i < 10 else 200  # 10% error rate
            metrics_collector.record_request("/api/query", 150.0, status_code)
        
        error_rate_status = metrics_collector.check_slo_status("error_rate")
        assert error_rate_status.status == "critical"
        assert error_rate_status.current_value == 10.0  # 10% error rate
    
    def test_slo_assertions(self, metrics_collector):
        """Test SLO assertion methods."""
        # Record healthy requests
        for i in range(100):
            metrics_collector.record_request("/api/query", 150.0, 200)
        
        # These should not raise
        metrics_collector.assert_slo_healthy("error_rate")
        metrics_collector.assert_error_rate_below(1.0)
        metrics_collector.assert_latency_below(200.0, "avg")
        metrics_collector.assert_latency_below(300.0, "p95")
    
    def test_slo_assertions_fail(self, metrics_collector):
        """Test SLO assertion methods fail when thresholds exceeded."""
        # Record high error rate
        for i in range(100):
            status_code = 500 if i < 5 else 200  # 5% error rate
            metrics_collector.record_request("/api/query", 150.0, status_code)
        
        # These should raise
        with pytest.raises(AssertionError):
            metrics_collector.assert_error_rate_below(1.0)
        
        with pytest.raises(AssertionError):
            metrics_collector.assert_slo_healthy("error_rate")


class TestGrafanaDashboardValidation:
    """Test Grafana dashboard metric validation."""
    
    def test_dashboard_validation_healthy(self, dashboard_validator, metrics_collector):
        """Test dashboard validation when metrics are healthy."""
        # Record healthy metrics
        for i in range(100):
            metrics_collector.record_request("/api/query", 150.0, 200)
        
        results = dashboard_validator.validate_dashboard_metrics("api_performance")
        
        assert results["overall_status"] == "healthy"
        assert len(results["panels"]) == 3
        
        for panel in results["panels"]:
            assert panel["status"] == "healthy"
    
    def test_dashboard_validation_warning(self, dashboard_validator, metrics_collector):
        """Test dashboard validation when metrics are in warning."""
        # Record metrics that exceed targets but not critically
        for i in range(100):
            latency = 250.0  # Exceeds 200ms target but within 1.5x
            metrics_collector.record_request("/api/query", latency, 200)
        
        results = dashboard_validator.validate_dashboard_metrics("api_performance")
        
        assert results["overall_status"] == "warning"
        
        # Check latency panel is in warning
        latency_panel = next(p for p in results["panels"] if p["metric"] == "avg_latency")
        assert latency_panel["status"] == "warning"
    
    def test_dashboard_validation_critical(self, dashboard_validator, metrics_collector):
        """Test dashboard validation when metrics are critical."""
        # Record critical metrics
        for i in range(100):
            status_code = 500 if i < 10 else 200  # 10% error rate
            metrics_collector.record_request("/api/query", 150.0, status_code)
        
        results = dashboard_validator.validate_dashboard_metrics("api_performance")
        
        assert results["overall_status"] == "critical"
        
        # Check error rate panel is critical
        error_panel = next(p for p in results["panels"] if p["metric"] == "error_rate")
        assert error_panel["status"] == "critical"


class TestE2EObservabilityIntegration:
    """Test observability integration in E2E scenarios."""
    
    @pytest.mark.asyncio
    async def test_e2e_workflow_with_metrics(self, metrics_collector):
        """Test E2E workflow with metrics collection."""
        # Simulate a complete workflow execution
        workflow_steps = [
            ("/api/query", 100.0, 200),
            ("/api/process", 200.0, 200),
            ("/api/validate", 150.0, 200),
            ("/api/complete", 180.0, 200)
        ]
        
        # Record workflow metrics
        for endpoint, latency, status in workflow_steps:
            metrics_collector.record_request(endpoint, latency, status)
            await asyncio.sleep(0.01)  # Simulate processing time
        
        # Assert SLOs are met for the workflow
        metrics_collector.assert_error_rate_below(1.0)
        metrics_collector.assert_latency_below(200.0, "avg")
        metrics_collector.assert_latency_below(300.0, "p95")
        
        # Verify all SLOs are healthy
        for slo_name in ["error_rate", "avg_latency", "p95_latency"]:
            metrics_collector.assert_slo_healthy(slo_name)
    
    @pytest.mark.asyncio
    async def test_e2e_error_scenario_with_metrics(self, metrics_collector):
        """Test E2E error scenario with metrics collection."""
        # Simulate a workflow with some errors
        workflow_steps = [
            ("/api/query", 100.0, 200),
            ("/api/process", 200.0, 200),
            ("/api/validate", 150.0, 500),  # Error
            ("/api/retry", 300.0, 200),
            ("/api/complete", 180.0, 200)
        ]
        
        # Record workflow metrics
        for endpoint, latency, status in workflow_steps:
            metrics_collector.record_request(endpoint, latency, status)
            await asyncio.sleep(0.01)
        
        # Calculate error rate
        error_rate = metrics_collector.calculate_error_rate()
        assert error_rate == 20.0  # 1 error out of 5 requests
        
        # Error rate should exceed SLO target
        with pytest.raises(AssertionError):
            metrics_collector.assert_slo_healthy("error_rate")
        
        # But latency should still be within bounds
        metrics_collector.assert_latency_below(250.0, "avg")
    
    @pytest.mark.asyncio
    async def test_e2e_load_testing_with_metrics(self, metrics_collector):
        """Test E2E load testing scenario with metrics."""
        # Simulate load testing with varying latencies
        import random
        
        for i in range(1000):
            # Simulate realistic latency distribution
            base_latency = 100.0
            jitter = random.uniform(-50.0, 150.0)
            latency = max(10.0, base_latency + jitter)
            
            # 1% error rate
            status_code = 500 if random.random() < 0.01 else 200
            
            metrics_collector.record_request("/api/query", latency, status_code)
        
        # Assert SLOs under load
        metrics_collector.assert_error_rate_below(2.0)  # Allow some tolerance
        metrics_collector.assert_latency_below(250.0, "avg")
        metrics_collector.assert_latency_below(400.0, "p95")
        
        # Verify metrics are reasonable
        error_rate = metrics_collector.calculate_error_rate()
        avg_latency = metrics_collector.calculate_avg_latency()
        p95_latency = metrics_collector.calculate_p95_latency()
        
        assert 0.5 <= error_rate <= 2.0  # Should be around 1%
        assert 100.0 <= avg_latency <= 250.0  # Should be around 150ms
        assert 200.0 <= p95_latency <= 400.0  # P95 should be higher


class TestMetricsIntegration:
    """Test metrics integration with other test components."""
    
    def test_metrics_with_performance_tests(self, metrics_collector):
        """Test metrics integration with performance tests."""
        # Simulate performance test results
        performance_data = [
            ("/api/query", [100.0, 120.0, 110.0, 130.0, 115.0], [200, 200, 200, 500, 200]),
            ("/api/process", [200.0, 220.0, 210.0, 230.0, 215.0], [200, 200, 200, 200, 200])
        ]
        
        for endpoint, latencies, statuses in performance_data:
            for latency, status in zip(latencies, statuses):
                metrics_collector.record_request(endpoint, latency, status)
        
        # Assert performance meets SLOs
        metrics_collector.assert_error_rate_below(15.0)  # 1 error out of 10 requests (10% error rate)
        metrics_collector.assert_latency_below(250.0, "avg")
        
        # Check endpoint-specific metrics
        query_error_rate = metrics_collector.calculate_error_rate("/api/query")
        process_error_rate = metrics_collector.calculate_error_rate("/api/process")
        
        assert query_error_rate == 20.0  # 1 error out of 5 requests
        assert process_error_rate == 0.0  # No errors
    
    def test_metrics_with_chaos_tests(self, metrics_collector):
        """Test metrics integration with chaos tests."""
        # Simulate chaos test with failures and recovery
        chaos_scenarios = [
            # Normal operation
            *[("/api/query", 150.0, 200) for _ in range(50)],
            # Chaos event - high latency and errors
            *[("/api/query", 500.0, 500) for _ in range(10)],
            *[("/api/query", 800.0, 200) for _ in range(10)],
            # Recovery
            *[("/api/query", 150.0, 200) for _ in range(50)]
        ]
        
        for endpoint, latency, status in chaos_scenarios:
            metrics_collector.record_request(endpoint, latency, status)
        
        # During chaos, metrics should be degraded
        error_rate = metrics_collector.calculate_error_rate()
        avg_latency = metrics_collector.calculate_avg_latency()
        
        # Should have some errors and high latency
        assert error_rate > 0
        assert avg_latency > 200.0  # Should be higher due to chaos
        
        # But not catastrophic
        assert error_rate < 50.0  # Less than 50% error rate
        assert avg_latency < 1000.0  # Less than 1 second average
