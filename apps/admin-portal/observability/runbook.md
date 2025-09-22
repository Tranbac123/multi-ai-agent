# Admin-Portal Service Runbook

## Service Overview
Backend admin interface for tenant management

**Technology**: FastAPI + Jinja2
**Port**: 8100

## Common Issues

### High Error Rate (5xx responses)

**Symptoms:**
- Increased 5xx error rate
- Client complaints about service unavailability

**Investigation:**
1. Check service logs: `kubectl logs -l app=admin-portal -n production`
2. Verify database connectivity
3. Check Redis connectivity (if applicable)
4. Review recent deployments

**Resolution:**
- If database issues: Check connection pool settings
- If Redis issues: Restart Redis or check memory usage
- If application issues: Rollback recent deployment

### High Latency

**Symptoms:**
- P95 latency > 1000ms
- Slow response times reported by clients

**Investigation:**
1. Check downstream service health
2. Review database query performance
3. Examine Redis response times (if applicable)
4. Check CPU/Memory utilization

**Resolution:**
- Scale up replicas if CPU/Memory high
- Optimize slow queries
- Add caching for frequently accessed data

### Service Down

**Symptoms:**
- Service not responding to health checks
- 0% availability

**Investigation:**
1. Check pod status: `kubectl get pods -l app=admin-portal -n production`
2. Check logs: `kubectl logs -l app=admin-portal -n production --tail=100`
3. Check resource limits and usage
4. Verify configuration

**Resolution:**
- Restart service: `kubectl rollout restart deployment/admin-portal -n production`
- Scale up if resource constrained
- Fix configuration issues if found

## Emergency Procedures

### Circuit Breaker Activation
```bash
# Enable maintenance mode
kubectl patch configmap admin-portal-config -p '{"data":{"MAINTENANCE_MODE":"true"}}'
kubectl rollout restart deployment/admin-portal
```

### Scaling Under Load
```bash
# Emergency scale up
kubectl scale deployment admin-portal --replicas=10
```

## Monitoring Links
- [Grafana Dashboard](http://grafana.company.com/d/admin-portal)
- [Prometheus Alerts](http://prometheus.company.com/alerts)
- [Log Aggregation](http://logs.company.com/admin-portal)

## On-call Checklist
- [ ] Check service health endpoint
- [ ] Verify database connectivity
- [ ] Check Redis connectivity (if applicable)
- [ ] Review recent deployments
- [ ] Check resource utilization
- [ ] Verify downstream service health
