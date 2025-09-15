"""Evaluation report models."""

import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class EvaluationMetrics:
    """Evaluation metrics."""

    average_score: float
    score_distribution: Dict[str, int]
    tier_accuracy: float
    cost_efficiency: float
    latency_performance: float


@dataclass
class EvaluationReport:
    """Evaluation report."""

    evaluation_type: str  # router, agent, end_to_end
    total_tasks: int
    successful_tasks: int
    metrics: EvaluationMetrics
    results: List[Dict[str, Any]]
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "evaluation_type": self.evaluation_type,
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "success_rate": self.successful_tasks / self.total_tasks
            if self.total_tasks > 0
            else 0.0,
            "metrics": {
                "average_score": self.metrics.average_score,
                "score_distribution": self.metrics.score_distribution,
                "tier_accuracy": self.metrics.tier_accuracy,
                "cost_efficiency": self.metrics.cost_efficiency,
                "latency_performance": self.metrics.latency_performance,
            },
            "results": self.results,
            "timestamp": self.timestamp.isoformat(),
        }

    def to_json(self) -> str:
        """Convert report to JSON string."""
        import json

        return json.dumps(self.to_dict(), indent=2)

    def save_to_file(self, filepath: str) -> None:
        """Save report to file."""
        import json

        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def get_summary(self) -> str:
        """Get summary of the report."""
        return f"""
Evaluation Report Summary
========================
Type: {self.evaluation_type}
Total Tasks: {self.total_tasks}
Successful Tasks: {self.successful_tasks}
Success Rate: {self.successful_tasks / self.total_tasks * 100:.1f}%

Metrics:
- Average Score: {self.metrics.average_score:.3f}
- Tier Accuracy: {self.metrics.tier_accuracy:.3f}
- Cost Efficiency: {self.metrics.cost_efficiency:.3f}
- Latency Performance: {self.metrics.latency_performance:.3f}

Score Distribution:
- 0.0-0.2: {self.metrics.score_distribution.get('0.0-0.2', 0)}
- 0.2-0.4: {self.metrics.score_distribution.get('0.2-0.4', 0)}
- 0.4-0.6: {self.metrics.score_distribution.get('0.4-0.6', 0)}
- 0.6-0.8: {self.metrics.score_distribution.get('0.6-0.8', 0)}
- 0.8-1.0: {self.metrics.score_distribution.get('0.8-1.0', 0)}
"""


class EvaluationReportGenerator:
    """Generate comprehensive evaluation reports."""

    def __init__(self):
        self.reports_dir = Path("eval/reports")
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    async def generate_report(
        self,
        evaluation_id: str,
        tenant_id: str,
        tasks: List[Any],
        results: List[Dict[str, Any]],
        metrics: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate comprehensive evaluation report."""
        timestamp = datetime.now(timezone.utc)

        # Calculate additional metrics
        task_categories = {}
        task_difficulties = {}
        task_tiers = {}

        for task in tasks:
            category = task.category.value
            difficulty = task.difficulty.value
            tier = task.expected_tier.value

            task_categories[category] = task_categories.get(category, 0) + 1
            task_difficulties[difficulty] = task_difficulties.get(difficulty, 0) + 1
            task_tiers[tier] = task_tiers.get(tier, 0) + 1

        # Generate recommendations
        recommendations = self._generate_recommendations(metrics, results)

        # Create report
        report = {
            "evaluation_id": evaluation_id,
            "tenant_id": tenant_id,
            "timestamp": timestamp.isoformat(),
            "summary": {
                "total_tasks": metrics["total_tasks"],
                "completed_tasks": metrics["completed_tasks"],
                "failed_tasks": metrics["failed_tasks"],
                "success_rate": metrics["success_rate"],
                "pass_rate": metrics["pass_rate"],
                "average_score": metrics["average_score"],
                "average_duration_ms": metrics["average_duration_ms"],
            },
            "task_breakdown": {
                "by_category": task_categories,
                "by_difficulty": task_difficulties,
                "by_tier": task_tiers,
            },
            "metrics": metrics,
            "score_distribution": metrics.get("score_distribution", {}),
            "recommendations": recommendations,
            "config": config,
            "detailed_results": results[:10],  # Include first 10 detailed results
        }

        # Save report to file
        report_file = self.reports_dir / f"{evaluation_id}.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        return report

    def _generate_recommendations(
        self, metrics: Dict[str, Any], results: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate recommendations based on evaluation results."""
        recommendations = []

        # Check success rate
        if metrics["success_rate"] < 0.9:
            recommendations.append(
                f"Success rate is {metrics['success_rate']:.1%}. "
                "Consider improving error handling and retry logic."
            )

        # Check pass rate
        if metrics["pass_rate"] < 0.8:
            recommendations.append(
                f"Pass rate is {metrics['pass_rate']:.1%}. "
                "Consider improving response quality and accuracy."
            )

        # Check average score
        if metrics["average_score"] < 0.7:
            recommendations.append(
                f"Average score is {metrics['average_score']:.3f}. "
                "Consider improving model performance or prompt engineering."
            )

        # Check duration
        if metrics["average_duration_ms"] > 5000:
            recommendations.append(
                f"Average duration is {metrics['average_duration_ms']:.0f}ms. "
                "Consider optimizing performance or reducing complexity."
            )

        # Check score distribution
        score_dist = metrics.get("score_distribution", {})
        poor_count = score_dist.get("poor", 0)
        total_tasks = metrics["total_tasks"]

        if poor_count > total_tasks * 0.1:  # More than 10% poor scores
            recommendations.append(
                f"{poor_count} tasks received poor scores. "
                "Consider reviewing task difficulty or model capabilities."
            )

        # Add general recommendations if no specific issues
        if not recommendations:
            recommendations.append(
                "Evaluation results look good! Consider running more comprehensive tests."
            )

        return recommendations

    def get_report_summary(self, evaluation_id: str) -> Optional[Dict[str, Any]]:
        """Get summary of a specific evaluation report."""
        report_file = self.reports_dir / f"{evaluation_id}.json"

        if not report_file.exists():
            return None

        with open(report_file, "r") as f:
            report = json.load(f)

        return {
            "evaluation_id": report["evaluation_id"],
            "tenant_id": report["tenant_id"],
            "timestamp": report["timestamp"],
            "summary": report["summary"],
            "recommendations": report["recommendations"],
        }

    def list_reports(self, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available evaluation reports."""
        reports = []

        for report_file in self.reports_dir.glob("*.json"):
            try:
                with open(report_file, "r") as f:
                    report = json.load(f)

                if tenant_id is None or report.get("tenant_id") == tenant_id:
                    reports.append(
                        {
                            "evaluation_id": report["evaluation_id"],
                            "tenant_id": report["tenant_id"],
                            "timestamp": report["timestamp"],
                            "summary": report["summary"],
                        }
                    )
            except (json.JSONDecodeError, KeyError):
                continue

        # Sort by timestamp (newest first)
        reports.sort(key=lambda x: x["timestamp"], reverse=True)

        return reports
