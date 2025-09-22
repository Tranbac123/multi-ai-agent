# Analytics Service Service Runbook

## Service Overview
- **Service**: analytics-service
- **Purpose**: Real-time analytics and reporting with time-series data
- **Port**: 8001
- **Type**: http
- **SLO Target**: 99.5%

## Quick Links
- **Dashboard**: [Grafana Dashboard](https://grafana.company.com/d/analytics-service)
- **Logs**: [Loki Logs](https://grafana.company.com/explore?query={service="analytics-service"})
- **Traces**: [Jaeger UI](https://jaeger.company.com/search?service=analytics-service)
- **Alerts**: [AlertManager](https://alertmanager.company.com/#/alerts?filter={service="analytics-service"})

## Common Issues and Solutions

### 🚨 High Error Rate (5xx errors > 5%)

**Symptoms:**
- Increase in 5xx status code responses
- Customer complaints about service unavailability
- Alert: `Analytics_ServiceHighErrorRate`

**Investigation Steps:**
1. **Check Service Health**
   ```bash
   # Check if service is up
   kubectl get pods -l app=analytics-service -n production
   
   # Check recent logs for errors
   kubectl logs -l app=analytics-service -n production --tail=100 | grep ERROR
   ```

2. **Review Error Patterns**
   ```promql
   # Top error endpoints
   topk(10, sum by (endpoint) (rate(http_requests_total{service="analytics-service",status=~"5.."}[5m])))
   
   # Error breakdown by status code
   sum by (status) (rate(http_requests_total{service="analytics-service",status=~"5.."}[5m]))
   ```

3. **Check Dependencies**
   ```bash
   # Database connectivity
   kubectl exec -n production deployment/analytics-service -- ping database-host
   
   # External service health
   curl -H "Authorization: Bearer $TOKEN" https://external-api.com/health
   ```

**Resolution:**
- If database issues: Check connection pool, query performance
- If external API issues: Implement circuit breaker, check API limits
- If memory issues: Scale up pods or optimize memory usage
- If code issues: Deploy hotfix or rollback to previous version

### ⚡ High Latency (P95 > 200ms)

**Symptoms:**
- Slow response times
- Timeout errors from clients
- Alert: `Analytics_ServiceHighLatency`

**Investigation Steps:**
1. **Identify Slow Endpoints**
   ```promql
   # Slowest endpoints (P95)
   topk(10, histogram_quantile(0.95, sum by (endpoint) (rate(http_request_duration_seconds_bucket{service="analytics-service"}[5m]))))
   ```

2. **Check Resource Usage**
   ```promql
   # CPU usage
   rate(container_cpu_usage_seconds_total{container="analytics-service"}[5m]) * 100
   
   # Memory usage
   container_memory_usage_bytes{container="analytics-service"} / 1024/1024/1024
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
- Alert: `Analytics_ServiceServiceDown`

**Investigation Steps:**
1. **Check Pod Status**
   ```bash
   kubectl describe pod -l app=analytics-service -n production
   kubectl get events -n production --sort-by='.lastTimestamp' | grep analytics-service
   ```

2. **Review Startup Logs**
   ```bash
   kubectl logs -l app=analytics-service -n production --previous
   ```

3. **Check Resource Limits**
   ```bash
   kubectl top pod -l app=analytics-service -n production
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
- Alert: `Analytics_ServiceHighMemoryUsage`

**Investigation Steps:**
1. **Memory Usage Breakdown**
   ```promql
   container_memory_usage_bytes{container="analytics-service"} / container_spec_memory_limit_bytes{container="analytics-service"} * 100
   ```

2. **Check for Memory Leaks**
   ```bash
   # Profile memory usage (if profiling enabled)
   curl http://analytics-service:6060/debug/pprof/heap
   ```

**Resolution:**
- Increase memory limits if justified by usage patterns
- Identify and fix memory leaks in application code
- Implement proper connection pooling and resource cleanup
- Consider horizontal scaling instead of vertical scaling

## Monitoring and Observability

### Key Metrics to Monitor
- **Request Rate**: `rate(http_requests_total{service="analytics-service"}[5m])`
- **Error Rate**: `rate(http_requests_total{service="analytics-service",status=~"5.."}[5m])`
- **Latency P95**: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{service="analytics-service"}[5m]))`
- **CPU Usage**: `rate(container_cpu_usage_seconds_total{container="analytics-service"}[5m]) * 100`
- **Memory Usage**: `container_memory_usage_bytes{container="analytics-service"}`

### Log Locations
- **Application Logs**: `kubectl logs -l app=analytics-service -n production`
- **Access Logs**: Available in Grafana Loki with label `{service="analytics-service"}`
- **Error Logs**: Filter by level=ERROR in log aggregation

### Trace Locations
- **Jaeger UI**: Search by service name `analytics-service`
- **Trace sampling**: 1% of requests (configurable)
- **Key operations**: HTTP requests, database queries, external API calls

## Escalation

### On-Call Rotation
- **Primary**: Platform Team oncall
- **Secondary**: Analytics Service Service Owner
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
kubectl get deployment analytics-service -n production -o jsonpath='{.spec.template.spec.containers[0].image}'

# Deploy new version (canary)
kubectl set image deployment/analytics-service analytics-service=new-image:tag -n production

# Monitor deployment
kubectl rollout status deployment/analytics-service -n production

# Rollback if needed
kubectl rollout undo deployment/analytics-service -n production
```

### Health Check Verification
```bash
# Test health endpoint
curl -f http://analytics-service.production.svc.cluster.local:8001/healthz

# Verify metrics endpoint
curl http://analytics-service.production.svc.cluster.local:8001/metrics
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
