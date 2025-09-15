"""Enhanced router engine with cost optimization and early exit."""

import asyncio
import time
from typing import Dict, Any, Optional, List
from uuid import UUID
import structlog

from libs.contracts.router import (
    RouterDecisionRequest,
    RouterDecisionResponse,
    RouterTier,
    TextFeatures,
    HistoryStats,
)
from libs.contracts.error import ErrorSpec, ErrorCode
from .features import FeatureExtractor
from .classifier import MLClassifier
from .cost import CostCalculator
from .judge import LLMJudge

logger = structlog.get_logger(__name__)


class RouterEngine:
    """Enhanced router engine with cost optimization and early exit."""

    def __init__(
        self,
        feature_extractor: FeatureExtractor,
        classifier: MLClassifier,
        cost_calculator: CostCalculator,
        llm_judge: LLMJudge,
    ):
        self.feature_extractor = feature_extractor
        self.classifier = classifier
        self.cost_calculator = cost_calculator
        self.llm_judge = llm_judge
        self.metrics = {
            "total_requests": 0,
            "tier_distribution": {tier.value: 0 for tier in RouterTier},
            "avg_decision_time_ms": 0.0,
            "misroute_rate": 0.0,
            "cost_savings_usd": 0.0,
        }
        self._ready = False
        self._initialize()

    def _initialize(self):
        """Initialize router engine."""
        try:
            # Initialize components
            self.feature_extractor.initialize()
            self.classifier.initialize()
            self.cost_calculator.initialize()
            self.llm_judge.initialize()

            self._ready = True
            logger.info("Router engine initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize router engine", error=str(e))
            self._ready = False

    def is_ready(self) -> bool:
        """Check if router engine is ready."""
        return self._ready

    async def route(self, request: RouterDecisionRequest) -> RouterDecisionResponse:
        """Route request to appropriate tier."""
        start_time = time.time()

        try:
            # Extract features
            features = await self.feature_extractor.extract(request)

            # Early exit for simple cases
            if self._should_early_exit(features):
                tier = RouterTier.SLM_A
                confidence = 0.95
                reasons = ["Early exit: Simple case detected"]
            else:
                # Use classifier for tier prediction
                tier_probs = await self.classifier.predict(features)

                # Use LLM judge for borderline cases
                if self._is_borderline(tier_probs):
                    judge_result = await self.llm_judge.judge(request, features)
                    tier = judge_result.tier
                    confidence = judge_result.confidence
                    reasons = judge_result.reasons
                else:
                    tier = self._select_tier(tier_probs)
                    confidence = tier_probs.get(tier.value, 0.0)
                    reasons = [f"Classifier prediction: {tier.value}"]

            # Calculate expected cost and latency
            expected_cost = await self.cost_calculator.calculate_cost(tier, features)
            expected_latency = self._calculate_expected_latency(tier)

            # Apply budget constraints
            if request.budget_usd and expected_cost > request.budget_usd:
                tier = self._downgrade_tier(tier)
                expected_cost = await self.cost_calculator.calculate_cost(
                    tier, features
                )
                expected_latency = self._calculate_expected_latency(tier)
                reasons.append(f"Budget constraint: Downgraded to {tier.value}")

            # Apply latency constraints
            if request.max_latency_ms and expected_latency > request.max_latency_ms:
                tier = self._downgrade_tier(tier)
                expected_latency = self._calculate_expected_latency(tier)
                reasons.append(f"Latency constraint: Downgraded to {tier.value}")

            # Check for policy escalation
            policy_escalation = self._check_policy_escalation(features, tier)
            if policy_escalation:
                tier = RouterTier.LLM
                confidence = 0.9
                reasons.append("Policy escalation: Escalated to LLM")

            # Create response
            response = RouterDecisionResponse(
                request_id=request.request_id,
                tier=tier,
                confidence=confidence,
                expected_cost_usd=expected_cost,
                expected_latency_ms=expected_latency,
                reasons=reasons,
                policy_escalation=policy_escalation,
                fallback_tier=self._get_fallback_tier(tier),
            )

            # Update metrics
            self._update_metrics(tier, time.time() - start_time)

            return response

        except Exception as e:
            logger.error(
                "Routing failed", error=str(e), request_id=str(request.request_id)
            )
            raise

    def _should_early_exit(self, features: TextFeatures) -> bool:
        """Check if request should use early exit to SLM_A."""
        # Simple heuristics for early exit
        return (
            features.token_count < 50
            and features.json_schema_complexity < 0.3
            and features.novelty_score < 0.2
            and features.historical_failure_rate < 0.1
            and not any(features.domain_flags.values())
        )

    def _is_borderline(self, tier_probs: Dict[str, float]) -> bool:
        """Check if tier probabilities are borderline."""
        max_prob = max(tier_probs.values())
        second_max_prob = sorted(tier_probs.values(), reverse=True)[1]

        return max_prob - second_max_prob < 0.2

    def _select_tier(self, tier_probs: Dict[str, float]) -> RouterTier:
        """Select tier based on probabilities."""
        # Use cost-aware selection
        best_tier = RouterTier.SLM_A
        best_score = float("inf")

        for tier_name, prob in tier_probs.items():
            tier = RouterTier(tier_name)
            # Score = expected_cost / success_probability
            score = self._get_tier_cost(tier) / max(prob, 0.1)

            if score < best_score:
                best_score = score
                best_tier = tier

        return best_tier

    def _get_tier_cost(self, tier: RouterTier) -> float:
        """Get base cost for tier."""
        costs = {RouterTier.SLM_A: 0.001, RouterTier.SLM_B: 0.005, RouterTier.LLM: 0.02}
        return costs.get(tier, 0.02)

    def _calculate_expected_latency(self, tier: RouterTier) -> int:
        """Calculate expected latency for tier."""
        latencies = {RouterTier.SLM_A: 100, RouterTier.SLM_B: 300, RouterTier.LLM: 1000}
        return latencies.get(tier, 1000)

    def _downgrade_tier(self, tier: RouterTier) -> RouterTier:
        """Downgrade tier to lower cost option."""
        if tier == RouterTier.LLM:
            return RouterTier.SLM_B
        elif tier == RouterTier.SLM_B:
            return RouterTier.SLM_A
        else:
            return tier

    def _check_policy_escalation(
        self, features: TextFeatures, tier: RouterTier
    ) -> bool:
        """Check if policy requires escalation."""
        # Escalate to LLM for high-risk domains
        high_risk_domains = ["finance", "legal", "medical"]
        if any(
            features.domain_flags.get(domain, False) for domain in high_risk_domains
        ):
            return tier != RouterTier.LLM

        # Escalate for high novelty
        if features.novelty_score > 0.8:
            return tier != RouterTier.LLM

        return False

    def _get_fallback_tier(self, tier: RouterTier) -> Optional[RouterTier]:
        """Get fallback tier for primary tier."""
        fallbacks = {
            RouterTier.LLM: RouterTier.SLM_B,
            RouterTier.SLM_B: RouterTier.SLM_A,
            RouterTier.SLM_A: None,
        }
        return fallbacks.get(tier)

    def _update_metrics(self, tier: RouterTier, decision_time: float):
        """Update router metrics."""
        self.metrics["total_requests"] += 1
        self.metrics["tier_distribution"][tier.value] += 1

        # Update average decision time
        total_requests = self.metrics["total_requests"]
        current_avg = self.metrics["avg_decision_time_ms"]
        self.metrics["avg_decision_time_ms"] = (
            current_avg * (total_requests - 1) + decision_time * 1000
        ) / total_requests

    async def get_metrics(self) -> Dict[str, Any]:
        """Get router metrics."""
        return {
            "total_requests": self.metrics["total_requests"],
            "tier_distribution": self.metrics["tier_distribution"],
            "avg_decision_time_ms": self.metrics["avg_decision_time_ms"],
            "misroute_rate": self.metrics["misroute_rate"],
            "cost_savings_usd": self.metrics["cost_savings_usd"],
        }
