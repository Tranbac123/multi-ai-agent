# AIaaS Platform Runbooks

## 🚨 **Emergency Response Procedures**

### **1. Service Down (TIMEOUT)**

**Symptoms:**

- High response times (>5s)
- Timeout errors in logs
- Circuit breakers opening

**Immediate Actions:**

```bash
# 1. Check service status
kubectl get pods -n aiaas
kubectl logs -f deployment/api-gateway -n aiaas

# 2. Check resource usage
kubectl top pods -n aiaas
kubectl describe nodes

# 3. Check database connections
kubectl exec -it postgres-0 -n aiaas -- psql -c "SELECT count(*) FROM pg_stat_activity;"

# 4. Restart affected services
kubectl rollout restart deployment/api-gateway -n aiaas
kubectl rollout restart deployment/orchestrator -n aiaas
```

**Escalation:**

- If service doesn't recover in 5 minutes, escalate to on-call engineer
- Check for database locks or deadlocks
- Consider scaling up resources

---

### **2. Tool Service Down (TOOL_DOWN)**

**Symptoms:**

- Tool calls failing
- Circuit breakers open for specific tools
- High error rates in tool metrics

**Immediate Actions:**

```bash
# 1. Check tool service health
curl -f http://tool-service:8000/health

# 2. Check tool logs
kubectl logs -f deployment/tool-service -n aiaas

# 3. Check external API status
curl -f https://api.external-service.com/health

# 4. Enable fallback mode
kubectl set env deployment/orchestrator FALLBACK_MODE=true -n aiaas
```

**Recovery:**

- If external API is down, enable cached responses
- If internal service is down, restart and check dependencies
- Monitor circuit breaker recovery

---

### **3. Validation Failures (VALIDATION_FAIL)**

**Symptoms:**

- High validation error rates
- Malformed requests being rejected
- Schema validation failures

**Immediate Actions:**

```bash
# 1. Check validation logs
kubectl logs -f deployment/api-gateway -n aiaas | grep validation

# 2. Check schema registry
curl -f http://schema-registry:8080/subjects

# 3. Validate request format
curl -X POST http://api-gateway:8000/api/v1/validate \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'

# 4. Check feature flags
curl -f http://feature-flags:8000/api/v1/flags
```

**Recovery:**

- Update schema definitions if needed
- Disable strict validation temporarily
- Check for client version mismatches

---

### **4. WebSocket Overload (WS_OVERLOAD)**

**Symptoms:**

- WebSocket connection failures
- High backpressure drops
- Memory usage spikes

**Immediate Actions:**

```bash
# 1. Check WebSocket service status
kubectl get pods -l app=realtime-service -n aiaas

# 2. Check connection limits
kubectl exec -it realtime-service-0 -n aiaas -- redis-cli get "ws:max_connections"

# 3. Check memory usage
kubectl top pods -l app=realtime-service -n aiaas

# 4. Scale WebSocket service
kubectl scale deployment realtime-service --replicas=3 -n aiaas
```

**Recovery:**

- Increase connection limits
- Scale horizontally
- Check for connection leaks

---

## 🔧 **Operational Procedures**

### **Database Maintenance**

**Daily Tasks:**

```bash
# 1. Check database health
kubectl exec -it postgres-0 -n aiaas -- psql -c "
SELECT
  datname,
  numbackends,
  xact_commit,
  xact_rollback,
  blks_read,
  blks_hit
FROM pg_stat_database
WHERE datname = 'aiaas';"

# 2. Check slow queries
kubectl exec -it postgres-0 -n aiaas -- psql -c "
SELECT query, mean_time, calls
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;"

# 3. Check table sizes
kubectl exec -it postgres-0 -n aiaas -- psql -c "
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"
```

**Weekly Tasks:**

```bash
# 1. Vacuum analyze
kubectl exec -it postgres-0 -n aiaas -- psql -c "VACUUM ANALYZE;"

# 2. Check for long-running transactions
kubectl exec -it postgres-0 -n aiaas -- psql -c "
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes';"

# 3. Check replication lag
kubectl exec -it postgres-0 -n aiaas -- psql -c "
SELECT client_addr, state, sync_state,
       pg_wal_lsn_diff(pg_current_wal_lsn(), flush_lsn) AS lag_bytes
FROM pg_stat_replication;"
```

### **Monitoring and Alerting**

**Key Metrics to Monitor:**

- Request rate and response time
- Error rates by service
- Database connection pool usage
- Memory and CPU usage
- Circuit breaker states
- WebSocket connection counts

**Alert Thresholds:**

- Response time P95 > 2 seconds
- Error rate > 5%
- Database connections > 80% of pool
- Memory usage > 85%
- Circuit breaker open for > 5 minutes

**Alert Commands:**

```bash
# 1. Check current alerts
kubectl get events --sort-by=.metadata.creationTimestamp -n aiaas

# 2. Check Prometheus alerts
curl -f http://prometheus:9090/api/v1/alerts

# 3. Check Grafana dashboards
curl -f http://grafana:3000/api/health
```

### **Deployment Procedures**

**Blue-Green Deployment:**

```bash
# 1. Deploy new version to green environment
kubectl apply -f k8s/green/

# 2. Run smoke tests
kubectl exec -it green-api-gateway-0 -n aiaas -- curl -f http://localhost:8000/health

# 3. Switch traffic
kubectl patch service api-gateway -n aiaas -p '{"spec":{"selector":{"version":"green"}}}'

# 4. Monitor for 10 minutes
kubectl logs -f deployment/api-gateway -n aiaas

# 5. Clean up old version
kubectl delete -f k8s/blue/
```

**Rolling Update:**

```bash
# 1. Update deployment
kubectl set image deployment/api-gateway api-gateway=image:v2.0.0 -n aiaas

# 2. Monitor rollout
kubectl rollout status deployment/api-gateway -n aiaas

# 3. Rollback if needed
kubectl rollout undo deployment/api-gateway -n aiaas
```

### **Troubleshooting Commands**

**Service Discovery:**

```bash
# 1. List all services
kubectl get services -n aiaas

# 2. Check service endpoints
kubectl get endpoints -n aiaas

# 3. Check DNS resolution
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup api-gateway.aiaas.svc.cluster.local
```

**Log Analysis:**

```bash
# 1. Search for errors
kubectl logs -f deployment/api-gateway -n aiaas | grep -i error

# 2. Search for specific patterns
kubectl logs -f deployment/orchestrator -n aiaas | grep "circuit breaker"

# 3. Follow logs from multiple pods
kubectl logs -f -l app=api-gateway -n aiaas
```

**Performance Analysis:**

```bash
# 1. Check resource usage
kubectl top pods -n aiaas
kubectl top nodes

# 2. Check network policies
kubectl get networkpolicies -n aiaas

# 3. Check persistent volumes
kubectl get pv
kubectl get pvc -n aiaas
```

### **Security Procedures**

**Access Control:**

```bash
# 1. Check RBAC permissions
kubectl get roles -n aiaas
kubectl get rolebindings -n aiaas

# 2. Check service accounts
kubectl get serviceaccounts -n aiaas

# 3. Check network policies
kubectl get networkpolicies -n aiaas
```

**Secret Management:**

```bash
# 1. List secrets
kubectl get secrets -n aiaas

# 2. Check secret contents (base64 encoded)
kubectl get secret api-keys -n aiaas -o yaml

# 3. Rotate secrets
kubectl create secret generic api-keys-new -n aiaas --from-literal=key=value
kubectl patch deployment api-gateway -n aiaas -p '{"spec":{"template":{"spec":{"containers":[{"name":"api-gateway","env":[{"name":"API_KEY","valueFrom":{"secretKeyRef":{"name":"api-keys-new","key":"key"}}}]}]}}}}'
```

### **Backup and Recovery**

**Database Backup:**

```bash
# 1. Create backup
kubectl exec -it postgres-0 -n aiaas -- pg_dump -U postgres aiaas > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Restore from backup
kubectl exec -i postgres-0 -n aiaas -- psql -U postgres aiaas < backup_20240101_120000.sql

# 3. Verify backup
kubectl exec -it postgres-0 -n aiaas -- psql -c "SELECT count(*) FROM users;"
```

**Configuration Backup:**

```bash
# 1. Backup Kubernetes resources
kubectl get all -n aiaas -o yaml > aiaas_backup_$(date +%Y%m%d_%H%M%S).yaml

# 2. Backup ConfigMaps
kubectl get configmaps -n aiaas -o yaml > configmaps_backup.yaml

# 3. Backup Secrets
kubectl get secrets -n aiaas -o yaml > secrets_backup.yaml
```

---

## 📞 **Escalation Procedures**

### **Level 1 (0-15 minutes)**

- Check service status and logs
- Restart affected services
- Check resource usage

### **Level 2 (15-30 minutes)**

- Escalate to senior engineer
- Check database and external dependencies
- Consider scaling resources

### **Level 3 (30+ minutes)**

- Escalate to engineering manager
- Consider rollback to previous version
- Implement emergency procedures

### **Contact Information**

- **On-Call Engineer**: +1-555-0123
- **Engineering Manager**: +1-555-0124
- **DevOps Team**: +1-555-0125
- **Emergency Pager**: +1-555-0126

---

## 🔍 **Common Issues and Solutions**

### **High Memory Usage**

```bash
# Check memory usage
kubectl top pods -n aiaas

# Check for memory leaks
kubectl exec -it api-gateway-0 -n aiaas -- ps aux

# Restart high-memory pods
kubectl delete pod api-gateway-0 -n aiaas
```

### **Database Connection Pool Exhaustion**

```bash
# Check connection count
kubectl exec -it postgres-0 -n aiaas -- psql -c "SELECT count(*) FROM pg_stat_activity;"

# Check connection limits
kubectl exec -it postgres-0 -n aiaas -- psql -c "SHOW max_connections;"

# Restart application pods
kubectl rollout restart deployment/api-gateway -n aiaas
```

### **Circuit Breaker Issues**

```bash
# Check circuit breaker state
curl -f http://api-gateway:8000/api/v1/health/circuit-breakers

# Reset circuit breaker
curl -X POST http://api-gateway:8000/api/v1/circuit-breakers/reset

# Check external service health
curl -f http://external-service:8000/health
```

---

## 📋 **Checklist Templates**

### **Pre-Deployment Checklist**

- [ ] All tests passing
- [ ] Security scan completed
- [ ] Performance tests passed
- [ ] Database migrations ready
- [ ] Rollback plan prepared
- [ ] Monitoring alerts configured

### **Post-Deployment Checklist**

- [ ] Health checks passing
- [ ] Metrics normal
- [ ] No error spikes
- [ ] Performance within SLA
- [ ] User acceptance testing
- [ ] Documentation updated

### **Incident Response Checklist**

- [ ] Incident identified and logged
- [ ] Impact assessed
- [ ] Team notified
- [ ] Root cause analysis started
- [ ] Fix implemented
- [ ] Monitoring for recurrence
- [ ] Post-incident review scheduled
