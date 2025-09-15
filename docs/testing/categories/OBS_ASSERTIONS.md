# Observability Assertions

## 📊 **Overview**

This document defines the observability assertions and monitoring requirements for the Multi-AI-Agent platform, including metrics validation, SLO monitoring, and alerting thresholds.

## 🎯 **Key Metrics & Thresholds**

### **API Performance Metrics**

#### **Response Time Metrics**

```promql
# API Response Time P95
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{service="api-gateway"}[5m]))

# API Response Time P99
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{service="api-gateway"}[5m]))

# Why it matters: Direct user experience impact
# Threshold: P95 < 500ms, P99 < 1000ms
```

#### **Request Rate Metrics**

```promql
# Request Rate
rate(http_requests_total{service="api-gateway"}[5m])

# Why it matters: System load and capacity planning
# Threshold: > 100 RPS sustained
```

#### **Error Rate Metrics**

```promql
# Error Rate
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])

# Why it matters: System reliability and user experience
# Threshold: < 0.1% error rate
```

### **WebSocket Performance Metrics**

#### **Connection Metrics**

```promql
# Active WebSocket Connections
websocket_active_connections{service="realtime"}

# Connection Establishment Time
histogram_quantile(0.95, rate(websocket_connection_duration_seconds_bucket[5m]))

# Why it matters: Real-time communication capacity
# Threshold: < 100ms connection time
```

#### **Backpressure Metrics**

```promql
# Backpressure Drops
rate(websocket_backpressure_drops_total[5m])

# Message Queue Size
websocket_message_queue_size

# Why it matters: System stability under load
# Threshold: < 10 drops/minute
```

### **Router Performance Metrics**

#### **Decision Latency**

```promql
# Router Decision Latency
histogram_quantile(0.95, rate(router_decision_latency_ms_bucket[5m]))

# Why it matters: AI routing efficiency
# Threshold: P95 < 100ms
```

#### **Misroute Rate**

```promql
# Router Misroute Rate
rate(router_misroute_total[5m]) / rate(router_requests_total[5m])

# Why it matters: AI accuracy and cost optimization
# Threshold: < 5% misroute rate
```

#### **Tier Distribution**

```promql
# Tier Usage Distribution
rate(router_tier_usage_total[5m]) by (tier)

# Why it matters: Cost optimization and performance
# Threshold: SLM_A > 60%, SLM_B > 30%, LLM < 10%
```

### **Workflow Execution Metrics**

#### **Execution Time**

```promql
# Workflow Execution Time
histogram_quantile(0.95, rate(workflow_execution_duration_seconds_bucket[5m]))

# Why it matters: User experience and SLA compliance
# Threshold: P95 < 5s
```

#### **Success Rate**

```promql
# Workflow Success Rate
rate(workflow_executions_total{status="success"}[5m]) / rate(workflow_executions_total[5m])

# Why it matters: Business process reliability
# Threshold: > 99% success rate
```

#### **Compensation Rate**

```promql
# Saga Compensation Rate
rate(workflow_compensations_total[5m]) / rate(workflow_executions_total[5m])

# Why it matters: Data consistency and reliability
# Threshold: < 1% compensation rate
```

### **Cost Metrics**

#### **Cost per Request**

```promql
# Average Cost per Request
rate(cost_usd_total[5m]) / rate(http_requests_total[5m])

# Why it matters: Business sustainability
# Threshold: < $0.01 per request
```

#### **Token Usage**

```promql
# Token Usage Rate
rate(tokens_total[5m])

# Why it matters: LLM cost optimization
# Threshold: < 1000 tokens/request average
```

### **Multi-Tenant Metrics**

#### **Tenant Isolation**

```promql
# Cross-Tenant Data Access (should be 0)
cross_tenant_data_access_total

# Why it matters: Data security and compliance
# Threshold: 0 cross-tenant access
```

#### **Quota Usage**

```promql
# Tenant Quota Usage
tenant_quota_usage_percent

# Why it matters: Fair resource allocation
# Threshold: < 90% quota usage
```

## 🔍 **SLO Monitoring**

### **Availability SLO**

```yaml
slo: "api_availability"
target: 99.9%
window: "30d"
description: "API availability over 30 days"
```

```promql
# Availability Calculation
(
  rate(http_requests_total{status!~"5.."}[5m]) /
  rate(http_requests_total[5m])
) * 100
```

### **Latency SLO**

```yaml
slo: "api_latency"
target: "P95 < 500ms"
window: "7d"
description: "API response time P95 over 7 days"
```

```promql
# Latency SLO
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

### **Error Rate SLO**

```yaml
slo: "api_error_rate"
target: "< 0.1%"
window: "7d"
description: "API error rate over 7 days"
```

```promql
# Error Rate SLO
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) * 100
```

## 🚨 **Alerting Rules**

### **Critical Alerts**

```yaml
alerts:
  - name: "API High Error Rate"
    condition: 'rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.01'
    severity: "critical"
    description: "API error rate exceeds 1%"

  - name: "API High Latency"
    condition: "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1"
    severity: "critical"
    description: "API P95 latency exceeds 1 second"

  - name: "WebSocket Backpressure High"
    condition: "rate(websocket_backpressure_drops_total[5m]) > 100"
    severity: "critical"
    description: "WebSocket backpressure drops exceed 100/minute"

  - name: "Cross-Tenant Data Access"
    condition: "increase(cross_tenant_data_access_total[5m]) > 0"
    severity: "critical"
    description: "Cross-tenant data access detected"
```

### **Warning Alerts**

```yaml
alerts:
  - name: "API Latency Warning"
    condition: "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 0.5"
    severity: "warning"
    description: "API P95 latency exceeds 500ms"

  - name: "Router Misroute Rate High"
    condition: "rate(router_misroute_total[5m]) / rate(router_requests_total[5m]) > 0.05"
    severity: "warning"
    description: "Router misroute rate exceeds 5%"

  - name: "Cost per Request High"
    condition: "rate(cost_usd_total[5m]) / rate(http_requests_total[5m]) > 0.01"
    severity: "warning"
    description: "Cost per request exceeds $0.01"

  - name: "Tenant Quota Usage High"
    condition: "tenant_quota_usage_percent > 90"
    severity: "warning"
    description: "Tenant quota usage exceeds 90%"
```

## 📊 **Dashboard Metrics**

### **System Overview Dashboard**

```yaml
dashboard: "system_overview"
panels:
  - title: "Request Rate"
    query: "rate(http_requests_total[5m])"
    type: "graph"

  - title: "Response Time P95"
    query: "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))"
    type: "graph"

  - title: "Error Rate"
    query: 'rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])'
    type: "graph"

  - title: "Active WebSocket Connections"
    query: "websocket_active_connections"
    type: "stat"
```

### **Business Metrics Dashboard**

```yaml
dashboard: "business_metrics"
panels:
  - title: "Workflow Success Rate"
    query: 'rate(workflow_executions_total{status="success"}[5m]) / rate(workflow_executions_total[5m])'
    type: "graph"

  - title: "Cost per Request"
    query: "rate(cost_usd_total[5m]) / rate(http_requests_total[5m])"
    type: "graph"

  - title: "Router Tier Distribution"
    query: "rate(router_tier_usage_total[5m]) by (tier)"
    type: "pie"

  - title: "Tenant Usage"
    query: "rate(tenant_requests_total[5m]) by (tenant_id)"
    type: "table"
```

## 🔍 **Distributed Tracing**

### **Trace Attributes**

```yaml
required_attributes:
  - "run_id": "Unique execution identifier"
  - "step_id": "Individual step identifier"
  - "tenant_id": "Tenant context"
  - "user_id": "User context"
  - "tool_id": "Tool identifier"
  - "tier": "AI tier used"
  - "workflow": "Workflow name"
  - "trace_id": "Distributed trace ID"
  - "span_id": "Span identifier"
```

### **Span Validation**

```python
def validate_trace_attributes(span):
    """Validate required trace attributes."""
    required_attrs = [
        "run_id", "step_id", "tenant_id", "user_id",
        "tool_id", "tier", "workflow", "trace_id", "span_id"
    ]

    for attr in required_attrs:
        assert attr in span.attributes, f"Missing attribute: {attr}"
        assert span.attributes[attr] is not None, f"Null attribute: {attr}"
```

## 📋 **Log Validation**

### **Structured Logging**

```yaml
log_format: "json"
required_fields:
  - "timestamp": "ISO 8601 format"
  - "level": "DEBUG, INFO, WARN, ERROR"
  - "service": "Service name"
  - "tenant_id": "Tenant context"
  - "user_id": "User context"
  - "trace_id": "Distributed trace ID"
  - "message": "Log message"
```

### **PII Redaction**

```python
def validate_log_redaction(log_entry):
    """Validate PII redaction in logs."""
    pii_patterns = [
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
        r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
        r'\b\d{4}-\d{4}-\d{4}-\d{4}\b',  # Credit card
        r'\b\d{3}-\d{3}-\d{4}\b'  # Phone
    ]

    for pattern in pii_patterns:
        assert not re.search(pattern, log_entry), f"PII detected: {pattern}"
```

## 🎯 **Assertion Examples**

### **Prometheus Query Validation**

```python
def validate_prometheus_metrics():
    """Validate Prometheus metrics are present and within thresholds."""
    metrics = [
        "http_requests_total",
        "http_request_duration_seconds",
        "websocket_active_connections",
        "router_decision_latency_ms",
        "workflow_executions_total",
        "cost_usd_total"
    ]

    for metric in metrics:
        result = prometheus_query(f"count({metric})")
        assert result > 0, f"Metric {metric} not found"
```

### **SLO Validation**

```python
def validate_slo_compliance():
    """Validate SLO compliance."""
    # Availability SLO
    availability = prometheus_query("rate(http_requests_total{status!~\"5..\"}[5m]) / rate(http_requests_total[5m])")
    assert availability > 0.999, f"Availability SLO violated: {availability}"

    # Latency SLO
    latency_p95 = prometheus_query("histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))")
    assert latency_p95 < 0.5, f"Latency SLO violated: {latency_p95}"

    # Error Rate SLO
    error_rate = prometheus_query("rate(http_requests_total{status=~\"5..\"}[5m]) / rate(http_requests_total[5m])")
    assert error_rate < 0.001, f"Error Rate SLO violated: {error_rate}"
```

---

**Status**: ✅ Production-Ready Observability Assertions  
**Last Updated**: September 2024  
**Version**: 1.0.0
