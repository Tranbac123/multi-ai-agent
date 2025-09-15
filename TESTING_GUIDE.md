# Production-Grade Testing Guide

## Overview

This guide covers the comprehensive testing architecture for the Multi-Tenant AIaaS Platform. The test system is designed to be production-grade with three execution modes, comprehensive coverage, and automated quality gates.

## Table of Contents

1. [Test Execution Modes](#test-execution-modes)
2. [Test Architecture](#test-architecture)
3. [Running Tests](#running-tests)
4. [Performance Testing](#performance-testing)
5. [Chaos Engineering](#chaos-engineering)
6. [Episode Replay](#episode-replay)
7. [Flakiness Management](#flakiness-management)
8. [Test Impact Selection](#test-impact-selection)
9. [Quality Gates](#quality-gates)
10. [Troubleshooting](#troubleshooting)

## Test Execution Modes

### MOCK Mode (Default)

- **Purpose**: Fast unit tests with mocked dependencies
- **Use Case**: Development, CI/CD pipeline
- **Execution**: `make test`
- **Dependencies**: None (all mocked)
- **Speed**: Fastest

### GOLDEN Mode

- **Purpose**: Deterministic tests with recorded LLM responses
- **Use Case**: Regression testing, golden output validation
- **Execution**: `TEST_MODE=GOLDEN make test`
- **Dependencies**: Cassette files in `tests/cassettes/`
- **Speed**: Medium (cached responses)

### LIVE_SMOKE Mode

- **Purpose**: Small-scale integration tests with real services
- **Use Case**: Production smoke tests, validation
- **Execution**: `TEST_MODE=LIVE_SMOKE make test`
- **Dependencies**: Live service stack
- **Speed**: Slowest (real API calls)

## Test Architecture

### Directory Structure

```
tests/
├── _fixtures/           # Test fixtures and factories
├── _helpers/            # Test utilities and helpers
├── _plugins/            # Custom pytest plugins
├── unit/                # Unit tests (fast, isolated)
├── integration/         # Integration tests
│   ├── security/        # Security and multi-tenant tests
│   ├── tools/           # Tool reliability tests
│   └── router/          # Router drift tests
├── e2e/                 # End-to-end journey tests
├── performance/         # Performance and load tests
├── observability/       # SLO and metrics tests
├── chaos/               # Chaos engineering tests
├── adversarial/         # Security and robustness tests
├── realtime/            # WebSocket and realtime tests
├── rag/                 # RAG isolation tests
├── contract/            # API contract tests
└── conftest.py          # Pytest configuration
```

### Test Categories

#### Unit Tests

- **Location**: `tests/unit/`
- **Purpose**: Test individual components in isolation
- **Execution Time**: < 1 second per test
- **Mocking**: Heavy use of mocks

#### Integration Tests

- **Location**: `tests/integration/`
- **Purpose**: Test component interactions
- **Execution Time**: 1-10 seconds per test
- **Mocking**: Minimal mocking, real service interactions

#### End-to-End Tests

- **Location**: `tests/e2e/`
- **Purpose**: Test complete user journeys
- **Execution Time**: 10-60 seconds per test
- **Mocking**: No mocking, full stack

#### Performance Tests

- **Location**: `tests/performance/`
- **Purpose**: Load testing and performance regression
- **Execution Time**: 1-10 minutes per test
- **Tools**: Locust, custom performance frameworks

#### Security Tests

- **Location**: `tests/integration/security/`, `tests/adversarial/`
- **Purpose**: Security validation and adversarial testing
- **Execution Time**: 5-30 seconds per test
- **Focus**: Multi-tenant isolation, PII protection, SSRF prevention

## Running Tests

### Basic Commands

```bash
# Run all tests in MOCK mode (default)
make test

# Run specific test categories
make test-unit
make test-integration
make test-e2e
make test-performance
make test-security

# Run tests in different modes
TEST_MODE=GOLDEN make test
TEST_MODE=LIVE_SMOKE make test

# Run with specific pytest options
make test ARGS="-v -k 'test_api_gateway'"
```

### Advanced Commands

```bash
# Run tests with coverage
make test-coverage

# Run performance tests with regression checking
make perf

# Run chaos engineering tests
make chaos

# Run episode replay for specific episode
make replay RUN=episode_12345

# Run flakiness analysis
make flakiness-report

# Run test impact selection
make test-impact CHANGED_FILES="app/api/main.py,app/core/config.py"
```

### Environment Variables

```bash
# Test configuration
export TEST_MODE=MOCK                    # MOCK, GOLDEN, LIVE_SMOKE
export TEST_SEED=42                      # Deterministic seed
export TEST_TIMEOUT=300                  # Test timeout in seconds
export TEST_TEMPERATURE=0                # LLM temperature for GOLDEN mode
export TEST_NORMALIZE_OUTPUTS=true       # Normalize outputs for comparison

# Performance testing
export PERF_BASELINE_DIR=perf/baselines  # Performance baseline directory
export PERF_REGRESSION_THRESHOLD=10      # Regression threshold percentage
export PERF_COST_CEILING=10.0            # Cost ceiling in USD

# Chaos engineering
export CHAOS_ENABLED=true                # Enable chaos tests
export CHAOS_PROBABILITY=0.1             # Failure probability
export CHAOS_DURATION=30                 # Chaos duration in seconds

# Observability
export PROMETHEUS_URL=http://localhost:9090
export GRAFANA_URL=http://localhost:3000
export OTEL_ENDPOINT=http://localhost:4317
```

## Performance Testing

### Locust Profiles

```bash
# Run baseline performance test
locust -f tests/performance/locustfile.py --headless -u 100 -r 10 -t 300s

# Run stress test
locust -f tests/performance/locustfile.py --headless -u 1000 -r 50 -t 600s

# Run spike test
locust -f tests/performance/locustfile.py --headless -u 5000 -r 100 -t 60s
```

### Performance Regression Gates

The system automatically checks for performance regressions:

- **P50 Latency**: Must not increase by > 10%
- **P95 Latency**: Must not increase by > 15%
- **P99 Latency**: Must not increase by > 20%
- **Throughput**: Must not decrease by > 5%
- **Cost**: Must not exceed ceiling

### Performance Artifacts

Performance tests generate:

- HTML reports in `locust-reports/`
- Baseline comparisons in `perf/baselines/`
- Trend analysis in `perf/trends/`

## Chaos Engineering

### Chaos Tests

```bash
# Run all chaos tests
make chaos

# Run specific chaos scenarios
make chaos-scenario SCENARIO=orchestrator_kill
make chaos-scenario SCENARIO=nats_outage
make chaos-scenario SCENARIO=db_failover
```

### Chaos Scenarios

1. **Orchestrator Kill**: Kills orchestrator mid-execution
2. **NATS Outage**: Simulates NATS service outage
3. **DB Primary Failover**: Tests read-replica promotion
4. **Vector Store Outage**: Tests fallback mechanisms
5. **Network Partition**: Simulates network issues

### Episode Replay

```bash
# Replay specific episode
make replay RUN=episode_12345

# Replay with frozen versions
make replay-frozen RUN=episode_12345 MODEL_VERSION=gpt-4-turbo-2024-04-09

# Batch replay
make replay-batch EPISODES_FILE=episodes.txt
```

## Flakiness Management

### Automatic Detection

The system automatically detects flaky tests:

- **Flakiness Rate**: > 10% failure rate
- **Quarantine Threshold**: > 20% failure rate
- **Retry Policy**: 2 automatic retries for flaky tests

### Flakiness Reports

```bash
# Generate weekly flakiness report
make flakiness-report

# View quarantine list
make quarantine-list

# Fix quarantined tests
make fix-quarantined
```

### Test Impact Selection

```bash
# Analyze test impact for changed files
make test-impact CHANGED_FILES="app/api/main.py"

# Run only affected tests
make test-selective

# Get impact analysis
make impact-analysis
```

## Quality Gates

### CI/CD Integration

All quality gates are enforced in CI/CD:

1. **Security Suite**: Must pass (blocks merge)
2. **Flakiness Budget**: < 5% flakiness rate
3. **Performance Regression**: No significant regressions
4. **Test Coverage**: > 80% coverage
5. **Adversarial Tests**: < 15% failure rate

### Manual Quality Gates

```bash
# Check all quality gates
make quality-gates

# Security gate only
make security-gate

# Performance gate only
make performance-gate

# Flakiness gate only
make flakiness-gate
```

## Troubleshooting

### Common Issues

#### Test Timeouts

```bash
# Increase timeout
export TEST_TIMEOUT=600
make test

# Run specific slow tests
make test ARGS="-m slow"
```

#### Flaky Tests

```bash
# Run with retries
make test ARGS="--reruns 3"

# Skip flaky tests
make test ARGS="-m 'not flaky'"

# Run only stable tests
make test ARGS="-m stable"
```

#### Performance Issues

```bash
# Run with profiling
make test ARGS="--profile"

# Check resource usage
make test ARGS="--monitor"

# Run in parallel
make test ARGS="-n auto"
```

#### Memory Issues

```bash
# Increase memory limit
export TEST_MEMORY_LIMIT=4G
make test

# Run tests sequentially
make test ARGS="-x"
```

### Debug Mode

```bash
# Enable debug logging
export TEST_DEBUG=true
export LOG_LEVEL=DEBUG
make test

# Run with verbose output
make test ARGS="-vvv"

# Run single test with debugging
make test ARGS="-vvv -k 'test_specific_function'"
```

### Test Data Management

```bash
# Clean test data
make clean-test-data

# Reset test database
make reset-test-db

# Generate test fixtures
make generate-fixtures

# Validate test data
make validate-test-data
```

## Best Practices

### Writing Tests

1. **Use descriptive test names**
2. **Follow AAA pattern** (Arrange, Act, Assert)
3. **Keep tests independent**
4. **Use appropriate test categories**
5. **Mock external dependencies**
6. **Test error conditions**

### Performance Testing

1. **Establish baselines early**
2. **Run performance tests regularly**
3. **Monitor cost ceilings**
4. **Use realistic test data**
5. **Test under various loads**

### Security Testing

1. **Test all attack vectors**
2. **Validate multi-tenant isolation**
3. **Check PII protection**
4. **Test authentication/authorization**
5. **Verify input validation**

### Maintenance

1. **Review flakiness reports weekly**
2. **Update test data regularly**
3. **Monitor test execution times**
4. **Keep dependencies updated**
5. **Document test scenarios**

## Support

For testing issues:

1. Check this guide first
2. Review test logs
3. Check CI/CD pipeline status
4. Contact the testing team
5. Create an issue with full details

## Appendix

### Test Configuration Files

- `pytest.ini`: Pytest configuration
- `conftest.py`: Test fixtures and configuration
- `.pytest_cache/`: Pytest cache directory
- `test_flakiness.db`: Flakiness tracking database
- `perf/baselines/`: Performance baseline data

### Environment Setup

```bash
# Install dependencies
pip install -r requirements.txt
pip install -r requirements-test.txt

# Set up test environment
export TEST_ENV=development
export TEST_DB_URL=sqlite:///test.db
export TEST_REDIS_URL=redis://localhost:6379/1

# Verify setup
make test-setup-verify
```
