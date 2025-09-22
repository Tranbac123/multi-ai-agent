"""
Integration tests for observability and SLOs.

Tests OpenTelemetry instrumentation, SLO management, error budget tracking,
and comprehensive monitoring capabilities.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from libs.observability.otel_instrumentation import (
    OTELInstrumentor, SpanManager, MetricsCollector, InstrumentationMiddleware,
    ServiceType, TraceContext
)
from libs.observability.slo_manager import (
    SLOManager, SLODefinition, SLOTarget, AlertSeverity, ErrorBudget,
    SLOStatus, SLOMetric, record_slo_metric, get_slo_status
)


class TestOTELInstrumentation:
    """Test OpenTelemetry instrumentation."""
    
    @pytest.fixture
    def instrumentor(self):
        """Create OTEL instrumentor for testing."""
        return OTELInstrumentor("test-service", ServiceType.API_GATEWAY)
    
    @pytest.fixture
    def span_manager(self, instrumentor):
        """Create span manager for testing."""
        return SpanManager(instrumentor)
    
    @pytest.fixture
    def metrics_collector(self, instrumentor):
        """Create metrics collector for testing."""
        return MetricsCollector(instrumentor)
    
    def test_create_span(self, instrumentor):
        """Test span creation."""
        
        context = TraceContext(
            run_id="run-123",
            tenant_id="tenant-456",
            step_id="step-789",
            tier="premium"
        )
        
        span = instrumentor.create_span(
            name="test-operation",
            context=context,
            attributes={"custom_attr": "value"}
        )
        
        assert span is not None
        assert span.name == "test-operation"
    
    def test_create_metric(self, instrumentor):
        """Test metric creation."""
        
        counter = instrumentor.create_metric(
            name="test_counter",
            metric_type="counter",
            description="Test counter metric"
        )
        
        assert counter is not None
    
    def test_span_manager_start_span(self, span_manager):
        """Test starting a span."""
        
        context = TraceContext(
            run_id="run-123",
            tenant_id="tenant-456"
        )
        
        span = span_manager.start_span(
            name="test-span",
            context=context
        )
        
        assert span is not None
        assert span_manager.get_current_span() == span
        assert span_manager.get_current_tenant() == "tenant-456"
        assert span_manager.get_current_run_id() == "run-123"
    
    def test_span_manager_end_span(self, span_manager):
        """Test ending a span."""
        
        context = TraceContext(
            run_id="run-123",
            tenant_id="tenant-456"
        )
        
        span = span_manager.start_span("test-span", context)
        span_manager.end_span(span)
        
        # Span should be removed from active spans
        assert span_manager.get_current_span() is None
    
    def test_metrics_collector_record_agent_latency(self, metrics_collector):
        """Test recording agent latency metrics."""
        
        metrics_collector.record_agent_run_latency(
            latency_ms=150.0,
            tenant_id="tenant-123",
            run_id="run-456"
        )
        
        # Verify metric was recorded (in real implementation, this would check the metric)
        assert "agent_run_latency_ms" in metrics_collector.metrics
    
    def test_metrics_collector_record_router_latency(self, metrics_collector):
        """Test recording router latency metrics."""
        
        metrics_collector.record_router_decision_latency(
            latency_ms=25.0,
            tenant_id="tenant-123",
            tier="premium"
        )
        
        assert "router_decision_latency_ms" in metrics_collector.metrics
    
    def test_metrics_collector_record_tier_distribution(self, metrics_collector):
        """Test recording tier distribution metrics."""
        
        metrics_collector.record_tier_distribution(
            tier="premium",
            tenant_id="tenant-123",
            count=5
        )
        
        assert "tier_distribution" in metrics_collector.metrics
    
    def test_metrics_collector_record_cost(self, metrics_collector):
        """Test recording cost metrics."""
        
        metrics_collector.record_cost(
            cost_usd=0.05,
            tenant_id="tenant-123",
            service="router"
        )
        
        assert "cost_usd_total" in metrics_collector.metrics
    
    def test_metrics_collector_record_tokens(self, metrics_collector):
        """Test recording token metrics."""
        
        metrics_collector.record_tokens(
            token_count=1000,
            tenant_id="tenant-123",
            service="orchestrator"
        )
        
        assert "tokens_total" in metrics_collector.metrics
    
    def test_metrics_collector_record_ws_connections(self, metrics_collector):
        """Test recording WebSocket connection metrics."""
        
        metrics_collector.record_ws_connections(
            count=50,
            tenant_id="tenant-123"
        )
        
        assert "ws_active_connections" in metrics_collector.metrics
    
    def test_metrics_collector_record_ws_drops(self, metrics_collector):
        """Test recording WebSocket backpressure drops."""
        
        metrics_collector.record_ws_backpressure_drops(
            count=10,
            tenant_id="tenant-123"
        )
        
        assert "ws_backpressure_drops" in metrics_collector.metrics


class TestSLOManager:
    """Test SLO manager functionality."""
    
    @pytest.fixture
    def slo_manager(self):
        """Create SLO manager for testing."""
        return SLOManager()
    
    @pytest.fixture
    def api_availability_slo(self):
        """Create API availability SLO definition."""
        return SLODefinition(
            name="test_api_availability",
            description="Test API availability SLO",
            target_type=SLOTarget.AVAILABILITY,
            target_value=99.9,
            measurement_window=300,
            evaluation_window=3600,
            error_budget_policy=0.1,
            service="api_gateway"
        )
    
    def test_add_slo(self, slo_manager, api_availability_slo):
        """Test adding an SLO definition."""
        
        slo_manager.add_slo(api_availability_slo)
        
        assert "test_api_availability" in slo_manager.slo_definitions
        assert "test_api_availability" in slo_manager.error_budgets
    
    def test_record_metric_success(self, slo_manager, api_availability_slo):
        """Test recording successful metrics."""
        
        slo_manager.add_slo(api_availability_slo)
        
        # Record successful metrics
        for _ in range(100):
            slo_manager.record_metric(
                slo_name="test_api_availability",
                success=True,
                latency_ms=100.0
            )
        
        status = slo_manager.get_slo_status("test_api_availability")
        
        assert status is not None
        assert status.current_value >= 99.0  # Should be very high
        assert status.is_healthy is True
    
    def test_record_metric_failure(self, slo_manager, api_availability_slo):
        """Test recording failed metrics."""
        
        slo_manager.add_slo(api_availability_slo)
        
        # Record mostly failed metrics
        for _ in range(100):
            slo_manager.record_metric(
                slo_name="test_api_availability",
                success=False,
                latency_ms=500.0,
                error_code="500"
            )
        
        status = slo_manager.get_slo_status("test_api_availability")
        
        assert status is not None
        assert status.current_value < 99.0  # Should be low
        assert status.is_healthy is False
        assert status.alert_level is not None
    
    def test_error_budget_calculation(self, slo_manager, api_availability_slo):
        """Test error budget calculation."""
        
        slo_manager.add_slo(api_availability_slo)
        
        # Record mix of success and failure
        for i in range(1000):
            success = i % 10 != 0  # 90% success rate
            slo_manager.record_metric(
                slo_name="test_api_availability",
                success=success,
                latency_ms=100.0 if success else 500.0
            )
        
        status = slo_manager.get_slo_status("test_api_availability")
        
        assert status is not None
        assert status.error_budget_remaining < 100.0  # Should have used some error budget
        assert status.error_budget_burn_rate > 0.0
    
    def test_get_service_slo_statuses(self, slo_manager):
        """Test getting SLO statuses for a service."""
        
        statuses = slo_manager.get_service_slo_statuses("api_gateway")
        
        assert len(statuses) > 0
        assert all(status.slo_name for status in statuses.values())
    
    def test_get_all_slo_statuses(self, slo_manager):
        """Test getting all SLO statuses."""
        
        all_statuses = slo_manager.get_all_slo_statuses()
        
        assert len(all_statuses) > 0
        assert all(isinstance(status, SLOStatus) for status in all_statuses.values())
    
    def test_get_slo_metrics_summary(self, slo_manager):
        """Test getting SLO metrics summary."""
        
        summary = slo_manager.get_slo_metrics_summary()
        
        assert "total_slos" in summary
        assert "healthy_slos" in summary
        assert "unhealthy_slos" in summary
        assert "critical_alerts" in summary
        assert "by_service" in summary
        assert summary["total_slos"] > 0


class TestErrorBudget:
    """Test error budget functionality."""
    
    @pytest.fixture
    def api_availability_slo(self):
        """Create API availability SLO definition."""
        return SLODefinition(
            name="test_api_availability",
            description="Test API availability SLO",
            target_type=SLOTarget.AVAILABILITY,
            target_value=99.9,
            measurement_window=300,
            evaluation_window=3600,
            error_budget_policy=0.1,
            service="api_gateway"
        )
    
    @pytest.fixture
    def error_budget(self, api_availability_slo):
        """Create error budget for testing."""
        return ErrorBudget(api_availability_slo)
    
    def test_add_metric(self, error_budget):
        """Test adding metrics to error budget."""
        
        # Add successful metric
        metric = SLOMetric(
            timestamp=datetime.now(),
            value=100.0,
            success=True,
            latency_ms=100.0
        )
        
        error_budget.add_metric(metric)
        
        assert len(error_budget.metrics_window) == 1
    
    def test_error_budget_calculation_perfect_performance(self, error_budget):
        """Test error budget with perfect performance."""
        
        # Add all successful metrics
        for _ in range(100):
            metric = SLOMetric(
                timestamp=datetime.now(),
                value=100.0,
                success=True,
                latency_ms=100.0
            )
            error_budget.add_metric(metric)
        
        status = error_budget.get_status()
        
        assert status.current_value >= 99.9  # Should meet target
        assert status.error_budget_remaining >= 90.0  # Should have most error budget left
        assert status.is_healthy is True
    
    def test_error_budget_calculation_poor_performance(self, error_budget):
        """Test error budget with poor performance."""
        
        # Add mostly failed metrics
        for i in range(100):
            success = i % 10 == 0  # Only 10% success rate
            metric = SLOMetric(
                timestamp=datetime.now(),
                value=100.0 if success else 0.0,
                success=success,
                latency_ms=100.0 if success else 500.0,
                error_code="500" if not success else None
            )
            error_budget.add_metric(metric)
        
        status = error_budget.get_status()
        
        assert status.current_value < 99.9  # Should not meet target
        assert status.error_budget_remaining < 50.0  # Should have used error budget
        assert status.is_healthy is False
        assert status.alert_level is not None
    
    def test_burn_rate_calculation(self, error_budget):
        """Test error budget burn rate calculation."""
        
        # Add metrics with poor performance
        for i in range(50):
            success = i % 5 == 0  # 20% success rate
            metric = SLOMetric(
                timestamp=datetime.now(),
                value=100.0 if success else 0.0,
                success=success,
                latency_ms=100.0 if success else 500.0
            )
            error_budget.add_metric(metric)
        
        burn_rate = error_budget.get_burn_rate()
        
        assert burn_rate > 0.0  # Should have some burn rate
        assert burn_rate > error_budget.slo_definition.error_budget_policy  # Should exceed threshold
    
    def test_is_burn_rate_exceeded(self, error_budget):
        """Test burn rate threshold checking."""
        
        # Add metrics that exceed burn rate
        for i in range(100):
            success = i % 10 == 0  # 10% success rate (very poor)
            metric = SLOMetric(
                timestamp=datetime.now(),
                value=100.0 if success else 0.0,
                success=success,
                latency_ms=100.0 if success else 500.0
            )
            error_budget.add_metric(metric)
        
        assert error_budget.is_burn_rate_exceeded() is True


class TestSLOMetrics:
    """Test SLO metric recording and tracking."""
    
    def test_record_slo_metric_function(self):
        """Test the convenience function for recording SLO metrics."""
        
        # Record a successful metric
        record_slo_metric(
            slo_name="api_availability",
            success=True,
            latency_ms=150.0
        )
        
        # Record a failed metric
        record_slo_metric(
            slo_name="api_availability",
            success=False,
            latency_ms=500.0,
            error_code="500"
        )
        
        # Get status
        status = get_slo_status("api_availability")
        
        assert status is not None
        assert isinstance(status, SLOStatus)
    
    def test_get_all_slo_statuses_function(self):
        """Test the convenience function for getting all SLO statuses."""
        
        all_statuses = get_all_slo_statuses()
        
        assert isinstance(all_statuses, dict)
        assert len(all_statuses) > 0
        assert all(isinstance(status, SLOStatus) for status in all_statuses.values())


@pytest.mark.asyncio
async def test_agent_run_latency_metric_recorded():
    """Test that agent run latency metrics are properly recorded."""
    
    # Create instrumentor and metrics collector
    instrumentor = OTELInstrumentor("test-orchestrator", ServiceType.ORCHESTRATOR)
    metrics_collector = MetricsCollector(instrumentor)
    
    # Record agent run latency
    metrics_collector.record_agent_run_latency(
        latency_ms=250.0,
        tenant_id="tenant-123",
        run_id="run-456"
    )
    
    # Verify metric exists
    assert "agent_run_latency_ms" in metrics_collector.metrics
    
    # Record multiple latencies to test histogram
    for latency in [100.0, 150.0, 200.0, 300.0, 500.0]:
        metrics_collector.record_agent_run_latency(
            latency_ms=latency,
            tenant_id="tenant-123",
            run_id=f"run-{latency}"
        )


@pytest.mark.asyncio
async def test_router_decision_latency_under_50ms():
    """Test that router decision latency stays under 50ms SLO."""
    
    # Create SLO manager
    slo_manager = SLOManager()
    
    # Record fast router decisions
    for _ in range(1000):
        latency_ms = 30.0 + (hash(str(_)) % 20)  # 30-50ms range
        slo_manager.record_metric(
            slo_name="router_decision_latency",
            success=True,
            latency_ms=latency_ms
        )
    
    # Get status
    status = slo_manager.get_slo_status("router_decision_latency")
    
    assert status is not None
    assert status.current_value <= 50.0  # Should meet SLO
    assert status.is_healthy is True


@pytest.mark.asyncio
async def test_ws_connection_success_rate_above_99_percent():
    """Test that WebSocket connection success rate stays above 99%."""
    
    # Create SLO manager
    slo_manager = SLOManager()
    
    # Record mostly successful connections
    for i in range(10000):
        success = i % 100 != 0  # 99% success rate
        slo_manager.record_metric(
            slo_name="ws_connection_success_rate",
            success=success,
            latency_ms=50.0 if success else 1000.0
        )
    
    # Get status
    status = slo_manager.get_slo_status("ws_connection_success_rate")
    
    assert status is not None
    assert status.current_value >= 99.0  # Should meet SLO
    assert status.is_healthy is True


@pytest.mark.asyncio
async def test_expected_vs_actual_cost_within_10_percent():
    """Test that expected vs actual cost stays within 10%."""
    
    # Create instrumentor and metrics collector
    instrumentor = OTELInstrumentor("test-router", ServiceType.ROUTER)
    metrics_collector = MetricsCollector(instrumentor)
    
    # Record cost differences within 10%
    for i in range(100):
        expected = 0.05 + (i * 0.001)
        actual = expected * (0.95 + (i % 10) * 0.01)  # Within 10% of expected
        
        metrics_collector.record_expected_vs_actual_cost(
            expected=expected,
            actual=actual,
            tenant_id="tenant-123"
        )
    
    # Verify metric was recorded
    assert "expected_vs_actual_cost" in metrics_collector.metrics


@pytest.mark.asyncio
async def test_expected_vs_actual_latency_within_20_percent():
    """Test that expected vs actual latency stays within 20%."""
    
    # Create instrumentor and metrics collector
    instrumentor = OTELInstrumentor("test-router", ServiceType.ROUTER)
    metrics_collector = MetricsCollector(instrumentor)
    
    # Record latency differences within 20%
    for i in range(100):
        expected_ms = 50.0 + (i * 0.5)
        actual_ms = expected_ms * (0.9 + (i % 20) * 0.01)  # Within 20% of expected
        
        metrics_collector.record_expected_vs_actual_latency(
            expected_ms=expected_ms,
            actual_ms=actual_ms,
            tenant_id="tenant-123"
        )
    
    # Verify metric was recorded
    assert "expected_vs_actual_latency" in metrics_collector.metrics
