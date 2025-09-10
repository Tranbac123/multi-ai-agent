"""Unit tests for reliability patterns and saga tests."""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
import redis.asyncio as redis

from services.tools.base_adapter import BaseAdapter, AdapterConfig, AdapterStatus
from services.tools.saga_adapter import SagaAdapter, SagaStep, SagaStatus, SagaContext
from services.tools.email_adapter import EmailAdapter, EmailMessage, EmailResult
from services.tools.payment_adapter import PaymentAdapter, PaymentRequest, PaymentResult, PaymentStatus
from services.tools.crm_adapter import CRMAdapter, CRMRecord, CRMResult, CRMStatus


@pytest.fixture
async def mock_redis():
    """Mock Redis client."""
    redis_mock = AsyncMock(spec=redis.Redis)
    redis_mock.get.return_value = None
    redis_mock.setex.return_value = True
    redis_mock.hset.return_value = True
    redis_mock.expire.return_value = True
    redis_mock.keys.return_value = []
    return redis_mock


@pytest.fixture
def adapter_config():
    """Adapter configuration for testing."""
    return AdapterConfig(
        timeout_ms=1000,
        max_retries=2,
        retry_delay_ms=100,
        circuit_breaker_threshold=3,
        circuit_breaker_timeout_ms=2000,
        bulkhead_max_concurrent=5,
        idempotency_ttl_seconds=3600
    )


class TestBaseAdapter:
    """Test base adapter reliability patterns."""
    
    @pytest.mark.asyncio
    async def test_successful_call(self, mock_redis, adapter_config):
        """Test successful adapter call."""
        adapter = BaseAdapter("test-adapter", adapter_config, mock_redis)
        
        async def test_operation():
            return "success"
        
        result = await adapter.call(test_operation)
        
        assert result == "success"
        assert adapter.metrics.total_requests == 1
        assert adapter.metrics.successful_requests == 1
        assert adapter.metrics.failed_requests == 0
    
    @pytest.mark.asyncio
    async def test_retry_on_failure(self, mock_redis, adapter_config):
        """Test retry on failure."""
        adapter = BaseAdapter("test-adapter", adapter_config, mock_redis)
        
        call_count = 0
        
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = await adapter.call(failing_operation)
        
        assert result == "success"
        assert call_count == 3
        assert adapter.metrics.total_requests == 1
        assert adapter.metrics.successful_requests == 1
        assert adapter.metrics.retry_attempts == 2
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens(self, mock_redis, adapter_config):
        """Test circuit breaker opens after threshold failures."""
        adapter = BaseAdapter("test-adapter", adapter_config, mock_redis)
        
        async def failing_operation():
            raise Exception("Permanent failure")
        
        # Make enough calls to open circuit breaker
        for _ in range(adapter_config.circuit_breaker_threshold + 1):
            try:
                await adapter.call(failing_operation)
            except Exception:
                pass
        
        # Circuit breaker should be open
        assert adapter.circuit_breaker_state == AdapterStatus.OPEN
        assert adapter.metrics.circuit_breaker_opens == 1
        
        # Next call should fail immediately
        with pytest.raises(Exception, match="Circuit breaker is open"):
            await adapter.call(failing_operation)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_resets(self, mock_redis, adapter_config):
        """Test circuit breaker resets after timeout."""
        adapter = BaseAdapter("test-adapter", adapter_config, mock_redis)
        
        async def failing_operation():
            raise Exception("Permanent failure")
        
        # Open circuit breaker
        for _ in range(adapter_config.circuit_breaker_threshold + 1):
            try:
                await adapter.call(failing_operation)
            except Exception:
                pass
        
        assert adapter.circuit_breaker_state == AdapterStatus.OPEN
        
        # Wait for timeout
        await asyncio.sleep(adapter_config.circuit_breaker_timeout_ms / 1000.0 + 0.1)
        
        # Circuit breaker should be half-open
        assert adapter.circuit_breaker_state == AdapterStatus.HALF_OPEN
        
        # Successful call should close circuit breaker
        async def successful_operation():
            return "success"
        
        result = await adapter.call(successful_operation)
        assert result == "success"
        assert adapter.circuit_breaker_state == AdapterStatus.CLOSED
    
    @pytest.mark.asyncio
    async def test_idempotency(self, mock_redis, adapter_config):
        """Test idempotency caching."""
        adapter = BaseAdapter("test-adapter", adapter_config, mock_redis)
        
        call_count = 0
        
        async def test_operation():
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"
        
        # First call
        result1 = await adapter.call(test_operation)
        assert result1 == "result_1"
        assert call_count == 1
        
        # Mock Redis to return cached result
        mock_redis.get.return_value = b'"cached_result"'
        
        # Second call should return cached result
        result2 = await adapter.call(test_operation)
        assert result2 == "cached_result"
        assert call_count == 1  # Operation not called again
    
    @pytest.mark.asyncio
    async def test_bulkhead_isolation(self, mock_redis, adapter_config):
        """Test bulkhead isolation."""
        adapter = BaseAdapter("test-adapter", adapter_config, mock_redis)
        
        async def slow_operation():
            await asyncio.sleep(0.1)
            return "success"
        
        # Start multiple concurrent calls
        tasks = []
        for _ in range(adapter_config.bulkhead_max_concurrent + 2):
            task = asyncio.create_task(adapter.call(slow_operation))
            tasks.append(task)
        
        # All should complete successfully
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check that all calls succeeded
        success_count = sum(1 for result in results if result == "success")
        assert success_count == adapter_config.bulkhead_max_concurrent + 2
    
    @pytest.mark.asyncio
    async def test_timeout(self, mock_redis, adapter_config):
        """Test operation timeout."""
        adapter = BaseAdapter("test-adapter", adapter_config, mock_redis)
        
        async def slow_operation():
            await asyncio.sleep(2.0)  # Longer than timeout
            return "success"
        
        with pytest.raises(asyncio.TimeoutError):
            await adapter.call(slow_operation)
        
        assert adapter.metrics.timeout_requests == 1


class TestSagaAdapter:
    """Test saga adapter."""
    
    @pytest.mark.asyncio
    async def test_successful_saga(self, mock_redis, adapter_config):
        """Test successful saga execution."""
        saga_adapter = SagaAdapter("test-saga", adapter_config, mock_redis)
        
        async def test_operation():
            return "success"
        
        async def test_compensate(result):
            return "compensated"
        
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
            tenant_id="tenant1",
            user_id="user1"
        )
        
        assert context.status == SagaStatus.COMPLETED
        assert len(context.steps) == 1
        assert context.steps[0].status == SagaStatus.COMPLETED
        assert context.steps[0].result == "success"
    
    @pytest.mark.asyncio
    async def test_saga_compensation(self, mock_redis, adapter_config):
        """Test saga compensation on failure."""
        saga_adapter = SagaAdapter("test-saga", adapter_config, mock_redis)
        
        async def failing_operation():
            raise Exception("Operation failed")
        
        async def test_compensate(result):
            return "compensated"
        
        steps = [
            SagaStep(
                step_id="test_step",
                operation=failing_operation,
                compensate=test_compensate
            )
        ]
        
        context = await saga_adapter.execute_saga(
            saga_id="test_saga",
            steps=steps,
            tenant_id="tenant1",
            user_id="user1"
        )
        
        assert context.status == SagaStatus.FAILED
        assert len(context.steps) == 1
        assert context.steps[0].status == SagaStatus.FAILED
        assert "Operation failed" in context.steps[0].error
    
    @pytest.mark.asyncio
    async def test_multi_step_saga_compensation(self, mock_redis, adapter_config):
        """Test multi-step saga with compensation."""
        saga_adapter = SagaAdapter("test-saga", adapter_config, mock_redis)
        
        async def successful_operation():
            return "success"
        
        async def failing_operation():
            raise Exception("Second step failed")
        
        async def test_compensate(result):
            return "compensated"
        
        steps = [
            SagaStep(
                step_id="step1",
                operation=successful_operation,
                compensate=test_compensate
            ),
            SagaStep(
                step_id="step2",
                operation=failing_operation,
                compensate=test_compensate
            )
        ]
        
        context = await saga_adapter.execute_saga(
            saga_id="test_saga",
            steps=steps,
            tenant_id="tenant1",
            user_id="user1"
        )
        
        assert context.status == SagaStatus.COMPENSATED
        assert len(context.steps) == 2
        assert context.steps[0].status == SagaStatus.COMPENSATED  # First step compensated
        assert context.steps[1].status == SagaStatus.FAILED  # Second step failed


class TestEmailAdapter:
    """Test email adapter."""
    
    @pytest.mark.asyncio
    async def test_send_email_success(self, mock_redis, adapter_config):
        """Test successful email sending."""
        email_adapter = EmailAdapter("email-adapter", adapter_config, mock_redis)
        
        message = EmailMessage(
            to="test@example.com",
            subject="Test Subject",
            body="Test Body"
        )
        
        result = await email_adapter.send_email(message, "tenant1", "user1")
        
        assert isinstance(result, EmailResult)
        assert result.status == "sent"
        assert result.message_id is not None
        assert result.sent_at > 0
    
    @pytest.mark.asyncio
    async def test_send_email_with_saga(self, mock_redis, adapter_config):
        """Test email sending with saga."""
        email_adapter = EmailAdapter("email-adapter", adapter_config, mock_redis)
        
        message = EmailMessage(
            to="test@example.com",
            subject="Test Subject",
            body="Test Body"
        )
        
        result = await email_adapter.send_email_with_saga(message, "tenant1", "user1")
        
        assert isinstance(result, EmailResult)
        assert result.status == "sent"
        assert result.message_id is not None


class TestPaymentAdapter:
    """Test payment adapter."""
    
    @pytest.mark.asyncio
    async def test_process_payment_success(self, mock_redis, adapter_config):
        """Test successful payment processing."""
        payment_adapter = PaymentAdapter("payment-adapter", adapter_config, mock_redis)
        
        request = PaymentRequest(
            amount=100.0,
            currency="USD",
            customer_id="customer1",
            order_id="order1"
        )
        
        result = await payment_adapter.process_payment(request, "tenant1", "user1")
        
        assert isinstance(result, PaymentResult)
        assert result.status == PaymentStatus.COMPLETED
        assert result.amount == 100.0
        assert result.currency == "USD"
        assert result.payment_id is not None
        assert result.transaction_id is not None
    
    @pytest.mark.asyncio
    async def test_process_payment_with_saga(self, mock_redis, adapter_config):
        """Test payment processing with saga."""
        payment_adapter = PaymentAdapter("payment-adapter", adapter_config, mock_redis)
        
        request = PaymentRequest(
            amount=100.0,
            currency="USD",
            customer_id="customer1",
            order_id="order1"
        )
        
        result = await payment_adapter.process_payment_with_saga(request, "tenant1", "user1")
        
        assert isinstance(result, PaymentResult)
        assert result.status == PaymentStatus.COMPLETED
        assert result.amount == 100.0


class TestCRMAdapter:
    """Test CRM adapter."""
    
    @pytest.mark.asyncio
    async def test_create_record_success(self, mock_redis, adapter_config):
        """Test successful CRM record creation."""
        crm_adapter = CRMAdapter("crm-adapter", adapter_config, mock_redis)
        
        record = CRMRecord(
            record_id="record1",
            record_type="lead",
            data={"name": "John Doe", "email": "john@example.com"},
            tenant_id="tenant1",
            user_id="user1"
        )
        
        result = await crm_adapter.create_record(record, "tenant1", "user1")
        
        assert isinstance(result, CRMResult)
        assert result.status == CRMStatus.COMPLETED
        assert result.record_id == "record1"
        assert result.crm_id is not None
    
    @pytest.mark.asyncio
    async def test_create_record_with_saga(self, mock_redis, adapter_config):
        """Test CRM record creation with saga."""
        crm_adapter = CRMAdapter("crm-adapter", adapter_config, mock_redis)
        
        record = CRMRecord(
            record_id="record1",
            record_type="lead",
            data={"name": "John Doe", "email": "john@example.com"},
            tenant_id="tenant1",
            user_id="user1"
        )
        
        result = await crm_adapter.create_record_with_saga(record, "tenant1", "user1")
        
        assert isinstance(result, CRMResult)
        assert result.status == CRMStatus.COMPLETED
        assert result.record_id == "record1"


class TestIntegration:
    """Integration tests for reliability patterns."""
    
    @pytest.mark.asyncio
    async def test_transient_failure_retry_then_success(self, mock_redis, adapter_config):
        """Test transient failure → retries then success."""
        adapter = BaseAdapter("test-adapter", adapter_config, mock_redis)
        
        call_count = 0
        
        async def transient_failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = await adapter.call(transient_failing_operation)
        
        assert result == "success"
        assert call_count == 3
        assert adapter.metrics.successful_requests == 1
        assert adapter.metrics.retry_attempts == 2
    
    @pytest.mark.asyncio
    async def test_permanent_failure_compensation_called(self, mock_redis, adapter_config):
        """Test permanent failure → compensation called."""
        saga_adapter = SagaAdapter("test-saga", adapter_config, mock_redis)
        
        compensation_called = False
        
        async def successful_operation():
            return "success"
        
        async def failing_operation():
            raise Exception("Permanent failure")
        
        async def test_compensate(result):
            nonlocal compensation_called
            compensation_called = True
            return "compensated"
        
        steps = [
            SagaStep(
                step_id="step1",
                operation=successful_operation,
                compensate=test_compensate
            ),
            SagaStep(
                step_id="step2",
                operation=failing_operation,
                compensate=test_compensate
            )
        ]
        
        context = await saga_adapter.execute_saga(
            saga_id="test_saga",
            steps=steps,
            tenant_id="tenant1",
            user_id="user1"
        )
        
        assert context.status == SagaStatus.COMPENSATED
        assert compensation_called
        assert context.steps[0].status == SagaStatus.COMPENSATED
    
    @pytest.mark.asyncio
    async def test_circuit_opens_and_later_resets(self, mock_redis, adapter_config):
        """Test circuit opens and later resets."""
        adapter = BaseAdapter("test-adapter", adapter_config, mock_redis)
        
        async def failing_operation():
            raise Exception("Permanent failure")
        
        # Open circuit breaker
        for _ in range(adapter_config.circuit_breaker_threshold + 1):
            try:
                await adapter.call(failing_operation)
            except Exception:
                pass
        
        assert adapter.circuit_breaker_state == AdapterStatus.OPEN
        
        # Wait for timeout
        await asyncio.sleep(adapter_config.circuit_breaker_timeout_ms / 1000.0 + 0.1)
        
        # Circuit breaker should be half-open
        assert adapter.circuit_breaker_state == AdapterStatus.HALF_OPEN
        
        # Successful call should close circuit breaker
        async def successful_operation():
            return "success"
        
        result = await adapter.call(successful_operation)
        assert result == "success"
        assert adapter.circuit_breaker_state == AdapterStatus.CLOSED
    
    @pytest.mark.asyncio
    async def test_idempotency_prevents_double_side_effect(self, mock_redis, adapter_config):
        """Test idempotency prevents double side-effect."""
        adapter = BaseAdapter("test-adapter", adapter_config, mock_redis)
        
        side_effect_count = 0
        
        async def side_effect_operation():
            nonlocal side_effect_count
            side_effect_count += 1
            return f"result_{side_effect_count}"
        
        # First call
        result1 = await adapter.call(side_effect_operation)
        assert result1 == "result_1"
        assert side_effect_count == 1
        
        # Mock Redis to return cached result
        mock_redis.get.return_value = b'"cached_result"'
        
        # Second call should return cached result without side effect
        result2 = await adapter.call(side_effect_operation)
        assert result2 == "cached_result"
        assert side_effect_count == 1  # No additional side effect


if __name__ == '__main__':
    pytest.main([__file__])
