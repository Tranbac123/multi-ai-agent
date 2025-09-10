"""Unit tests for Analytics Service."""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock
import redis.asyncio as redis
from datetime import datetime

from apps.analytics-service.core.analytics_engine import AnalyticsEngine, KPIMetrics
from apps.analytics-service.core.dashboard_generator import DashboardGenerator


@pytest.fixture
async def mock_redis():
    """Mock Redis client."""
    redis_mock = AsyncMock(spec=redis.Redis)
    redis_mock.get.return_value = None
    redis_mock.setex.return_value = True
    redis_mock.ping.return_value = True
    return redis_mock


class TestAnalyticsEngine:
    """Test analytics engine."""
    
    @pytest.mark.asyncio
    async def test_get_kpi_metrics_basic(self, mock_redis):
        """Test basic KPI metrics retrieval."""
        engine = AnalyticsEngine(mock_redis)
        metrics = await engine.get_kpi_metrics("tenant123", "1h")
        
        assert metrics.tenant_id == "tenant123"
        assert metrics.time_window == "1h"
        assert 0.0 <= metrics.success_rate <= 1.0
        assert metrics.p50_latency > 0
        assert metrics.p95_latency > 0
        assert metrics.tokens_in > 0
        assert metrics.tokens_out > 0
        assert metrics.cost_per_run > 0
        assert isinstance(metrics.tier_distribution, dict)
        assert 'A' in metrics.tier_distribution
        assert 'B' in metrics.tier_distribution
        assert 'C' in metrics.tier_distribution
        assert 0.0 <= metrics.router_misroute_rate <= 1.0
        assert metrics.expected_vs_actual_cost > 0
        assert metrics.expected_vs_actual_latency > 0
        assert isinstance(metrics.timestamp, datetime)
    
    @pytest.mark.asyncio
    async def test_get_kpi_metrics_with_cache(self, mock_redis):
        """Test KPI metrics with cached data."""
        # Mock cached data
        cached_metrics = KPIMetrics(
            tenant_id="tenant123",
            time_window="1h",
            success_rate=0.98,
            p50_latency=45.0,
            p95_latency=180.0,
            tokens_in=120,
            tokens_out=180,
            cost_per_run=0.012,
            tier_distribution={'A': 60, 'B': 25, 'C': 15},
            router_misroute_rate=0.01,
            expected_vs_actual_cost=0.95,
            expected_vs_actual_latency=1.05,
            timestamp=datetime.utcnow()
        )
        
        # Mock Redis response
        mock_redis.get.return_value = json.dumps(cached_metrics.__dict__, default=str).encode()
        
        engine = AnalyticsEngine(mock_redis)
        metrics = await engine.get_kpi_metrics("tenant123", "1h")
        
        assert metrics.success_rate == 0.98
        assert metrics.p50_latency == 45.0
        assert metrics.p95_latency == 180.0
        assert metrics.tokens_in == 120
        assert metrics.tokens_out == 180
        assert metrics.cost_per_run == 0.012
        assert metrics.tier_distribution == {'A': 60, 'B': 25, 'C': 15}
        assert metrics.router_misroute_rate == 0.01
        assert metrics.expected_vs_actual_cost == 0.95
        assert metrics.expected_vs_actual_latency == 1.05
    
    @pytest.mark.asyncio
    async def test_cache_metrics(self, mock_redis):
        """Test metrics caching."""
        engine = AnalyticsEngine(mock_redis)
        metrics = await engine.get_kpi_metrics("tenant123", "1h")
        
        # Verify cache was called
        assert mock_redis.setex.called
        
        # Check cache key format
        call_args = mock_redis.setex.call_args
        cache_key = call_args[0][0]
        assert cache_key == "kpi_metrics:tenant123:1h"
        assert call_args[0][1] == 300  # TTL
    
    @pytest.mark.asyncio
    async def test_different_time_windows(self, mock_redis):
        """Test different time windows."""
        engine = AnalyticsEngine(mock_redis)
        
        time_windows = ["1h", "24h", "7d", "30d"]
        for window in time_windows:
            metrics = await engine.get_kpi_metrics("tenant123", window)
            assert metrics.time_window == window
            assert metrics.tenant_id == "tenant123"
    
    @pytest.mark.asyncio
    async def test_error_handling(self, mock_redis):
        """Test error handling."""
        # Mock Redis error
        mock_redis.get.side_effect = Exception("Redis error")
        
        engine = AnalyticsEngine(mock_redis)
        metrics = await engine.get_kpi_metrics("tenant123", "1h")
        
        # Should return default metrics on error
        assert metrics.tenant_id == "tenant123"
        assert metrics.time_window == "1h"
        assert metrics.success_rate == 0.95  # Default value


class TestDashboardGenerator:
    """Test dashboard generator."""
    
    def test_generate_router_dashboard(self):
        """Test router dashboard generation."""
        generator = DashboardGenerator()
        dashboard = generator.generate_router_dashboard("tenant123")
        
        assert "dashboard" in dashboard
        assert dashboard["dashboard"]["title"] == "Router Analytics - tenant123"
        assert "panels" in dashboard["dashboard"]
        assert len(dashboard["dashboard"]["panels"]) == 7
        
        # Check panel types
        panel_types = [panel["type"] for panel in dashboard["dashboard"]["panels"]]
        assert "stat" in panel_types
        assert "graph" in panel_types
        assert "piechart" in panel_types
    
    def test_dashboard_panels(self):
        """Test dashboard panel creation."""
        generator = DashboardGenerator()
        dashboard = generator.generate_router_dashboard("tenant123")
        
        panels = dashboard["dashboard"]["panels"]
        
        # Check specific panels exist
        panel_titles = [panel["title"] for panel in panels]
        expected_titles = [
            "Success Rate",
            "Latency Percentiles",
            "Tier Distribution",
            "Token Usage",
            "Cost per Run",
            "Router Misroute Rate",
            "Expected vs Actual"
        ]
        
        for title in expected_titles:
            assert title in panel_titles
    
    def test_panel_grid_positions(self):
        """Test panel grid positions."""
        generator = DashboardGenerator()
        dashboard = generator.generate_router_dashboard("tenant123")
        
        panels = dashboard["dashboard"]["panels"]
        
        for panel in panels:
            assert "gridPos" in panel
            grid_pos = panel["gridPos"]
            assert "h" in grid_pos
            assert "w" in grid_pos
            assert "x" in grid_pos
            assert "y" in grid_pos
            assert grid_pos["h"] > 0
            assert grid_pos["w"] > 0
            assert grid_pos["x"] >= 0
            assert grid_pos["y"] >= 0
    
    def test_panel_targets(self):
        """Test panel targets."""
        generator = DashboardGenerator()
        dashboard = generator.generate_router_dashboard("tenant123")
        
        panels = dashboard["dashboard"]["panels"]
        
        for panel in panels:
            if "targets" in panel:
                targets = panel["targets"]
                assert isinstance(targets, list)
                for target in targets:
                    assert "expr" in target
                    assert "refId" in target
                    assert "$tenant_id" in target["expr"]  # Should use template variable
    
    def test_save_dashboard_json(self, tmp_path):
        """Test saving dashboard as JSON."""
        generator = DashboardGenerator()
        dashboard = generator.generate_router_dashboard("tenant123")
        
        filepath = tmp_path / "test_dashboard.json"
        generator.save_dashboard_json(dashboard, str(filepath))
        
        assert filepath.exists()
        
        # Verify JSON content
        with open(filepath, 'r') as f:
            saved_dashboard = json.load(f)
        
        assert saved_dashboard == dashboard
    
    def test_panel_id_generation(self):
        """Test panel ID generation."""
        generator = DashboardGenerator()
        
        # Generate multiple dashboards to test ID counter
        dashboard1 = generator.generate_router_dashboard("tenant1")
        dashboard2 = generator.generate_router_dashboard("tenant2")
        
        panels1 = dashboard1["dashboard"]["panels"]
        panels2 = dashboard2["dashboard"]["panels"]
        
        # Check that panel IDs are unique and sequential
        ids1 = [panel["id"] for panel in panels1]
        ids2 = [panel["id"] for panel in panels2]
        
        assert len(set(ids1)) == len(ids1)  # All unique
        assert len(set(ids2)) == len(ids2)  # All unique
        assert min(ids2) > max(ids1)  # Sequential


class TestIntegration:
    """Integration tests for analytics service."""
    
    @pytest.mark.asyncio
    async def test_analytics_engine_with_dashboard_generator(self, mock_redis):
        """Test analytics engine with dashboard generator."""
        engine = AnalyticsEngine(mock_redis)
        generator = DashboardGenerator()
        
        # Get metrics
        metrics = await engine.get_kpi_metrics("tenant123", "1h")
        
        # Generate dashboard
        dashboard = generator.generate_router_dashboard("tenant123")
        
        # Both should work without errors
        assert metrics.tenant_id == "tenant123"
        assert dashboard["dashboard"]["title"] == "Router Analytics - tenant123"
    
    @pytest.mark.asyncio
    async def test_metrics_consistency(self, mock_redis):
        """Test metrics consistency across calls."""
        engine = AnalyticsEngine(mock_redis)
        
        # Get metrics multiple times
        metrics1 = await engine.get_kpi_metrics("tenant123", "1h")
        metrics2 = await engine.get_kpi_metrics("tenant123", "1h")
        
        # Should be consistent (using default values)
        assert metrics1.tenant_id == metrics2.tenant_id
        assert metrics1.time_window == metrics2.time_window
        assert metrics1.success_rate == metrics2.success_rate
        assert metrics1.p50_latency == metrics2.p50_latency
        assert metrics1.p95_latency == metrics2.p95_latency
    
    def test_dashboard_json_structure(self):
        """Test dashboard JSON structure."""
        generator = DashboardGenerator()
        dashboard = generator.generate_router_dashboard("tenant123")
        
        # Verify JSON structure
        assert isinstance(dashboard, dict)
        assert "dashboard" in dashboard
        
        dashboard_data = dashboard["dashboard"]
        required_fields = [
            "title", "tags", "timezone", "panels", "time", "refresh",
            "schemaVersion", "version", "links"
        ]
        
        for field in required_fields:
            assert field in dashboard_data
        
        # Verify time configuration
        assert "from" in dashboard_data["time"]
        assert "to" in dashboard_data["time"]
        assert dashboard_data["time"]["from"] == "now-1h"
        assert dashboard_data["time"]["to"] == "now"
        
        # Verify refresh interval
        assert dashboard_data["refresh"] == "30s"
        
        # Verify schema version
        assert dashboard_data["schemaVersion"] == 27


if __name__ == '__main__':
    pytest.main([__file__])
