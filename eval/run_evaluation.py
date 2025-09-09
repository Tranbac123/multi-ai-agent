"""Main evaluation runner for the AIaaS platform."""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import UUID
import structlog
import argparse

from .golden_tasks.faq_tasks import get_faq_tasks
from .golden_tasks.order_tasks import get_order_tasks
from .judges.llm_judge import LLMJudge
from .episode_replay import episode_recorder, episode_replayer

logger = structlog.get_logger(__name__)


class EvaluationRunner:
    """Main evaluation runner."""
    
    def __init__(self, openai_api_key: str):
        self.llm_judge = LLMJudge(openai_api_key)
        self.results: Dict[str, Any] = {}
    
    async def run_evaluation(
        self,
        tenant_id: UUID,
        task_categories: List[str] = None,
        max_tasks: int = None
    ) -> Dict[str, Any]:
        """Run comprehensive evaluation."""
        if task_categories is None:
            task_categories = ["faq", "order"]
        
        logger.info("Starting evaluation", 
                   tenant_id=tenant_id, 
                   categories=task_categories)
        
        evaluation_start = time.time()
        all_tasks = []
        all_results = []
        
        # Collect tasks from all categories
        for category in task_categories:
            if category == "faq":
                tasks = get_faq_tasks()
            elif category == "order":
                tasks = get_order_tasks()
            else:
                logger.warning("Unknown task category", category=category)
                continue
            
            all_tasks.extend(tasks)
        
        # Limit tasks if specified
        if max_tasks and len(all_tasks) > max_tasks:
            all_tasks = all_tasks[:max_tasks]
        
        logger.info("Collected tasks", 
                   total_tasks=len(all_tasks), 
                   categories=task_categories)
        
        # Run tasks
        for i, task in enumerate(all_tasks):
            logger.info("Running task", 
                       task_id=task.task_id, 
                       progress=f"{i+1}/{len(all_tasks)}")
            
            try:
                # Simulate task execution (replace with actual execution)
                result = await self._simulate_task_execution(task, tenant_id)
                all_results.append(result)
                
            except Exception as e:
                logger.error("Task execution failed", 
                            task_id=task.task_id, 
                            error=str(e))
                # Add failed result
                all_results.append({
                    "task_id": task.task_id,
                    "success": False,
                    "error": str(e),
                    "actual_response": "",
                    "actual_intent": "",
                    "actual_confidence": 0.0,
                    "actual_tools_used": []
                })
        
        # Evaluate results
        logger.info("Starting evaluation of results")
        evaluations = await self.llm_judge.batch_evaluate(
            [self._task_to_dict(task) for task in all_tasks],
            all_results,
            tenant_id
        )
        
        # Calculate overall statistics
        evaluation_duration = time.time() - evaluation_start
        stats = self._calculate_statistics(all_tasks, all_results, evaluations)
        
        # Compile final results
        final_results = {
            "evaluation_id": f"eval_{int(time.time())}",
            "tenant_id": str(tenant_id),
            "start_time": evaluation_start,
            "end_time": time.time(),
            "duration": evaluation_duration,
            "task_categories": task_categories,
            "total_tasks": len(all_tasks),
            "statistics": stats,
            "task_results": [
                {
                    "task": self._task_to_dict(task),
                    "result": result,
                    "evaluation": evaluation
                }
                for task, result, evaluation in zip(all_tasks, all_results, evaluations)
            ]
        }
        
        self.results[final_results["evaluation_id"]] = final_results
        
        logger.info("Evaluation completed", 
                   evaluation_id=final_results["evaluation_id"], 
                   duration=evaluation_duration)
        
        return final_results
    
    async def _simulate_task_execution(
        self, 
        task, 
        tenant_id: UUID
    ) -> Dict[str, Any]:
        """Simulate task execution (replace with actual execution)."""
        # This would typically call the actual AI system
        # For now, simulate based on expected values
        
        await asyncio.sleep(0.1)  # Simulate processing time
        
        # Simulate response based on task
        if task.category == "faq":
            # Simulate FAQ response
            actual_response = f"FAQ Response for: {task.input_text}"
            actual_intent = task.expected_intent
            actual_confidence = task.expected_confidence + 0.05  # Slightly higher
            actual_tools_used = task.expected_tools
        elif task.category == "order":
            # Simulate order response
            actual_response = f"Order Response for: {task.input_text}"
            actual_intent = task.expected_intent
            actual_confidence = task.expected_confidence - 0.05  # Slightly lower
            actual_tools_used = task.expected_tools
        else:
            # Default simulation
            actual_response = f"Response for: {task.input_text}"
            actual_intent = "unknown"
            actual_confidence = 0.5
            actual_tools_used = []
        
        return {
            "task_id": task.task_id,
            "success": True,
            "actual_response": actual_response,
            "actual_intent": actual_intent,
            "actual_confidence": actual_confidence,
            "actual_tools_used": actual_tools_used,
            "execution_time": 0.1
        }
    
    def _task_to_dict(self, task) -> Dict[str, Any]:
        """Convert task to dictionary."""
        return {
            "task_id": task.task_id,
            "category": task.category,
            "input_text": task.input_text,
            "expected_response": task.expected_response,
            "expected_intent": task.expected_intent,
            "expected_confidence": task.expected_confidence,
            "expected_tools": task.expected_tools,
            "metadata": task.metadata
        }
    
    def _calculate_statistics(
        self, 
        tasks: List, 
        results: List[Dict[str, Any]], 
        evaluations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate evaluation statistics."""
        total_tasks = len(tasks)
        successful_tasks = sum(1 for result in results if result["success"])
        
        # Calculate average scores
        avg_scores = {
            "overall_score": 0.0,
            "response_quality": 0.0,
            "intent_accuracy": 0.0,
            "confidence_appropriateness": 0.0,
            "tool_usage_correctness": 0.0
        }
        
        if evaluations:
            for score in avg_scores:
                avg_scores[score] = sum(
                    eval.get(score, 0.0) for eval in evaluations
                ) / len(evaluations)
        
        # Calculate pass rate
        passes = sum(1 for eval in evaluations if eval.get("passes_threshold", False))
        pass_rate = passes / len(evaluations) if evaluations else 0.0
        
        # Calculate category breakdown
        category_stats = {}
        for task in tasks:
            category = task.category
            if category not in category_stats:
                category_stats[category] = {
                    "total": 0,
                    "successful": 0,
                    "avg_score": 0.0
                }
            category_stats[category]["total"] += 1
        
        # Calculate difficulty breakdown
        difficulty_stats = {}
        for task in tasks:
            difficulty = task.metadata.get("difficulty", "unknown")
            if difficulty not in difficulty_stats:
                difficulty_stats[difficulty] = {
                    "total": 0,
                    "successful": 0,
                    "avg_score": 0.0
                }
            difficulty_stats[difficulty]["total"] += 1
        
        return {
            "total_tasks": total_tasks,
            "successful_tasks": successful_tasks,
            "success_rate": successful_tasks / total_tasks if total_tasks > 0 else 0.0,
            "pass_rate": pass_rate,
            "average_scores": avg_scores,
            "category_breakdown": category_stats,
            "difficulty_breakdown": difficulty_stats
        }
    
    def save_results(self, evaluation_id: str, file_path: str):
        """Save evaluation results to file."""
        if evaluation_id not in self.results:
            raise ValueError(f"Evaluation {evaluation_id} not found")
        
        with open(file_path, 'w') as f:
            json.dump(self.results[evaluation_id], f, indent=2)
        
        logger.info("Results saved", 
                   evaluation_id=evaluation_id, 
                   file_path=file_path)
    
    def load_results(self, file_path: str) -> Dict[str, Any]:
        """Load evaluation results from file."""
        with open(file_path, 'r') as f:
            results = json.load(f)
        
        self.results[results["evaluation_id"]] = results
        
        logger.info("Results loaded", 
                   evaluation_id=results["evaluation_id"], 
                   file_path=file_path)
        
        return results


async def main():
    """Main evaluation runner."""
    parser = argparse.ArgumentParser(description="Run AIaaS evaluation")
    parser.add_argument("--tenant-id", required=True, help="Tenant ID")
    parser.add_argument("--categories", nargs="+", default=["faq", "order"], 
                       help="Task categories to evaluate")
    parser.add_argument("--max-tasks", type=int, help="Maximum number of tasks")
    parser.add_argument("--openai-api-key", required=True, help="OpenAI API key")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--replay", help="Replay episode ID")
    
    args = parser.parse_args()
    
    # Initialize evaluation runner
    runner = EvaluationRunner(args.openai_api_key)
    
    if args.replay:
        # Replay specific episode
        logger.info("Replaying episode", episode_id=args.replay)
        # Implementation for episode replay would go here
    else:
        # Run evaluation
        tenant_id = UUID(args.tenant_id)
        results = await runner.run_evaluation(
            tenant_id=tenant_id,
            task_categories=args.categories,
            max_tasks=args.max_tasks
        )
        
        # Save results if output file specified
        if args.output:
            runner.save_results(results["evaluation_id"], args.output)
        
        # Print summary
        print(f"Evaluation completed: {results['evaluation_id']}")
        print(f"Total tasks: {results['total_tasks']}")
        print(f"Success rate: {results['statistics']['success_rate']:.2%}")
        print(f"Pass rate: {results['statistics']['pass_rate']:.2%}")
        print(f"Duration: {results['duration']:.2f} seconds")


if __name__ == "__main__":
    asyncio.run(main())
