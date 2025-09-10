"""Router v2 with calibrated bandit policy, early exit, and canary support."""

import asyncio
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import structlog
import redis.asyncio as redis

from .feature_extractor import FeatureExtractor, RouterFeatures, Tier
from .calibrated_classifier import CalibratedClassifier
from .bandit_policy import BanditPolicy
from .early_exit_escalation import EarlyExitEscalation, EscalationDecision
from .canary_manager import CanaryManager
from .metrics import MetricsCollector

logger = structlog.get_logger(__name__)


@dataclass
class RouterDecision:
    """Router decision result."""
    tier: Tier
    confidence: float
    decision_time_ms: float
    features: RouterFeatures
    escalation_decision: Optional[EscalationDecision]
    canary_info: Optional[Dict[str, Any]]
    bandit_info: Optional[Dict[str, Any]]
    classifier_info: Optional[Dict[str, Any]]


class RouterV2:
    """Router v2 with calibrated bandit policy, early exit, and canary support."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.feature_extractor = FeatureExtractor(redis_client)
        self.classifier = CalibratedClassifier(redis_client)
        self.bandit_policy = BanditPolicy(redis_client)
        self.early_exit = EarlyExitEscalation(redis_client)
        self.canary_manager = CanaryManager(redis_client)
        self.metrics_collector = MetricsCollector(redis_client)
    
    async def route_request(
        self,
        request: Dict[str, Any],
        tenant_id: str,
        user_id: str
    ) -> RouterDecision:
        """Route request using router v2."""
        start_time = time.time()
        
        try:
            # Extract features
            features = await self.feature_extractor.extract_features(request, tenant_id, user_id)
            
            # Check for canary first
            is_canary, canary_tier, canary_info = await self.canary_manager.should_use_canary(
                tenant_id, user_id, features
            )
            
            if is_canary and canary_tier:
                decision_time = (time.time() - start_time) * 1000
                return RouterDecision(
                    tier=canary_tier,
                    confidence=0.9,  # High confidence for canary
                    decision_time_ms=decision_time,
                    features=features,
                    escalation_decision=None,
                    canary_info=canary_info,
                    bandit_info=None,
                    classifier_info=None
                )
            
            # Use calibrated classifier
            predicted_tier, confidence, should_escalate = await self.classifier.classify(features, tenant_id)
            
            # Check for early exit
            escalation_decision = await self.early_exit.make_escalation_decision(
                features, predicted_tier, confidence, tenant_id
            )
            
            if escalation_decision.early_exit_tier:
                # Early exit to Tier A
                decision_time = (time.time() - start_time) * 1000
                return RouterDecision(
                    tier=escalation_decision.early_exit_tier,
                    confidence=escalation_decision.early_exit_confidence,
                    decision_time_ms=decision_time,
                    features=features,
                    escalation_decision=escalation_decision,
                    canary_info=None,
                    bandit_info=None,
                    classifier_info={
                        'predicted_tier': predicted_tier.value,
                        'confidence': confidence,
                        'early_exit': True
                    }
                )
            
            # Use bandit policy for final decision
            final_tier, bandit_value, bandit_info = await self.bandit_policy.select_arm(
                features, tenant_id
            )
            
            # Apply escalation if needed
            if escalation_decision.should_escalate:
                final_tier = escalation_decision.target_tier
                confidence = min(confidence, 0.7)  # Reduce confidence for escalated requests
            
            decision_time = (time.time() - start_time) * 1000
            
            # Record metrics
            await self._record_router_metrics(tenant_id, final_tier, decision_time, features)
            
            # Record decision metrics
            expected_cost = self._calculate_cost(final_tier)
            actual_cost = expected_cost  # For now, assume actual equals expected
            await self.metrics_collector.record_decision(
                tenant_id, final_tier, decision_time, True, expected_cost, actual_cost
            )
            
            return RouterDecision(
                tier=final_tier,
                confidence=confidence,
                decision_time_ms=decision_time,
                features=features,
                escalation_decision=escalation_decision,
                canary_info=None,
                bandit_info=bandit_info,
                classifier_info={
                    'predicted_tier': predicted_tier.value,
                    'confidence': confidence,
                    'escalated': escalation_decision.should_escalate
                }
            )
            
        except Exception as e:
            logger.error("Router v2 failed", error=str(e))
            # Fallback to Tier B
            decision_time = (time.time() - start_time) * 1000
            return RouterDecision(
                tier=Tier.B,
                confidence=0.5,
                decision_time_ms=decision_time,
                features=features if 'features' in locals() else None,
                escalation_decision=None,
                canary_info=None,
                bandit_info=None,
                classifier_info={'error': str(e)}
            )
    
    async def record_outcome(
        self,
        tenant_id: str,
        user_id: str,
        tier: Tier,
        success: bool,
        latency: float,
        quality_score: float = 0.0
    ) -> None:
        """Record routing outcome for learning."""
        try:
            # Record for bandit policy
            cost = self._calculate_cost(tier)
            reward = 1.0 if success else 0.0
            error = not success
            
            await self.bandit_policy.update_arm(tenant_id, tier, reward, cost, error)
            
            # Record for canary if applicable
            is_canary, _, _ = await self.canary_manager.should_use_canary(tenant_id, user_id, None)
            if is_canary:
                await self.canary_manager.record_canary_outcome(
                    tenant_id, user_id, tier, success, latency, quality_score
                )
            
            # Record for escalation learning
            if not success:
                await self.early_exit.record_escalation_outcome(
                    tenant_id, tier, tier, None, success, latency
                )
            
            # Record outcome metrics
            expected_cost = self._calculate_cost(tier)
            actual_cost = expected_cost  # For now, assume actual equals expected
            await self.metrics_collector.record_decision(
                tenant_id, tier, latency, success, expected_cost, actual_cost
            )
            
        except Exception as e:
            logger.error("Failed to record outcome", error=str(e))
    
    def _calculate_cost(self, tier: Tier) -> float:
        """Calculate cost for tier."""
        cost_map = {
            Tier.A: 0.1,  # Cheap
            Tier.B: 0.5,  # Medium
            Tier.C: 1.0   # Expensive
        }
        return cost_map.get(tier, 0.5)
    
    async def _record_router_metrics(
        self,
        tenant_id: str,
        tier: Tier,
        decision_time_ms: float,
        features: RouterFeatures
    ) -> None:
        """Record router metrics."""
        try:
            metrics_key = f"router_metrics:{tenant_id}:{int(time.time() // 60)}"  # Per minute
            
            # Record decision metrics
            await self.redis.hincrby(metrics_key, 'total_decisions', 1)
            await self.redis.hincrby(metrics_key, f'decisions_{tier.value}', 1)
            await self.redis.hincrbyfloat(metrics_key, 'total_decision_time', decision_time_ms)
            await self.redis.hincrby(metrics_key, 'total_tokens', features.token_count)
            
            # Record feature metrics
            await self.redis.hincrbyfloat(metrics_key, 'total_complexity', features.request_complexity)
            await self.redis.hincrbyfloat(metrics_key, 'total_novelty', features.novelty_score)
            await self.redis.hincrbyfloat(metrics_key, 'total_failure_rate', features.historical_failure_rate)
            
            await self.redis.expire(metrics_key, 86400 * 7)  # 7 days TTL
            
        except Exception as e:
            logger.error("Failed to record router metrics", error=str(e))
    
    async def get_router_statistics(self, tenant_id: str) -> Dict[str, Any]:
        """Get router statistics for tenant."""
        try:
            # Get bandit statistics
            bandit_stats = await self.bandit_policy.get_arm_statistics(tenant_id)
            
            # Get canary status
            canary_status = await self.canary_manager.get_canary_status(tenant_id)
            
            # Get escalation statistics
            escalation_stats = await self.early_exit.get_escalation_statistics(tenant_id)
            
            # Get recent metrics
            recent_metrics = await self._get_recent_metrics(tenant_id)
            
            # Get metrics collector data
            metrics_data = await self.metrics_collector.get_metrics(tenant_id)
            
            return {
                'tenant_id': tenant_id,
                'bandit_statistics': bandit_stats,
                'canary_status': canary_status,
                'escalation_statistics': escalation_stats,
                'recent_metrics': recent_metrics,
                'metrics': {
                    'decision_latency_ms': metrics_data.decision_latency_ms,
                    'misroute_rate': metrics_data.misroute_rate,
                    'tier_distribution': metrics_data.tier_distribution,
                    'expected_vs_actual_cost': metrics_data.expected_vs_actual_cost,
                    'total_requests': metrics_data.total_requests,
                    'successful_requests': metrics_data.successful_requests,
                    'failed_requests': metrics_data.failed_requests
                }
            }
            
        except Exception as e:
            logger.error("Failed to get router statistics", error=str(e))
            return {'error': str(e)}
    
    async def _get_recent_metrics(self, tenant_id: str) -> Dict[str, Any]:
        """Get recent router metrics."""
        try:
            current_time = int(time.time() // 60)  # Current minute
            metrics_keys = []
            
            # Get last 60 minutes of metrics
            for i in range(60):
                minute_key = current_time - i
                metrics_key = f"router_metrics:{tenant_id}:{minute_key}"
                if await self.redis.exists(metrics_key):
                    metrics_keys.append(metrics_key)
            
            if not metrics_keys:
                return {'no_data': True}
            
            # Aggregate metrics
            total_decisions = 0
            tier_distribution = {tier.value: 0 for tier in Tier}
            total_decision_time = 0.0
            total_tokens = 0
            total_complexity = 0.0
            total_novelty = 0.0
            total_failure_rate = 0.0
            
            for metrics_key in metrics_keys:
                metrics_data = await self.redis.hgetall(metrics_key)
                if metrics_data:
                    total_decisions += int(metrics_data.get('total_decisions', 0))
                    for tier in Tier:
                        tier_distribution[tier.value] += int(metrics_data.get(f'decisions_{tier.value}', 0))
                    total_decision_time += float(metrics_data.get('total_decision_time', 0))
                    total_tokens += int(metrics_data.get('total_tokens', 0))
                    total_complexity += float(metrics_data.get('total_complexity', 0))
                    total_novelty += float(metrics_data.get('total_novelty', 0))
                    total_failure_rate += float(metrics_data.get('total_failure_rate', 0))
            
            if total_decisions == 0:
                return {'no_data': True}
            
            return {
                'total_decisions': total_decisions,
                'tier_distribution': tier_distribution,
                'average_decision_time_ms': total_decision_time / total_decisions,
                'average_tokens_per_request': total_tokens / total_decisions,
                'average_complexity': total_complexity / total_decisions,
                'average_novelty': total_novelty / total_decisions,
                'average_failure_rate': total_failure_rate / total_decisions,
                'time_window_minutes': len(metrics_keys)
            }
            
        except Exception as e:
            logger.error("Failed to get recent metrics", error=str(e))
            return {'error': str(e)}
    
    async def calibrate_models(self, tenant_id: str) -> None:
        """Calibrate all models for tenant."""
        try:
            # Calibrate classifier temperature
            await self.classifier.calibrate_temperature(tenant_id)
            
            logger.info("Models calibrated", tenant_id=tenant_id)
            
        except Exception as e:
            logger.error("Failed to calibrate models", error=str(e))
    
    async def reset_learning(self, tenant_id: str) -> None:
        """Reset learning for tenant."""
        try:
            # Reset bandit arms
            await self.bandit_policy.reset_arms(tenant_id)
            
            # Reset metrics
            await self.metrics_collector.reset_metrics(tenant_id)
            
            logger.info("Learning reset", tenant_id=tenant_id)
            
        except Exception as e:
            logger.error("Failed to reset learning", error=str(e))
    
    async def get_prometheus_metrics(self, tenant_id: str) -> Dict[str, Any]:
        """Get metrics in Prometheus format."""
        try:
            metrics_data = await self.metrics_collector.get_metrics(tenant_id)
            
            return {
                "router_decision_latency_ms": metrics_data.decision_latency_ms,
                "router_misroute_rate": metrics_data.misroute_rate,
                "tier_distribution": metrics_data.tier_distribution,
                "expected_vs_actual_cost": metrics_data.expected_vs_actual_cost,
                "total_requests": metrics_data.total_requests,
                "successful_requests": metrics_data.successful_requests,
                "failed_requests": metrics_data.failed_requests
            }
            
        except Exception as e:
            logger.error("Failed to get Prometheus metrics", error=str(e))
            return {
                "router_decision_latency_ms": 0.0,
                "router_misroute_rate": 0.0,
                "tier_distribution": {},
                "expected_vs_actual_cost": 0.0,
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0
            }
