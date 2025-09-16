"""
Canary Manager for Router v2

Implements per-tenant canary deployments with automatic rollback
on quality drift detection.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import structlog
from datetime import datetime, timedelta
import statistics

logger = structlog.get_logger(__name__)


class CanaryStatus(Enum):
    """Canary deployment status."""
    INACTIVE = "inactive"
    ACTIVE = "active"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class CanaryConfig:
    """Canary deployment configuration."""
    
    tenant_id: str
    canary_percentage: float  # 5-10% traffic to canary
    quality_threshold: float  # Quality threshold for rollback
    evaluation_window_minutes: int  # Time window for evaluation
    min_requests: int  # Minimum requests before evaluation
    max_evaluation_time_minutes: int  # Maximum evaluation time
    auto_rollback_enabled: bool  # Enable automatic rollback


@dataclass
class RequestMetrics:
    """Metrics for a single request."""
    
    timestamp: datetime
    tier: str
    success: bool
    latency_ms: float
    cost_usd: float
    quality_score: Optional[float] = None
    user_feedback: Optional[int] = None  # 1-5 rating


@dataclass
class CanaryDeployment:
    """Canary deployment state."""
    
    tenant_id: str
    config: CanaryConfig
    status: CanaryStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    
    # Metrics tracking
    baseline_metrics: List[RequestMetrics] = field(default_factory=list)
    canary_metrics: List[RequestMetrics] = field(default_factory=list)
    
    # Quality tracking
    baseline_quality_scores: List[float] = field(default_factory=list)
    canary_quality_scores: List[float] = field(default_factory=list)
    
    # Decision tracking
    decisions_made: int = 0
    canary_decisions: int = 0
    
    # Rollback information
    rollback_reason: Optional[str] = None
    rollback_time: Optional[datetime] = None


class QualityDriftDetector:
    """Detects quality drift in canary deployments."""
    
    def __init__(self):
        self.drift_threshold = 0.1  # 10% quality degradation
        self.statistical_significance_level = 0.05  # 5% significance level
    
    def detect_drift(
        self, 
        baseline_scores: List[float], 
        canary_scores: List[float]
    ) -> Tuple[bool, float, str]:
        """Detect quality drift between baseline and canary."""
        
        if len(baseline_scores) < 10 or len(canary_scores) < 10:
            return False, 0.0, "Insufficient data for drift detection"
        
        # Calculate means
        baseline_mean = statistics.mean(baseline_scores)
        canary_mean = statistics.mean(canary_scores)
        
        # Calculate drift percentage
        drift_percentage = (baseline_mean - canary_mean) / baseline_mean
        
        # Check if drift exceeds threshold
        significant_drift = drift_percentage > self.drift_threshold
        
        # Statistical significance test (simplified t-test)
        is_statistically_significant = self._is_statistically_significant(
            baseline_scores, canary_scores
        )
        
        # Generate reason
        if significant_drift and is_statistically_significant:
            reason = f"Significant quality drift detected: {drift_percentage:.1%} degradation"
            return True, drift_percentage, reason
        elif significant_drift:
            reason = f"Quality drift detected but not statistically significant: {drift_percentage:.1%}"
            return False, drift_percentage, reason
        else:
            reason = f"No significant drift: {drift_percentage:.1%}"
            return False, drift_percentage, reason
    
    def _is_statistically_significant(
        self, 
        baseline_scores: List[float], 
        canary_scores: List[float]
    ) -> bool:
        """Check statistical significance using Welch's t-test (simplified)."""
        
        # Calculate means and variances
        baseline_mean = statistics.mean(baseline_scores)
        canary_mean = statistics.mean(canary_scores)
        
        baseline_var = statistics.variance(baseline_scores, baseline_mean)
        canary_var = statistics.variance(canary_scores, canary_mean)
        
        # Calculate standard error
        se = (baseline_var / len(baseline_scores) + canary_var / len(canary_scores)) ** 0.5
        
        # Calculate t-statistic
        if se == 0:
            return False
        
        t_stat = abs(baseline_mean - canary_mean) / se
        
        # Simplified significance check (in production, use proper t-test)
        # For now, consider significant if t > 2 (approximately 95% confidence)
        return t_stat > 2.0


class QualityScoreCalculator:
    """Calculates quality scores for requests."""
    
    def __init__(self):
        self.weights = {
            "success_rate": 0.4,
            "latency_score": 0.2,
            "cost_score": 0.1,
            "user_feedback": 0.3
        }
    
    def calculate_quality_score(self, metrics: RequestMetrics) -> float:
        """Calculate quality score for a single request."""
        
        scores = {}
        
        # Success rate (binary)
        scores["success_rate"] = 1.0 if metrics.success else 0.0
        
        # Latency score (inverse of latency, normalized)
        # Good latency: < 1000ms = 1.0, > 5000ms = 0.0
        latency_score = max(0.0, 1.0 - (metrics.latency_ms - 1000) / 4000)
        scores["latency_score"] = latency_score
        
        # Cost score (lower cost is better, normalized)
        # Good cost: < $0.01 = 1.0, > $0.05 = 0.0
        cost_score = max(0.0, 1.0 - (metrics.cost_usd - 0.01) / 0.04)
        scores["cost_score"] = cost_score
        
        # User feedback (if available)
        if metrics.user_feedback is not None:
            scores["user_feedback"] = metrics.user_feedback / 5.0
        else:
            scores["user_feedback"] = 0.5  # Neutral if no feedback
        
        # Calculate weighted score
        quality_score = sum(
            scores[metric] * weight 
            for metric, weight in self.weights.items()
        )
        
        return min(1.0, quality_score)
    
    def calculate_batch_quality_score(self, metrics_list: List[RequestMetrics]) -> float:
        """Calculate average quality score for a batch of requests."""
        
        if not metrics_list:
            return 0.0
        
        quality_scores = [self.calculate_quality_score(metrics) for metrics in metrics_list]
        return statistics.mean(quality_scores)


class CanaryManager:
    """Manages canary deployments for router decisions."""
    
    def __init__(self):
        self.active_deployments: Dict[str, CanaryDeployment] = {}
        self.drift_detector = QualityDriftDetector()
        self.quality_calculator = QualityScoreCalculator()
        
        # Statistics
        self.total_deployments = 0
        self.successful_deployments = 0
        self.rolled_back_deployments = 0
        
        logger.info("Canary manager initialized")
    
    def start_canary(
        self, 
        tenant_id: str, 
        canary_percentage: float = 0.05,
        quality_threshold: float = 0.8
    ) -> CanaryDeployment:
        """Start a new canary deployment."""
        
        if tenant_id in self.active_deployments:
            raise ValueError(f"Canary deployment already active for tenant {tenant_id}")
        
        config = CanaryConfig(
            tenant_id=tenant_id,
            canary_percentage=canary_percentage,
            quality_threshold=quality_threshold,
            evaluation_window_minutes=30,
            min_requests=50,
            max_evaluation_time_minutes=60,
            auto_rollback_enabled=True
        )
        
        deployment = CanaryDeployment(
            tenant_id=tenant_id,
            config=config,
            status=CanaryStatus.ACTIVE,
            start_time=datetime.now()
        )
        
        self.active_deployments[tenant_id] = deployment
        self.total_deployments += 1
        
        logger.info("Canary deployment started", 
                   tenant_id=tenant_id,
                   canary_percentage=canary_percentage,
                   quality_threshold=quality_threshold)
        
        return deployment
    
    def should_route_to_canary(self, tenant_id: str) -> bool:
        """Determine if request should be routed to canary."""
        
        if tenant_id not in self.active_deployments:
            return False
        
        deployment = self.active_deployments[tenant_id]
        
        if deployment.status != CanaryStatus.ACTIVE:
            return False
        
        # Simple random routing based on percentage
        import random
        return random.random() < deployment.config.canary_percentage
    
    def record_request_metrics(
        self, 
        tenant_id: str, 
        tier: str, 
        success: bool, 
        latency_ms: float, 
        cost_usd: float,
        is_canary: bool = False,
        quality_score: Optional[float] = None,
        user_feedback: Optional[int] = None
    ):
        """Record metrics for a request."""
        
        if tenant_id not in self.active_deployments:
            return
        
        deployment = self.active_deployments[tenant_id]
        
        if deployment.status != CanaryStatus.ACTIVE:
            return
        
        metrics = RequestMetrics(
            timestamp=datetime.now(),
            tier=tier,
            success=success,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            quality_score=quality_score,
            user_feedback=user_feedback
        )
        
        if is_canary:
            deployment.canary_metrics.append(metrics)
            deployment.canary_decisions += 1
            
            # Calculate and store quality score
            if quality_score is None:
                quality_score = self.quality_calculator.calculate_quality_score(metrics)
            deployment.canary_quality_scores.append(quality_score)
        else:
            deployment.baseline_metrics.append(metrics)
            deployment.decisions_made += 1
            
            # Calculate and store quality score
            if quality_score is None:
                quality_score = self.quality_calculator.calculate_quality_score(metrics)
            deployment.baseline_quality_scores.append(quality_score)
        
        # Check if we should evaluate for drift
        self._evaluate_deployment(deployment)
    
    def _evaluate_deployment(self, deployment: CanaryDeployment):
        """Evaluate deployment for quality drift."""
        
        # Check minimum requests requirement
        if (len(deployment.canary_metrics) < deployment.config.min_requests or
            len(deployment.baseline_metrics) < deployment.config.min_requests):
            return
        
        # Check evaluation time window
        elapsed_minutes = (datetime.now() - deployment.start_time).total_seconds() / 60
        if elapsed_minutes > deployment.config.max_evaluation_time_minutes:
            self._complete_deployment(deployment, "Evaluation time exceeded")
            return
        
        # Detect quality drift
        has_drift, drift_percentage, reason = self.drift_detector.detect_drift(
            deployment.baseline_quality_scores,
            deployment.canary_quality_scores
        )
        
        if has_drift and deployment.config.auto_rollback_enabled:
            self._rollback_deployment(deployment, reason)
        elif elapsed_minutes >= deployment.config.evaluation_window_minutes:
            # Evaluation complete, check if canary is better
            baseline_quality = statistics.mean(deployment.baseline_quality_scores)
            canary_quality = statistics.mean(deployment.canary_quality_scores)
            
            if canary_quality > baseline_quality + 0.05:  # 5% improvement
                self._complete_deployment(deployment, "Canary shows improvement")
            else:
                self._rollback_deployment(deployment, "No significant improvement")
    
    def _rollback_deployment(self, deployment: CanaryDeployment, reason: str):
        """Rollback a canary deployment."""
        
        deployment.status = CanaryStatus.ROLLING_BACK
        deployment.rollback_reason = reason
        deployment.rollback_time = datetime.now()
        
        logger.warning("Canary deployment rolled back", 
                      tenant_id=deployment.tenant_id,
                      reason=reason)
        
        # Complete rollback after a short delay
        asyncio.create_task(self._complete_rollback(deployment))
    
    async def _complete_rollback(self, deployment: CanaryDeployment):
        """Complete the rollback process."""
        
        # Simulate rollback delay
        await asyncio.sleep(1)
        
        deployment.status = CanaryStatus.ROLLED_BACK
        deployment.end_time = datetime.now()
        
        self.rolled_back_deployments += 1
        
        logger.info("Canary rollback completed", 
                   tenant_id=deployment.tenant_id,
                   duration_minutes=(deployment.end_time - deployment.start_time).total_seconds() / 60)
        
        # Remove from active deployments
        if deployment.tenant_id in self.active_deployments:
            del self.active_deployments[deployment.tenant_id]
    
    def _complete_deployment(self, deployment: CanaryDeployment, reason: str):
        """Complete a successful deployment."""
        
        deployment.status = CanaryStatus.ACTIVE  # Keep active for now
        deployment.end_time = datetime.now()
        
        self.successful_deployments += 1
        
        logger.info("Canary deployment completed successfully", 
                   tenant_id=deployment.tenant_id,
                   reason=reason,
                   duration_minutes=(deployment.end_time - deployment.start_time).total_seconds() / 60)
        
        # In production, this would trigger the actual deployment
        # For now, we just log the success
    
    def stop_canary(self, tenant_id: str) -> bool:
        """Stop a canary deployment."""
        
        if tenant_id not in self.active_deployments:
            return False
        
        deployment = self.active_deployments[tenant_id]
        deployment.status = CanaryStatus.ROLLED_BACK
        deployment.end_time = datetime.now()
        deployment.rollback_reason = "Manually stopped"
        
        del self.active_deployments[tenant_id]
        
        logger.info("Canary deployment stopped", tenant_id=tenant_id)
        return True
    
    def get_deployment_status(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a canary deployment."""
        
        if tenant_id not in self.active_deployments:
            return None
        
        deployment = self.active_deployments[tenant_id]
        
        return {
            "tenant_id": tenant_id,
            "status": deployment.status.value,
            "start_time": deployment.start_time.isoformat(),
            "duration_minutes": (datetime.now() - deployment.start_time).total_seconds() / 60,
            "canary_percentage": deployment.config.canary_percentage,
            "decisions_made": deployment.decisions_made,
            "canary_decisions": deployment.canary_decisions,
            "baseline_quality": statistics.mean(deployment.baseline_quality_scores) if deployment.baseline_quality_scores else 0.0,
            "canary_quality": statistics.mean(deployment.canary_quality_scores) if deployment.canary_quality_scores else 0.0,
            "rollback_reason": deployment.rollback_reason
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get canary manager statistics."""
        
        return {
            "total_deployments": self.total_deployments,
            "active_deployments": len(self.active_deployments),
            "successful_deployments": self.successful_deployments,
            "rolled_back_deployments": self.rolled_back_deployments,
            "success_rate": self.successful_deployments / max(1, self.total_deployments),
            "active_tenants": list(self.active_deployments.keys())
        }
