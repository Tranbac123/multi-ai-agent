"""Unit tests for services/tools."""

import asyncio
import time
from unittest.mock import AsyncMock, patch
import pytest
from hypothesis import given, strategies as st

from services.tools.base_adapter import BaseAdapter, CircuitBreakerState
from services.tools.saga_adapter import SagaAdapter
from services.tools.email_adapter import EmailAdapter
from services.tools.payment_adapter import PaymentAdapter
from services.tools.crm_adapter import CRMAdapter


class TestBaseAdapter:
    """Test base adapter functionality."""

    @pytest.mark.asyncio
    async def test_retry_with_exponential_backoff(self):
        """Test retry mechanism with exponential backoff."""
        adapter = BaseAdapter(
            max_retries=3,
            base_delay=0.1,
            max_delay=1.0,
            backoff_multiplier=2.0
        )
        
        call_count = 0
        
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = await adapter._retry_with_backoff(failing_operation)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_max_attempts_exceeded(self):
        """Test retry when max attempts exceeded."""
        adapter = BaseAdapter(max_retries=2, base_delay=0.01)
        
        async def always_failing():
            raise Exception("Permanent failure")
        
        with pytest.raises(Exception, match="Permanent failure"):
            await adapter._retry_with_backoff(always_failing)

    @pytest.mark.asyncio
    async def test_circuit_breaker_open(self):
        """Test circuit breaker opens after failure threshold."""
        adapter = BaseAdapter(
            circuit_breaker_threshold=2,
            circuit_breaker_timeout=0.1
        )
        
        # Fail twice to open circuit breaker
        for _ in range(2):
            with pytest.raises(Exception):
                await adapter._execute_with_circuit_breaker(lambda: (_ for _ in ()).throw(Exception("Failure")))
        
        # Circuit should be open now
        assert adapter.circuit_breaker_state == CircuitBreakerState.OPEN
        
        # Should fail immediately without calling operation
        with pytest.raises(Exception, match="Circuit breaker is open"):
            await adapter._execute_with_circuit_breaker(lambda: "success")

    @pytest.mark.asyncio
    async def test_circuit_breaker_reset(self):
        """Test circuit breaker resets after timeout."""
        adapter = BaseAdapter(
            circuit_breaker_threshold=1,
            circuit_breaker_timeout=0.1
        )
        
        # Open circuit breaker
        with pytest.raises(Exception):
            await adapter._execute_with_circuit_breaker(lambda: (_ for _ in ()).throw(Exception("Failure")))
        
        # Wait for timeout
        await asyncio.sleep(0.2)
        
        # Should be in half-open state and allow one call
        result = await adapter._execute_with_circuit_breaker(lambda: "success")
        assert result == "success"

    @pytest.mark.asyncio
    async def test_idempotency_key_generation(self):
        """Test idempotency key generation."""
        adapter = BaseAdapter()
        
        key1 = adapter._generate_idempotency_key("operation", {"param": "value"})
        key2 = adapter._generate_idempotency_key("operation", {"param": "value"})
        key3 = adapter._generate_idempotency_key("operation", {"param": "different"})
        
        assert key1 == key2  # Same operation should generate same key
        assert key1 != key3  # Different params should generate different key

    @pytest.mark.asyncio
    async def test_idempotency_prevention(self):
        """Test idempotency prevents duplicate operations."""
        adapter = BaseAdapter()
        operation_called = 0
        
        async def operation():
            nonlocal operation_called
            operation_called += 1
            return "result"
        
        # First call
        result1 = await adapter._execute_with_idempotency("test_key", operation)
        assert result1 == "result"
        assert operation_called == 1
        
        # Second call with same key should return cached result
        result2 = await adapter._execute_with_idempotency("test_key", operation)
        assert result2 == "result"
        assert operation_called == 1  # Should not call operation again

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout handling."""
        adapter = BaseAdapter(timeout=0.1)
        
        async def slow_operation():
            await asyncio.sleep(0.2)
            return "result"
        
        with pytest.raises(asyncio.TimeoutError):
            await adapter._execute_with_timeout(slow_operation)

    @pytest.mark.asyncio
    async def test_bulkhead_isolation(self):
        """Test bulkhead pattern isolation."""
        adapter = BaseAdapter(max_concurrent_operations=2)
        
        # Start 3 operations, only 2 should run concurrently
        operations = []
        for i in range(3):
            async def op():
                await asyncio.sleep(0.1)
                return f"result_{i}"
            operations.append(adapter._execute_with_bulkhead(op))
        
        results = await asyncio.gather(*operations)
        assert len(results) == 3
        assert all(result.startswith("result_") for result in results)


class TestSagaAdapter:
    """Test saga adapter functionality."""

    @pytest.mark.asyncio
    async def test_saga_compensation(self):
        """Test saga compensation on failure."""
        saga = SagaAdapter()
        
        # Mock operations
        operations = []
        compensations = []
        
        async def op1():
            operations.append("op1")
            return "result1"
        
        async def comp1():
            compensations.append("comp1")
        
        async def op2():
            operations.append("op2")
            raise Exception("Failure")
        
        async def comp2():
            compensations.append("comp2")
        
        # Execute saga
        with pytest.raises(Exception, match="Failure"):
            await saga.execute_saga([
                (op1, comp1),
                (op2, comp2)
            ])
        
        # Verify operations and compensations
        assert operations == ["op1", "op2"]
        assert compensations == ["comp2", "comp1"]  # Reversed order

    @pytest.mark.asyncio
    async def test_saga_success_no_compensation(self):
        """Test saga success without compensation."""
        saga = SagaAdapter()
        
        operations = []
        
        async def op1():
            operations.append("op1")
            return "result1"
        
        async def op2():
            operations.append("op2")
            return "result2"
        
        # Execute saga
        result = await saga.execute_saga([
            (op1, None),
            (op2, None)
        ])
        
        assert result == ["result1", "result2"]
        assert operations == ["op1", "op2"]

    @pytest.mark.asyncio
    async def test_saga_partial_compensation(self):
        """Test saga with partial compensation."""
        saga = SagaAdapter()
        
        operations = []
        compensations = []
        
        async def op1():
            operations.append("op1")
            return "result1"
        
        async def comp1():
            compensations.append("comp1")
        
        async def op2():
            operations.append("op2")
            return "result2"
        
        async def op3():
            operations.append("op3")
            raise Exception("Failure")
        
        # Execute saga
        with pytest.raises(Exception, match="Failure"):
            await saga.execute_saga([
                (op1, comp1),
                (op2, None),
                (op3, None)
            ])
        
        # Only op1 should be compensated (op2 has no compensation)
        assert operations == ["op1", "op2", "op3"]
        assert compensations == ["comp1"]


class TestEmailAdapter:
    """Test email adapter functionality."""

    @pytest.mark.asyncio
    async def test_send_email_success(self):
        """Test successful email sending."""
        adapter = EmailAdapter()
        
        result = await adapter.send_email(
            to="test@example.com",
            subject="Test",
            body="Test message"
        )
        
        assert result["success"] is True
        assert "message_id" in result

    @pytest.mark.asyncio
    async def test_send_email_validation(self):
        """Test email validation."""
        adapter = EmailAdapter()
        
        with pytest.raises(ValueError, match="Invalid email"):
            await adapter.send_email(
                to="invalid-email",
                subject="Test",
                body="Test message"
            )

    @pytest.mark.asyncio
    async def test_send_email_retry(self):
        """Test email sending with retry."""
        adapter = EmailAdapter(max_retries=2, base_delay=0.01)
        
        # Mock failure then success
        with patch.object(adapter, '_send_email_internal') as mock_send:
            mock_send.side_effect = [Exception("Network error"), "success"]
            
            result = await adapter.send_email(
                to="test@example.com",
                subject="Test",
                body="Test message"
            )
            
            assert result["success"] is True
            assert mock_send.call_count == 2


class TestPaymentAdapter:
    """Test payment adapter functionality."""

    @pytest.mark.asyncio
    async def test_process_payment_success(self):
        """Test successful payment processing."""
        adapter = PaymentAdapter()
        
        result = await adapter.process_payment(
            amount=100.0,
            currency="USD",
            payment_method="card"
        )
        
        assert result["success"] is True
        assert "transaction_id" in result

    @pytest.mark.asyncio
    async def test_process_payment_validation(self):
        """Test payment validation."""
        adapter = PaymentAdapter()
        
        with pytest.raises(ValueError, match="Invalid amount"):
            await adapter.process_payment(
                amount=-100.0,
                currency="USD",
                payment_method="card"
            )

    @pytest.mark.asyncio
    async def test_refund_payment(self):
        """Test payment refund."""
        adapter = PaymentAdapter()
        
        # First process payment
        payment_result = await adapter.process_payment(
            amount=100.0,
            currency="USD",
            payment_method="card"
        )
        
        # Then refund
        refund_result = await adapter.refund_payment(
            transaction_id=payment_result["transaction_id"],
            amount=50.0
        )
        
        assert refund_result["success"] is True
        assert "refund_id" in refund_result


class TestCRMAdapter:
    """Test CRM adapter functionality."""

    @pytest.mark.asyncio
    async def test_create_lead_success(self):
        """Test successful lead creation."""
        adapter = CRMAdapter()
        
        result = await adapter.create_lead(
            name="John Doe",
            email="john@example.com",
            company="Acme Corp"
        )
        
        assert result["success"] is True
        assert "lead_id" in result

    @pytest.mark.asyncio
    async def test_update_lead(self):
        """Test lead update."""
        adapter = CRMAdapter()
        
        # Create lead
        create_result = await adapter.create_lead(
            name="John Doe",
            email="john@example.com",
            company="Acme Corp"
        )
        
        # Update lead
        update_result = await adapter.update_lead(
            lead_id=create_result["lead_id"],
            status="qualified"
        )
        
        assert update_result["success"] is True

    @pytest.mark.asyncio
    async def test_get_lead(self):
        """Test lead retrieval."""
        adapter = CRMAdapter()
        
        # Create lead
        create_result = await adapter.create_lead(
            name="John Doe",
            email="john@example.com",
            company="Acme Corp"
        )
        
        # Get lead
        lead = await adapter.get_lead(create_result["lead_id"])
        
        assert lead["success"] is True
        assert lead["data"]["name"] == "John Doe"


# Property-based tests
class TestToolsPropertyBased:
    """Property-based tests for tools."""

    @given(st.text(min_size=1, max_size=100))
    def test_idempotency_key_deterministic(self, operation_name):
        """Test idempotency key is deterministic."""
        adapter = BaseAdapter()
        
        key1 = adapter._generate_idempotency_key(operation_name, {"param": "value"})
        key2 = adapter._generate_idempotency_key(operation_name, {"param": "value"})
        
        assert key1 == key2

    @given(st.floats(min_value=0.1, max_value=1000.0))
    def test_cost_calculation_positive(self, amount):
        """Test cost calculation is always positive."""
        adapter = BaseAdapter()
        cost = adapter._calculate_cost(amount, 0.01)  # 1% fee
        assert cost >= 0

    @given(st.integers(min_value=1, max_value=10))
    def test_retry_attempts_respected(self, max_retries):
        """Test retry attempts are respected."""
        adapter = BaseAdapter(max_retries=max_retries)
        
        call_count = 0
        
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            raise Exception("Always fails")
        
        with pytest.raises(Exception):
            asyncio.run(adapter._retry_with_backoff(failing_operation))
        
        assert call_count == max_retries + 1  # Initial call + retries
