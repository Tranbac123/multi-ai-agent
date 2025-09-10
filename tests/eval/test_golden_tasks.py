"""Evaluation tests for golden tasks."""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch
from hypothesis import given, strategies as st

from eval.golden_tasks.faq_handling import FAQHandlingGoldenTasks, GoldenTask, TaskResult, TaskStatus
from eval.golden_tasks.order_management import OrderManagementGoldenTasks
from eval.golden_tasks.lead_capture import LeadCaptureGoldenTasks
from eval.episode_replay import EpisodeReplay
from eval.evaluation_metrics import EvaluationMetrics


class TestGoldenTasks:
    """Test golden task functionality."""

    @pytest.mark.asyncio
    async def test_faq_handling_golden_tasks(self):
        """Test FAQ handling golden tasks."""
        faq_tasks = FAQHandlingGoldenTasks()
        
        # Get all tasks
        tasks = await faq_tasks.get_all_tasks()
        assert len(tasks) > 0
        
        # Execute each task
        for task in tasks:
            result = await faq_tasks.execute_task(task)
            
            assert result.task_id == task.task_id
            assert result.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]
            assert result.execution_time_ms > 0
            assert result.assertion_results is not None
            
            # Check assertions
            for assertion_result in result.assertion_results:
                assert "passed" in assertion_result
                assert "type" in assertion_result
                assert "field" in assertion_result

    @pytest.mark.asyncio
    async def test_order_management_golden_tasks(self):
        """Test order management golden tasks."""
        order_tasks = OrderManagementGoldenTasks()
        
        # Get all tasks
        tasks = await order_tasks.get_all_tasks()
        assert len(tasks) > 0
        
        # Execute each task
        for task in tasks:
            result = await order_tasks.execute_task(task)
            
            assert result.task_id == task.task_id
            assert result.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]
            assert result.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_lead_capture_golden_tasks(self):
        """Test lead capture golden tasks."""
        lead_tasks = LeadCaptureGoldenTasks()
        
        # Get all tasks
        tasks = await lead_tasks.get_all_tasks()
        assert len(tasks) > 0
        
        # Execute each task
        for task in tasks:
            result = await lead_tasks.execute_task(task)
            
            assert result.task_id == task.task_id
            assert result.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]
            assert result.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_golden_task_json_assertions(self):
        """Test golden task JSON assertions."""
        faq_tasks = FAQHandlingGoldenTasks()
        
        # Test equals assertion
        assertion = {"type": "equals", "field": "status", "value": "completed"}
        actual_output = {"status": "completed", "response": "Hello"}
        result = await faq_tasks._evaluate_assertion(assertion, actual_output)
        
        assert result["passed"] is True
        assert result["type"] == "equals"
        assert result["field"] == "status"
        assert result["expected"] == "completed"
        assert result["actual"] == "completed"
        
        # Test contains assertion
        assertion = {"type": "contains", "field": "response", "value": "help"}
        actual_output = {"status": "completed", "response": "I can help you"}
        result = await faq_tasks._evaluate_assertion(assertion, actual_output)
        
        assert result["passed"] is True
        assert result["type"] == "contains"
        
        # Test greater_than assertion
        assertion = {"type": "greater_than", "field": "confidence", "value": 0.8}
        actual_output = {"status": "completed", "confidence": 0.9}
        result = await faq_tasks._evaluate_assertion(assertion, actual_output)
        
        assert result["passed"] is True
        assert result["type"] == "greater_than"

    @pytest.mark.asyncio
    async def test_golden_task_failure_scenarios(self):
        """Test golden task failure scenarios."""
        faq_tasks = FAQHandlingGoldenTasks()
        
        # Test with invalid input
        invalid_task = GoldenTask(
            task_id="invalid_task",
            name="Invalid Task",
            description="Test invalid task",
            input_data={"invalid": "data"},
            expected_output={"status": "completed"},
            assertions=[{"type": "equals", "field": "status", "value": "completed"}],
            timeout_seconds=1
        )
        
        result = await faq_tasks.execute_task(invalid_task)
        
        assert result.task_id == "invalid_task"
        assert result.status == TaskStatus.FAILED
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_golden_task_timeout(self):
        """Test golden task timeout handling."""
        faq_tasks = FAQHandlingGoldenTasks()
        
        # Create task that will timeout
        timeout_task = GoldenTask(
            task_id="timeout_task",
            name="Timeout Task",
            description="Test timeout task",
            input_data={"message": "Test"},
            expected_output={"status": "completed"},
            assertions=[{"type": "equals", "field": "status", "value": "completed"}],
            timeout_seconds=0.1  # Very short timeout
        )
        
        # Mock slow execution
        with patch.object(faq_tasks, '_execute_task_internal') as mock_execute:
            mock_execute.side_effect = asyncio.sleep(1.0)  # Longer than timeout
            
            result = await faq_tasks.execute_task(timeout_task)
            
            assert result.task_id == "timeout_task"
            assert result.status == TaskStatus.FAILED
            assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_golden_task_retry_mechanism(self):
        """Test golden task retry mechanism."""
        faq_tasks = FAQHandlingGoldenTasks()
        
        # Create task with retries
        retry_task = GoldenTask(
            task_id="retry_task",
            name="Retry Task",
            description="Test retry task",
            input_data={"message": "Test"},
            expected_output={"status": "completed"},
            assertions=[{"type": "equals", "field": "status", "value": "completed"}],
            timeout_seconds=30,
            max_retries=3
        )
        
        # Mock execution that fails first two times, succeeds third time
        call_count = 0
        
        async def mock_execute_with_retries(task):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return {"status": "completed", "response": "Success"}
        
        with patch.object(faq_tasks, '_execute_task_internal', side_effect=mock_execute_with_retries):
            result = await faq_tasks.execute_task(retry_task)
            
            assert result.task_id == "retry_task"
            assert result.status == TaskStatus.COMPLETED
            assert call_count == 3  # Should have retried 3 times


class TestLLMJudgeScoring:
    """Test LLM judge scoring functionality."""

    @pytest.mark.asyncio
    async def test_llm_judge_scoring(self):
        """Test LLM judge scoring."""
        from eval.judges.llm_judge import LLMJudge
        
        judge = LLMJudge()
        
        # Test response scoring
        response = {
            "content": "I can help you with your order. What's your order number?",
            "confidence": 0.9,
            "metadata": {"model": "gpt-4"}
        }
        
        expected_response = {
            "content": "I can help you with your order. Please provide your order number.",
            "confidence": 0.8
        }
        
        score = await judge.score_response(response, expected_response)
        
        assert 0 <= score <= 1
        assert score > 0.7  # Should be high similarity

    @pytest.mark.asyncio
    async def test_llm_judge_rubric_scoring(self):
        """Test LLM judge rubric scoring."""
        from eval.judges.llm_judge import LLMJudge
        
        judge = LLMJudge()
        
        # Define scoring rubric
        rubric = {
            "helpfulness": 0.4,
            "accuracy": 0.3,
            "politeness": 0.2,
            "completeness": 0.1
        }
        
        response = {
            "content": "I can help you with your order. What's your order number?",
            "confidence": 0.9
        }
        
        scores = await judge.score_with_rubric(response, rubric)
        
        assert "helpfulness" in scores
        assert "accuracy" in scores
        assert "politeness" in scores
        assert "completeness" in scores
        
        for score in scores.values():
            assert 0 <= score <= 1

    @pytest.mark.asyncio
    async def test_llm_judge_threshold_blocking(self):
        """Test LLM judge threshold blocking."""
        from eval.judges.llm_judge import LLMJudge
        
        judge = LLMJudge(threshold=0.8)
        
        # High quality response
        good_response = {
            "content": "I can help you with your order. What's your order number?",
            "confidence": 0.9
        }
        
        good_score = await judge.score_response(good_response, good_response)
        assert good_score >= 0.8
        assert judge.should_block(good_score) is False
        
        # Low quality response
        bad_response = {
            "content": "I don't know",
            "confidence": 0.3
        }
        
        bad_score = await judge.score_response(bad_response, good_response)
        assert bad_score < 0.8
        assert judge.should_block(bad_score) is True

    @pytest.mark.asyncio
    async def test_llm_judge_batch_scoring(self):
        """Test LLM judge batch scoring."""
        from eval.judges.llm_judge import LLMJudge
        
        judge = LLMJudge()
        
        # Batch of responses
        responses = [
            {
                "content": "I can help you with your order. What's your order number?",
                "confidence": 0.9
            },
            {
                "content": "I don't know about that",
                "confidence": 0.5
            },
            {
                "content": "Please contact support for assistance",
                "confidence": 0.8
            }
        ]
        
        expected_responses = [
            {
                "content": "I can help you with your order. Please provide your order number.",
                "confidence": 0.8
            },
            {
                "content": "I don't know about that",
                "confidence": 0.5
            },
            {
                "content": "Please contact support for assistance",
                "confidence": 0.8
            }
        ]
        
        scores = await judge.score_batch(responses, expected_responses)
        
        assert len(scores) == 3
        for score in scores:
            assert 0 <= score <= 1


class TestEpisodeReplay:
    """Test episode replay functionality."""

    @pytest.mark.asyncio
    async def test_episode_replay_exact_mode(self, redis_fixture):
        """Test episode replay in exact mode."""
        replay = EpisodeReplay(redis_fixture)
        
        # Create test episode
        steps = [
            {
                "step_id": "step_001",
                "step_type": "user_message",
                "timestamp": 1234567890.0,
                "data": {"message": "Hello, I need help"}
            },
            {
                "step_id": "step_002",
                "step_type": "agent_response",
                "timestamp": 1234567891.0,
                "data": {"response": "I can help you with that"}
            }
        ]
        
        # Record episode
        episode_id = await replay.record_episode(
            tenant_id="tenant_001",
            user_id="user_001",
            session_id="session_001",
            steps=steps
        )
        
        assert episode_id is not None
        
        # Replay episode
        replay_id = await replay.replay_episode(episode_id, mode="exact")
        
        assert replay_id is not None

    @pytest.mark.asyncio
    async def test_episode_replay_parametric_mode(self, redis_fixture):
        """Test episode replay in parametric mode."""
        replay = EpisodeReplay(redis_fixture)
        
        # Create test episode
        steps = [
            {
                "step_id": "step_001",
                "step_type": "user_message",
                "timestamp": 1234567890.0,
                "data": {"message": "Hello, I need help with {product}"}
            }
        ]
        
        # Record episode
        episode_id = await replay.record_episode(
            tenant_id="tenant_001",
            user_id="user_001",
            session_id="session_001",
            steps=steps
        )
        
        # Replay with parameters
        parameters = {"product": "order tracking"}
        replay_id = await replay.replay_episode(
            episode_id, 
            mode="parametric",
            parameters=parameters
        )
        
        assert replay_id is not None

    @pytest.mark.asyncio
    async def test_episode_replay_stress_mode(self, redis_fixture):
        """Test episode replay in stress mode."""
        replay = EpisodeReplay(redis_fixture)
        
        # Create test episode
        steps = [
            {
                "step_id": "step_001",
                "step_type": "user_message",
                "timestamp": 1234567890.0,
                "data": {"message": "Test message"}
            }
        ]
        
        # Record episode
        episode_id = await replay.record_episode(
            tenant_id="tenant_001",
            user_id="user_001",
            session_id="session_001",
            steps=steps
        )
        
        # Replay in stress mode
        replay_id = await replay.replay_episode(episode_id, mode="stress")
        
        assert replay_id is not None

    @pytest.mark.asyncio
    async def test_episode_replay_reproduces_outputs(self, redis_fixture):
        """Test that episode replay reproduces outputs."""
        replay = EpisodeReplay(redis_fixture)
        
        # Create episode with known output
        steps = [
            {
                "step_id": "step_001",
                "step_type": "user_message",
                "timestamp": 1234567890.0,
                "data": {"message": "What is 2+2?"}
            },
            {
                "step_id": "step_002",
                "step_type": "agent_response",
                "timestamp": 1234567891.0,
                "data": {"response": "2+2 equals 4"}
            }
        ]
        
        # Record episode
        episode_id = await replay.record_episode(
            tenant_id="tenant_001",
            user_id="user_001",
            session_id="session_001",
            steps=steps
        )
        
        # Replay episode
        replay_id = await replay.replay_episode(episode_id, mode="exact")
        
        # Get replay results
        replay_results = await replay.get_replay_results(replay_id)
        
        assert replay_results is not None
        assert replay_results["status"] == "completed"
        assert len(replay_results["steps"]) == 2
        assert replay_results["steps"][0]["data"]["message"] == "What is 2+2?"
        assert replay_results["steps"][1]["data"]["response"] == "2+2 equals 4"


class TestEvaluationMetrics:
    """Test evaluation metrics functionality."""

    @pytest.mark.asyncio
    async def test_evaluation_metrics_calculation(self):
        """Test evaluation metrics calculation."""
        metrics = EvaluationMetrics()
        
        # Test data
        results = [
            TaskResult(
                task_id="task_001",
                status=TaskStatus.COMPLETED,
                execution_time_ms=1000,
                assertion_results=[
                    {"passed": True, "type": "equals"},
                    {"passed": True, "type": "contains"}
                ]
            ),
            TaskResult(
                task_id="task_002",
                status=TaskStatus.COMPLETED,
                execution_time_ms=1500,
                assertion_results=[
                    {"passed": True, "type": "equals"},
                    {"passed": False, "type": "contains"}
                ]
            ),
            TaskResult(
                task_id="task_003",
                status=TaskStatus.FAILED,
                execution_time_ms=2000,
                assertion_results=[]
            )
        ]
        
        # Calculate metrics
        calculated_metrics = await metrics.calculate_metrics(results)
        
        assert calculated_metrics["total_tasks"] == 3
        assert calculated_metrics["completed_tasks"] == 2
        assert calculated_metrics["failed_tasks"] == 1
        assert calculated_metrics["success_rate"] == 2/3
        assert calculated_metrics["avg_execution_time_ms"] == 1500
        assert calculated_metrics["assertion_pass_rate"] == 3/4  # 3 out of 4 assertions passed

    @pytest.mark.asyncio
    async def test_evaluation_metrics_threshold_checking(self):
        """Test evaluation metrics threshold checking."""
        metrics = EvaluationMetrics(
            min_success_rate=0.8,
            max_avg_execution_time_ms=2000,
            min_assertion_pass_rate=0.9
        )
        
        # Test data that meets thresholds
        good_results = [
            TaskResult(
                task_id="task_001",
                status=TaskStatus.COMPLETED,
                execution_time_ms=1000,
                assertion_results=[{"passed": True}, {"passed": True}]
            ),
            TaskResult(
                task_id="task_002",
                status=TaskStatus.COMPLETED,
                execution_time_ms=1500,
                assertion_results=[{"passed": True}, {"passed": True}]
            )
        ]
        
        # Should pass thresholds
        threshold_check = await metrics.check_thresholds(good_results)
        assert threshold_check["passed"] is True
        assert threshold_check["success_rate_met"] is True
        assert threshold_check["execution_time_met"] is True
        assert threshold_check["assertion_pass_rate_met"] is True
        
        # Test data that fails thresholds
        bad_results = [
            TaskResult(
                task_id="task_001",
                status=TaskStatus.FAILED,
                execution_time_ms=3000,
                assertion_results=[{"passed": False}, {"passed": False}]
            )
        ]
        
        # Should fail thresholds
        threshold_check = await metrics.check_thresholds(bad_results)
        assert threshold_check["passed"] is False
        assert threshold_check["success_rate_met"] is False
        assert threshold_check["execution_time_met"] is False
        assert threshold_check["assertion_pass_rate_met"] is False

    @pytest.mark.asyncio
    async def test_evaluation_metrics_report_generation(self):
        """Test evaluation metrics report generation."""
        metrics = EvaluationMetrics()
        
        # Test data
        results = [
            TaskResult(
                task_id="task_001",
                status=TaskStatus.COMPLETED,
                execution_time_ms=1000,
                assertion_results=[{"passed": True}, {"passed": True}]
            ),
            TaskResult(
                task_id="task_002",
                status=TaskStatus.COMPLETED,
                execution_time_ms=1500,
                assertion_results=[{"passed": True}, {"passed": False}]
            )
        ]
        
        # Generate report
        report = await metrics.generate_report(results)
        
        assert "summary" in report
        assert "detailed_metrics" in report
        assert "recommendations" in report
        
        assert report["summary"]["total_tasks"] == 2
        assert report["summary"]["success_rate"] == 1.0
        assert report["summary"]["avg_execution_time_ms"] == 1250
        
        assert len(report["recommendations"]) > 0
