# API Gateway Service Level Objectives (SLO)

## Service Level Indicators (SLIs)

| Metric            | Description                       | Target  | Error Budget |
| ----------------- | --------------------------------- | ------- | ------------ |
| **Availability**  | Percentage of successful requests | 99.9%   | 0.1%         |
| **Latency (p50)** | 50th percentile response time     | < 100ms | < 200ms      |
| **Latency (p95)** | 95th percentile response time     | < 500ms | < 1000ms     |
| **Error Rate**    | Percentage of 5xx responses       | < 0.1%  | < 1%         |

## Monitoring Queries

### Availability

```promql
(
  sum(rate(http_requests_total{service="api-gateway",status!~"5.."}[5m])) /
  sum(rate(http_requests_total{service="api-gateway"}[5m]))
) * 100
```

### Latency P95

```promql
histogram_quantile(0.95,
  rate(http_request_duration_seconds_bucket{service="api-gateway"}[5m])
) * 1000
```

### Error Rate

```promql
(
  sum(rate(http_requests_total{service="api-gateway",status=~"5.."}[5m])) /
  sum(rate(http_requests_total{service="api-gateway"}[5m]))
) * 100
```

## Alerting Rules

### Critical Alerts

- **High Error Rate**: Error rate > 1% for 5 minutes
- **High Latency**: P95 latency > 1000ms for 5 minutes
- **Service Down**: Availability < 95% for 2 minutes

### Warning Alerts

- **Elevated Error Rate**: Error rate > 0.5% for 10 minutes
- **Elevated Latency**: P95 latency > 500ms for 10 minutes
- **Low Availability**: Availability < 99% for 5 minutes

## Error Budget Burn Rate

| Period   | Budget Consumption | Alert Threshold  |
| -------- | ------------------ | ---------------- |
| 1 hour   | 5%                 | Page immediately |
| 6 hours  | 10%                | Page immediately |
| 24 hours | 25%                | Ticket creation  |
| 72 hours | 50%                | Review required  |
