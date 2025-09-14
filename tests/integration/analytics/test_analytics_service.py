"""Test analytics service functionality."""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from datetime import datetime

from apps.analytics_service.main import app
from apps.analytics_service.core.analytics_engine import KPIMetrics, TenantAnalytics, DataSource


class TestAnalyticsService:
    """Test analytics service functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis_client = Mock()
        redis_client.ping = AsyncMock()
        redis_client.close = AsyncMock()
        redis_client.keys = AsyncMock(return_value=[])
        redis_client.delete = AsyncMock()
        return redis_client

    @pytest.fixture
    def mock_analytics_engine(self):
        """Create mock analytics engine."""
        analytics_engine = Mock()
        analytics_engine.get_kpi_metrics = AsyncMock()
        analytics_engine.get_comprehensive_analytics = AsyncMock()
        return analytics_engine

    @pytest.fixture
    def mock_dashboard_generator(self):
        """Create mock dashboard generator."""
        dashboard_generator = Mock()
        dashboard_generator.generate_router_analytics_dashboard.return_value = {
            "dashboard": {"title": "Router v2 Analytics", "panels": []}
        }
        dashboard_generator.generate_realtime_analytics_dashboard.return_value = {
            "dashboard": {"title": "Realtime Service Analytics", "panels": []}
        }
        dashboard_generator.generate_comprehensive_analytics_dashboard.return_value = {
            "dashboard": {"title": "Comprehensive Analytics", "panels": []}
        }
        dashboard_generator.generate_all_dashboards = Mock()
        return dashboard_generator

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        assert response.json()["service"] == "analytics"

    @pytest.mark.asyncio
    async def test_readiness_check_success(self, client, mock_redis):
        """Test readiness check when Redis is available."""
        with patch('apps.analytics_service.main.redis_client', mock_redis):
            response = client.get("/ready")
            assert response.status_code == 200
            assert response.json()["status"] == "ready"
            assert response.json()["service"] == "analytics"

    @pytest.mark.asyncio
    async def test_readiness_check_failure(self, client, mock_redis):
        """Test readiness check when Redis is unavailable."""
        mock_redis.ping.side_effect = Exception("Redis connection failed")
        
        with patch('apps.analytics_service.main.redis_client', mock_redis):
            response = client.get("/ready")
            assert response.status_code == 500
            assert "not ready" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_kpi_metrics_success(self, client, mock_analytics_engine):
        """Test getting KPI metrics successfully."""
        tenant_id = "tenant_123"
        time_window = "1h"
        
        # Mock KPI metrics
        mock_metrics = KPIMetrics(
            tenant_id=tenant_id,
            time_window=time_window,
            success_rate=0.97,
            p50_latency=45.0,
            p95_latency=180.0,
            p99_latency=300.0,
            tokens_in=120,
            tokens_out=180,
            cost_per_run=0.008,
            total_cost=120.0,
            tier_distribution={"A": 60, "B": 25, "C": 15},
            router_misroute_rate=0.015,
            expected_vs_actual_cost=0.98,
            expected_vs_actual_latency=1.02,
            total_requests=1500,
            successful_requests=1455,
            failed_requests=45,
            avg_tokens_per_request=150.0,
            cost_efficiency=0.98,
            latency_efficiency=1.02,
            data_source=DataSource.CLICKHOUSE.value,
            timestamp=datetime.utcnow(),
        )
        mock_analytics_engine.get_kpi_metrics.return_value = mock_metrics
        
        with patch('apps.analytics_service.main.analytics_engine', mock_analytics_engine):
            response = client.get(f"/analytics/kpi/{tenant_id}?time_window={time_window}")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["tenant_id"] == tenant_id
            assert data["time_window"] == time_window
            assert "metrics" in data
            
            metrics = data["metrics"]
            assert metrics["success_rate"] == 0.97
            assert metrics["p50_latency"] == 45.0
            assert metrics["tier_distribution"] == {"A": 60, "B": 25, "C": 15}
            assert metrics["router_misroute_rate"] == 0.015
            assert metrics["data_source"] == DataSource.CLICKHOUSE.value

    @pytest.mark.asyncio
    async def test_get_kpi_metrics_service_not_ready(self, client):
        """Test getting KPI metrics when service is not ready."""
        with patch('apps.analytics_service.main.analytics_engine', None):
            response = client.get("/analytics/kpi/tenant_123")
            assert response.status_code == 500
            assert "not ready" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_kpi_metrics_error(self, client, mock_analytics_engine):
        """Test getting KPI metrics with error."""
        tenant_id = "tenant_123"
        mock_analytics_engine.get_kpi_metrics.side_effect = Exception("Database error")
        
        with patch('apps.analytics_service.main.analytics_engine', mock_analytics_engine):
            response = client.get(f"/analytics/kpi/{tenant_id}")
            assert response.status_code == 500
            assert "Failed to get KPI metrics" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_comprehensive_analytics_success(self, client, mock_analytics_engine):
        """Test getting comprehensive analytics successfully."""
        tenant_id = "tenant_123"
        time_window = "24h"
        
        # Mock comprehensive analytics
        mock_kpi_metrics = KPIMetrics(
            tenant_id=tenant_id,
            time_window=time_window,
            success_rate=0.96,
            p50_latency=50.0,
            p95_latency=200.0,
            p99_latency=400.0,
            tokens_in=100,
            tokens_out=150,
            cost_per_run=0.01,
            total_cost=100.0,
            tier_distribution={"A": 50, "B": 30, "C": 20},
            router_misroute_rate=0.02,
            expected_vs_actual_cost=1.0,
            expected_vs_actual_latency=1.0,
            total_requests=1000,
            successful_requests=960,
            failed_requests=40,
            avg_tokens_per_request=125.0,
            cost_efficiency=1.0,
            latency_efficiency=1.0,
            data_source=DataSource.CLICKHOUSE.value,
            timestamp=datetime.utcnow(),
        )
        
        mock_analytics = TenantAnalytics(
            tenant_id=tenant_id,
            time_window=time_window,
            kpi_metrics=mock_kpi_metrics,
            usage_trends={
                "requests_per_hour": [100, 120, 110, 130],
                "growth_rate": 0.15,
            },
            performance_insights={
                "latency_improvement": 0.12,
                "cost_optimization": 0.08,
                "reliability_score": 0.97,
            },
            cost_analysis={
                "total_cost": 100.0,
                "cost_breakdown": {"tier_a": 50.0, "tier_b": 30.0, "tier_c": 20.0},
            },
            reliability_metrics={
                "uptime": 0.999,
                "error_rate": 0.01,
                "mean_time_to_recovery": 120,
            },
            data_source=DataSource.CLICKHOUSE.value,
            generated_at=datetime.utcnow(),
        )
        mock_analytics_engine.get_comprehensive_analytics.return_value = mock_analytics
        
        with patch('apps.analytics_service.main.analytics_engine', mock_analytics_engine):
            response = client.get(f"/analytics/comprehensive/{tenant_id}?time_window={time_window}")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["tenant_id"] == tenant_id
            assert data["time_window"] == time_window
            assert "kpi_metrics" in data
            assert "usage_trends" in data
            assert "performance_insights" in data
            assert "cost_analysis" in data
            assert "reliability_metrics" in data
            
            # Check KPI metrics
            kpi_metrics = data["kpi_metrics"]
            assert kpi_metrics["success_rate"] == 0.96
            assert kpi_metrics["tier_distribution"] == {"A": 50, "B": 30, "C": 20}
            
            # Check usage trends
            usage_trends = data["usage_trends"]
            assert "requests_per_hour" in usage_trends
            assert "growth_rate" in usage_trends
            
            # Check performance insights
            performance_insights = data["performance_insights"]
            assert "latency_improvement" in performance_insights
            assert "cost_optimization" in performance_insights
            
            # Check cost analysis
            cost_analysis = data["cost_analysis"]
            assert "total_cost" in cost_analysis
            assert "cost_breakdown" in cost_analysis
            
            # Check reliability metrics
            reliability_metrics = data["reliability_metrics"]
            assert "uptime" in reliability_metrics
            assert "error_rate" in reliability_metrics

    @pytest.mark.asyncio
    async def test_get_comprehensive_analytics_error(self, client, mock_analytics_engine):
        """Test getting comprehensive analytics with error."""
        tenant_id = "tenant_123"
        mock_analytics_engine.get_comprehensive_analytics.side_effect = Exception("Warehouse error")
        
        with patch('apps.analytics_service.main.analytics_engine', mock_analytics_engine):
            response = client.get(f"/analytics/comprehensive/{tenant_id}")
            assert response.status_code == 500
            assert "Failed to get comprehensive analytics" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_tenants_success(self, client, mock_redis):
        """Test listing tenants successfully."""
        # Mock Redis keys
        mock_keys = [
            b"kpi_metrics:tenant_123:1h",
            b"kpi_metrics:tenant_123:24h",
            b"kpi_metrics:tenant_456:1h",
            b"kpi_metrics:tenant_789:7d",
        ]
        mock_redis.keys.return_value = mock_keys
        
        with patch('apps.analytics_service.main.redis_client', mock_redis):
            response = client.get("/analytics/tenants")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "tenants" in data
            assert "total_count" in data
            assert len(data["tenants"]) == 3
            assert "tenant_123" in data["tenants"]
            assert "tenant_456" in data["tenants"]
            assert "tenant_789" in data["tenants"]
            assert data["total_count"] == 3

    @pytest.mark.asyncio
    async def test_list_tenants_service_not_ready(self, client):
        """Test listing tenants when service is not ready."""
        with patch('apps.analytics_service.main.redis_client', None):
            response = client.get("/analytics/tenants")
            assert response.status_code == 500
            assert "not ready" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_tenants_error(self, client, mock_redis):
        """Test listing tenants with error."""
        mock_redis.keys.side_effect = Exception("Redis error")
        
        with patch('apps.analytics_service.main.redis_client', mock_redis):
            response = client.get("/analytics/tenants")
            assert response.status_code == 500
            assert "Failed to list tenants" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_dashboards_success(self, client, mock_dashboard_generator):
        """Test listing dashboards successfully."""
        with patch('apps.analytics_service.main.dashboard_generator', mock_dashboard_generator):
            response = client.get("/analytics/dashboards")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "dashboards" in data
            assert "location" in data
            assert len(data["dashboards"]) == 3
            
            dashboard_names = [d["name"] for d in data["dashboards"]]
            assert "Router Analytics" in dashboard_names
            assert "Realtime Analytics" in dashboard_names
            assert "Comprehensive Analytics" in dashboard_names
            
            assert data["location"] == "observability/dashboards/"

    @pytest.mark.asyncio
    async def test_list_dashboards_service_not_ready(self, client):
        """Test listing dashboards when service is not ready."""
        with patch('apps.analytics_service.main.dashboard_generator', None):
            response = client.get("/analytics/dashboards")
            assert response.status_code == 500
            assert "not ready" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_dashboard_success(self, client, mock_dashboard_generator):
        """Test getting specific dashboard successfully."""
        with patch('apps.analytics_service.main.dashboard_generator', mock_dashboard_generator):
            response = client.get("/analytics/dashboards/router")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "dashboard" in data
            assert data["dashboard"]["title"] == "Router v2 Analytics"
            
            mock_dashboard_generator.generate_router_analytics_dashboard.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_dashboard_not_found(self, client, mock_dashboard_generator):
        """Test getting non-existent dashboard."""
        with patch('apps.analytics_service.main.dashboard_generator', mock_dashboard_generator):
            response = client.get("/analytics/dashboards/nonexistent")
            assert response.status_code == 404
            assert "Dashboard not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_dashboard_service_not_ready(self, client):
        """Test getting dashboard when service is not ready."""
        with patch('apps.analytics_service.main.dashboard_generator', None):
            response = client.get("/analytics/dashboards/router")
            assert response.status_code == 500
            assert "not ready" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_prometheus_metrics_success(self, client, mock_analytics_engine):
        """Test getting Prometheus metrics successfully."""
        with patch('apps.analytics_service.main.analytics_engine', mock_analytics_engine):
            response = client.get("/analytics/metrics/prometheus")
            
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/json"
            
            content = response.text
            assert "analytics_requests_total" in content
            assert "analytics_cache_hits_total" in content
            assert "analytics_warehouse_queries_total" in content

    @pytest.mark.asyncio
    async def test_get_prometheus_metrics_service_not_ready(self, client):
        """Test getting Prometheus metrics when service is not ready."""
        with patch('apps.analytics_service.main.analytics_engine', None):
            response = client.get("/analytics/metrics/prometheus")
            assert response.status_code == 500
            assert "not ready" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_refresh_analytics_success(self, client, mock_redis):
        """Test refreshing analytics successfully."""
        tenant_id = "tenant_123"
        
        # Mock Redis keys and delete
        mock_keys = [
            b"kpi_metrics:tenant_123:1h",
            b"kpi_metrics:tenant_123:24h",
            b"kpi_metrics:tenant_123:7d",
        ]
        mock_redis.keys.return_value = mock_keys
        mock_redis.delete = AsyncMock()
        
        with patch('apps.analytics_service.main.redis_client', mock_redis), \
             patch('apps.analytics_service.main.analytics_engine', Mock()):
            response = client.post(f"/analytics/refresh/{tenant_id}")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "message" in data
            assert f"Analytics cache cleared for tenant {tenant_id}" in data["message"]
            assert data["cleared_keys"] == 3
            
            mock_redis.keys.assert_called_once_with(f"kpi_metrics:{tenant_id}:*")
            mock_redis.delete.assert_called_once_with(*mock_keys)

    @pytest.mark.asyncio
    async def test_refresh_analytics_service_not_ready(self, client):
        """Test refreshing analytics when service is not ready."""
        with patch('apps.analytics_service.main.analytics_engine', None):
            response = client.post("/analytics/refresh/tenant_123")
            assert response.status_code == 500
            assert "not ready" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_refresh_analytics_error(self, client, mock_redis):
        """Test refreshing analytics with error."""
        tenant_id = "tenant_123"
        mock_redis.keys.side_effect = Exception("Redis error")
        
        with patch('apps.analytics_service.main.redis_client', mock_redis), \
             patch('apps.analytics_service.main.analytics_engine', Mock()):
            response = client.post(f"/analytics/refresh/{tenant_id}")
            assert response.status_code == 500
            assert "Failed to refresh analytics" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_query_parameters(self, client, mock_analytics_engine):
        """Test query parameters handling."""
        tenant_id = "tenant_123"
        time_window = "7d"
        
        mock_metrics = KPIMetrics(
            tenant_id=tenant_id,
            time_window=time_window,
            success_rate=0.95,
            p50_latency=50.0,
            p95_latency=200.0,
            p99_latency=400.0,
            tokens_in=100,
            tokens_out=150,
            cost_per_run=0.01,
            total_cost=100.0,
            tier_distribution={"A": 50, "B": 30, "C": 20},
            router_misroute_rate=0.02,
            expected_vs_actual_cost=1.0,
            expected_vs_actual_latency=1.0,
            total_requests=1000,
            successful_requests=950,
            failed_requests=50,
            avg_tokens_per_request=125.0,
            cost_efficiency=1.0,
            latency_efficiency=1.0,
            data_source=DataSource.CLICKHOUSE.value,
            timestamp=datetime.utcnow(),
        )
        mock_analytics_engine.get_kpi_metrics.return_value = mock_metrics
        
        with patch('apps.analytics_service.main.analytics_engine', mock_analytics_engine):
            response = client.get(f"/analytics/kpi/{tenant_id}?time_window={time_window}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["time_window"] == time_window
            
            # Verify the analytics engine was called with correct parameters
            mock_analytics_engine.get_kpi_metrics.assert_called_once_with(tenant_id, time_window)

    @pytest.mark.asyncio
    async def test_default_time_window(self, client, mock_analytics_engine):
        """Test default time window when not specified."""
        tenant_id = "tenant_123"
        
        mock_metrics = KPIMetrics(
            tenant_id=tenant_id,
            time_window="1h",  # Default
            success_rate=0.95,
            p50_latency=50.0,
            p95_latency=200.0,
            p99_latency=400.0,
            tokens_in=100,
            tokens_out=150,
            cost_per_run=0.01,
            total_cost=100.0,
            tier_distribution={"A": 50, "B": 30, "C": 20},
            router_misroute_rate=0.02,
            expected_vs_actual_cost=1.0,
            expected_vs_actual_latency=1.0,
            total_requests=1000,
            successful_requests=950,
            failed_requests=50,
            avg_tokens_per_request=125.0,
            cost_efficiency=1.0,
            latency_efficiency=1.0,
            data_source=DataSource.CLICKHOUSE.value,
            timestamp=datetime.utcnow(),
        )
        mock_analytics_engine.get_kpi_metrics.return_value = mock_metrics
        
        with patch('apps.analytics_service.main.analytics_engine', mock_analytics_engine):
            response = client.get(f"/analytics/kpi/{tenant_id}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["time_window"] == "1h"  # Default value
            
            # Verify the analytics engine was called with default time window
            mock_analytics_engine.get_kpi_metrics.assert_called_once_with(tenant_id, "1h")
