# Tool-Service Service Level Objectives (SLO)

## Service Level Indicators (SLIs)

| Metric | Description | Target | Error Budget |
|--------|-------------|---------|--------------|
| **Availability** | Percentage of successful requests | 99.9% | 0.1% |
| **Latency (p50)** | 50th percentile response time | < 100ms | < 200ms |
| **Latency (p95)** | 95th percentile response time | < 500ms | < 1000ms |
| **Error Rate** | Percentage of 5xx responses | < 0.1% | < 1% |

## Monitoring Queries

### Availability
```promql
(
  sum(rate(http_requests_total{service="tool-service",status!~"5.."}[5m])) /
  sum(rate(http_requests_total{service="tool-service"}[5m]))
) * 100
```

### Error Rate
```promql
(
  sum(rate(http_requests_total{service="tool-service",status=~"5.."}[5m])) /
  sum(rate(http_requests_total{service="tool-service"}[5m]))
) * 100
```