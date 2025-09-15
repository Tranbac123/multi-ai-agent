# Performance Testing Documentation

## Overview

This document provides comprehensive guidance on performance testing for the Multi-AI-Agent platform, including load testing, performance benchmarking, scalability validation, and performance monitoring strategies.

## Table of Contents

1. [Performance Testing Strategy](#performance-testing-strategy)
2. [Performance Targets](#performance-targets)
3. [Load Testing with Locust](#load-testing-with-locust)
4. [Performance Benchmarking](#performance-benchmarking)
5. [Scalability Testing](#scalability-testing)
6. [Performance Monitoring](#performance-monitoring)
7. [Performance Regression Testing](#performance-regression-testing)
8. [Best Practices](#best-practices)

## Performance Testing Strategy

### Testing Pyramid for Performance

```
                    ┌─────────────────┐
                    │   Load Tests    │  ← High load, long duration
                    │   (Locust)      │
                    └─────────────────┘
                  ┌─────────────────────┐
                  │  Stress Tests       │  ← Beyond normal capacity
                  │  (Resource limits)  │
                  └─────────────────────┘
              ┌─────────────────────────────┐
              │    Performance Tests       │  ← Baseline performance
              │    (Benchmarks)            │
              └─────────────────────────────┘
```

### Performance Test Categories

| Test Type           | Purpose                                  | Duration       | Load Level      | Frequency |
| ------------------- | ---------------------------------------- | -------------- | --------------- | --------- |
| **Benchmark Tests** | Establish baseline performance           | 1-5 minutes    | Normal load     | Every PR  |
| **Load Tests**      | Validate performance under expected load | 10-30 minutes  | Expected load   | Daily     |
| **Stress Tests**    | Find breaking points                     | 30-60 minutes  | Beyond capacity | Weekly    |
| **Spike Tests**     | Test sudden load increases               | 5-15 minutes   | Sudden spikes   | Weekly    |
| **Volume Tests**    | Test with large data volumes             | 30-120 minutes | Large datasets  | Weekly    |

## Performance Targets

### Latency Targets

| Component              | p50 Target | p95 Target | p99 Target | SLA   |
| ---------------------- | ---------- | ---------- | ---------- | ----- |
| **Router Decision**    | < 50ms     | < 100ms    | < 200ms    | 99.9% |
| **Tool Execution**     | < 500ms    | < 1000ms   | < 2000ms   | 99.5% |
| **Workflow Execution** | < 2000ms   | < 5000ms   | < 10000ms  | 99.0% |
| **API Response**       | < 100ms    | < 500ms    | < 1000ms   | 99.9% |
| **WebSocket Message**  | < 10ms     | < 50ms     | < 100ms    | 99.9% |
| **Database Query**     | < 10ms     | < 50ms     | < 100ms    | 99.9% |
| **Cache Access**       | < 1ms      | < 5ms      | < 10ms     | 99.9% |

### Throughput Targets

| Component                 | Target           | Peak             | Burst            |
| ------------------------- | ---------------- | ---------------- | ---------------- |
| **API Requests**          | 1000 req/s       | 2000 req/s       | 5000 req/s       |
| **WebSocket Connections** | 10000 concurrent | 20000 concurrent | 50000 concurrent |
| **Database Queries**      | 10000 qps        | 20000 qps        | 50000 qps        |
| **Message Processing**    | 5000 msg/s       | 10000 msg/s      | 25000 msg/s      |
| **Workflow Executions**   | 100 exec/s       | 200 exec/s       | 500 exec/s       |

### Resource Usage Targets

| Resource         | Normal      | Peak        | Limit       |
| ---------------- | ----------- | ----------- | ----------- |
| **CPU Usage**    | < 60%       | < 80%       | < 90%       |
| **Memory Usage** | < 2GB       | < 4GB       | < 8GB       |
| **Disk I/O**     | < 1000 IOPS | < 2000 IOPS | < 5000 IOPS |
| **Network I/O**  | < 100 Mbps  | < 200 Mbps  | < 500 Mbps  |

## Load Testing with Locust

### Locust Configuration

**File**: `tests/performance/locustfile.py`

```python
from locust import HttpUser, task, between
import random
import json
import time

class AIaaSUser(HttpUser):
    """Simulate user behavior for AIaaS platform."""

    wait_time = between(1, 3)

    def on_start(self):
        """Setup user session."""
        self.tenant_id = f"tenant-{random.randint(1000, 9999)}"
        self.session_id = f"session-{random.randint(10000, 99999)}"
        self.headers = {
            "Content-Type": "application/json",
            "X-Tenant-ID": self.tenant_id,
            "Authorization": f"Bearer {self.get_auth_token()}"
        }

    def get_auth_token(self):
        """Get authentication token."""
        response = self.client.post("/api/v1/auth/login", json={
            "username": "test_user",
            "password": "test_password"
        })
        return response.json().get("token")

    @task(5)
    def chat_message(self):
        """Send chat message (most common operation)."""
        payload = {
            "message": f"Hello, I need help with my order #{random.randint(1000, 9999)}",
            "session_id": self.session_id,
            "metadata": {
                "priority": random.choice(["low", "medium", "high"]),
                "category": random.choice(["support", "sales", "billing"])
            }
        }

        with self.client.post(
            "/api/v1/chat/message",
            json=payload,
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(3)
    def get_agents(self):
        """Get available agents."""
        with self.client.get(
            "/api/v1/agents",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(2)
    def get_conversation_history(self):
        """Get conversation history."""
        with self.client.get(
            f"/api/v1/chat/history/{self.session_id}",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(1)
    def create_workflow(self):
        """Create new workflow."""
        payload = {
            "name": f"test_workflow_{random.randint(1000, 9999)}",
            "description": "Test workflow for load testing",
            "nodes": [
                {"id": "start", "type": "input", "name": "Start"},
                {"id": "process", "type": "llm", "name": "Process"},
                {"id": "end", "type": "output", "name": "End"}
            ],
            "edges": [
                {"from": "start", "to": "process"},
                {"from": "process", "to": "end"}
            ]
        }

        with self.client.post(
            "/api/v1/workflows",
            json=payload,
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 201:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(1)
    def get_analytics(self):
        """Get analytics data."""
        with self.client.get(
            f"/api/v1/analytics/tenant/{self.tenant_id}",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")


class HighLoadUser(HttpUser):
    """Simulate high-load user behavior."""

    wait_time = between(0.1, 0.5)

    def on_start(self):
        """Setup high-load session."""
        self.tenant_id = f"highload-{random.randint(1000, 9999)}"
        self.headers = {
            "Content-Type": "application/json",
            "X-Tenant-ID": self.tenant_id
        }

    @task(10)
    def rapid_chat_messages(self):
        """Send rapid chat messages."""
        payload = {
            "message": f"Rapid message {random.randint(1, 10000)}",
            "session_id": f"session-{random.randint(10000, 99999)}"
        }

        with self.client.post(
            "/api/v1/chat/message",
            json=payload,
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")
```

### Locust Test Execution

```bash
# Basic load test
locust -f tests/performance/locustfile.py \
  --host=http://localhost:8000 \
  --users=100 \
  --spawn-rate=10 \
  --run-time=5m \
  --headless \
  --html=load-test-report.html

# High load test
locust -f tests/performance/locustfile.py \
  --host=http://localhost:8000 \
  --users=1000 \
  --spawn-rate=50 \
  --run-time=10m \
  --headless \
  --html=high-load-test-report.html

# Stress test
locust -f tests/performance/locustfile.py \
  --host=http://localhost:8000 \
  --users=2000 \
  --spawn-rate=100 \
  --run-time=30m \
  --headless \
  --html=stress-test-report.html
```

## Performance Benchmarking

### Router Performance Tests

```python
import pytest
import asyncio
import time
import statistics
from concurrent.futures import ThreadPoolExecutor

class TestRouterPerformance:
    """Test router performance benchmarks."""

    @pytest.mark.asyncio
    async def test_router_decision_latency(self, router_v2, mock_redis):
        """Test router decision latency meets p50 < 50ms requirement."""
        request = {
            "message": "I need help with my order",
            "tenant_id": "test_tenant",
            "user_id": "test_user"
        }

        # Warm up
        for _ in range(10):
            await router_v2.route_request(request)

        # Measure latency
        latencies = []
        for _ in range(100):
            start_time = time.time()
            result = await router_v2.route_request(request)
            latency = (time.time() - start_time) * 1000
            latencies.append(latency)

        # Calculate percentiles
        p50 = statistics.median(latencies)
        p95 = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        p99 = statistics.quantiles(latencies, n=100)[98]  # 99th percentile

        assert p50 < 50, f"p50 latency {p50:.2f}ms exceeds 50ms target"
        assert p95 < 100, f"p95 latency {p95:.2f}ms exceeds 100ms target"
        assert p99 < 200, f"p99 latency {p99:.2f}ms exceeds 200ms target"

    @pytest.mark.asyncio
    async def test_router_throughput(self, router_v2, mock_redis):
        """Test router throughput meets 1000 req/s requirement."""
        request = {
            "message": "Test message",
            "tenant_id": "test_tenant",
            "user_id": "test_user"
        }

        # Measure throughput
        start_time = time.time()
        tasks = [router_v2.route_request(request) for _ in range(1000)]
        results = await asyncio.gather(*tasks)
        end_time = time.time()

        throughput = 1000 / (end_time - start_time)

        assert throughput > 1000, f"Throughput {throughput:.2f} req/s below 1000 req/s target"
        assert len(results) == 1000, "Not all requests completed"

    @pytest.mark.asyncio
    async def test_router_concurrent_requests(self, router_v2, mock_redis):
        """Test router performance under concurrent load."""
        request = {
            "message": "Concurrent test message",
            "tenant_id": "test_tenant",
            "user_id": "test_user"
        }

        # Test with increasing concurrency
        for concurrency in [10, 50, 100, 200]:
            start_time = time.time()
            tasks = [router_v2.route_request(request) for _ in range(concurrency)]
            results = await asyncio.gather(*tasks)
            end_time = time.time()

            avg_latency = (end_time - start_time) * 1000 / concurrency

            assert avg_latency < 100, f"Avg latency {avg_latency:.2f}ms too high for {concurrency} concurrent requests"
            assert len(results) == concurrency, f"Not all {concurrency} requests completed"
```

### Tool Execution Performance Tests

```python
class TestToolPerformance:
    """Test tool execution performance benchmarks."""

    @pytest.mark.asyncio
    async def test_payment_adapter_performance(self, payment_adapter, mock_redis):
        """Test payment adapter performance."""
        request = PaymentRequest(
            amount=100.0,
            currency="USD",
            customer_id="test_customer",
            payment_method_id="pm_test",
            description="Performance test payment"
        )

        # Measure execution time
        start_time = time.time()
        result = await payment_adapter.process_payment(request)
        execution_time = (time.time() - start_time) * 1000

        assert execution_time < 500, f"Payment processing {execution_time:.2f}ms exceeds 500ms target"
        assert result.status in [PaymentStatus.COMPLETED, PaymentStatus.FAILED]

    @pytest.mark.asyncio
    async def test_email_adapter_performance(self, email_adapter, mock_redis):
        """Test email adapter performance."""
        message = EmailMessage(
            to="test@example.com",
            subject="Performance Test",
            body="This is a performance test email",
            from_email="noreply@example.com"
        )

        # Measure execution time
        start_time = time.time()
        result = await email_adapter.send_email(message)
        execution_time = (time.time() - start_time) * 1000

        assert execution_time < 1000, f"Email sending {execution_time:.2f}ms exceeds 1000ms target"
        assert result.success in [True, False]
```

## Scalability Testing

### Horizontal Scaling Tests

```python
class TestHorizontalScaling:
    """Test horizontal scaling capabilities."""

    @pytest.mark.asyncio
    async def test_router_scaling(self, router_instances):
        """Test router scaling with multiple instances."""
        request = {
            "message": "Scaling test message",
            "tenant_id": "test_tenant",
            "user_id": "test_user"
        }

        # Test with different numbers of router instances
        for instance_count in [1, 2, 4, 8]:
            routers = router_instances[:instance_count]

            # Distribute load across instances
            tasks = []
            for i in range(100):
                router = routers[i % len(routers)]
                tasks.append(router.route_request(request))

            start_time = time.time()
            results = await asyncio.gather(*tasks)
            end_time = time.time()

            throughput = 100 / (end_time - start_time)
            avg_latency = (end_time - start_time) * 1000 / 100

            # Throughput should scale linearly with instances
            expected_throughput = 100 * instance_count
            assert throughput >= expected_throughput * 0.8, f"Throughput {throughput:.2f} req/s below expected {expected_throughput * 0.8:.2f} req/s"

            # Latency should remain stable
            assert avg_latency < 100, f"Avg latency {avg_latency:.2f}ms too high with {instance_count} instances"

    @pytest.mark.asyncio
    async def test_database_scaling(self, db_instances):
        """Test database scaling with multiple instances."""
        query = "SELECT COUNT(*) FROM users WHERE tenant_id = %s"
        tenant_id = "test_tenant"

        # Test with different numbers of database instances
        for instance_count in [1, 2, 4]:
            dbs = db_instances[:instance_count]

            # Distribute queries across instances
            tasks = []
            for i in range(1000):
                db = dbs[i % len(dbs)]
                tasks.append(db.execute(query, (tenant_id,)))

            start_time = time.time()
            results = await asyncio.gather(*tasks)
            end_time = time.time()

            throughput = 1000 / (end_time - start_time)
            avg_latency = (end_time - start_time) * 1000 / 1000

            # Throughput should scale with instances
            expected_throughput = 1000 * instance_count
            assert throughput >= expected_throughput * 0.8, f"DB throughput {throughput:.2f} qps below expected {expected_throughput * 0.8:.2f} qps"

            # Latency should remain stable
            assert avg_latency < 50, f"DB latency {avg_latency:.2f}ms too high with {instance_count} instances"
```

### Vertical Scaling Tests

```python
class TestVerticalScaling:
    """Test vertical scaling capabilities."""

    @pytest.mark.asyncio
    async def test_memory_scaling(self, router_v2, mock_redis):
        """Test router performance with different memory allocations."""
        request = {
            "message": "Memory scaling test message",
            "tenant_id": "test_tenant",
            "user_id": "test_user"
        }

        # Test with different memory limits
        memory_limits = [512, 1024, 2048, 4096]  # MB

        for memory_limit in memory_limits:
            # Simulate memory limit
            router_v2.set_memory_limit(memory_limit)

            # Measure performance
            start_time = time.time()
            tasks = [router_v2.route_request(request) for _ in range(100)]
            results = await asyncio.gather(*tasks)
            end_time = time.time()

            avg_latency = (end_time - start_time) * 1000 / 100

            # Performance should improve with more memory
            assert avg_latency < 100, f"Latency {avg_latency:.2f}ms too high with {memory_limit}MB memory"
            assert len(results) == 100, "Not all requests completed"

    @pytest.mark.asyncio
    async def test_cpu_scaling(self, router_v2, mock_redis):
        """Test router performance with different CPU allocations."""
        request = {
            "message": "CPU scaling test message",
            "tenant_id": "test_tenant",
            "user_id": "test_user"
        }

        # Test with different CPU limits
        cpu_limits = [0.5, 1.0, 2.0, 4.0]  # CPU cores

        for cpu_limit in cpu_limits:
            # Simulate CPU limit
            router_v2.set_cpu_limit(cpu_limit)

            # Measure performance
            start_time = time.time()
            tasks = [router_v2.route_request(request) for _ in range(100)]
            results = await asyncio.gather(*tasks)
            end_time = time.time()

            avg_latency = (end_time - start_time) * 1000 / 100

            # Performance should improve with more CPU
            assert avg_latency < 100, f"Latency {avg_latency:.2f}ms too high with {cpu_limit} CPU cores"
            assert len(results) == 100, "Not all requests completed"
```

## Performance Monitoring

### Real-time Performance Metrics

```python
class PerformanceMonitor:
    """Real-time performance monitoring."""

    def __init__(self):
        self.metrics = {
            "latency": [],
            "throughput": [],
            "error_rate": [],
            "cpu_usage": [],
            "memory_usage": []
        }

    def record_latency(self, latency_ms):
        """Record latency metric."""
        self.metrics["latency"].append(latency_ms)

        # Keep only last 1000 measurements
        if len(self.metrics["latency"]) > 1000:
            self.metrics["latency"] = self.metrics["latency"][-1000:]

    def record_throughput(self, requests_per_second):
        """Record throughput metric."""
        self.metrics["throughput"].append(requests_per_second)

        if len(self.metrics["throughput"]) > 1000:
            self.metrics["throughput"] = self.metrics["throughput"][-1000:]

    def get_performance_summary(self):
        """Get performance summary."""
        if not self.metrics["latency"]:
            return {}

        return {
            "latency": {
                "p50": statistics.median(self.metrics["latency"]),
                "p95": statistics.quantiles(self.metrics["latency"], n=20)[18],
                "p99": statistics.quantiles(self.metrics["latency"], n=100)[98],
                "avg": statistics.mean(self.metrics["latency"])
            },
            "throughput": {
                "avg": statistics.mean(self.metrics["throughput"]),
                "max": max(self.metrics["throughput"]),
                "min": min(self.metrics["throughput"])
            },
            "error_rate": {
                "current": self.metrics["error_rate"][-1] if self.metrics["error_rate"] else 0,
                "avg": statistics.mean(self.metrics["error_rate"]) if self.metrics["error_rate"] else 0
            }
        }
```

### Performance Alerting

```python
class PerformanceAlerts:
    """Performance alerting system."""

    def __init__(self):
        self.thresholds = {
            "latency_p50": 50,
            "latency_p95": 100,
            "latency_p99": 200,
            "error_rate": 0.05,
            "cpu_usage": 80,
            "memory_usage": 80
        }

    def check_alerts(self, metrics):
        """Check for performance alerts."""
        alerts = []

        if metrics["latency"]["p50"] > self.thresholds["latency_p50"]:
            alerts.append({
                "type": "latency_p50_high",
                "message": f"p50 latency {metrics['latency']['p50']:.2f}ms exceeds {self.thresholds['latency_p50']}ms threshold",
                "severity": "warning"
            })

        if metrics["latency"]["p95"] > self.thresholds["latency_p95"]:
            alerts.append({
                "type": "latency_p95_high",
                "message": f"p95 latency {metrics['latency']['p95']:.2f}ms exceeds {self.thresholds['latency_p95']}ms threshold",
                "severity": "critical"
            })

        if metrics["error_rate"]["current"] > self.thresholds["error_rate"]:
            alerts.append({
                "type": "error_rate_high",
                "message": f"Error rate {metrics['error_rate']['current']:.2%} exceeds {self.thresholds['error_rate']:.2%} threshold",
                "severity": "critical"
            })

        return alerts
```

## Performance Regression Testing

### Automated Performance Regression Detection

```python
class PerformanceRegressionTest:
    """Performance regression testing."""

    def __init__(self):
        self.baseline_metrics = self.load_baseline_metrics()

    def load_baseline_metrics(self):
        """Load baseline performance metrics."""
        try:
            with open("performance_baseline.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def save_baseline_metrics(self, metrics):
        """Save baseline performance metrics."""
        with open("performance_baseline.json", "w") as f:
            json.dump(metrics, f, indent=2)

    def detect_regression(self, current_metrics):
        """Detect performance regression."""
        if not self.baseline_metrics:
            return {"regression": False, "message": "No baseline metrics available"}

        regressions = []

        # Check latency regression
        if "latency" in current_metrics and "latency" in self.baseline_metrics:
            baseline_p50 = self.baseline_metrics["latency"]["p50"]
            current_p50 = current_metrics["latency"]["p50"]

            if current_p50 > baseline_p50 * 1.2:  # 20% regression threshold
                regressions.append({
                    "metric": "latency_p50",
                    "baseline": baseline_p50,
                    "current": current_p50,
                    "regression": (current_p50 - baseline_p50) / baseline_p50 * 100
                })

        # Check throughput regression
        if "throughput" in current_metrics and "throughput" in self.baseline_metrics:
            baseline_throughput = self.baseline_metrics["throughput"]["avg"]
            current_throughput = current_metrics["throughput"]["avg"]

            if current_throughput < baseline_throughput * 0.8:  # 20% regression threshold
                regressions.append({
                    "metric": "throughput",
                    "baseline": baseline_throughput,
                    "current": current_throughput,
                    "regression": (baseline_throughput - current_throughput) / baseline_throughput * 100
                })

        return {
            "regression": len(regressions) > 0,
            "regressions": regressions,
            "message": f"Found {len(regressions)} performance regressions" if regressions else "No performance regressions detected"
        }
```

### Performance Test Automation

```python
@pytest.mark.performance
class TestPerformanceRegression:
    """Performance regression tests."""

    @pytest.mark.asyncio
    async def test_router_performance_regression(self, router_v2, mock_redis):
        """Test router performance regression."""
        request = {
            "message": "Performance regression test",
            "tenant_id": "test_tenant",
            "user_id": "test_user"
        }

        # Measure current performance
        latencies = []
        for _ in range(100):
            start_time = time.time()
            result = await router_v2.route_request(request)
            latency = (time.time() - start_time) * 1000
            latencies.append(latency)

        current_metrics = {
            "latency": {
                "p50": statistics.median(latencies),
                "p95": statistics.quantiles(latencies, n=20)[18],
                "p99": statistics.quantiles(latencies, n=100)[98]
            }
        }

        # Check for regression
        regression_test = PerformanceRegressionTest()
        regression_result = regression_test.detect_regression(current_metrics)

        if regression_result["regression"]:
            pytest.fail(f"Performance regression detected: {regression_result['message']}")

        # Update baseline if no regression
        regression_test.save_baseline_metrics(current_metrics)
```

## Best Practices

### 1. Test Design

- **Realistic scenarios**: Use realistic user behavior patterns
- **Gradual load increase**: Start with low load and gradually increase
- **Long duration tests**: Run tests long enough to detect memory leaks
- **Resource monitoring**: Monitor CPU, memory, and I/O during tests

### 2. Test Execution

- **Isolated environments**: Use dedicated test environments
- **Consistent conditions**: Ensure consistent test conditions
- **Baseline establishment**: Establish performance baselines
- **Regular execution**: Run performance tests regularly

### 3. Result Analysis

- **Percentile analysis**: Focus on p95 and p99 percentiles
- **Trend analysis**: Monitor performance trends over time
- **Regression detection**: Automatically detect performance regressions
- **Root cause analysis**: Investigate performance issues thoroughly

### 4. Monitoring

- **Real-time monitoring**: Monitor performance in real-time
- **Alerting**: Set up alerts for performance issues
- **Dashboard**: Create performance dashboards
- **Reporting**: Generate regular performance reports

### 5. Optimization

- **Profiling**: Use profiling tools to identify bottlenecks
- **Caching**: Implement appropriate caching strategies
- **Database optimization**: Optimize database queries and indexes
- **Code optimization**: Optimize critical code paths

This comprehensive performance testing strategy ensures the Multi-AI-Agent platform meets performance requirements and maintains optimal performance over time.
