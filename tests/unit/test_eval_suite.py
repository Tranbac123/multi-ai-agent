"""Unit tests for evaluation suite."""

import pytest
import asyncio
import time
import json
from unittest.mock import AsyncMock, MagicMock
import redis.asyncio as redis

from eval.golden_tasks.faq_handling import FAQHandlingGoldenTasks, GoldenTask, TaskResult, TaskStatus
from eval.golden_tasks.order_management import OrderManagementGoldenTasks
from eval.golden_tasks.lead_capture import LeadCaptureGoldenTasks
from eval.episode_replay import EpisodeReplay, Episode, EpisodeStep, EpisodeStatus, ReplayMode


@pytest.fixture
async def mock_redis():
    """Mock Redis client."""
    redis_mock = AsyncMock(spec=redis.Redis)
    redis_mock.get.return_value = None
    redis_mock.setex.return_value = True
    redis_mock.hset.return_value = True
    redis_mock.expire.return_value = True
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
        assert result.status == TaskStatus.COMPLETED
        assert result.execution_time_ms > 0
        assert result.assertion_results is not None
        assert len(result.assertion_results) > 0
        
        # Check all assertions passed
        for assertion_result in result.assertion_results:
            assert assertion_result['passed'] is True
    
    @pytest.mark.asyncio
    async def test_run_all_tasks(self):
        """Test running all tasks."""
        faq_tasks = FAQHandlingGoldenTasks()
        results = await faq_tasks.run_all_tasks()
        
        assert len(results) == 2
        
        # Check all tasks completed
        for result in results:
            assert result.status == TaskStatus.COMPLETED
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
        
        assert result['passed'] is True
        assert result['type'] == "equals"
        assert result['field'] == "status"
        assert result['expected'] == "completed"
        assert result['actual'] == "completed"
        
        # Test contains assertion
        assertion = {"type": "contains", "field": "response", "value": "features"}
        actual_output = {"response": "Our AI Platform offers the following features:"}
        result = await faq_tasks._evaluate_assertion(assertion, actual_output)
        
        assert result['passed'] is True
        assert result['type'] == "contains"
        
        # Test greater_than assertion
        assertion = {"type": "greater_than", "field": "confidence", "value": 0.9}
        actual_output = {"confidence": 0.95}
        result = await faq_tasks._evaluate_assertion(assertion, actual_output)
        
        assert result['passed'] is True
        assert result['type'] == "greater_than"
    
    @pytest.mark.asyncio
    async def test_nested_value_extraction(self):
        """Test nested value extraction."""
        faq_tasks = FAQHandlingGoldenTasks()
        
        data = {
            "user": {
                "profile": {
                    "name": "John Doe"
                }
            }
        }
        
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
        assert result.status == TaskStatus.COMPLETED
        assert result.execution_time_ms > 0
        assert result.assertion_results is not None
        
        # Check order-specific assertions
        for assertion_result in result.assertion_results:
            assert assertion_result['passed'] is True


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
        assert result.status == TaskStatus.COMPLETED
        assert result.execution_time_ms > 0
        assert result.assertion_results is not None
        
        # Check lead-specific assertions
        for assertion_result in result.assertion_results:
            assert assertion_result['passed'] is True


class TestEpisodeReplay:
    """Test episode replay system."""
    
    @pytest.mark.asyncio
    async def test_record_episode(self, mock_redis):
        """Test episode recording."""
        replay_system = EpisodeReplay(mock_redis)
        
        # Create test steps
        steps = [
            EpisodeStep(
                step_id="step_001",
                step_type="user_message",
                timestamp=time.time(),
                data={"message": "Hello, I need help"}
            ),
            EpisodeStep(
                step_id="step_002",
                step_type="agent_response",
                timestamp=time.time(),
                data={"response": "How can I help you?"}
            )
        ]
        
        episode_id = await replay_system.record_episode(
            tenant_id="tenant_001",
            user_id="user_001",
            session_id="session_001",
            steps=steps,
            metadata={"test": True}
        )
        
        assert episode_id is not None
        assert len(episode_id) > 0
        
        # Verify Redis was called
        assert mock_redis.hset.called
        assert mock_redis.expire.called
    
    @pytest.mark.asyncio
    async def test_replay_episode(self, mock_redis):
        """Test episode replay."""
        replay_system = EpisodeReplay(mock_redis)
        
        # Mock episode data
        episode_data = {
            'episode_id': 'episode_001',
            'tenant_id': 'tenant_001',
            'user_id': 'user_001',
            'session_id': 'session_001',
            'status': 'completed',
            'created_at': str(time.time()),
            'steps': json.dumps([
                {
                    'step_id': 'step_001',
                    'step_type': 'user_message',
                    'timestamp': time.time(),
                    'data': {'message': 'Hello'},
                    'metadata': None
                }
            ]),
            'metadata': json.dumps({'test': True})
        }
        
        # Mock Redis response
        mock_redis.keys.return_value = [b'episode:tenant_001:episode_001']
        mock_redis.hgetall.return_value = {k.encode(): v.encode() for k, v in episode_data.items()}
        
        # Start replay
        replay_id = await replay_system.replay_episode(
            episode_id="episode_001",
            replay_mode=ReplayMode.EXACT
        )
        
        assert replay_id is not None
        assert len(replay_id) > 0
    
    @pytest.mark.asyncio
    async def test_apply_replay_mode(self, mock_redis):
        """Test replay mode application."""
        replay_system = EpisodeReplay(mock_redis)
        
        step = EpisodeStep(
            step_id="step_001",
            step_type="user_message",
            timestamp=time.time(),
            data={"message": "Hello", "user_id": "user_001"}
        )
        
        # Test exact mode
        modified_step = await replay_system._apply_replay_mode(
            step, ReplayMode.EXACT, {}
        )
        assert modified_step.data == step.data
        
        # Test parametric mode
        parameters = {"user_id": "user_002"}
        modified_step = await replay_system._apply_replay_mode(
            step, ReplayMode.PARAMETRIC, parameters
        )
        assert modified_step.data["user_id"] == "user_002"
        assert modified_step.data["message"] == "Hello"
    
    @pytest.mark.asyncio
    async def test_execute_step(self, mock_redis):
        """Test step execution."""
        replay_system = EpisodeReplay(mock_redis)
        
        step = EpisodeStep(
            step_id="step_001",
            step_type="user_message",
            timestamp=time.time(),
            data={"message": "Hello"}
        )
        
        episode = Episode(
            episode_id="episode_001",
            tenant_id="tenant_001",
            user_id="user_001",
            session_id="session_001",
            status=EpisodeStatus.COMPLETED,
            created_at=time.time()
        )
        
        result = await replay_system._execute_step(step, episode)
        
        assert result['step_id'] == "step_001"
        assert result['step_type'] == "user_message"
        assert result['execution_time'] > 0
        assert result['result']['status'] == "processed"
        assert result['timestamp'] > 0


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
            assert result.status == TaskStatus.COMPLETED
            assert result.execution_time_ms > 0
            assert result.assertion_results is not None
    
    @pytest.mark.asyncio
    async def test_episode_replay_integration(self, mock_redis):
        """Test episode replay integration."""
        replay_system = EpisodeReplay(mock_redis)
        
        # Create test episode
        steps = [
            EpisodeStep(
                step_id="step_001",
                step_type="user_message",
                timestamp=time.time(),
                data={"message": "I need help with my order"}
            ),
            EpisodeStep(
                step_id="step_002",
                step_type="agent_response",
                timestamp=time.time(),
                data={"response": "I can help you with that"}
            ),
            EpisodeStep(
                step_id="step_003",
                step_type="tool_call",
                timestamp=time.time(),
                data={"tool": "order_lookup", "order_id": "12345"}
            )
        ]
        
        # Record episode
        episode_id = await replay_system.record_episode(
            tenant_id="tenant_001",
            user_id="user_001",
            session_id="session_001",
            steps=steps
        )
        
        assert episode_id is not None
        
        # Mock episode retrieval for replay
        episode_data = {
            'episode_id': episode_id,
            'tenant_id': 'tenant_001',
            'user_id': 'user_001',
            'session_id': 'session_001',
            'status': 'completed',
            'created_at': str(time.time()),
            'steps': json.dumps([asdict(step) for step in steps]),
            'metadata': json.dumps({})
        }
        
        mock_redis.keys.return_value = [f'episode:tenant_001:{episode_id}'.encode()]
        mock_redis.hgetall.return_value = {k.encode(): v.encode() for k, v in episode_data.items()}
        
        # Replay episode
        replay_id = await replay_system.replay_episode(
            episode_id=episode_id,
            replay_mode=ReplayMode.EXACT
        )
        
        assert replay_id is not None
    
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


if __name__ == '__main__':
    pytest.main([__file__])
