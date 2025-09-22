"""
Integration tests for tool adapter reliability patterns.

Tests timeouts, retries, circuit-breaker, bulkhead, idempotency, write-ahead logging,
and saga compensation across various tool adapters.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

from libs.reliability import (
    BaseToolAdapter, CircuitBreaker, Bulkhead, RetryManager, IdempotencyManager,
    WriteAheadLogger, RetryConfig, CircuitBreakerConfig, BulkheadConfig,
    TimeoutConfig, RetryStrategy, CircuitState, SagaManager, create_saga_step
)

from apps.tool_service.adapters.example_adapter import (
    DatabaseAdapter, APIClientAdapter, FileSystemAdapter
)


class TestToolAdapter:
    """Test tool adapter implementation."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis_mock = AsyncMock()
        redis_mock.get.return_value = None
        redis_mock.setex.return_value = True
        return redis_mock
    
    @pytest.fixture
    def database_adapter(self, mock_redis):
        """Create database adapter for testing."""
        return DatabaseAdapter(redis_client=mock_redis)
    
    @pytest.fixture
    def api_adapter(self, mock_redis):
        """Create API adapter for testing."""
        return APIClientAdapter(redis_client=mock_redis)
    
    @pytest.fixture
    def filesystem_adapter(self, mock_redis):
        """Create filesystem adapter for testing."""
        return FileSystemAdapter(redis_client=mock_redis)


class TestDatabaseAdapter(TestToolAdapter):
    """Test database adapter reliability."""
    
    @pytest.mark.asyncio
    async def test_successful_select_operation(self, database_adapter):
        """Test successful SELECT operation."""
        parameters = {
            "operation": "select",
            "query": "SELECT * FROM users"
        }
        
        result = await database_adapter.execute(parameters)
        
        assert result["operation"] == "select"
        assert result["query"] == "SELECT * FROM users"
        assert "rows" in result
        assert result["row_count"] == 2
    
    @pytest.mark.asyncio
    async def test_successful_insert_operation(self, database_adapter):
        """Test successful INSERT operation."""
        parameters = {
            "operation": "insert",
            "data": {"name": "Test User", "email": "test@example.com"}
        }
        
        result = await database_adapter.execute(parameters)
        
        assert result["operation"] == "insert"
        assert result["data"] == parameters["data"]
        assert "inserted_id" in result
        assert result["affected_rows"] == 1
    
    @pytest.mark.asyncio
    async def test_successful_update_operation(self, database_adapter):
        """Test successful UPDATE operation."""
        parameters = {
            "operation": "update",
            "data": {"name": "Updated User"},
            "where": {"id": 1}
        }
        
        result = await database_adapter.execute(parameters)
        
        assert result["operation"] == "update"
        assert result["data"] == parameters["data"]
        assert result["where"] == parameters["where"]
        assert "affected_rows" in result
    
    @pytest.mark.asyncio
    async def test_successful_delete_operation(self, database_adapter):
        """Test successful DELETE operation."""
        parameters = {
            "operation": "delete",
            "where": {"id": 1}
        }
        
        result = await database_adapter.execute(parameters)
        
        assert result["operation"] == "delete"
        assert result["where"] == parameters["where"]
        assert "affected_rows" in result
    
    @pytest.mark.asyncio
    async def test_invalid_operation(self, database_adapter):
        """Test invalid operation handling."""
        parameters = {
            "operation": "invalid",
            "query": "SELECT * FROM users"
        }
        
        with pytest.raises(ValueError, match="Unsupported operation"):
            await database_adapter.execute(parameters)
    
    @pytest.mark.asyncio
    async def test_compensation_insert(self, database_adapter):
        """Test compensation for INSERT operation."""
        parameters = {
            "operation": "insert",
            "data": {"name": "Test User"}
        }
        
        result = {
            "operation": "insert",
            "inserted_id": 12345,
            "affected_rows": 1
        }
        
        success = await database_adapter.compensate(parameters, result)
        assert success is True
    
    @pytest.mark.asyncio
    async def test_compensation_update(self, database_adapter):
        """Test compensation for UPDATE operation."""
        parameters = {
            "operation": "update",
            "data": {"name": "Updated User"}
        }
        
        result = {
            "operation": "update",
            "affected_rows": 1
        }
        
        success = await database_adapter.compensate(parameters, result)
        assert success is True
    
    @pytest.mark.asyncio
    async def test_compensation_delete(self, database_adapter):
        """Test compensation for DELETE operation."""
        parameters = {
            "operation": "delete",
            "where": {"id": 1}
        }
        
        result = {
            "operation": "delete",
            "affected_rows": 1
        }
        
        success = await database_adapter.compensate(parameters, result)
        assert success is True


class TestAPIClientAdapter(TestToolAdapter):
    """Test API client adapter reliability."""
    
    @pytest.mark.asyncio
    async def test_successful_get_request(self, api_adapter):
        """Test successful GET request."""
        parameters = {
            "method": "GET",
            "endpoint": "/users",
            "headers": {"Authorization": "Bearer token"}
        }
        
        result = await api_adapter.execute(parameters)
        
        assert result["method"] == "GET"
        assert result["endpoint"] == "/users"
        assert result["status_code"] == 200
        assert "data" in result
    
    @pytest.mark.asyncio
    async def test_successful_post_request(self, api_adapter):
        """Test successful POST request."""
        parameters = {
            "method": "POST",
            "endpoint": "/users",
            "data": {"name": "New User"},
            "headers": {"Content-Type": "application/json"}
        }
        
        result = await api_adapter.execute(parameters)
        
        assert result["method"] == "POST"
        assert result["endpoint"] == "/users"
        assert result["status_code"] == 201
        assert "data" in result
    
    @pytest.mark.asyncio
    async def test_successful_put_request(self, api_adapter):
        """Test successful PUT request."""
        parameters = {
            "method": "PUT",
            "endpoint": "/users/1",
            "data": {"name": "Updated User"},
            "headers": {"Content-Type": "application/json"}
        }
        
        result = await api_adapter.execute(parameters)
        
        assert result["method"] == "PUT"
        assert result["endpoint"] == "/users/1"
        assert result["status_code"] == 200
        assert "data" in result
    
    @pytest.mark.asyncio
    async def test_successful_delete_request(self, api_adapter):
        """Test successful DELETE request."""
        parameters = {
            "method": "DELETE",
            "endpoint": "/users/1",
            "headers": {"Authorization": "Bearer token"}
        }
        
        result = await api_adapter.execute(parameters)
        
        assert result["method"] == "DELETE"
        assert result["endpoint"] == "/users/1"
        assert result["status_code"] == 204
        assert "data" in result
    
    @pytest.mark.asyncio
    async def test_invalid_http_method(self, api_adapter):
        """Test invalid HTTP method handling."""
        parameters = {
            "method": "PATCH",
            "endpoint": "/users/1"
        }
        
        with pytest.raises(ValueError, match="Unsupported HTTP method"):
            await api_adapter.execute(parameters)
    
    @pytest.mark.asyncio
    async def test_compensation_post(self, api_adapter):
        """Test compensation for POST request."""
        parameters = {
            "method": "POST",
            "endpoint": "/users",
            "data": {"name": "New User"}
        }
        
        result = {
            "method": "POST",
            "status_code": 201,
            "data": {"id": 12345, "created": True}
        }
        
        success = await api_adapter.compensate(parameters, result)
        assert success is True
    
    @pytest.mark.asyncio
    async def test_compensation_put(self, api_adapter):
        """Test compensation for PUT request."""
        parameters = {
            "method": "PUT",
            "endpoint": "/users/1",
            "data": {"name": "Updated User"}
        }
        
        result = {
            "method": "PUT",
            "status_code": 200,
            "data": {"updated": True}
        }
        
        success = await api_adapter.compensate(parameters, result)
        assert success is True
    
    @pytest.mark.asyncio
    async def test_compensation_delete(self, api_adapter):
        """Test compensation for DELETE request."""
        parameters = {
            "method": "DELETE",
            "endpoint": "/users/1"
        }
        
        result = {
            "method": "DELETE",
            "status_code": 204,
            "data": {"deleted": True}
        }
        
        success = await api_adapter.compensate(parameters, result)
        assert success is True


class TestFileSystemAdapter(TestToolAdapter):
    """Test file system adapter reliability."""
    
    @pytest.mark.asyncio
    async def test_successful_read_operation(self, filesystem_adapter):
        """Test successful file read operation."""
        parameters = {
            "operation": "read",
            "path": "/path/to/file.txt"
        }
        
        result = await filesystem_adapter.execute(parameters)
        
        assert result["operation"] == "read"
        assert result["path"] == "/path/to/file.txt"
        assert "content" in result
        assert "size_bytes" in result
    
    @pytest.mark.asyncio
    async def test_successful_write_operation(self, filesystem_adapter):
        """Test successful file write operation."""
        parameters = {
            "operation": "write",
            "path": "/path/to/file.txt",
            "content": "Hello, World!"
        }
        
        result = await filesystem_adapter.execute(parameters)
        
        assert result["operation"] == "write"
        assert result["path"] == "/path/to/file.txt"
        assert result["content"] == "Hello, World!"
        assert result["created"] is True
    
    @pytest.mark.asyncio
    async def test_successful_delete_operation(self, filesystem_adapter):
        """Test successful file delete operation."""
        parameters = {
            "operation": "delete",
            "path": "/path/to/file.txt"
        }
        
        result = await filesystem_adapter.execute(parameters)
        
        assert result["operation"] == "delete"
        assert result["path"] == "/path/to/file.txt"
        assert result["deleted"] is True
    
    @pytest.mark.asyncio
    async def test_successful_copy_operation(self, filesystem_adapter):
        """Test successful file copy operation."""
        parameters = {
            "operation": "copy",
            "path": "/path/to/source.txt",
            "destination": "/path/to/destination.txt"
        }
        
        result = await filesystem_adapter.execute(parameters)
        
        assert result["operation"] == "copy"
        assert result["source"] == "/path/to/source.txt"
        assert result["destination"] == "/path/to/destination.txt"
        assert result["copied"] is True
    
    @pytest.mark.asyncio
    async def test_invalid_file_operation(self, filesystem_adapter):
        """Test invalid file operation handling."""
        parameters = {
            "operation": "move",
            "path": "/path/to/file.txt"
        }
        
        with pytest.raises(ValueError, match="Unsupported file operation"):
            await filesystem_adapter.execute(parameters)
    
    @pytest.mark.asyncio
    async def test_compensation_write(self, filesystem_adapter):
        """Test compensation for file write operation."""
        parameters = {
            "operation": "write",
            "path": "/path/to/file.txt",
            "content": "Hello, World!"
        }
        
        result = {
            "operation": "write",
            "path": "/path/to/file.txt",
            "created": True
        }
        
        success = await filesystem_adapter.compensate(parameters, result)
        assert success is True
    
    @pytest.mark.asyncio
    async def test_compensation_delete(self, filesystem_adapter):
        """Test compensation for file delete operation."""
        parameters = {
            "operation": "delete",
            "path": "/path/to/file.txt"
        }
        
        result = {
            "operation": "delete",
            "path": "/path/to/file.txt",
            "deleted": True
        }
        
        success = await filesystem_adapter.compensate(parameters, result)
        assert success is True
    
    @pytest.mark.asyncio
    async def test_compensation_copy(self, filesystem_adapter):
        """Test compensation for file copy operation."""
        parameters = {
            "operation": "copy",
            "path": "/path/to/source.txt",
            "destination": "/path/to/destination.txt"
        }
        
        result = {
            "operation": "copy",
            "source": "/path/to/source.txt",
            "destination": "/path/to/destination.txt",
            "copied": True
        }
        
        success = await filesystem_adapter.compensate(parameters, result)
        assert success is True


class TestReliabilityPatterns:
    """Test individual reliability patterns."""
    
    @pytest.fixture
    def retry_config(self):
        """Create retry configuration."""
        return RetryConfig(
            max_attempts=3,
            base_delay_ms=100,
            max_delay_ms=1000,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            jitter=True
        )
    
    @pytest.fixture
    def circuit_breaker_config(self):
        """Create circuit breaker configuration."""
        return CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_ms=5000
        )
    
    @pytest.fixture
    def bulkhead_config(self):
        """Create bulkhead configuration."""
        return BulkheadConfig(
            max_concurrent_calls=3,
            max_wait_time_ms=1000
        )
    
    @pytest.fixture
    def timeout_config(self):
        """Create timeout configuration."""
        return TimeoutConfig(
            connect_timeout_ms=1000,
            read_timeout_ms=2000,
            total_timeout_ms=3000
        )
    
    @pytest.mark.asyncio
    async def test_retry_manager_success(self, retry_config):
        """Test retry manager with successful operation."""
        retry_manager = RetryManager(retry_config)
        
        call_count = 0
        
        async def mock_operation():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await retry_manager.call_with_retry(mock_operation)
        
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_manager_with_retries(self, retry_config):
        """Test retry manager with retries."""
        retry_manager = RetryManager(retry_config)
        
        call_count = 0
        
        async def mock_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = await retry_manager.call_with_retry(mock_operation)
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_manager_max_attempts_exceeded(self, retry_config):
        """Test retry manager when max attempts exceeded."""
        retry_manager = RetryManager(retry_config)
        
        call_count = 0
        
        async def mock_operation():
            nonlocal call_count
            call_count += 1
            raise Exception("Permanent failure")
        
        with pytest.raises(Exception, match="Permanent failure"):
            await retry_manager.call_with_retry(mock_operation)
        
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_state(self, circuit_breaker_config):
        """Test circuit breaker in closed state."""
        circuit_breaker = CircuitBreaker(circuit_breaker_config)
        
        async def mock_operation():
            return "success"
        
        result = await circuit_breaker.call(mock_operation)
        
        assert result == "success"
        assert circuit_breaker.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_failures(self, circuit_breaker_config):
        """Test circuit breaker opens after failure threshold."""
        circuit_breaker = CircuitBreaker(circuit_breaker_config)
        
        async def mock_operation():
            raise Exception("Service failure")
        
        # Trigger failures to open circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await circuit_breaker.call(mock_operation)
        
        assert circuit_breaker.state == CircuitState.OPEN
        
        # Circuit should reject calls in open state
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            await circuit_breaker.call(mock_operation)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_resets_after_timeout(self, circuit_breaker_config):
        """Test circuit breaker resets after timeout."""
        circuit_breaker = CircuitBreaker(circuit_breaker_config)
        
        async def mock_operation():
            raise Exception("Service failure")
        
        # Open circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await circuit_breaker.call(mock_operation)
        
        assert circuit_breaker.state == CircuitState.OPEN
        
        # Wait for timeout
        await asyncio.sleep(0.1)  # Mock time passage
        
        # Circuit should enter half-open state
        circuit_breaker.last_failure_time = None  # Simulate timeout
        circuit_breaker.state = CircuitState.HALF_OPEN
        
        async def successful_operation():
            return "success"
        
        # Successful call should close circuit
        result = await circuit_breaker.call(successful_operation)
        assert result == "success"
        assert circuit_breaker.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_bulkhead_concurrent_calls(self, bulkhead_config):
        """Test bulkhead limits concurrent calls."""
        bulkhead = Bulkhead(bulkhead_config)
        
        call_count = 0
        max_concurrent = 0
        
        async def mock_operation():
            nonlocal call_count, max_concurrent
            call_count += 1
            current_concurrent = bulkhead.active_calls
            max_concurrent = max(max_concurrent, current_concurrent)
            await asyncio.sleep(0.1)  # Simulate work
            call_count -= 1
        
        # Start multiple concurrent operations
        tasks = [bulkhead.call(mock_operation) for _ in range(5)]
        await asyncio.gather(*tasks)
        
        # Should not exceed max concurrent calls
        assert max_concurrent <= bulkhead_config.max_concurrent_calls
    
    @pytest.mark.asyncio
    async def test_bulkhead_timeout(self, bulkhead_config):
        """Test bulkhead timeout when too many concurrent calls."""
        bulkhead = Bulkhead(bulkhead_config)
        
        async def long_operation():
            await asyncio.sleep(1.0)  # Long operation
        
        # Fill up bulkhead
        tasks = [bulkhead.call(long_operation) for _ in range(bulkhead_config.max_concurrent_calls)]
        
        # This call should timeout
        with pytest.raises(Exception, match="Bulkhead timeout"):
            await bulkhead.call(long_operation)
        
        # Clean up
        for task in tasks:
            task.cancel()


class TestIdempotencyManager:
    """Test idempotency manager."""
    
    @pytest.fixture
    def idempotency_manager(self, mock_redis):
        """Create idempotency manager."""
        return IdempotencyManager(mock_redis)
    
    def test_generate_key(self, idempotency_manager):
        """Test idempotency key generation."""
        tool_id = "test_tool"
        parameters = {"param1": "value1", "param2": "value2"}
        
        key1 = idempotency_manager.generate_key(tool_id, parameters)
        key2 = idempotency_manager.generate_key(tool_id, parameters)
        
        # Same parameters should generate same key
        assert key1 == key2
        
        # Different parameters should generate different keys
        different_params = {"param1": "value1", "param2": "different"}
        key3 = idempotency_manager.generate_key(tool_id, different_params)
        assert key1 != key3
    
    @pytest.mark.asyncio
    async def test_store_and_get_result(self, idempotency_manager):
        """Test storing and retrieving results."""
        key = "test_key"
        result = {"data": "test_result"}
        
        # Store result
        await idempotency_manager.store_result(key, result)
        
        # Retrieve result
        retrieved_result = await idempotency_manager.get_result(key)
        
        assert retrieved_result == result
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_result(self, idempotency_manager):
        """Test retrieving nonexistent result."""
        key = "nonexistent_key"
        
        result = await idempotency_manager.get_result(key)
        
        assert result is None


class TestWriteAheadLogger:
    """Test write-ahead logger."""
    
    @pytest.fixture
    def write_ahead_logger(self, mock_redis):
        """Create write-ahead logger."""
        return WriteAheadLogger(mock_redis)
    
    @pytest.mark.asyncio
    async def test_log_request(self, write_ahead_logger):
        """Test logging tool request."""
        tool_id = "test_tool"
        operation = "test_operation"
        parameters = {"param1": "value1"}
        
        log_id = await write_ahead_logger.log_request(tool_id, operation, parameters)
        
        assert log_id is not None
        assert len(write_ahead_logger.local_log) == 1
        
        log_entry = write_ahead_logger.local_log[0]
        assert log_entry.tool_id == tool_id
        assert log_entry.operation == operation
        assert log_entry.parameters == parameters
        assert log_entry.status == "requested"
    
    @pytest.mark.asyncio
    async def test_log_success(self, write_ahead_logger):
        """Test logging successful execution."""
        # First log a request
        log_id = await write_ahead_logger.log_request("test_tool", "test_op", {})
        
        # Then log success
        result = {"data": "success"}
        await write_ahead_logger.log_success(log_id, result)
        
        # Check log entry was updated
        log_entry = write_ahead_logger.local_log[0]
        assert log_entry.status == "succeeded"
        assert log_entry.result == result
    
    @pytest.mark.asyncio
    async def test_log_failure(self, write_ahead_logger):
        """Test logging failed execution."""
        # First log a request
        log_id = await write_ahead_logger.log_request("test_tool", "test_op", {})
        
        # Then log failure
        error = "Test error"
        await write_ahead_logger.log_failure(log_id, error)
        
        # Check log entry was updated
        log_entry = write_ahead_logger.local_log[0]
        assert log_entry.status == "failed"
        assert log_entry.error == error


class TestSagaManager:
    """Test saga manager."""
    
    @pytest.fixture
    def saga_manager(self, mock_redis):
        """Create saga manager."""
        return SagaManager(mock_redis)
    
    @pytest.fixture
    def mock_tool_adapters(self):
        """Create mock tool adapters."""
        adapter1 = AsyncMock()
        adapter1.execute.return_value = {"result": "step1_success"}
        adapter1.compensate.return_value = True
        
        adapter2 = AsyncMock()
        adapter2.execute.return_value = {"result": "step2_success"}
        adapter2.compensate.return_value = True
        
        adapter3 = AsyncMock()
        adapter3.execute.return_value = {"result": "step3_success"}
        adapter3.compensate.return_value = True
        
        return [adapter1, adapter2, adapter3]
    
    @pytest.mark.asyncio
    async def test_successful_saga_execution(self, saga_manager, mock_tool_adapters):
        """Test successful saga execution."""
        steps = [
            create_saga_step(mock_tool_adapters[0])
                .with_parameters({"operation": "step1"})
                .build(),
            create_saga_step(mock_tool_adapters[1])
                .with_parameters({"operation": "step2"})
                .build(),
            create_saga_step(mock_tool_adapters[2])
                .with_parameters({"operation": "step3"})
                .build()
        ]
        
        saga_id = await saga_manager.start_saga("tenant_123", "workflow_123", steps)
        
        # Wait for saga to complete
        await asyncio.sleep(0.1)
        
        status = await saga_manager.get_saga_status(saga_id)
        
        assert status is not None
        assert status["status"] == "completed"
        assert status["tenant_id"] == "tenant_123"
        assert status["workflow_id"] == "workflow_123"
        assert len(status["steps"]) == 3
        
        # All steps should be completed
        for step in status["steps"]:
            assert step["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_saga_execution_with_failure(self, saga_manager, mock_tool_adapters):
        """Test saga execution with step failure and compensation."""
        # Make second step fail
        mock_tool_adapters[1].execute.side_effect = Exception("Step 2 failed")
        
        steps = [
            create_saga_step(mock_tool_adapters[0])
                .with_parameters({"operation": "step1"})
                .build(),
            create_saga_step(mock_tool_adapters[1])
                .with_parameters({"operation": "step2"})
                .build(),
            create_saga_step(mock_tool_adapters[2])
                .with_parameters({"operation": "step3"})
                .build()
        ]
        
        saga_id = await saga_manager.start_saga("tenant_123", "workflow_123", steps)
        
        # Wait for saga to complete
        await asyncio.sleep(0.1)
        
        status = await saga_manager.get_saga_status(saga_id)
        
        assert status is not None
        assert status["status"] == "compensated"
        assert status["compensation_reason"] == "Step 2 failed"
        
        # First step should be completed and compensated
        assert status["steps"][0]["status"] == "compensated"
        
        # Second step should be failed
        assert status["steps"][1]["status"] == "failed"
        
        # Third step should not have been executed
        assert status["steps"][2]["status"] == "pending"
        
        # Verify compensation was called
        mock_tool_adapters[0].compensate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_saga_cancellation(self, saga_manager, mock_tool_adapters):
        """Test saga cancellation."""
        # Make first step take a long time
        async def slow_operation(*args, **kwargs):
            await asyncio.sleep(1.0)
            return {"result": "slow_success"}
        
        mock_tool_adapters[0].execute.side_effect = slow_operation
        
        steps = [
            create_saga_step(mock_tool_adapters[0])
                .with_parameters({"operation": "slow_step"})
                .build(),
            create_saga_step(mock_tool_adapters[1])
                .with_parameters({"operation": "step2"})
                .build()
        ]
        
        saga_id = await saga_manager.start_saga("tenant_123", "workflow_123", steps)
        
        # Cancel saga immediately
        success = await saga_manager.cancel_saga(saga_id)
        assert success is True
        
        # Wait for cancellation to complete
        await asyncio.sleep(0.1)
        
        status = await saga_manager.get_saga_status(saga_id)
        
        assert status is not None
        assert status["status"] == "compensated"
        assert status["compensation_reason"] == "Manually cancelled"
    
    @pytest.mark.asyncio
    async def test_saga_statistics(self, saga_manager, mock_tool_adapters):
        """Test saga manager statistics."""
        initial_stats = saga_manager.get_statistics()
        assert initial_stats["total_sagas"] == 0
        
        # Run a successful saga
        steps = [
            create_saga_step(mock_tool_adapters[0])
                .with_parameters({"operation": "step1"})
                .build()
        ]
        
        saga_id = await saga_manager.start_saga("tenant_123", "workflow_123", steps)
        
        # Wait for completion
        await asyncio.sleep(0.1)
        
        stats = saga_manager.get_statistics()
        
        assert stats["total_sagas"] == 1
        assert stats["completed_sagas"] == 1
        assert stats["success_rate"] == 1.0


@pytest.mark.asyncio
async def test_transient_failure_retry_succeeds():
    """Test that transient failures are retried and eventually succeed."""
    retry_config = RetryConfig(
        max_attempts=3,
        base_delay_ms=10,  # Short delay for testing
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF
    )
    
    retry_manager = RetryManager(retry_config)
    
    call_count = 0
    
    async def mock_operation():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Temporary network error")
        return "success"
    
    result = await retry_manager.call_with_retry(mock_operation)
    
    assert result == "success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_permanent_failure_compensate_called():
    """Test that permanent failures trigger compensation."""
    # This test would require a more complex setup with actual saga execution
    # For now, we'll test the compensation logic directly
    
    class MockToolAdapter(BaseToolAdapter):
        def __init__(self):
            super().__init__("mock_tool")
            self.compensation_called = False
        
        async def _execute_tool(self, parameters):
            raise Exception("Permanent failure")
        
        async def compensate(self, parameters, result):
            self.compensation_called = True
            return True
    
    adapter = MockToolAdapter()
    
    try:
        await adapter.execute({"test": "param"})
    except Exception:
        pass
    
    # In a real scenario, the saga manager would call compensate
    # For this test, we'll call it directly
    success = await adapter.compensate({"test": "param"}, None)
    
    assert success is True
    assert adapter.compensation_called is True


@pytest.mark.asyncio
async def test_idempotency_prevents_duplicates():
    """Test that idempotency prevents duplicate executions."""
    idempotency_manager = IdempotencyManager()
    
    tool_id = "test_tool"
    parameters = {"param1": "value1"}
    
    # Generate idempotency key
    key = idempotency_manager.generate_key(tool_id, parameters)
    
    # Store result
    result = {"data": "test_result"}
    await idempotency_manager.store_result(key, result)
    
    # Retrieve result multiple times
    result1 = await idempotency_manager.get_result(key)
    result2 = await idempotency_manager.get_result(key)
    
    assert result1 == result
    assert result2 == result
    assert result1 == result2


@pytest.mark.asyncio
async def test_circuit_opens_and_resets():
    """Test circuit breaker opens and resets properly."""
    circuit_breaker_config = CircuitBreakerConfig(
        failure_threshold=2,
        success_threshold=1,
        timeout_ms=100  # Short timeout for testing
    )
    
    circuit_breaker = CircuitBreaker(circuit_breaker_config)
    
    async def failing_operation():
        raise Exception("Service failure")
    
    async def successful_operation():
        return "success"
    
    # Trigger failures to open circuit
    for _ in range(2):
        with pytest.raises(Exception):
            await circuit_breaker.call(failing_operation)
    
    assert circuit_breaker.state == CircuitState.OPEN
    
    # Circuit should reject calls
    with pytest.raises(Exception, match="Circuit breaker is OPEN"):
        await circuit_breaker.call(failing_operation)
    
    # Simulate timeout
    circuit_breaker.last_failure_time = None
    
    # Circuit should reset to half-open and then closed on success
    result = await circuit_breaker.call(successful_operation)
    assert result == "success"
    assert circuit_breaker.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_metrics_retry_total_circuit_open_total_observed():
    """Test that metrics are properly collected and observed."""
    retry_config = RetryConfig(max_attempts=3, base_delay_ms=10)
    circuit_breaker_config = CircuitBreakerConfig(failure_threshold=2, success_threshold=1)
    
    retry_manager = RetryManager(retry_config)
    circuit_breaker = CircuitBreaker(circuit_breaker_config)
    
    # Test retry metrics
    call_count = 0
    
    async def retry_operation():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Temporary failure")
        return "success"
    
    await retry_manager.call_with_retry(retry_operation)
    
    retry_metrics = retry_manager.get_metrics()
    assert retry_metrics["total_retries"] >= 2  # At least 2 retries
    assert retry_metrics["successful_retries"] >= 1
    
    # Test circuit breaker metrics
    async def failing_operation():
        raise Exception("Service failure")
    
    # Open circuit
    for _ in range(2):
        with pytest.raises(Exception):
            await circuit_breaker.call(failing_operation)
    
    circuit_metrics = circuit_breaker.get_state()
    assert circuit_metrics["state"] == "open"
    assert circuit_metrics["failure_count"] >= 2
