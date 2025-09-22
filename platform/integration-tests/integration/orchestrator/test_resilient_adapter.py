"""Test resilient adapter functionality."""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch

from libs.adapters.resilient_adapter import (
    ResilientAdapter,
    CircuitBreakerState,
    CircuitBreakerOpenError,
    BulkheadRejectError,
    resilient,
    create_database_adapter,
    create_api_adapter,
    create_llm_adapter,
)


class TestResilientAdapter:
    """Test ResilientAdapter functionality."""

    @pytest.fixture
    def adapter(self):
        """Create ResilientAdapter instance."""
        return ResilientAdapter(
            name="test_adapter",
            timeout=1.0,
            max_retries=3,
            base_delay=0.1,
            max_delay=1.0,
            circuit_breaker_config={
                "failure_threshold": 3,
                "recovery_timeout": 1.0,
            },
            bulkhead_size=2,
        )

    @pytest.mark.asyncio
    async def test_successful_execution(self, adapter):
        """Test successful function execution."""
        async def mock_function():
            return "success"

        result = await adapter.execute(mock_function)

        assert result == "success"
        assert adapter.stats["total_requests"] == 1
        assert adapter.stats["successful_requests"] == 1
        assert adapter.stats["failed_requests"] == 0

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, adapter):
        """Test retry logic on function failure."""
        call_count = 0

        async def mock_function_with_failures():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"

        result = await adapter.execute(mock_function_with_failures)

        assert result == "success"
        assert call_count == 3
        assert adapter.stats["total_requests"] == 1
        assert adapter.stats["successful_requests"] == 1
        assert adapter.stats["retry_attempts"] == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, adapter):
        """Test behavior when max retries are exceeded."""
        call_count = 0

        async def mock_function_always_fails():
            nonlocal call_count
            call_count += 1
            raise Exception("Persistent failure")

        with pytest.raises(Exception, match="Persistent failure"):
            await adapter.execute(mock_function_always_fails)

        assert call_count == 4  # Initial + 3 retries
        assert adapter.stats["total_requests"] == 1
        assert adapter.stats["failed_requests"] == 1
        assert adapter.stats["retry_attempts"] == 3

    @pytest.mark.asyncio
    async def test_timeout_handling(self, adapter):
        """Test timeout handling."""
        async def mock_slow_function():
            await asyncio.sleep(2.0)  # Sleep longer than timeout
            return "success"

        with pytest.raises(asyncio.TimeoutError):
            await adapter.execute(mock_slow_function)

        assert adapter.stats["total_requests"] == 1
        assert adapter.stats["timeout_requests"] == 1
        assert adapter.stats["failed_requests"] == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens(self, adapter):
        """Test circuit breaker opening after failures."""
        async def mock_function_always_fails():
            raise Exception("Always fails")

        # Execute enough times to open circuit breaker
        for _ in range(3):
            with pytest.raises(Exception):
                await adapter.execute(mock_function_always_fails)

        # Circuit breaker should now be open
        assert adapter.circuit_state == CircuitBreakerState.OPEN
        assert adapter.failure_count >= 3

        # Next request should be rejected
        async def mock_function():
            return "success"

        with pytest.raises(CircuitBreakerOpenError):
            await adapter.execute(mock_function)

        assert adapter.stats["circuit_breaker_open"] == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self, adapter):
        """Test circuit breaker recovery from half-open state."""
        async def mock_function_always_fails():
            raise Exception("Always fails")

        # Open circuit breaker
        for _ in range(3):
            with pytest.raises(Exception):
                await adapter.execute(mock_function_always_fails)

        assert adapter.circuit_state == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # Next request should transition to half-open
        async def mock_success_function():
            return "success"

        result = await adapter.execute(mock_success_function)

        assert result == "success"
        assert adapter.circuit_state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_failure(self, adapter):
        """Test circuit breaker reopening from half-open state."""
        async def mock_function_always_fails():
            raise Exception("Always fails")

        # Open circuit breaker
        for _ in range(3):
            with pytest.raises(Exception):
                await adapter.execute(mock_function_always_fails)

        assert adapter.circuit_state == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # Next request should fail and reopen circuit breaker
        with pytest.raises(Exception):
            await adapter.execute(mock_function_always_fails)

        assert adapter.circuit_state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_bulkhead_capacity(self, adapter):
        """Test bulkhead capacity limiting."""
        async def mock_slow_function():
            await asyncio.sleep(0.5)
            return "success"

        # Start multiple concurrent requests
        tasks = []
        for _ in range(5):  # More than bulkhead size (2)
            task = asyncio.create_task(adapter.execute(mock_slow_function))
            tasks.append(task)

        # Wait a bit for some requests to be processed
        await asyncio.sleep(0.1)

        # Check that bulkhead rejections occurred
        assert adapter.stats["bulkhead_rejections"] > 0

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Some should succeed, some should be rejected
        successes = [r for r in results if r == "success"]
        rejections = [r for r in results if isinstance(r, BulkheadRejectError)]

        assert len(successes) > 0
        assert len(rejections) > 0

    @pytest.mark.asyncio
    async def test_get_stats(self, adapter):
        """Test getting adapter statistics."""
        async def mock_function():
            return "success"

        await adapter.execute(mock_function)

        stats = adapter.get_stats()

        assert "total_requests" in stats
        assert "successful_requests" in stats
        assert "failed_requests" in stats
        assert "timeout_requests" in stats
        assert "circuit_breaker_open" in stats
        assert "retry_attempts" in stats
        assert "bulkhead_rejections" in stats
        assert "circuit_breaker_state" in stats
        assert "failure_count" in stats
        assert "bulkhead_available" in stats
        assert "bulkhead_capacity" in stats

        assert stats["total_requests"] == 1
        assert stats["successful_requests"] == 1
        assert stats["circuit_breaker_state"] == CircuitBreakerState.CLOSED.value

    @pytest.mark.asyncio
    async def test_reset_stats(self, adapter):
        """Test resetting adapter statistics."""
        async def mock_function():
            return "success"

        await adapter.execute(mock_function)

        # Verify stats are populated
        assert adapter.stats["total_requests"] == 1

        # Reset stats
        adapter.reset_stats()

        # Verify stats are reset
        assert adapter.stats["total_requests"] == 0
        assert adapter.stats["successful_requests"] == 0
        assert adapter.failure_count == 0
        assert adapter.circuit_state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_resilient_decorator(self):
        """Test resilient decorator functionality."""
        @resilient(
            name="decorated_function",
            timeout=1.0,
            max_retries=2,
            base_delay=0.1,
            max_delay=1.0,
            circuit_breaker_config={
                "failure_threshold": 2,
                "recovery_timeout": 1.0,
            },
            bulkhead_size=1,
        )
        async def test_function():
            return "decorated_success"

        result = await test_function()

        assert result == "decorated_success"
        assert hasattr(test_function, "_adapter")
        assert test_function._adapter.name == "decorated_function"

    @pytest.mark.asyncio
    async def test_create_database_adapter(self):
        """Test creating database adapter."""
        adapter = create_database_adapter("test_db")

        assert adapter.name == "test_db"
        assert adapter.timeout == 30.0
        assert adapter.max_retries == 3
        assert adapter.bulkhead_size == 20
        assert adapter.failure_threshold == 5
        assert adapter.recovery_timeout == 60.0

    @pytest.mark.asyncio
    async def test_create_api_adapter(self):
        """Test creating API adapter."""
        adapter = create_api_adapter("test_api")

        assert adapter.name == "test_api"
        assert adapter.timeout == 45.0
        assert adapter.max_retries == 3
        assert adapter.bulkhead_size == 10
        assert adapter.failure_threshold == 3
        assert adapter.recovery_timeout == 120.0

    @pytest.mark.asyncio
    async def test_create_llm_adapter(self):
        """Test creating LLM adapter."""
        adapter = create_llm_adapter("test_llm")

        assert adapter.name == "test_llm"
        assert adapter.timeout == 120.0
        assert adapter.max_retries == 2
        assert adapter.bulkhead_size == 5
        assert adapter.failure_threshold == 3
        assert adapter.recovery_timeout == 300.0

    @pytest.mark.asyncio
    async def test_exponential_backoff(self, adapter):
        """Test exponential backoff in retry logic."""
        call_times = []

        async def mock_function_with_failures():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise Exception("Temporary failure")
            return "success"

        result = await adapter.execute(mock_function_with_failures)

        assert result == "success"
        assert len(call_times) == 3

        # Check that delays increased exponentially
        if len(call_times) >= 3:
            delay1 = call_times[1] - call_times[0]
            delay2 = call_times[2] - call_times[1]
            assert delay2 > delay1  # Second delay should be longer

    @pytest.mark.asyncio
    async def test_circuit_breaker_state_transitions(self, adapter):
        """Test circuit breaker state transitions."""
        async def mock_function_always_fails():
            raise Exception("Always fails")

        # Start in CLOSED state
        assert adapter.circuit_state == CircuitBreakerState.CLOSED

        # Fail enough times to open circuit breaker
        for _ in range(3):
            with pytest.raises(Exception):
                await adapter.execute(mock_function_always_fails)

        # Should be OPEN now
        assert adapter.circuit_state == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # Next request should transition to HALF_OPEN
        async def mock_function():
            return "success"

        result = await adapter.execute(mock_function)

        # Should be CLOSED after successful request
        assert result == "success"
        assert adapter.circuit_state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_concurrent_executions(self, adapter):
        """Test concurrent executions with bulkhead limiting."""
        async def mock_function():
            await asyncio.sleep(0.2)
            return "success"

        # Start multiple concurrent executions
        tasks = []
        for _ in range(4):  # More than bulkhead size (2)
            task = asyncio.create_task(adapter.execute(mock_function))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Some should succeed, some should be rejected due to bulkhead
        successes = [r for r in results if r == "success"]
        rejections = [r for r in results if isinstance(r, BulkheadRejectError)]

        assert len(successes) <= 2  # Bulkhead size
        assert len(rejections) >= 2  # Should have rejections
        assert len(successes) + len(rejections) == 4

    @pytest.mark.asyncio
    async def test_error_types_preservation(self, adapter):
        """Test that original error types are preserved."""
        async def mock_function():
            raise ValueError("Custom error")

        with pytest.raises(ValueError, match="Custom error"):
            await adapter.execute(mock_function)

        assert adapter.stats["failed_requests"] == 1
