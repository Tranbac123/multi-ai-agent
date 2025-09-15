# Performance Testing Profiles

## 📊 **Overview**

This document defines the performance testing profiles and strategies for the Multi-AI-Agent platform, including load testing scenarios, performance baselines, and regression detection.

## 🎯 **Load Testing Strategy**

### **Performance Objectives**

- **API Response Time**: p95 < 500ms, p99 < 1000ms
- **WebSocket Latency**: p95 < 100ms, p99 < 200ms
- **Throughput**: > 1000 RPS sustained
- **Error Rate**: < 0.1% under normal load
- **Cost per Request**: < $0.01

### **Test Environments**

- **Baseline**: Development environment with production-like data
- **Stress**: Staging environment with increased load
- **Production**: Canary deployment with limited traffic

## 👥 **User Profiles**

### **APIUser (REST API)**

```python
class APIUser(HttpUser):
    """REST API user simulating typical API usage patterns."""

    wait_time = between(1, 3)  # 1-3 seconds between requests

    @task(3)
    def chat_request(self):
        """Chat API requests (70% of traffic)."""
        self.client.post("/api/chat", json={
            "message": "How can I help you?",
            "context": {"session_id": "test_session"}
        })

    @task(2)
    def workflow_request(self):
        """Workflow execution requests (20% of traffic)."""
        self.client.post("/api/workflows/execute", json={
            "workflow_id": "faq_workflow",
            "parameters": {"query": "test query"}
        })

    @task(1)
    def analytics_request(self):
        """Analytics requests (10% of traffic)."""
        self.client.get("/api/analytics/metrics")
```

### **WSUser (WebSocket Streaming)**

```python
class WSUser(User):
    """WebSocket user simulating real-time communication."""

    wait_time = between(0.5, 2)  # 0.5-2 seconds between messages

    def on_start(self):
        """Establish WebSocket connection."""
        self.ws = self.client.websocket("/ws/chat")

    @task(5)
    def send_message(self):
        """Send chat message via WebSocket."""
        message = {
            "type": "message",
            "content": "Hello, I need help",
            "timestamp": datetime.now().isoformat()
        }
        self.ws.send(json.dumps(message))

        # Wait for response
        response = self.ws.recv()
        self.validate_response(response)

    @task(1)
    def send_heartbeat(self):
        """Send heartbeat to maintain connection."""
        self.ws.send(json.dumps({"type": "ping"}))

    def on_stop(self):
        """Close WebSocket connection."""
        self.ws.close()
```

## 📈 **Performance Profiles**

### **Baseline Profile**

```yaml
profile: "baseline"
description: "Normal production load"
users: 100
spawn_rate: 10
duration: "10m"
targets:
  - api_response_time_p95: "< 500ms"
  - api_response_time_p99: "< 1000ms"
  - websocket_latency_p95: "< 100ms"
  - error_rate: "< 0.1%"
  - throughput: "> 100 RPS"
```

### **Stress Profile**

```yaml
profile: "stress"
description: "High load stress testing"
users: 500
spawn_rate: 50
duration: "5m"
targets:
  - api_response_time_p95: "< 1000ms"
  - api_response_time_p99: "< 2000ms"
  - websocket_latency_p95: "< 200ms"
  - error_rate: "< 1%"
  - throughput: "> 500 RPS"
```

### **Spike Profile**

```yaml
profile: "spike"
description: "Traffic spike testing"
users: 1000
spawn_rate: 100
duration: "2m"
targets:
  - api_response_time_p95: "< 1500ms"
  - api_response_time_p99: "< 3000ms"
  - websocket_latency_p95: "< 300ms"
  - error_rate: "< 5%"
  - throughput: "> 1000 RPS"
```

### **Soak Profile**

```yaml
profile: "soak"
description: "Extended duration testing"
users: 200
spawn_rate: 20
duration: "2h"
targets:
  - api_response_time_p95: "< 800ms"
  - api_response_time_p99: "< 1500ms"
  - websocket_latency_p95: "< 150ms"
  - error_rate: "< 0.5%"
  - throughput: "> 200 RPS"
  - memory_leak: "none"
```

## 🔄 **WebSocket Backpressure Testing**

### **Slow Client Simulation**

```python
class SlowClientUser(User):
    """Simulates slow clients that cause backpressure."""

    def on_start(self):
        self.ws = self.client.websocket("/ws/chat")

    @task
    def slow_message_processing(self):
        """Send message but process response slowly."""
        message = {"type": "message", "content": "test"}
        self.ws.send(json.dumps(message))

        # Simulate slow processing
        time.sleep(5)  # 5 second delay

        response = self.ws.recv()
        self.validate_response(response)

    @task
    def rapid_message_sending(self):
        """Send multiple messages rapidly."""
        for i in range(10):
            message = {"type": "message", "content": f"message {i}"}
            self.ws.send(json.dumps(message))
            time.sleep(0.1)  # 100ms between messages
```

### **Backpressure Validation**

```python
def validate_backpressure_behavior(self, response):
    """Validate backpressure handling."""
    # Check for backpressure indicators
    assert "backpressure" in response
    assert response["backpressure"]["drops"] >= 0
    assert response["backpressure"]["queue_size"] < 1000

    # Verify final message delivery
    if response["type"] == "final":
        assert "content" in response
        assert len(response["content"]) > 0
```

## 📊 **Performance Baselines**

### **API Performance Baselines**

```json
{
  "api_baselines": {
    "chat_endpoint": {
      "p50": 150,
      "p95": 450,
      "p99": 800,
      "max": 1200,
      "unit": "ms"
    },
    "workflow_endpoint": {
      "p50": 800,
      "p95": 2000,
      "p99": 4000,
      "max": 8000,
      "unit": "ms"
    },
    "analytics_endpoint": {
      "p50": 100,
      "p95": 300,
      "p99": 600,
      "max": 1000,
      "unit": "ms"
    }
  }
}
```

### **WebSocket Performance Baselines**

```json
{
  "websocket_baselines": {
    "message_latency": {
      "p50": 50,
      "p95": 100,
      "p99": 200,
      "max": 500,
      "unit": "ms"
    },
    "connection_establishment": {
      "p50": 100,
      "p95": 200,
      "p99": 500,
      "max": 1000,
      "unit": "ms"
    },
    "backpressure_drops": {
      "max": 10,
      "unit": "count"
    }
  }
}
```

## 🎯 **Performance Regression Detection**

### **Regression Thresholds**

```yaml
regression_thresholds:
  api_response_time:
    p95: 20% # 20% increase triggers regression
    p99: 25% # 25% increase triggers regression

  websocket_latency:
    p95: 15% # 15% increase triggers regression
    p99: 20% # 20% increase triggers regression

  error_rate:
    absolute: 0.1% # 0.1% absolute increase triggers regression

  throughput:
    relative: 10% # 10% decrease triggers regression
```

### **Performance Gate Validation**

```python
def validate_performance_gate(baseline, current):
    """Validate performance against regression thresholds."""
    regressions = []

    # Check response time regression
    if current["p95"] > baseline["p95"] * 1.2:
        regressions.append("API response time p95 regression")

    # Check error rate regression
    if current["error_rate"] > baseline["error_rate"] + 0.001:
        regressions.append("Error rate regression")

    # Check throughput regression
    if current["throughput"] < baseline["throughput"] * 0.9:
        regressions.append("Throughput regression")

    if regressions:
        raise PerformanceRegressionError(regressions)
```

## 📈 **Performance Monitoring**

### **Key Metrics**

- **Request Rate**: `rate(http_requests_total[5m])`
- **Response Time**: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))`
- **Error Rate**: `rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])`
- **WebSocket Connections**: `websocket_active_connections`
- **Backpressure Drops**: `websocket_backpressure_drops_total`

### **Performance Alerts**

```yaml
alerts:
  - name: "High Response Time"
    condition: "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1"
    severity: "warning"

  - name: "High Error Rate"
    condition: 'rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.01'
    severity: "critical"

  - name: "WebSocket Backpressure"
    condition: "websocket_backpressure_drops_total > 100"
    severity: "warning"
```

## 🚀 **Performance Test Execution**

### **Local Execution**

```bash
# Run baseline performance test
make perf PROFILE=baseline

# Run stress test
make perf PROFILE=stress

# Run spike test
make perf PROFILE=spike

# Run soak test
make perf PROFILE=soak
```

### **CI/CD Integration**

```yaml
performance_tests:
  baseline: "Every PR"
  stress: "Nightly"
  spike: "Weekly"
  soak: "Weekly"
```

---

**Status**: ✅ Production-Ready Performance Profiles  
**Last Updated**: September 2024  
**Version**: 1.0.0
