"""Grafana dashboard generator for analytics."""

import json
from typing import Dict, List, Any, Optional


class GrafanaDashboardGenerator:
    """Generator for Grafana dashboard configurations."""
    
    def __init__(self):
        self.dashboard_id = 1
        self.panel_id = 1
    
    def generate_analytics_dashboard(self) -> Dict[str, Any]:
        """Generate comprehensive analytics dashboard."""
        return {
            "dashboard": {
                "id": None,
                "title": "AIaaS Platform Analytics",
                "tags": ["aiaas", "analytics", "monitoring"],
                "style": "dark",
                "timezone": "browser",
                "panels": [
                    self._create_success_rate_panel(),
                    self._create_latency_panel(),
                    self._create_cost_panel(),
                    self._create_router_metrics_panel(),
                    self._create_tenant_kpis_panel(),
                    self._create_usage_metrics_panel(),
                    self._create_error_rates_panel(),
                    self._create_throughput_panel()
                ],
                "time": {
                    "from": "now-24h",
                    "to": "now"
                },
                "refresh": "30s",
                "schemaVersion": 27,
                "version": 1,
                "links": []
            }
        }
    
    def _create_success_rate_panel(self) -> Dict[str, Any]:
        """Create success rate panel."""
        return {
            "id": self._next_panel_id(),
            "title": "Success Rate",
            "type": "stat",
            "gridPos": {"h": 8, "w": 6, "x": 0, "y": 0},
            "targets": [
                {
                    "expr": "agent_run_success_rate{tenant_id=\"$tenant\"}",
                    "legendFormat": "Success Rate %",
                    "refId": "A"
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "mappings": [],
                    "thresholds": {
                        "steps": [
                            {"color": "red", "value": 0},
                            {"color": "yellow", "value": 80},
                            {"color": "green", "value": 95}
                        ]
                    },
                    "unit": "percent"
                }
            },
            "options": {
                "colorMode": "value",
                "graphMode": "area",
                "justifyMode": "auto",
                "orientation": "auto"
            }
        }
    
    def _create_latency_panel(self) -> Dict[str, Any]:
        """Create latency panel."""
        return {
            "id": self._next_panel_id(),
            "title": "Response Latency",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 12, "x": 6, "y": 0},
            "targets": [
                {
                    "expr": "histogram_quantile(0.50, agent_run_duration_seconds{tenant_id=\"$tenant\"})",
                    "legendFormat": "P50",
                    "refId": "A"
                },
                {
                    "expr": "histogram_quantile(0.95, agent_run_duration_seconds{tenant_id=\"$tenant\"})",
                    "legendFormat": "P95",
                    "refId": "B"
                },
                {
                    "expr": "histogram_quantile(0.99, agent_run_duration_seconds{tenant_id=\"$tenant\"})",
                    "legendFormat": "P99",
                    "refId": "C"
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "palette-classic"},
                    "custom": {
                        "axisLabel": "",
                        "axisPlacement": "auto",
                        "barAlignment": 0,
                        "drawStyle": "line",
                        "fillOpacity": 10,
                        "gradientMode": "none",
                        "hideFrom": {
                            "legend": False,
                            "tooltip": False,
                            "vis": False
                        },
                        "lineInterpolation": "linear",
                        "lineWidth": 1,
                        "pointSize": 5,
                        "scaleDistribution": {"type": "linear"},
                        "showPoints": "never",
                        "spanNulls": False,
                        "stacking": {"group": "A", "mode": "none"},
                        "thresholdsStyle": {"mode": "off"}
                    },
                    "mappings": [],
                    "thresholds": {
                        "steps": [
                            {"color": "green", "value": 0},
                            {"color": "red", "value": 5}
                        ]
                    },
                    "unit": "s"
                }
            }
        }
    
    def _create_cost_panel(self) -> Dict[str, Any]:
        """Create cost panel."""
        return {
            "id": self._next_panel_id(),
            "title": "Cost Analysis",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 6, "x": 18, "y": 0},
            "targets": [
                {
                    "expr": "sum(rate(agent_run_cost_usd_total{tenant_id=\"$tenant\"}[5m]))",
                    "legendFormat": "Cost per minute",
                    "refId": "A"
                },
                {
                    "expr": "sum(agent_run_cost_usd_total{tenant_id=\"$tenant\"})",
                    "legendFormat": "Total cost",
                    "refId": "B"
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "palette-classic"},
                    "custom": {
                        "axisLabel": "",
                        "axisPlacement": "auto",
                        "barAlignment": 0,
                        "drawStyle": "line",
                        "fillOpacity": 10,
                        "gradientMode": "none",
                        "hideFrom": {
                            "legend": False,
                            "tooltip": False,
                            "vis": False
                        },
                        "lineInterpolation": "linear",
                        "lineWidth": 1,
                        "pointSize": 5,
                        "scaleDistribution": {"type": "linear"},
                        "showPoints": "never",
                        "spanNulls": False,
                        "stacking": {"group": "A", "mode": "none"},
                        "thresholdsStyle": {"mode": "off"}
                    },
                    "mappings": [],
                    "thresholds": {"steps": []},
                    "unit": "currencyUSD"
                }
            }
        }
    
    def _create_router_metrics_panel(self) -> Dict[str, Any]:
        """Create router metrics panel."""
        return {
            "id": self._next_panel_id(),
            "title": "Router Performance",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
            "targets": [
                {
                    "expr": "histogram_quantile(0.50, router_decision_duration_seconds{tenant_id=\"$tenant\"})",
                    "legendFormat": "Decision P50",
                    "refId": "A"
                },
                {
                    "expr": "histogram_quantile(0.95, router_decision_duration_seconds{tenant_id=\"$tenant\"})",
                    "legendFormat": "Decision P95",
                    "refId": "B"
                },
                {
                    "expr": "rate(router_misroute_total{tenant_id=\"$tenant\"}[5m])",
                    "legendFormat": "Misroute rate",
                    "refId": "C"
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "palette-classic"},
                    "custom": {
                        "axisLabel": "",
                        "axisPlacement": "auto",
                        "barAlignment": 0,
                        "drawStyle": "line",
                        "fillOpacity": 10,
                        "gradientMode": "none",
                        "hideFrom": {
                            "legend": False,
                            "tooltip": False,
                            "vis": False
                        },
                        "lineInterpolation": "linear",
                        "lineWidth": 1,
                        "pointSize": 5,
                        "scaleDistribution": {"type": "linear"},
                        "showPoints": "never",
                        "spanNulls": False,
                        "stacking": {"group": "A", "mode": "none"},
                        "thresholdsStyle": {"mode": "off"}
                    },
                    "mappings": [],
                    "thresholds": {"steps": []},
                    "unit": "s"
                }
            }
        }
    
    def _create_tenant_kpis_panel(self) -> Dict[str, Any]:
        """Create tenant KPIs panel."""
        return {
            "id": self._next_panel_id(),
            "title": "Tenant KPIs",
            "type": "table",
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
            "targets": [
                {
                    "expr": "tenant_efficiency_score{tenant_id=\"$tenant\"}",
                    "legendFormat": "Efficiency Score",
                    "refId": "A"
                },
                {
                    "expr": "tenant_success_rate{tenant_id=\"$tenant\"}",
                    "legendFormat": "Success Rate",
                    "refId": "B"
                },
                {
                    "expr": "tenant_avg_latency{tenant_id=\"$tenant\"}",
                    "legendFormat": "Avg Latency",
                    "refId": "C"
                },
                {
                    "expr": "tenant_total_cost{tenant_id=\"$tenant\"}",
                    "legendFormat": "Total Cost",
                    "refId": "D"
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "custom": {
                        "align": "auto",
                        "displayMode": "auto",
                        "filterable": True
                    },
                    "mappings": [],
                    "thresholds": {"steps": []}
                }
            }
        }
    
    def _create_usage_metrics_panel(self) -> Dict[str, Any]:
        """Create usage metrics panel."""
        return {
            "id": self._next_panel_id(),
            "title": "Usage Metrics",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 16},
            "targets": [
                {
                    "expr": "sum(rate(usage_tokens_in_total{tenant_id=\"$tenant\"}[5m]))",
                    "legendFormat": "Tokens In/min",
                    "refId": "A"
                },
                {
                    "expr": "sum(rate(usage_tokens_out_total{tenant_id=\"$tenant\"}[5m]))",
                    "legendFormat": "Tokens Out/min",
                    "refId": "B"
                },
                {
                    "expr": "sum(rate(usage_tool_calls_total{tenant_id=\"$tenant\"}[5m]))",
                    "legendFormat": "Tool Calls/min",
                    "refId": "C"
                },
                {
                    "expr": "sum(rate(usage_ws_minutes_total{tenant_id=\"$tenant\"}[5m]))",
                    "legendFormat": "WS Minutes/min",
                    "refId": "D"
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "palette-classic"},
                    "custom": {
                        "axisLabel": "",
                        "axisPlacement": "auto",
                        "barAlignment": 0,
                        "drawStyle": "line",
                        "fillOpacity": 10,
                        "gradientMode": "none",
                        "hideFrom": {
                            "legend": False,
                            "tooltip": False,
                            "vis": False
                        },
                        "lineInterpolation": "linear",
                        "lineWidth": 1,
                        "pointSize": 5,
                        "scaleDistribution": {"type": "linear"},
                        "showPoints": "never",
                        "spanNulls": False,
                        "stacking": {"group": "A", "mode": "none"},
                        "thresholdsStyle": {"mode": "off"}
                    },
                    "mappings": [],
                    "thresholds": {"steps": []},
                    "unit": "short"
                }
            }
        }
    
    def _create_error_rates_panel(self) -> Dict[str, Any]:
        """Create error rates panel."""
        return {
            "id": self._next_panel_id(),
            "title": "Error Rates",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 16},
            "targets": [
                {
                    "expr": "sum(rate(agent_run_errors_total{tenant_id=\"$tenant\"}[5m])) by (error_type)",
                    "legendFormat": "{{error_type}}",
                    "refId": "A"
                },
                {
                    "expr": "sum(rate(tool_errors_total{tenant_id=\"$tenant\"}[5m])) by (tool_id)",
                    "legendFormat": "Tool {{tool_id}}",
                    "refId": "B"
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "palette-classic"},
                    "custom": {
                        "axisLabel": "",
                        "axisPlacement": "auto",
                        "barAlignment": 0,
                        "drawStyle": "line",
                        "fillOpacity": 10,
                        "gradientMode": "none",
                        "hideFrom": {
                            "legend": False,
                            "tooltip": False,
                            "vis": False
                        },
                        "lineInterpolation": "linear",
                        "lineWidth": 1,
                        "pointSize": 5,
                        "scaleDistribution": {"type": "linear"},
                        "showPoints": "never",
                        "spanNulls": False,
                        "stacking": {"group": "A", "mode": "none"},
                        "thresholdsStyle": {"mode": "off"}
                    },
                    "mappings": [],
                    "thresholds": {"steps": []},
                    "unit": "short"
                }
            }
        }
    
    def _create_throughput_panel(self) -> Dict[str, Any]:
        """Create throughput panel."""
        return {
            "id": self._next_panel_id(),
            "title": "Throughput",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 24, "x": 0, "y": 24},
            "targets": [
                {
                    "expr": "sum(rate(agent_runs_total{tenant_id=\"$tenant\"}[5m]))",
                    "legendFormat": "Agent Runs/min",
                    "refId": "A"
                },
                {
                    "expr": "sum(rate(router_decisions_total{tenant_id=\"$tenant\"}[5m]))",
                    "legendFormat": "Router Decisions/min",
                    "refId": "B"
                },
                {
                    "expr": "sum(rate(websocket_connections_total{tenant_id=\"$tenant\"}[5m]))",
                    "legendFormat": "WS Connections/min",
                    "refId": "C"
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "palette-classic"},
                    "custom": {
                        "axisLabel": "",
                        "axisPlacement": "auto",
                        "barAlignment": 0,
                        "drawStyle": "line",
                        "fillOpacity": 10,
                        "gradientMode": "none",
                        "hideFrom": {
                            "legend": False,
                            "tooltip": False,
                            "vis": False
                        },
                        "lineInterpolation": "linear",
                        "lineWidth": 1,
                        "pointSize": 5,
                        "scaleDistribution": {"type": "linear"},
                        "showPoints": "never",
                        "spanNulls": False,
                        "stacking": {"group": "A", "mode": "none"},
                        "thresholdsStyle": {"mode": "off"}
                    },
                    "mappings": [],
                    "thresholds": {"steps": []},
                    "unit": "short"
                }
            }
        }
    
    def _next_panel_id(self) -> int:
        """Get next panel ID."""
        current_id = self.panel_id
        self.panel_id += 1
        return current_id
    
    def generate_tenant_dashboard(self, tenant_id: str) -> Dict[str, Any]:
        """Generate tenant-specific dashboard."""
        dashboard = self.generate_analytics_dashboard()
        dashboard["dashboard"]["title"] = f"Analytics - Tenant {tenant_id}"
        dashboard["dashboard"]["templating"] = {
            "list": [
                {
                    "name": "tenant",
                    "type": "custom",
                    "query": tenant_id,
                    "current": {"text": tenant_id, "value": tenant_id}
                }
            ]
        }
        return dashboard
    
    def generate_system_dashboard(self) -> Dict[str, Any]:
        """Generate system-wide dashboard."""
        return {
            "dashboard": {
                "id": None,
                "title": "AIaaS Platform - System Overview",
                "tags": ["aiaas", "system", "monitoring"],
                "style": "dark",
                "timezone": "browser",
                "panels": [
                    {
                        "id": 1,
                        "title": "System Health",
                        "type": "stat",
                        "gridPos": {"h": 8, "w": 6, "x": 0, "y": 0},
                        "targets": [
                            {
                                "expr": "up{job=\"aiaas-api-gateway\"}",
                                "legendFormat": "API Gateway",
                                "refId": "A"
                            }
                        ]
                    }
                ],
                "time": {
                    "from": "now-1h",
                    "to": "now"
                },
                "refresh": "30s",
                "schemaVersion": 27,
                "version": 1
            }
        }