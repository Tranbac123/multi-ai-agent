"""Test dashboard generator functionality."""

import pytest
import json
import os
from unittest.mock import Mock, patch

from apps.analytics_service.core.dashboard_generator import GrafanaDashboardGenerator, DashboardPanel


class TestGrafanaDashboardGenerator:
    """Test GrafanaDashboardGenerator functionality."""

    @pytest.fixture
    def dashboard_generator(self):
        """Create GrafanaDashboardGenerator instance."""
        return GrafanaDashboardGenerator()

    def test_generate_router_analytics_dashboard(self, dashboard_generator):
        """Test generating router analytics dashboard."""
        dashboard = dashboard_generator.generate_router_analytics_dashboard()
        
        assert "dashboard" in dashboard
        assert dashboard["dashboard"]["title"] == "Router v2 Analytics"
        assert "panels" in dashboard["dashboard"]
        assert len(dashboard["dashboard"]["panels"]) == 8
        
        # Check specific panels exist
        panel_titles = [panel["title"] for panel in dashboard["dashboard"]["panels"]]
        assert "Router Decision Latency" in panel_titles
        assert "Router Misroute Rate" in panel_titles
        assert "Tier Distribution" in panel_titles
        assert "Expected vs Actual Cost" in panel_titles
        assert "Expected vs Actual Latency" in panel_titles

    def test_generate_realtime_analytics_dashboard(self, dashboard_generator):
        """Test generating realtime analytics dashboard."""
        dashboard = dashboard_generator.generate_realtime_analytics_dashboard()
        
        assert "dashboard" in dashboard
        assert dashboard["dashboard"]["title"] == "Realtime Service Analytics"
        assert "panels" in dashboard["dashboard"]
        assert len(dashboard["dashboard"]["panels"]) == 6
        
        # Check specific panels exist
        panel_titles = [panel["title"] for panel in dashboard["dashboard"]["panels"]]
        assert "WebSocket Active Connections" in panel_titles
        assert "WebSocket Backpressure Drops" in panel_titles
        assert "WebSocket Send Errors" in panel_titles
        assert "WebSocket Message Throughput" in panel_titles
        assert "WebSocket Queue Size" in panel_titles
        assert "WebSocket Connection Health" in panel_titles

    def test_generate_comprehensive_analytics_dashboard(self, dashboard_generator):
        """Test generating comprehensive analytics dashboard."""
        dashboard = dashboard_generator.generate_comprehensive_analytics_dashboard()
        
        assert "dashboard" in dashboard
        assert dashboard["dashboard"]["title"] == "Multi-AI-Agent Comprehensive Analytics"
        assert "panels" in dashboard["dashboard"]
        assert len(dashboard["dashboard"]["panels"]) == 13
        
        # Check specific panels exist
        panel_titles = [panel["title"] for panel in dashboard["dashboard"]["panels"]]
        assert "Overview Metrics" in panel_titles
        assert "SLO Compliance" in panel_titles
        assert "Router Decision Latency" in panel_titles
        assert "WebSocket Active Connections" in panel_titles
        assert "Cost Breakdown by Tier" in panel_titles
        assert "System Error Rate" in panel_titles
        assert "System Uptime" in panel_titles
        assert "Circuit Breaker Status" in panel_titles

    def test_router_decision_latency_panel(self, dashboard_generator):
        """Test router decision latency panel structure."""
        panel = dashboard_generator._create_router_decision_latency_panel()
        
        assert panel["title"] == "Router Decision Latency"
        assert panel["type"] == "stat"
        assert "gridPos" in panel
        assert "targets" in panel
        assert len(panel["targets"]) == 3
        
        # Check PromQL expressions
        expressions = [target["expr"] for target in panel["targets"]]
        assert any("histogram_quantile(0.50" in expr for expr in expressions)
        assert any("histogram_quantile(0.95" in expr for expr in expressions)
        assert any("histogram_quantile(0.99" in expr for expr in expressions)
        
        # Check field configuration
        assert "fieldConfig" in panel
        assert panel["fieldConfig"]["defaults"]["unit"] == "ms"
        assert "thresholds" in panel["fieldConfig"]["defaults"]

    def test_router_misroute_rate_panel(self, dashboard_generator):
        """Test router misroute rate panel structure."""
        panel = dashboard_generator._create_router_misroute_rate_panel()
        
        assert panel["title"] == "Router Misroute Rate"
        assert panel["type"] == "stat"
        assert len(panel["targets"]) == 1
        
        # Check PromQL expression
        expr = panel["targets"][0]["expr"]
        assert "rate(router_misroute_rate[5m])" in expr
        
        # Check field configuration
        assert panel["fieldConfig"]["defaults"]["unit"] == "percentunit"

    def test_tier_distribution_panel(self, dashboard_generator):
        """Test tier distribution panel structure."""
        panel = dashboard_generator._create_tier_distribution_panel()
        
        assert panel["title"] == "Tier Distribution"
        assert panel["type"] == "piechart"
        assert len(panel["targets"]) == 1
        
        # Check PromQL expression
        expr = panel["targets"][0]["expr"]
        assert "sum by (tier) (rate(tier_distribution[5m]))" in expr
        
        # Check options
        assert "options" in panel
        assert panel["options"]["pieType"] == "pie"

    def test_expected_vs_actual_cost_panel(self, dashboard_generator):
        """Test expected vs actual cost panel structure."""
        panel = dashboard_generator._create_expected_vs_actual_cost_panel()
        
        assert panel["title"] == "Expected vs Actual Cost"
        assert panel["type"] == "timeseries"
        assert len(panel["targets"]) == 1
        
        # Check PromQL expression
        expr = panel["targets"][0]["expr"]
        assert "rate(expected_vs_actual_cost[5m])" in expr

    def test_expected_vs_actual_latency_panel(self, dashboard_generator):
        """Test expected vs actual latency panel structure."""
        panel = dashboard_generator._create_expected_vs_actual_latency_panel()
        
        assert panel["title"] == "Expected vs Actual Latency"
        assert panel["type"] == "timeseries"
        assert len(panel["targets"]) == 1
        
        # Check PromQL expression
        expr = panel["targets"][0]["expr"]
        assert "rate(expected_vs_actual_latency[5m])" in expr

    def test_websocket_panels(self, dashboard_generator):
        """Test WebSocket-related panels."""
        # Test active connections panel
        panel = dashboard_generator._create_ws_active_connections_panel()
        assert panel["title"] == "WebSocket Active Connections"
        assert panel["type"] == "stat"
        assert "ws_active_connections" in panel["targets"][0]["expr"]
        
        # Test backpressure drops panel
        panel = dashboard_generator._create_ws_backpressure_drops_panel()
        assert panel["title"] == "WebSocket Backpressure Drops"
        assert "rate(ws_backpressure_drops[5m])" in panel["targets"][0]["expr"]
        
        # Test send errors panel
        panel = dashboard_generator._create_ws_send_errors_panel()
        assert panel["title"] == "WebSocket Send Errors"
        assert "rate(ws_send_errors[5m])" in panel["targets"][0]["expr"]

    def test_overview_metrics_panel(self, dashboard_generator):
        """Test overview metrics panel structure."""
        panel = dashboard_generator._create_overview_metrics_panel()
        
        assert panel["title"] == "Overview Metrics"
        assert panel["type"] == "stat"
        assert len(panel["targets"]) == 4
        
        # Check PromQL expressions
        expressions = [target["expr"] for target in panel["targets"]]
        assert any("rate(total_requests[5m])" in expr for expr in expressions)
        assert any("rate(successful_requests[5m])" in expr for expr in expressions)
        assert any("rate(failed_requests[5m])" in expr for expr in expressions)
        assert any("rate(total_cost[5m])" in expr for expr in expressions)

    def test_slo_compliance_panel(self, dashboard_generator):
        """Test SLO compliance panel structure."""
        panel = dashboard_generator._create_slo_compliance_panel()
        
        assert panel["title"] == "SLO Compliance"
        assert panel["type"] == "gauge"
        assert len(panel["targets"]) == 3
        
        # Check PromQL expressions
        expressions = [target["expr"] for target in panel["targets"]]
        assert "latency_slo_compliance" in expressions
        assert "availability_slo_compliance" in expressions
        assert "cost_slo_compliance" in expressions
        
        # Check field configuration
        field_config = panel["fieldConfig"]["defaults"]
        assert field_config["unit"] == "percentunit"
        assert field_config["min"] == 0
        assert field_config["max"] == 1

    def test_cost_breakdown_panel(self, dashboard_generator):
        """Test cost breakdown panel structure."""
        panel = dashboard_generator._create_cost_breakdown_panel()
        
        assert panel["title"] == "Cost Breakdown by Tier"
        assert panel["type"] == "timeseries"
        assert len(panel["targets"]) == 3
        
        # Check PromQL expressions
        expressions = [target["expr"] for target in panel["targets"]]
        assert any("rate(tier_a_cost[5m])" in expr for expr in expressions)
        assert any("rate(tier_b_cost[5m])" in expr for expr in expressions)
        assert any("rate(tier_c_cost[5m])" in expr for expr in expressions)
        
        # Check field configuration
        assert panel["fieldConfig"]["defaults"]["unit"] == "currencyUSD"

    def test_reliability_panels(self, dashboard_generator):
        """Test reliability-related panels."""
        # Test error rate panel
        panel = dashboard_generator._create_error_rate_panel()
        assert panel["title"] == "System Error Rate"
        assert "rate(system_errors_total[5m])" in panel["targets"][0]["expr"]
        
        # Test uptime panel
        panel = dashboard_generator._create_uptime_panel()
        assert panel["title"] == "System Uptime"
        assert "system_uptime" in panel["targets"][0]["expr"]
        
        # Test circuit breaker panel
        panel = dashboard_generator._create_circuit_breaker_panel()
        assert panel["title"] == "Circuit Breaker Status"
        assert "circuit_breaker_state" in panel["targets"][0]["expr"]

    def test_save_dashboard_to_file(self, dashboard_generator, tmp_path):
        """Test saving dashboard to file."""
        dashboard = dashboard_generator.generate_router_analytics_dashboard()
        filename = tmp_path / "test_dashboard.json"
        
        dashboard_generator.save_dashboard_to_file(dashboard, str(filename))
        
        assert filename.exists()
        
        # Verify file content
        with open(filename, 'r') as f:
            saved_dashboard = json.load(f)
        
        assert saved_dashboard["dashboard"]["title"] == "Router v2 Analytics"
        assert len(saved_dashboard["dashboard"]["panels"]) == 8

    def test_generate_all_dashboards(self, dashboard_generator, tmp_path):
        """Test generating all dashboards."""
        output_dir = str(tmp_path / "dashboards")
        
        dashboard_generator.generate_all_dashboards(output_dir)
        
        # Check that directory was created
        assert os.path.exists(output_dir)
        
        # Check that all dashboard files were created
        expected_files = [
            "router_analytics.json",
            "realtime_analytics.json",
            "comprehensive_analytics.json",
        ]
        
        for filename in expected_files:
            filepath = os.path.join(output_dir, filename)
            assert os.path.exists(filepath)
            
            # Verify file content
            with open(filepath, 'r') as f:
                dashboard = json.load(f)
            
            assert "dashboard" in dashboard
            assert "panels" in dashboard["dashboard"]

    def test_base_dashboard_structure(self, dashboard_generator):
        """Test base dashboard structure."""
        base_dashboard = dashboard_generator.base_dashboard
        
        assert "dashboard" in base_dashboard
        dashboard = base_dashboard["dashboard"]
        
        # Check required fields
        assert "title" in dashboard
        assert "tags" in dashboard
        assert "timezone" in dashboard
        assert "panels" in dashboard
        assert "time" in dashboard
        assert "refresh" in dashboard
        assert "schemaVersion" in dashboard
        assert "version" in dashboard
        
        # Check default values
        assert dashboard["timezone"] == "browser"
        assert dashboard["refresh"] == "30s"
        assert dashboard["schemaVersion"] == 30
        assert dashboard["version"] == 1
        assert dashboard["panels"] == []

    def test_panel_grid_positions(self, dashboard_generator):
        """Test that panels have proper grid positions."""
        dashboard = dashboard_generator.generate_comprehensive_analytics_dashboard()
        panels = dashboard["dashboard"]["panels"]
        
        # Check that all panels have gridPos
        for panel in panels:
            assert "gridPos" in panel
            grid_pos = panel["gridPos"]
            assert "h" in grid_pos  # height
            assert "w" in grid_pos  # width
            assert "x" in grid_pos  # x position
            assert "y" in grid_pos  # y position
            
            # Check that values are reasonable
            assert grid_pos["h"] > 0
            assert grid_pos["w"] > 0
            assert grid_pos["x"] >= 0
            assert grid_pos["y"] >= 0

    def test_panel_thresholds(self, dashboard_generator):
        """Test that panels have appropriate thresholds."""
        # Test router decision latency panel thresholds
        panel = dashboard_generator._create_router_decision_latency_panel()
        thresholds = panel["fieldConfig"]["defaults"]["thresholds"]["steps"]
        
        assert len(thresholds) == 3
        assert thresholds[0]["color"] == "green"
        assert thresholds[1]["color"] == "yellow"
        assert thresholds[1]["value"] == 50
        assert thresholds[2]["color"] == "red"
        assert thresholds[2]["value"] == 100
        
        # Test router misroute rate panel thresholds
        panel = dashboard_generator._create_router_misroute_rate_panel()
        thresholds = panel["fieldConfig"]["defaults"]["thresholds"]["steps"]
        
        assert len(thresholds) == 3
        assert thresholds[1]["value"] == 0.05  # 5%
        assert thresholds[2]["value"] == 0.1   # 10%

    def test_promql_expressions_format(self, dashboard_generator):
        """Test that PromQL expressions are properly formatted."""
        dashboard = dashboard_generator.generate_comprehensive_analytics_dashboard()
        panels = dashboard["dashboard"]["panels"]
        
        for panel in panels:
            if "targets" in panel:
                for target in panel["targets"]:
                    if "expr" in target:
                        expr = target["expr"]
                        # Check that expressions contain valid PromQL syntax
                        assert isinstance(expr, str)
                        assert len(expr) > 0
                        
                        # Check for common PromQL patterns
                        if "rate(" in expr:
                            assert "[" in expr and "]" in expr  # rate functions should have time range
                        if "histogram_quantile(" in expr:
                            assert "bucket" in expr  # histogram quantiles should reference buckets

    def test_dashboard_metadata(self, dashboard_generator):
        """Test dashboard metadata and tags."""
        dashboard = dashboard_generator.generate_router_analytics_dashboard()
        dashboard_data = dashboard["dashboard"]
        
        assert "tags" in dashboard_data
        tags = dashboard_data["tags"]
        assert "ai-agent" in tags
        assert "analytics" in tags
        assert "monitoring" in tags
        
        assert "time" in dashboard_data
        time_config = dashboard_data["time"]
        assert "from" in time_config
        assert "to" in time_config
        assert time_config["from"] == "now-1h"
        assert time_config["to"] == "now"
