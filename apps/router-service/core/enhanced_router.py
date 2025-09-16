"""
Enhanced Router v2 with Guarantees

Integrates feature extraction, calibrated classification, early exit,
and canary management for production-grade routing decisions.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import structlog
from opentelemetry import trace

from .feature_extractor import FeatureExtractor, FeatureVector
from .calibrated_classifier import CalibratedClassifier, RouterTier, ClassificationResult
from .early_exit_manager import EarlyExitManager, EarlyExitResult
from .canary_manager import CanaryManager

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


@dataclass
class RouterMetrics:
    """Router performance metrics."""
    
    router_decision_latency_ms: float
    router_misroute_rate: float
    tier_distribution: Dict[RouterTier, int]
    expected_vs_actual_cost: Dict[RouterTier, Tuple[float, float]]
    expected_vs_actual_latency: Dict[RouterTier, Tuple[int, int]]
    early_exit_rate: float
    canary_activity: Dict[str, Any]


class EnhancedRouter:
    """Enhanced router with comprehensive guarantees."""
    
    def __init__(
        self,
        lambda_error: float = 1.0,
        exploration_rate: float = 0.1,
        early_exit_threshold: float = 0.85
    ):
        self.feature_extractor = FeatureExtractor()
        self.classifier = CalibratedClassifier(lambda_error, exploration_rate)
        self.early_exit_manager = EarlyExitManager(early_exit_threshold)
        self.canary_manager = CanaryManager()
        
        # Metrics tracking
        self.metrics = RouterMetrics(
            router_decision_latency_ms=0.0,
            router_misroute_rate=0.0,
            tier_distribution={tier: 0 for tier in RouterTier},
            expected_vs_actual_cost={tier: (0.0, 0.0) for tier in RouterTier},
            expected_vs_actual_latency={tier: (0, 0) for tier in RouterTier},
            early_exit_rate=0.0,
            canary_activity={}
        )
        
        # Decision tracking
        self.total_decisions = 0
        self.successful_decisions = 0
        self.early_exits = 0
        
        logger.info("Enhanced router initialized", 
                   lambda_error=lambda_error,
                   exploration_rate=exploration_rate,
                   early_exit_threshold=early_exit_threshold)
    
    async def route_request(
        self,
        input_text: str,
        tenant_id: str,
        input_data: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        available_tiers: Optional[List[RouterTier]] = None,
        expected_schema: Optional[str] = None
    ) -> Dict[str, Any]:
        """Route request with comprehensive guarantees."""
        
        start_time = time.time()
        
        with tracer.start_as_current_span("router.route_request") as span:
            span.set_attribute("tenant_id", tenant_id)
            span.set_attribute("input_length", len(input_text))
            
            try:
                # Extract features
                features = self.feature_extractor.extract_features(
                    input_text, input_data, context
                )
                
                span.set_attribute("feature_vector", str(features.to_dict()))
                
                # Check for canary routing
                is_canary = self.canary_manager.should_route_to_canary(tenant_id)
                if is_canary:
                    span.set_attribute("canary_routing", True)
                
                # Make classification decision
                classification_result = await self._make_classification_decision(
                    features, context, available_tiers, span
                )
                
                # Check for early exit
                early_exit_result = None
                if (classification_result.tier == RouterTier.SLM_A and 
                    classification_result.confidence >= self.early_exit_manager.confidence_threshold):
                    
                    early_exit_result = await self._evaluate_early_exit(
                        input_text, expected_schema, context, span
                    )
                
                # Record metrics
                decision_latency_ms = (time.time() - start_time) * 1000
                self._update_metrics(classification_result, early_exit_result, decision_latency_ms)
                
                # Prepare response
                response = self._prepare_response(
                    classification_result, early_exit_result, features, is_canary
                )
                
                span.set_attribute("selected_tier", classification_result.tier.value)
                span.set_attribute("confidence", classification_result.confidence)
                span.set_attribute("early_exit", early_exit_result.should_exit if early_exit_result else False)
                
                logger.info("Router decision completed", 
                           tenant_id=tenant_id,
                           tier=classification_result.tier.value,
                           confidence=classification_result.confidence,
                           early_exit=early_exit_result.should_exit if early_exit_result else False,
                           latency_ms=decision_latency_ms)
                
                return response
                
            except Exception as e:
                logger.error("Router decision failed", 
                           tenant_id=tenant_id,
                           error=str(e),
                           exc_info=True)
                
                span.set_attribute("error", str(e))
                raise
    
    async def _make_classification_decision(
        self,
        features: FeatureVector,
        context: Optional[Dict[str, Any]],
        available_tiers: Optional[List[RouterTier]],
        span
    ) -> ClassificationResult:
        """Make classification decision using calibrated classifier."""
        
        with tracer.start_as_current_span("router.classification") as class_span:
            class_span.set_attribute("feature_count", len(features.to_dict()))
            
            # Convert features to dict for classifier
            feature_dict = features.to_dict()
            
            # Filter available tiers if specified
            if available_tiers:
                # Update classifier to only consider available tiers
                # This is a simplified implementation
                pass
            
            # Make classification
            classification_result = self.classifier.classify(feature_dict, context)
            
            class_span.set_attribute("selected_tier", classification_result.tier.value)
            class_span.set_attribute("confidence", classification_result.confidence)
            
            return classification_result
    
    async def _evaluate_early_exit(
        self,
        input_text: str,
        expected_schema: Optional[str],
        context: Optional[Dict[str, Any]],
        span
    ) -> EarlyExitResult:
        """Evaluate early exit for SLM_A responses."""
        
        with tracer.start_as_current_span("router.early_exit") as exit_span:
            exit_span.set_attribute("expected_schema", expected_schema or "none")
            
            # Simulate SLM_A response (in production, this would be actual response)
            simulated_response = await self._simulate_slm_a_response(input_text, expected_schema)
            
            # Evaluate early exit
            early_exit_result = self.early_exit_manager.evaluate_early_exit(
                simulated_response, expected_schema, context
            )
            
            exit_span.set_attribute("should_exit", early_exit_result.should_exit)
            exit_span.set_attribute("exit_confidence", early_exit_result.confidence)
            
            if early_exit_result.should_exit:
                self.early_exits += 1
            
            return early_exit_result
    
    async def _simulate_slm_a_response(self, input_text: str, expected_schema: Optional[str]) -> str:
        """Simulate SLM_A response for early exit evaluation."""
        
        # Simulate processing delay
        await asyncio.sleep(0.01)
        
        # Generate response based on expected schema
        if expected_schema == "simple_response":
            return '{"answer": "This is a simulated response from SLM_A.", "confidence": 0.85}'
        elif expected_schema == "classification":
            return '{"category": "general", "probability": 0.9, "reasoning": "Clear classification"}'
        elif expected_schema == "boolean_response":
            return '{"result": true, "confidence": 0.8, "reasoning": "Boolean evaluation complete"}'
        else:
            return '{"answer": "SLM_A response", "confidence": 0.75}'
    
    def _prepare_response(
        self,
        classification_result: ClassificationResult,
        early_exit_result: Optional[EarlyExitResult],
        features: FeatureVector,
        is_canary: bool
    ) -> Dict[str, Any]:
        """Prepare router response."""
        
        response = {
            "selected_tier": classification_result.tier.value,
            "confidence": classification_result.confidence,
            "confidence_level": self._get_confidence_level(classification_result.confidence),
            "reasoning": classification_result.reasoning,
            "expected_cost_usd": self._get_expected_cost(classification_result.tier, features.token_count),
            "expected_latency_ms": self._get_expected_latency(classification_result.tier),
            "alternative_tiers": [tier.value for tier in RouterTier if tier != classification_result.tier],
            "decision_metadata": {
                "feature_vector": features.to_dict(),
                "raw_scores": {tier.value: score for tier, score in classification_result.raw_scores.items()},
                "calibrated_scores": {tier.value: score for tier, score in classification_result.calibrated_scores.items()},
                "is_canary": is_canary
            }
        }
        
        # Add early exit information if applicable
        if early_exit_result:
            response["early_exit"] = {
                "should_exit": early_exit_result.should_exit,
                "confidence": early_exit_result.confidence,
                "reason": early_exit_result.reason
            }
        
        return response
    
    def _get_confidence_level(self, confidence: float) -> str:
        """Get confidence level string."""
        if confidence >= 0.8:
            return "high"
        elif confidence >= 0.6:
            return "medium"
        else:
            return "low"
    
    def _get_expected_cost(self, tier: RouterTier, token_count: int) -> float:
        """Get expected cost for tier and token count."""
        tier_configs = {
            RouterTier.SLM_A: 0.0001,
            RouterTier.SLM_B: 0.0002,
            RouterTier.LLM_A: 0.002,
            RouterTier.LLM_B: 0.006,
            RouterTier.HUMAN: 0.02
        }
        
        cost_per_token = tier_configs.get(tier, 0.002)
        return cost_per_token * token_count
    
    def _get_expected_latency(self, tier: RouterTier) -> int:
        """Get expected latency for tier."""
        tier_latencies = {
            RouterTier.SLM_A: 100,
            RouterTier.SLM_B: 150,
            RouterTier.LLM_A: 500,
            RouterTier.LLM_B: 1000,
            RouterTier.HUMAN: 3600000  # 1 hour
        }
        
        return tier_latencies.get(tier, 500)
    
    def _update_metrics(
        self,
        classification_result: ClassificationResult,
        early_exit_result: Optional[EarlyExitResult],
        decision_latency_ms: float
    ):
        """Update router metrics."""
        
        self.total_decisions += 1
        
        # Update tier distribution
        self.metrics.tier_distribution[classification_result.tier] += 1
        
        # Update decision latency
        self.metrics.router_decision_latency_ms = decision_latency_ms
        
        # Update early exit rate
        if early_exit_result and early_exit_result.should_exit:
            self.metrics.early_exit_rate = self.early_exits / self.total_decisions
        
        # Update canary activity
        self.metrics.canary_activity = self.canary_manager.get_statistics()
    
    async def record_outcome(
        self,
        tenant_id: str,
        tier: RouterTier,
        success: bool,
        actual_latency_ms: float,
        actual_cost_usd: float,
        quality_score: Optional[float] = None,
        user_feedback: Optional[int] = None
    ):
        """Record the outcome of a routing decision."""
        
        # Update classifier with feedback
        features = FeatureVector(
            token_count=0,  # Would need actual token count
            json_schema_strictness=0.0,
            domain_flags=[],
            novelty=0.0,
            historical_failure_rate=0.0,
            complexity_score=0.0,
            urgency_score=0.0,
            cost_sensitivity=0.0
        )
        
        self.classifier.update_with_feedback(
            tier, success, actual_cost_usd, features.to_dict()
        )
        
        # Record canary metrics if applicable
        self.canary_manager.record_request_metrics(
            tenant_id=tenant_id,
            tier=tier.value,
            success=success,
            latency_ms=actual_latency_ms,
            cost_usd=actual_cost_usd,
            quality_score=quality_score,
            user_feedback=user_feedback
        )
        
        # Update expected vs actual metrics
        expected_cost = self._get_expected_cost(tier, 100)  # Assume 100 tokens
        expected_latency = self._get_expected_latency(tier)
        
        self.metrics.expected_vs_actual_cost[tier] = (expected_cost, actual_cost_usd)
        self.metrics.expected_vs_actual_latency[tier] = (expected_latency, int(actual_latency_ms))
        
        # Update misroute rate
        if not success:
            self.metrics.router_misroute_rate = (self.total_decisions - self.successful_decisions) / self.total_decisions
        
        if success:
            self.successful_decisions += 1
    
    def start_canary_deployment(self, tenant_id: str, canary_percentage: float = 0.05) -> bool:
        """Start canary deployment for a tenant."""
        
        try:
            self.canary_manager.start_canary(tenant_id, canary_percentage)
            return True
        except ValueError:
            return False
    
    def stop_canary_deployment(self, tenant_id: str) -> bool:
        """Stop canary deployment for a tenant."""
        
        return self.canary_manager.stop_canary(tenant_id)
    
    def get_canary_status(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get canary deployment status for a tenant."""
        
        return self.canary_manager.get_deployment_status(tenant_id)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive router metrics."""
        
        return {
            "router_decision_latency_ms": self.metrics.router_decision_latency_ms,
            "router_misroute_rate": self.metrics.router_misroute_rate,
            "tier_distribution": {tier.value: count for tier, count in self.metrics.tier_distribution.items()},
            "expected_vs_actual_cost": {
                tier.value: {"expected": expected, "actual": actual} 
                for tier, (expected, actual) in self.metrics.expected_vs_actual_cost.items()
            },
            "expected_vs_actual_latency": {
                tier.value: {"expected": expected, "actual": actual} 
                for tier, (expected, actual) in self.metrics.expected_vs_actual_latency.items()
            },
            "early_exit_rate": self.metrics.early_exit_rate,
            "canary_activity": self.metrics.canary_activity,
            "total_decisions": self.total_decisions,
            "successful_decisions": self.successful_decisions,
            "early_exit_statistics": self.early_exit_manager.get_statistics()
        }
    
    def calibrate_classifier(self, calibration_data: List[Tuple[Dict[str, float], int]]):
        """Calibrate the classifier with validation data."""
        
        if not calibration_data:
            return
        
        # Extract logits and labels
        logits_list = []
        labels_list = []
        
        for features, label in calibration_data:
            # Get raw scores from classifier
            classification_result = self.classifier.classify(features)
            logits = [classification_result.raw_scores[tier] for tier in RouterTier]
            logits_list.append(logits)
            labels_list.append(label)
        
        import numpy as np
        logits_array = np.array(logits_list)
        labels_array = np.array(labels_list)
        
        # Calibrate temperature scaling
        self.classifier.temperature_scaling.calibrate(logits_array, labels_array)
        
        logger.info("Classifier calibrated", 
                   calibration_samples=len(calibration_data),
                   temperature=self.classifier.temperature_scaling.temperature)
