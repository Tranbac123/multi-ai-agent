# Model Gateway SLO

## Service Level Objectives

### Availability

- **Target**: 99.9% uptime
- **Measurement**: `(total_requests - error_requests) / total_requests`
- **Time Window**: Rolling 30 days

### Latency

- **Target**: P95 < 5 seconds, P99 < 10 seconds
- **Measurement**: `histogram_quantile(0.95, http_request_duration_seconds)`
- **Time Window**: Rolling 24 hours

### Error Rate

- **Target**: < 1% error rate
- **Measurement**: `rate(http_requests_total{status=~"5.."}[5m])`
- **Time Window**: Rolling 1 hour

### Provider Availability

- **Target**: At least 1 provider healthy at all times
- **Measurement**: `count(provider_health == 1)`
- **Time Window**: Real-time

## Service Level Indicators

```promql
# Availability
100 * (1 - rate(http_requests_total{status=~"5.."}[30d]) / rate(http_requests_total[30d]))

# P95 Latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[24h]))

# Error Rate
100 * rate(http_requests_total{status=~"5.."}[1h]) / rate(http_requests_total[1h])

# Provider Health
count(provider_health == 1)
```

## Error Budget

- **Monthly Error Budget**: 0.1% (43.2 minutes downtime per month)
- **Daily Error Budget**: 0.1% (1.44 minutes downtime per day)
