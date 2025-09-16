"""
Calibrated Classifier for Router v2

Implements calibrated classifier with temperature scaling and bandit policy
for minimizing E[cost + λ·error] in routing decisions.
"""

import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import structlog
import json
from datetime import datetime, timedelta

logger = structlog.get_logger(__name__)


class RouterTier(Enum):
    """Router tier enumeration."""
    SLM_A = "slm_a"
    SLM_B = "slm_b"
    LLM_A = "llm_a"
    LLM_B = "llm_b"
    HUMAN = "human"


@dataclass
class TierConfig:
    """Configuration for a routing tier."""
    
    tier: RouterTier
    cost_per_token: float  # USD per token
    latency_ms: int  # Expected latency in milliseconds
    accuracy_score: float  # Expected accuracy (0-1)
    availability: float  # Service availability (0-1)
    max_tokens: int  # Maximum token limit
    capabilities: List[str]  # Supported capabilities


@dataclass
class ClassificationResult:
    """Result of tier classification."""
    
    tier: RouterTier
    confidence: float
    raw_scores: Dict[RouterTier, float]
    calibrated_scores: Dict[RouterTier, float]
    reasoning: str


class TemperatureScaling:
    """Temperature scaling for calibration."""
    
    def __init__(self):
        self.temperature = 1.0
        self.calibration_data = []
        self.is_calibrated = False
    
    def calibrate(self, logits: np.ndarray, labels: np.ndarray) -> float:
        """Calibrate temperature scaling on validation data."""
        from scipy.optimize import minimize_scalar
        
        def temperature_loss(temp):
            scaled_logits = logits / temp
            scaled_probs = self._softmax(scaled_logits)
            
            # Calculate negative log likelihood
            nll = -np.mean(np.log(scaled_probs[np.arange(len(labels)), labels] + 1e-8))
            return nll
        
        # Optimize temperature
        result = minimize_scalar(temperature_loss, bounds=(0.1, 10.0), method='bounded')
        self.temperature = result.x
        self.is_calibrated = True
        
        logger.info("Temperature scaling calibrated", temperature=self.temperature)
        return self.temperature
    
    def apply_scaling(self, logits: np.ndarray) -> np.ndarray:
        """Apply temperature scaling to logits."""
        return logits / self.temperature
    
    def _softmax(self, logits: np.ndarray) -> np.ndarray:
        """Apply softmax function."""
        exp_logits = np.exp(logits - np.max(logits, axis=-1, keepdims=True))
        return exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)


class BanditPolicy:
    """Bandit policy for exploration-exploitation trade-off."""
    
    def __init__(self, exploration_rate: float = 0.1):
        self.exploration_rate = exploration_rate
        self.action_counts = {tier: 0 for tier in RouterTier}
        self.action_rewards = {tier: [] for tier in RouterTier}
        self.ucb_bonus = 2.0  # Upper confidence bound bonus
    
    def select_action(
        self, 
        calibrated_scores: Dict[RouterTier, float],
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[RouterTier, bool]:
        """Select action using epsilon-greedy with UCB."""
        
        # Epsilon-greedy exploration
        if np.random.random() < self.exploration_rate:
            # Explore: select random tier
            tier = np.random.choice(list(RouterTier))
            is_exploration = True
        else:
            # Exploit: select best tier with UCB
            tier = self._select_with_ucb(calibrated_scores)
            is_exploration = False
        
        return tier, is_exploration
    
    def _select_with_ucb(self, calibrated_scores: Dict[RouterTier, float]) -> RouterTier:
        """Select tier using Upper Confidence Bound."""
        total_actions = sum(self.action_counts.values())
        
        if total_actions == 0:
            # No actions taken yet, select randomly
            return np.random.choice(list(RouterTier))
        
        ucb_scores = {}
        for tier, score in calibrated_scores.items():
            if self.action_counts[tier] == 0:
                # Never selected this tier, give it high priority
                ucb_scores[tier] = float('inf')
            else:
                # Calculate average reward
                avg_reward = np.mean(self.action_rewards[tier]) if self.action_rewards[tier] else 0.0
                
                # Calculate UCB bonus
                ucb_bonus = self.ucb_bonus * np.sqrt(
                    np.log(total_actions) / self.action_counts[tier]
                )
                
                ucb_scores[tier] = avg_reward + ucb_bonus
        
        # Select tier with highest UCB score
        return max(ucb_scores.keys(), key=lambda t: ucb_scores[t])
    
    def update_reward(self, tier: RouterTier, reward: float):
        """Update reward for a tier."""
        self.action_counts[tier] += 1
        self.action_rewards[tier].append(reward)
        
        # Keep only recent rewards (sliding window)
        max_rewards = 100
        if len(self.action_rewards[tier]) > max_rewards:
            self.action_rewards[tier] = self.action_rewards[tier][-max_rewards:]


class CostOptimizer:
    """Optimizes routing decisions based on cost and error trade-offs."""
    
    def __init__(self, lambda_error: float = 1.0):
        self.lambda_error = lambda_error  # Weight for error in cost function
        self.tier_configs = self._initialize_tier_configs()
    
    def _initialize_tier_configs(self) -> Dict[RouterTier, TierConfig]:
        """Initialize tier configurations."""
        return {
            RouterTier.SLM_A: TierConfig(
                tier=RouterTier.SLM_A,
                cost_per_token=0.0001,  # $0.0001 per token
                latency_ms=100,
                accuracy_score=0.75,
                availability=0.99,
                max_tokens=4000,
                capabilities=["simple_qa", "classification", "basic_reasoning"]
            ),
            RouterTier.SLM_B: TierConfig(
                tier=RouterTier.SLM_B,
                cost_per_token=0.0002,  # $0.0002 per token
                latency_ms=150,
                accuracy_score=0.80,
                availability=0.98,
                max_tokens=4000,
                capabilities=["complex_qa", "analysis", "moderate_reasoning"]
            ),
            RouterTier.LLM_A: TierConfig(
                tier=RouterTier.LLM_A,
                cost_per_token=0.002,  # $0.002 per token
                latency_ms=500,
                accuracy_score=0.90,
                availability=0.95,
                max_tokens=8000,
                capabilities=["advanced_reasoning", "creative_writing", "complex_analysis"]
            ),
            RouterTier.LLM_B: TierConfig(
                tier=RouterTier.LLM_B,
                cost_per_token=0.006,  # $0.006 per token
                latency_ms=1000,
                accuracy_score=0.95,
                availability=0.90,
                max_tokens=16000,
                capabilities=["expert_reasoning", "research", "specialized_tasks"]
            ),
            RouterTier.HUMAN: TierConfig(
                tier=RouterTier.HUMAN,
                cost_per_token=0.02,  # $0.02 per token (human cost)
                latency_ms=3600000,  # 1 hour
                accuracy_score=0.98,
                availability=0.80,
                max_tokens=float('inf'),
                capabilities=["all"]
            )
        }
    
    def calculate_expected_cost(
        self, 
        tier: RouterTier, 
        token_count: int,
        error_probability: float
    ) -> float:
        """Calculate expected cost including error penalty."""
        config = self.tier_configs[tier]
        
        # Base cost
        base_cost = config.cost_per_token * token_count
        
        # Error penalty (cost of re-routing or correction)
        error_penalty = error_probability * self.lambda_error * base_cost
        
        return base_cost + error_penalty
    
    def calculate_error_probability(
        self, 
        tier: RouterTier, 
        confidence: float,
        complexity: float
    ) -> float:
        """Calculate error probability based on tier and confidence."""
        config = self.tier_configs[tier]
        
        # Base error rate (1 - accuracy)
        base_error_rate = 1.0 - config.accuracy_score
        
        # Adjust for confidence
        confidence_factor = 1.0 - confidence
        
        # Adjust for complexity
        complexity_factor = complexity * 0.5
        
        # Combined error probability
        error_probability = base_error_rate * (1.0 + confidence_factor + complexity_factor)
        
        return min(1.0, error_probability)


class CalibratedClassifier:
    """Main calibrated classifier for routing decisions."""
    
    def __init__(self, lambda_error: float = 1.0, exploration_rate: float = 0.1):
        self.temperature_scaling = TemperatureScaling()
        self.bandit_policy = BanditPolicy(exploration_rate=exploration_rate)
        self.cost_optimizer = CostOptimizer(lambda_error=lambda_error)
        
        # Model parameters (would be loaded from training in production)
        self.feature_weights = self._initialize_feature_weights()
        
        logger.info("Calibrated classifier initialized", 
                   lambda_error=lambda_error, 
                   exploration_rate=exploration_rate)
    
    def _initialize_feature_weights(self) -> Dict[RouterTier, Dict[str, float]]:
        """Initialize feature weights for each tier."""
        return {
            RouterTier.SLM_A: {
                "token_count": -0.001,
                "complexity_score": -0.5,
                "novelty": -0.3,
                "json_schema_strictness": 0.2,
                "urgency_score": 0.4,
                "cost_sensitivity": 0.6
            },
            RouterTier.SLM_B: {
                "token_count": -0.0005,
                "complexity_score": -0.2,
                "novelty": -0.1,
                "json_schema_strictness": 0.1,
                "urgency_score": 0.3,
                "cost_sensitivity": 0.4
            },
            RouterTier.LLM_A: {
                "token_count": -0.0002,
                "complexity_score": 0.3,
                "novelty": 0.2,
                "json_schema_strictness": 0.0,
                "urgency_score": 0.1,
                "cost_sensitivity": -0.2
            },
            RouterTier.LLM_B: {
                "token_count": -0.0001,
                "complexity_score": 0.5,
                "novelty": 0.4,
                "json_schema_strictness": -0.1,
                "urgency_score": -0.1,
                "cost_sensitivity": -0.4
            },
            RouterTier.HUMAN: {
                "token_count": 0.0,
                "complexity_score": 0.8,
                "novelty": 0.6,
                "json_schema_strictness": -0.2,
                "urgency_score": -0.3,
                "cost_sensitivity": -0.6
            }
        }
    
    def classify(
        self, 
        features: Dict[str, float],
        context: Optional[Dict[str, Any]] = None
    ) -> ClassificationResult:
        """Classify request and return routing decision."""
        
        # Calculate raw scores for each tier
        raw_scores = {}
        for tier, weights in self.feature_weights.items():
            score = 0.0
            for feature, weight in weights.items():
                if feature in features:
                    score += weight * features[feature]
            raw_scores[tier] = score
        
        # Convert to numpy array for calibration
        tier_list = list(RouterTier)
        logits = np.array([raw_scores[tier] for tier in tier_list])
        
        # Apply temperature scaling if calibrated
        if self.temperature_scaling.is_calibrated:
            calibrated_logits = self.temperature_scaling.apply_scaling(logits)
        else:
            calibrated_logits = logits
        
        # Convert to probabilities
        calibrated_probs = self._softmax(calibrated_logits)
        calibrated_scores = {tier: float(prob) for tier, prob in zip(tier_list, calibrated_probs)}
        
        # Select tier using bandit policy
        selected_tier, is_exploration = self.bandit_policy.select_action(calibrated_scores, context)
        
        # Calculate confidence
        confidence = calibrated_scores[selected_tier]
        
        # Generate reasoning
        reasoning = self._generate_reasoning(
            selected_tier, confidence, features, is_exploration
        )
        
        return ClassificationResult(
            tier=selected_tier,
            confidence=confidence,
            raw_scores=raw_scores,
            calibrated_scores=calibrated_scores,
            reasoning=reasoning
        )
    
    def update_with_feedback(
        self, 
        tier: RouterTier, 
        success: bool, 
        actual_cost: float,
        features: Dict[str, float]
    ):
        """Update classifier with feedback."""
        
        # Calculate reward (negative cost for success, higher penalty for failure)
        if success:
            reward = -actual_cost  # Negative cost is reward
        else:
            reward = -actual_cost - 1.0  # Additional penalty for failure
        
        # Update bandit policy
        self.bandit_policy.update_reward(tier, reward)
        
        logger.info("Updated classifier with feedback", 
                   tier=tier.value, 
                   success=success, 
                   reward=reward)
    
    def _softmax(self, logits: np.ndarray) -> np.ndarray:
        """Apply softmax function."""
        exp_logits = np.exp(logits - np.max(logits))
        return exp_logits / np.sum(exp_logits)
    
    def _generate_reasoning(
        self, 
        tier: RouterTier, 
        confidence: float, 
        features: Dict[str, float],
        is_exploration: bool
    ) -> str:
        """Generate human-readable reasoning for the decision."""
        
        reasoning_parts = []
        
        if is_exploration:
            reasoning_parts.append("Exploration: Trying this tier to gather more data.")
        
        # Feature-based reasoning
        if features.get("complexity_score", 0) > 0.7:
            reasoning_parts.append("High complexity request requires advanced capabilities.")
        
        if features.get("cost_sensitivity", 0) > 0.7:
            reasoning_parts.append("Cost-sensitive request, prioritizing lower-cost tiers.")
        
        if features.get("urgency_score", 0) > 0.7:
            reasoning_parts.append("Urgent request, prioritizing faster response times.")
        
        if features.get("novelty", 0) > 0.7:
            reasoning_parts.append("Novel request pattern, using higher-capability tier.")
        
        # Confidence-based reasoning
        if confidence > 0.8:
            reasoning_parts.append("High confidence in this tier selection.")
        elif confidence < 0.5:
            reasoning_parts.append("Lower confidence, may require fallback options.")
        
        # Tier-specific reasoning
        tier_config = self.cost_optimizer.tier_configs[tier]
        reasoning_parts.append(f"Selected {tier.value} with {tier_config.accuracy_score:.1%} expected accuracy.")
        
        return " ".join(reasoning_parts)
    
    def get_expected_cost(
        self, 
        tier: RouterTier, 
        token_count: int,
        confidence: float,
        complexity: float
    ) -> float:
        """Get expected cost for a tier selection."""
        error_prob = self.cost_optimizer.calculate_error_probability(tier, confidence, complexity)
        return self.cost_optimizer.calculate_expected_cost(tier, token_count, error_prob)
    
    def should_early_exit(
        self, 
        tier: RouterTier, 
        confidence: float,
        threshold: float = 0.9
    ) -> bool:
        """Determine if early exit should be triggered."""
        return tier == RouterTier.SLM_A and confidence >= threshold
