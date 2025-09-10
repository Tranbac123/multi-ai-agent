# Load Testing Suite

This directory contains load testing scripts for the AIaaS platform using K6 and Locust.

## 🎯 Overview

The load testing suite provides comprehensive performance testing for:
- **WebSocket connections** - Real-time chat functionality
- **REST API endpoints** - All service endpoints
- **Billing system** - Usage tracking and plan enforcement
- **Analytics service** - KPI metrics and dashboards

## 📁 Files

- `k6_websocket_test.js` - K6 WebSocket load test
- `k6_api_test.js` - K6 REST API load test
- `locust_test.py` - Locust comprehensive load test
- `README.md` - This documentation

## 🚀 Quick Start

### Prerequisites

```bash
# Install K6
curl https://github.com/grafana/k6/releases/download/v0.47.0/k6-v0.47.0-linux-amd64.tar.gz -L | tar xvz --strip-components 1

# Install Locust
pip install locust
```

### Running Tests

#### K6 WebSocket Test

```bash
# Run WebSocket load test
k6 run load/k6_websocket_test.js

# Run with custom parameters
k6 run --vus 50 --duration 5m load/k6_websocket_test.js
```

#### K6 API Test

```bash
# Run API load test
k6 run load/k6_api_test.js

# Run with custom parameters
k6 run --vus 100 --duration 10m load/k6_api_test.js
```

#### Locust Test

```bash
# Run Locust test
locust -f load/locust_test.py --host=http://localhost:8000

# Run with custom parameters
locust -f load/locust_test.py --host=http://localhost:8000 --users 200 --spawn-rate 10 --run-time 5m
```

## 📊 Test Scenarios

### WebSocket Load Test

**Purpose**: Test real-time chat functionality under load

**Configuration**:
- **Stages**: 10 → 50 → 100 users over 21 minutes
- **Thresholds**:
  - Connection success rate > 95%
  - Message success rate > 90%
  - Connection duration p95 < 1000ms
  - Message latency p95 < 500ms
  - Errors < 100

**Test Flow**:
1. Establish WebSocket connection
2. Send initial message
3. Listen for agent response
4. Send follow-up message
5. Keep connection alive for 30 seconds

### API Load Test

**Purpose**: Test REST API endpoints under load

**Configuration**:
- **Stages**: 20 → 100 → 200 users over 21 minutes
- **Thresholds**:
  - API success rate > 95%
  - Response time p95 < 1000ms
  - Errors < 50

**Endpoints Tested**:
- `/chat/messages` - Chat processing
- `/healthz` - Health checks
- `/analytics/kpi` - Analytics data
- `/billing/usage` - Billing information
- `/auth/status` - Authentication status

### Locust Comprehensive Test

**Purpose**: Comprehensive load testing with multiple user types

**User Types**:
- **Normal Users**: Standard load testing
- **High Load Users**: Stress testing with rapid requests

**Test Scenarios**:
- Chat endpoint testing
- Health check monitoring
- Analytics data retrieval
- Billing information access
- Authentication validation
- WebSocket endpoint testing

## 📈 Performance Baselines

### WebSocket Performance

| Metric | Target | Baseline |
|--------|--------|----------|
| Connection Success Rate | > 95% | 98.5% |
| Message Success Rate | > 90% | 94.2% |
| Connection Duration (p95) | < 1000ms | 450ms |
| Message Latency (p95) | < 500ms | 280ms |
| Concurrent Connections | 100+ | 150+ |

### API Performance

| Metric | Target | Baseline |
|--------|--------|----------|
| API Success Rate | > 95% | 97.8% |
| Response Time (p95) | < 1000ms | 650ms |
| Response Time (p50) | < 500ms | 320ms |
| Throughput | 100+ RPS | 150+ RPS |
| Error Rate | < 5% | 2.2% |

### Billing Performance

| Metric | Target | Baseline |
|--------|--------|----------|
| Usage Tracking Latency | < 100ms | 45ms |
| Invoice Generation | < 2s | 1.2s |
| Plan Enforcement | < 50ms | 25ms |
| Webhook Processing | < 200ms | 120ms |

## 🔧 Configuration

### Environment Variables

```bash
# Test configuration
TEST_BASE_URL=http://localhost:8000
TEST_TENANT_ID=tenant_001
TEST_USER_ID=user_001

# Load test parameters
K6_VUS=100
K6_DURATION=10m
LOCUST_USERS=200
LOCUST_SPAWN_RATE=10
```

### Custom Test Data

Modify the test data arrays in the scripts:

```javascript
// K6 test data
const testMessages = [
  "Hello, I need help with my order",
  "What are your business hours?",
  // Add more test messages
];

const tenants = [
  'tenant_001',
  'tenant_002',
  // Add more tenant IDs
];
```

```python
# Locust test data
TEST_MESSAGES = [
    "Hello, I need help with my order",
    "What are your business hours?",
    # Add more test messages
]

TENANTS = [
    'tenant_001',
    'tenant_002',
    # Add more tenant IDs
]
```

## 📊 Results Analysis

### K6 Results

K6 generates detailed reports including:
- **Metrics**: Success rates, response times, error counts
- **Thresholds**: Pass/fail status for performance criteria
- **Trends**: Performance over time
- **Custom Metrics**: WebSocket-specific metrics

### Locust Results

Locust provides:
- **Real-time Statistics**: Live performance metrics
- **Charts**: Response time and request rate graphs
- **CSV Reports**: Detailed performance data
- **HTML Reports**: Comprehensive test results

### Performance Monitoring

Monitor these key metrics during tests:
- **Response Times**: p50, p95, p99 percentiles
- **Success Rates**: Overall and per-endpoint
- **Error Rates**: Failed requests and error types
- **Throughput**: Requests per second
- **Resource Usage**: CPU, memory, database connections

## 🚨 Troubleshooting

### Common Issues

1. **Connection Refused**
   ```bash
   # Check if services are running
   curl http://localhost:8000/healthz
   ```

2. **Rate Limiting**
   ```bash
   # Reduce load or increase rate limits
   k6 run --vus 10 load/k6_api_test.js
   ```

3. **WebSocket Connection Failures**
   ```bash
   # Check WebSocket endpoint
   curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Key: test" -H "Sec-WebSocket-Version: 13" http://localhost:8000/ws/chat
   ```

4. **High Error Rates**
   ```bash
   # Check service logs
   docker-compose logs -f api-gateway
   ```

### Performance Optimization

1. **Database Optimization**
   - Check connection pool settings
   - Monitor query performance
   - Optimize indexes

2. **Redis Optimization**
   - Monitor memory usage
   - Check connection limits
   - Optimize cache strategies

3. **Service Optimization**
   - Monitor CPU and memory usage
   - Check for memory leaks
   - Optimize code paths

## 📝 Best Practices

### Test Design

1. **Start Small**: Begin with low load and gradually increase
2. **Realistic Data**: Use production-like test data
3. **Multiple Scenarios**: Test different user behaviors
4. **Long Duration**: Run tests for sufficient time to identify issues

### Test Execution

1. **Baseline First**: Establish performance baselines
2. **Isolated Environment**: Use dedicated test environment
3. **Monitor Resources**: Watch system resources during tests
4. **Document Results**: Record all test results and configurations

### Analysis

1. **Compare Metrics**: Compare against baselines and targets
2. **Identify Bottlenecks**: Find performance limiting factors
3. **Root Cause Analysis**: Investigate performance issues
4. **Continuous Improvement**: Iterate on performance optimizations

## 🎯 Next Steps

1. **Automated Testing**: Integrate load tests into CI/CD pipeline
2. **Performance Regression**: Set up automated performance monitoring
3. **Capacity Planning**: Use results for infrastructure planning
4. **Optimization**: Continuously improve performance based on results

---

For more information, see the main project documentation and implementation guides.
