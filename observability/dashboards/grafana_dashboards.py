"""Grafana dashboard definitions for AIaaS platform."""

from typing import Dict, Any, List


def get_main_dashboard() -> Dict[str, Any]:
    """Get main Grafana dashboard for AIaaS platform."""
    return {
        "dashboard": {
            "id": None,
            "title": "AIaaS Platform - Main Dashboard",
            "tags": ["aiaas", "platform", "main"],
            "style": "dark",
            "timezone": "browser",
            "refresh": "30s",
            "time": {
                "from": "now-1h",
                "to": "now"
            },
            "panels": [
                {
                    "id": 1,
                    "title": "Request Rate",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "sum(rate(request_total[5m])) by (service)",
                            "legendFormat": "{{service}}"
                        }
                    ],
                    "yAxes": [
                        {
                            "label": "Requests/sec",
                            "min": 0
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}
                },
                {
                    "id": 2,
                    "title": "Response Time",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "histogram_quantile(0.95, sum(rate(request_duration_seconds_bucket[5m])) by (le, service))",
                            "legendFormat": "{{service}} p95"
                        },
                        {
                            "expr": "histogram_quantile(0.50, sum(rate(request_duration_seconds_bucket[5m])) by (le, service))",
                            "legendFormat": "{{service}} p50"
                        }
                    ],
                    "yAxes": [
                        {
                            "label": "Seconds",
                            "min": 0
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0}
                },
                {
                    "id": 3,
                    "title": "Error Rate",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "sum(rate(errors_total[5m])) by (service)",
                            "legendFormat": "{{service}}"
                        }
                    ],
                    "yAxes": [
                        {
                            "label": "Errors/sec",
                            "min": 0
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8}
                },
                {
                    "id": 4,
                    "title": "Active Connections",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "active_connections",
                            "legendFormat": "{{service}}"
                        }
                    ],
                    "yAxes": [
                        {
                            "label": "Connections",
                            "min": 0
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8}
                }
            ]
        }
    }


def get_agent_dashboard() -> Dict[str, Any]:
    """Get agent-specific dashboard."""
    return {
        "dashboard": {
            "id": None,
            "title": "AIaaS Platform - Agent Dashboard",
            "tags": ["aiaas", "agent", "workflow"],
            "style": "dark",
            "timezone": "browser",
            "refresh": "30s",
            "time": {
                "from": "now-1h",
                "to": "now"
            },
            "panels": [
                {
                    "id": 1,
                    "title": "Agent Run Rate",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "sum(rate(agent_run_total[5m])) by (workflow, status)",
                            "legendFormat": "{{workflow}} - {{status}}"
                        }
                    ],
                    "yAxes": [
                        {
                            "label": "Runs/sec",
                            "min": 0
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}
                },
                {
                    "id": 2,
                    "title": "Agent Run Duration",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "histogram_quantile(0.95, sum(rate(agent_run_duration_seconds_bucket[5m])) by (le, workflow))",
                            "legendFormat": "{{workflow}} p95"
                        },
                        {
                            "expr": "histogram_quantile(0.50, sum(rate(agent_run_duration_seconds_bucket[5m])) by (le, workflow))",
                            "legendFormat": "{{workflow}} p50"
                        }
                    ],
                    "yAxes": [
                        {
                            "label": "Seconds",
                            "min": 0
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0}
                },
                {
                    "id": 3,
                    "title": "Token Usage",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "sum(rate(agent_run_tokens_total[5m])) by (type)",
                            "legendFormat": "{{type}} tokens"
                        }
                    ],
                    "yAxes": [
                        {
                            "label": "Tokens/sec",
                            "min": 0
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8}
                },
                {
                    "id": 4,
                    "title": "Cost per Run",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "sum(rate(agent_run_cost_usd_total[5m])) by (workflow)",
                            "legendFormat": "{{workflow}}"
                        }
                    ],
                    "yAxes": [
                        {
                            "label": "USD/sec",
                            "min": 0
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8}
                }
            ]
        }
    }


def get_router_dashboard() -> Dict[str, Any]:
    """Get router-specific dashboard."""
    return {
        "dashboard": {
            "id": None,
            "title": "AIaaS Platform - Router Dashboard",
            "tags": ["aiaas", "router", "routing"],
            "style": "dark",
            "timezone": "browser",
            "refresh": "30s",
            "time": {
                "from": "now-1h",
                "to": "now"
            },
            "panels": [
                {
                    "id": 1,
                    "title": "Router Decision Rate",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "sum(rate(router_decisions_total[5m])) by (tier)",
                            "legendFormat": "{{tier}}"
                        }
                    ],
                    "yAxes": [
                        {
                            "label": "Decisions/sec",
                            "min": 0
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}
                },
                {
                    "id": 2,
                    "title": "Router Decision Duration",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "histogram_quantile(0.95, sum(rate(router_decision_duration_seconds_bucket[5m])) by (le))",
                            "legendFormat": "p95"
                        },
                        {
                            "expr": "histogram_quantile(0.50, sum(rate(router_decision_duration_seconds_bucket[5m])) by (le))",
                            "legendFormat": "p50"
                        }
                    ],
                    "yAxes": [
                        {
                            "label": "Seconds",
                            "min": 0
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0}
                },
                {
                    "id": 3,
                    "title": "Tier Distribution",
                    "type": "piechart",
                    "targets": [
                        {
                            "expr": "sum(router_decisions_total) by (tier)",
                            "legendFormat": "{{tier}}"
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8}
                },
                {
                    "id": 4,
                    "title": "Misroute Rate",
                    "type": "singlestat",
                    "targets": [
                        {
                            "expr": "avg(router_misroute_rate)",
                            "legendFormat": "Misroute Rate"
                        }
                    ],
                    "format": "percent",
                    "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8}
                }
            ]
        }
    }


def get_tenant_dashboard() -> Dict[str, Any]:
    """Get tenant-specific dashboard."""
    return {
        "dashboard": {
            "id": None,
            "title": "AIaaS Platform - Tenant Dashboard",
            "tags": ["aiaas", "tenant", "multi-tenant"],
            "style": "dark",
            "timezone": "browser",
            "refresh": "30s",
            "time": {
                "from": "now-1h",
                "to": "now"
            },
            "templating": {
                "list": [
                    {
                        "name": "tenant_id",
                        "type": "query",
                        "query": "label_values(agent_run_total, tenant_id)",
                        "refresh": 1,
                        "includeAll": True,
                        "multi": True
                    }
                ]
            },
            "panels": [
                {
                    "id": 1,
                    "title": "Tenant Request Rate",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "sum(rate(request_total[5m])) by (tenant_id)",
                            "legendFormat": "{{tenant_id}}"
                        }
                    ],
                    "yAxes": [
                        {
                            "label": "Requests/sec",
                            "min": 0
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}
                },
                {
                    "id": 2,
                    "title": "Tenant Token Usage",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "sum(rate(usage_tokens_total[5m])) by (tenant_id, type)",
                            "legendFormat": "{{tenant_id}} - {{type}}"
                        }
                    ],
                    "yAxes": [
                        {
                            "label": "Tokens/sec",
                            "min": 0
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0}
                },
                {
                    "id": 3,
                    "title": "Tenant Cost",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "sum(rate(usage_cost_usd_total[5m])) by (tenant_id)",
                            "legendFormat": "{{tenant_id}}"
                        }
                    ],
                    "yAxes": [
                        {
                            "label": "USD/sec",
                            "min": 0
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8}
                },
                {
                    "id": 4,
                    "title": "WebSocket Connections",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "websocket_connections_active",
                            "legendFormat": "{{tenant_id}}"
                        }
                    ],
                    "yAxes": [
                        {
                            "label": "Connections",
                            "min": 0
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8}
                }
            ]
        }
    }


def get_sla_dashboard() -> Dict[str, Any]:
    """Get SLA monitoring dashboard."""
    return {
        "dashboard": {
            "id": None,
            "title": "AIaaS Platform - SLA Dashboard",
            "tags": ["aiaas", "sla", "slo"],
            "style": "dark",
            "timezone": "browser",
            "refresh": "30s",
            "time": {
                "from": "now-24h",
                "to": "now"
            },
            "panels": [
                {
                    "id": 1,
                    "title": "Availability SLO",
                    "type": "singlestat",
                    "targets": [
                        {
                            "expr": "avg_over_time(up[1h]) * 100",
                            "legendFormat": "Availability"
                        }
                    ],
                    "format": "percent",
                    "thresholds": "95,99",
                    "gridPos": {"h": 8, "w": 6, "x": 0, "y": 0}
                },
                {
                    "id": 2,
                    "title": "Response Time SLO",
                    "type": "singlestat",
                    "targets": [
                        {
                            "expr": "histogram_quantile(0.95, sum(rate(request_duration_seconds_bucket[1h])) by (le))",
                            "legendFormat": "P95 Response Time"
                        }
                    ],
                    "format": "s",
                    "thresholds": "0.5,1.0",
                    "gridPos": {"h": 8, "w": 6, "x": 6, "y": 0}
                },
                {
                    "id": 3,
                    "title": "Error Rate SLO",
                    "type": "singlestat",
                    "targets": [
                        {
                            "expr": "sum(rate(errors_total[1h])) / sum(rate(request_total[1h])) * 100",
                            "legendFormat": "Error Rate"
                        }
                    ],
                    "format": "percent",
                    "thresholds": "1,5",
                    "gridPos": {"h": 8, "w": 6, "x": 12, "y": 0}
                },
                {
                    "id": 4,
                    "title": "SLA Compliance",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "avg_over_time(up[5m]) * 100",
                            "legendFormat": "Availability"
                        },
                        {
                            "expr": "histogram_quantile(0.95, sum(rate(request_duration_seconds_bucket[5m])) by (le)) * 1000",
                            "legendFormat": "P95 Response Time (ms)"
                        }
                    ],
                    "yAxes": [
                        {
                            "label": "Percentage / Milliseconds",
                            "min": 0
                        }
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8}
                }
            ]
        }
    }


def get_all_dashboards() -> List[Dict[str, Any]]:
    """Get all dashboard definitions."""
    return [
        get_main_dashboard(),
        get_agent_dashboard(),
        get_router_dashboard(),
        get_tenant_dashboard(),
        get_sla_dashboard()
    ]
