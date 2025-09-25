# Getting Started with Multi-AI-Agent Testing

## Quick Start Guide

This guide will help you get started with testing the Multi-AI-Agent platform quickly and effectively.

## Prerequisites

### System Requirements

- Python 3.11+
- Docker and Docker Compose
- Git
- At least 4GB RAM
- At least 2GB disk space

### Required Services (for Integration Tests)

- PostgreSQL 15+
- Redis 7+
- NATS 2.9+

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/multi-ai-agent.git
cd multi-ai-agent
```

### 2. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install additional testing dependencies
pip install pytest pytest-asyncio hypothesis httpx redis nats-py asyncpg locust
```

### 3. Start Required Services

```bash
# Start services using Docker Compose
docker-compose -f docker-compose.test.yml up -d

# Or start services individually
docker run -d --name postgres \
  -e POSTGRES_DB=test_db \
  -e POSTGRES_USER=test_user \
  -e POSTGRES_PASSWORD=test_pass \
  -p 5432:5432 postgres:15

docker run -d --name redis \
  -p 6379:6379 redis:7

docker run -d --name nats \
  -p 4222:4222 nats:2.9
```

### 4. Verify Installation

```bash
# Check if services are running
docker ps

# Test database connection
psql -h localhost -U test_user -d test_db -c "SELECT 1"

# Test Redis connection
redis-cli -h localhost -p 6379 ping

# Test NATS connection
nats-server --help
```

## Running Tests

### Basic Test Execution

#### 1. Unit Tests (Recommended for Development)

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run specific test file
pytest tests/unit/test_tools.py -v

# Run specific test class
pytest tests/unit/test_tools.py::TestBaseAdapter -v

# Run specific test method
pytest tests/unit/test_tools.py::TestBaseAdapter::test_retry_with_exponential_backoff -v
```

#### 2. Integration Tests

```bash
# Run all integration tests
pytest tests/integration/ -v

# Run specific integration test
pytest tests/integration/test_workflow_execution.py -v
```

#### 3. End-to-End Tests

```bash
# Run E2E tests
pytest tests/e2e/ -v
```

#### 4. Performance Tests

```bash
# Run performance tests
pytest tests/performance/ -v

# Run load tests with Locust
locust -f tests/performance/locustfile.py \
  --host=http://localhost:8000 \
  --users=100 \
  --spawn-rate=10 \
  --run-time=5m \
  --headless \
  --html=load-test-report.html
```

### Advanced Test Execution

#### 1. Run Tests with Coverage

```bash
# Run unit tests with coverage
pytest tests/unit/ --cov=libs --cov=apps --cov-report=html --cov-report=term

# View coverage report
open htmlcov/index.html
```

#### 2. Run Tests in Parallel

```bash
# Install pytest-xdist for parallel execution
pip install pytest-xdist

# Run tests in parallel
pytest tests/unit/ -n 4  # Use 4 workers
```

#### 3. Run Tests with Specific Markers

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only slow tests
pytest -m slow

# Run only live API tests
pytest -m live
```

#### 4. Run Tests with Timeout

```bash
# Install pytest-timeout
pip install pytest-timeout

# Run tests with timeout
pytest tests/unit/ --timeout=300  # 5 minute timeout
```

## Test Configuration

### Environment Variables

```bash
# Set test mode
export TEST_MODE=mock  # or live_smoke

# Set service URLs
export API_GATEWAY_URL=http://localhost:8000
export ORCHESTRATOR_URL=http://localhost:8001
export ROUTER_URL=http://localhost:8002

# Set database URLs
export POSTGRES_URL=postgresql://test_user:test_pass@localhost:5432/test_db
export REDIS_URL=redis://localhost:6379/15
export NATS_URL=nats://localhost:4222

# Set LLM API keys (for live_smoke mode)
export OPENAI_API_KEY=your_openai_api_key_here
export ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

### Pytest Configuration

Create `pytest.ini` in the project root:

```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    -v
    --strict-markers
    --disable-warnings
    --tb=short
markers =
    unit: Unit tests
    contract: Contract tests
    integration: Integration tests
    e2e: End-to-end tests
    chaos: Chaos engineering tests
    eval: Evaluation tests
    slow: Slow tests
    live: Live API tests
    mock: Mock tests
```

## Common Test Scenarios

### 1. Testing Tool Adapters

```python
# Test payment adapter
pytest tests/unit/test_tools.py::TestPaymentAdapter::test_process_payment_success -v

# Test email adapter
pytest tests/unit/test_tools.py::TestEmailAdapter::test_send_email_success -v

# Test CRM adapter
pytest tests/unit/test_tools.py::TestCRMAdapter::test_create_lead_success -v
```

### 2. Testing Workflow Loading

```python
# Test basic workflow loading
pytest tests/unit/test_workflow_loader.py::TestWorkflowLoader::test_load_workflow_basic -v

# Test workflow inheritance
pytest tests/unit/test_workflow_loader.py::TestWorkflowLoader::test_workflow_extends -v

# Test workflow mutations
pytest tests/unit/test_workflow_loader.py::TestWorkflowLoader::test_workflow_insert_after -v
```

### 3. Testing Router Performance

```python
# Test router decision latency
pytest tests/unit/test_router_v2_hardening.py::TestRouterV2Performance::test_high_concurrency_routing -v

# Test router consistency
pytest tests/unit/test_router_v2_hardening.py::TestRouterV2Integration::test_router_consistency -v
```

### 4. Testing Reliability Patterns

```python
# Test retry mechanism
pytest tests/unit/test_reliability_patterns.py::TestBaseAdapterReliability::test_operation_with_retries -v

# Test circuit breaker
pytest tests/unit/test_reliability_patterns.py::TestBaseAdapterReliability::test_circuit_breaker_opens -v

# Test saga compensation
pytest tests/unit/test_reliability_patterns.py::TestSagaOrchestrator::test_saga_compensation -v
```

## Debugging Tests

### 1. Debug Mode

```bash
# Enable debug logging
pytest tests/unit/test_tools.py -v -s --log-cli-level=DEBUG

# Run single test with debug
pytest tests/unit/test_tools.py::TestBaseAdapter::test_retry_with_exponential_backoff -v -s
```

### 2. Test Failure Investigation

```bash
# Run tests with detailed traceback
pytest tests/unit/test_tools.py -v --tb=long

# Run tests with pdb debugger
pytest tests/unit/test_tools.py -v --pdb

# Run tests with pdb on failure
pytest tests/unit/test_tools.py -v --pdbcls=IPython.terminal.debugger:Pdb
```

### 3. Test Output Analysis

```bash
# Run tests with verbose output
pytest tests/unit/test_tools.py -v -s

# Run tests with coverage and show missing lines
pytest tests/unit/test_tools.py --cov=libs --cov-report=term-missing

# Run tests and save results
pytest tests/unit/test_tools.py --junitxml=test-results.xml
```

## Troubleshooting

### Common Issues

#### 1. Service Connection Failures

```bash
# Check service health
curl http://localhost:8000/healthz
curl http://localhost:8001/healthz
curl http://localhost:8002/healthz

# Check service logs
docker logs postgres
docker logs redis
docker logs nats
```

#### 2. Database Connection Issues

```bash
# Check PostgreSQL
psql -h localhost -U test_user -d test_db -c "SELECT 1"

# Check Redis
redis-cli -h localhost -p 6379 ping

# Check NATS
nats-server --help
```

#### 3. Test Timeouts

```bash
# Increase timeout
pytest tests/unit/test_tools.py --timeout=300

# Run specific slow tests
pytest -m slow --timeout=600
```

#### 4. Memory Issues

```bash
# Run with memory profiling
pytest tests/unit/test_tools.py --profile-memory

# Check memory usage
pytest tests/unit/test_tools.py --memray
```

#### 5. Import Errors

```bash
# Check Python path
python -c "import sys; print(sys.path)"

# Install missing dependencies
pip install -r requirements-dev.txt

# Check for circular imports
python -m py_compile libs/workflows/workflow_loader.py
```

### Getting Help

#### 1. Check Documentation

- Read the main [README.md](README.md) for overview
- Check [test-categories.md](test-categories.md) for detailed test information
- Review [testing-patterns.md](testing-patterns.md) for best practices

#### 2. Run Test Helpers

```bash
# Run all tests to check system health
python tests/run_all_tests.py

# Run evaluation tests
python tests/run_evaluation.py --type all

# Check test configuration
pytest --collect-only tests/unit/
```

#### 3. Debug Specific Issues

```bash
# Check test discovery
pytest --collect-only tests/unit/test_tools.py

# Check fixture availability
pytest --fixtures tests/unit/test_tools.py

# Check marker usage
pytest --markers
```

## Next Steps

### 1. Explore Test Categories

- Read [test-categories.md](test-categories.md) to understand different test types
- Try running tests from each category
- Understand the purpose and scope of each test type

### 2. Learn Testing Patterns

- Study [testing-patterns.md](testing-patterns.md) for best practices
- Understand async testing patterns
- Learn about property-based testing with Hypothesis

### 3. Set Up CI/CD

- Review [ci-cd-integration.md](ci-cd-integration.md) for automation
- Set up GitHub Actions workflows
- Configure quality gates

### 4. Performance Testing

- Read [performance-testing.md](performance-testing.md) for load testing
- Set up Locust for load testing
- Understand performance targets and monitoring

### 5. Contribute

- Follow the testing patterns and best practices
- Add tests for new features
- Maintain test quality and coverage
- Update documentation as needed

## Quick Reference

### Essential Commands

```bash
# Run unit tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ --cov=libs --cov=apps

# Run specific test
pytest tests/unit/test_tools.py::TestBaseAdapter::test_retry_with_exponential_backoff -v

# Run integration tests
pytest tests/integration/ -v

# Run performance tests
locust -f tests/performance/locustfile.py --host=http://localhost:8000 --users=100 --spawn-rate=10 --run-time=5m --headless
```

### Key Files

- `tests/conftest.py` - Test configuration and fixtures
- `tests/unit/` - Unit tests directory
- `tests/integration/` - Integration tests directory
- `tests/performance/locustfile.py` - Load testing configuration
- `pytest.ini` - Pytest configuration

### Important URLs

- Test coverage report: `htmlcov/index.html`
- Load test report: `load-test-report.html`
- Service health: `http://localhost:8000/healthz`

This guide should get you started with testing the Multi-AI-Agent platform. For more detailed information, refer to the other documentation files in this directory.
