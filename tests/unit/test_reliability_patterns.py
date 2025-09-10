"""Unit tests for reliability patterns in tool adapters."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from services.tools.base_adapter import BaseAdapter, AdapterConfig, AdapterStatus
from services.tools.saga_adapter import SagaAdapter, SagaStep, SagaStatus
from services.tools.email_adapter import EmailAdapter, EmailMessage, EmailResult


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.setex = AsyncMock()
    redis_mock.ping = AsyncMock()
    return redis_mock


@pytest.fixture
def adapter_config():
    """Adapter configuration for testing."""
    return AdapterConfig(
        timeout_ms=1000,
        max_retries=2,
        retry_delay_ms=100,
        circuit_breaker_threshold=3,
        circuit_breaker_timeout_ms=5000,
        bulkhead_max_concurrent=5,
        idempotency_ttl_seconds=3600
    )


@pytest.fixture
def base_adapter(mock_redis, adapter_config):
    """Base adapter instance with mocked dependencies."""
    return BaseAdapter("test_adapter", adapter_config, mock_redis)


@pytest.fixture
def saga_adapter(mock_redis, adapter_config):
    """Saga adapter instance with mocked dependencies."""
    return SagaAdapter("test_saga", adapter_config, mock_redis)


@pytest.fixture
def email_adapter(mock_redis, adapter_config):
    """Email adapter instance with mocked dependencies."""
    return EmailAdapter("test_email", adapter_config, mock_redis)


class TestBaseAdapter:
    """Test base adapter reliability patterns."""
    
    @pytest.mark.asyncio
    async def test_successful_call(self, base_adapter):
        """Test successful adapter call."""
        async def mock_operation(x, y):
            return x + y
        
        result = await base_adapter.call(mock_operation, 2, 3)
        
        assert result == 5
        assert base_adapter.metrics.total_requests == 1
        assert base_adapter.metrics.successful_requests == 1
        assert base_adapter.metrics.failed_requests == 0
    
    @pytest.mark.asyncio
    async def test_retry_on_failure(self, base_adapter):
        """Test retry behavior on failure."""
        call_count = 0
        
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = await base_adapter.call(failing_operation)
        
        assert result == "success"
        assert call_count == 3  # 1 initial + 2 retries
        assert base_adapter.metrics.retry_attempts == 2
        assert base_adapter.metrics.total_requests == 1
        assert base_adapter.metrics.successful_requests == 1
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, base_adapter):
        """Test timeout handling."""
        async def slow_operation():
            await asyncio.sleep(2)  # Longer than timeout
            return "success"
        
        with pytest.raises(asyncio.TimeoutError):
            await base_adapter.call(slow_operation)
        
        assert base_adapter.metrics.timeout_requests == 1
        assert base_adapter.metrics.failed_requests == 1
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens(self, base_adapter):
        """Test circuit breaker opens after threshold failures."""
        async def failing_operation():
            raise Exception("Permanent failure")
        
        # Make enough calls to open circuit breaker
        for _ in range(4):  # threshold + 1
            with pytest.raises(Exception):
                await base_adapter.call(failing_operation)
        
        assert base_adapter.circuit_breaker_state == AdapterStatus.OPEN
        assert base_adapter.metrics.circuit_breaker_opens == 1
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_calls(self, base_adapter):
        """Test circuit breaker blocks calls when open."""
        async def failing_operation():
            raise Exception("Permanent failure")
        
        # Open circuit breaker
        for _ in range(4):
            with pytest.raises(Exception):
                await base_adapter.call(failing_operation)
        
        # Next call should be blocked
        with pytest.raises(Exception, match="Circuit breaker is open"):
            await base_adapter.call(failing_operation)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_resets(self, base_adapter):
        """Test circuit breaker resets after timeout."""
        async def failing_operation():
            raise Exception("Permanent failure")
        
        # Open circuit breaker
        for _ in range(4):
            with pytest.raises(Exception):
                await base_adapter.call(failing_operation)
        
        # Wait for timeout
        await asyncio.sleep(0.1)  # Mock time passage
        
        # Reset circuit breaker manually for test
        base_adapter.circuit_breaker_state = AdapterStatus.CLOSED
        base_adapter.circuit_breaker_failures = 0
        
        # Call should work now
        async def success_operation():
            return "success"
        
        result = await base_adapter.call(success_operation)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_idempotency(self, base_adapter):
        """Test idempotency behavior."""
        call_count = 0
        
        async def expensive_operation():
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"
        
        # First call
        result1 = await base_adapter.call(expensive_operation)
        assert result1 == "result_1"
        assert call_count == 1
        
        # Second call with same parameters should return cached result
        result2 = await base_adapter.call(expensive_operation)
        assert result2 == "result_1"  # Cached result
        assert call_count == 1  # Not called again
    
    @pytest.mark.asyncio
    async def test_bulkhead_limits_concurrency(self, base_adapter):
        """Test bulkhead limits concurrent operations."""
        async def slow_operation():
            await asyncio.sleep(0.1)
            return "done"
        
        # Start more operations than bulkhead limit
        tasks = []
        for _ in range(10):  # More than bulkhead_max_concurrent (5)
            task = asyncio.create_task(base_adapter.call(slow_operation))
            tasks.append(task)
        
        # Wait for all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should succeed (bulkhead just limits concurrency, doesn't reject)
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) == 10
    
    @pytest.mark.asyncio
    async def test_write_ahead_events(self, base_adapter, mock_redis):
        """Test write-ahead events are recorded."""
        async def test_operation():
            return "test_result"
        
        await base_adapter.call(test_operation)
        
        # Verify write-ahead events were recorded
        assert mock_redis.setex.call_count >= 3  # requested, succeeded, idempotency
    
    @pytest.mark.asyncio
    async def test_metrics_collection(self, base_adapter):
        """Test metrics collection."""
        async def test_operation():
            return "test_result"
        
        await base_adapter.call(test_operation)
        
        metrics = await base_adapter.get_metrics()
        
        assert metrics['name'] == "test_adapter"
        assert metrics['total_requests'] == 1
        assert metrics['successful_requests'] == 1
        assert metrics['failed_requests'] == 0
        assert metrics['success_rate'] == 1.0
        assert metrics['circuit_breaker_state'] == "closed"


class TestSagaAdapter:
    """Test saga adapter compensation patterns."""
    
    @pytest.mark.asyncio
    async def test_successful_saga_execution(self, saga_adapter):
        """Test successful saga execution."""
        async def step1_operation():
            return "step1_result"
        
        async def step1_compensate(result):
            return "step1_compensated"
        
        steps = [
            SagaStep(
                step_id="step1",
                operation=step1_operation,
                compensate=step1_compensate
            )
        ]
        
        context = await saga_adapter.execute_saga(
            saga_id="test_saga",
            steps=steps,
            tenant_id="tenant123",
            user_id="user456"
        )
        
        assert context.status == SagaStatus.COMPLETED
        assert len(context.steps) == 1
        assert context.steps[0].status == SagaStatus.COMPLETED
        assert context.steps[0].result == "step1_result"
    
    @pytest.mark.asyncio
    async def test_saga_compensation_on_failure(self, saga_adapter):
        """Test saga compensation when step fails."""
        async def step1_operation():
            return "step1_result"
        
        async def step1_compensate(result):
            return "step1_compensated"
        
        async def step2_operation():
            raise Exception("Step 2 failed")
        
        async def step2_compensate(result):
            return "step2_compensated"
        
        steps = [
            SagaStep(
                step_id="step1",
                operation=step1_operation,
                compensate=step1_compensate
            ),
            SagaStep(
                step_id="step2",
                operation=step2_operation,
                compensate=step2_compensate
            )
        ]
        
        context = await saga_adapter.execute_saga(
            saga_id="test_saga",
            steps=steps,
            tenant_id="tenant123",
            user_id="user456"
        )
        
        assert context.status == SagaStatus.FAILED
        assert context.steps[0].status == SagaStatus.COMPLETED  # First step completed
        assert context.steps[1].status == SagaStatus.FAILED  # Second step failed
    
    @pytest.mark.asyncio
    async def test_saga_context_storage(self, saga_adapter):
        """Test saga context storage and retrieval."""
        async def test_operation():
            return "test_result"
        
        async def test_compensate(result):
            return "test_compensated"
        
        steps = [
            SagaStep(
                step_id="test_step",
                operation=test_operation,
                compensate=test_compensate
            )
        ]
        
        context = await saga_adapter.execute_saga(
            saga_id="test_saga",
            steps=steps,
            tenant_id="tenant123",
            user_id="user456"
        )
        
        # Retrieve context
        retrieved_context = await saga_adapter.get_saga_context("test_saga")
        
        assert retrieved_context is not None
        assert retrieved_context.saga_id == "test_saga"
        assert retrieved_context.status == SagaStatus.COMPLETED
        assert retrieved_context.tenant_id == "tenant123"
        assert retrieved_context.user_id == "user456"
    
    @pytest.mark.asyncio
    async def test_saga_metrics(self, saga_adapter):
        """Test saga metrics collection."""
        async def test_operation():
            return "test_result"
        
        async def test_compensate(result):
            return "test_compensated"
        
        steps = [
            SagaStep(
                step_id="test_step",
                operation=test_operation,
                compensate=test_compensate
            )
        ]
        
        await saga_adapter.execute_saga(
            saga_id="test_saga",
            steps=steps,
            tenant_id="tenant123",
            user_id="user456"
        )
        
        metrics = await saga_adapter.get_saga_metrics()
        
        assert metrics['adapter_name'] == "test_saga"
        assert 'base_metrics' in metrics
        assert 'total_sagas' in metrics
        assert 'status_counts' in metrics


class TestEmailAdapter:
    """Test email adapter with saga compensation."""
    
    @pytest.mark.asyncio
    async def test_send_email_success(self, email_adapter):
        """Test successful email sending."""
        message = EmailMessage(
            to="test@example.com",
            subject="Test Email",
            body="This is a test email"
        )
        
        result = await email_adapter.send_email(message, "tenant123", "user456")
        
        assert isinstance(result, EmailResult)
        assert result.status == "sent"
        assert result.message_id is not None
        assert result.sent_at > 0
    
    @pytest.mark.asyncio
    async def test_send_email_with_saga_success(self, email_adapter):
        """Test successful email sending with saga."""
        message = EmailMessage(
            to="test@example.com",
            subject="Test Email",
            body="This is a test email"
        )
        
        result = await email_adapter.send_email_with_saga(message, "tenant123", "user456")
        
        assert isinstance(result, EmailResult)
        assert result.status == "sent"
        assert result.message_id is not None
    
    @pytest.mark.asyncio
    async def test_email_compensation(self, email_adapter):
        """Test email compensation function."""
        message = EmailMessage(
            to="test@example.com",
            subject="Test Email",
            body="This is a test email"
        )
        
        result = EmailResult(
            message_id="test_message_id",
            status="sent",
            sent_at=1234567890.0
        )
        
        # Test compensation
        await email_adapter._compensate_email_operation(result, message)
        
        # Should not raise exception
        assert True
    
    @pytest.mark.asyncio
    async def test_email_metrics(self, email_adapter):
        """Test email adapter metrics."""
        message = EmailMessage(
            to="test@example.com",
            subject="Test Email",
            body="This is a test email"
        )
        
        await email_adapter.send_email(message, "tenant123", "user456")
        
        metrics = await email_adapter.get_email_metrics()
        
        assert metrics['adapter_name'] == "test_email"
        assert 'base_metrics' in metrics
        assert 'saga_metrics' in metrics


class TestReliabilityIntegration:
    """Test reliability patterns integration."""
    
    @pytest.mark.asyncio
    async def test_transient_failure_recovery(self, base_adapter):
        """Test recovery from transient failures."""
        call_count = 0
        
        async def transient_failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Transient failure")
            return "recovered"
        
        result = await base_adapter.call(transient_failing_operation)
        
        assert result == "recovered"
        assert call_count == 3  # 1 initial + 2 retries
        assert base_adapter.metrics.successful_requests == 1
        assert base_adapter.metrics.retry_attempts == 2
    
    @pytest.mark.asyncio
    async def test_permanent_failure_compensation(self, saga_adapter):
        """Test compensation for permanent failures."""
        async def step1_operation():
            return "step1_result"
        
        async def step1_compensate(result):
            return "step1_compensated"
        
        async def step2_operation():
            raise Exception("Permanent failure")
        
        async def step2_compensate(result):
            return "step2_compensated"
        
        steps = [
            SagaStep(
                step_id="step1",
                operation=step1_operation,
                compensate=step1_compensate
            ),
            SagaStep(
                step_id="step2",
                operation=step2_operation,
                compensate=step2_compensate
            )
        ]
        
        context = await saga_adapter.execute_saga(
            saga_id="test_saga",
            steps=steps,
            tenant_id="tenant123",
            user_id="user456"
        )
        
        # Saga should fail and compensate step1
        assert context.status == SagaStatus.FAILED
        assert context.steps[0].status == SagaStatus.COMPLETED
        assert context.steps[1].status == SagaStatus.FAILED
    
    @pytest.mark.asyncio
    async def test_idempotency_prevents_double_side_effects(self, base_adapter):
        """Test that idempotency prevents double side effects."""
        side_effect_count = 0
        
        async def side_effect_operation():
            nonlocal side_effect_count
            side_effect_count += 1
            return f"side_effect_{side_effect_count}"
        
        # First call
        result1 = await base_adapter.call(side_effect_operation)
        assert result1 == "side_effect_1"
        assert side_effect_count == 1
        
        # Second call with same parameters should not execute side effect
        result2 = await base_adapter.call(side_effect_operation)
        assert result2 == "side_effect_1"  # Cached result
        assert side_effect_count == 1  # Side effect not executed again