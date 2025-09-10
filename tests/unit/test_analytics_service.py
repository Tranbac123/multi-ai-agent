"""Unit tests for Analytics service."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any
from datetime import datetime

from apps.analytics_service.core.analytics_engine import AnalyticsEngine, KPIMetrics
from apps.analytics_service.core.dashboard_generator import DashboardGenerator


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.setex = AsyncMock()
    redis_mock.ping = AsyncMock()
    return redis_mock


@pytest.fixture
def analytics_engine(mock_redis):
    """Analytics engine instance with mocked dependencies."""
    return AnalyticsEngine(mock_redis)


@pytest.fixture
def dashboard_generator():
    """Dashboard generator instance."""
    return DashboardGenerator()


class TestAnalyticsEngine:
    """Test analytics engine functionality."""
    
    @pytest.mark.asyncio
    async def test_get_kpi_metrics_basic(self, analytics_engine):
        """Test basic KPI metrics retrieval."""
        metrics = await analytics_engine.get_kpi_metrics("tenant123", "1h")
        
        assert isinstance(metrics, KPIMetrics)
        assert metrics.tenant_id == "tenant123"
        assert metrics.time_window == "1h"
        assert 0 <= metrics.success_rate <= 1
        assert metrics.p50_latency > 0
        assert metrics.p95_latency > 0
        assert metrics.tokens_in >= 0
        assert metrics.tokens_out >= 0
        assert metrics.cost_per_run >= 0
        assert isinstance(metrics.tier_distribution, dict)
        assert 0 <= metrics.router_misroute_rate <= 1
        assert metrics.expected_vs_actual_cost > 0
        assert metrics.expected_vs_actual_latency > 0
        assert isinstance(metrics.timestamp, datetime)
    
    @pytest.mark.asyncio
    async def test_get_kpi_metrics_different_windows(self, analytics_engine):
        """Test KPI metrics for different time windows."""
        windows = ["1h", "24h", "7d", "30d"]
        
        for window in windows:
            metrics = await analytics_engine.get_kpi_metrics("tenant123", window)
            assert metrics.time_window == window
            assert metrics.tenant_id == "tenant123"
    
    @pytest.mark.asyncio
    async def test_caching_behavior(self, analytics_engine, mock_redis):
        """Test that metrics are cached properly."""
        # First call should cache the result
        metrics1 = await analytics_engine.get_kpi_metrics("tenant123", "1h")
        
        # Verify cache was called
        mock_redis.setex.assert_called()
        
        # Mock cache hit
        mock_redis.get.return_value = '{"tenant_id": "tenant123", "time_window": "1h", "success_rate": 0.95, "p50_latency": 50.0, "p95_latency": 200.0, "tokens_in": 100, "tokens_out": 150, "cost_per_run": 0.01, "tier_distribution": {"A": 50, "B": 30, "C": 20}, "router_misroute_rate": 0.02, "expected_vs_actual_cost": 1.0, "expected_vs_actual_latency": 1.0, "timestamp": "2024-01-01T00:00:00"}'
        
        # Second call should use cache
        metrics2 = await analytics_engine.get_kpi_metrics("tenant123", "1h")
        
        # Should have called get for cache lookup
        mock_redis.get.assert_called()
    
    @pytest.mark.asyncio
    async def test_error_handling(self, analytics_engine, mock_redis):
        """Test error handling in analytics engine."""
        # Mock Redis error
        mock_redis.get.side_effect = Exception("Redis error")
        
        # Should still return default metrics
        metrics = await analytics_engine.get_kpi_metrics("tenant123", "1h")
        
        assert isinstance(metrics, KPIMetrics)
        assert metrics.tenant_id == "tenant123"


class TestDashboardGenerator:
    """Test dashboard generator functionality."""
    
    def test_generate_router_dashboard(self, dashboard_generator):
        """Test router dashboard generation."""
        dashboard = dashboard_generator.generate_router_dashboard("tenant123")
        
        assert isinstance(dashboard, dict)
        assert "dashboard" in dashboard
        assert dashboard["dashboard"]["title"] == "Router Analytics - tenant123"
        assert "panels" in dashboard["dashboard"]
        assert len(dashboard["dashboard"]["panels"]) > 0
    
    def test_dashboard_panels(self, dashboard_generator):
        """Test that dashboard contains expected panels."""
        dashboard = dashboard_generator.generate_router_dashboard("tenant123")
        panels = dashboard["dashboard"]["panels"]
        
        panel_titles = [panel["title"] for panel in panels]
        
        expected_panels = [
            "Success Rate",
            "Decision Latency",
            "Tier Distribution",
            "Token Usage",
            "Cost per Run",
            "Router Misroute Rate",
            "Expected vs Actual"
        ]
        
        for expected_panel in expected_panels:
            assert expected_panel in panel_titles
    
    def test_panel_configuration(self, dashboard_generator):
        """Test panel configuration."""
        dashboard = dashboard_generator.generate_router_dashboard("tenant123")
        panels = dashboard["dashboard"]["panels"]
        
        for panel in panels:
            assert "id" in panel
            assert "title" in panel
            assert "type" in panel
            assert "gridPos" in panel
            assert "targets" in panel
    
    def test_success_rate_panel(self, dashboard_generator):
        """Test success rate panel configuration."""
        panel = dashboard_generator._create_success_rate_panel()
        
        assert panel["title"] == "Success Rate"
        assert panel["type"] == "stat"
        assert "fieldConfig" in panel
        assert panel["fieldConfig"]["defaults"]["unit"] == "percent"
        assert panel["fieldConfig"]["defaults"]["min"] == 0
        assert panel["fieldConfig"]["defaults"]["max"] == 1
    
    def test_latency_panel(self, dashboard_generator):
        """Test latency panel configuration."""
        panel = dashboard_generator._create_latency_panel()
        
        assert panel["title"] == "Latency Percentiles"
        assert panel["type"] == "graph"
        assert len(panel["targets"]) >= 2  # P50 and P95
        assert "yAxes" in panel
    
    def test_tier_distribution_panel(self, dashboard_generator):
        """Test tier distribution panel configuration."""
        panel = dashboard_generator._create_tier_distribution_panel()
        
        assert panel["title"] == "Tier Distribution"
        assert panel["type"] == "piechart"
        assert len(panel["targets"]) == 3  # A, B, C tiers
    
    def test_save_dashboard_json(self, dashboard_generator, tmp_path):
        """Test saving dashboard as JSON."""
        dashboard = {"test": "dashboard"}
        filepath = tmp_path / "test_dashboard.json"
        
        dashboard_generator.save_dashboard_json(dashboard, str(filepath))
        
        assert filepath.exists()
        with open(filepath) as f:
            import json
            saved_data = json.load(f)
            assert saved_data == dashboard
    
    def test_panel_id_generation(self, dashboard_generator):
        """Test panel ID generation."""
        id1 = dashboard_generator._get_next_panel_id()
        id2 = dashboard_generator._get_next_panel_id()
        
        assert id1 == 1
        assert id2 == 2
        assert id2 > id1


class TestKPIMetrics:
    """Test KPI metrics data structure."""
    
    def test_kpi_metrics_creation(self):
        """Test KPI metrics creation."""
        metrics = KPIMetrics(
            tenant_id="tenant123",
            time_window="1h",
            success_rate=0.95,
            p50_latency=50.0,
            p95_latency=200.0,
            tokens_in=100,
            tokens_out=150,
            cost_per_run=0.01,
            tier_distribution={"A": 50, "B": 30, "C": 20},
            router_misroute_rate=0.02,
            expected_vs_actual_cost=1.0,
            expected_vs_actual_latency=1.0,
            timestamp=datetime.utcnow()
        )
        
        assert metrics.tenant_id == "tenant123"
        assert metrics.time_window == "1h"
        assert metrics.success_rate == 0.95
        assert metrics.p50_latency == 50.0
        assert metrics.p95_latency == 200.0
        assert metrics.tokens_in == 100
        assert metrics.tokens_out == 150
        assert metrics.cost_per_run == 0.01
        assert metrics.tier_distribution == {"A": 50, "B": 30, "C": 20}
        assert metrics.router_misroute_rate == 0.02
        assert metrics.expected_vs_actual_cost == 1.0
        assert metrics.expected_vs_actual_latency == 1.0
        assert isinstance(metrics.timestamp, datetime)


class TestAnalyticsServiceIntegration:
    """Test analytics service integration."""
    
    @pytest.mark.asyncio
    async def test_analytics_engine_with_dashboard_generator(self, mock_redis):
        """Test analytics engine with dashboard generator."""
        analytics_engine = AnalyticsEngine(mock_redis)
        dashboard_generator = DashboardGenerator()
        
        # Get metrics
        metrics = await analytics_engine.get_kpi_metrics("tenant123", "1h")
        
        # Generate dashboard
        dashboard = dashboard_generator.generate_router_dashboard("tenant123")
        
        assert isinstance(metrics, KPIMetrics)
        assert isinstance(dashboard, dict)
        assert metrics.tenant_id == "tenant123"
        assert "tenant123" in dashboard["dashboard"]["title"]
    
    @pytest.mark.asyncio
    async def test_error_recovery(self, mock_redis):
        """Test error recovery in analytics service."""
        # Mock Redis connection error
        mock_redis.get.side_effect = Exception("Connection error")
        mock_redis.setex.side_effect = Exception("Connection error")
        
        analytics_engine = AnalyticsEngine(mock_redis)
        
        # Should still return default metrics
        metrics = await analytics_engine.get_kpi_metrics("tenant123", "1h")
        
        assert isinstance(metrics, KPIMetrics)
        assert metrics.tenant_id == "tenant123"
    
    def test_dashboard_tenant_isolation(self, dashboard_generator):
        """Test that dashboards are tenant-specific."""
        dashboard1 = dashboard_generator.generate_router_dashboard("tenant1")
        dashboard2 = dashboard_generator.generate_router_dashboard("tenant2")
        
        assert dashboard1["dashboard"]["title"] == "Router Analytics - tenant1"
        assert dashboard2["dashboard"]["title"] == "Router Analytics - tenant2"
        assert dashboard1 != dashboard2