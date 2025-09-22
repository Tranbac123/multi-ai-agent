# Operational Runbooks

## Overview

This document contains operational runbooks for the Multi-Tenant AIaaS Platform.

## Runbooks

### TIMEOUT: Service Timeout Handling

**Symptoms:**

- High latency metrics (P95 > 500ms)
- Timeout errors in logs
- Circuit breaker activations

**Immediate Actions:**

1. Check service health: `curl http://service:port/health`
2. Check resource usage: `kubectl top pods -n production`
3. Check logs: `kubectl logs -f deployment/service-name -n production`

**Commands:**

```bash
# Check service status
kubectl get pods -n production | grep service-name

# Check resource usage
kubectl top pods -n production | grep service-name

# Check logs for timeout errors
kubectl logs -f deployment/service-name -n production | grep -i timeout

# Scale up if needed
kubectl scale deployment service-name --replicas=3 -n production
```

**Environment Toggles:**

- `TIMEOUT_THRESHOLD_MS`: Increase from 5000 to 10000
- `CIRCUIT_BREAKER_TIMEOUT`: Increase from 30000 to 60000
- `MAX_RETRIES`: Increase from 3 to 5

**Dashboards to Check:**

- Grafana: Service Latency Dashboard
- Prometheus: `service_latency_histogram`
- Jaeger: Service traces

---

### TOOL_DOWN: Tool Service Failure Recovery

**Symptoms:**

- Tool service health checks failing
- 503 errors from tool endpoints
- Circuit breaker open for tool services

**Immediate Actions:**

1. Check tool service status: `curl http://tool-service:port/health`
2. Check tool service logs: `kubectl logs -f deployment/tool-service -n production`
3. Verify tool service dependencies

**Commands:**

```bash
# Check tool service status
kubectl get pods -n production | grep tool-service

# Check tool service logs
kubectl logs -f deployment/tool-service -n production

# Restart tool service if needed
kubectl rollout restart deployment/tool-service -n production

# Check tool service dependencies
kubectl describe pod tool-service-pod -n production
```

**Environment Toggles:**

- `TOOL_TIMEOUT_MS`: Increase from 30000 to 60000
- `TOOL_RETRY_ATTEMPTS`: Increase from 3 to 5
- `CIRCUIT_BREAKER_THRESHOLD`: Increase from 5 to 10

**Dashboards to Check:**

- Grafana: Tool Service Health Dashboard
- Prometheus: `tool_service_health_check`
- Jaeger: Tool service traces

---

### VALIDATION_FAIL: Input Validation Failure Handling

**Symptoms:**

- High validation error rates
- 400 Bad Request errors
- Input validation failures in logs

**Immediate Actions:**

1. Check validation error logs: `kubectl logs -f deployment/service-name -n production | grep -i validation`
2. Check input patterns causing failures
3. Verify validation rules are correct

**Commands:**

```bash
# Check validation errors
kubectl logs -f deployment/service-name -n production | grep -i "validation failed"

# Check error rates
kubectl logs -f deployment/service-name -n production | grep -i "400"

# Check validation rules
kubectl exec -it deployment/service-name -n production -- cat /app/validation_rules.json
```

**Environment Toggles:**

- `VALIDATION_STRICT_MODE`: Set to false for temporary relief
- `VALIDATION_TIMEOUT_MS`: Increase from 1000 to 5000
- `LOG_VALIDATION_ERRORS`: Set to true for debugging

**Dashboards to Check:**

- Grafana: Validation Error Dashboard
- Prometheus: `validation_errors_total`
- Jaeger: Validation traces

---

### WS_OVERLOAD: WebSocket Overload Management

**Symptoms:**

- High WebSocket connection counts
- Backpressure drops in logs
- WebSocket connection timeouts

**Immediate Actions:**

1. Check WebSocket connection count: `kubectl logs -f deployment/realtime -n production | grep -i "connections"`
2. Check backpressure metrics: `kubectl logs -f deployment/realtime -n production | grep -i "backpressure"`
3. Scale realtime service if needed

**Commands:**

```bash
# Check WebSocket connections
kubectl logs -f deployment/realtime -n production | grep -i "active connections"

# Check backpressure drops
kubectl logs -f deployment/realtime -n production | grep -i "backpressure"

# Scale realtime service
kubectl scale deployment realtime --replicas=5 -n production

# Check WebSocket metrics
kubectl exec -it deployment/realtime -n production -- curl http://localhost:8080/metrics | grep websocket
```

**Environment Toggles:**

- `MAX_WEBSOCKET_CONNECTIONS`: Increase from 1000 to 2000
- `BACKPRESSURE_THRESHOLD`: Increase from 0.8 to 0.9
- `WEBSOCKET_TIMEOUT_MS`: Increase from 30000 to 60000

**Dashboards to Check:**

- Grafana: WebSocket Dashboard
- Prometheus: `websocket_connections_active`
- Prometheus: `websocket_backpressure_drops`

---

## General Troubleshooting Commands

### Service Health Checks

```bash
# Check all services
kubectl get pods -n production

# Check service logs
kubectl logs -f deployment/service-name -n production

# Check service metrics
kubectl exec -it deployment/service-name -n production -- curl http://localhost:8080/metrics
```

### Resource Monitoring

```bash
# Check resource usage
kubectl top pods -n production

# Check node resources
kubectl top nodes

# Check persistent volumes
kubectl get pv
```

### Network Troubleshooting

```bash
# Check service endpoints
kubectl get endpoints -n production

# Check ingress
kubectl get ingress -n production

# Check network policies
kubectl get networkpolicies -n production
```

### Database Troubleshooting

```bash
# Check database connections
kubectl exec -it deployment/api-gateway -n production -- psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity;"

# Check database locks
kubectl exec -it deployment/api-gateway -n production -- psql $DATABASE_URL -c "SELECT * FROM pg_locks WHERE NOT granted;"
```

## Alert Response Procedures

### Critical Alerts (P0)

1. **Immediate Response**: Acknowledge alert within 5 minutes
2. **Investigation**: Start investigation within 10 minutes
3. **Communication**: Update status page and notify stakeholders
4. **Resolution**: Work towards resolution with regular updates

### Warning Alerts (P1)

1. **Response**: Acknowledge alert within 15 minutes
2. **Investigation**: Start investigation within 30 minutes
3. **Communication**: Update status page if impact is significant
4. **Resolution**: Work towards resolution with regular updates

### Info Alerts (P2)

1. **Response**: Acknowledge alert within 1 hour
2. **Investigation**: Start investigation within 2 hours
3. **Communication**: Update status page if needed
4. **Resolution**: Work towards resolution

## Escalation Procedures

### Level 1: On-Call Engineer

- Initial response and investigation
- Basic troubleshooting using runbooks
- Escalate to Level 2 if unable to resolve

### Level 2: Senior Engineer

- Advanced troubleshooting
- System architecture analysis
- Escalate to Level 3 if needed

### Level 3: Engineering Manager

- Critical system decisions
- Resource allocation
- External vendor coordination

## Post-Incident Procedures

1. **Incident Report**: Document incident details
2. **Root Cause Analysis**: Identify root cause
3. **Action Items**: Create action items to prevent recurrence
4. **Runbook Updates**: Update runbooks based on learnings
5. **Team Review**: Conduct team review and lessons learned
