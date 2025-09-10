"""Integration tests for observability functionality."""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch
from hypothesis import given, strategies as st

from observability.otel.tracing import TracingManager
from observability.metrics.prometheus_metrics import PrometheusMetrics
from observability.slo.slo_monitor import SLOMonitor
from observability.dashboards.grafana_dashboard import GrafanaDashboard


class TestPrometheusMetrics:
    """Test Prometheus metrics functionality."""

    @pytest.mark.asyncio
    async def test_agent_run_latency_ms_metric(self):
        """Test agent run latency metric."""
        metrics = PrometheusMetrics()
        
        # Record agent run latency
        await metrics.record_agent_run_latency("tenant_001", "workflow_001", 1500.0)
        
        # Get metric value
        latency_metric = await metrics.get_metric("agent_run_latency_ms")
        
        assert latency_metric is not None
        assert "tenant_id" in latency_metric["labels"]
        assert "workflow_id" in latency_metric["labels"]
        assert latency_metric["value"] == 1500.0

    @pytest.mark.asyncio
    async def test_router_misroute_rate_metric(self):
        """Test router misroute rate metric."""
        metrics = PrometheusMetrics()
        
        # Record router decisions
        await metrics.record_router_decision("tenant_001", "gpt-4", "gpt-3.5-turbo", True)
        await metrics.record_router_decision("tenant_001", "gpt-4", "gpt-4", False)
        await metrics.record_router_decision("tenant_001", "gpt-3.5-turbo", "gpt-3.5-turbo", False)
        
        # Get misroute rate
        misroute_rate = await metrics.get_router_misroute_rate("tenant_001")
        
        assert misroute_rate is not None
        assert 0 <= misroute_rate <= 1
        assert misroute_rate == 0.5  # 1 out of 2 decisions was a misroute

    @pytest.mark.asyncio
    async def test_ws_backpressure_drops_metric(self):
        """Test WebSocket backpressure drops metric."""
        metrics = PrometheusMetrics()
        
        # Record backpressure drops
        await metrics.record_ws_backpressure_drop("tenant_001", "session_001", "slow_client")
        await metrics.record_ws_backpressure_drop("tenant_001", "session_002", "slow_client")
        
        # Get drops count
        drops_count = await metrics.get_ws_backpressure_drops("tenant_001")
        
        assert drops_count == 2

    @pytest.mark.asyncio
    async def test_tool_error_rate_metric(self):
        """Test tool error rate metric."""
        metrics = PrometheusMetrics()
        
        # Record tool executions
        await metrics.record_tool_execution("tenant_001", "order_lookup", True, 500.0)
        await metrics.record_tool_execution("tenant_001", "order_lookup", False, 1000.0)
        await metrics.record_tool_execution("tenant_001", "payment_tool", True, 300.0)
        
        # Get error rate
        error_rate = await metrics.get_tool_error_rate("tenant_001", "order_lookup")
        
        assert error_rate is not None
        assert 0 <= error_rate <= 1
        assert error_rate == 0.5  # 1 out of 2 executions failed

    @pytest.mark.asyncio
    async def test_metrics_scraping(self):
        """Test metrics scraping endpoint."""
        metrics = PrometheusMetrics()
        
        # Record some metrics
        await metrics.record_agent_run_latency("tenant_001", "workflow_001", 1500.0)
        await metrics.record_router_decision("tenant_001", "gpt-4", "gpt-4", False)
        
        # Get scraped metrics
        scraped_metrics = await metrics.scrape_metrics()
        
        assert "agent_run_latency_ms" in scraped_metrics
        assert "router_misroute_rate" in scraped_metrics
        assert "ws_backpressure_drops" in scraped_metrics
        assert "tool_error_rate" in scraped_metrics

    @pytest.mark.asyncio
    async def test_metrics_aggregation(self):
        """Test metrics aggregation by tenant."""
        metrics = PrometheusMetrics()
        
        # Record metrics for different tenants
        await metrics.record_agent_run_latency("tenant_001", "workflow_001", 1000.0)
        await metrics.record_agent_run_latency("tenant_001", "workflow_002", 2000.0)
        await metrics.record_agent_run_latency("tenant_002", "workflow_001", 1500.0)
        
        # Get aggregated metrics
        tenant_metrics = await metrics.get_tenant_metrics("tenant_001")
        
        assert "agent_run_latency_ms" in tenant_metrics
        assert tenant_metrics["agent_run_latency_ms"]["count"] == 2
        assert tenant_metrics["agent_run_latency_ms"]["sum"] == 3000.0
        assert tenant_metrics["agent_run_latency_ms"]["avg"] == 1500.0


class TestOpenTelemetryTracing:
    """Test OpenTelemetry tracing functionality."""

    @pytest.mark.asyncio
    async def test_trace_span_attributes(self):
        """Test trace span attributes."""
        tracing = TracingManager()
        
        # Create span with required attributes
        with tracing.create_span("test_operation") as span:
            span.set_attribute("run_id", "run_001")
            span.set_attribute("step_id", "step_001")
            span.set_attribute("tenant_id", "tenant_001")
            span.set_attribute("tool_id", "order_lookup")
            span.set_attribute("tier", "premium")
            span.set_attribute("workflow", "order_processing")
            
            # Simulate some work
            await asyncio.sleep(0.1)
        
        # Get span data
        span_data = await tracing.get_span_data("test_operation")
        
        assert span_data is not None
        assert span_data["attributes"]["run_id"] == "run_001"
        assert span_data["attributes"]["step_id"] == "step_001"
        assert span_data["attributes"]["tenant_id"] == "tenant_001"
        assert span_data["attributes"]["tool_id"] == "order_lookup"
        assert span_data["attributes"]["tier"] == "premium"
        assert span_data["attributes"]["workflow"] == "order_processing"

    @pytest.mark.asyncio
    async def test_trace_hierarchy(self):
        """Test trace hierarchy."""
        tracing = TracingManager()
        
        # Create parent span
        with tracing.create_span("parent_operation") as parent_span:
            parent_span.set_attribute("tenant_id", "tenant_001")
            
            # Create child span
            with tracing.create_span("child_operation", parent=parent_span) as child_span:
                child_span.set_attribute("step_id", "step_001")
                
                # Simulate work
                await asyncio.sleep(0.1)
        
        # Get trace hierarchy
        trace_data = await tracing.get_trace_hierarchy("parent_operation")
        
        assert trace_data is not None
        assert "parent_operation" in trace_data
        assert "child_operation" in trace_data["parent_operation"]["children"]
        
        child_data = trace_data["parent_operation"]["children"]["child_operation"]
        assert child_data["attributes"]["step_id"] == "step_001"

    @pytest.mark.asyncio
    async def test_trace_error_handling(self):
        """Test trace error handling."""
        tracing = TracingManager()
        
        # Create span that fails
        with tracing.create_span("failing_operation") as span:
            span.set_attribute("tenant_id", "tenant_001")
            
            try:
                # Simulate error
                raise Exception("Test error")
            except Exception as e:
                span.record_exception(e)
                span.set_status("ERROR", str(e))
        
        # Get span data
        span_data = await tracing.get_span_data("failing_operation")
        
        assert span_data is not None
        assert span_data["status"] == "ERROR"
        assert "Test error" in span_data["error_message"]
        assert span_data["attributes"]["tenant_id"] == "tenant_001"

    @pytest.mark.asyncio
    async def test_trace_sampling(self):
        """Test trace sampling."""
        tracing = TracingManager(sampling_rate=0.5)
        
        # Create multiple spans
        sampled_count = 0
        total_count = 100
        
        for i in range(total_count):
            with tracing.create_span(f"operation_{i}") as span:
                span.set_attribute("tenant_id", f"tenant_{i % 10}")
                
                # Check if span was sampled
                if span.is_sampled():
                    sampled_count += 1
        
        # Should have sampled approximately 50% of spans
        assert 30 <= sampled_count <= 70  # Allow some variance

    @pytest.mark.asyncio
    async def test_trace_export(self):
        """Test trace export."""
        tracing = TracingManager()
        
        # Create span
        with tracing.create_span("export_test") as span:
            span.set_attribute("tenant_id", "tenant_001")
            span.set_attribute("operation", "test")
            
            await asyncio.sleep(0.1)
        
        # Export traces
        exported_traces = await tracing.export_traces()
        
        assert len(exported_traces) > 0
        assert any(trace["name"] == "export_test" for trace in exported_traces)


class TestSLOMonitoring:
    """Test SLO monitoring functionality."""

    @pytest.mark.asyncio
    async def test_slo_availability_monitoring(self, redis_fixture):
        """Test SLO availability monitoring."""
        slo_monitor = SLOMonitor(redis_fixture)
        
        # Define SLO target
        slo_target = {
            "service": "api_gateway",
            "metric": "availability",
            "target": 0.99,  # 99% availability
            "window": "1h",
            "burn_rate_threshold": 0.1
        }
        
        await slo_monitor.add_slo_target(slo_target)
        
        # Record some availability data
        await slo_monitor.record_availability("api_gateway", True, time.time())
        await slo_monitor.record_availability("api_gateway", True, time.time())
        await slo_monitor.record_availability("api_gateway", False, time.time())  # 1 failure out of 3
        
        # Check SLO status
        slo_status = await slo_monitor.check_slo_status("api_gateway", "availability")
        
        assert slo_status is not None
        assert slo_status["service"] == "api_gateway"
        assert slo_status["metric"] == "availability"
        assert slo_status["current_value"] == 2/3  # 2 out of 3 successful
        assert slo_status["target"] == 0.99
        assert slo_status["status"] in ["healthy", "warning", "critical"]

    @pytest.mark.asyncio
    async def test_slo_latency_monitoring(self, redis_fixture):
        """Test SLO latency monitoring."""
        slo_monitor = SLOMonitor(redis_fixture)
        
        # Define SLO target
        slo_target = {
            "service": "router_service",
            "metric": "p95_latency",
            "target": 1000.0,  # 1000ms p95 latency
            "window": "1h",
            "burn_rate_threshold": 0.1
        }
        
        await slo_monitor.add_slo_target(slo_target)
        
        # Record latency data
        latencies = [500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400]  # p95 = 1300
        for latency in latencies:
            await slo_monitor.record_latency("router_service", latency, time.time())
        
        # Check SLO status
        slo_status = await slo_monitor.check_slo_status("router_service", "p95_latency")
        
        assert slo_status is not None
        assert slo_status["service"] == "router_service"
        assert slo_status["metric"] == "p95_latency"
        assert slo_status["current_value"] == 1300.0  # p95 latency
        assert slo_status["target"] == 1000.0
        assert slo_status["status"] in ["warning", "critical"]  # Exceeds target

    @pytest.mark.asyncio
    async def test_slo_burn_rate_calculation(self, redis_fixture):
        """Test SLO burn rate calculation."""
        slo_monitor = SLOMonitor(redis_fixture)
        
        # Define SLO target
        slo_target = {
            "service": "orchestrator",
            "metric": "availability",
            "target": 0.99,
            "window": "1h",
            "burn_rate_threshold": 0.1
        }
        
        await slo_monitor.add_slo_target(slo_target)
        
        # Record availability data with high failure rate
        for i in range(100):
            is_available = i < 80  # 80% availability (below 99% target)
            await slo_monitor.record_availability("orchestrator", is_available, time.time())
        
        # Check burn rate
        burn_rate = await slo_monitor.calculate_burn_rate("orchestrator", "availability")
        
        assert burn_rate > 0.1  # Should exceed burn rate threshold

    @pytest.mark.asyncio
    async def test_slo_alert_generation(self, redis_fixture):
        """Test SLO alert generation."""
        slo_monitor = SLOMonitor(redis_fixture)
        
        # Define SLO target
        slo_target = {
            "service": "billing_service",
            "metric": "availability",
            "target": 0.99,
            "window": "1h",
            "burn_rate_threshold": 0.1
        }
        
        await slo_monitor.add_slo_target(slo_target)
        
        # Record data that violates SLO
        for i in range(50):
            is_available = i < 30  # 60% availability (well below 99% target)
            await slo_monitor.record_availability("billing_service", is_available, time.time())
        
        # Check for alerts
        alerts = await slo_monitor.check_all_slos()
        
        assert len(alerts) > 0
        billing_alerts = [alert for alert in alerts if alert["service"] == "billing_service"]
        assert len(billing_alerts) > 0
        assert billing_alerts[0]["status"] in ["warning", "critical"]


class TestGrafanaDashboards:
    """Test Grafana dashboard functionality."""

    @pytest.mark.asyncio
    async def test_dashboard_generation(self):
        """Test dashboard generation."""
        dashboard = GrafanaDashboard()
        
        # Generate dashboard
        dashboard_config = await dashboard.generate_dashboard(
            title="AIaaS Platform Metrics",
            panels=[
                {
                    "title": "Agent Run Latency",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "agent_run_latency_ms",
                            "legendFormat": "Latency (ms)"
                        }
                    ]
                },
                {
                    "title": "Router Misroute Rate",
                    "type": "singlestat",
                    "targets": [
                        {
                            "expr": "router_misroute_rate",
                            "legendFormat": "Misroute Rate"
                        }
                    ]
                }
            ]
        )
        
        assert dashboard_config["title"] == "AIaaS Platform Metrics"
        assert len(dashboard_config["panels"]) == 2
        assert dashboard_config["panels"][0]["title"] == "Agent Run Latency"
        assert dashboard_config["panels"][1]["title"] == "Router Misroute Rate"

    @pytest.mark.asyncio
    async def test_dashboard_export(self):
        """Test dashboard export."""
        dashboard = GrafanaDashboard()
        
        # Generate dashboard
        dashboard_config = await dashboard.generate_dashboard(
            title="Test Dashboard",
            panels=[]
        )
        
        # Export dashboard
        exported_data = await dashboard.export_dashboard(dashboard_config)
        
        assert "dashboard" in exported_data
        assert exported_data["dashboard"]["title"] == "Test Dashboard"

    @pytest.mark.asyncio
    async def test_dashboard_import(self):
        """Test dashboard import."""
        dashboard = GrafanaDashboard()
        
        # Import dashboard
        imported_dashboard = await dashboard.import_dashboard({
            "dashboard": {
                "title": "Imported Dashboard",
                "panels": []
            }
        })
        
        assert imported_dashboard["title"] == "Imported Dashboard"

    @pytest.mark.asyncio
    async def test_dashboard_validation(self):
        """Test dashboard validation."""
        dashboard = GrafanaDashboard()
        
        # Valid dashboard
        valid_dashboard = {
            "title": "Valid Dashboard",
            "panels": [
                {
                    "title": "Test Panel",
                    "type": "graph",
                    "targets": []
                }
            ]
        }
        
        is_valid = await dashboard.validate_dashboard(valid_dashboard)
        assert is_valid is True
        
        # Invalid dashboard (missing title)
        invalid_dashboard = {
            "panels": []
        }
        
        is_valid = await dashboard.validate_dashboard(invalid_dashboard)
        assert is_valid is False


class TestObservabilityIntegration:
    """Test observability integration."""

    @pytest.mark.asyncio
    async def test_end_to_end_observability(self, redis_fixture):
        """Test end-to-end observability."""
        # Initialize all observability components
        tracing = TracingManager()
        metrics = PrometheusMetrics()
        slo_monitor = SLOMonitor(redis_fixture)
        dashboard = GrafanaDashboard()
        
        # Simulate a complete request flow
        with tracing.create_span("api_request") as span:
            span.set_attribute("tenant_id", "tenant_001")
            span.set_attribute("user_id", "user_001")
            span.set_attribute("workflow", "customer_support")
            
            # Record metrics
            await metrics.record_agent_run_latency("tenant_001", "workflow_001", 1500.0)
            await metrics.record_router_decision("tenant_001", "gpt-4", "gpt-4", False)
            await metrics.record_tool_execution("tenant_001", "order_lookup", True, 500.0)
            
            # Record SLO data
            await slo_monitor.record_availability("api_gateway", True, time.time())
            await slo_monitor.record_latency("router_service", 800.0, time.time())
            
            # Simulate work
            await asyncio.sleep(0.1)
        
        # Verify all observability data is collected
        span_data = await tracing.get_span_data("api_request")
        assert span_data is not None
        assert span_data["attributes"]["tenant_id"] == "tenant_001"
        
        scraped_metrics = await metrics.scrape_metrics()
        assert "agent_run_latency_ms" in scraped_metrics
        assert "router_misroute_rate" in scraped_metrics
        assert "tool_error_rate" in scraped_metrics
        
        slo_status = await slo_monitor.check_slo_status("api_gateway", "availability")
        assert slo_status is not None

    @pytest.mark.asyncio
    async def test_observability_under_load(self, redis_fixture):
        """Test observability under load."""
        tracing = TracingManager()
        metrics = PrometheusMetrics()
        
        # Simulate high load
        tasks = []
        for i in range(100):
            task = asyncio.create_task(self._simulate_request(tracing, metrics, i))
            tasks.append(task)
        
        # Wait for all tasks to complete
        await asyncio.gather(*tasks)
        
        # Verify observability data is collected
        scraped_metrics = await metrics.scrape_metrics()
        assert "agent_run_latency_ms" in scraped_metrics
        
        # Check that metrics are aggregated correctly
        tenant_metrics = await metrics.get_tenant_metrics("tenant_001")
        assert tenant_metrics["agent_run_latency_ms"]["count"] == 100

    async def _simulate_request(self, tracing, metrics, request_id):
        """Simulate a single request."""
        with tracing.create_span(f"request_{request_id}") as span:
            span.set_attribute("tenant_id", "tenant_001")
            span.set_attribute("request_id", str(request_id))
            
            # Record metrics
            await metrics.record_agent_run_latency("tenant_001", "workflow_001", 1000.0 + request_id)
            
            # Simulate work
            await asyncio.sleep(0.01)
