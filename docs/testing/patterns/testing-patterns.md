# Testing Patterns and Best Practices

## Overview

This document outlines the testing patterns, best practices, and implementation strategies used throughout the Multi-AI-Agent platform test suite. These patterns ensure consistent, maintainable, and effective testing across all components.

## Table of Contents

1. [Testing Patterns](#testing-patterns)
2. [Fixture Patterns](#fixture-patterns)
3. [Mocking Strategies](#mocking-strategies)
4. [Async Testing Patterns](#async-testing-patterns)
5. [Property-Based Testing](#property-based-testing)
6. [Error Testing Patterns](#error-testing-patterns)
7. [Performance Testing Patterns](#performance-testing-patterns)
8. [Test Data Management](#test-data-management)
9. [Best Practices](#best-practices)

## Testing Patterns

### 1. Arrange-Act-Assert (AAA) Pattern

The standard pattern for organizing test code:

```python
def test_workflow_loading(self):
    """Test workflow loading functionality."""
    # Arrange
    workflow_data = {
        "name": "test_workflow",
        "version": "1.0.0",
        "nodes": [{"id": "start", "type": "input"}],
        "edges": []
    }

    # Act
    result = loader.load_workflow(workflow_data)

    # Assert
    assert result.name == "test_workflow"
    assert result.version == "1.0.0"
    assert len(result.steps) == 1
```

### 2. Test Class Organization

Organize related tests into classes with descriptive names:

```python
class TestBaseAdapter:
    """Test base adapter functionality."""

    @pytest.mark.asyncio
    async def test_retry_with_exponential_backoff(self, mock_redis):
        """Test retry mechanism with exponential backoff."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_open(self, mock_redis):
        """Test circuit breaker opens after failures."""

    @pytest.mark.asyncio
    async def test_idempotency_prevention(self, mock_redis):
        """Test idempotency key prevents duplicate operations."""


class TestPaymentAdapter:
    """Test payment adapter functionality."""

    @pytest.mark.asyncio
    async def test_process_payment_success(self, mock_redis):
        """Test successful payment processing."""

    @pytest.mark.asyncio
    async def test_process_payment_validation(self, mock_redis):
        """Test payment validation."""
```

### 3. Parameterized Testing

Use pytest.mark.parametrize for testing multiple scenarios:

```python
@pytest.mark.parametrize("amount,expected_status", [
    (100.0, PaymentStatus.COMPLETED),
    (0.0, PaymentStatus.FAILED),
    (-10.0, PaymentStatus.FAILED),
])
async def test_payment_amount_validation(self, amount, expected_status, mock_redis):
    """Test payment amount validation."""
    adapter = PaymentAdapter("payment_adapter", config, mock_redis)
    request = PaymentRequest(amount=amount, currency="USD", customer_id="test")

    result = await adapter.process_payment(request)

    assert result.status == expected_status
```

### 4. Test Discovery and Naming

Follow consistent naming conventions:

```python
# Test file naming
test_tools.py                    # Tests for tools module
test_workflow_loader.py         # Tests for workflow loader
test_router_v2.py              # Tests for router v2

# Test class naming
class TestBaseAdapter:          # Tests for BaseAdapter class
class TestPaymentAdapter:       # Tests for PaymentAdapter class
class TestRouterV2:             # Tests for RouterV2 class

# Test method naming
def test_retry_with_exponential_backoff(self):
def test_circuit_breaker_opens(self):
def test_workflow_validation_error_missing_name(self):
```

## Fixture Patterns

### 1. Scope-Based Fixtures

Use appropriate fixture scopes for different use cases:

```python
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def mock_redis():
    """Mock Redis client for each test."""
    mock = AsyncMock()
    mock.get.return_value = None
    mock.setex.return_value = True
    return mock


@pytest.fixture(scope="module")
def test_config():
    """Test configuration shared across module."""
    return {
        "timeout": 30.0,
        "retry_attempts": 3,
        "cost_tolerance": 0.1
    }
```

### 2. Factory Fixtures

Create test data using factory patterns:

```python
@pytest.fixture
def tenant_factory():
    """Factory for creating test tenants."""
    def _create_tenant(tenant_id=None, **kwargs):
        return {
            "tenant_id": tenant_id or f"tenant_{uuid.uuid4().hex[:8]}",
            "name": kwargs.get("name", "Test Tenant"),
            "plan": kwargs.get("plan", "basic"),
            "created_at": time.time(),
            **kwargs
        }
    return _create_tenant


@pytest.fixture
def message_factory():
    """Factory for creating test messages."""
    def _create_message(content=None, **kwargs):
        return {
            "message_id": kwargs.get("message_id", str(uuid.uuid4())),
            "content": content or "Test message",
            "tenant_id": kwargs.get("tenant_id", "test_tenant"),
            "user_id": kwargs.get("user_id", "test_user"),
            "session_id": kwargs.get("session_id", str(uuid.uuid4())),
            "timestamp": kwargs.get("timestamp", time.time()),
            "metadata": kwargs.get("metadata", {}),
            **kwargs
        }
    return _create_message
```

### 3. Dependency Injection Fixtures

Inject dependencies for testing:

```python
@pytest.fixture
def payment_adapter(mock_redis):
    """Payment adapter with mocked dependencies."""
    config = AdapterConfig(
        max_retries=3,
        retry_delay_ms=100,
        timeout_ms=5000,
    )
    return PaymentAdapter("payment_adapter", config, mock_redis)


@pytest.fixture
def workflow_loader():
    """Workflow loader for testing."""
    return WorkflowLoader()


@pytest.fixture
def router_v2(mock_redis):
    """Router v2 with mocked dependencies."""
    return RouterV2(config, mock_redis)
```

## Mocking Strategies

### 1. AsyncMock for Async Operations

Use AsyncMock for mocking async functions:

```python
@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    mock = AsyncMock()
    mock.get.return_value = None
    mock.setex.return_value = True
    mock.hset.return_value = True
    mock.expire.return_value = True
    mock.keys.return_value = []
    mock.hgetall.return_value = {}
    return mock


@pytest.fixture
def mock_llm():
    """Mock LLM client for testing."""
    mock = AsyncMock()
    mock.generate.return_value = {
        "content": "Mocked response",
        "tokens_used": 100,
        "model": "gpt-4",
        "finish_reason": "stop"
    }
    return mock
```

### 2. Patch Decorators

Use patch decorators for mocking external dependencies:

```python
@patch('services.tools.payment_adapter.time.time')
async def test_payment_timestamp(self, mock_time, mock_redis):
    """Test payment timestamp generation."""
    mock_time.return_value = 1234567890.0

    adapter = PaymentAdapter("payment_adapter", config, mock_redis)
    request = PaymentRequest(amount=100.0, currency="USD", customer_id="test")

    result = await adapter.process_payment(request)

    assert result.processed_at == 1234567890.0


@patch('apps.router_service.core.features.FeatureExtractor.extract_features')
def test_router_feature_extraction(self, mock_extract):
    """Test router feature extraction."""
    mock_extract.return_value = {"feature1": 0.5, "feature2": 0.3}

    router = RouterV2(config, mock_redis)
    result = router.extract_features({"message": "test"})

    assert result["feature1"] == 0.5
    assert result["feature2"] == 0.3
```

### 3. Side Effects for Complex Behavior

Use side_effects for more complex mock behavior:

```python
async def test_retry_mechanism(self, mock_redis):
    """Test retry mechanism with failures."""
    call_count = 0

    async def failing_operation():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Temporary failure")
        return {"success": True}

    adapter = BaseAdapter("test_adapter", config, mock_redis)
    result = await adapter.call(failing_operation)

    assert result["success"] is True
    assert call_count == 3
```

## Async Testing Patterns

### 1. Proper Async/Await Usage

Always properly await async operations:

```python
@pytest.mark.asyncio
async def test_async_operation(self):
    """Test async operation with proper awaiting."""
    adapter = PaymentAdapter("payment_adapter", config, mock_redis)
    request = PaymentRequest(amount=100.0, currency="USD", customer_id="test")

    # Properly await the async operation
    result = await adapter.process_payment(request)

    assert result.status == PaymentStatus.COMPLETED


@pytest.mark.asyncio
async def test_concurrent_operations(self):
    """Test concurrent async operations."""
    adapter = PaymentAdapter("payment_adapter", config, mock_redis)
    requests = [
        PaymentRequest(amount=100.0, currency="USD", customer_id=f"customer_{i}")
        for i in range(10)
    ]

    # Run concurrent operations
    tasks = [adapter.process_payment(req) for req in requests]
    results = await asyncio.gather(*tasks)

    assert len(results) == 10
    assert all(result.status in [PaymentStatus.COMPLETED, PaymentStatus.FAILED] for result in results)
```

### 2. Timeout Handling

Use timeouts for async operations:

```python
@pytest.mark.asyncio
async def test_operation_timeout(self):
    """Test operation timeout handling."""
    async def slow_operation():
        await asyncio.sleep(10)  # Simulate slow operation
        return {"success": True}

    adapter = BaseAdapter("test_adapter", config, mock_redis)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(adapter.call(slow_operation), timeout=1.0)
```

### 3. Resource Cleanup

Ensure proper cleanup of async resources:

```python
@pytest.fixture
async def redis_fixture():
    """Redis test fixture with proper cleanup."""
    redis_client = redis.Redis(host="localhost", port=6379, db=15)
    await redis_client.flushdb()

    try:
        yield redis_client
    finally:
        await redis_client.flushdb()
        await redis_client.close()
```

## Property-Based Testing

### 1. Hypothesis Strategies

Use Hypothesis for property-based testing:

```python
@given(st.text(min_size=1, max_size=1000))
def test_message_validation(self, message_content):
    """Test message validation with various inputs."""
    result = validate_message(message_content)
    assert result.is_valid
    assert len(result.content) <= 1000


@given(st.floats(min_value=0.01, max_value=1000.0))
def test_amount_validation(self, amount):
    """Test amount validation for positive values."""
    request = PaymentRequest(amount=amount, currency="USD", customer_id="test")
    assert request.amount > 0


@given(st.text(min_size=8, max_size=32, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))))
def test_tenant_id_validation(self, tenant_id):
    """Test tenant ID validation."""
    tenant = tenant_factory(tenant_id=tenant_id)
    assert validate_tenant_id(tenant["tenant_id"])
```

### 2. Complex Data Structures

Test complex data structures with Hypothesis:

```python
@given(st.recursive(
    st.one_of(st.text(), st.integers(), st.floats(), st.booleans(), st.none()),
    lambda children: st.lists(children) | st.dictionaries(st.text(), children)
))
def test_json_serialization(self, data):
    """Test JSON serialization with various data structures."""
    serialized = json.dumps(data)
    deserialized = json.loads(serialized)
    assert data == deserialized
```

## Error Testing Patterns

### 1. Exception Testing

Test exception scenarios:

```python
def test_workflow_validation_error_missing_name(self):
    """Test workflow validation error for missing name."""
    workflow_data = {
        "version": "1.0.0",
        "nodes": [],
        "edges": []
    }

    with pytest.raises(ValueError, match="Workflow name is required"):
        loader.load_workflow(workflow_data)


async def test_payment_validation_error_negative_amount(self, mock_redis):
    """Test payment validation error for negative amount."""
    adapter = PaymentAdapter("payment_adapter", config, mock_redis)
    request = PaymentRequest(amount=-100.0, currency="USD", customer_id="test")

    result = await adapter.process_payment(request)

    assert result.status == PaymentStatus.FAILED
    assert "Invalid amount" in result.error_message
```

### 2. Error Recovery Testing

Test error recovery mechanisms:

```python
async def test_circuit_breaker_recovery(self, mock_redis):
    """Test circuit breaker recovery after timeout."""
    adapter = BaseAdapter("test_adapter", config, mock_redis)

    # Cause failures to open circuit breaker
    for _ in range(5):
        with pytest.raises(Exception):
            await adapter.call(lambda: (_ for _ in ()).throw(Exception("Failure")))

    # Wait for circuit breaker timeout
    await asyncio.sleep(0.1)

    # Should recover and allow operations
    result = await adapter.call(lambda: {"success": True})
    assert result["success"] is True
```

## Performance Testing Patterns

### 1. Latency Measurement

Measure and assert latency requirements:

```python
async def test_router_performance(self, mock_redis):
    """Test router performance meets requirements."""
    router = RouterV2(config, mock_redis)
    request = {"message": "test message", "tenant_id": "test_tenant"}

    start_time = time.time()
    result = await router.route_request(request)
    execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds

    assert execution_time < 50  # p50 < 50ms requirement
    assert result.decision_time_ms < 50


async def test_high_concurrency_routing(self, mock_redis):
    """Test router performance under high concurrency."""
    router = RouterV2(config, mock_redis)
    requests = [{"message": f"test {i}", "tenant_id": "test_tenant"} for i in range(100)]

    start_time = time.time()
    tasks = [router.route_request(req) for req in requests]
    results = await asyncio.gather(*tasks)
    execution_time = (time.time() - start_time) * 1000

    assert len(results) == 100
    assert execution_time < 300  # Should handle 100 requests in < 300ms
    assert all(result.decision_time_ms < 300 for result in results)
```

### 2. Memory Usage Testing

Monitor memory usage:

```python
def test_memory_usage(self):
    """Test memory usage stays within limits."""
    import psutil

    process = psutil.Process()
    memory_before = process.memory_info().rss

    # Perform memory-intensive operation
    large_data = [{"data": "x" * 1000} for _ in range(10000)]
    result = process_large_data(large_data)

    memory_after = process.memory_info().rss
    memory_increase = memory_after - memory_before

    assert memory_increase < 100 * 1024 * 1024  # Less than 100MB increase
    assert result["success"] is True
```

## Test Data Management

### 1. Test Data Isolation

Ensure test data isolation:

```python
@pytest.fixture(autouse=True)
async def cleanup_test_data(redis_fixture):
    """Clean up test data after each test."""
    yield
    await redis_fixture.flushdb()


@pytest.fixture
def isolated_tenant():
    """Create isolated tenant for testing."""
    tenant_id = f"test_tenant_{uuid.uuid4().hex[:8]}"
    yield tenant_id
    # Cleanup handled by cleanup_test_data fixture
```

### 2. Realistic Test Data

Use realistic test data:

```python
@pytest.fixture
def realistic_message():
    """Create realistic test message."""
    return {
        "message_id": str(uuid.uuid4()),
        "content": "I need help with my order #12345. It was supposed to arrive yesterday.",
        "tenant_id": "ecommerce_corp",
        "user_id": "customer_123",
        "session_id": str(uuid.uuid4()),
        "timestamp": time.time(),
        "metadata": {
            "priority": "high",
            "category": "support",
            "source": "web_chat"
        }
    }


@pytest.fixture
def realistic_workflow():
    """Create realistic test workflow."""
    return {
        "name": "customer_support_workflow",
        "version": "2.1.0",
        "description": "Handle customer support requests",
        "nodes": [
            {"id": "start", "type": "input", "name": "Start"},
            {"id": "classify", "type": "classifier", "name": "Classify Request"},
            {"id": "route", "type": "router", "name": "Route to Agent"},
            {"id": "respond", "type": "llm", "name": "Generate Response"}
        ],
        "edges": [
            {"from": "start", "to": "classify"},
            {"from": "classify", "to": "route"},
            {"from": "route", "to": "respond"}
        ]
    }
```

### 3. Test Data Builders

Use builder pattern for complex test data:

```python
class PaymentRequestBuilder:
    """Builder for PaymentRequest test data."""

    def __init__(self):
        self._data = {
            "amount": 100.0,
            "currency": "USD",
            "customer_id": "test_customer",
            "payment_method_id": "pm_test",
            "description": "Test payment"
        }

    def with_amount(self, amount):
        self._data["amount"] = amount
        return self

    def with_currency(self, currency):
        self._data["currency"] = currency
        return self

    def with_customer_id(self, customer_id):
        self._data["customer_id"] = customer_id
        return self

    def build(self):
        return PaymentRequest(**self._data)


@pytest.fixture
def payment_request_builder():
    """Payment request builder fixture."""
    return PaymentRequestBuilder()


def test_payment_processing(payment_request_builder, mock_redis):
    """Test payment processing with builder."""
    request = payment_request_builder.with_amount(250.0).with_currency("EUR").build()

    adapter = PaymentAdapter("payment_adapter", config, mock_redis)
    result = await adapter.process_payment(request)

    assert result.amount == 250.0
    assert result.currency == "EUR"
```

## Best Practices

### 1. Test Organization

- **One test per behavior**: Each test should verify one specific behavior
- **Descriptive names**: Test names should clearly describe what is being tested
- **Proper grouping**: Group related tests into classes
- **Logical ordering**: Order tests logically within files

### 2. Test Independence

- **Isolated tests**: Tests should not depend on each other
- **Clean state**: Each test should start with a clean state
- **No side effects**: Tests should not have side effects on other tests
- **Deterministic**: Tests should produce consistent results

### 3. Test Maintainability

- **DRY principle**: Don't repeat yourself in test code
- **Use fixtures**: Extract common setup into fixtures
- **Clear assertions**: Use clear, descriptive assertions
- **Documentation**: Document complex test logic

### 4. Test Performance

- **Fast execution**: Keep unit tests fast (< 1 second)
- **Efficient mocking**: Use efficient mocking strategies
- **Parallel execution**: Design tests for parallel execution
- **Resource cleanup**: Clean up resources properly

### 5. Error Handling

- **Test error scenarios**: Test both success and failure cases
- **Validate error messages**: Check error messages and codes
- **Test recovery**: Test error recovery mechanisms
- **Edge cases**: Test boundary conditions and edge cases

### 6. Documentation

- **Docstrings**: Use docstrings for test methods
- **Comments**: Add comments for complex test logic
- **Examples**: Provide examples in documentation
- **README**: Maintain test documentation

This comprehensive guide to testing patterns ensures consistent, maintainable, and effective testing across the Multi-AI-Agent platform. By following these patterns and best practices, the test suite maintains high quality and reliability standards.
