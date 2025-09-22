# Test Suite Documentation

This directory contains a comprehensive production-grade test suite for the MULTI-AI-AGENT platform.

## Test Structure

```
tests/
├── conftest.py                 # Test configuration and fixtures
├── unit/                       # Unit tests
│   ├── test_tools.py          # Tools and adapters
│   ├── test_workflow_loader.py # Workflow loading
│   └── test_router_v2.py      # Router v2 functionality
├── contract/                   # Contract tests
│   └── test_api_contracts.py  # API boundary contracts
├── integration/                # Integration tests
│   ├── test_workflow_execution.py # Workflow execution
│   ├── test_realtime.py       # Realtime functionality
│   ├── test_rag_memory.py     # RAG/Memory
│   ├── test_multitenant_security.py # Multi-tenant & security
│   └── test_observability.py  # Observability
├── e2e/                        # End-to-end tests
├── chaos/                      # Chaos engineering tests
│   └── test_chaos_engineering.py # Resilience testing
├── eval/                       # Evaluation tests
│   └── test_golden_tasks.py   # Golden task evaluation
└── README.md                   # This file
```

## Test Modes

### MOCK Mode (Default)

- Uses mocked LLM responses and service calls
- Fast execution, deterministic results
- Suitable for CI/CD and development

### LIVE_SMOKE Mode

- Uses real API calls with minimal test set
- Validates actual service integration
- Requires API keys and service availability

## Running Tests

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio hypothesis httpx redis nats-py asyncpg

# Start required services (for integration tests)
docker-compose up -d postgres redis nats
```

### Basic Test Execution

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit/                    # Unit tests
pytest tests/contract/               # Contract tests
pytest tests/integration/            # Integration tests
pytest tests/e2e/                    # E2E tests
pytest tests/chaos/                  # Chaos tests
pytest tests/eval/                   # Evaluation tests

# Run with specific markers
pytest -m "unit"                     # Unit tests only
pytest -m "integration"              # Integration tests only
pytest -m "slow"                     # Slow tests only
pytest -m "live"                     # Live API tests only
```

### Test Modes

```bash
# MOCK mode (default)
pytest tests/unit/

# LIVE_SMOKE mode
TEST_MODE=live_smoke pytest tests/unit/
```

### Performance and Load Testing

```bash
# Run performance tests
pytest tests/unit/test_router_v2.py -v --timeout=60

# Run load tests
pytest tests/integration/test_observability.py::TestObservabilityIntegration::test_observability_under_load
```

## Test Categories

### Unit Tests (`tests/unit/`)

**Purpose**: Test individual components in isolation

**Coverage**:

- Tools and adapters (retries, circuit breakers, idempotency)
- Workflow loader (extends, insert_after, patch, budgets)
- Router v2 (feature extraction, calibration, bandit policy)
- Feature extractor monotonicity
- Calibration properties

**Key Features**:

- Fast execution (< 1 second per test)
- Property-based testing with Hypothesis
- Mocked dependencies
- Comprehensive error scenarios

### Contract Tests (`tests/contract/`)

**Purpose**: Validate API boundaries and data contracts

**Coverage**:

- API ↔ Orchestrator ↔ Router ↔ Tool DTOs
- Error mapping between services
- Schema validation and rejection
- Service boundary contracts

**Key Features**:

- Pact-like contract validation
- JSON schema strict validation
- Error propagation testing
- Cross-service compatibility

### Integration Tests (`tests/integration/`)

**Purpose**: Test service interactions and workflows

**Coverage**:

- Workflow execution (Plan → Route → Work → Verify → Repair → Commit)
- Saga orchestration with compensation
- Realtime WebSocket handling
- RAG/Memory permissioned retrieval
- Multi-tenant isolation (RLS)
- Rate limiting and quota enforcement
- Security validation
- Observability metrics and tracing

**Key Features**:

- Real service interactions
- Database and Redis integration
- WebSocket backpressure testing
- Security and isolation validation

### E2E Tests (`tests/e2e/`)

**Purpose**: Test complete user journeys

**Coverage**:

- Full request flow from API Gateway to response
- Multi-tenant scenarios
- Error handling and recovery
- Performance under load

### Chaos Tests (`tests/chaos/`)

**Purpose**: Test system resilience and failure recovery

**Coverage**:

- Orchestrator failure and recovery
- NATS outage and DLQ handling
- Database connection failures
- Redis failures and fallbacks
- Network partitions
- Resource exhaustion scenarios

**Key Features**:

- Failure injection
- Recovery validation
- Episode replay testing
- Resilience pattern verification

### Evaluation Tests (`tests/eval/`)

**Purpose**: Test AI model performance and quality

**Coverage**:

- Golden task execution
- LLM judge scoring
- Episode replay functionality
- Evaluation metrics calculation
- Threshold checking and blocking

**Key Features**:

- Deterministic evaluation
- Quality scoring
- Performance benchmarking
- CI integration with blocking

## Test Fixtures

### Core Fixtures

```python
# Service clients
router_client          # Router service client
orchestrator_client    # Orchestrator service client
api_gateway_client     # API Gateway client
analytics_client       # Analytics service client
billing_client         # Billing service client
realtime_client        # Realtime service client

# Infrastructure
redis_fixture          # Redis test instance
nats_fixture          # NATS test instance
postgres_fixture      # PostgreSQL test instance

# LLM
llm_mock              # Mocked LLM client
llm_golden            # Golden LLM responses

# Test data factories
tenant_factory        # Tenant data factory
user_factory          # User data factory
message_factory       # Message data factory
workflow_factory      # Workflow data factory
```

### Helper Functions

```python
# JSON validation
assert_json_strict(data, schema)     # Strict JSON schema validation

# Cost validation
assert_cost_within(actual, expected, tolerance)  # Cost within tolerance

# Trace validation
assert_trace_attrs(span, required_attrs)  # Required trace attributes
```

## Test Configuration

### Environment Variables

```bash
# Test mode
TEST_MODE=mock                    # or live_smoke

# Service URLs
API_GATEWAY_URL=http://localhost:8000
ORCHESTRATOR_URL=http://localhost:8001
ROUTER_URL=http://localhost:8002

# Database
POSTGRES_URL=postgresql://user:pass@localhost:5432/test_db
REDIS_URL=redis://localhost:6379/15
NATS_URL=nats://localhost:4222

# LLM API Keys (for live_smoke mode)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-...
```

### Pytest Configuration

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

## CI/CD Integration

### GitHub Actions

The test suite is integrated with GitHub Actions:

```yaml
# .github/workflows/test.yml
- Unit tests with coverage
- Contract tests
- Integration tests with services
- E2E tests
- Chaos tests
- Evaluation tests
- Router performance tests (p50 < 50ms)
- RLS tests
- Security tests
```

### Test Results

- **Unit Tests**: Must pass for all PRs
- **Contract Tests**: Must pass for API changes
- **Integration Tests**: Must pass for service changes
- **E2E Tests**: Must pass for deployment
- **Chaos Tests**: Must pass for resilience changes
- **Evaluation Tests**: Must pass above threshold
- **Router Performance**: Must meet p50 < 50ms requirement
- **RLS Tests**: Must pass for security changes

### Failure Conditions

The build will fail if:

- Any unit test fails
- Contract tests fail
- Integration tests fail
- E2E tests fail
- Chaos tests fail
- Evaluation score below threshold
- Router p50 latency > 50ms
- RLS tests fail

## Performance Baselines

### Latency Targets

- **Router Decision**: p50 < 50ms, p95 < 100ms
- **Tool Execution**: p50 < 500ms, p95 < 1000ms
- **Workflow Execution**: p50 < 2000ms, p95 < 5000ms
- **API Response**: p50 < 100ms, p95 < 500ms

### Throughput Targets

- **API Requests**: 1000 req/s
- **WebSocket Connections**: 10000 concurrent
- **Database Queries**: 10000 qps
- **Message Processing**: 5000 msg/s

### Resource Usage

- **Memory**: < 2GB per service
- **CPU**: < 80% utilization
- **Disk I/O**: < 1000 IOPS
- **Network**: < 100 Mbps

## Troubleshooting

### Common Issues

1. **Service Connection Failures**

   ```bash
   # Check service health
   curl http://localhost:8000/healthz
   curl http://localhost:8001/healthz
   curl http://localhost:8002/healthz
   ```

2. **Database Connection Issues**

   ```bash
   # Check PostgreSQL
   psql -h localhost -U postgres -d test_db -c "SELECT 1"

   # Check Redis
   redis-cli -h localhost -p 6379 ping

   # Check NATS
   nats-server --help
   ```

3. **Test Timeouts**

   ```bash
   # Increase timeout
   pytest --timeout=300

   # Run specific slow tests
   pytest -m "slow" --timeout=600
   ```

4. **Memory Issues**

   ```bash
   # Run with memory profiling
   pytest --profile-memory

   # Check memory usage
   pytest --memray
   ```

### Debug Mode

```bash
# Enable debug logging
pytest --log-cli-level=DEBUG

# Run single test with debug
pytest tests/unit/test_tools.py::TestBaseAdapter::test_retry_with_exponential_backoff -v -s

# Run with coverage
pytest --cov=apps --cov-report=html
```

## Best Practices

### Writing Tests

1. **Use descriptive test names**

   ```python
   def test_router_early_exit_valid_json(self):
       """Test early exit for valid JSON responses."""
   ```

2. **Test one thing per test**

   ```python
   def test_retry_mechanism(self):
       """Test retry mechanism only."""

   def test_circuit_breaker(self):
       """Test circuit breaker only."""
   ```

3. **Use appropriate fixtures**

   ```python
   def test_workflow_execution(self, orchestrator_client, tenant_factory):
       """Test workflow execution with proper fixtures."""
   ```

4. **Mock external dependencies**

   ```python
   @patch('external_service.api_call')
   def test_with_mock(self, mock_api):
       """Test with mocked external service."""
   ```

5. **Use property-based testing**
   ```python
   @given(st.text(min_size=1, max_size=100))
   def test_input_validation(self, input_text):
       """Test input validation with various inputs."""
   ```

### Test Data

1. **Use factories for test data**

   ```python
   tenant = tenant_factory(name="Test Tenant", plan="premium")
   user = user_factory(tenant_id=tenant["tenant_id"], role="admin")
   ```

2. **Clean up test data**

   ```python
   @pytest.fixture(autouse=True)
   async def cleanup_test_data(redis_fixture):
       yield
       await redis_fixture.flushdb()
   ```

3. **Use realistic test data**
   ```python
   message = message_factory(
       content="I need help with my order",
       metadata={"priority": "high", "category": "support"}
   )
   ```

### Performance Testing

1. **Set performance baselines**

   ```python
   def test_router_performance(self):
       """Test router performance meets p50 < 50ms requirement."""
       start_time = time.time()
       result = await router.route_request(request)
       execution_time = (time.time() - start_time) * 1000
       assert execution_time < 50  # p50 < 50ms
   ```

2. **Test under load**

   ```python
   async def test_under_load(self):
       """Test system performance under load."""
       tasks = [self._simulate_request() for _ in range(1000)]
       results = await asyncio.gather(*tasks)
       assert all(result["success"] for result in results)
   ```

3. **Monitor resource usage**
   ```python
   def test_memory_usage(self):
       """Test memory usage stays within limits."""
       memory_before = psutil.Process().memory_info().rss
       result = await process_large_data()
       memory_after = psutil.Process().memory_info().rss
       assert memory_after - memory_before < 100 * 1024 * 1024  # 100MB
   ```

## Contributing

### Adding New Tests

1. **Follow naming conventions**

   - Test files: `test_*.py`
   - Test classes: `Test*`
   - Test methods: `test_*`

2. **Use appropriate markers**

   ```python
   @pytest.mark.unit
   @pytest.mark.slow
   def test_complex_operation(self):
       """Test complex operation."""
   ```

3. **Add proper documentation**

   ```python
   def test_router_bandit_policy(self):
       """Test bandit policy arm selection and reward updates.

       This test verifies that the bandit policy:
       - Selects arms based on expected value
       - Updates rewards correctly
       - Balances exploration vs exploitation
       """
   ```

4. **Include edge cases**
   ```python
   def test_edge_cases(self):
       """Test edge cases and error conditions."""
       # Test with empty input
       # Test with invalid input
       # Test with boundary values
       # Test error conditions
   ```

### Test Review Checklist

- [ ] Test covers the intended functionality
- [ ] Test is deterministic and repeatable
- [ ] Test uses appropriate fixtures and mocks
- [ ] Test includes edge cases and error conditions
- [ ] Test has clear documentation
- [ ] Test follows naming conventions
- [ ] Test is properly marked
- [ ] Test performance meets requirements
- [ ] Test cleans up after itself
- [ ] Test is maintainable and readable
