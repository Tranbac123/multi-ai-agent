"""Integration tests for Analytics service."""

import pytest
import asyncio
import json
import os
from typing import Dict, Any

from apps.analytics_service.core.analytics_engine import AnalyticsEngine
from apps.analytics_service.core.dashboard_generator import DashboardGenerator


@pytest.fixture
async def analytics_engine_with_redis():
    """Analytics engine instance with real Redis connection."""
    import redis.asyncio as redis
    
    redis_client = redis.Redis(
        host="localhost",
        port=6379,
        db=2,  # Use different DB for tests
        decode_responses=False
    )
    
    engine = AnalyticsEngine(redis_client)
    
    yield engine
    
    # Cleanup
    await redis_client.flushdb()
    await redis_client.close()


@pytest.fixture
def dashboard_generator():
    """Dashboard generator instance."""
    return DashboardGenerator()


class TestAnalyticsIntegration:
    """Integration tests for Analytics service."""
    
    @pytest.mark.asyncio
    async def test_kpi_metrics_retrieval(self, analytics_engine_with_redis):
        """Test KPI metrics retrieval with real Redis."""
        metrics = await analytics_engine_with_redis.get_kpi_metrics("tenant123", "1h")
        
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
    
    @pytest.mark.asyncio
    async def test_caching_behavior(self, analytics_engine_with_redis):
        """Test caching behavior with real Redis."""
        # First call should cache the result
        metrics1 = await analytics_engine_with_redis.get_kpi_metrics("tenant123", "1h")
        
        # Second call should use cache (if available)
        metrics2 = await analytics_engine_with_redis.get_kpi_metrics("tenant123", "1h")
        
        # Both should return valid metrics
        assert isinstance(metrics1, type(metrics2))
        assert metrics1.tenant_id == metrics2.tenant_id
        assert metrics1.time_window == metrics2.time_window
    
    @pytest.mark.asyncio
    async def test_different_tenants(self, analytics_engine_with_redis):
        """Test metrics for different tenants."""
        metrics1 = await analytics_engine_with_redis.get_kpi_metrics("tenant1", "1h")
        metrics2 = await analytics_engine_with_redis.get_kpi_metrics("tenant2", "1h")
        
        assert metrics1.tenant_id == "tenant1"
        assert metrics2.tenant_id == "tenant2"
        assert metrics1.tenant_id != metrics2.tenant_id
    
    @pytest.mark.asyncio
    async def test_different_time_windows(self, analytics_engine_with_redis):
        """Test metrics for different time windows."""
        windows = ["1h", "24h", "7d", "30d"]
        
        for window in windows:
            metrics = await analytics_engine_with_redis.get_kpi_metrics("tenant123", window)
            assert metrics.time_window == window
            assert metrics.tenant_id == "tenant123"
    
    def test_dashboard_generation(self, dashboard_generator):
        """Test dashboard generation."""
        dashboard = dashboard_generator.generate_router_dashboard("tenant123")
        
        assert isinstance(dashboard, dict)
        assert "dashboard" in dashboard
        assert dashboard["dashboard"]["title"] == "Router Analytics - tenant123"
        assert "panels" in dashboard["dashboard"]
        assert len(dashboard["dashboard"]["panels"]) > 0
    
    def test_dashboard_save_and_load(self, dashboard_generator, tmp_path):
        """Test dashboard save and load functionality."""
        dashboard = dashboard_generator.generate_router_dashboard("tenant123")
        filepath = tmp_path / "test_dashboard.json"
        
        # Save dashboard
        dashboard_generator.save_dashboard_json(dashboard, str(filepath))
        
        # Verify file exists
        assert filepath.exists()
        
        # Load and verify content
        with open(filepath) as f:
            loaded_dashboard = json.load(f)
        
        assert loaded_dashboard == dashboard
        assert loaded_dashboard["dashboard"]["title"] == "Router Analytics - tenant123"
    
    def test_dashboard_panel_configuration(self, dashboard_generator):
        """Test dashboard panel configuration."""
        dashboard = dashboard_generator.generate_router_dashboard("tenant123")
        panels = dashboard["dashboard"]["panels"]
        
        # Check that all panels have required fields
        for panel in panels:
            assert "id" in panel
            assert "title" in panel
            assert "type" in panel
            assert "gridPos" in panel
            assert "targets" in panel
            
            # Check gridPos has required fields
            assert "h" in panel["gridPos"]
            assert "w" in panel["gridPos"]
            assert "x" in panel["gridPos"]
            assert "y" in panel["gridPos"]
            
            # Check targets is a list
            assert isinstance(panel["targets"], list)
    
    def test_dashboard_tenant_isolation(self, dashboard_generator):
        """Test that dashboards are properly isolated by tenant."""
        dashboard1 = dashboard_generator.generate_router_dashboard("tenant1")
        dashboard2 = dashboard_generator.generate_router_dashboard("tenant2")
        
        assert dashboard1["dashboard"]["title"] == "Router Analytics - tenant1"
        assert dashboard2["dashboard"]["title"] == "Router Analytics - tenant2"
        assert dashboard1 != dashboard2
    
    def test_dashboard_panel_types(self, dashboard_generator):
        """Test that dashboard contains expected panel types."""
        dashboard = dashboard_generator.generate_router_dashboard("tenant123")
        panels = dashboard["dashboard"]["panels"]
        
        panel_types = [panel["type"] for panel in panels]
        
        expected_types = ["stat", "graph", "piechart"]
        
        for panel_type in panel_types:
            assert panel_type in expected_types
    
    def test_dashboard_prometheus_queries(self, dashboard_generator):
        """Test that dashboard contains valid Prometheus queries."""
        dashboard = dashboard_generator.generate_router_dashboard("tenant123")
        panels = dashboard["dashboard"]["panels"]
        
        for panel in panels:
            for target in panel["targets"]:
                if "expr" in target:
                    expr = target["expr"]
                    # Check that expression contains tenant_id variable
                    assert "tenant_id" in expr
                    # Check that expression looks like a Prometheus query
                    assert any(op in expr for op in ["{", "}", "(", ")", "=", "\""])
    
    @pytest.mark.asyncio
    async def test_analytics_service_end_to_end(self, analytics_engine_with_redis, dashboard_generator):
        """Test end-to-end analytics service functionality."""
        # Get metrics
        metrics = await analytics_engine_with_redis.get_kpi_metrics("tenant123", "1h")
        
        # Generate dashboard
        dashboard = dashboard_generator.generate_router_dashboard("tenant123")
        
        # Verify metrics
        assert isinstance(metrics, type(analytics_engine_with_redis._get_default_metrics("", "")))
        assert metrics.tenant_id == "tenant123"
        assert metrics.time_window == "1h"
        
        # Verify dashboard
        assert isinstance(dashboard, dict)
        assert "dashboard" in dashboard
        assert dashboard["dashboard"]["title"] == "Router Analytics - tenant123"
        
        # Verify dashboard contains metrics-related panels
        panel_titles = [panel["title"] for panel in dashboard["dashboard"]["panels"]]
        assert "Success Rate" in panel_titles
        assert "Decision Latency" in panel_titles
        assert "Tier Distribution" in panel_titles
        assert "Router Misroute Rate" in panel_titles
    
    def test_dashboard_json_structure(self, dashboard_generator):
        """Test that generated dashboard has valid JSON structure."""
        dashboard = dashboard_generator.generate_router_dashboard("tenant123")
        
        # Convert to JSON and back to verify structure
        json_str = json.dumps(dashboard)
        parsed_dashboard = json.loads(json_str)
        
        assert parsed_dashboard == dashboard
        assert "dashboard" in parsed_dashboard
        assert "panels" in parsed_dashboard["dashboard"]
    
    def test_dashboard_time_configuration(self, dashboard_generator):
        """Test dashboard time configuration."""
        dashboard = dashboard_generator.generate_router_dashboard("tenant123")
        
        assert "time" in dashboard["dashboard"]
        assert "from" in dashboard["dashboard"]["time"]
        assert "to" in dashboard["dashboard"]["time"]
        assert "refresh" in dashboard["dashboard"]
        assert dashboard["dashboard"]["refresh"] == "30s"
    
    def test_dashboard_tags(self, dashboard_generator):
        """Test dashboard tags."""
        dashboard = dashboard_generator.generate_router_dashboard("tenant123")
        
        assert "tags" in dashboard["dashboard"]
        tags = dashboard["dashboard"]["tags"]
        assert "router" in tags
        assert "analytics" in tags
        assert "tenant123" in tags
