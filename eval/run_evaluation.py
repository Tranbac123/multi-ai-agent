#!/usr/bin/env python3
"""Enhanced evaluation runner with CI integration and comprehensive reporting."""

import asyncio
import json
import time
import uuid
import argparse
import sys
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime, timezone
import structlog
import redis.asyncio as redis
from contextlib import asynccontextmanager

# Import evaluation components
from eval.golden_tasks.comprehensive_tasks import (
    get_all_tasks, get_tasks_by_category, get_tasks_by_difficulty,
    get_tasks_by_tier, get_high_priority_tasks, TaskCategory, TaskDifficulty, ExpectedTier
)
from eval.judges.llm_judge import LLMJudge
from eval.episode_replay import EpisodeReplayEngine, ReplayMode
from eval.evaluation_metrics import EvaluationMetrics
from eval.reports.evaluation_report import EvaluationReportGenerator

logger = structlog.get_logger(__name__)


class EvaluationRunner:
    """Enhanced evaluation runner with comprehensive testing and reporting."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.redis_client: Optional[redis.Redis] = None
        self.llm_judge: Optional[LLMJudge] = None
        self.replay_engine: Optional[EpisodeReplayEngine] = None
        self.metrics = None  # Will be initialized in __aenter__
        self.report_generator = EvaluationReportGenerator()
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.redis_client = redis.from_url(self.config["redis_url"])
        self.llm_judge = LLMJudge(
            api_key=self.config["openai_api_key"],
            model=self.config.get("judge_model", "gpt-4")
        )
        self.replay_engine = EpisodeReplayEngine(
            redis_client=self.redis_client,
            storage_path=self.config.get("episode_storage_path", "eval/episodes")
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.redis_client:
            await self.redis_client.close()
    
    async def run_evaluation(
        self,
        tenant_id: str,
        evaluation_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run comprehensive evaluation."""
        evaluation_id = str(uuid.uuid4())
        start_time = time.time()
        
        logger.info("Starting evaluation", 
                   evaluation_id=evaluation_id,
                   tenant_id=tenant_id,
                   config=evaluation_config)
        
        try:
            # Get tasks based on configuration
            tasks = await self._get_evaluation_tasks(evaluation_config)
            logger.info("Selected tasks for evaluation", 
                       task_count=len(tasks),
                       evaluation_id=evaluation_id)
            
            # Run evaluation tasks
            results = await self._run_evaluation_tasks(tasks, tenant_id, evaluation_id)
            
            # Calculate metrics
            metrics = await self._calculate_metrics(results, tenant_id)
            
            # Generate report
            report = await self._generate_report(
                evaluation_id, tenant_id, tasks, results, metrics, evaluation_config
            )
            
            # Check if evaluation passes threshold
            passes_threshold = await self._check_threshold(metrics, evaluation_config)
            
            # Store results
            await self._store_evaluation_results(evaluation_id, tenant_id, results, metrics, report)
            
            duration = time.time() - start_time
            
            logger.info("Evaluation completed", 
                       evaluation_id=evaluation_id,
                       tenant_id=tenant_id,
                       duration_seconds=duration,
                       passes_threshold=passes_threshold)
            
            return {
                "evaluation_id": evaluation_id,
                "tenant_id": tenant_id,
                "status": "completed",
                "duration_seconds": duration,
                "task_count": len(tasks),
                "results": results,
                "metrics": metrics,
                "report": report,
                "passes_threshold": passes_threshold
            }
            
        except Exception as e:
            logger.error("Evaluation failed", 
                        evaluation_id=evaluation_id,
                        tenant_id=tenant_id,
                        error=str(e))
            
            return {
                "evaluation_id": evaluation_id,
                "tenant_id": tenant_id,
                "status": "failed",
                "error": str(e),
                "duration_seconds": time.time() - start_time
            }
    
    async def _get_evaluation_tasks(self, config: Dict[str, Any]) -> List[Any]:
        """Get tasks based on evaluation configuration."""
        task_filters = config.get("task_filters", {})
        
        if task_filters.get("use_all_tasks", False):
            tasks = get_all_tasks()
        else:
            tasks = []
            
            # Filter by category
            if "categories" in task_filters:
                for category in task_filters["categories"]:
                    tasks.extend(get_tasks_by_category(TaskCategory(category)))
            
            # Filter by difficulty
            if "difficulties" in task_filters:
                for difficulty in task_filters["difficulties"]:
                    tasks.extend(get_tasks_by_difficulty(TaskDifficulty(difficulty)))
            
            # Filter by tier
            if "tiers" in task_filters:
                for tier in task_filters["tiers"]:
                    tasks.extend(get_tasks_by_tier(ExpectedTier(tier)))
            
            # Use high priority tasks if no filters specified
            if not tasks:
                tasks = get_high_priority_tasks()
        
        # Limit number of tasks
        max_tasks = config.get("max_tasks", 50)
        if len(tasks) > max_tasks:
            import random
            tasks = random.sample(tasks, max_tasks)
        
        return tasks
    
    async def _run_evaluation_tasks(
        self,
        tasks: List[Any],
        tenant_id: str,
        evaluation_id: str
    ) -> List[Dict[str, Any]]:
        """Run evaluation tasks and collect results."""
        results = []
        
        # Run tasks in parallel batches
        batch_size = self.config.get("batch_size", 10)
        
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            batch_results = await self._run_task_batch(batch, tenant_id, evaluation_id)
            results.extend(batch_results)
            
            # Small delay between batches
            await asyncio.sleep(0.1)
        
        return results
    
    async def _run_task_batch(
        self,
        tasks: List[Any],
        tenant_id: str,
        evaluation_id: str
    ) -> List[Dict[str, Any]]:
        """Run a batch of tasks in parallel."""
        batch_tasks = []
        
        for task in tasks:
            task_coroutine = self._run_single_task(task, tenant_id, evaluation_id)
            batch_tasks.append(task_coroutine)
        
        # Run batch in parallel
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        
        # Process results and handle exceptions
        processed_results = []
        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                logger.error("Task execution failed", 
                           task_id=tasks[i].task_id,
                           error=str(result))
                
                processed_results.append({
                    "task_id": tasks[i].task_id,
                    "status": "failed",
                    "error": str(result),
                    "duration_ms": 0,
                    "evaluation": None
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _run_single_task(
        self,
        task: Any,
        tenant_id: str,
        evaluation_id: str
    ) -> Dict[str, Any]:
        """Run a single evaluation task."""
        start_time = time.time()
        
        try:
            # Simulate task execution (in real implementation, this would call the actual AI system)
            actual_response = await self._simulate_ai_response(task)
            
            # Evaluate response with LLM judge
            evaluation = await self.llm_judge.evaluate_response(
                task={
                    "task_id": task.task_id,
                    "category": task.category.value,
                    "input_text": task.input_text,
                    "expected_response": task.expected_response,
                    "expected_intent": task.expected_intent,
                    "expected_confidence": task.expected_confidence,
                    "expected_tools": task.expected_tools,
                    "metadata": task.metadata
                },
                actual_response=actual_response["response"],
                actual_intent=actual_response["intent"],
                actual_confidence=actual_response["confidence"],
                actual_tools_used=actual_response["tools_used"],
                tenant_id=uuid.UUID(tenant_id)
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            return {
                "task_id": task.task_id,
                "status": "completed",
                "duration_ms": duration_ms,
                "actual_response": actual_response,
                "evaluation": evaluation,
                "passes_threshold": evaluation.get("passes_threshold", False)
            }
            
        except Exception as e:
            logger.error("Single task execution failed", 
                       task_id=task.task_id,
                       error=str(e))
            
            return {
                "task_id": task.task_id,
                "status": "failed",
                "error": str(e),
                "duration_ms": int((time.time() - start_time) * 1000),
                "evaluation": None,
                "passes_threshold": False
            }
    
    async def _simulate_ai_response(self, task: Any) -> Dict[str, Any]:
        """Simulate AI response for testing purposes."""
        # In real implementation, this would call the actual AI system
        await asyncio.sleep(0.1)  # Simulate processing time
        
        # Simulate response based on task difficulty
        if task.difficulty.value == "easy":
            confidence = 0.9
            success_rate = 0.95
        elif task.difficulty.value == "medium":
            confidence = 0.8
            success_rate = 0.85
        else:  # hard or expert
            confidence = 0.7
            success_rate = 0.75
        
        # Simulate success/failure
        import random
        if random.random() < success_rate:
            response = task.expected_response
            intent = task.expected_intent
            tools_used = task.expected_tools
        else:
            response = "I'm not sure how to help with that. Could you provide more details?"
            intent = "unclear"
            tools_used = []
            confidence *= 0.8
        
        return {
            "response": response,
            "intent": intent,
            "confidence": confidence,
            "tools_used": tools_used
        }
    
    async def _calculate_metrics(
        self,
        results: List[Dict[str, Any]],
        tenant_id: str
    ) -> Dict[str, Any]:
        """Calculate evaluation metrics."""
        total_tasks = len(results)
        completed_tasks = len([r for r in results if r["status"] == "completed"])
        failed_tasks = total_tasks - completed_tasks
        
        if completed_tasks == 0:
            return {
                "total_tasks": total_tasks,
                "completed_tasks": 0,
                "failed_tasks": failed_tasks,
                "success_rate": 0.0,
                "average_score": 0.0,
                "pass_rate": 0.0,
                "average_duration_ms": 0,
                "score_distribution": {}
            }
        
        # Calculate scores
        evaluations = [r["evaluation"] for r in results if r["evaluation"]]
        scores = [e.get("overall_score", 0.0) for e in evaluations]
        
        # Calculate pass rate
        passes = [r["passes_threshold"] for r in results if r["status"] == "completed"]
        pass_rate = sum(passes) / len(passes) if passes else 0.0
        
        # Calculate duration
        durations = [r["duration_ms"] for r in results if r["duration_ms"] > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # Score distribution
        score_distribution = {
            "excellent": len([s for s in scores if s >= 0.9]),
            "good": len([s for s in scores if 0.7 <= s < 0.9]),
            "fair": len([s for s in scores if 0.5 <= s < 0.7]),
            "poor": len([s for s in scores if s < 0.5])
        }
        
        return {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "success_rate": completed_tasks / total_tasks,
            "average_score": sum(scores) / len(scores) if scores else 0.0,
            "pass_rate": pass_rate,
            "average_duration_ms": avg_duration,
            "score_distribution": score_distribution
        }
    
    async def _generate_report(
        self,
        evaluation_id: str,
        tenant_id: str,
        tasks: List[Any],
        results: List[Dict[str, Any]],
        metrics: Dict[str, Any],
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate comprehensive evaluation report."""
        return await self.report_generator.generate_report(
            evaluation_id=evaluation_id,
            tenant_id=tenant_id,
            tasks=tasks,
            results=results,
            metrics=metrics,
            config=config
        )
    
    async def _check_threshold(
        self,
        metrics: Dict[str, Any],
        config: Dict[str, Any]
    ) -> bool:
        """Check if evaluation passes threshold."""
        threshold_config = config.get("thresholds", {})
        
        # Check pass rate threshold
        pass_rate_threshold = threshold_config.get("pass_rate", 0.8)
        if metrics["pass_rate"] < pass_rate_threshold:
            return False
        
        # Check average score threshold
        score_threshold = threshold_config.get("average_score", 0.7)
        if metrics["average_score"] < score_threshold:
            return False
        
        # Check success rate threshold
        success_rate_threshold = threshold_config.get("success_rate", 0.9)
        if metrics["success_rate"] < success_rate_threshold:
            return False
        
        return True
    
    async def _store_evaluation_results(
        self,
        evaluation_id: str,
        tenant_id: str,
        results: List[Dict[str, Any]],
        metrics: Dict[str, Any],
        report: Dict[str, Any]
    ) -> None:
        """Store evaluation results."""
        try:
            evaluation_data = {
                "evaluation_id": evaluation_id,
                "tenant_id": tenant_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "results": results,
                "metrics": metrics,
                "report": report
            }
            
            # Store in Redis
            key = f"evaluation:{evaluation_id}"
            await self.redis_client.setex(key, 86400, json.dumps(evaluation_data))  # 24 hours TTL
            
            # Store in file system
            report_file = Path("eval/reports") / f"{evaluation_id}.json"
            report_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(report_file, 'w') as f:
                json.dump(evaluation_data, f, indent=2)
            
            logger.info("Evaluation results stored", 
                       evaluation_id=evaluation_id,
                       redis_key=key,
                       file_path=str(report_file))
            
        except Exception as e:
            logger.error("Failed to store evaluation results", 
                        evaluation_id=evaluation_id,
                        error=str(e))


async def main():
    """Main function for running evaluation."""
    parser = argparse.ArgumentParser(description="Run AI system evaluation")
    parser.add_argument("--tenant-id", required=True, help="Tenant ID for evaluation")
    parser.add_argument("--config-file", help="Configuration file path")
    parser.add_argument("--max-tasks", type=int, default=50, help="Maximum number of tasks")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size for parallel execution")
    parser.add_argument("--threshold-pass-rate", type=float, default=0.8, help="Pass rate threshold")
    parser.add_argument("--threshold-average-score", type=float, default=0.7, help="Average score threshold")
    parser.add_argument("--categories", nargs="+", help="Task categories to evaluate")
    parser.add_argument("--difficulties", nargs="+", help="Task difficulties to evaluate")
    parser.add_argument("--tiers", nargs="+", help="Expected tiers to evaluate")
    parser.add_argument("--output-file", help="Output file for results")
    parser.add_argument("--ci-mode", action="store_true", help="Run in CI mode with strict thresholds")
    
    args = parser.parse_args()
    
    # Load configuration
    if args.config_file:
        with open(args.config_file, 'r') as f:
            config = json.load(f)
    else:
        config = {
            "redis_url": "redis://localhost:6379",
            "openai_api_key": "your-api-key-here",
            "judge_model": "gpt-4",
            "episode_storage_path": "eval/episodes"
        }
    
    # Override with command line arguments
    config["max_tasks"] = args.max_tasks
    config["batch_size"] = args.batch_size
    
    # Set up evaluation configuration
    evaluation_config = {
        "task_filters": {
            "categories": args.categories or ["faq", "order", "tracking", "lead"],
            "difficulties": args.difficulties or ["easy", "medium"],
            "tiers": args.tiers or ["SLM_A", "SLM_B"]
        },
        "thresholds": {
            "pass_rate": args.threshold_pass_rate,
            "average_score": args.threshold_average_score,
            "success_rate": 0.9
        }
    }
    
    # CI mode adjustments
    if args.ci_mode:
        evaluation_config["thresholds"]["pass_rate"] = 0.85
        evaluation_config["thresholds"]["average_score"] = 0.75
        evaluation_config["max_tasks"] = 100  # More comprehensive in CI
    
    # Run evaluation
    async with EvaluationRunner(config) as runner:
        result = await runner.run_evaluation(args.tenant_id, evaluation_config)
        
        # Output results
        if args.output_file:
            with open(args.output_file, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"Results saved to {args.output_file}")
        else:
            print(json.dumps(result, indent=2))
        
        # Exit with appropriate code
        if result["status"] == "failed":
            sys.exit(1)
        elif not result.get("passes_threshold", False):
            sys.exit(2)  # Failed threshold
        else:
            sys.exit(0)  # Success


if __name__ == "__main__":
    asyncio.run(main())