# Tenant Service Service Level Objectives (SLO)

## Overview
This document defines the Service Level Objectives (SLOs) for the tenant-service service.

**Service Purpose**: Multi-tenant management with regional data residency

## SLO Definitions

### 1. Availability SLO
- **Objective**: 99.9% availability over a 30-day rolling window
- **SLI**: Percentage of successful requests (non-5xx responses)
- **Error Budget**: 0.1% (0.1 hours downtime per month)

**PromQL Query**:
```promql
# Success Rate (SLI)
(
  sum(rate(http_requests_total{service="tenant-service",status!~"5.."}[30d])) /
  sum(rate(http_requests_total{service="tenant-service"}[30d]))
) * 100

# Error Budget Burn Rate (1h window)
(
  1 - (
    sum(rate(http_requests_total{service="tenant-service",status!~"5.."}[1h])) /
    sum(rate(http_requests_total{service="tenant-service"}[1h]))
  )
) / (1 - 0.9990000000000001)
```

### 2. Latency SLO
- **Objective**: 95% of requests complete within 100ms
- **SLI**: P95 latency of successful requests

**PromQL Query**:
```promql
# P95 Latency (SLI)
histogram_quantile(0.95, 
  rate(http_request_duration_seconds_bucket{service="tenant-service",status!~"5.."}[5m])
)

# Latency SLO Compliance (percentage of requests under threshold)
(
  sum(rate(http_request_duration_seconds_bucket{service="tenant-service",status!~"5..",le="0.1"}[5m])) /
  sum(rate(http_request_duration_seconds_count{service="tenant-service",status!~"5.."}[5m]))
) * 100
```

### 3. Error Rate SLO
- **Objective**: Less than 1% error rate over a 1-hour rolling window
- **SLI**: Percentage of requests returning 5xx status codes

**PromQL Query**:
```promql
# Error Rate (SLI)
(
  sum(rate(http_requests_total{service="tenant-service",status=~"5.."}[1h])) /
  sum(rate(http_requests_total{service="tenant-service"}[1h]))
) * 100
```

## SLO Monitoring and Alerting

### Error Budget Alerts
- **Fast Burn**: Error budget consumption > 2% in 1 hour
- **Slow Burn**: Error budget consumption > 5% in 6 hours

### SLO Dashboard
- **Grafana Dashboard**: `tenant-service-slo-dashboard`
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
- [Runbook](./tenant-service-runbook.md)
- [Service Architecture](../README.md)
- [Incident Response](https://docs.company.com/incident-response)
