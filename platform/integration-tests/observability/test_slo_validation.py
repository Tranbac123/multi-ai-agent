"""SLO validation tests with Prometheus metrics and Grafana dashboard assertions."""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, AsyncMock, patch

from tests.observability import (
    SLOTarget, SLOStatus, SLOMonitor, SLOAlert, ObservabilityTestResult,
    MockSpan, MockTracer, MetricsCollector
)


class SLOManager:
    """Manages SLO monitoring and validation."""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.monitors: Dict[str, SLOMonitor] = {}
        self.alerts: Dict[str, SLOAlert] = {}
    
    def add_monitor(self, monitor: SLOMonitor):
        """Add an SLO monitor."""
        self.monitors[monitor.name] = monitor
    
    def add_alert(self, alert: SLOAlert):
        """Add an SLO alert."""
        self.alerts[alert.name] = alert
    
    def validate_slo(self, monitor_name: str, test_duration_minutes: int = 5) -> SLOStatus:
        """Validate SLO against metrics."""
        monitor = self.monitors.get(monitor_name)
        if not monitor:
            return SLOStatus.UNKNOWN
        
        # Collect metrics for the specified window
        metrics = self._collect_metrics(monitor, test_duration_minutes)
        
        # Evaluate SLO
        return self._evaluate_slo(monitor, metrics)
    
    def _collect_metrics(self, monitor: SLOMonitor, duration_minutes: int) -> Dict[str, float]:
        """Collect metrics for SLO evaluation."""
        metrics = {}
        
        if monitor.target == SLOTarget.LATENCY_P50:
            hist_stats = self.metrics_collector.get_histogram_stats("http_request_duration_seconds")
            metrics["p50"] = hist_stats.get("avg", 0.0) * 1000  # Convert to ms
        
        elif monitor.target == SLOTarget.LATENCY_P95:
            hist_stats = self.metrics_collector.get_histogram_stats("http_request_duration_seconds")
            metrics["p95"] = hist_stats.get("max", 0.0) * 1000  # Approximate p95
        
        elif monitor.target == SLOTarget.LATENCY_P99:
            hist_stats = self.metrics_collector.get_histogram_stats("http_request_duration_seconds")
            metrics["p99"] = hist_stats.get("max", 0.0) * 1000  # Approximate p99
        
        elif monitor.target == SLOTarget.ERROR_RATE:
            total_requests = self.metrics_collector.get_counter_value("http_requests_total")
            success_requests = self.metrics_collector.get_counter_value("http_requests_total", {"status": "success"})
            metrics["error_rate"] = ((total_requests - success_requests) / max(total_requests, 1)) * 100
        
        elif monitor.target == SLOTarget.AVAILABILITY:
            total_requests = self.metrics_collector.get_counter_value("http_requests_total")
            success_requests = self.metrics_collector.get_counter_value("http_requests_total", {"status": "success"})
            metrics["availability"] = (success_requests / max(total_requests, 1)) * 100
        
        elif monitor.target == SLOTarget.THROUGHPUT:
            requests_count = self.metrics_collector.get_counter_value("http_requests_total")
            metrics["throughput"] = requests_count / max(duration_minutes * 60, 1)  # RPS
        
        elif monitor.target == SLOTarget.SUCCESS_RATE:
            total_requests = self.metrics_collector.get_counter_value("http_requests_total")
            success_requests = self.metrics_collector.get_counter_value("http_requests_total", {"status": "success"})
            metrics["success_rate"] = (success_requests / max(total_requests, 1)) * 100
        
        return metrics
    
    def _evaluate_slo(self, monitor: SLOMonitor, metrics: Dict[str, float]) -> SLOStatus:
        """Evaluate SLO against collected metrics."""
        if not metrics:
            return SLOStatus.UNKNOWN
        
        # Get the relevant metric value
        metric_value = 0.0
        if monitor.target in [SLOTarget.LATENCY_P50, SLOTarget.LATENCY_P95, SLOTarget.LATENCY_P99]:
            metric_value = metrics.get("p50", metrics.get("p95", metrics.get("p99", 0.0)))
        elif monitor.target == SLOTarget.ERROR_RATE:
            metric_value = metrics.get("error_rate", 0.0)
        elif monitor.target == SLOTarget.AVAILABILITY:
            metric_value = metrics.get("availability", 0.0)
        elif monitor.target == SLOTarget.THROUGHPUT:
            metric_value = metrics.get("throughput", 0.0)
        elif monitor.target == SLOTarget.SUCCESS_RATE:
            metric_value = metrics.get("success_rate", 0.0)
        
        # Evaluate against threshold
        if monitor.target in [SLOTarget.LATENCY_P50, SLOTarget.LATENCY_P95, SLOTarget.LATENCY_P99]:
            # For latency, higher is worse
            if metric_value <= monitor.threshold:
                return SLOStatus.MEETING
            elif metric_value <= monitor.threshold * 1.2:  # 20% tolerance
                return SLOStatus.WARNING
            else:
                return SLOStatus.BREACHED
        else:
            # For rates, lower is worse (except throughput)
            if monitor.target == SLOTarget.THROUGHPUT:
                if metric_value >= monitor.threshold:
                    return SLOStatus.MEETING
                elif metric_value >= monitor.threshold * 0.8:  # 20% tolerance
                    return SLOStatus.WARNING
                else:
                    return SLOStatus.BREACHED
            else:
                if metric_value >= monitor.threshold:
                    return SLOStatus.MEETING
                elif metric_value >= monitor.threshold * 0.8:  # 20% tolerance
                    return SLOStatus.WARNING
                else:
                    return SLOStatus.BREACHED


class GrafanaDashboardValidator:
    """Validates Grafana dashboard configurations."""
    
    def __init__(self):
        self.dashboards: Dict[str, Dict[str, Any]] = {}
    
    def add_dashboard(self, name: str, config: Dict[str, Any]):
        """Add a dashboard configuration."""
        self.dashboards[name] = config
    
    def validate_dashboard(self, name: str) -> bool:
        """Validate dashboard configuration."""
        dashboard = self.dashboards.get(name)
        if not dashboard:
            return False
        
        # Check required fields
        required_fields = ['title', 'panels', 'time']
        for field in required_fields:
            if field not in dashboard:
                return False
        
        # Validate panels
        panels = dashboard.get('panels', [])
        for panel in panels:
            if not self._validate_panel(panel):
                return False
        
        return True
    
    def _validate_panel(self, panel: Dict[str, Any]) -> bool:
        """Validate individual panel configuration."""
        required_fields = ['id', 'title', 'type', 'targets']
        for field in required_fields:
            if field not in panel:
                return False
        
        # Validate targets
        targets = panel.get('targets', [])
        for target in targets:
            if not self._validate_target(target):
                return False
        
        return True
    
    def _validate_target(self, target: Dict[str, Any]) -> bool:
        """Validate query target configuration."""
        required_fields = ['expr', 'refId']
        for field in required_fields:
            if field not in target:
                return False
        
        # Validate Prometheus query syntax
        expr = target.get('expr', '')
        if not expr or not isinstance(expr, str):
            return False
        
        return True


class TestSLOValidation:
    """Test SLO validation and monitoring."""
    
    @pytest.fixture
    def metrics_collector(self):
        """Create metrics collector."""
        return MetricsCollector()
    
    @pytest.fixture
    def slo_manager(self, metrics_collector):
        """Create SLO manager."""
        return SLOManager(metrics_collector)
    
    @pytest.fixture
    def grafana_validator(self):
        """Create Grafana dashboard validator."""
        return GrafanaDashboardValidator()
    
    def test_latency_slo_validation(self, slo_manager, metrics_collector):
        """Test latency SLO validation."""
        # Create latency SLO monitor
        monitor = SLOMonitor(
            name="api_latency_p95",
            target=SLOTarget.LATENCY_P95,
            threshold=500.0,  # 500ms
            window_minutes=5,
            description="API 95th percentile latency",
            severity="critical"
        )
        
        slo_manager.add_monitor(monitor)
        
        # Simulate good performance
        for i in range(100):
            metrics_collector.record_histogram("http_request_duration_seconds", 0.1)  # 100ms
        
        # Validate SLO
        status = slo_manager.validate_slo("api_latency_p95")
        assert status == SLOStatus.MEETING
    
    def test_error_rate_slo_validation(self, slo_manager, metrics_collector):
        """Test error rate SLO validation."""
        # Create error rate SLO monitor
        monitor = SLOMonitor(
            name="api_error_rate",
            target=SLOTarget.ERROR_RATE,
            threshold=5.0,  # 5% error rate (95% success rate)
            window_minutes=5,
            description="API error rate",
            severity="critical"
        )
        
        slo_manager.add_monitor(monitor)
        
        # Simulate good performance (95% success rate)
        for i in range(100):
            metrics_collector.increment_counter("http_requests_total")
            if i < 95:
                metrics_collector.increment_counter("http_requests_total", labels={"status": "success"})
            else:
                metrics_collector.increment_counter("http_requests_total", labels={"status": "error"})
        
        # Validate SLO
        status = slo_manager.validate_slo("api_error_rate")
        assert status == SLOStatus.MEETING
    
    def test_availability_slo_validation(self, slo_manager, metrics_collector):
        """Test availability SLO validation."""
        # Create availability SLO monitor
        monitor = SLOMonitor(
            name="api_availability",
            target=SLOTarget.AVAILABILITY,
            threshold=99.9,  # 99.9% availability
            window_minutes=5,
            description="API availability",
            severity="critical"
        )
        
        slo_manager.add_monitor(monitor)
        
        # Simulate high availability (99.9%)
        for i in range(1000):
            metrics_collector.increment_counter("http_requests_total")
            if i < 999:
                metrics_collector.increment_counter("http_requests_total", labels={"status": "success"})
            else:
                metrics_collector.increment_counter("http_requests_total", labels={"status": "error"})
        
        # Validate SLO
        status = slo_manager.validate_slo("api_availability")
        assert status == SLOStatus.MEETING
    
    def test_throughput_slo_validation(self, slo_manager, metrics_collector):
        """Test throughput SLO validation."""
        # Create throughput SLO monitor
        monitor = SLOMonitor(
            name="api_throughput",
            target=SLOTarget.THROUGHPUT,
            threshold=10.0,  # 10 RPS
            window_minutes=1,
            description="API throughput",
            severity="warning"
        )
        
        slo_manager.add_monitor(monitor)
        
        # Simulate high throughput
        for i in range(600):  # 600 requests in 1 minute = 10 RPS (meets threshold)
            metrics_collector.increment_counter("http_requests_total")
        
        # Validate SLO
        status = slo_manager.validate_slo("api_throughput", test_duration_minutes=1)
        assert status == SLOStatus.MEETING
    
    def test_slo_breach_detection(self, slo_manager, metrics_collector):
        """Test SLO breach detection."""
        # Create latency SLO monitor
        monitor = SLOMonitor(
            name="api_latency_breach",
            target=SLOTarget.LATENCY_P95,
            threshold=200.0,  # 200ms
            window_minutes=5,
            description="API latency breach test",
            severity="critical"
        )
        
        slo_manager.add_monitor(monitor)
        
        # Simulate poor performance (high latency)
        for i in range(100):
            metrics_collector.record_histogram("http_request_duration_seconds", 0.5)  # 500ms
        
        # Validate SLO
        status = slo_manager.validate_slo("api_latency_breach")
        assert status == SLOStatus.BREACHED
    
    def test_slo_warning_detection(self, slo_manager, metrics_collector):
        """Test SLO warning detection."""
        # Create latency SLO monitor
        monitor = SLOMonitor(
            name="api_latency_warning",
            target=SLOTarget.LATENCY_P95,
            threshold=200.0,  # 200ms
            window_minutes=5,
            description="API latency warning test",
            severity="warning"
        )
        
        slo_manager.add_monitor(monitor)
        
        # Simulate moderate performance (within warning range)
        for i in range(100):
            metrics_collector.record_histogram("http_request_duration_seconds", 0.22)  # 220ms (10% over threshold)
        
        # Validate SLO
        status = slo_manager.validate_slo("api_latency_warning")
        assert status == SLOStatus.WARNING
    
    def test_multiple_slo_monitors(self, slo_manager, metrics_collector):
        """Test multiple SLO monitors."""
        # Create multiple monitors
        monitors = [
            SLOMonitor("latency_p95", SLOTarget.LATENCY_P95, 500.0, 5),
            SLOMonitor("error_rate", SLOTarget.ERROR_RATE, 5.0, 5),  # 5% error rate
            SLOMonitor("availability", SLOTarget.AVAILABILITY, 95.0, 5)  # 95% availability
        ]
        
        for monitor in monitors:
            slo_manager.add_monitor(monitor)
        
        # Simulate mixed performance
        for i in range(100):
            # Good latency
            metrics_collector.record_histogram("http_request_duration_seconds", 0.1)
            
            # Good error rate (95% success = 5% error rate)
            metrics_collector.increment_counter("http_requests_total")
            if i < 95:
                metrics_collector.increment_counter("http_requests_total", labels={"status": "success"})
            else:
                metrics_collector.increment_counter("http_requests_total", labels={"status": "error"})
        
        # Validate all SLOs
        results = {}
        for monitor in monitors:
            status = slo_manager.validate_slo(monitor.name)
            results[monitor.name] = status
        
        # Check results
        assert results["latency_p95"] == SLOStatus.MEETING
        assert results["error_rate"] == SLOStatus.MEETING
        assert results["availability"] == SLOStatus.MEETING
    
    def test_grafana_dashboard_validation(self, grafana_validator):
        """Test Grafana dashboard validation."""
        # Create valid dashboard
        dashboard_config = {
            "title": "API Performance Dashboard",
            "panels": [
                {
                    "id": 1,
                    "title": "Request Rate",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "rate(http_requests_total[5m])",
                            "refId": "A"
                        }
                    ]
                },
                {
                    "id": 2,
                    "title": "Error Rate",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "rate(http_requests_total{status=\"error\"}[5m])",
                            "refId": "B"
                        }
                    ]
                }
            ],
            "time": {
                "from": "now-1h",
                "to": "now"
            }
        }
        
        grafana_validator.add_dashboard("api_dashboard", dashboard_config)
        
        # Validate dashboard
        is_valid = grafana_validator.validate_dashboard("api_dashboard")
        assert is_valid is True
    
    def test_invalid_grafana_dashboard(self, grafana_validator):
        """Test invalid Grafana dashboard detection."""
        # Create invalid dashboard (missing required fields)
        invalid_dashboard = {
            "title": "Invalid Dashboard",
            "panels": [
                {
                    "id": 1,
                    "title": "Invalid Panel",
                    "type": "graph"
                    # Missing targets
                }
            ]
            # Missing time configuration
        }
        
        grafana_validator.add_dashboard("invalid_dashboard", invalid_dashboard)
        
        # Validate dashboard
        is_valid = grafana_validator.validate_dashboard("invalid_dashboard")
        assert is_valid is False
    
    def test_slo_alert_configuration(self, slo_manager):
        """Test SLO alert configuration."""
        # Create monitors
        latency_monitor = SLOMonitor("latency_p95", SLOTarget.LATENCY_P95, 500.0, 5)
        error_monitor = SLOMonitor("error_rate", SLOTarget.ERROR_RATE, 95.0, 5)
        
        slo_manager.add_monitor(latency_monitor)
        slo_manager.add_monitor(error_monitor)
        
        # Create alert
        alert = SLOAlert(
            name="api_critical_alert",
            monitors=["latency_p95", "error_rate"],
            condition="any",
            notification_channels=["slack", "email"],
            escalation_policy="immediate"
        )
        
        slo_manager.add_alert(alert)
        
        # Verify alert configuration
        assert alert.name == "api_critical_alert"
        assert len(alert.monitors) == 2
        assert alert.condition == "any"
        assert "slack" in alert.notification_channels
        assert alert.escalation_policy == "immediate"
    
    def test_observability_test_result(self):
        """Test observability test result creation."""
        # Create test result
        result = ObservabilityTestResult(
            test_name="slo_validation_test",
            slo_results={
                "latency_p95": SLOStatus.MEETING,
                "error_rate": SLOStatus.WARNING,
                "availability": SLOStatus.MEETING
            },
            metric_assertions={
                "request_rate": True,
                "error_rate": False,
                "latency": True
            },
            trace_assertions={
                "api_request": True,
                "database_query": True
            },
            overall_passed=False,  # Failed due to error_rate
            timestamp=datetime.now(),
            details={
                "error_rate_breach": "Error rate exceeded 5% threshold",
                "latency_improvement": "Latency improved by 10%"
            }
        )
        
        # Verify result
        assert result.test_name == "slo_validation_test"
        assert result.slo_results["latency_p95"] == SLOStatus.MEETING
        assert result.slo_results["error_rate"] == SLOStatus.WARNING
        assert result.metric_assertions["request_rate"] is True
        assert result.metric_assertions["error_rate"] is False
        assert result.overall_passed is False
        assert "error_rate_breach" in result.details
