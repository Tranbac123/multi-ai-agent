"""Test saga orchestrator functionality."""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

from apps.orchestrator.core.saga_orchestrator import (
    SagaOrchestrator,
    SagaDefinition,
    SagaStep,
    SagaStatus,
    StepStatus,
)


class TestSagaOrchestrator:
    """Test SagaOrchestrator functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis_client = Mock()
        redis_client.setex = AsyncMock()
        redis_client.get = AsyncMock()
        return redis_client

    @pytest.fixture
    def saga_orchestrator(self, mock_redis):
        """Create SagaOrchestrator instance."""
        return SagaOrchestrator(mock_redis)

    @pytest.mark.asyncio
    async def test_create_saga(self, saga_orchestrator):
        """Test creating a saga."""
        # Mock async operations
        async def mock_operation():
            return {"result": "success"}

        steps = [
            SagaStep(
                step_id="step1",
                name="Step 1",
                operation=mock_operation,
                timeout_ms=5000,
                max_retries=3,
            ),
            SagaStep(
                step_id="step2",
                name="Step 2",
                operation=mock_operation,
                timeout_ms=5000,
                max_retries=3,
            ),
        ]

        saga_id = await saga_orchestrator.create_saga(
            name="Test Saga",
            steps=steps,
            timeout_ms=60000,
            parallel_execution=False,
            compensation_strategy="reverse_order",
        )

        assert saga_id is not None
        assert saga_id in saga_orchestrator.active_sagas
        assert saga_orchestrator.saga_metrics["total_sagas"] == 1
        assert saga_orchestrator.saga_metrics["active_sagas"] == 1

    @pytest.mark.asyncio
    async def test_execute_saga_sequential_success(self, saga_orchestrator, mock_redis):
        """Test executing a saga sequentially with success."""
        # Mock successful operations
        async def mock_operation():
            return {"result": "success"}

        steps = [
            SagaStep(
                step_id="step1",
                name="Step 1",
                operation=mock_operation,
                timeout_ms=5000,
                max_retries=3,
            ),
            SagaStep(
                step_id="step2",
                name="Step 2",
                operation=mock_operation,
                timeout_ms=5000,
                max_retries=3,
            ),
        ]

        saga_id = await saga_orchestrator.create_saga(
            name="Test Saga",
            steps=steps,
            timeout_ms=60000,
            parallel_execution=False,
        )

        result = await saga_orchestrator.execute_saga(saga_id)

        assert result["success"] is True
        assert result["saga_id"] == saga_id
        assert "results" in result
        assert len(result["results"]) == 2

        # Check metrics
        assert saga_orchestrator.saga_metrics["completed_sagas"] == 1
        assert saga_orchestrator.saga_metrics["active_sagas"] == 0

    @pytest.mark.asyncio
    async def test_execute_saga_sequential_failure(self, saga_orchestrator, mock_redis):
        """Test executing a saga sequentially with failure."""
        # Mock operations - first succeeds, second fails
        async def mock_success_operation():
            return {"result": "success"}

        async def mock_failure_operation():
            raise Exception("Operation failed")

        steps = [
            SagaStep(
                step_id="step1",
                name="Step 1",
                operation=mock_success_operation,
                timeout_ms=5000,
                max_retries=3,
            ),
            SagaStep(
                step_id="step2",
                name="Step 2",
                operation=mock_failure_operation,
                timeout_ms=5000,
                max_retries=3,
            ),
        ]

        saga_id = await saga_orchestrator.create_saga(
            name="Test Saga",
            steps=steps,
            timeout_ms=60000,
            parallel_execution=False,
        )

        result = await saga_orchestrator.execute_saga(saga_id)

        assert result["success"] is False
        assert result["saga_id"] == saga_id
        assert "error" in result
        assert "completed_steps" in result
        assert "failed_step" in result
        assert result["failed_step"] == "step2"

        # Check metrics
        assert saga_orchestrator.saga_metrics["compensated_sagas"] == 1
        assert saga_orchestrator.saga_metrics["active_sagas"] == 0

    @pytest.mark.asyncio
    async def test_execute_saga_parallel_success(self, saga_orchestrator, mock_redis):
        """Test executing a saga in parallel with success."""
        # Mock successful operations
        async def mock_operation():
            await asyncio.sleep(0.1)  # Simulate async work
            return {"result": "success"}

        steps = [
            SagaStep(
                step_id="step1",
                name="Step 1",
                operation=mock_operation,
                timeout_ms=5000,
                max_retries=3,
            ),
            SagaStep(
                step_id="step2",
                name="Step 2",
                operation=mock_operation,
                timeout_ms=5000,
                max_retries=3,
            ),
        ]

        saga_id = await saga_orchestrator.create_saga(
            name="Test Saga",
            steps=steps,
            timeout_ms=60000,
            parallel_execution=True,
        )

        result = await saga_orchestrator.execute_saga(saga_id)

        assert result["success"] is True
        assert result["saga_id"] == saga_id
        assert "results" in result
        assert len(result["results"]) == 2

        # Check metrics
        assert saga_orchestrator.saga_metrics["completed_sagas"] == 1
        assert saga_orchestrator.saga_metrics["active_sagas"] == 0

    @pytest.mark.asyncio
    async def test_execute_saga_parallel_failure(self, saga_orchestrator, mock_redis):
        """Test executing a saga in parallel with failure."""
        # Mock operations - one succeeds, one fails
        async def mock_success_operation():
            await asyncio.sleep(0.1)
            return {"result": "success"}

        async def mock_failure_operation():
            await asyncio.sleep(0.1)
            raise Exception("Operation failed")

        steps = [
            SagaStep(
                step_id="step1",
                name="Step 1",
                operation=mock_success_operation,
                timeout_ms=5000,
                max_retries=3,
            ),
            SagaStep(
                step_id="step2",
                name="Step 2",
                operation=mock_failure_operation,
                timeout_ms=5000,
                max_retries=3,
            ),
        ]

        saga_id = await saga_orchestrator.create_saga(
            name="Test Saga",
            steps=steps,
            timeout_ms=60000,
            parallel_execution=True,
        )

        result = await saga_orchestrator.execute_saga(saga_id)

        assert result["success"] is False
        assert result["saga_id"] == saga_id
        assert "error" in result
        assert "completed_steps" in result
        assert "failed_step" in result

        # Check metrics
        assert saga_orchestrator.saga_metrics["compensated_sagas"] == 1
        assert saga_orchestrator.saga_metrics["active_sagas"] == 0

    @pytest.mark.asyncio
    async def test_step_retry_logic(self, saga_orchestrator, mock_redis):
        """Test step retry logic."""
        call_count = 0

        async def mock_operation_with_failures():
            nonlocal call_count
            call_count += 1
            if call_count < 3:  # Fail first 2 attempts
                raise Exception("Temporary failure")
            return {"result": "success"}

        steps = [
            SagaStep(
                step_id="step1",
                name="Step 1",
                operation=mock_operation_with_failures,
                timeout_ms=5000,
                max_retries=3,
            ),
        ]

        saga_id = await saga_orchestrator.create_saga(
            name="Test Saga",
            steps=steps,
            timeout_ms=60000,
            parallel_execution=False,
        )

        result = await saga_orchestrator.execute_saga(saga_id)

        assert result["success"] is True
        assert call_count == 3  # Should have retried 2 times

    @pytest.mark.asyncio
    async def test_step_timeout(self, saga_orchestrator, mock_redis):
        """Test step timeout handling."""
        async def mock_slow_operation():
            await asyncio.sleep(10)  # Sleep longer than timeout
            return {"result": "success"}

        steps = [
            SagaStep(
                step_id="step1",
                name="Step 1",
                operation=mock_slow_operation,
                timeout_ms=100,  # Very short timeout
                max_retries=1,
            ),
        ]

        saga_id = await saga_orchestrator.create_saga(
            name="Test Saga",
            steps=steps,
            timeout_ms=60000,
            parallel_execution=False,
        )

        result = await saga_orchestrator.execute_saga(saga_id)

        assert result["success"] is False
        assert "timed out" in result["error"]

    @pytest.mark.asyncio
    async def test_compensation_execution(self, saga_orchestrator, mock_redis):
        """Test compensation execution."""
        compensation_calls = []

        async def mock_success_operation():
            return {"result": "success"}

        async def mock_compensation():
            compensation_calls.append("compensated")
            return {"compensation": "success"}

        async def mock_failure_operation():
            raise Exception("Operation failed")

        steps = [
            SagaStep(
                step_id="step1",
                name="Step 1",
                operation=mock_success_operation,
                compensation=mock_compensation,
                timeout_ms=5000,
                max_retries=3,
            ),
            SagaStep(
                step_id="step2",
                name="Step 2",
                operation=mock_failure_operation,
                timeout_ms=5000,
                max_retries=3,
            ),
        ]

        saga_id = await saga_orchestrator.create_saga(
            name="Test Saga",
            steps=steps,
            timeout_ms=60000,
            parallel_execution=False,
            compensation_strategy="reverse_order",
        )

        result = await saga_orchestrator.execute_saga(saga_id)

        assert result["success"] is False
        assert len(compensation_calls) == 1  # Should have called compensation

    @pytest.mark.asyncio
    async def test_get_saga_status(self, saga_orchestrator, mock_redis):
        """Test getting saga status."""
        async def mock_operation():
            return {"result": "success"}

        steps = [
            SagaStep(
                step_id="step1",
                name="Step 1",
                operation=mock_operation,
                timeout_ms=5000,
                max_retries=3,
            ),
        ]

        saga_id = await saga_orchestrator.create_saga(
            name="Test Saga",
            steps=steps,
            timeout_ms=60000,
            parallel_execution=False,
        )

        # Get status before execution
        status = await saga_orchestrator.get_saga_status(saga_id)
        assert status is not None
        assert status["saga_id"] == saga_id
        assert status["name"] == "Test Saga"
        assert status["status"] == SagaStatus.PENDING.value

        # Execute saga
        await saga_orchestrator.execute_saga(saga_id)

        # Get status after execution
        status = await saga_orchestrator.get_saga_status(saga_id)
        assert status is not None
        assert status["status"] == SagaStatus.COMPLETED.value

    @pytest.mark.asyncio
    async def test_get_saga_metrics(self, saga_orchestrator, mock_redis):
        """Test getting saga metrics."""
        async def mock_operation():
            return {"result": "success"}

        steps = [
            SagaStep(
                step_id="step1",
                name="Step 1",
                operation=mock_operation,
                timeout_ms=5000,
                max_retries=3,
            ),
        ]

        # Create and execute a saga
        saga_id = await saga_orchestrator.create_saga(
            name="Test Saga",
            steps=steps,
            timeout_ms=60000,
            parallel_execution=False,
        )
        await saga_orchestrator.execute_saga(saga_id)

        metrics = await saga_orchestrator.get_saga_metrics()

        assert "total_sagas" in metrics
        assert "completed_sagas" in metrics
        assert "failed_sagas" in metrics
        assert "compensated_sagas" in metrics
        assert "active_sagas" in metrics
        assert "success_rate" in metrics

        assert metrics["total_sagas"] == 1
        assert metrics["completed_sagas"] == 1
        assert metrics["active_sagas"] == 0
        assert metrics["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_saga_not_found(self, saga_orchestrator, mock_redis):
        """Test handling of non-existent saga."""
        with pytest.raises(ValueError, match="Saga .* not found"):
            await saga_orchestrator.execute_saga("non-existent-saga")

    @pytest.mark.asyncio
    async def test_redis_integration(self, saga_orchestrator, mock_redis):
        """Test Redis integration for saga persistence."""
        async def mock_operation():
            return {"result": "success"}

        steps = [
            SagaStep(
                step_id="step1",
                name="Step 1",
                operation=mock_operation,
                timeout_ms=5000,
                max_retries=3,
            ),
        ]

        saga_id = await saga_orchestrator.create_saga(
            name="Test Saga",
            steps=steps,
            timeout_ms=60000,
            parallel_execution=False,
        )

        # Verify Redis operations were called
        mock_redis.setex.assert_called()

        # Mock Redis get to return saga data
        saga_data = {
            "saga_id": saga_id,
            "name": "Test Saga",
            "timeout_ms": 60000,
            "parallel_execution": False,
            "compensation_strategy": "reverse_order",
            "created_at": time.time(),
            "status": SagaStatus.PENDING.value,
            "steps": [
                {
                    "step_id": "step1",
                    "name": "Step 1",
                    "timeout_ms": 5000,
                    "max_retries": 3,
                    "status": StepStatus.PENDING.value,
                }
            ],
        }

        import json
        mock_redis.get.return_value = json.dumps(saga_data)

        # Remove from active sagas to test Redis retrieval
        del saga_orchestrator.active_sagas[saga_id]

        # Execute saga (should retrieve from Redis)
        result = await saga_orchestrator.execute_saga(saga_id)

        assert result["success"] is True
        mock_redis.get.assert_called()

    @pytest.mark.asyncio
    async def test_compensation_strategy_custom(self, saga_orchestrator, mock_redis):
        """Test custom compensation strategy."""
        compensation_order = []

        async def mock_operation():
            return {"result": "success"}

        async def mock_compensation1():
            compensation_order.append("comp1")

        async def mock_compensation2():
            compensation_order.append("comp2")

        async def mock_failure_operation():
            raise Exception("Operation failed")

        steps = [
            SagaStep(
                step_id="step1",
                name="Step 1",
                operation=mock_operation,
                compensation=mock_compensation1,
                timeout_ms=5000,
                max_retries=3,
            ),
            SagaStep(
                step_id="step2",
                name="Step 2",
                operation=mock_operation,
                compensation=mock_compensation2,
                timeout_ms=5000,
                max_retries=3,
            ),
            SagaStep(
                step_id="step3",
                name="Step 3",
                operation=mock_failure_operation,
                timeout_ms=5000,
                max_retries=3,
            ),
        ]

        saga_id = await saga_orchestrator.create_saga(
            name="Test Saga",
            steps=steps,
            timeout_ms=60000,
            parallel_execution=False,
            compensation_strategy="custom",  # Custom strategy
        )

        result = await saga_orchestrator.execute_saga(saga_id)

        assert result["success"] is False
        assert len(compensation_order) == 2  # Should have called both compensations
        # With custom strategy, order should be maintained (not reversed)
        assert compensation_order == ["comp1", "comp2"]
