"""Grafana dashboard generator for analytics service."""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class DashboardPanel:
    """Grafana dashboard panel configuration."""

    title: str
    type: str
    targets: List[Dict[str, Any]]
    grid_pos: Dict[str, int]
    options: Optional[Dict[str, Any]] = None


class GrafanaDashboardGenerator:
    """Generator for Grafana dashboards from analytics data."""

    def __init__(self):
        self.base_dashboard = {
            "dashboard": {
                "id": None,
                "title": "Multi-AI-Agent Analytics",
                "tags": ["ai-agent", "analytics", "monitoring"],
                "timezone": "browser",
                "panels": [],
                "time": {"from": "now-1h", "to": "now"},
                "refresh": "30s",
                "schemaVersion": 30,
                "version": 1,
                "links": [],
            }
        }

    def generate_router_analytics_dashboard(self) -> Dict[str, Any]:
        """Generate router analytics dashboard."""
        dashboard = self.base_dashboard.copy()
        dashboard["dashboard"]["title"] = "Router v2 Analytics"
        dashboard["dashboard"]["panels"] = [
            self._create_router_decision_latency_panel(),
            self._create_router_misroute_rate_panel(),
            self._create_tier_distribution_panel(),
            self._create_expected_vs_actual_cost_panel(),
            self._create_expected_vs_actual_latency_panel(),
            self._create_router_throughput_panel(),
            self._create_router_success_rate_panel(),
            self._create_router_error_rate_panel(),
        ]
        return dashboard

    def generate_realtime_analytics_dashboard(self) -> Dict[str, Any]:
        """Generate realtime analytics dashboard."""
        dashboard = self.base_dashboard.copy()
        dashboard["dashboard"]["title"] = "Realtime Service Analytics"
        dashboard["dashboard"]["panels"] = [
            self._create_ws_active_connections_panel(),
            self._create_ws_backpressure_drops_panel(),
            self._create_ws_send_errors_panel(),
            self._create_ws_message_throughput_panel(),
            self._create_ws_queue_size_panel(),
            self._create_ws_connection_health_panel(),
        ]
        return dashboard

    def generate_comprehensive_analytics_dashboard(self) -> Dict[str, Any]:
        """Generate comprehensive analytics dashboard."""
        dashboard = self.base_dashboard.copy()
        dashboard["dashboard"]["title"] = "Multi-AI-Agent Comprehensive Analytics"
        dashboard["dashboard"]["panels"] = [
            # Overview panels
            self._create_overview_metrics_panel(),
            self._create_slo_compliance_panel(),
            # Router panels
            self._create_router_decision_latency_panel(),
            self._create_router_misroute_rate_panel(),
            self._create_tier_distribution_panel(),
            # Realtime panels
            self._create_ws_active_connections_panel(),
            self._create_ws_backpressure_drops_panel(),
            # Cost and performance panels
            self._create_expected_vs_actual_cost_panel(),
            self._create_expected_vs_actual_latency_panel(),
            self._create_cost_breakdown_panel(),
            # Reliability panels
            self._create_error_rate_panel(),
            self._create_uptime_panel(),
            self._create_circuit_breaker_panel(),
        ]
        return dashboard

    def _create_router_decision_latency_panel(self) -> Dict[str, Any]:
        """Create router decision latency panel."""
        return {
            "id": 1,
            "title": "Router Decision Latency",
            "type": "stat",
            "gridPos": {"h": 8, "w": 6, "x": 0, "y": 0},
            "targets": [
                {
                    "expr": "histogram_quantile(0.50, rate(router_decision_latency_ms_bucket[5m]))",
                    "legendFormat": "p50",
                    "refId": "A",
                },
                {
                    "expr": "histogram_quantile(0.95, rate(router_decision_latency_ms_bucket[5m]))",
                    "legendFormat": "p95",
                    "refId": "B",
                },
                {
                    "expr": "histogram_quantile(0.99, rate(router_decision_latency_ms_bucket[5m]))",
                    "legendFormat": "p99",
                    "refId": "C",
                },
            ],
            "fieldConfig": {
                "defaults": {
                    "unit": "ms",
                    "thresholds": {
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 50},
                            {"color": "red", "value": 100},
                        ]
                    },
                }
            },
        }

    def _create_router_misroute_rate_panel(self) -> Dict[str, Any]:
        """Create router misroute rate panel."""
        return {
            "id": 2,
            "title": "Router Misroute Rate",
            "type": "stat",
            "gridPos": {"h": 8, "w": 6, "x": 6, "y": 0},
            "targets": [
                {
                    "expr": "rate(router_misroute_rate[5m])",
                    "legendFormat": "Misroute Rate",
                    "refId": "A",
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "unit": "percentunit",
                    "thresholds": {
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 0.05},
                            {"color": "red", "value": 0.1},
                        ]
                    },
                }
            },
        }

    def _create_tier_distribution_panel(self) -> Dict[str, Any]:
        """Create tier distribution panel."""
        return {
            "id": 3,
            "title": "Tier Distribution",
            "type": "piechart",
            "gridPos": {"h": 8, "w": 6, "x": 12, "y": 0},
            "targets": [
                {
                    "expr": "sum by (tier) (rate(tier_distribution[5m]))",
                    "legendFormat": "{{tier}}",
                    "refId": "A",
                }
            ],
            "options": {
                "pieType": "pie",
                "displayLabels": ["name", "value", "percent"],
            },
        }

    def _create_expected_vs_actual_cost_panel(self) -> Dict[str, Any]:
        """Create expected vs actual cost panel."""
        return {
            "id": 4,
            "title": "Expected vs Actual Cost",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
            "targets": [
                {
                    "expr": "rate(expected_vs_actual_cost[5m])",
                    "legendFormat": "Cost Ratio",
                    "refId": "A",
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "unit": "short",
                    "thresholds": {
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 1.1},
                            {"color": "red", "value": 1.2},
                        ]
                    },
                }
            },
        }

    def _create_expected_vs_actual_latency_panel(self) -> Dict[str, Any]:
        """Create expected vs actual latency panel."""
        return {
            "id": 5,
            "title": "Expected vs Actual Latency",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
            "targets": [
                {
                    "expr": "rate(expected_vs_actual_latency[5m])",
                    "legendFormat": "Latency Ratio",
                    "refId": "A",
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "unit": "short",
                    "thresholds": {
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 1.1},
                            {"color": "red", "value": 1.2},
                        ]
                    },
                }
            },
        }

    def _create_ws_active_connections_panel(self) -> Dict[str, Any]:
        """Create WebSocket active connections panel."""
        return {
            "id": 6,
            "title": "WebSocket Active Connections",
            "type": "stat",
            "gridPos": {"h": 8, "w": 6, "x": 0, "y": 16},
            "targets": [
                {
                    "expr": "ws_active_connections",
                    "legendFormat": "Active Connections",
                    "refId": "A",
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "unit": "short",
                    "thresholds": {
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 1000},
                            {"color": "red", "value": 2000},
                        ]
                    },
                }
            },
        }

    def _create_ws_backpressure_drops_panel(self) -> Dict[str, Any]:
        """Create WebSocket backpressure drops panel."""
        return {
            "id": 7,
            "title": "WebSocket Backpressure Drops",
            "type": "stat",
            "gridPos": {"h": 8, "w": 6, "x": 6, "y": 16},
            "targets": [
                {
                    "expr": "rate(ws_backpressure_drops[5m])",
                    "legendFormat": "Drops/sec",
                    "refId": "A",
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "unit": "short",
                    "thresholds": {
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 10},
                            {"color": "red", "value": 50},
                        ]
                    },
                }
            },
        }

    def _create_ws_send_errors_panel(self) -> Dict[str, Any]:
        """Create WebSocket send errors panel."""
        return {
            "id": 8,
            "title": "WebSocket Send Errors",
            "type": "stat",
            "gridPos": {"h": 8, "w": 6, "x": 12, "y": 16},
            "targets": [
                {
                    "expr": "rate(ws_send_errors[5m])",
                    "legendFormat": "Errors/sec",
                    "refId": "A",
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "unit": "short",
                    "thresholds": {
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 5},
                            {"color": "red", "value": 20},
                        ]
                    },
                }
            },
        }

    def _create_overview_metrics_panel(self) -> Dict[str, Any]:
        """Create overview metrics panel."""
        return {
            "id": 9,
            "title": "Overview Metrics",
            "type": "stat",
            "gridPos": {"h": 8, "w": 24, "x": 0, "y": 0},
            "targets": [
                {
                    "expr": "sum(rate(total_requests[5m]))",
                    "legendFormat": "Total Requests/sec",
                    "refId": "A",
                },
                {
                    "expr": "sum(rate(successful_requests[5m]))",
                    "legendFormat": "Successful Requests/sec",
                    "refId": "B",
                },
                {
                    "expr": "sum(rate(failed_requests[5m]))",
                    "legendFormat": "Failed Requests/sec",
                    "refId": "C",
                },
                {
                    "expr": "sum(rate(total_cost[5m]))",
                    "legendFormat": "Total Cost/sec",
                    "refId": "D",
                },
            ],
            "fieldConfig": {"defaults": {"unit": "short"}},
        }

    def _create_slo_compliance_panel(self) -> Dict[str, Any]:
        """Create SLO compliance panel."""
        return {
            "id": 10,
            "title": "SLO Compliance",
            "type": "gauge",
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
            "targets": [
                {
                    "expr": "latency_slo_compliance",
                    "legendFormat": "Latency SLO",
                    "refId": "A",
                },
                {
                    "expr": "availability_slo_compliance",
                    "legendFormat": "Availability SLO",
                    "refId": "B",
                },
                {
                    "expr": "cost_slo_compliance",
                    "legendFormat": "Cost SLO",
                    "refId": "C",
                },
            ],
            "fieldConfig": {
                "defaults": {
                    "unit": "percentunit",
                    "min": 0,
                    "max": 1,
                    "thresholds": {
                        "steps": [
                            {"color": "red", "value": 0},
                            {"color": "yellow", "value": 0.8},
                            {"color": "green", "value": 0.95},
                        ]
                    },
                }
            },
        }

    def _create_router_throughput_panel(self) -> Dict[str, Any]:
        """Create router throughput panel."""
        return {
            "id": 11,
            "title": "Router Throughput",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
            "targets": [
                {
                    "expr": "rate(router_requests_total[5m])",
                    "legendFormat": "Requests/sec",
                    "refId": "A",
                }
            ],
            "fieldConfig": {"defaults": {"unit": "reqps"}},
        }

    def _create_router_success_rate_panel(self) -> Dict[str, Any]:
        """Create router success rate panel."""
        return {
            "id": 12,
            "title": "Router Success Rate",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 16},
            "targets": [
                {
                    "expr": "rate(successful_requests[5m]) / rate(total_requests[5m])",
                    "legendFormat": "Success Rate",
                    "refId": "A",
                }
            ],
            "fieldConfig": {"defaults": {"unit": "percentunit", "min": 0, "max": 1}},
        }

    def _create_router_error_rate_panel(self) -> Dict[str, Any]:
        """Create router error rate panel."""
        return {
            "id": 13,
            "title": "Router Error Rate",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 16},
            "targets": [
                {
                    "expr": "rate(failed_requests[5m]) / rate(total_requests[5m])",
                    "legendFormat": "Error Rate",
                    "refId": "A",
                }
            ],
            "fieldConfig": {"defaults": {"unit": "percentunit", "min": 0, "max": 1}},
        }

    def _create_ws_message_throughput_panel(self) -> Dict[str, Any]:
        """Create WebSocket message throughput panel."""
        return {
            "id": 14,
            "title": "WebSocket Message Throughput",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 24},
            "targets": [
                {
                    "expr": "rate(ws_messages_sent[5m])",
                    "legendFormat": "Messages/sec",
                    "refId": "A",
                }
            ],
            "fieldConfig": {"defaults": {"unit": "short"}},
        }

    def _create_ws_queue_size_panel(self) -> Dict[str, Any]:
        """Create WebSocket queue size panel."""
        return {
            "id": 15,
            "title": "WebSocket Queue Size",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 24},
            "targets": [
                {"expr": "ws_queue_size", "legendFormat": "Queue Size", "refId": "A"}
            ],
            "fieldConfig": {"defaults": {"unit": "short"}},
        }

    def _create_ws_connection_health_panel(self) -> Dict[str, Any]:
        """Create WebSocket connection health panel."""
        return {
            "id": 16,
            "title": "WebSocket Connection Health",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 32},
            "targets": [
                {
                    "expr": "ws_connections_healthy",
                    "legendFormat": "Healthy Connections",
                    "refId": "A",
                },
                {
                    "expr": "ws_connections_unhealthy",
                    "legendFormat": "Unhealthy Connections",
                    "refId": "B",
                },
            ],
            "fieldConfig": {"defaults": {"unit": "short"}},
        }

    def _create_cost_breakdown_panel(self) -> Dict[str, Any]:
        """Create cost breakdown panel."""
        return {
            "id": 17,
            "title": "Cost Breakdown by Tier",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 32},
            "targets": [
                {
                    "expr": "rate(tier_a_cost[5m])",
                    "legendFormat": "Tier A Cost",
                    "refId": "A",
                },
                {
                    "expr": "rate(tier_b_cost[5m])",
                    "legendFormat": "Tier B Cost",
                    "refId": "B",
                },
                {
                    "expr": "rate(tier_c_cost[5m])",
                    "legendFormat": "Tier C Cost",
                    "refId": "C",
                },
            ],
            "fieldConfig": {"defaults": {"unit": "currencyUSD"}},
        }

    def _create_error_rate_panel(self) -> Dict[str, Any]:
        """Create error rate panel."""
        return {
            "id": 18,
            "title": "System Error Rate",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 40},
            "targets": [
                {
                    "expr": "rate(system_errors_total[5m])",
                    "legendFormat": "Error Rate",
                    "refId": "A",
                }
            ],
            "fieldConfig": {"defaults": {"unit": "short"}},
        }

    def _create_uptime_panel(self) -> Dict[str, Any]:
        """Create uptime panel."""
        return {
            "id": 19,
            "title": "System Uptime",
            "type": "stat",
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 40},
            "targets": [
                {"expr": "system_uptime", "legendFormat": "Uptime", "refId": "A"}
            ],
            "fieldConfig": {"defaults": {"unit": "percentunit", "min": 0, "max": 1}},
        }

    def _create_circuit_breaker_panel(self) -> Dict[str, Any]:
        """Create circuit breaker panel."""
        return {
            "id": 20,
            "title": "Circuit Breaker Status",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 24, "x": 0, "y": 48},
            "targets": [
                {
                    "expr": "circuit_breaker_state",
                    "legendFormat": "Circuit Breaker State",
                    "refId": "A",
                }
            ],
            "fieldConfig": {"defaults": {"unit": "short"}},
        }

    def save_dashboard_to_file(self, dashboard: Dict[str, Any], filename: str) -> None:
        """Save dashboard to JSON file."""
        with open(filename, "w") as f:
            json.dump(dashboard, f, indent=2)

    def generate_all_dashboards(
        self, output_dir: str = "platform/shared-observability/dashboards"
    ) -> None:
        """Generate all dashboards and save to files."""
        import os

        os.makedirs(output_dir, exist_ok=True)

        # Generate and save dashboards
        router_dashboard = self.generate_router_analytics_dashboard()
        self.save_dashboard_to_file(
            router_dashboard, f"{output_dir}/router_analytics.json"
        )

        realtime_dashboard = self.generate_realtime_analytics_dashboard()
        self.save_dashboard_to_file(
            realtime_dashboard, f"{output_dir}/realtime_analytics.json"
        )

        comprehensive_dashboard = self.generate_comprehensive_analytics_dashboard()
        self.save_dashboard_to_file(
            comprehensive_dashboard, f"{output_dir}/comprehensive_analytics.json"
        )

        print(f"Generated dashboards in {output_dir}/")
        print("- router_analytics.json")
        print("- realtime_analytics.json")
        print("- comprehensive_analytics.json")
