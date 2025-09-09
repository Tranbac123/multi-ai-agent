"""Evaluation report models."""

from typing import Dict, Any, List
from dataclasses import dataclass
from datetime import datetime


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
            "success_rate": self.successful_tasks / self.total_tasks if self.total_tasks > 0 else 0.0,
            "metrics": {
                "average_score": self.metrics.average_score,
                "score_distribution": self.metrics.score_distribution,
                "tier_accuracy": self.metrics.tier_accuracy,
                "cost_efficiency": self.metrics.cost_efficiency,
                "latency_performance": self.metrics.latency_performance
            },
            "results": self.results,
            "timestamp": self.timestamp.isoformat()
        }
    
    def to_json(self) -> str:
        """Convert report to JSON string."""
        import json
        return json.dumps(self.to_dict(), indent=2)
    
    def save_to_file(self, filepath: str) -> None:
        """Save report to file."""
        import json
        with open(filepath, 'w') as f:
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
