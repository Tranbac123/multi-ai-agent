# API Gateway Runbook

## Service Overview

The API Gateway serves as the main entry point for all client requests, providing authentication, rate limiting, and intelligent routing to backend services.

## Common Issues

### High Error Rate (5xx responses)

**Symptoms:**

- Increased 5xx error rate
- Client complaints about service unavailability

**Investigation:**

1. Check service logs: `kubectl logs -l app=api-gateway -n production`
2. Verify database connectivity: Check DATABASE_URL connection
3. Check Redis connectivity: Verify rate limiting and session storage
4. Review recent deployments

**Resolution:**

- If database issues: Scale read replicas or check connection pool
- If Redis issues: Restart Redis or check memory usage
- If application issues: Rollback recent deployment

### High Latency

**Symptoms:**

- P95 latency > 1000ms
- Slow response times reported by clients

**Investigation:**

1. Check downstream service health
2. Review database query performance
3. Examine Redis response times
4. Check CPU/Memory utilization

**Resolution:**

- Scale up replicas if CPU/Memory high
- Optimize slow database queries
- Add Redis cluster if memory pressure
- Enable caching for frequently accessed data

### Authentication Failures

**Symptoms:**

- Increased 401/403 responses
- Users unable to login

**Investigation:**

1. Check JWT secret configuration
2. Verify token expiration settings
3. Check user database connectivity
4. Review authentication logs

**Resolution:**

- Rotate JWT secrets if compromised
- Update token expiration if too short
- Scale authentication service
- Clear invalid sessions from Redis

## Emergency Procedures

### Circuit Breaker Activation

```bash
# Enable maintenance mode
kubectl patch configmap api-gateway-config -p '{"data":{"MAINTENANCE_MODE":"true"}}'
kubectl rollout restart deployment/api-gateway
```

### Traffic Rerouting

```bash
# Route traffic to backup region
kubectl patch ingress api-gateway -p '{"spec":{"rules":[{"host":"api.company.com","http":{"paths":[{"path":"/","backend":{"serviceName":"api-gateway-backup","servicePort":8000}}]}}]}}'
```

### Scaling Under Load

```bash
# Emergency scale up
kubectl scale deployment api-gateway --replicas=10
```

## Monitoring Links

- [Grafana Dashboard](http://grafana.company.com/d/api-gateway)
- [Prometheus Alerts](http://prometheus.company.com/alerts)
- [Log Aggregation](http://logs.company.com/api-gateway)
