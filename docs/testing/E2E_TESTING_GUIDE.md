# 🧪 E2E Testing Guide

## Overview

This guide covers End-to-End (E2E) testing for the AI Chatbot microservices system. E2E tests verify complete user workflows and service integrations from frontend to backend.

## 🎯 E2E Test Categories

### 1. **User Workflow Tests** (`test_user_workflows.py`)

- Complete user journeys across all services
- Chatbot user experience
- Admin portal workflows
- Web frontend user registration
- Data retrieval workflows
- Tools service integration
- Model gateway integration
- Configuration management

### 2. **Service Integration Tests** (`test_service_integration.py`)

- API Gateway to all backend services communication
- Frontend to API Gateway integration
- Data flow through service chains
- Error handling across services
- Service discovery and health checks
- Concurrent request handling
- Configuration consistency

### 3. **Performance E2E Tests** (`test_performance_e2e.py`)

- Response time benchmarks
- Concurrent load performance
- Memory usage stability
- End-to-end latency testing
- Error recovery performance

## 🚀 Running E2E Tests

### Quick Start

```bash
# Run all E2E tests
./scripts/run_e2e_tests.sh

# Run quick E2E tests (excluding slow performance tests)
./scripts/run_e2e_quick.sh
```

### Individual Test Suites

```bash
# User workflow tests only
pytest tests/e2e/test_user_workflows.py -v

# Service integration tests only
pytest tests/e2e/test_service_integration.py -v

# Performance tests only
pytest tests/e2e/test_performance_e2e.py -v
```

### Specific Test Categories

```bash
# Run only user workflow tests
pytest tests/e2e/test_user_workflows.py -v -m user_workflow

# Run only integration tests
pytest tests/e2e/test_service_integration.py -v -m integration

# Run only performance tests (excluding slow ones)
pytest tests/e2e/test_performance_e2e.py -v -m "performance and not slow"
```

## 📋 Prerequisites

### 1. Services Running

```bash
# Start all services
docker-compose -f docker-compose.local.yml up -d

# Verify services are running
docker-compose -f docker-compose.local.yml ps
```

### 2. Dependencies Installed

```bash
# Install E2E test dependencies
pip install -r tests/e2e/requirements.txt
```

## 🧪 Test Scenarios

### User Workflow Scenarios

#### 1. Chatbot User Journey

```
1. Access AI Chatbot Frontend (localhost:3001)
2. Initialize chat session
3. Send chat message through API Gateway
4. Verify response structure
```

#### 2. Admin Portal Workflow

```
1. Access Admin Portal (localhost:8099)
2. Check health endpoint
3. Access configuration through API Gateway
4. Verify admin functionality
```

#### 3. Web Frontend Registration

```
1. Access Web Frontend (localhost:3000)
2. Test frontend accessibility
3. Test API endpoints that frontend uses
4. Verify user registration flow
```

#### 4. Data Retrieval Workflow

```
1. Test Retrieval Service health (localhost:8081)
2. Test search functionality
3. Verify search results
4. Test data indexing
```

### Service Integration Scenarios

#### 1. API Gateway Communication

```
1. Verify API Gateway can reach all backend services
2. Test proxy functionality
3. Verify error handling
4. Test load balancing
```

#### 2. Frontend Integration

```
1. Test AI Chatbot → API Gateway
2. Test Admin Portal → API Gateway
3. Test Web Frontend → API Gateway
4. Verify all frontend-backend communication
```

#### 3. Data Flow Testing

```
1. User request through API Gateway
2. Routing to appropriate services
3. Data processing and response
4. Response back to user
```

### Performance Scenarios

#### 1. Response Time Benchmarks

```
- API Gateway: < 1000ms
- Model Gateway: < 2000ms
- Config Service: < 500ms
- Retrieval Service: < 1500ms
- Tools Service: < 1000ms
- Router Service: < 1000ms
- Policy Adapter: < 1000ms
- Admin Portal: < 1000ms
```

#### 2. Concurrent Load Testing

```
- 20 concurrent requests per service
- Success rate: ≥ 80%
- Response time degradation: < 50%
```

#### 3. End-to-End Latency

```
- Chat Workflow: < 10 seconds
- Admin Workflow: < 5 seconds
- Search Workflow: < 8 seconds
```

## 📊 Test Results

### HTML Reports

E2E tests generate detailed HTML reports:

- `test-results/e2e/complete-e2e-report.html` - Complete test suite
- `test-results/e2e/user-workflows-report.html` - User workflow tests
- `test-results/e2e/service-integration-report.html` - Integration tests
- `test-results/e2e/performance-report.html` - Performance tests

### XML Results

JUnit XML format for CI/CD integration:

- `test-results/e2e/complete-e2e-results.xml`
- Individual test suite XML files

### Console Output

Real-time test progress and results in terminal.

## 🔧 Configuration

### Service URLs

E2E tests use these default service URLs:

```python
service_urls = {
    "api_gateway": "http://localhost:8000",
    "model_gateway": "http://localhost:8080",
    "config_service": "http://localhost:8090",
    "policy_adapter": "http://localhost:8091",
    "retrieval_service": "http://localhost:8081",
    "tools_service": "http://localhost:8082",
    "router_service": "http://localhost:8083",
    "admin_portal": "http://localhost:8099",
    "web_frontend": "http://localhost:3000",
    "ai_chatbot": "http://localhost:3001",
}
```

### Test Data

Default test data includes:

- Test user information
- Chat message samples
- Configuration data
- Session information

## 🐛 Troubleshooting

### Common Issues

#### 1. Services Not Running

```bash
# Check service status
docker-compose -f docker-compose.local.yml ps

# Start services
docker-compose -f docker-compose.local.yml up -d

# Check logs
docker-compose -f docker-compose.local.yml logs -f
```

#### 2. Connection Timeouts

```bash
# Wait for services to be ready
sleep 30

# Check individual service health
curl http://localhost:8000/healthz  # API Gateway
curl http://localhost:8080/healthz  # Model Gateway
curl http://localhost:8090/healthz  # Config Service
```

#### 3. Test Failures

```bash
# Run tests with verbose output
pytest tests/e2e/test_user_workflows.py -v -s

# Run specific test
pytest tests/e2e/test_user_workflows.py::TestUserWorkflows::test_chatbot_user_journey -v -s

# Check test logs
pytest tests/e2e/ --capture=no
```

#### 4. Performance Test Issues

```bash
# Run without slow tests
pytest tests/e2e/test_performance_e2e.py -v -m "not slow"

# Increase timeout
pytest tests/e2e/test_performance_e2e.py -v --timeout=600
```

## 📈 Continuous Integration

### GitHub Actions Integration

```yaml
- name: Run E2E Tests
  run: |
    docker-compose -f docker-compose.local.yml up -d
    sleep 30
    ./scripts/run_e2e_tests.sh
```

### Jenkins Integration

```groovy
stage('E2E Tests') {
    steps {
        sh 'docker-compose -f docker-compose.local.yml up -d'
        sh 'sleep 30'
        sh './scripts/run_e2e_tests.sh'
    }
    post {
        always {
            publishHTML([
                allowMissing: false,
                alwaysLinkToLastBuild: true,
                keepAll: true,
                reportDir: 'test-results/e2e',
                reportFiles: 'complete-e2e-report.html',
                reportName: 'E2E Test Report'
            ])
        }
    }
}
```

## 🎯 Best Practices

### 1. Test Organization

- Group related tests in classes
- Use descriptive test names
- Include setup and teardown
- Use fixtures for common data

### 2. Error Handling

- Test both success and failure scenarios
- Verify error messages and codes
- Test timeout handling
- Test network failures

### 3. Performance Testing

- Set realistic performance expectations
- Test under various load conditions
- Monitor resource usage
- Test recovery scenarios

### 4. Maintenance

- Keep tests up to date with service changes
- Regular review of test results
- Update test data as needed
- Monitor test execution time

## 📚 Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [HTTPX Documentation](https://www.python-httpx.org/)
- [AsyncIO Testing](https://docs.python.org/3/library/asyncio-testing.html)
- [Docker Compose Testing](https://docs.docker.com/compose/testing/)

---

**🎉 Happy Testing!** Your E2E test suite ensures your AI chatbot system works end-to-end for real users.
