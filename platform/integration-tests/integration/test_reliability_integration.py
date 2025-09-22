"""Integration tests for reliability patterns."""

import pytest
import asyncio
from typing import Dict, Any

from services.tools.base_adapter import BaseAdapter, AdapterConfig
from services.tools.saga_adapter import SagaAdapter, SagaStep, SagaStatus
from services.tools.email_adapter import EmailAdapter, EmailMessage


@pytest.fixture
async def base_adapter_with_redis():
    """Base adapter instance with real Redis connection."""
    import redis.asyncio as redis

    redis_client = redis.Redis(
        host="localhost",
        port=6379,
        db=3,  # Use different DB for tests
        decode_responses=False,
    )

    config = AdapterConfig(
        timeout_ms=1000,
        max_retries=2,
        retry_delay_ms=100,
        circuit_breaker_threshold=3,
        circuit_breaker_timeout_ms=5000,
        bulkhead_max_concurrent=5,
        idempotency_ttl_seconds=3600,
    )

    adapter = BaseAdapter("test_adapter", config, redis_client)

    yield adapter

    # Cleanup
    await redis_client.flushdb()
    await redis_client.close()


@pytest.fixture
async def saga_adapter_with_redis():
    """Saga adapter instance with real Redis connection."""
    import redis.asyncio as redis

    redis_client = redis.Redis(
        host="localhost",
        port=6379,
        db=4,  # Use different DB for tests
        decode_responses=False,
    )

    config = AdapterConfig(
        timeout_ms=1000,
        max_retries=2,
        retry_delay_ms=100,
        circuit_breaker_threshold=3,
        circuit_breaker_timeout_ms=5000,
        bulkhead_max_concurrent=5,
        idempotency_ttl_seconds=3600,
    )

    adapter = SagaAdapter("test_saga", config, redis_client)

    yield adapter

    # Cleanup
    await redis_client.flushdb()
    await redis_client.close()


@pytest.fixture
async def email_adapter_with_redis():
    """Email adapter instance with real Redis connection."""
    import redis.asyncio as redis

    redis_client = redis.Redis(
        host="localhost",
        port=6379,
        db=5,  # Use different DB for tests
        decode_responses=False,
    )

    config = AdapterConfig(
        timeout_ms=1000,
        max_retries=2,
        retry_delay_ms=100,
        circuit_breaker_threshold=3,
        circuit_breaker_timeout_ms=5000,
        bulkhead_max_concurrent=5,
        idempotency_ttl_seconds=3600,
    )

    adapter = EmailAdapter("test_email", config, redis_client)

    yield adapter

    # Cleanup
    await redis_client.flushdb()
    await redis_client.close()


class TestReliabilityIntegration:
    """Integration tests for reliability patterns."""

    @pytest.mark.asyncio
    async def test_retry_then_success(self, base_adapter_with_redis):
        """Test retry behavior with real Redis."""
        call_count = 0

        async def failing_then_success_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"

        result = await base_adapter_with_redis.call(failing_then_success_operation)

        assert result == "success"
        assert call_count == 3  # 1 initial + 2 retries

        metrics = await base_adapter_with_redis.get_metrics()
        assert metrics["retry_attempts"] == 2
        assert metrics["successful_requests"] == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_and_resets(self, base_adapter_with_redis):
        """Test circuit breaker opens and resets with real Redis."""

        async def failing_operation():
            raise Exception("Permanent failure")

        # Open circuit breaker
        for _ in range(4):  # threshold + 1
            with pytest.raises(Exception):
                await base_adapter_with_redis.call(failing_operation)

        # Circuit breaker should be open
        metrics = await base_adapter_with_redis.get_metrics()
        assert metrics["circuit_breaker_state"] == "open"
        assert metrics["circuit_breaker_opens"] == 1

        # Reset circuit breaker manually for test
        base_adapter_with_redis.circuit_breaker_state = (
            base_adapter_with_redis.base_adapter.AdapterStatus.CLOSED
        )
        base_adapter_with_redis.circuit_breaker_failures = 0

        # Call should work now
        async def success_operation():
            return "success"

        result = await base_adapter_with_redis.call(success_operation)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_idempotency_with_redis(self, base_adapter_with_redis):
        """Test idempotency behavior with real Redis."""
        call_count = 0

        async def expensive_operation():
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"

        # First call
        result1 = await base_adapter_with_redis.call(expensive_operation)
        assert result1 == "result_1"
        assert call_count == 1

        # Second call with same parameters should return cached result
        result2 = await base_adapter_with_redis.call(expensive_operation)
        assert result2 == "result_1"  # Cached result
        assert call_count == 1  # Not called again

    @pytest.mark.asyncio
    async def test_bulkhead_concurrency_limit(self, base_adapter_with_redis):
        """Test bulkhead concurrency limit with real Redis."""

        async def slow_operation():
            await asyncio.sleep(0.1)
            return "done"

        # Start more operations than bulkhead limit
        tasks = []
        for _ in range(10):  # More than bulkhead_max_concurrent (5)
            task = asyncio.create_task(base_adapter_with_redis.call(slow_operation))
            tasks.append(task)

        # Wait for all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed (bulkhead just limits concurrency, doesn't reject)
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) == 10

    @pytest.mark.asyncio
    async def test_write_ahead_events_with_redis(self, base_adapter_with_redis):
        """Test write-ahead events with real Redis."""

        async def test_operation():
            return "test_result"

        await base_adapter_with_redis.call(test_operation)

        # Check that write-ahead events were stored in Redis
        event_keys = await base_adapter_with_redis.redis.keys("write_ahead_event:*")
        assert len(event_keys) >= 2  # requested and succeeded events

    @pytest.mark.asyncio
    async def test_saga_execution_with_redis(self, saga_adapter_with_redis):
        """Test saga execution with real Redis."""

        async def step1_operation():
            return "step1_result"

        async def step1_compensate(result):
            return "step1_compensated"

        async def step2_operation():
            return "step2_result"

        async def step2_compensate(result):
            return "step2_compensated"

        steps = [
            SagaStep(
                step_id="step1", operation=step1_operation, compensate=step1_compensate
            ),
            SagaStep(
                step_id="step2", operation=step2_operation, compensate=step2_compensate
            ),
        ]

        context = await saga_adapter_with_redis.execute_saga(
            saga_id="test_saga", steps=steps, tenant_id="tenant123", user_id="user456"
        )

        assert context.status == SagaStatus.COMPLETED
        assert len(context.steps) == 2
        assert context.steps[0].status == SagaStatus.COMPLETED
        assert context.steps[1].status == SagaStatus.COMPLETED
        assert context.steps[0].result == "step1_result"
        assert context.steps[1].result == "step2_result"

    @pytest.mark.asyncio
    async def test_saga_compensation_with_redis(self, saga_adapter_with_redis):
        """Test saga compensation with real Redis."""

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
                step_id="step1", operation=step1_operation, compensate=step1_compensate
            ),
            SagaStep(
                step_id="step2", operation=step2_operation, compensate=step2_compensate
            ),
        ]

        context = await saga_adapter_with_redis.execute_saga(
            saga_id="test_saga", steps=steps, tenant_id="tenant123", user_id="user456"
        )

        assert context.status == SagaStatus.FAILED
        assert context.steps[0].status == SagaStatus.COMPLETED
        assert context.steps[1].status == SagaStatus.FAILED

    @pytest.mark.asyncio
    async def test_saga_context_persistence(self, saga_adapter_with_redis):
        """Test saga context persistence with real Redis."""

        async def test_operation():
            return "test_result"

        async def test_compensate(result):
            return "test_compensated"

        steps = [
            SagaStep(
                step_id="test_step",
                operation=test_operation,
                compensate=test_compensate,
            )
        ]

        context = await saga_adapter_with_redis.execute_saga(
            saga_id="test_saga", steps=steps, tenant_id="tenant123", user_id="user456"
        )

        # Retrieve context from Redis
        retrieved_context = await saga_adapter_with_redis.get_saga_context("test_saga")

        assert retrieved_context is not None
        assert retrieved_context.saga_id == "test_saga"
        assert retrieved_context.status == SagaStatus.COMPLETED
        assert retrieved_context.tenant_id == "tenant123"
        assert retrieved_context.user_id == "user456"

    @pytest.mark.asyncio
    async def test_email_adapter_with_redis(self, email_adapter_with_redis):
        """Test email adapter with real Redis."""
        message = EmailMessage(
            to="test@example.com", subject="Test Email", body="This is a test email"
        )

        result = await email_adapter_with_redis.send_email(
            message, "tenant123", "user456"
        )

        assert result.status == "sent"
        assert result.message_id is not None
        assert result.sent_at > 0

    @pytest.mark.asyncio
    async def test_email_adapter_with_saga(self, email_adapter_with_redis):
        """Test email adapter with saga pattern."""
        message = EmailMessage(
            to="test@example.com", subject="Test Email", body="This is a test email"
        )

        result = await email_adapter_with_redis.send_email_with_saga(
            message, "tenant123", "user456"
        )

        assert result.status == "sent"
        assert result.message_id is not None

    @pytest.mark.asyncio
    async def test_email_metrics_with_redis(self, email_adapter_with_redis):
        """Test email adapter metrics with real Redis."""
        message = EmailMessage(
            to="test@example.com", subject="Test Email", body="This is a test email"
        )

        await email_adapter_with_redis.send_email(message, "tenant123", "user456")

        metrics = await email_adapter_with_redis.get_email_metrics()

        assert metrics["adapter_name"] == "test_email"
        assert "base_metrics" in metrics
        assert "saga_metrics" in metrics
        assert metrics["base_metrics"]["total_requests"] == 1
        assert metrics["base_metrics"]["successful_requests"] == 1

    @pytest.mark.asyncio
    async def test_end_to_end_reliability(
        self, base_adapter_with_redis, saga_adapter_with_redis
    ):
        """Test end-to-end reliability patterns."""
        # Test transient failure recovery
        call_count = 0

        async def transient_failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Transient failure")
            return "recovered"

        result = await base_adapter_with_redis.call(transient_failing_operation)
        assert result == "recovered"

        # Test saga compensation
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
                step_id="step1", operation=step1_operation, compensate=step1_compensate
            ),
            SagaStep(
                step_id="step2", operation=step2_operation, compensate=step2_compensate
            ),
        ]

        context = await saga_adapter_with_redis.execute_saga(
            saga_id="test_saga", steps=steps, tenant_id="tenant123", user_id="user456"
        )

        assert context.status == SagaStatus.FAILED
        assert context.steps[0].status == SagaStatus.COMPLETED
        assert context.steps[1].status == SagaStatus.FAILED

    @pytest.mark.asyncio
    async def test_metrics_aggregation(
        self, base_adapter_with_redis, saga_adapter_with_redis
    ):
        """Test metrics aggregation across adapters."""

        # Generate some activity
        async def test_operation():
            return "test_result"

        await base_adapter_with_redis.call(test_operation)

        # Get metrics
        base_metrics = await base_adapter_with_redis.get_metrics()
        saga_metrics = await saga_adapter_with_redis.get_saga_metrics()

        assert base_metrics["total_requests"] == 1
        assert base_metrics["successful_requests"] == 1
        assert base_metrics["success_rate"] == 1.0

        assert saga_metrics["adapter_name"] == "test_saga"
        assert "base_metrics" in saga_metrics
        assert "total_sagas" in saga_metrics
