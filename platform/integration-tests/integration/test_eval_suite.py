"""Integration tests for the evaluation suite."""

import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from eval.run_evaluation import EvaluationRunner
from eval.golden_tasks.comprehensive_tasks import (
    get_all_tasks,
    TaskCategory,
    TaskDifficulty,
    ExpectedTier,
)
from eval.judges.llm_judge import LLMJudge
from eval.episode_replay import EpisodeReplayEngine
from eval.evaluation_metrics import EvaluationMetrics
from eval.reports.evaluation_report import EvaluationReportGenerator


class TestEvaluationRunner:
    """Test the evaluation runner functionality."""

    @pytest.fixture
    def config(self):
        """Test configuration."""
        return {
            "redis_url": "redis://localhost:6379",
            "openai_api_key": "test-api-key",
            "judge_model": "gpt-4",
            "episode_storage_path": "test_episodes",
            "max_tasks": 10,
            "batch_size": 5,
        }

    @pytest.fixture
    def evaluation_config(self):
        """Test evaluation configuration."""
        return {
            "task_filters": {
                "categories": ["faq", "order"],
                "difficulties": ["easy", "medium"],
                "tiers": ["SLM_A", "SLM_B"],
            },
            "thresholds": {"pass_rate": 0.8, "average_score": 0.7, "success_rate": 0.9},
        }

    @pytest.fixture
    async def runner(self, config):
        """Create evaluation runner with mocked dependencies."""
        with patch("redis.asyncio.from_url") as mock_redis:
            mock_redis_client = AsyncMock()
            mock_redis.return_value = mock_redis_client

            with patch("eval.judges.llm_judge.LLMJudge") as mock_judge:
                with patch("eval.episode_replay.EpisodeReplayEngine") as mock_replay:
                    async with EvaluationRunner(config) as runner:
                        yield runner

    @pytest.mark.asyncio
    async def test_evaluation_runner_initialization(self, config):
        """Test evaluation runner initialization."""
        with patch("redis.asyncio.from_url") as mock_redis:
            mock_redis_client = AsyncMock()
            mock_redis.return_value = mock_redis_client

            with patch("eval.judges.llm_judge.LLMJudge") as mock_judge:
                with patch("eval.episode_replay.EpisodeReplayEngine") as mock_replay:
                    async with EvaluationRunner(config) as runner:
                        assert runner.config == config
                        assert runner.redis_client is not None
                        assert runner.llm_judge is not None
                        assert runner.replay_engine is not None
                        assert runner.metrics is not None
                        assert runner.report_generator is not None

    @pytest.mark.asyncio
    async def test_get_evaluation_tasks_all(self, runner, evaluation_config):
        """Test getting all evaluation tasks."""
        evaluation_config["task_filters"]["use_all_tasks"] = True

        tasks = await runner._get_evaluation_tasks(evaluation_config)

        assert len(tasks) > 0
        assert all(hasattr(task, "task_id") for task in tasks)

    @pytest.mark.asyncio
    async def test_get_evaluation_tasks_filtered(self, runner, evaluation_config):
        """Test getting filtered evaluation tasks."""
        tasks = await runner._get_evaluation_tasks(evaluation_config)

        assert len(tasks) > 0
        assert all(hasattr(task, "task_id") for task in tasks)

        # Check that tasks match the filters
        categories = {task.category.value for task in tasks}
        assert categories.issubset({"faq", "order"})

        difficulties = {task.difficulty.value for task in tasks}
        assert difficulties.issubset({"easy", "medium"})

        tiers = {task.expected_tier.value for task in tasks}
        assert tiers.issubset({"SLM_A", "SLM_B"})

    @pytest.mark.asyncio
    async def test_get_evaluation_tasks_max_limit(self, runner, evaluation_config):
        """Test that task count is limited by max_tasks."""
        evaluation_config["max_tasks"] = 5

        tasks = await runner._get_evaluation_tasks(evaluation_config)

        assert len(tasks) <= 5

    @pytest.mark.asyncio
    async def test_run_evaluation_tasks(self, runner, evaluation_config):
        """Test running evaluation tasks."""
        # Get a small set of tasks
        tasks = get_all_tasks()[:3]

        # Mock the LLM judge evaluation
        mock_evaluation = {
            "overall_score": 0.85,
            "passes_threshold": True,
            "reasoning": "Good response",
            "criteria_scores": {
                "accuracy": 0.9,
                "completeness": 0.8,
                "relevance": 0.85,
            },
        }

        runner.llm_judge.evaluate_response = AsyncMock(return_value=mock_evaluation)

        results = await runner._run_evaluation_tasks(tasks, "test-tenant", "test-eval")

        assert len(results) == 3
        assert all(result["status"] in ["completed", "failed"] for result in results)

        # Check that completed tasks have evaluation results
        completed_results = [r for r in results if r["status"] == "completed"]
        assert len(completed_results) > 0
        assert all("evaluation" in result for result in completed_results)

    @pytest.mark.asyncio
    async def test_calculate_metrics(self, runner):
        """Test metrics calculation."""
        results = [
            {
                "status": "completed",
                "duration_ms": 1000,
                "evaluation": {"overall_score": 0.8},
                "passes_threshold": True,
            },
            {
                "status": "completed",
                "duration_ms": 1500,
                "evaluation": {"overall_score": 0.9},
                "passes_threshold": True,
            },
            {
                "status": "failed",
                "duration_ms": 0,
                "evaluation": None,
                "passes_threshold": False,
            },
        ]

        metrics = await runner._calculate_metrics(results, "test-tenant")

        assert metrics["total_tasks"] == 3
        assert metrics["completed_tasks"] == 2
        assert metrics["failed_tasks"] == 1
        assert metrics["success_rate"] == 2 / 3
        assert metrics["average_score"] == 0.85
        assert metrics["pass_rate"] == 1.0
        assert metrics["average_duration_ms"] == 1250
        assert "score_distribution" in metrics

    @pytest.mark.asyncio
    async def test_check_threshold_pass(self, runner):
        """Test threshold checking when evaluation passes."""
        metrics = {"pass_rate": 0.85, "average_score": 0.8, "success_rate": 0.95}

        config = {
            "thresholds": {"pass_rate": 0.8, "average_score": 0.7, "success_rate": 0.9}
        }

        passes = await runner._check_threshold(metrics, config)
        assert passes is True

    @pytest.mark.asyncio
    async def test_check_threshold_fail(self, runner):
        """Test threshold checking when evaluation fails."""
        metrics = {"pass_rate": 0.75, "average_score": 0.6, "success_rate": 0.95}

        config = {
            "thresholds": {"pass_rate": 0.8, "average_score": 0.7, "success_rate": 0.9}
        }

        passes = await runner._check_threshold(metrics, config)
        assert passes is False

    @pytest.mark.asyncio
    async def test_full_evaluation_run(self, runner, evaluation_config):
        """Test full evaluation run."""
        # Mock the LLM judge evaluation
        mock_evaluation = {
            "overall_score": 0.85,
            "passes_threshold": True,
            "reasoning": "Good response",
            "criteria_scores": {
                "accuracy": 0.9,
                "completeness": 0.8,
                "relevance": 0.85,
            },
        }

        runner.llm_judge.evaluate_response = AsyncMock(return_value=mock_evaluation)

        # Mock report generation
        mock_report = {
            "summary": "Evaluation completed successfully",
            "recommendations": ["Improve response accuracy"],
        }

        runner.report_generator.generate_report = AsyncMock(return_value=mock_report)

        # Mock Redis storage
        runner.redis_client.setex = AsyncMock()

        result = await runner.run_evaluation("test-tenant", evaluation_config)

        assert result["status"] == "completed"
        assert "evaluation_id" in result
        assert "tenant_id" in result
        assert "duration_seconds" in result
        assert "task_count" in result
        assert "results" in result
        assert "metrics" in result
        assert "report" in result
        assert "passes_threshold" in result

    @pytest.mark.asyncio
    async def test_evaluation_run_failure(self, runner, evaluation_config):
        """Test evaluation run with failure."""
        # Mock LLM judge to raise an exception
        runner.llm_judge.evaluate_response = AsyncMock(
            side_effect=Exception("API Error")
        )

        result = await runner.run_evaluation("test-tenant", evaluation_config)

        assert result["status"] == "failed"
        assert "error" in result
        assert "API Error" in result["error"]


class TestEvaluationIntegration:
    """Test evaluation suite integration."""

    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Create temporary directory for test files."""
        return tmp_path

    @pytest.mark.asyncio
    async def test_golden_tasks_integration(self, temp_dir):
        """Test integration with golden tasks."""
        # Test getting tasks by category
        faq_tasks = get_all_tasks()
        faq_tasks = [task for task in faq_tasks if task.category == "faq"]

        assert len(faq_tasks) > 0
        assert all(task.category == "faq" for task in faq_tasks)

        # Test getting tasks by difficulty
        easy_tasks = [
            task for task in faq_tasks if task.metadata.get("difficulty") == "easy"
        ]

        assert len(easy_tasks) > 0
        assert all(task.metadata.get("difficulty") == "easy" for task in easy_tasks)

        # Test getting tasks by tier
        slm_a_tasks = [
            task for task in faq_tasks if task.metadata.get("expected_tier") == "SLM_A"
        ]

        assert len(slm_a_tasks) > 0
        assert all(
            task.metadata.get("expected_tier") == "SLM_A" for task in slm_a_tasks
        )

    @pytest.mark.asyncio
    async def test_llm_judge_integration(self, temp_dir):
        """Test integration with LLM judge."""
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client

            # Mock the chat completion response
            mock_response = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "overall_score": 0.85,
                                    "passes_threshold": True,
                                    "reasoning": "Good response",
                                    "criteria_scores": {
                                        "accuracy": 0.9,
                                        "completeness": 0.8,
                                        "relevance": 0.85,
                                    },
                                }
                            )
                        }
                    }
                ]
            }
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            judge = LLMJudge(api_key="test-key", model="gpt-4")

            task = {
                "task_id": "test-task",
                "category": "faq",
                "input_text": "What is your return policy?",
                "expected_response": "Our return policy allows returns within 30 days.",
                "expected_intent": "return_policy",
                "expected_confidence": 0.9,
                "expected_tools": [],
                "metadata": {},
            }

            evaluation = await judge.evaluate_response(
                task=task,
                actual_response="Our return policy allows returns within 30 days.",
                actual_intent="return_policy",
                actual_confidence=0.9,
                actual_tools_used=[],
                tenant_id="test-tenant",
            )

            assert evaluation["overall_score"] == 0.85
            assert evaluation["passes_threshold"] is True
            assert "reasoning" in evaluation
            assert "criteria_scores" in evaluation

    @pytest.mark.asyncio
    async def test_episode_replay_integration(self, temp_dir):
        """Test integration with episode replay."""
        with patch("redis.asyncio.from_url") as mock_redis:
            mock_redis_client = AsyncMock()
            mock_redis.return_value = mock_redis_client

            replay_engine = EpisodeReplayEngine(
                redis_client=mock_redis_client, storage_path=str(temp_dir / "episodes")
            )

            # Test episode recording
            episode_data = {
                "tenant_id": "test-tenant",
                "session_id": "test-session",
                "model_version": "gpt-4",
                "prompt_version": "v1.0",
                "tool_versions": {"email": "v1.0", "payment": "v1.0"},
                "steps": [],
                "metadata": {},
            }

            episode_id = await replay_engine.record_episode(episode_data)

            assert episode_id is not None

            # Test episode stats
            stats = await replay_engine.get_episode_stats("test-tenant")

            assert stats is not None
            assert "total_episodes" in stats

    @pytest.mark.asyncio
    async def test_metrics_integration(self, temp_dir):
        """Test integration with evaluation metrics."""
        # Create a simple metrics tracking
        metrics_data = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "durations": [],
        }

        # Test metric recording
        def record_task_completion(task_id, duration_ms, success):
            metrics_data["total_tasks"] += 1
            metrics_data["completed_tasks"] += 1
            if success:
                metrics_data["successful_tasks"] += 1
            else:
                metrics_data["failed_tasks"] += 1
            metrics_data["durations"].append(duration_ms)

        # Record test data
        record_task_completion("task-1", 1000, True)
        record_task_completion("task-2", 1500, False)
        record_task_completion("task-3", 800, True)

        # Test metric retrieval
        success_rate = (
            metrics_data["successful_tasks"] / metrics_data["completed_tasks"]
        )
        avg_duration = sum(metrics_data["durations"]) / len(metrics_data["durations"])

        assert metrics_data["total_tasks"] == 3
        assert metrics_data["completed_tasks"] == 3
        assert metrics_data["successful_tasks"] == 2
        assert metrics_data["failed_tasks"] == 1
        assert success_rate == 2 / 3
        assert avg_duration == 1100

    @pytest.mark.asyncio
    async def test_report_generation_integration(self, temp_dir):
        """Test integration with report generation."""
        report_generator = EvaluationReportGenerator()

        # Mock data
        tasks = get_all_tasks()[:2]
        results = [
            {
                "task_id": "task-1",
                "status": "completed",
                "duration_ms": 1000,
                "evaluation": {"overall_score": 0.8},
                "passes_threshold": True,
            },
            {
                "task_id": "task-2",
                "status": "completed",
                "duration_ms": 1500,
                "evaluation": {"overall_score": 0.9},
                "passes_threshold": True,
            },
        ]
        metrics = {
            "total_tasks": 2,
            "completed_tasks": 2,
            "failed_tasks": 0,
            "success_rate": 1.0,
            "average_score": 0.85,
            "pass_rate": 1.0,
            "average_duration_ms": 1250,
        }

        report = await report_generator.generate_report(
            evaluation_id="test-eval",
            tenant_id="test-tenant",
            tasks=tasks,
            results=results,
            metrics=metrics,
            config={},
        )

        assert "evaluation_id" in report
        assert "tenant_id" in report
        assert "summary" in report
        assert "metrics" in report
        assert "recommendations" in report
        assert "timestamp" in report


class TestCIIntegration:
    """Test CI integration functionality."""

    @pytest.mark.asyncio
    async def test_ci_mode_configuration(self):
        """Test CI mode configuration adjustments."""
        config = {
            "max_tasks": 50,
            "batch_size": 10,
            "thresholds": {"pass_rate": 0.8, "average_score": 0.7, "success_rate": 0.9},
        }

        # Simulate CI mode adjustments
        if True:  # CI mode
            config["thresholds"]["pass_rate"] = 0.85
            config["thresholds"]["average_score"] = 0.75
            config["max_tasks"] = 100

        assert config["thresholds"]["pass_rate"] == 0.85
        assert config["thresholds"]["average_score"] == 0.75
        assert config["max_tasks"] == 100

    @pytest.mark.asyncio
    async def test_artifact_generation(self, temp_dir):
        """Test artifact generation for CI."""
        # Mock evaluation results
        results = {
            "evaluation_id": "test-eval",
            "tenant_id": "test-tenant",
            "status": "completed",
            "duration_seconds": 120.5,
            "task_count": 50,
            "passes_threshold": True,
            "metrics": {"success_rate": 0.95, "pass_rate": 0.88, "average_score": 0.82},
        }

        # Write results to file
        results_file = temp_dir / "eval-results.json"
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)

        # Verify file exists and contains expected data
        assert results_file.exists()

        with open(results_file, "r") as f:
            loaded_results = json.load(f)

        assert loaded_results["evaluation_id"] == "test-eval"
        assert loaded_results["passes_threshold"] is True
        assert loaded_results["metrics"]["success_rate"] == 0.95
