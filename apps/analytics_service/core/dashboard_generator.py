"""Dashboard generator for Grafana dashboards."""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class DashboardPanel:
    """Dashboard panel configuration."""
    title: str
    type: str
    targets: List[Dict[str, Any]]
    gridPos: Dict[str, int]
    options: Optional[Dict[str, Any]] = None


class DashboardGenerator:
    """Dashboard generator for Grafana dashboards."""
    
    def __init__(self):
        self.panel_id_counter = 1
    
    def generate_router_dashboard(self, tenant_id: str) -> Dict[str, Any]:
        """Generate router analytics dashboard."""
        try:
            dashboard = {
                "dashboard": {
                    "id": None,
                    "title": f"Router Analytics - {tenant_id}",
                    "tags": ["router", "analytics", tenant_id],
                    "timezone": "browser",
                    "panels": [],
                    "time": {
                        "from": "now-1h",
                        "to": "now"
                    },
                    "refresh": "30s",
                    "schemaVersion": 27,
                    "version": 0,
                    "links": []
                }
            }
            
            # Add panels
            panels = [
                self._create_success_rate_panel(),
                self._create_latency_panel(),
                self._create_tier_distribution_panel(),
                self._create_token_metrics_panel(),
                self._create_cost_metrics_panel(),
                self._create_misroute_rate_panel(),
                self._create_expected_vs_actual_panel()
            ]
            
            dashboard["dashboard"]["panels"] = panels
            
            return dashboard
            
        except Exception as e:
            logger.error("Failed to generate router dashboard", error=str(e))
            return {}
    
    def _create_success_rate_panel(self) -> Dict[str, Any]:
        """Create success rate panel."""
        return {
            "id": self._get_next_panel_id(),
            "title": "Success Rate",
            "type": "stat",
            "gridPos": {"h": 8, "w": 6, "x": 0, "y": 0},
            "targets": [
                {
                    "expr": "router_success_rate{tenant_id=\"$tenant_id\"}",
                    "legendFormat": "Success Rate",
                    "refId": "A"
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "unit": "percent",
                    "min": 0,
                    "max": 1,
                    "thresholds": {
                        "steps": [
                            {"color": "red", "value": 0},
                            {"color": "yellow", "value": 0.8},
                            {"color": "green", "value": 0.95}
                        ]
                    }
                }
            }
        }
    
    def _create_latency_panel(self) -> Dict[str, Any]:
        """Create latency panel."""
        return {
            "id": self._get_next_panel_id(),
            "title": "Latency Percentiles",
            "type": "graph",
            "gridPos": {"h": 8, "w": 12, "x": 6, "y": 0},
            "targets": [
                {
                    "expr": "histogram_quantile(0.50, router_latency_histogram{tenant_id=\"$tenant_id\"})",
                    "legendFormat": "P50",
                    "refId": "A"
                },
                {
                    "expr": "histogram_quantile(0.95, router_latency_histogram{tenant_id=\"$tenant_id\"})",
                    "legendFormat": "P95",
                    "refId": "B"
                }
            ],
            "yAxes": [
                {
                    "label": "Latency (ms)",
                    "min": 0
                }
            ]
        }
    
    def _create_tier_distribution_panel(self) -> Dict[str, Any]:
        """Create tier distribution panel."""
        return {
            "id": self._get_next_panel_id(),
            "title": "Tier Distribution",
            "type": "piechart",
            "gridPos": {"h": 8, "w": 6, "x": 18, "y": 0},
            "targets": [
                {
                    "expr": "router_tier_distribution{tenant_id=\"$tenant_id\", tier=\"A\"}",
                    "legendFormat": "Tier A",
                    "refId": "A"
                },
                {
                    "expr": "router_tier_distribution{tenant_id=\"$tenant_id\", tier=\"B\"}",
                    "legendFormat": "Tier B",
                    "refId": "B"
                },
                {
                    "expr": "router_tier_distribution{tenant_id=\"$tenant_id\", tier=\"C\"}",
                    "legendFormat": "Tier C",
                    "refId": "C"
                }
            ]
        }
    
    def _create_token_metrics_panel(self) -> Dict[str, Any]:
        """Create token metrics panel."""
        return {
            "id": self._get_next_panel_id(),
            "title": "Token Usage",
            "type": "graph",
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
            "targets": [
                {
                    "expr": "router_tokens_in{tenant_id=\"$tenant_id\"}",
                    "legendFormat": "Tokens In",
                    "refId": "A"
                },
                {
                    "expr": "router_tokens_out{tenant_id=\"$tenant_id\"}",
                    "legendFormat": "Tokens Out",
                    "refId": "B"
                }
            ],
            "yAxes": [
                {
                    "label": "Tokens",
                    "min": 0
                }
            ]
        }
    
    def _create_cost_metrics_panel(self) -> Dict[str, Any]:
        """Create cost metrics panel."""
        return {
            "id": self._get_next_panel_id(),
            "title": "Cost per Run",
            "type": "stat",
            "gridPos": {"h": 8, "w": 6, "x": 12, "y": 8},
            "targets": [
                {
                    "expr": "router_cost_per_run{tenant_id=\"$tenant_id\"}",
                    "legendFormat": "Cost per Run",
                    "refId": "A"
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "unit": "currencyUSD",
                    "min": 0
                }
            }
        }
    
    def _create_misroute_rate_panel(self) -> Dict[str, Any]:
        """Create misroute rate panel."""
        return {
            "id": self._get_next_panel_id(),
            "title": "Router Misroute Rate",
            "type": "stat",
            "gridPos": {"h": 8, "w": 6, "x": 18, "y": 8},
            "targets": [
                {
                    "expr": "router_misroute_rate{tenant_id=\"$tenant_id\"}",
                    "legendFormat": "Misroute Rate",
                    "refId": "A"
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "unit": "percent",
                    "min": 0,
                    "max": 1,
                    "thresholds": {
                        "steps": [
                            {"color": "green", "value": 0},
                            {"color": "yellow", "value": 0.05},
                            {"color": "red", "value": 0.1}
                        ]
                    }
                }
            }
        }
    
    def _create_expected_vs_actual_panel(self) -> Dict[str, Any]:
        """Create expected vs actual metrics panel."""
        return {
            "id": self._get_next_panel_id(),
            "title": "Expected vs Actual",
            "type": "graph",
            "gridPos": {"h": 8, "w": 24, "x": 0, "y": 16},
            "targets": [
                {
                    "expr": "router_expected_vs_actual_cost{tenant_id=\"$tenant_id\"}",
                    "legendFormat": "Cost Ratio",
                    "refId": "A"
                },
                {
                    "expr": "router_expected_vs_actual_latency{tenant_id=\"$tenant_id\"}",
                    "legendFormat": "Latency Ratio",
                    "refId": "B"
                }
            ],
            "yAxes": [
                {
                    "label": "Ratio",
                    "min": 0,
                    "max": 2
                }
            ]
        }
    
    def _get_next_panel_id(self) -> int:
        """Get next panel ID."""
        panel_id = self.panel_id_counter
        self.panel_id_counter += 1
        return panel_id
    
    def save_dashboard_json(self, dashboard: Dict[str, Any], filepath: str) -> None:
        """Save dashboard as JSON file."""
        try:
            with open(filepath, 'w') as f:
                json.dump(dashboard, f, indent=2)
            logger.info("Dashboard saved", filepath=filepath)
        except Exception as e:
            logger.error("Failed to save dashboard", error=str(e), filepath=filepath)