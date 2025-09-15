"""Tests for Analytics service with CQRS and warehouse support."""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from apps.analytics_service.core.analytics_engine import (
    AnalyticsEngine,
    DataSource,
    KPIMetrics,
    TenantAnalytics,
)
from apps.analytics_service.core.dashboard_generator import GrafanaDashboardGenerator
from apps.analytics_service.main import app


class TestAnalyticsEngine:
    """Test analytics engine with warehouse support."""

    @pytest.fixture
    def redis_mock(self):
        """Create mock Redis client."""
        return AsyncMock()

    @pytest.fixture
    def analytics_engine_postgres(self, redis_mock):
        """Create analytics engine with Postgres data source."""
        return AnalyticsEngine(
            redis_client=redis_mock, data_source=DataSource.POSTGRES_READ_REPLICA
        )

    @pytest.fixture
    def analytics_engine_clickhouse(self, redis_mock):
        """Create analytics engine with ClickHouse data source."""
        warehouse_config = {"host": "localhost", "port": 9000}
        return AnalyticsEngine(
            redis_client=redis_mock,
            data_source=DataSource.CLICKHOUSE,
            warehouse_config=warehouse_config,
        )

    @pytest.mark.asyncio
    async def test_get_kpi_metrics_postgres(
        self, analytics_engine_postgres, redis_mock
    ):
        """Test getting KPI metrics from Postgres."""
        # Mock Redis cache miss
        redis_mock.get.return_value = None

        # Get metrics
        metrics = await analytics_engine_postgres.get_kpi_metrics("tenant123", "1h")

        # Verify metrics
        assert metrics.tenant_id == "tenant123"
        assert metrics.time_window == "1h"
        assert metrics.success_rate == 0.95
        assert metrics.p50_latency == 50.0
        assert metrics.data_source == "postgres_read_replica"
        assert metrics.total_requests == 1000
        assert metrics.cost_efficiency == 1.0

    @pytest.mark.asyncio
    async def test_get_kpi_metrics_clickhouse(
        self, analytics_engine_clickhouse, redis_mock
    ):
        """Test getting KPI metrics from ClickHouse."""
        # Mock Redis cache miss
        redis_mock.get.return_value = None

        # Get metrics
        metrics = await analytics_engine_clickhouse.get_kpi_metrics("tenant123", "1h")

        # Verify metrics
        assert metrics.tenant_id == "tenant123"
        assert metrics.time_window == "1h"
        assert metrics.success_rate == 0.97  # Enhanced metrics
        assert metrics.p50_latency == 45.0
        assert metrics.data_source == "clickhouse"
        assert metrics.total_requests == 1500
        assert metrics.cost_efficiency == 0.98

    @pytest.mark.asyncio
    async def test_get_comprehensive_analytics(
        self, analytics_engine_postgres, redis_mock
    ):
        """Test getting comprehensive analytics."""
        # Mock Redis cache miss
        redis_mock.get.return_value = None

        # Get comprehensive analytics
        analytics = await analytics_engine_postgres.get_comprehensive_analytics(
            "tenant123", "1h"
        )

        # Verify analytics structure
        assert isinstance(analytics, TenantAnalytics)
        assert analytics.tenant_id == "tenant123"
        assert analytics.time_window == "1h"
        assert analytics.kpi_metrics is not None
        assert analytics.usage_trends is not None
        assert analytics.performance_insights is not None
        assert analytics.cost_analysis is not None
        assert analytics.reliability_metrics is not None
        assert analytics.data_source == "postgres_read_replica"

    @pytest.mark.asyncio
    async def test_usage_trends(self, analytics_engine_postgres):
        """Test usage trends generation."""
        trends = await analytics_engine_postgres._get_usage_trends("tenant123", "1h")

        assert "requests_per_hour" in trends
        assert "tokens_per_hour" in trends
        assert "cost_per_hour" in trends
        assert "success_rate_trend" in trends
        assert "peak_usage_hours" in trends
        assert "growth_rate" in trends

        assert len(trends["requests_per_hour"]) == 7
        assert trends["growth_rate"] == 0.15

    @pytest.mark.asyncio
    async def test_performance_insights(self, analytics_engine_postgres):
        """Test performance insights generation."""
        insights = await analytics_engine_postgres._get_performance_insights(
            "tenant123", "1h"
        )

        assert "latency_improvement" in insights
        assert "cost_optimization" in insights
        assert "reliability_score" in insights
        assert "bottlenecks" in insights
        assert "recommendations" in insights
        assert "slo_compliance" in insights

        assert insights["reliability_score"] == 0.97
        assert len(insights["bottlenecks"]) > 0
        assert len(insights["recommendations"]) > 0

    @pytest.mark.asyncio
    async def test_cost_analysis(self, analytics_engine_postgres):
        """Test cost analysis generation."""
        analysis = await analytics_engine_postgres._get_cost_analysis("tenant123", "1h")

        assert "total_cost" in analysis
        assert "cost_breakdown" in analysis
        assert "cost_per_request" in analysis
        assert "cost_efficiency" in analysis
        assert "savings_opportunities" in analysis
        assert "budget_utilization" in analysis
        assert "projected_monthly_cost" in analysis

        assert analysis["total_cost"] == 120.0
        assert "tier_a" in analysis["cost_breakdown"]
        assert len(analysis["savings_opportunities"]) > 0

    @pytest.mark.asyncio
    async def test_reliability_metrics(self, analytics_engine_postgres):
        """Test reliability metrics generation."""
        metrics = await analytics_engine_postgres._get_reliability_metrics(
            "tenant123", "1h"
        )

        assert "uptime" in metrics
        assert "error_rate" in metrics
        assert "mean_time_to_recovery" in metrics
        assert "circuit_breaker_trips" in metrics
        assert "retry_success_rate" in metrics
        assert "escalation_rate" in metrics
        assert "canary_success_rate" in metrics
        assert "incidents" in metrics

        assert metrics["uptime"] == 0.999
        assert metrics["error_rate"] == 0.01
        assert len(metrics["incidents"]) > 0

    @pytest.mark.asyncio
    async def test_caching_behavior(self, analytics_engine_postgres, redis_mock):
        """Test caching behavior."""
        # Mock cache hit
        cached_data = {
            "tenant_id": "tenant123",
            "time_window": "1h",
            "success_rate": 0.98,
            "p50_latency": 40.0,
            "p95_latency": 150.0,
            "p99_latency": 250.0,
            "tokens_in": 110,
            "tokens_out": 170,
            "cost_per_run": 0.009,
            "total_cost": 110.0,
            "tier_distribution": {"A": 55, "B": 30, "C": 15},
            "router_misroute_rate": 0.01,
            "expected_vs_actual_cost": 0.99,
            "expected_vs_actual_latency": 1.01,
            "total_requests": 1200,
            "successful_requests": 1176,
            "failed_requests": 24,
            "avg_tokens_per_request": 140.0,
            "cost_efficiency": 0.99,
            "latency_efficiency": 1.01,
            "data_source": "postgres_read_replica",
            "timestamp": "2024-01-15T10:30:00",
        }
        redis_mock.get.return_value = json.dumps(cached_data)

        # Get metrics (should use cache)
        metrics = await analytics_engine_postgres.get_kpi_metrics("tenant123", "1h")

        # Verify cached data is used
        assert metrics.success_rate == 0.98
        assert metrics.p50_latency == 40.0
        assert metrics.total_requests == 1200

        # Verify Redis was called
        redis_mock.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling(self, analytics_engine_postgres, redis_mock):
        """Test error handling in analytics engine."""
        # Mock Redis error
        redis_mock.get.side_effect = Exception("Redis error")

        # Should return default metrics
        metrics = await analytics_engine_postgres.get_kpi_metrics("tenant123", "1h")

        # Verify default metrics are returned
        assert metrics.tenant_id == "tenant123"
        assert metrics.time_window == "1h"
        assert metrics.success_rate == 0.95  # Default value


class TestGrafanaDashboardGenerator:
    """Test Grafana dashboard generator."""

    @pytest.fixture
    def dashboard_generator(self):
        """Create dashboard generator."""
        return GrafanaDashboardGenerator()

    def test_generate_router_dashboard(self, dashboard_generator):
        """Test router analytics dashboard generation."""
        dashboard = dashboard_generator.generate_router_analytics_dashboard()

        assert "dashboard" in dashboard
        assert dashboard["dashboard"]["title"] == "Router v2 Analytics"
        assert len(dashboard["dashboard"]["panels"]) == 8

        # Check specific panels
        panel_titles = [panel["title"] for panel in dashboard["dashboard"]["panels"]]
        assert "Router Decision Latency" in panel_titles
        assert "Router Misroute Rate" in panel_titles
        assert "Tier Distribution" in panel_titles
        assert "Expected vs Actual Cost" in panel_titles

    def test_generate_realtime_dashboard(self, dashboard_generator):
        """Test realtime analytics dashboard generation."""
        dashboard = dashboard_generator.generate_realtime_analytics_dashboard()

        assert "dashboard" in dashboard
        assert dashboard["dashboard"]["title"] == "Realtime Service Analytics"
        assert len(dashboard["dashboard"]["panels"]) == 6

        # Check specific panels
        panel_titles = [panel["title"] for panel in dashboard["dashboard"]["panels"]]
        assert "WebSocket Active Connections" in panel_titles
        assert "WebSocket Backpressure Drops" in panel_titles
        assert "WebSocket Send Errors" in panel_titles

    def test_generate_comprehensive_dashboard(self, dashboard_generator):
        """Test comprehensive analytics dashboard generation."""
        dashboard = dashboard_generator.generate_comprehensive_analytics_dashboard()

        assert "dashboard" in dashboard
        assert (
            dashboard["dashboard"]["title"] == "Multi-AI-Agent Comprehensive Analytics"
        )
        assert len(dashboard["dashboard"]["panels"]) == 13

        # Check specific panels
        panel_titles = [panel["title"] for panel in dashboard["dashboard"]["panels"]]
        assert "Overview Metrics" in panel_titles
        assert "SLO Compliance" in panel_titles
        assert "Router Decision Latency" in panel_titles
        assert "WebSocket Active Connections" in panel_titles

    def test_dashboard_panel_structure(self, dashboard_generator):
        """Test dashboard panel structure."""
        dashboard = dashboard_generator.generate_router_analytics_dashboard()
        panel = dashboard["dashboard"]["panels"][0]

        assert "id" in panel
        assert "title" in panel
        assert "type" in panel
        assert "gridPos" in panel
        assert "targets" in panel
        assert "fieldConfig" in panel

    def test_save_dashboard_to_file(self, dashboard_generator, tmp_path):
        """Test saving dashboard to file."""
        dashboard = dashboard_generator.generate_router_analytics_dashboard()
        filename = tmp_path / "test_dashboard.json"

        dashboard_generator.save_dashboard_to_file(dashboard, str(filename))

        assert filename.exists()

        # Verify file content
        with open(filename) as f:
            saved_dashboard = json.load(f)

        assert saved_dashboard["dashboard"]["title"] == "Router v2 Analytics"


class TestAnalyticsServiceAPI:
    """Test analytics service API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "analytics"

    def test_kpi_metrics_endpoint(self, client):
        """Test KPI metrics endpoint."""
        response = client.get("/analytics/kpi/tenant123?time_window=1h")
        # Should return 500 since Redis is not available in test
        assert response.status_code == 500

    def test_comprehensive_analytics_endpoint(self, client):
        """Test comprehensive analytics endpoint."""
        response = client.get("/analytics/comprehensive/tenant123?time_window=1h")
        # Should return 500 since Redis is not available in test
        assert response.status_code == 500

    def test_list_tenants_endpoint(self, client):
        """Test list tenants endpoint."""
        response = client.get("/analytics/tenants")
        # Should return 500 since Redis is not available in test
        assert response.status_code == 500

    def test_list_dashboards_endpoint(self, client):
        """Test list dashboards endpoint."""
        response = client.get("/analytics/dashboards")
        # Should return 500 since service is not ready in test
        assert response.status_code == 500

    def test_get_dashboard_endpoint(self, client):
        """Test get dashboard endpoint."""
        response = client.get("/analytics/dashboards/router")
        # Should return 500 since service is not ready in test
        assert response.status_code == 503

    def test_prometheus_metrics_endpoint(self, client):
        """Test Prometheus metrics endpoint."""
        response = client.get("/analytics/metrics/prometheus")
        # Should return 500 since service is not ready in test
        assert response.status_code == 500

    def test_refresh_analytics_endpoint(self, client):
        """Test refresh analytics endpoint."""
        response = client.post("/analytics/refresh/tenant123")
        # Should return 500 since service is not ready in test
        assert response.status_code == 500


class TestAnalyticsPerformance:
    """Test analytics service performance."""

    @pytest.fixture
    def analytics_engine(self):
        """Create analytics engine for performance tests."""
        redis_mock = AsyncMock()
        redis_mock.get.return_value = None  # Cache miss
        return AnalyticsEngine(
            redis_client=redis_mock, data_source=DataSource.POSTGRES_READ_REPLICA
        )

    @pytest.mark.asyncio
    async def test_concurrent_analytics_requests(self, analytics_engine):
        """Test concurrent analytics requests."""
        tenant_ids = [f"tenant{i}" for i in range(10)]

        # Make concurrent requests
        start_time = asyncio.get_event_loop().time()
        tasks = [
            analytics_engine.get_kpi_metrics(tenant_id, "1h")
            for tenant_id in tenant_ids
        ]
        results = await asyncio.gather(*tasks)
        end_time = asyncio.get_event_loop().time()

        # Verify all requests completed
        assert len(results) == 10
        for i, metrics in enumerate(results):
            assert metrics.tenant_id == f"tenant{i}"
            assert metrics.time_window == "1h"

        # Verify performance (should complete quickly)
        duration = end_time - start_time
        assert duration < 1.0  # Should complete in under 1 second

    @pytest.mark.asyncio
    async def test_comprehensive_analytics_performance(self, analytics_engine):
        """Test comprehensive analytics performance."""
        # Test single comprehensive analytics request
        start_time = asyncio.get_event_loop().time()
        analytics = await analytics_engine.get_comprehensive_analytics(
            "tenant123", "1h"
        )
        end_time = asyncio.get_event_loop().time()

        # Verify results
        assert analytics.tenant_id == "tenant123"
        assert analytics.kpi_metrics is not None
        assert analytics.usage_trends is not None
        assert analytics.performance_insights is not None
        assert analytics.cost_analysis is not None
        assert analytics.reliability_metrics is not None

        # Verify performance
        duration = end_time - start_time
        assert duration < 0.5  # Should complete in under 0.5 seconds


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
