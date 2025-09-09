"""Bandit policy for cost optimization and routing decisions."""

import asyncio
import math
import random
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
import structlog
import redis.asyncio as redis
from dataclasses import dataclass

logger = structlog.get_logger(__name__)


@dataclass
class RouterTier:
    """Router tier definition."""
    name: str
    cost_per_request: float
    latency_ms: float
    success_rate: float
    max_tokens: int
    capabilities: List[str]


@dataclass
class RoutingDecision:
    """Routing decision result."""
    tier: str
    confidence: float
    expected_cost: float
    expected_latency: float
    reasons: List[str]
    policy_escalation: bool


class BanditPolicy:
    """Bandit policy for intelligent routing decisions."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.tiers = {
            "SLM_A": RouterTier(
                name="SLM_A",
                cost_per_request=0.001,
                latency_ms=50,
                success_rate=0.85,
                max_tokens=1000,
                capabilities=["simple_qa", "classification", "json_validation"]
            ),
            "SLM_B": RouterTier(
                name="SLM_B", 
                cost_per_request=0.005,
                latency_ms=200,
                success_rate=0.92,
                max_tokens=2000,
                capabilities=["complex_qa", "reasoning", "multi_step"]
            ),
            "LLM": RouterTier(
                name="LLM",
                cost_per_request=0.02,
                latency_ms=1000,
                success_rate=0.95,
                max_tokens=4000,
                capabilities=["advanced_reasoning", "creative", "complex_analysis"]
            )
        }
        
        # Bandit parameters
        self.exploration_rate = 0.1  # 10% exploration
        self.learning_rate = 0.01
        self.confidence_threshold = 0.8
        
        # Cost optimization parameters
        self.cost_weight = 0.3
        self.quality_weight = 0.7
        self.latency_weight = 0.1
    
    async def decide_route(
        self,
        features: Dict[str, Any],
        tenant_id: UUID,
        request_id: str
    ) -> RoutingDecision:
        """Make routing decision using bandit policy."""
        try:
            # Calculate tier scores
            tier_scores = await self._calculate_tier_scores(features, tenant_id)
            
            # Apply bandit policy
            selected_tier = await self._select_tier(tier_scores, tenant_id)
            
            # Calculate confidence and expected values
            confidence = tier_scores[selected_tier]["confidence"]
            expected_cost = self.tiers[selected_tier].cost_per_request
            expected_latency = self.tiers[selected_tier].latency_ms
            
            # Generate reasons
            reasons = self._generate_reasons(features, selected_tier, tier_scores)
            
            # Check if policy escalation is needed
            policy_escalation = confidence < self.confidence_threshold
            
            decision = RoutingDecision(
                tier=selected_tier,
                confidence=confidence,
                expected_cost=expected_cost,
                expected_latency=expected_latency,
                reasons=reasons,
                policy_escalation=policy_escalation
            )
            
            # Store decision for learning
            await self._store_decision(request_id, features, decision, tenant_id)
            
            logger.info("Routing decision made", 
                       tier=selected_tier, 
                       confidence=confidence,
                       tenant_id=tenant_id)
            
            return decision
            
        except Exception as e:
            logger.error("Routing decision failed", 
                        tenant_id=tenant_id, 
                        error=str(e))
            # Fallback to LLM tier
            return RoutingDecision(
                tier="LLM",
                confidence=0.5,
                expected_cost=self.tiers["LLM"].cost_per_request,
                expected_latency=self.tiers["LLM"].latency_ms,
                reasons=["Fallback due to error"],
                policy_escalation=True
            )
    
    async def _calculate_tier_scores(
        self, 
        features: Dict[str, Any], 
        tenant_id: UUID
    ) -> Dict[str, Dict[str, float]]:
        """Calculate scores for each tier."""
        scores = {}
        
        for tier_name, tier in self.tiers.items():
            # Get historical performance for this tier
            performance = await self._get_tier_performance(tier_name, tenant_id)
            
            # Calculate base score
            base_score = self._calculate_base_score(features, tier)
            
            # Apply historical performance
            historical_factor = self._calculate_historical_factor(performance)
            
            # Calculate confidence
            confidence = self._calculate_confidence(features, tier, performance)
            
            # Calculate final score
            final_score = base_score * historical_factor
            
            scores[tier_name] = {
                "score": final_score,
                "confidence": confidence,
                "base_score": base_score,
                "historical_factor": historical_factor
            }
        
        return scores
    
    def _calculate_base_score(self, features: Dict[str, Any], tier: RouterTier) -> float:
        """Calculate base score for tier based on features."""
        score = 0.0
        
        # Text complexity scoring
        text_length = features.get("text_length", 0)
        word_count = features.get("word_count", 0)
        avg_word_length = features.get("avg_word_length", 0)
        
        # Simple requests favor SLM_A
        if text_length < 100 and word_count < 20:
            if tier.name == "SLM_A":
                score += 0.8
            elif tier.name == "SLM_B":
                score += 0.6
            else:
                score += 0.4
        
        # Complex requests favor higher tiers
        elif text_length > 500 or word_count > 100:
            if tier.name == "LLM":
                score += 0.9
            elif tier.name == "SLM_B":
                score += 0.7
            else:
                score += 0.3
        
        # Intent-based scoring
        if features.get("has_question", False):
            if tier.name == "SLM_A":
                score += 0.6
            elif tier.name == "SLM_B":
                score += 0.8
            else:
                score += 0.7
        
        if features.get("has_technical_terms", False):
            if tier.name == "LLM":
                score += 0.8
            elif tier.name == "SLM_B":
                score += 0.6
            else:
                score += 0.3
        
        # Urgency scoring
        if features.get("has_urgency", False):
            # Urgent requests favor faster tiers
            if tier.name == "SLM_A":
                score += 0.7
            elif tier.name == "SLM_B":
                score += 0.8
            else:
                score += 0.5
        
        # Cost optimization
        cost_factor = 1.0 - (tier.cost_per_request * self.cost_weight)
        score *= cost_factor
        
        # Latency optimization
        latency_factor = 1.0 - (tier.latency_ms / 1000.0 * self.latency_weight)
        score *= latency_factor
        
        return max(0.0, min(1.0, score))
    
    async def _get_tier_performance(self, tier_name: str, tenant_id: UUID) -> Dict[str, float]:
        """Get historical performance for tier."""
        try:
            performance_key = f"tier_performance:{tier_name}:{tenant_id}"
            performance = await self.redis.hgetall(performance_key)
            
            if performance:
                return {
                    "success_rate": float(performance.get("success_rate", 0.0)),
                    "avg_latency": float(performance.get("avg_latency", 0.0)),
                    "request_count": int(performance.get("request_count", 0)),
                    "last_updated": float(performance.get("last_updated", 0.0))
                }
            else:
                # Default performance based on tier
                tier = self.tiers[tier_name]
                return {
                    "success_rate": tier.success_rate,
                    "avg_latency": tier.latency_ms,
                    "request_count": 0,
                    "last_updated": 0.0
                }
                
        except Exception as e:
            logger.error("Failed to get tier performance", 
                        tier_name=tier_name, 
                        error=str(e))
            return {
                "success_rate": 0.0,
                "avg_latency": 0.0,
                "request_count": 0,
                "last_updated": 0.0
            }
    
    def _calculate_historical_factor(self, performance: Dict[str, float]) -> float:
        """Calculate historical performance factor."""
        success_rate = performance["success_rate"]
        request_count = performance["request_count"]
        
        # Weight by request count (more data = more reliable)
        weight = min(1.0, request_count / 100.0)
        
        # Factor in success rate
        factor = success_rate * weight + (1.0 - weight) * 0.5
        
        return max(0.1, min(1.0, factor))
    
    def _calculate_confidence(
        self, 
        features: Dict[str, Any], 
        tier: RouterTier, 
        performance: Dict[str, float]
    ) -> float:
        """Calculate confidence in routing decision."""
        # Base confidence on tier capabilities
        capability_match = 0.0
        if features.get("has_question", False) and "simple_qa" in tier.capabilities:
            capability_match += 0.3
        if features.get("has_technical_terms", False) and "advanced_reasoning" in tier.capabilities:
            capability_match += 0.4
        if features.get("text_length", 0) > 500 and "complex_analysis" in tier.capabilities:
            capability_match += 0.3
        
        # Historical confidence
        historical_confidence = performance["success_rate"]
        
        # Combine factors
        confidence = (capability_match + historical_confidence) / 2.0
        
        return max(0.0, min(1.0, confidence))
    
    async def _select_tier(
        self, 
        tier_scores: Dict[str, Dict[str, float]], 
        tenant_id: UUID
    ) -> str:
        """Select tier using bandit policy."""
        # Check if we should explore
        if random.random() < self.exploration_rate:
            # Exploration: select random tier
            return random.choice(list(tier_scores.keys()))
        
        # Exploitation: select best tier
        best_tier = max(tier_scores.keys(), key=lambda t: tier_scores[t]["score"])
        
        # Check for canary mode
        if await self._is_canary_mode(tenant_id):
            # 10% chance to use different tier for A/B testing
            if random.random() < 0.1:
                alternatives = [t for t in tier_scores.keys() if t != best_tier]
                if alternatives:
                    return random.choice(alternatives)
        
        return best_tier
    
    async def _is_canary_mode(self, tenant_id: UUID) -> bool:
        """Check if tenant is in canary mode."""
        try:
            canary_key = f"canary_mode:{tenant_id}"
            return await self.redis.get(canary_key) == "true"
        except Exception:
            return False
    
    def _generate_reasons(
        self, 
        features: Dict[str, Any], 
        selected_tier: str, 
        tier_scores: Dict[str, Dict[str, float]]
    ) -> List[str]:
        """Generate human-readable reasons for decision."""
        reasons = []
        
        # Text complexity reasons
        text_length = features.get("text_length", 0)
        if text_length < 100:
            reasons.append("Short request suitable for fast processing")
        elif text_length > 500:
            reasons.append("Complex request requires advanced processing")
        
        # Intent-based reasons
        if features.get("has_question", False):
            reasons.append("Question detected - using appropriate tier")
        
        if features.get("has_technical_terms", False):
            reasons.append("Technical content requires advanced capabilities")
        
        # Cost reasons
        if selected_tier == "SLM_A":
            reasons.append("Cost-optimized for simple request")
        elif selected_tier == "LLM":
            reasons.append("Complex request requires full LLM capabilities")
        
        # Historical reasons
        score_info = tier_scores[selected_tier]
        if score_info["historical_factor"] > 0.8:
            reasons.append("Strong historical performance for this tier")
        
        return reasons
    
    async def _store_decision(
        self, 
        request_id: str, 
        features: Dict[str, Any], 
        decision: RoutingDecision, 
        tenant_id: UUID
    ):
        """Store decision for learning and analysis."""
        try:
            decision_data = {
                "request_id": request_id,
                "tier": decision.tier,
                "confidence": decision.confidence,
                "features": features,
                "timestamp": time.time(),
                "tenant_id": str(tenant_id)
            }
            
            # Store in Redis
            decision_key = f"routing_decisions:{tenant_id}"
            import json
            await self.redis.lpush(decision_key, json.dumps(decision_data))
            await self.redis.ltrim(decision_key, 0, 10000)  # Keep last 10k decisions
            await self.redis.expire(decision_key, 86400 * 7)  # 7 days
            
        except Exception as e:
            logger.error("Failed to store decision", 
                        request_id=request_id, 
                        error=str(e))
    
    async def update_performance(
        self, 
        tier: str, 
        success: bool, 
        latency_ms: float, 
        tenant_id: UUID
    ):
        """Update tier performance based on actual results."""
        try:
            performance_key = f"tier_performance:{tier}:{tenant_id}"
            
            # Get current performance
            current = await self.redis.hgetall(performance_key)
            if not current:
                current = {
                    "success_rate": "0.0",
                    "avg_latency": "0.0",
                    "request_count": "0",
                    "last_updated": "0.0"
                }
            
            # Update metrics
            success_rate = float(current["success_rate"])
            avg_latency = float(current["avg_latency"])
            request_count = int(current["request_count"])
            
            # Update with exponential moving average
            new_success_rate = (success_rate * request_count + (1.0 if success else 0.0)) / (request_count + 1)
            new_avg_latency = (avg_latency * request_count + latency_ms) / (request_count + 1)
            new_request_count = request_count + 1
            
            # Store updated performance
            await self.redis.hset(performance_key, mapping={
                "success_rate": str(new_success_rate),
                "avg_latency": str(new_avg_latency),
                "request_count": str(new_request_count),
                "last_updated": str(time.time())
            })
            
            logger.debug("Performance updated", 
                        tier=tier, 
                        success=success, 
                        latency_ms=latency_ms,
                        tenant_id=tenant_id)
            
        except Exception as e:
            logger.error("Failed to update performance", 
                        tier=tier, 
                        error=str(e))
