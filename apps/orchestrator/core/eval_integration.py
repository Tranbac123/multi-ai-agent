"""Evaluation integration for orchestrator."""

import asyncio
import time
import json
import uuid
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
import redis.asyncio as redis

from eval.golden_tasks.faq_handling import FAQHandlingGoldenTasks, GoldenTask, TaskResult, TaskStatus
from eval.golden_tasks.order_management import OrderManagementGoldenTasks
from eval.golden_tasks.lead_capture import LeadCaptureGoldenTasks
from eval.episode_replay import EpisodeReplay, Episode, EpisodeStep, EpisodeStatus, ReplayMode

logger = structlog.get_logger(__name__)


class EvalTrigger(Enum):
    """Evaluation trigger types."""
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    DEPLOYMENT = "deployment"
    INCIDENT = "incident"
    PERFORMANCE = "performance"


class EvalScope(Enum):
    """Evaluation scope."""
    ALL = "all"
    GOLDEN_TASKS = "golden_tasks"
    EPISODE_REPLAY = "episode_replay"
    INTEGRATION = "integration"
    PERFORMANCE = "performance"


@dataclass
class EvalConfig:
    """Evaluation configuration."""
    scope: EvalScope
    trigger: EvalTrigger
    timeout_seconds: int = 300
    max_retries: int = 3
    performance_thresholds: Dict[str, float] = None
    quality_gates: Dict[str, Any] = None


@dataclass
class EvalResult:
    """Evaluation result."""
    eval_id: str
    scope: EvalScope
    trigger: EvalTrigger
    status: str
    start_time: float
    end_time: float
    duration_seconds: float
    results: Dict[str, Any]
    quality_gates_passed: bool
    performance_metrics: Dict[str, float]
    errors: List[str]
    metadata: Dict[str, Any]


class EvalIntegration:
    """Evaluation integration for orchestrator."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.faq_tasks = FAQHandlingGoldenTasks()
        self.order_tasks = OrderManagementGoldenTasks()
        self.lead_tasks = LeadCaptureGoldenTasks()
        self.episode_replay = EpisodeReplay(redis_client)
        self.active_evals = {}
        
        # Default performance thresholds
        self.default_performance_thresholds = {
            "max_task_time_seconds": 2.0,
            "max_total_time_seconds": 10.0,
            "min_success_rate": 0.95,
            "max_error_rate": 0.05
        }
        
        # Default quality gates
        self.default_quality_gates = {
            "all_tasks_must_pass": True,
            "performance_thresholds_must_meet": True,
            "no_critical_errors": True,
            "episode_replay_success": True
        }

    async def run_evaluation(
        self,
        config: EvalConfig,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> EvalResult:
        """Run evaluation based on configuration."""
        try:
            eval_id = str(uuid.uuid4())
            start_time = time.time()
            
            logger.info("Starting evaluation", eval_id=eval_id, scope=config.scope.value, trigger=config.trigger.value)
            
            # Store active evaluation
            self.active_evals[eval_id] = {
                "config": config,
                "start_time": start_time,
                "status": "running"
            }
            
            # Run evaluation based on scope
            results = {}
            errors = []
            performance_metrics = {}
            
            if config.scope in [EvalScope.ALL, EvalScope.GOLDEN_TASKS]:
                try:
                    golden_results = await self._run_golden_tasks()
                    results["golden_tasks"] = golden_results
                    performance_metrics.update(self._extract_performance_metrics(golden_results))
                except Exception as e:
                    error_msg = f"Golden tasks failed: {str(e)}"
                    errors.append(error_msg)
                    logger.error("Golden tasks evaluation failed", error=error_msg)
            
            if config.scope in [EvalScope.ALL, EvalScope.EPISODE_REPLAY]:
                try:
                    replay_results = await self._run_episode_replay()
                    results["episode_replay"] = replay_results
                    performance_metrics.update(self._extract_replay_metrics(replay_results))
                except Exception as e:
                    error_msg = f"Episode replay failed: {str(e)}"
                    errors.append(error_msg)
                    logger.error("Episode replay evaluation failed", error=error_msg)
            
            if config.scope in [EvalScope.ALL, EvalScope.INTEGRATION]:
                try:
                    integration_results = await self._run_integration_tests()
                    results["integration"] = integration_results
                    performance_metrics.update(self._extract_integration_metrics(integration_results))
                except Exception as e:
                    error_msg = f"Integration tests failed: {str(e)}"
                    errors.append(error_msg)
                    logger.error("Integration tests evaluation failed", error=error_msg)
            
            if config.scope in [EvalScope.ALL, EvalScope.PERFORMANCE]:
                try:
                    perf_results = await self._run_performance_benchmarks()
                    results["performance"] = perf_results
                    performance_metrics.update(self._extract_performance_benchmark_metrics(perf_results))
                except Exception as e:
                    error_msg = f"Performance benchmarks failed: {str(e)}"
                    errors.append(error_msg)
                    logger.error("Performance benchmarks evaluation failed", error=error_msg)
            
            end_time = time.time()
            duration_seconds = end_time - start_time
            
            # Check quality gates
            quality_gates_passed = await self._check_quality_gates(
                results, performance_metrics, errors, config
            )
            
            # Create evaluation result
            eval_result = EvalResult(
                eval_id=eval_id,
                scope=config.scope,
                trigger=config.trigger,
                status="completed" if quality_gates_passed else "failed",
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration_seconds,
                results=results,
                quality_gates_passed=quality_gates_passed,
                performance_metrics=performance_metrics,
                errors=errors,
                metadata={
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "config": asdict(config)
                }
            )
            
            # Store evaluation result
            await self._store_eval_result(eval_result)
            
            # Clean up active evaluation
            if eval_id in self.active_evals:
                del self.active_evals[eval_id]
            
            logger.info(
                "Evaluation completed",
                eval_id=eval_id,
                status=eval_result.status,
                duration_seconds=duration_seconds,
                quality_gates_passed=quality_gates_passed
            )
            
            return eval_result
            
        except Exception as e:
            end_time = time.time()
            duration_seconds = end_time - start_time
            
            error_msg = f"Evaluation failed: {str(e)}"
            errors.append(error_msg)
            
            eval_result = EvalResult(
                eval_id=eval_id,
                scope=config.scope,
                trigger=config.trigger,
                status="failed",
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration_seconds,
                results={},
                quality_gates_passed=False,
                performance_metrics={},
                errors=errors,
                metadata={
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "config": asdict(config)
                }
            )
            
            # Store failed evaluation result
            await self._store_eval_result(eval_result)
            
            # Clean up active evaluation
            if eval_id in self.active_evals:
                del self.active_evals[eval_id]
            
            logger.error("Evaluation failed", eval_id=eval_id, error=error_msg)
            return eval_result

    async def _run_golden_tasks(self) -> Dict[str, Any]:
        """Run golden tasks evaluation."""
        results = {}
        
        # Run FAQ tasks
        faq_results = await self.faq_tasks.run_all_tasks()
        results["faq"] = {
            "total_tasks": len(faq_results),
            "passed": len([r for r in faq_results if r.status == TaskStatus.COMPLETED]),
            "failed": len([r for r in faq_results if r.status == TaskStatus.FAILED]),
            "avg_execution_time_ms": sum(r.execution_time_ms for r in faq_results) / len(faq_results),
            "results": [asdict(r) for r in faq_results]
        }
        
        # Run Order tasks
        order_results = await self.order_tasks.run_all_tasks()
        results["order"] = {
            "total_tasks": len(order_results),
            "passed": len([r for r in order_results if r.status == TaskStatus.COMPLETED]),
            "failed": len([r for r in order_results if r.status == TaskStatus.FAILED]),
            "avg_execution_time_ms": sum(r.execution_time_ms for r in order_results) / len(order_results),
            "results": [asdict(r) for r in order_results]
        }
        
        # Run Lead tasks
        lead_results = await self.lead_tasks.run_all_tasks()
        results["lead"] = {
            "total_tasks": len(lead_results),
            "passed": len([r for r in lead_results if r.status == TaskStatus.COMPLETED]),
            "failed": len([r for r in lead_results if r.status == TaskStatus.FAILED]),
            "avg_execution_time_ms": sum(r.execution_time_ms for r in lead_results) / len(lead_results),
            "results": [asdict(r) for r in lead_results]
        }
        
        return results

    async def _run_episode_replay(self) -> Dict[str, Any]:
        """Run episode replay evaluation."""
        results = {}
        
        # Create test episode
        test_steps = [
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
        episode_id = await self.episode_replay.record_episode(
            tenant_id="test_tenant",
            user_id="test_user",
            session_id="test_session",
            steps=test_steps
        )
        
        # Replay episode
        replay_id = await self.episode_replay.replay_episode(
            episode_id=episode_id,
            replay_mode=ReplayMode.EXACT
        )
        
        results["episode_replay"] = {
            "episode_id": episode_id,
            "replay_id": replay_id,
            "steps_count": len(test_steps),
            "status": "completed"
        }
        
        return results

    async def _run_integration_tests(self) -> Dict[str, Any]:
        """Run integration tests."""
        results = {}
        
        # Test golden tasks integration
        faq_results = await self.faq_tasks.run_all_tasks()
        order_results = await self.order_tasks.run_all_tasks()
        lead_results = await self.lead_tasks.run_all_tasks()
        
        total_tasks = len(faq_results) + len(order_results) + len(lead_results)
        total_passed = (
            len([r for r in faq_results if r.status == TaskStatus.COMPLETED]) +
            len([r for r in order_results if r.status == TaskStatus.COMPLETED]) +
            len([r for r in lead_results if r.status == TaskStatus.COMPLETED])
        )
        
        results["integration"] = {
            "total_tasks": total_tasks,
            "total_passed": total_passed,
            "success_rate": total_passed / total_tasks if total_tasks > 0 else 0,
            "faq_tasks": len(faq_results),
            "order_tasks": len(order_results),
            "lead_tasks": len(lead_results)
        }
        
        return results

    async def _run_performance_benchmarks(self) -> Dict[str, Any]:
        """Run performance benchmarks."""
        results = {}
        
        # Benchmark golden tasks
        start_time = time.time()
        faq_results = await self.faq_tasks.run_all_tasks()
        end_time = time.time()
        
        faq_duration = end_time - start_time
        faq_avg_time = sum(r.execution_time_ms for r in faq_results) / len(faq_results) if faq_results else 0
        
        results["performance"] = {
            "faq_duration_seconds": faq_duration,
            "faq_avg_time_ms": faq_avg_time,
            "faq_tasks_count": len(faq_results),
            "throughput_tasks_per_second": len(faq_results) / faq_duration if faq_duration > 0 else 0
        }
        
        return results

    def _extract_performance_metrics(self, golden_results: Dict[str, Any]) -> Dict[str, float]:
        """Extract performance metrics from golden task results."""
        metrics = {}
        
        for task_type, results in golden_results.items():
            if "avg_execution_time_ms" in results:
                metrics[f"{task_type}_avg_time_ms"] = results["avg_execution_time_ms"]
            if "total_tasks" in results:
                metrics[f"{task_type}_total_tasks"] = results["total_tasks"]
            if "passed" in results and "total_tasks" in results:
                success_rate = results["passed"] / results["total_tasks"] if results["total_tasks"] > 0 else 0
                metrics[f"{task_type}_success_rate"] = success_rate
        
        return metrics

    def _extract_replay_metrics(self, replay_results: Dict[str, Any]) -> Dict[str, float]:
        """Extract metrics from episode replay results."""
        metrics = {}
        
        if "episode_replay" in replay_results:
            replay_data = replay_results["episode_replay"]
            if "steps_count" in replay_data:
                metrics["replay_steps_count"] = replay_data["steps_count"]
        
        return metrics

    def _extract_integration_metrics(self, integration_results: Dict[str, Any]) -> Dict[str, float]:
        """Extract metrics from integration test results."""
        metrics = {}
        
        if "integration" in integration_results:
            integration_data = integration_results["integration"]
            if "success_rate" in integration_data:
                metrics["integration_success_rate"] = integration_data["success_rate"]
            if "total_tasks" in integration_data:
                metrics["integration_total_tasks"] = integration_data["total_tasks"]
        
        return metrics

    def _extract_performance_benchmark_metrics(self, perf_results: Dict[str, Any]) -> Dict[str, float]:
        """Extract metrics from performance benchmark results."""
        metrics = {}
        
        if "performance" in perf_results:
            perf_data = perf_results["performance"]
            for key, value in perf_data.items():
                if isinstance(value, (int, float)):
                    metrics[f"perf_{key}"] = value
        
        return metrics

    async def _check_quality_gates(
        self,
        results: Dict[str, Any],
        performance_metrics: Dict[str, float],
        errors: List[str],
        config: EvalConfig
    ) -> bool:
        """Check quality gates."""
        quality_gates = config.quality_gates or self.default_quality_gates
        performance_thresholds = config.performance_thresholds or self.default_performance_thresholds
        
        # Check if all tasks must pass
        if quality_gates.get("all_tasks_must_pass", True):
            for result_type, result_data in results.items():
                if result_type == "golden_tasks":
                    for task_type, task_data in result_data.items():
                        if task_data.get("failed", 0) > 0:
                            logger.warning("Quality gate failed: tasks failed", task_type=task_type, failed=task_data["failed"])
                            return False
        
        # Check performance thresholds
        if quality_gates.get("performance_thresholds_must_meet", True):
            for metric_name, threshold in performance_thresholds.items():
                if metric_name in performance_metrics:
                    if performance_metrics[metric_name] > threshold:
                        logger.warning("Quality gate failed: performance threshold exceeded", metric=metric_name, value=performance_metrics[metric_name], threshold=threshold)
                        return False
        
        # Check for critical errors
        if quality_gates.get("no_critical_errors", True):
            if errors:
                logger.warning("Quality gate failed: critical errors present", error_count=len(errors))
                return False
        
        # Check episode replay success
        if quality_gates.get("episode_replay_success", True):
            if "episode_replay" in results:
                replay_data = results["episode_replay"]
                if replay_data.get("episode_replay", {}).get("status") != "completed":
                    logger.warning("Quality gate failed: episode replay not completed")
                    return False
        
        return True

    async def _store_eval_result(self, eval_result: EvalResult) -> None:
        """Store evaluation result in Redis."""
        try:
            eval_key = f"eval_result:{eval_result.eval_id}"
            
            eval_data = {
                "eval_id": eval_result.eval_id,
                "scope": eval_result.scope.value,
                "trigger": eval_result.trigger.value,
                "status": eval_result.status,
                "start_time": eval_result.start_time,
                "end_time": eval_result.end_time,
                "duration_seconds": eval_result.duration_seconds,
                "results": json.dumps(eval_result.results),
                "quality_gates_passed": eval_result.quality_gates_passed,
                "performance_metrics": json.dumps(eval_result.performance_metrics),
                "errors": json.dumps(eval_result.errors),
                "metadata": json.dumps(eval_result.metadata)
            }
            
            await self.redis.hset(eval_key, mapping=eval_data)
            await self.redis.expire(eval_key, 86400 * 7)  # 7 days TTL
            
        except Exception as e:
            logger.error("Failed to store evaluation result", error=str(e))

    async def get_eval_result(self, eval_id: str) -> Optional[EvalResult]:
        """Get evaluation result by ID."""
        try:
            eval_key = f"eval_result:{eval_id}"
            eval_data = await self.redis.hgetall(eval_key)
            
            if not eval_data:
                return None
            
            return EvalResult(
                eval_id=eval_data["eval_id"],
                scope=EvalScope(eval_data["scope"]),
                trigger=EvalTrigger(eval_data["trigger"]),
                status=eval_data["status"],
                start_time=float(eval_data["start_time"]),
                end_time=float(eval_data["end_time"]),
                duration_seconds=float(eval_data["duration_seconds"]),
                results=json.loads(eval_data["results"]),
                quality_gates_passed=eval_data["quality_gates_passed"] == "True",
                performance_metrics=json.loads(eval_data["performance_metrics"]),
                errors=json.loads(eval_data["errors"]),
                metadata=json.loads(eval_data["metadata"])
            )
            
        except Exception as e:
            logger.error("Failed to get evaluation result", error=str(e))
            return None

    async def get_active_evals(self) -> Dict[str, Any]:
        """Get active evaluations."""
        return self.active_evals.copy()

    async def cancel_eval(self, eval_id: str) -> bool:
        """Cancel an active evaluation."""
        if eval_id in self.active_evals:
            del self.active_evals[eval_id]
            logger.info("Evaluation cancelled", eval_id=eval_id)
            return True
        return False
