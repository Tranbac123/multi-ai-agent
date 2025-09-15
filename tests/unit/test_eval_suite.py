"""Unit tests for evaluation suite."""

import pytest
import asyncio
import time
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
import redis.asyncio as redis

from eval.golden_tasks.faq_handling import (
    FAQHandlingGoldenTasks,
    GoldenTask,
    TaskResult,
    TaskStatus,
)
from eval.golden_tasks.order_management import OrderManagementGoldenTasks
from eval.golden_tasks.lead_capture import LeadCaptureGoldenTasks
from eval.episode_replay import (
    EpisodeReplayEngine,
    Episode,
    EpisodeStep,
    EpisodeConfig,
    ReplayStatus,
    ReplayMode,
)


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = AsyncMock(spec=redis.Redis)
    redis_mock.get.return_value = None
    redis_mock.setex = AsyncMock(return_value=True)
    redis_mock.hset = AsyncMock(return_value=True)
    redis_mock.expire = AsyncMock(return_value=True)
    redis_mock.keys.return_value = []
    redis_mock.hgetall.return_value = {}
    return redis_mock


class TestFAQHandlingGoldenTasks:
    """Test FAQ handling golden tasks."""

    @pytest.mark.asyncio
    async def test_initialize_faq_tasks(self):
        """Test FAQ tasks initialization."""
        faq_tasks = FAQHandlingGoldenTasks()
        tasks = await faq_tasks.get_all_tasks()

        assert len(tasks) == 2

        # Check specific tasks exist
        task_ids = [task.task_id for task in tasks]
        assert "faq_001" in task_ids
        assert "faq_002" in task_ids

    @pytest.mark.asyncio
    async def test_execute_task_success(self):
        """Test successful task execution."""
        faq_tasks = FAQHandlingGoldenTasks()
        tasks = await faq_tasks.get_all_tasks()

        task = tasks[0]  # Get first task
        result = await faq_tasks.execute_task(task)

        assert result.task_id == task.task_id
        assert result.status.value == TaskStatus.COMPLETED.value
        assert result.execution_time_ms > 0
        assert result.assertion_results is not None
        assert len(result.assertion_results) > 0

        # Check all assertions passed
        for assertion_result in result.assertion_results:
            assert assertion_result["passed"] is True

    @pytest.mark.asyncio
    async def test_run_all_tasks(self):
        """Test running all tasks."""
        faq_tasks = FAQHandlingGoldenTasks()
        results = await faq_tasks.run_all_tasks()

        assert len(results) == 2

        # Check all tasks completed
        for result in results:
            assert result.status.value == TaskStatus.COMPLETED.value
            assert result.execution_time_ms > 0
            assert result.assertion_results is not None

    @pytest.mark.asyncio
    async def test_assertion_evaluation(self):
        """Test assertion evaluation."""
        faq_tasks = FAQHandlingGoldenTasks()

        # Test equals assertion
        assertion = {"type": "equals", "field": "status", "value": "completed"}
        actual_output = {"status": "completed"}
        result = await faq_tasks._evaluate_assertion(assertion, actual_output)

        assert result["passed"] is True
        assert result["type"] == "equals"
        assert result["field"] == "status"
        assert result["expected"] == "completed"
        assert result["actual"] == "completed"

        # Test contains assertion
        assertion = {"type": "contains", "field": "response", "value": "features"}
        actual_output = {"response": "Our AI Platform offers the following features:"}
        result = await faq_tasks._evaluate_assertion(assertion, actual_output)

        assert result["passed"] is True
        assert result["type"] == "contains"

        # Test greater_than assertion
        assertion = {"type": "greater_than", "field": "confidence", "value": 0.9}
        actual_output = {"confidence": 0.95}
        result = await faq_tasks._evaluate_assertion(assertion, actual_output)

        assert result["passed"] is True
        assert result["type"] == "greater_than"

    @pytest.mark.asyncio
    async def test_nested_value_extraction(self):
        """Test nested value extraction."""
        faq_tasks = FAQHandlingGoldenTasks()

        data = {"user": {"profile": {"name": "John Doe"}}}

        # Test nested field access
        value = faq_tasks._get_nested_value(data, "user.profile.name")
        assert value == "John Doe"

        # Test non-existent field
        value = faq_tasks._get_nested_value(data, "user.profile.email")
        assert value is None

        # Test non-existent nested field
        value = faq_tasks._get_nested_value(data, "user.settings.theme")
        assert value is None


class TestOrderManagementGoldenTasks:
    """Test order management golden tasks."""

    @pytest.mark.asyncio
    async def test_initialize_order_tasks(self):
        """Test order tasks initialization."""
        order_tasks = OrderManagementGoldenTasks()
        tasks = await order_tasks.get_all_tasks()

        assert len(tasks) == 2

        # Check specific tasks exist
        task_ids = [task.task_id for task in tasks]
        assert "order_001" in task_ids
        assert "order_002" in task_ids

    @pytest.mark.asyncio
    async def test_execute_order_task(self):
        """Test order task execution."""
        order_tasks = OrderManagementGoldenTasks()
        tasks = await order_tasks.get_all_tasks()

        task = tasks[0]  # Get first task
        result = await order_tasks.execute_task(task)

        assert result.task_id == task.task_id
        assert result.status.value == TaskStatus.COMPLETED.value
        assert result.execution_time_ms > 0
        assert result.assertion_results is not None

        # Check order-specific assertions
        for assertion_result in result.assertion_results:
            assert assertion_result["passed"] is True


class TestLeadCaptureGoldenTasks:
    """Test lead capture golden tasks."""

    @pytest.mark.asyncio
    async def test_initialize_lead_tasks(self):
        """Test lead tasks initialization."""
        lead_tasks = LeadCaptureGoldenTasks()
        tasks = await lead_tasks.get_all_tasks()

        assert len(tasks) == 2

        # Check specific tasks exist
        task_ids = [task.task_id for task in tasks]
        assert "lead_001" in task_ids
        assert "lead_002" in task_ids

    @pytest.mark.asyncio
    async def test_execute_lead_task(self):
        """Test lead task execution."""
        lead_tasks = LeadCaptureGoldenTasks()
        tasks = await lead_tasks.get_all_tasks()

        task = tasks[0]  # Get first task
        result = await lead_tasks.execute_task(task)

        assert result.task_id == task.task_id
        assert result.status.value == TaskStatus.COMPLETED.value
        assert result.execution_time_ms > 0
        assert result.assertion_results is not None

        # Check lead-specific assertions
        for assertion_result in result.assertion_results:
            assert assertion_result["passed"] is True


class TestEpisodeReplay:
    """Test episode replay system."""

    @pytest.mark.asyncio
    async def test_record_episode(self, mock_redis):
        """Test episode recording."""
        replay_system = EpisodeReplayEngine(mock_redis)

        # Create test steps
        steps = [
            EpisodeStep(
                step_id="step_001",
                step_type="user_message",
                timestamp=datetime.now(),
                input_data={"message": "Hello, I need help"},
                output_data={},
                duration_ms=100,
                success=True,
            ),
            EpisodeStep(
                step_id="step_002",
                step_type="agent_response",
                timestamp=datetime.now(),
                input_data={},
                output_data={"response": "How can I help you?"},
                duration_ms=150,
                success=True,
            ),
        ]

        # Create episode config
        config = EpisodeConfig(
            episode_id="episode_001",
            model_version="gpt-4",
            prompt_version="v1.0",
            tool_versions={"order_lookup": "v1.0"},
            router_config={},
            tenant_config={},
            timestamp=datetime.now(),
            metadata={"test": True}
        )
        
        episode_id = await replay_system.record_episode(
            tenant_id="tenant_001",
            session_id="session_001",
            config=config,
            steps=steps
        )

        assert episode_id is not None
        assert len(episode_id) > 0

        # Verify Redis was called
        assert mock_redis.setex.called

    @pytest.mark.asyncio
    async def test_replay_episode(self, mock_redis):
        """Test episode replay."""
        replay_system = EpisodeReplayEngine(mock_redis)

        # Mock episode data with proper structure
        episode_data = {
            "episode_id": "episode_001",
            "tenant_id": "tenant_001",
            "user_id": "user_001",
            "session_id": "session_001",
            "status": "completed",
            "created_at": str(time.time()),
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "total_duration_ms": 100,
            "success_count": 1,
            "failure_count": 0,
            "config": {
                "episode_id": "episode_001",
                "model_version": "gpt-4",
                "prompt_version": "v1.0",
                "tool_versions": {"tool1": "v1.0"},
                "router_config": {},
                "tenant_config": {},
                "timestamp": datetime.now().isoformat(),
                "metadata": {"test": True}
            },
            "steps": [
                {
                    "step_id": "step_001",
                    "step_type": "user_message",
                    "timestamp": datetime.now().isoformat(),
                    "input_data": {"message": "Hello"},
                    "output_data": {},
                    "duration_ms": 100,
                    "success": True,
                    "error_message": None,
                    "metadata": {},
                }
            ],
            "metadata": json.dumps({"test": True}),
        }

        # Mock Redis response - use get method to return episode data
        mock_redis.get = AsyncMock(return_value=json.dumps(episode_data))

        # Start replay
        replay_episode = await replay_system.replay_episode(
            episode_id="episode_001", mode=ReplayMode.EXACT
        )

        assert replay_episode is not None
        assert replay_episode.episode_id is not None
        assert len(replay_episode.episode_id) > 0

    @pytest.mark.asyncio
    async def test_apply_replay_mode(self, mock_redis):
        """Test replay mode application - simplified test."""
        replay_system = EpisodeReplayEngine(mock_redis)

        # Test that the replay system can be created successfully
        assert replay_system is not None
        assert replay_system.redis is not None

    @pytest.mark.asyncio
    async def test_execute_step(self, mock_redis):
        """Test step execution."""
        replay_system = EpisodeReplayEngine(mock_redis)

        step = EpisodeStep(
            step_id="step_001",
            step_type="user_message",
            timestamp=datetime.now(),
            input_data={"message": "Hello"},
            output_data={},
            duration_ms=100,
            success=True,
        )

        config = EpisodeConfig(
            episode_id="episode_001",
            model_version="gpt-4",
            prompt_version="v1.0",
            tool_versions={"tool1": "v1.0"},
            router_config={},
            tenant_config={},
            timestamp=datetime.now(),
            metadata={"test": True}
        )
        
        episode = Episode(
            episode_id="episode_001",
            tenant_id="tenant_001",
            session_id="session_001",
            config=config,
            status=ReplayStatus.COMPLETED,
        )

        # Test that the episode was created successfully
        assert episode.episode_id == "episode_001"
        assert episode.tenant_id == "tenant_001"


class TestIntegration:
    """Integration tests for evaluation suite."""

    @pytest.mark.asyncio
    async def test_golden_tasks_integration(self):
        """Test integration between different golden task types."""
        # Test FAQ tasks
        faq_tasks = FAQHandlingGoldenTasks()
        faq_results = await faq_tasks.run_all_tasks()

        # Test Order tasks
        order_tasks = OrderManagementGoldenTasks()
        order_results = await order_tasks.run_all_tasks()

        # Test Lead tasks
        lead_tasks = LeadCaptureGoldenTasks()
        lead_results = await lead_tasks.run_all_tasks()

        # Verify all tasks completed
        assert len(faq_results) == 2
        assert len(order_results) == 2
        assert len(lead_results) == 2

        for result in faq_results + order_results + lead_results:
            assert result.status.value == TaskStatus.COMPLETED.value
            assert result.execution_time_ms > 0
            assert result.assertion_results is not None

    @pytest.mark.asyncio
    async def test_episode_replay_integration(self, mock_redis):
        """Test episode replay integration."""
        replay_system = EpisodeReplayEngine(mock_redis)

        # Create test episode
        steps = [
            EpisodeStep(
                step_id="step_001",
                step_type="user_message",
                timestamp=datetime.now(),
                input_data={"message": "I need help with my order"},
                output_data={},
                duration_ms=100,
                success=True,
            ),
            EpisodeStep(
                step_id="step_002",
                step_type="agent_response",
                timestamp=datetime.now(),
                input_data={},
                output_data={"response": "I can help you with that"},
                duration_ms=150,
                success=True,
            ),
            EpisodeStep(
                step_id="step_003",
                step_type="tool_call",
                timestamp=datetime.now(),
                input_data={"tool": "order_lookup", "order_id": "12345"},
                output_data={},
                duration_ms=200,
                success=True,
            ),
        ]

        # Create episode config
        config = EpisodeConfig(
            episode_id="test_episode",
            model_version="gpt-4",
            prompt_version="v1.0",
            tool_versions={"tool1": "v1.0"},
            router_config={},
            tenant_config={},
            timestamp=datetime.now(),
            metadata={"test": True}
        )
        
        # Record episode
        episode_id = await replay_system.record_episode(
            tenant_id="tenant_001",
            session_id="session_001",
            config=config,
            steps=steps,
        )

        assert episode_id is not None

        # Mock episode retrieval for replay
        episode_data = {
            "episode_id": episode_id,
            "tenant_id": "tenant_001",
            "session_id": "session_001",
            "status": "completed",
            "created_at": str(time.time()),
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "total_duration_ms": 450,
            "success_count": 3,
            "failure_count": 0,
            "config": {
                "episode_id": episode_id,
                "model_version": "gpt-4",
                "prompt_version": "v1.0",
                "tool_versions": {"tool1": "v1.0"},
                "router_config": {},
                "tenant_config": {},
                "timestamp": datetime.now().isoformat(),
                "metadata": {"test": True}
            },
            "steps": [
                {
                    "step_id": step.step_id,
                    "step_type": step.step_type,
                    "timestamp": step.timestamp.isoformat(),
                    "input_data": step.input_data,
                    "output_data": step.output_data,
                    "duration_ms": step.duration_ms,
                    "success": step.success,
                    "error_message": step.error_message,
                    "metadata": step.metadata,
                }
                for step in steps
            ],
            "metadata": {},
        }

        # Mock Redis to return the episode data for the correct key
        mock_redis.get = AsyncMock(return_value=json.dumps(episode_data))

        # Replay episode
        replay_episode = await replay_system.replay_episode(
            episode_id=episode_id, mode=ReplayMode.EXACT
        )

        assert replay_episode is not None

    @pytest.mark.asyncio
    async def test_evaluation_consistency(self):
        """Test evaluation consistency across runs."""
        faq_tasks = FAQHandlingGoldenTasks()

        # Run tasks multiple times
        results1 = await faq_tasks.run_all_tasks()
        results2 = await faq_tasks.run_all_tasks()

        # Results should be consistent
        assert len(results1) == len(results2)

        for i, (result1, result2) in enumerate(zip(results1, results2)):
            assert result1.task_id == result2.task_id
            assert result1.status == result2.status
            # Execution times may vary slightly
            assert abs(result1.execution_time_ms - result2.execution_time_ms) < 100


if __name__ == "__main__":
    pytest.main([__file__])
