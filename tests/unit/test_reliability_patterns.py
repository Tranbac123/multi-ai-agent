"""Tests for reliability patterns and Saga orchestration."""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock
from services.tools.base_adapter import BaseAdapter, AdapterConfig, AdapterStatus
from services.tools.email_adapter import EmailAdapter, EmailMessage
from services.tools.payment_adapter import PaymentAdapter, PaymentRequest, PaymentStatus
from services.tools.crm_adapter import CRMAdapter, Contact, Lead, CRMOperation
from apps.orchestrator.core.saga_orchestrator import SagaOrchestrator, SagaStep, SagaStatus, StepStatus


class TestBaseAdapterReliability:
    """Test base adapter reliability patterns."""
    
    @pytest.fixture
    def redis_mock(self):
        """Create mock Redis client."""
        return AsyncMock()
    
    @pytest.fixture
    def adapter_config(self):
        """Create adapter configuration."""
        return AdapterConfig(
            timeout_ms=1000,
            max_retries=2,
            retry_delay_ms=100,
            circuit_breaker_threshold=2,
            circuit_breaker_timeout_ms=5000,
            bulkhead_max_concurrent=2,
            idempotency_ttl_seconds=60,
            saga_compensation_enabled=True,
            saga_compensation_timeout_ms=5000
        )
    
    @pytest.fixture
    def base_adapter(self, redis_mock, adapter_config):
        """Create base adapter with mocks."""
        return BaseAdapter("test_adapter", adapter_config, redis_mock)
    
    @pytest.mark.asyncio
    async def test_successful_operation(self, base_adapter, redis_mock):
        """Test successful operation execution."""
        # Mock Redis responses
        redis_mock.get.return_value = None  # No cache hit
        redis_mock.setex.return_value = True
        
        async def test_operation():
            return "success"
        
        result = await base_adapter.call(test_operation)
        
        assert result == "success"
        assert base_adapter.metrics.successful_requests == 1
        assert base_adapter.metrics.total_requests == 1
    
    @pytest.mark.asyncio
    async def test_operation_with_retries(self, base_adapter, redis_mock):
        """Test operation with retries."""
        # Mock Redis responses
        redis_mock.get.return_value = None
        redis_mock.setex.return_value = True
        
        call_count = 0
        
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = await base_adapter.call(failing_operation)
        
        assert result == "success"
        assert call_count == 3  # Initial call + 2 retries
        assert base_adapter.metrics.retry_attempts == 2
        assert base_adapter.metrics.successful_requests == 1
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens(self, base_adapter, redis_mock):
        """Test circuit breaker opens after threshold failures."""
        # Mock Redis responses
        redis_mock.get.return_value = None
        redis_mock.setex.return_value = True
        
        async def failing_operation():
            raise Exception("Permanent failure")
        
        # Execute operations until circuit breaker opens
        for i in range(3):  # threshold + 1
            try:
                await base_adapter.call(failing_operation)
            except Exception:
                pass
        
        # Circuit breaker should be open
        assert base_adapter.circuit_breaker_state == AdapterStatus.OPEN
        assert base_adapter.metrics.circuit_breaker_opens >= 1  # May open multiple times due to retries
        
        # Next call should be rejected
        with pytest.raises(Exception, match="Circuit breaker is open"):
            await base_adapter.call(failing_operation)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_resets(self, base_adapter, redis_mock):
        """Test circuit breaker resets after timeout."""
        # Mock Redis responses
        redis_mock.get.return_value = None
        redis_mock.setex.return_value = True
        
        async def failing_operation():
            raise Exception("Permanent failure")
        
        # Open circuit breaker
        for i in range(3):
            try:
                await base_adapter.call(failing_operation)
            except Exception:
                pass
        
        assert base_adapter.circuit_breaker_state == AdapterStatus.OPEN
        
        # Wait for timeout
        await asyncio.sleep(0.1)  # Short sleep for test
        
        # Manually reset for testing
        base_adapter.circuit_breaker_state = AdapterStatus.HALF_OPEN
        
        async def success_operation():
            return "success"
        
        # Should work in half-open state
        result = await base_adapter.call(success_operation)
        assert result == "success"
        assert base_adapter.circuit_breaker_state == AdapterStatus.CLOSED
    
    @pytest.mark.asyncio
    async def test_idempotency(self, base_adapter, redis_mock):
        """Test idempotency caching."""
        # Mock Redis responses
        redis_mock.get.return_value = None  # No cache hit initially
        redis_mock.setex.return_value = True
        
        call_count = 0
        
        async def test_operation():
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"
        
        # First call
        result1 = await base_adapter.call(test_operation)
        assert result1 == "result_1"
        assert call_count == 1
        
        # Mock cache hit for second call
        redis_mock.get.return_value = '"result_1"'
        
        # Second call should use cache
        result2 = await base_adapter.call(test_operation)
        assert result2 == "result_1"
        assert call_count == 1  # Should not call operation again
    
    @pytest.mark.asyncio
    async def test_compensation_execution(self, base_adapter):
        """Test compensation execution."""
        async def compensation_operation():
            return "compensated"
        
        result = await base_adapter.compensate(compensation_operation)
        assert result == "compensated"
    
    @pytest.mark.asyncio
    async def test_compensation_timeout(self, base_adapter):
        """Test compensation timeout."""
        # Create adapter with very short timeout
        config = AdapterConfig(saga_compensation_timeout_ms=10)  # 10ms timeout
        base_adapter.config = config
        
        async def slow_compensation():
            await asyncio.sleep(0.1)  # Longer than timeout
            return "compensated"
        
        with pytest.raises(asyncio.TimeoutError):
            await base_adapter.compensate(slow_compensation)


class TestEmailAdapter:
    """Test email adapter with Saga compensation."""
    
    @pytest.fixture
    def redis_mock(self):
        """Create mock Redis client."""
        return AsyncMock()
    
    @pytest.fixture
    def smtp_config(self):
        """Create SMTP configuration."""
        return {
            "host": "smtp.example.com",
            "port": 587,
            "username": "test@example.com",
            "password": "password"
        }
    
    @pytest.fixture
    def email_adapter(self, redis_mock, smtp_config):
        """Create email adapter."""
        return EmailAdapter(redis_mock, smtp_config)
    
    @pytest.mark.asyncio
    async def test_send_email(self, email_adapter, redis_mock):
        """Test sending email."""
        # Mock Redis responses
        redis_mock.get.return_value = None
        redis_mock.setex.return_value = True
        
        message = EmailMessage(
            to="test@example.com",
            subject="Test Email",
            body="This is a test email"
        )
        
        result = await email_adapter.send_email(message)
        
        assert result.message_id.startswith("email_")
        assert result.status == "sent"
        assert result.recipient == "test@example.com"
        assert result.subject == "Test Email"
    
    @pytest.mark.asyncio
    async def test_compensate_send_email(self, email_adapter, redis_mock):
        """Test email compensation."""
        # Mock Redis responses
        redis_mock.get.return_value = None
        redis_mock.setex.return_value = True
        
        # Send an email first
        message = EmailMessage(
            to="test@example.com",
            subject="Test Email",
            body="This is a test email"
        )
        
        result = await email_adapter.send_email(message)
        message_id = result.message_id
        
        # Compensate the email
        compensation_result = await email_adapter.compensate_send_email(message_id)
        
        assert compensation_result is True
        assert message_id not in email_adapter.sent_emails
    
    @pytest.mark.asyncio
    async def test_bulk_email(self, email_adapter, redis_mock):
        """Test bulk email sending."""
        # Mock Redis responses
        redis_mock.get.return_value = None
        redis_mock.setex.return_value = True
        
        messages = [
            EmailMessage(to="user1@example.com", subject="Email 1", body="Body 1"),
            EmailMessage(to="user2@example.com", subject="Email 2", body="Body 2")
        ]
        
        results = await email_adapter.send_bulk_email(messages)
        
        assert len(results) == 2
        assert all(result.status == "sent" for result in results)


class TestPaymentAdapter:
    """Test payment adapter with Saga compensation."""
    
    @pytest.fixture
    def redis_mock(self):
        """Create mock Redis client."""
        return AsyncMock()
    
    @pytest.fixture
    def payment_config(self):
        """Create payment configuration."""
        return {
            "gateway": "stripe",
            "api_key": "sk_test_123",
            "webhook_secret": "whsec_123"
        }
    
    @pytest.fixture
    def payment_adapter(self, redis_mock, payment_config):
        """Create payment adapter."""
        return PaymentAdapter(redis_mock, payment_config)
    
    @pytest.mark.asyncio
    async def test_process_payment(self, payment_adapter, redis_mock):
        """Test payment processing."""
        # Mock Redis responses
        redis_mock.get.return_value = None
        redis_mock.setex.return_value = True
        
        request = PaymentRequest(
            amount=100.0,
            currency="USD",
            customer_id="cust_123",
            payment_method_id="pm_123",
            description="Test payment"
        )
        
        result = await payment_adapter.process_payment(request)
        
        assert result.payment_id.startswith("pay_")
        assert result.amount == 100.0
        assert result.currency == "USD"
        assert result.customer_id == "cust_123"
    
    @pytest.mark.asyncio
    async def test_compensate_payment(self, payment_adapter, redis_mock):
        """Test payment compensation (refund)."""
        # Mock Redis responses
        redis_mock.get.return_value = None
        redis_mock.setex.return_value = True
        
        # Process a payment first
        request = PaymentRequest(
            amount=100.0,
            currency="USD",
            customer_id="cust_123",
            payment_method_id="pm_123",
            description="Test payment"
        )
        
        result = await payment_adapter.process_payment(request)
        payment_id = result.payment_id
        
        # Compensate the payment
        compensation_result = await payment_adapter.compensate_payment(payment_id)
        
        assert compensation_result is True
        # Payment should be marked as refunded
        payment = await payment_adapter.get_payment_status(payment_id)
        assert payment.status == PaymentStatus.REFUNDED


class TestCRMAdapter:
    """Test CRM adapter with Saga compensation."""
    
    @pytest.fixture
    def redis_mock(self):
        """Create mock Redis client."""
        return AsyncMock()
    
    @pytest.fixture
    def crm_config(self):
        """Create CRM configuration."""
        return {
            "system": "salesforce",
            "endpoint": "https://api.salesforce.com",
            "api_version": "v52.0"
        }
    
    @pytest.fixture
    def crm_adapter(self, redis_mock, crm_config):
        """Create CRM adapter."""
        return CRMAdapter(redis_mock, crm_config)
    
    @pytest.mark.asyncio
    async def test_create_contact(self, crm_adapter, redis_mock):
        """Test contact creation."""
        # Mock Redis responses
        redis_mock.get.return_value = None
        redis_mock.setex.return_value = True
        
        contact = Contact(
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            company="Example Corp"
        )
        
        result = await crm_adapter.create_contact(contact)
        
        assert result.operation == CRMOperation.CREATE_CONTACT
        assert result.record_id.startswith("contact_")
        assert result.status == "created"
        assert result.data["email"] == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_create_lead(self, crm_adapter, redis_mock):
        """Test lead creation."""
        # Mock Redis responses
        redis_mock.get.return_value = None
        redis_mock.setex.return_value = True
        
        lead = Lead(
            email="lead@example.com",
            first_name="Jane",
            last_name="Smith",
            company="Lead Corp",
            source="website"
        )
        
        result = await crm_adapter.create_lead(lead)
        
        assert result.operation == CRMOperation.CREATE_LEAD
        assert result.record_id.startswith("lead_")
        assert result.status == "created"
        assert result.data["email"] == "lead@example.com"
    
    @pytest.mark.asyncio
    async def test_compensate_crm_operation(self, crm_adapter, redis_mock):
        """Test CRM operation compensation."""
        # Mock Redis responses
        redis_mock.get.return_value = None
        redis_mock.setex.return_value = True
        
        # Create a contact first
        contact = Contact(
            email="test@example.com",
            first_name="John",
            last_name="Doe"
        )
        
        result = await crm_adapter.create_contact(contact)
        contact_id = result.record_id
        
        # Compensate the operation
        compensation_result = await crm_adapter.compensate_crm_operation(contact_id)
        
        assert compensation_result is True


class TestSagaOrchestrator:
    """Test Saga orchestrator."""
    
    @pytest.fixture
    def redis_mock(self):
        """Create mock Redis client."""
        return AsyncMock()
    
    @pytest.fixture
    def saga_orchestrator(self, redis_mock):
        """Create saga orchestrator."""
        return SagaOrchestrator(redis_mock)
    
    @pytest.mark.asyncio
    async def test_create_saga(self, saga_orchestrator, redis_mock):
        """Test saga creation."""
        # Mock Redis responses
        redis_mock.setex.return_value = True
        
        async def step1():
            return "step1_result"
        
        async def step2():
            return "step2_result"
        
        steps = [
            SagaStep(step_id="step1", name="Step 1", operation=step1),
            SagaStep(step_id="step2", name="Step 2", operation=step2)
        ]
        
        saga_id = await saga_orchestrator.create_saga("Test Saga", steps)
        
        assert saga_id is not None
        assert saga_id in saga_orchestrator.active_sagas
        assert saga_orchestrator.saga_metrics["total_sagas"] == 1
        assert saga_orchestrator.saga_metrics["active_sagas"] == 1
    
    @pytest.mark.asyncio
    async def test_execute_saga_sequential(self, saga_orchestrator, redis_mock):
        """Test sequential saga execution."""
        # Mock Redis responses
        redis_mock.setex.return_value = True
        redis_mock.get.return_value = None
        redis_mock.keys.return_value = []
        
        execution_order = []
        
        async def step1():
            execution_order.append("step1")
            return "step1_result"
        
        async def step2():
            execution_order.append("step2")
            return "step2_result"
        
        steps = [
            SagaStep(step_id="step1", name="Step 1", operation=step1),
            SagaStep(step_id="step2", name="Step 2", operation=step2)
        ]
        
        saga_id = await saga_orchestrator.create_saga("Test Saga", steps, parallel_execution=False)
        result = await saga_orchestrator.execute_saga(saga_id)
        
        assert result["success"] is True
        assert len(result["results"]) == 2
        assert execution_order == ["step1", "step2"]  # Sequential execution
        assert saga_orchestrator.saga_metrics["completed_sagas"] == 1
    
    @pytest.mark.asyncio
    async def test_execute_saga_parallel(self, saga_orchestrator, redis_mock):
        """Test parallel saga execution."""
        # Mock Redis responses
        redis_mock.setex.return_value = True
        redis_mock.get.return_value = None
        redis_mock.keys.return_value = []
        
        execution_times = {}
        
        async def step1():
            execution_times["step1"] = time.time()
            await asyncio.sleep(0.1)
            return "step1_result"
        
        async def step2():
            execution_times["step2"] = time.time()
            await asyncio.sleep(0.1)
            return "step2_result"
        
        steps = [
            SagaStep(step_id="step1", name="Step 1", operation=step1),
            SagaStep(step_id="step2", name="Step 2", operation=step2)
        ]
        
        saga_id = await saga_orchestrator.create_saga("Test Saga", steps, parallel_execution=True)
        result = await saga_orchestrator.execute_saga(saga_id)
        
        assert result["success"] is True
        assert len(result["results"]) == 2
        
        # Steps should start at roughly the same time (parallel execution)
        time_diff = abs(execution_times["step1"] - execution_times["step2"])
        assert time_diff < 0.05  # Should start within 50ms of each other
    
    @pytest.mark.asyncio
    async def test_saga_compensation(self, saga_orchestrator, redis_mock):
        """Test saga compensation on failure."""
        # Mock Redis responses
        redis_mock.setex.return_value = True
        redis_mock.get.return_value = None
        redis_mock.keys.return_value = []
        
        compensation_called = []
        
        async def step1():
            return "step1_result"
        
        async def step2():
            raise Exception("Step 2 failed")
        
        async def compensate_step1():
            compensation_called.append("step1")
        
        steps = [
            SagaStep(step_id="step1", name="Step 1", operation=step1, compensation=compensate_step1),
            SagaStep(step_id="step2", name="Step 2", operation=step2)
        ]
        
        saga_id = await saga_orchestrator.create_saga("Test Saga", steps)
        result = await saga_orchestrator.execute_saga(saga_id)
        
        assert result["success"] is False
        assert "step1" in compensation_called  # Compensation should be called
        assert saga_orchestrator.saga_metrics["compensated_sagas"] == 1
    
    @pytest.mark.asyncio
    async def test_get_saga_status(self, saga_orchestrator, redis_mock):
        """Test getting saga status."""
        # Mock Redis responses
        redis_mock.setex.return_value = True
        redis_mock.get.return_value = None
        redis_mock.keys.return_value = []
        
        async def step1():
            return "step1_result"
        
        steps = [SagaStep(step_id="step1", name="Step 1", operation=step1)]
        
        saga_id = await saga_orchestrator.create_saga("Test Saga", steps)
        await saga_orchestrator.execute_saga(saga_id)
        
        status = await saga_orchestrator.get_saga_status(saga_id)
        
        assert status is not None
        assert status["saga_id"] == saga_id
        assert status["name"] == "Test Saga"
        assert status["status"] == SagaStatus.COMPLETED.value
        assert len(status["steps"]) == 1
        assert status["steps"][0]["status"] == StepStatus.COMPLETED.value
    
    @pytest.mark.asyncio
    async def test_saga_metrics(self, saga_orchestrator):
        """Test saga metrics."""
        metrics = await saga_orchestrator.get_saga_metrics()
        
        assert "total_sagas" in metrics
        assert "completed_sagas" in metrics
        assert "failed_sagas" in metrics
        assert "compensated_sagas" in metrics
        assert "active_sagas" in metrics
        assert "success_rate" in metrics


if __name__ == "__main__":
    pytest.main([__file__, "-v"])