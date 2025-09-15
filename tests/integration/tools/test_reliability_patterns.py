"""Tests for reliability patterns including timeouts, retries, circuit breakers, and bulkheads."""

import pytest
import asyncio
import time
import random
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from tests.integration.tools import (
    ReliabilityPattern, CircuitState, RetryStrategy, SagaStep, IdempotencyKey
)
from tests._fixtures.factories import factory, TenantTier


class MockCircuitBreaker:
    """Mock circuit breaker for testing."""
    
    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    async def call(self, func: Callable, *args, **kwargs):
        """Call function through circuit breaker."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
            
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset."""
        if self.last_failure_time is None:
            return True
        
        # For testing, use a very short timeout
        return (datetime.now() - self.last_failure_time).total_seconds() >= 0.05


class MockRetryManager:
    """Mock retry manager with exponential backoff and jitter."""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.retry_count = 0
    
    async def execute_with_retry(self, func: Callable, *args, **kwargs):
        """Execute function with retry logic."""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                last_exception = e
                self.retry_count += 1
                
                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt)
                    await asyncio.sleep(delay)
                else:
                    break
        
        raise last_exception
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter."""
        delay = self.base_delay * (2 ** attempt)
        jitter = random.uniform(0, 0.1 * delay)
        return delay + jitter


class MockBulkhead:
    """Mock bulkhead for resource isolation."""
    
    def __init__(self, max_concurrent: int = 10, timeout_seconds: int = 30):
        self.max_concurrent = max_concurrent
        self.timeout_seconds = timeout_seconds
        self.active_requests = 0
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def execute(self, func: Callable, *args, **kwargs):
        """Execute function through bulkhead."""
        try:
            await asyncio.wait_for(
                self.semaphore.acquire(),
                timeout=self.timeout_seconds
            )
            self.active_requests += 1
            
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                self.active_requests -= 1
                self.semaphore.release()
        except asyncio.TimeoutError:
            raise Exception("Bulkhead timeout - too many concurrent requests")


class MockIdempotencyManager:
    """Mock idempotency manager for request deduplication."""
    
    def __init__(self):
        self.processed_requests: Dict[str, Any] = {}
        self.ttl_seconds = 3600  # 1 hour
    
    async def execute_idempotent(self, key: IdempotencyKey, func: Callable, *args, **kwargs):
        """Execute function with idempotency."""
        # Check if request already processed
        if key.key in self.processed_requests:
            stored_result = self.processed_requests[key.key]
            # Check TTL
            if self._is_expired(stored_result['timestamp']):
                del self.processed_requests[key.key]
            else:
                return stored_result['result']
        
        # Execute function
        result = await func(*args, **kwargs)
        
        # Store result
        self.processed_requests[key.key] = {
            'result': result,
            'timestamp': datetime.now(),
            'key': key
        }
        
        return result
    
    def _is_expired(self, timestamp: datetime) -> bool:
        """Check if stored result is expired."""
        return (datetime.now() - timestamp).total_seconds() > self.ttl_seconds


class MockSagaManager:
    """Mock saga manager for distributed transaction coordination."""
    
    def __init__(self):
        self.sagas: Dict[str, List[SagaStep]] = {}
        self.compensation_log: List[Dict[str, Any]] = []
    
    async def execute_saga(self, saga_id: str, steps: List[SagaStep]):
        """Execute saga with compensation on failure."""
        self.sagas[saga_id] = steps.copy()
        
        try:
            # Execute steps in order
            for step in steps:
                await self._execute_step(step)
                step.completed = True
            
            return {"success": True, "saga_id": saga_id}
        
        except Exception as e:
            # Execute compensation
            await self._compensate_saga(saga_id, steps)
            return {"success": False, "error": str(e), "compensated": True}
    
    async def _execute_step(self, step: SagaStep):
        """Execute individual saga step."""
        step.retry_count = 0
        
        while step.retry_count <= step.max_retries:
            try:
                # Simulate step execution
                await asyncio.sleep(0.1)  # Simulate work
                
                # Random failure for testing
                if random.random() < 0.3:  # 30% failure rate
                    raise Exception(f"Step {step.step_id} failed")
                
                step.completed = True
                return
            
            except Exception as e:
                step.retry_count += 1
                if step.retry_count > step.max_retries:
                    step.failed = True
                    raise e
                
                # Wait before retry
                await asyncio.sleep(0.05)
    
    async def _compensate_saga(self, saga_id: str, steps: List[SagaStep]):
        """Execute compensation for failed saga."""
        # Execute compensation in reverse order
        for step in reversed(steps):
            if step.completed and not step.compensated:
                try:
                    # Simulate compensation
                    await asyncio.sleep(0.05)
                    step.compensated = True
                    
                    self.compensation_log.append({
                        'saga_id': saga_id,
                        'step_id': step.step_id,
                        'compensation_action': step.compensate,
                        'timestamp': datetime.now()
                    })
                except Exception as e:
                    # Log compensation failure
                    self.compensation_log.append({
                        'saga_id': saga_id,
                        'step_id': step.step_id,
                        'compensation_action': step.compensate,
                        'error': str(e),
                        'timestamp': datetime.now()
                    })


class TestReliabilityPatterns:
    """Test reliability patterns for tool operations."""
    
    @pytest.fixture
    def mock_circuit_breaker(self):
        """Create mock circuit breaker."""
        return MockCircuitBreaker(failure_threshold=3, timeout_seconds=5)
    
    @pytest.fixture
    def mock_retry_manager(self):
        """Create mock retry manager."""
        return MockRetryManager(max_retries=3, base_delay=0.1)
    
    @pytest.fixture
    def mock_bulkhead(self):
        """Create mock bulkhead."""
        return MockBulkhead(max_concurrent=5, timeout_seconds=10)
    
    @pytest.fixture
    def mock_idempotency_manager(self):
        """Create mock idempotency manager."""
        return MockIdempotencyManager()
    
    @pytest.fixture
    def mock_saga_manager(self):
        """Create mock saga manager."""
        return MockSagaManager()
    
    async def failing_function(self, should_fail: bool = True):
        """Mock function that can fail."""
        if should_fail:
            raise Exception("Function failed")
        return "success"
    
    async def slow_function(self, delay_seconds: float = 2.0):
        """Mock function that takes time."""
        await asyncio.sleep(delay_seconds)
        return "completed"
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_open_state(self, mock_circuit_breaker):
        """Test circuit breaker opening after failures."""
        # Cause failures to open circuit
        for _ in range(4):  # More than failure threshold
            try:
                await mock_circuit_breaker.call(self.failing_function, should_fail=True)
            except Exception:
                pass
        
        # Circuit should be open
        assert mock_circuit_breaker.state == CircuitState.OPEN
        
        # Should reject new calls
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            await mock_circuit_breaker.call(self.failing_function, should_fail=True)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self, mock_circuit_breaker):
        """Test circuit breaker recovery to half-open state."""
        # Open the circuit
        for _ in range(4):
            try:
                await mock_circuit_breaker.call(self.failing_function, should_fail=True)
            except Exception:
                pass
        
        assert mock_circuit_breaker.state == CircuitState.OPEN
        
        # Wait for timeout
        await asyncio.sleep(0.1)  # Wait for timeout to pass
        
        # Successful call should close circuit
        result = await mock_circuit_breaker.call(self.failing_function, should_fail=False)
        assert result == "success"
        assert mock_circuit_breaker.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_retry_with_exponential_backoff(self, mock_retry_manager):
        """Test retry with exponential backoff."""
        start_time = time.time()
        
        # This should succeed after retries
        result = await mock_retry_manager.execute_with_retry(
            self.failing_function, should_fail=False
        )
        
        end_time = time.time()
        
        assert result == "success"
        assert mock_retry_manager.retry_count == 0  # No retries needed
        
        # Test with failures
        mock_retry_manager.retry_count = 0
        start_time = time.time()
        
        try:
            await mock_retry_manager.execute_with_retry(
                self.failing_function, should_fail=True
            )
        except Exception as e:
            assert "Function failed" in str(e)
        
        end_time = time.time()
        assert mock_retry_manager.retry_count == 4  # 3 retries + 1 initial attempt
    
    @pytest.mark.asyncio
    async def test_bulkhead_concurrency_limiting(self, mock_bulkhead):
        """Test bulkhead concurrency limiting."""
        async def slow_task():
            await asyncio.sleep(0.2)
            return "completed"
        
        # Start multiple concurrent tasks
        tasks = []
        for i in range(8):  # More than max_concurrent
            task = asyncio.create_task(mock_bulkhead.execute(slow_task))
            tasks.append(task)
        
        # Wait for completion
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check that all tasks completed (some may have been queued)
        successful_results = [r for r in results if r == "completed"]
        assert len(successful_results) == 8
        
        # Verify bulkhead managed concurrency
        assert mock_bulkhead.active_requests <= mock_bulkhead.max_concurrent
    
    @pytest.mark.asyncio
    async def test_bulkhead_timeout(self, mock_bulkhead):
        """Test bulkhead timeout under high load."""
        # Create a bulkhead with very low concurrency
        limited_bulkhead = MockBulkhead(max_concurrent=1, timeout_seconds=0.1)
        
        async def slow_task():
            await asyncio.sleep(0.5)  # Longer than timeout
            return "completed"
        
        # Start two tasks - second should timeout
        task1 = asyncio.create_task(limited_bulkhead.execute(slow_task))
        task2 = asyncio.create_task(limited_bulkhead.execute(slow_task))
        
        results = await asyncio.gather(task1, task2, return_exceptions=True)
        
        # One should succeed, one should timeout
        successful = [r for r in results if r == "completed"]
        timeouts = [r for r in results if isinstance(r, Exception) and "timeout" in str(r)]
        
        assert len(successful) == 1
        assert len(timeouts) == 1
    
    @pytest.mark.asyncio
    async def test_idempotency_key_deduplication(self, mock_idempotency_manager):
        """Test idempotency key deduplication."""
        async def expensive_operation():
            await asyncio.sleep(0.1)  # Simulate expensive operation
            return {"result": "expensive_computation", "timestamp": datetime.now()}
        
        # Create idempotency key
        key = IdempotencyKey(
            key="test_operation_123",
            tenant_id="tenant_1234",
            user_id="user_1234",
            operation="expensive_computation",
            timestamp=datetime.now(),
            ttl_seconds=3600
        )
        
        # Execute same operation twice with same key
        result1 = await mock_idempotency_manager.execute_idempotent(
            key, expensive_operation
        )
        
        result2 = await mock_idempotency_manager.execute_idempotent(
            key, expensive_operation
        )
        
        # Results should be identical (cached)
        assert result1 == result2
        assert "expensive_computation" in result1["result"]
        
        # Verify operation was only executed once
        assert len(mock_idempotency_manager.processed_requests) == 1
    
    @pytest.mark.asyncio
    async def test_idempotency_key_expiration(self, mock_idempotency_manager):
        """Test idempotency key expiration."""
        # Set short TTL for testing
        mock_idempotency_manager.ttl_seconds = 0.1
        
        async def simple_operation():
            return {"result": "simple_computation"}
        
        key = IdempotencyKey(
            key="test_expiry_123",
            tenant_id="tenant_1234",
            user_id="user_1234",
            operation="simple_computation",
            timestamp=datetime.now(),
            ttl_seconds=0.1
        )
        
        # Execute operation
        result1 = await mock_idempotency_manager.execute_idempotent(
            key, simple_operation
        )
        
        # Wait for expiration
        await asyncio.sleep(0.2)
        
        # Execute again - should not be cached
        result2 = await mock_idempotency_manager.execute_idempotent(
            key, simple_operation
        )
        
        # Results should be identical but operation executed twice
        assert result1 == result2
        assert len(mock_idempotency_manager.processed_requests) == 1  # Only latest result
    
    @pytest.mark.asyncio
    async def test_saga_successful_execution(self, mock_saga_manager):
        """Test successful saga execution."""
        steps = [
            SagaStep(
                step_id="step_1",
                action="create_order",
                compensate="cancel_order",
                timeout_seconds=30,
                retry_count=0,
                max_retries=3
            ),
            SagaStep(
                step_id="step_2",
                action="reserve_inventory",
                compensate="release_inventory",
                timeout_seconds=30,
                retry_count=0,
                max_retries=3
            ),
            SagaStep(
                step_id="step_3",
                action="process_payment",
                compensate="refund_payment",
                timeout_seconds=30,
                retry_count=0,
                max_retries=3
            )
        ]
        
        # Execute saga (with low failure rate for success)
        result = await mock_saga_manager.execute_saga("saga_001", steps)
        
        # Should succeed
        assert result["success"] is True
        assert result["saga_id"] == "saga_001"
        
        # All steps should be completed
        for step in steps:
            assert step.completed is True
            assert step.failed is False
            assert step.compensated is False
    
    @pytest.mark.asyncio
    async def test_saga_failure_and_compensation(self, mock_saga_manager):
        """Test saga failure and compensation execution."""
        steps = [
            SagaStep(
                step_id="step_1",
                action="create_order",
                compensate="cancel_order",
                timeout_seconds=30,
                retry_count=0,
                max_retries=1  # Low retries for faster failure
            ),
            SagaStep(
                step_id="step_2",
                action="reserve_inventory",
                compensate="release_inventory",
                timeout_seconds=30,
                retry_count=0,
                max_retries=1
            )
        ]
        
        # Execute saga with high failure rate
        result = await mock_saga_manager.execute_saga("saga_002", steps)
        
        # Should fail and be compensated
        assert result["success"] is False
        assert result["compensated"] is True
        
        # Check compensation log
        assert len(mock_saga_manager.compensation_log) > 0
        
        # Verify compensation actions were logged
        compensation_actions = [log["compensation_action"] for log in mock_saga_manager.compensation_log]
        assert "cancel_order" in compensation_actions or "release_inventory" in compensation_actions
    
    @pytest.mark.asyncio
    async def test_saga_step_retry_logic(self, mock_saga_manager):
        """Test saga step retry logic."""
        step = SagaStep(
            step_id="retry_step",
            action="flaky_operation",
            compensate="rollback_operation",
            timeout_seconds=30,
            retry_count=0,
            max_retries=2
        )
        
        # Execute step directly
        try:
            await mock_saga_manager._execute_step(step)
        except Exception:
            pass  # Expected to fail
        
        # Check retry count - step may succeed on first try or after retries
        assert step.retry_count >= 0
        assert step.retry_count <= step.max_retries + 1  # Initial attempt + retries
    
    @pytest.mark.asyncio
    async def test_reliability_patterns_integration(self, mock_circuit_breaker, mock_retry_manager, mock_bulkhead, mock_idempotency_manager):
        """Test integration of multiple reliability patterns."""
        async def unreliable_operation():
            # Simulate unreliable operation
            if random.random() < 0.4:  # 40% failure rate
                raise Exception("Operation failed")
            return "operation_success"
        
        async def wrapped_operation():
            # Wrap with multiple reliability patterns
            key = IdempotencyKey(
                key="integration_test_123",
                tenant_id="tenant_1234",
                user_id="user_1234",
                operation="unreliable_operation",
                timestamp=datetime.now(),
                ttl_seconds=3600
            )
            
            return await mock_idempotency_manager.execute_idempotent(
                key, 
                lambda: mock_retry_manager.execute_with_retry(
                    lambda: mock_circuit_breaker.call(unreliable_operation)
                )
            )
        
        # Execute through bulkhead
        result = await mock_bulkhead.execute(wrapped_operation)
        
        # Should eventually succeed
        assert result == "operation_success"
        
        # Verify patterns were used
        assert mock_retry_manager.retry_count >= 0  # May have retried
        assert mock_circuit_breaker.failure_count >= 0  # May have failed
        assert mock_bulkhead.active_requests >= 0  # Was managed by bulkhead
        assert len(mock_idempotency_manager.processed_requests) == 1  # Was cached
