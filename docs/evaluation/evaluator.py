"""Main evaluator for the AIaaS platform."""

import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID
import structlog

from libs.contracts.agent import AgentSpec, AgentBudgets
from libs.contracts.router import RouterDecisionRequest, RouterTier
from .golden_tasks.customer_support import CustomerSupportGoldenTasks, GoldenTask
from .judges.llm_judge import LLMJudge, LLMJudgeConfig
from .judges.base_judge import JudgeResult
from .reports.evaluation_report import EvaluationReport, EvaluationMetrics

logger = structlog.get_logger(__name__)


class Evaluator:
    """Main evaluator for the AIaaS platform."""

    def __init__(self, judge_config: LLMJudgeConfig = None):
        self.judge = LLMJudge(judge_config)
        self.golden_tasks = CustomerSupportGoldenTasks()
        self._ready = False

    async def initialize(self):
        """Initialize evaluator."""
        try:
            await self.judge.initialize()
            self._ready = True
            logger.info("Evaluator initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize evaluator", error=str(e))
            self._ready = False

    def is_ready(self) -> bool:
        """Check if evaluator is ready."""
        return self._ready

    async def evaluate_router(
        self, router_engine, task_filter: Optional[Dict[str, Any]] = None
    ) -> EvaluationReport:
        """Evaluate router performance."""
        if not self._ready:
            raise RuntimeError("Evaluator not initialized")

        # Get tasks to evaluate
        tasks = self._filter_tasks(task_filter)

        # Evaluate each task
        results = []
        for task in tasks:
            try:
                result = await self._evaluate_router_task(router_engine, task)
                results.append(result)
            except Exception as e:
                logger.error(
                    "Router evaluation failed for task",
                    task_id=task.task_id,
                    error=str(e),
                )
                results.append(
                    {"task_id": task.task_id, "success": False, "error": str(e)}
                )

        # Generate report
        report = self._generate_router_report(results)

        logger.info(
            "Router evaluation completed",
            total_tasks=len(tasks),
            successful_tasks=len([r for r in results if r.get("success", False)]),
            average_score=report.metrics.average_score,
        )

        return report

    async def evaluate_agent(
        self, orchestrator_engine, task_filter: Optional[Dict[str, Any]] = None
    ) -> EvaluationReport:
        """Evaluate agent performance."""
        if not self._ready:
            raise RuntimeError("Evaluator not initialized")

        # Get tasks to evaluate
        tasks = self._filter_tasks(task_filter)

        # Evaluate each task
        results = []
        for task in tasks:
            try:
                result = await self._evaluate_agent_task(orchestrator_engine, task)
                results.append(result)
            except Exception as e:
                logger.error(
                    "Agent evaluation failed for task",
                    task_id=task.task_id,
                    error=str(e),
                )
                results.append(
                    {"task_id": task.task_id, "success": False, "error": str(e)}
                )

        # Generate report
        report = self._generate_agent_report(results)

        logger.info(
            "Agent evaluation completed",
            total_tasks=len(tasks),
            successful_tasks=len([r for r in results if r.get("success", False)]),
            average_score=report.metrics.average_score,
        )

        return report

    async def evaluate_end_to_end(
        self,
        router_engine,
        orchestrator_engine,
        task_filter: Optional[Dict[str, Any]] = None,
    ) -> EvaluationReport:
        """Evaluate end-to-end performance."""
        if not self._ready:
            raise RuntimeError("Evaluator not initialized")

        # Get tasks to evaluate
        tasks = self._filter_tasks(task_filter)

        # Evaluate each task
        results = []
        for task in tasks:
            try:
                result = await self._evaluate_e2e_task(
                    router_engine, orchestrator_engine, task
                )
                results.append(result)
            except Exception as e:
                logger.error(
                    "E2E evaluation failed for task", task_id=task.task_id, error=str(e)
                )
                results.append(
                    {"task_id": task.task_id, "success": False, "error": str(e)}
                )

        # Generate report
        report = self._generate_e2e_report(results)

        logger.info(
            "E2E evaluation completed",
            total_tasks=len(tasks),
            successful_tasks=len([r for r in results if r.get("success", False)]),
            average_score=report.metrics.average_score,
        )

        return report

    def _filter_tasks(self, task_filter: Optional[Dict[str, Any]]) -> List[GoldenTask]:
        """Filter tasks based on criteria."""
        tasks = self.golden_tasks.get_tasks()

        if not task_filter:
            return tasks

        filtered_tasks = []
        for task in tasks:
            if (
                task_filter.get("difficulty")
                and task.difficulty != task_filter["difficulty"]
            ):
                continue
            if task_filter.get("domain") and task.domain != task_filter["domain"]:
                continue
            if task_filter.get("category") and task.category != task_filter["category"]:
                continue
            filtered_tasks.append(task)

        return filtered_tasks

    async def _evaluate_router_task(
        self, router_engine, task: GoldenTask
    ) -> Dict[str, Any]:
        """Evaluate single router task."""
        # Create router request
        router_request = RouterDecisionRequest(
            tenant_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            task_id=UUID(task.task_id),
            requirement=task.description,
            text_features={
                "token_count": len(task.input_data.get("user_message", "").split()),
                "json_schema_complexity": 0.5,
                "domain_flags": {task.domain: True},
                "novelty_score": 0.3,
                "historical_failure_rate": 0.1,
                "reasoning_keywords": [],
                "entity_count": 0,
                "format_strictness": 0.5,
            },
            history_stats={
                "total_runs": 100,
                "success_rate": 0.9,
                "avg_latency_ms": 500.0,
                "avg_cost_usd": 0.01,
                "tier_distribution": {"SLM_A": 50, "SLM_B": 30, "LLM": 20},
            },
        )

        # Get router decision
        decision = await router_engine.route(router_request)

        # Judge decision
        judge_result = await self.judge.judge_router_decision(
            task_input=task.input_data,
            expected_tier=task.expected_tier,
            actual_tier=decision.tier,
            actual_confidence=decision.confidence,
            actual_cost_usd=decision.expected_cost_usd,
            actual_latency_ms=decision.expected_latency_ms,
        )

        return {
            "task_id": task.task_id,
            "success": True,
            "expected_tier": task.expected_tier.value,
            "actual_tier": decision.tier.value,
            "expected_confidence": task.expected_confidence,
            "actual_confidence": decision.confidence,
            "expected_cost": task.expected_cost_usd,
            "actual_cost": decision.expected_cost_usd,
            "expected_latency": task.expected_latency_ms,
            "actual_latency": decision.expected_latency_ms,
            "judge_score": judge_result.score,
            "judge_reasoning": judge_result.reasoning,
            "judge_metrics": judge_result.metrics,
        }

    async def _evaluate_agent_task(
        self, orchestrator_engine, task: GoldenTask
    ) -> Dict[str, Any]:
        """Evaluate single agent task."""
        # Create agent spec
        budgets = AgentBudgets(max_tokens=1000, max_cost_usd=0.01, wall_ms=5000)

        agent_spec = AgentSpec(
            name="test-agent",
            version="1.0.0",
            inputs_schema={"type": "object"},
            outputs_schema={"type": "object"},
            tools_allowed=["tool1", "tool2"],
            budgets=budgets,
            role="Test agent",
            system_prompt="You are a test agent.",
        )

        # Create run
        run = await orchestrator_engine.create_run(
            tenant_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            agent_spec=agent_spec,
            context=task.input_data,
        )

        # Start run
        await orchestrator_engine.start_run(run.run_id, run.tenant_id)

        # Wait for completion
        await asyncio.sleep(1)

        # Get completed run
        completed_run = await orchestrator_engine.get_run(run.run_id, run.tenant_id)

        # Mock agent output
        actual_output = {
            "response": "Mock response",
            "confidence": 0.8,
            "actions": ["mock_action"],
        }

        # Judge response
        judge_result = await self.judge.judge_agent_response(
            task_input=task.input_data,
            expected_output=task.expected_output,
            actual_output=actual_output,
        )

        return {
            "task_id": task.task_id,
            "success": True,
            "expected_output": task.expected_output,
            "actual_output": actual_output,
            "run_status": completed_run.status,
            "tokens_in": completed_run.tokens_in,
            "tokens_out": completed_run.tokens_out,
            "cost_usd": completed_run.cost_usd,
            "judge_score": judge_result.score,
            "judge_reasoning": judge_result.reasoning,
            "judge_metrics": judge_result.metrics,
        }

    async def _evaluate_e2e_task(
        self, router_engine, orchestrator_engine, task: GoldenTask
    ) -> Dict[str, Any]:
        """Evaluate single end-to-end task."""
        # First evaluate router
        router_result = await self._evaluate_router_task(router_engine, task)

        # Then evaluate agent
        agent_result = await self._evaluate_agent_task(orchestrator_engine, task)

        # Combine results
        return {
            "task_id": task.task_id,
            "success": router_result["success"] and agent_result["success"],
            "router_result": router_result,
            "agent_result": agent_result,
            "overall_score": (
                router_result.get("judge_score", 0) + agent_result.get("judge_score", 0)
            )
            / 2,
        }

    def _generate_router_report(
        self, results: List[Dict[str, Any]]
    ) -> EvaluationReport:
        """Generate router evaluation report."""
        successful_results = [r for r in results if r.get("success", False)]

        if not successful_results:
            return EvaluationReport(
                evaluation_type="router",
                total_tasks=len(results),
                successful_tasks=0,
                metrics=EvaluationMetrics(
                    average_score=0.0,
                    score_distribution={},
                    tier_accuracy=0.0,
                    cost_efficiency=0.0,
                    latency_performance=0.0,
                ),
                results=results,
            )

        # Calculate metrics
        scores = [r.get("judge_score", 0) for r in successful_results]
        average_score = sum(scores) / len(scores) if scores else 0.0

        # Tier accuracy
        tier_correct = sum(
            1
            for r in successful_results
            if r.get("expected_tier") == r.get("actual_tier")
        )
        tier_accuracy = (
            tier_correct / len(successful_results) if successful_results else 0.0
        )

        # Cost efficiency
        cost_ratios = [
            r.get("actual_cost", 0) / r.get("expected_cost", 1)
            for r in successful_results
            if r.get("expected_cost", 0) > 0
        ]
        cost_efficiency = (
            1.0 - (sum(cost_ratios) / len(cost_ratios) - 1.0) if cost_ratios else 0.0
        )
        cost_efficiency = max(0.0, min(1.0, cost_efficiency))

        # Latency performance
        latency_ratios = [
            r.get("actual_latency", 0) / r.get("expected_latency", 1)
            for r in successful_results
            if r.get("expected_latency", 0) > 0
        ]
        latency_performance = (
            1.0 - (sum(latency_ratios) / len(latency_ratios) - 1.0)
            if latency_ratios
            else 0.0
        )
        latency_performance = max(0.0, min(1.0, latency_performance))

        return EvaluationReport(
            evaluation_type="router",
            total_tasks=len(results),
            successful_tasks=len(successful_results),
            metrics=EvaluationMetrics(
                average_score=average_score,
                score_distribution=self._calculate_score_distribution(scores),
                tier_accuracy=tier_accuracy,
                cost_efficiency=cost_efficiency,
                latency_performance=latency_performance,
            ),
            results=results,
        )

    def _generate_agent_report(self, results: List[Dict[str, Any]]) -> EvaluationReport:
        """Generate agent evaluation report."""
        successful_results = [r for r in results if r.get("success", False)]

        if not successful_results:
            return EvaluationReport(
                evaluation_type="agent",
                total_tasks=len(results),
                successful_tasks=0,
                metrics=EvaluationMetrics(
                    average_score=0.0,
                    score_distribution={},
                    tier_accuracy=0.0,
                    cost_efficiency=0.0,
                    latency_performance=0.0,
                ),
                results=results,
            )

        # Calculate metrics
        scores = [r.get("judge_score", 0) for r in successful_results]
        average_score = sum(scores) / len(scores) if scores else 0.0

        return EvaluationReport(
            evaluation_type="agent",
            total_tasks=len(results),
            successful_tasks=len(successful_results),
            metrics=EvaluationMetrics(
                average_score=average_score,
                score_distribution=self._calculate_score_distribution(scores),
                tier_accuracy=0.0,  # Not applicable for agent
                cost_efficiency=0.0,  # Not applicable for agent
                latency_performance=0.0,  # Not applicable for agent
            ),
            results=results,
        )

    def _generate_e2e_report(self, results: List[Dict[str, Any]]) -> EvaluationReport:
        """Generate end-to-end evaluation report."""
        successful_results = [r for r in results if r.get("success", False)]

        if not successful_results:
            return EvaluationReport(
                evaluation_type="end_to_end",
                total_tasks=len(results),
                successful_tasks=0,
                metrics=EvaluationMetrics(
                    average_score=0.0,
                    score_distribution={},
                    tier_accuracy=0.0,
                    cost_efficiency=0.0,
                    latency_performance=0.0,
                ),
                results=results,
            )

        # Calculate metrics
        scores = [r.get("overall_score", 0) for r in successful_results]
        average_score = sum(scores) / len(scores) if scores else 0.0

        return EvaluationReport(
            evaluation_type="end_to_end",
            total_tasks=len(results),
            successful_tasks=len(successful_results),
            metrics=EvaluationMetrics(
                average_score=average_score,
                score_distribution=self._calculate_score_distribution(scores),
                tier_accuracy=0.0,  # Not applicable for E2E
                cost_efficiency=0.0,  # Not applicable for E2E
                latency_performance=0.0,  # Not applicable for E2E
            ),
            results=results,
        )

    def _calculate_score_distribution(self, scores: List[float]) -> Dict[str, int]:
        """Calculate score distribution."""
        distribution = {
            "0.0-0.2": 0,
            "0.2-0.4": 0,
            "0.4-0.6": 0,
            "0.6-0.8": 0,
            "0.8-1.0": 0,
        }

        for score in scores:
            if score < 0.2:
                distribution["0.0-0.2"] += 1
            elif score < 0.4:
                distribution["0.2-0.4"] += 1
            elif score < 0.6:
                distribution["0.4-0.6"] += 1
            elif score < 0.8:
                distribution["0.6-0.8"] += 1
            else:
                distribution["0.8-1.0"] += 1

        return distribution
