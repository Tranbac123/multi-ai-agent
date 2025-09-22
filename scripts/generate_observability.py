#!/usr/bin/env python3
"""
Generate comprehensive observability configurations for all services.
Creates dashboards, alerts, SLOs, and runbooks with production-ready templates.
"""

import os
import json
import yaml
from pathlib import Path

# Service configuration with their specific details
SERVICES = {
    "api-gateway": {
        "port": 8000,
        "type": "http",
        "purpose": "Main entry point with authentication, rate limiting, and routing",
        "slo_target": "99.9%",
        "latency_target": "100ms"
    },
    "analytics-service": {
        "port": 8001,
        "type": "http", 
        "purpose": "Real-time analytics and reporting with time-series data",
        "slo_target": "99.5%",
        "latency_target": "200ms"
    },
    "orchestrator": {
        "port": 8002,
        "type": "grpc",
        "purpose": "LangGraph workflow execution with resilient tool adapters",
        "slo_target": "99.9%",
        "latency_target": "500ms"
    },
    "router-service": {
        "port": 8003,
        "type": "grpc",
        "purpose": "Intelligent request routing with load balancing and failover",
        "slo_target": "99.95%",
        "latency_target": "50ms"
    },
    "realtime": {
        "port": 8004,
        "type": "http",
        "purpose": "WebSocket connections with backpressure management",
        "slo_target": "99.5%",
        "latency_target": "100ms"
    },
    "ingestion": {
        "port": 8005,
        "type": "http",
        "purpose": "Data ingestion pipeline with batch and stream processing",
        "slo_target": "99.5%",
        "latency_target": "300ms"
    },
    "billing-service": {
        "port": 8006,
        "type": "http",
        "purpose": "Usage tracking and billing with cost optimization",
        "slo_target": "99.9%",
        "latency_target": "150ms"
    },
    "tenant-service": {
        "port": 8007,
        "type": "http",
        "purpose": "Multi-tenant management with regional data residency",
        "slo_target": "99.9%",
        "latency_target": "100ms"
    },
    "chat-adapters": {
        "port": 8008,
        "type": "http",
        "purpose": "Multi-channel chat integration (Facebook, Zalo, TikTok)",
        "slo_target": "99.5%",
        "latency_target": "200ms"
    },
    "tool-service": {
        "port": 8009,
        "type": "grpc",
        "purpose": "External tool integration with circuit breakers",
        "slo_target": "99.5%",
        "latency_target": "1000ms"
    },
    "eval-service": {
        "port": 8010,
        "type": "http",
        "purpose": "AI model evaluation and performance testing",
        "slo_target": "99.0%",
        "latency_target": "2000ms"
    },
    "capacity-monitor": {
        "port": 8011,
        "type": "http",
        "purpose": "Resource monitoring and auto-scaling decisions",
        "slo_target": "99.5%",
        "latency_target": "100ms"
    },
    "admin-portal": {
        "port": 8012,
        "type": "http",
        "purpose": "Administrative dashboard and tenant management",
        "slo_target": "99.0%",
        "latency_target": "500ms"
    },
    "web-frontend": {
        "port": 3000,
        "type": "frontend",
        "purpose": "React-based user interface with real-time features",
        "slo_target": "99.5%",
        "latency_target": "200ms"
    }
}

def generate_dashboard_json(service_name, service_config):
    """Generate Grafana dashboard JSON for a service."""
    dashboard = {
        "dashboard": {
            "id": None,
            "title": f"{service_name.replace('-', ' ').title()} Service Dashboard",
            "tags": ["multi-ai-agent", service_name, service_config["type"]],
            "timezone": "browser",
            "panels": [
                {
                    "id": 1,
                    "title": "Request Rate",
                    "type": "stat",
                    "targets": [
                        {
                            "expr": f'rate(http_requests_total{{service="{service_name}"}}[5m])',
                            "legendFormat": "Requests/sec",
                            "refId": "A"
                        }
                    ],
                    "fieldConfig": {
                        "defaults": {
                            "unit": "reqps",
                            "thresholds": {
                                "steps": [
                                    {"color": "green", "value": None},
                                    {"color": "yellow", "value": 100},
                                    {"color": "red", "value": 1000}
                                ]
                            }
                        }
                    },
                    "gridPos": {"h": 8, "w": 8, "x": 0, "y": 0}
                },
                {
                    "id": 2,
                    "title": "Latency P95",
                    "type": "stat",
                    "targets": [
                        {
                            "expr": f'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m]))',
                            "legendFormat": "P95 Latency",
                            "refId": "B"
                        }
                    ],
                    "fieldConfig": {
                        "defaults": {
                            "unit": "s",
                            "thresholds": {
                                "steps": [
                                    {"color": "green", "value": None},
                                    {"color": "yellow", "value": 0.1},
                                    {"color": "red", "value": 0.5}
                                ]
                            }
                        }
                    },
                    "gridPos": {"h": 8, "w": 8, "x": 8, "y": 0}
                },
                {
                    "id": 3,
                    "title": "Error Rate",
                    "type": "stat",
                    "targets": [
                        {
                            "expr": f'rate(http_requests_total{{service="{service_name}",status=~"5.."}}[5m]) / rate(http_requests_total{{service="{service_name}"}}[5m]) * 100',
                            "legendFormat": "Error Rate %",
                            "refId": "C"
                        }
                    ],
                    "fieldConfig": {
                        "defaults": {
                            "unit": "percent",
                            "thresholds": {
                                "steps": [
                                    {"color": "green", "value": None},
                                    {"color": "yellow", "value": 1},
                                    {"color": "red", "value": 5}
                                ]
                            }
                        }
                    },
                    "gridPos": {"h": 8, "w": 8, "x": 16, "y": 0}
                },
                {
                    "id": 4,
                    "title": "Request Rate Timeline",
                    "type": "timeseries",
                    "targets": [
                        {
                            "expr": f'rate(http_requests_total{{service="{service_name}"}}[5m])',
                            "legendFormat": "{{method}} {{endpoint}}",
                            "refId": "D"
                        }
                    ],
                    "fieldConfig": {
                        "defaults": {
                            "unit": "reqps"
                        }
                    },
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8}
                },
                {
                    "id": 5,
                    "title": "Latency Percentiles",
                    "type": "timeseries",
                    "targets": [
                        {
                            "expr": f'histogram_quantile(0.50, rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m]))',
                            "legendFormat": "P50",
                            "refId": "E1"
                        },
                        {
                            "expr": f'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m]))',
                            "legendFormat": "P95",
                            "refId": "E2"
                        },
                        {
                            "expr": f'histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m]))',
                            "legendFormat": "P99",
                            "refId": "E3"
                        }
                    ],
                    "fieldConfig": {
                        "defaults": {
                            "unit": "s"
                        }
                    },
                    "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8}
                },
                {
                    "id": 6,
                    "title": "Resource Usage",
                    "type": "timeseries",
                    "targets": [
                        {
                            "expr": f'rate(container_cpu_usage_seconds_total{{container="{service_name}"}}[5m]) * 100',
                            "legendFormat": "CPU %",
                            "refId": "F1"
                        },
                        {
                            "expr": f'container_memory_usage_bytes{{container="{service_name}"}} / container_spec_memory_limit_bytes{{container="{service_name}"}} * 100',
                            "legendFormat": "Memory %",
                            "refId": "F2"
                        }
                    ],
                    "fieldConfig": {
                        "defaults": {
                            "unit": "percent"
                        }
                    },
                    "gridPos": {"h": 8, "w": 24, "x": 0, "y": 16}
                }
            ],
            "time": {
                "from": "now-1h",
                "to": "now"
            },
            "refresh": "30s"
        }
    }
    return dashboard

def generate_alerts_yaml(service_name, service_config):
    """Generate AlertManager alerts for a service."""
    alerts = {
        "groups": [
            {
                "name": f"{service_name}-alerts",
                "rules": [
                    {
                        "alert": f"{service_name.replace('-', '_').title()}HighErrorRate",
                        "expr": f'rate(http_requests_total{{service="{service_name}",status=~"5.."}}[5m]) / rate(http_requests_total{{service="{service_name}"}}[5m]) * 100 > 5',
                        "for": "2m",
                        "labels": {
                            "severity": "critical",
                            "service": service_name,
                            "team": "platform"
                        },
                        "annotations": {
                            "summary": f"{service_name} has high error rate",
                            "description": f"Error rate for {service_name} is {{ $value }}% which is above the 5% threshold.",
                            "runbook_url": f"https://runbooks.company.com/{service_name}#high-error-rate"
                        }
                    },
                    {
                        "alert": f"{service_name.replace('-', '_').title()}HighLatency",
                        "expr": f'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m])) > {float(service_config["latency_target"].rstrip("ms")) / 1000}',
                        "for": "5m",
                        "labels": {
                            "severity": "warning",
                            "service": service_name,
                            "team": "platform"
                        },
                        "annotations": {
                            "summary": f"{service_name} has high latency",
                            "description": f"P95 latency for {service_name} is {{ $value }}s which is above the {service_config['latency_target']} threshold.",
                            "runbook_url": f"https://runbooks.company.com/{service_name}#high-latency"
                        }
                    },
                    {
                        "alert": f"{service_name.replace('-', '_').title()}ServiceDown",
                        "expr": f'up{{service="{service_name}"}} == 0',
                        "for": "1m",
                        "labels": {
                            "severity": "critical",
                            "service": service_name,
                            "team": "platform"
                        },
                        "annotations": {
                            "summary": f"{service_name} is down",
                            "description": f"{service_name} has been down for more than 1 minute.",
                            "runbook_url": f"https://runbooks.company.com/{service_name}#service-down"
                        }
                    },
                    {
                        "alert": f"{service_name.replace('-', '_').title()}HighMemoryUsage",
                        "expr": f'container_memory_usage_bytes{{container="{service_name}"}} / container_spec_memory_limit_bytes{{container="{service_name}"}} * 100 > 80',
                        "for": "5m",
                        "labels": {
                            "severity": "warning",
                            "service": service_name,
                            "team": "platform"
                        },
                        "annotations": {
                            "summary": f"{service_name} has high memory usage",
                            "description": f"Memory usage for {service_name} is {{ $value }}% which is above 80%.",
                            "runbook_url": f"https://runbooks.company.com/{service_name}#high-memory"
                        }
                    }
                ]
            }
        ]
    }
    return alerts

def generate_slo_md(service_name, service_config):
    """Generate SLO.md with objectives and SLI queries."""
    content = f"""# {service_name.replace('-', ' ').title()} Service Level Objectives (SLO)

## Overview
This document defines the Service Level Objectives (SLOs) for the {service_name} service.

**Service Purpose**: {service_config['purpose']}

## SLO Definitions

### 1. Availability SLO
- **Objective**: {service_config['slo_target']} availability over a 30-day rolling window
- **SLI**: Percentage of successful requests (non-5xx responses)
- **Error Budget**: {100 - float(service_config['slo_target'].rstrip('%')):.1f}% ({100 - float(service_config['slo_target'].rstrip('%')):.1f} hours downtime per month)

**PromQL Query**:
```promql
# Success Rate (SLI)
(
  sum(rate(http_requests_total{{service="{service_name}",status!~"5.."}}[30d])) /
  sum(rate(http_requests_total{{service="{service_name}"}}[30d]))
) * 100

# Error Budget Burn Rate (1h window)
(
  1 - (
    sum(rate(http_requests_total{{service="{service_name}",status!~"5.."}}[1h])) /
    sum(rate(http_requests_total{{service="{service_name}"}}[1h]))
  )
) / (1 - {float(service_config['slo_target'].rstrip('%')) / 100})
```

### 2. Latency SLO
- **Objective**: 95% of requests complete within {service_config['latency_target']}
- **SLI**: P95 latency of successful requests

**PromQL Query**:
```promql
# P95 Latency (SLI)
histogram_quantile(0.95, 
  rate(http_request_duration_seconds_bucket{{service="{service_name}",status!~"5.."}}[5m])
)

# Latency SLO Compliance (percentage of requests under threshold)
(
  sum(rate(http_request_duration_seconds_bucket{{service="{service_name}",status!~"5..",le="{float(service_config['latency_target'].rstrip('ms')) / 1000}"}}[5m])) /
  sum(rate(http_request_duration_seconds_count{{service="{service_name}",status!~"5.."}}[5m]))
) * 100
```

### 3. Error Rate SLO
- **Objective**: Less than 1% error rate over a 1-hour rolling window
- **SLI**: Percentage of requests returning 5xx status codes

**PromQL Query**:
```promql
# Error Rate (SLI)
(
  sum(rate(http_requests_total{{service="{service_name}",status=~"5.."}}[1h])) /
  sum(rate(http_requests_total{{service="{service_name}"}}[1h]))
) * 100
```

## SLO Monitoring and Alerting

### Error Budget Alerts
- **Fast Burn**: Error budget consumption > 2% in 1 hour
- **Slow Burn**: Error budget consumption > 5% in 6 hours

### SLO Dashboard
- **Grafana Dashboard**: `{service_name}-slo-dashboard`
- **Metrics**: Availability, Latency P95/P99, Error Rate, Error Budget Burn Rate

## SLO Review Process
- **Review Frequency**: Monthly
- **Stakeholders**: Platform Team, Service Owners, Product Team
- **Review Criteria**: 
  - SLO achievement vs. target
  - Error budget consumption
  - Alert noise vs. actionable incidents
  - Customer impact correlation

## Historical Performance
<!-- Update monthly with actual performance data -->
| Month | Availability | P95 Latency | Error Rate | SLO Met |
|-------|-------------|-------------|------------|---------|
| TBD   | TBD         | TBD         | TBD        | TBD     |

## Related Documents
- [Runbook](./{service_name}-runbook.md)
- [Service Architecture](../README.md)
- [Incident Response](https://docs.company.com/incident-response)
"""
    return content

def generate_runbook_md(service_name, service_config):
    """Generate runbook.md with oncall procedures."""
    content = f"""# {service_name.replace('-', ' ').title()} Service Runbook

## Service Overview
- **Service**: {service_name}
- **Purpose**: {service_config['purpose']}
- **Port**: {service_config['port']}
- **Type**: {service_config['type']}
- **SLO Target**: {service_config['slo_target']}

## Quick Links
- **Dashboard**: [Grafana Dashboard](https://grafana.company.com/d/{service_name})
- **Logs**: [Loki Logs](https://grafana.company.com/explore?query={{service="{service_name}"}})
- **Traces**: [Jaeger UI](https://jaeger.company.com/search?service={service_name})
- **Alerts**: [AlertManager](https://alertmanager.company.com/#/alerts?filter={{service="{service_name}"}})

## Common Issues and Solutions

### 🚨 High Error Rate (5xx errors > 5%)

**Symptoms:**
- Increase in 5xx status code responses
- Customer complaints about service unavailability
- Alert: `{service_name.replace('-', '_').title()}HighErrorRate`

**Investigation Steps:**
1. **Check Service Health**
   ```bash
   # Check if service is up
   kubectl get pods -l app={service_name} -n production
   
   # Check recent logs for errors
   kubectl logs -l app={service_name} -n production --tail=100 | grep ERROR
   ```

2. **Review Error Patterns**
   ```promql
   # Top error endpoints
   topk(10, sum by (endpoint) (rate(http_requests_total{{service="{service_name}",status=~"5.."}}[5m])))
   
   # Error breakdown by status code
   sum by (status) (rate(http_requests_total{{service="{service_name}",status=~"5.."}}[5m]))
   ```

3. **Check Dependencies**
   ```bash
   # Database connectivity
   kubectl exec -n production deployment/{service_name} -- ping database-host
   
   # External service health
   curl -H "Authorization: Bearer $TOKEN" https://external-api.com/health
   ```

**Resolution:**
- If database issues: Check connection pool, query performance
- If external API issues: Implement circuit breaker, check API limits
- If memory issues: Scale up pods or optimize memory usage
- If code issues: Deploy hotfix or rollback to previous version

### ⚡ High Latency (P95 > {service_config['latency_target']})

**Symptoms:**
- Slow response times
- Timeout errors from clients
- Alert: `{service_name.replace('-', '_').title()}HighLatency`

**Investigation Steps:**
1. **Identify Slow Endpoints**
   ```promql
   # Slowest endpoints (P95)
   topk(10, histogram_quantile(0.95, sum by (endpoint) (rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m]))))
   ```

2. **Check Resource Usage**
   ```promql
   # CPU usage
   rate(container_cpu_usage_seconds_total{{container="{service_name}"}}[5m]) * 100
   
   # Memory usage
   container_memory_usage_bytes{{container="{service_name}"}} / 1024/1024/1024
   ```

3. **Database Performance**
   ```sql
   -- Check slow queries (PostgreSQL)
   SELECT query, mean_time, calls 
   FROM pg_stat_statements 
   WHERE mean_time > 1000 
   ORDER BY mean_time DESC LIMIT 10;
   ```

**Resolution:**
- Scale horizontally: Increase replica count
- Optimize database queries: Add indexes, optimize joins
- Implement caching: Redis for frequently accessed data
- Review and optimize critical code paths

### 💥 Service Down (Service unavailable)

**Symptoms:**
- Service not responding to health checks
- 0 successful requests
- Alert: `{service_name.replace('-', '_').title()}ServiceDown`

**Investigation Steps:**
1. **Check Pod Status**
   ```bash
   kubectl describe pod -l app={service_name} -n production
   kubectl get events -n production --sort-by='.lastTimestamp' | grep {service_name}
   ```

2. **Review Startup Logs**
   ```bash
   kubectl logs -l app={service_name} -n production --previous
   ```

3. **Check Resource Limits**
   ```bash
   kubectl top pod -l app={service_name} -n production
   ```

**Resolution:**
- If pod crash: Check logs for errors, review resource limits
- If node issues: Check node health, consider pod rescheduling  
- If deployment issues: Rollback to previous working version
- If resource exhaustion: Scale up resources or optimize usage

### 🧠 High Memory Usage (> 80%)

**Symptoms:**
- Memory usage consistently high
- Potential OOM kills
- Alert: `{service_name.replace('-', '_').title()}HighMemoryUsage`

**Investigation Steps:**
1. **Memory Usage Breakdown**
   ```promql
   container_memory_usage_bytes{{container="{service_name}"}} / container_spec_memory_limit_bytes{{container="{service_name}"}} * 100
   ```

2. **Check for Memory Leaks**
   ```bash
   # Profile memory usage (if profiling enabled)
   curl http://{service_name}:6060/debug/pprof/heap
   ```

**Resolution:**
- Increase memory limits if justified by usage patterns
- Identify and fix memory leaks in application code
- Implement proper connection pooling and resource cleanup
- Consider horizontal scaling instead of vertical scaling

## Monitoring and Observability

### Key Metrics to Monitor
- **Request Rate**: `rate(http_requests_total{{service="{service_name}"}}[5m])`
- **Error Rate**: `rate(http_requests_total{{service="{service_name}",status=~"5.."}}[5m])`
- **Latency P95**: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m]))`
- **CPU Usage**: `rate(container_cpu_usage_seconds_total{{container="{service_name}"}}[5m]) * 100`
- **Memory Usage**: `container_memory_usage_bytes{{container="{service_name}"}}`

### Log Locations
- **Application Logs**: `kubectl logs -l app={service_name} -n production`
- **Access Logs**: Available in Grafana Loki with label `{{service="{service_name}"}}`
- **Error Logs**: Filter by level=ERROR in log aggregation

### Trace Locations
- **Jaeger UI**: Search by service name `{service_name}`
- **Trace sampling**: 1% of requests (configurable)
- **Key operations**: HTTP requests, database queries, external API calls

## Escalation

### On-Call Rotation
- **Primary**: Platform Team oncall
- **Secondary**: {service_name.replace('-', ' ').title()} Service Owner
- **Manager**: Platform Engineering Manager

### Escalation Triggers
- Multiple alerts firing simultaneously
- Customer-impacting outage > 15 minutes
- Data loss or corruption suspected
- Security incident suspected

### Emergency Contacts
- **Slack**: #platform-alerts, #incident-response
- **PagerDuty**: Platform Engineering team
- **Phone**: Emergency contact list in PagerDuty

## Deployment and Rollback

### Safe Deployment Practices
```bash
# Check current version
kubectl get deployment {service_name} -n production -o jsonpath='{{.spec.template.spec.containers[0].image}}'

# Deploy new version (canary)
kubectl set image deployment/{service_name} {service_name}=new-image:tag -n production

# Monitor deployment
kubectl rollout status deployment/{service_name} -n production

# Rollback if needed
kubectl rollout undo deployment/{service_name} -n production
```

### Health Check Verification
```bash
# Test health endpoint
curl -f http://{service_name}.production.svc.cluster.local:{service_config['port']}/healthz

# Verify metrics endpoint
curl http://{service_name}.production.svc.cluster.local:{service_config['port']}/metrics
```

## Maintenance

### Regular Maintenance Tasks
- **Weekly**: Review error trends and performance metrics
- **Monthly**: Update dependencies and security patches
- **Quarterly**: Load testing and capacity planning review

### Capacity Planning
- Monitor resource utilization trends
- Plan for traffic growth (20% monthly growth assumed)
- Review and update resource requests/limits

## Related Documentation
- [Service Level Objectives](./SLO.md)
- [API Documentation](../contracts/)
- [Deployment Guide](../deploy/)
- [Architecture Overview](../README.md)

---
*Last Updated: $(date)*
*Next Review: Monthly*
"""
    return content

def main():
    print("🔍 Generating comprehensive observability configurations for all services...")
    
    for service_name, service_config in SERVICES.items():
        print(f"\n📊 Processing {service_name}...")
        
        service_dir = f"apps/{service_name}"
        obs_dir = f"{service_dir}/observability"
        
        # Ensure observability directory exists
        os.makedirs(obs_dir, exist_ok=True)
        os.makedirs(f"{obs_dir}/dashboards", exist_ok=True)
        
        # Generate dashboard JSON
        dashboard = generate_dashboard_json(service_name, service_config)
        with open(f"{obs_dir}/dashboards/{service_name}.json", "w") as f:
            json.dump(dashboard, f, indent=2)
        print(f"  ✅ Dashboard: {obs_dir}/dashboards/{service_name}.json")
        
        # Generate alerts YAML
        alerts = generate_alerts_yaml(service_name, service_config)
        with open(f"{obs_dir}/alerts.yaml", "w") as f:
            yaml.dump(alerts, f, default_flow_style=False, sort_keys=False)
        print(f"  ✅ Alerts: {obs_dir}/alerts.yaml")
        
        # Generate SLO.md
        slo_content = generate_slo_md(service_name, service_config)
        with open(f"{obs_dir}/SLO.md", "w") as f:
            f.write(slo_content)
        print(f"  ✅ SLO: {obs_dir}/SLO.md")
        
        # Generate runbook.md
        runbook_content = generate_runbook_md(service_name, service_config)
        with open(f"{obs_dir}/runbook.md", "w") as f:
            f.write(runbook_content)
        print(f"  ✅ Runbook: {obs_dir}/runbook.md")
    
    print(f"\n🎯 Generated observability configurations for {len(SERVICES)} services!")
    print("📁 Files created per service:")
    print("   - observability/dashboards/{service}.json")
    print("   - observability/alerts.yaml") 
    print("   - observability/SLO.md")
    print("   - observability/runbook.md")

if __name__ == "__main__":
    main()
