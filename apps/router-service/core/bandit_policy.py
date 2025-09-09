"""Bandit policy for router decision making."""

import asyncio
import time
import math
import random
from typing import Dict, List, Any, Optional, Tuple
import structlog
import redis.asyncio as redis
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV

logger = structlog.get_logger(__name__)


class BanditPolicy:
    """Bandit policy for minimizing cost + λ·error."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        lambda_error: float = 0.1,
        exploration_rate: float = 0.1,
        min_samples: int = 100
    ):
        self.redis = redis_client
        self.lambda_error = lambda_error
        self.exploration_rate = exploration_rate
        self.min_samples = min_samples
        
        # Agent tiers and their costs
        self.tier_costs = {
            'A': 0.01,  # Fast, cheap
            'B': 0.05,  # Medium
            'C': 0.20   # Slow, expensive but accurate
        }
        
        # Initialize models for each tenant
        self.models = {}
        self.calibrated_models = {}
    
    async def decide(
        self,
        features: Dict[str, Any],
        tenant_id: str,
        user_id: Optional[str] = None
    ) -> Tuple[str, float, str]:
        """
        Decide on agent tier using bandit policy.
        
        Returns:
            (tier, confidence, reasoning)
        """
        try:
            # Get or create model for tenant
            model = await self._get_tenant_model(tenant_id)
            
            # Extract feature vector
            feature_vector = self._extract_feature_vector(features)
            
            # Check if we have enough samples for confident prediction
            if await self._has_enough_samples(tenant_id):
                # Use calibrated model for prediction
                tier, confidence, reasoning = await self._predict_with_model(
                    model, feature_vector, tenant_id
                )
            else:
                # Use exploration strategy
                tier, confidence, reasoning = await self._explore_tier(
                    feature_vector, tenant_id
                )
            
            # Record decision for learning
            await self._record_decision(
                tenant_id, user_id, features, tier, confidence
            )
            
            logger.info(
                "Bandit decision made",
                tenant_id=tenant_id,
                user_id=user_id,
                tier=tier,
                confidence=confidence,
                reasoning=reasoning
            )
            
            return tier, confidence, reasoning
            
        except Exception as e:
            logger.error(
                "Bandit decision failed",
                error=str(e),
                tenant_id=tenant_id,
                user_id=user_id
            )
            # Fallback to tier A
            return 'A', 0.5, "Fallback due to error"
    
    async def _get_tenant_model(self, tenant_id: str) -> Any:
        """Get or create model for tenant."""
        if tenant_id not in self.models:
            # Create new model
            self.models[tenant_id] = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
            
            # Create calibrated model
            self.calibrated_models[tenant_id] = CalibratedClassifierCV(
                self.models[tenant_id],
                method='isotonic',
                cv=3
            )
            
            # Load existing data if available
            await self._load_tenant_data(tenant_id)
        
        return self.calibrated_models[tenant_id]
    
    async def _has_enough_samples(self, tenant_id: str) -> bool:
        """Check if we have enough samples for confident prediction."""
        try:
            samples_key = f"bandit_samples:{tenant_id}"
            sample_count = await self.redis.scard(samples_key)
            return sample_count >= self.min_samples
        except Exception as e:
            logger.error("Failed to check sample count", error=str(e))
            return False
    
    async def _predict_with_model(
        self,
        model: Any,
        feature_vector: np.ndarray,
        tenant_id: str
    ) -> Tuple[str, float, str]:
        """Predict using trained model."""
        try:
            # Get prediction probabilities
            probabilities = model.predict_proba([feature_vector])[0]
            
            # Get class labels
            classes = model.classes_
            
            # Calculate expected cost for each tier
            expected_costs = {}
            for i, tier in enumerate(classes):
                cost = self.tier_costs.get(tier, 1.0)
                error_prob = 1 - probabilities[i]
                expected_cost = cost + self.lambda_error * error_prob
                expected_costs[tier] = expected_cost
            
            # Select tier with minimum expected cost
            best_tier = min(expected_costs, key=expected_costs.get)
            confidence = probabilities[classes.tolist().index(best_tier)]
            
            reasoning = f"Expected cost: {expected_costs[best_tier]:.3f}, " \
                       f"Confidence: {confidence:.3f}"
            
            return best_tier, confidence, reasoning
            
        except Exception as e:
            logger.error("Model prediction failed", error=str(e))
            return 'A', 0.5, "Model prediction failed"
    
    async def _explore_tier(
        self,
        feature_vector: np.ndarray,
        tenant_id: str
    ) -> Tuple[str, float, str]:
        """Explore tier selection when we don't have enough samples."""
        try:
            # Get historical performance for each tier
            tier_performance = await self._get_tier_performance(tenant_id)
            
            # Calculate UCB (Upper Confidence Bound) for each tier
            ucb_scores = {}
            for tier in self.tier_costs.keys():
                if tier in tier_performance:
                    success_rate = tier_performance[tier]['success_rate']
                    sample_count = tier_performance[tier]['sample_count']
                    
                    # UCB calculation
                    if sample_count > 0:
                        confidence_radius = math.sqrt(
                            2 * math.log(sum(tier_performance[t]['sample_count'] 
                                           for t in tier_performance)) / sample_count
                        )
                        ucb_score = success_rate + confidence_radius
                    else:
                        ucb_score = 1.0  # High exploration for untested tiers
                else:
                    ucb_score = 1.0  # High exploration for new tiers
                
                ucb_scores[tier] = ucb_score
            
            # Select tier with highest UCB score
            best_tier = max(ucb_scores, key=ucb_scores.get)
            confidence = min(ucb_scores[best_tier], 1.0)
            
            reasoning = f"UCB exploration, UCB score: {ucb_scores[best_tier]:.3f}"
            
            return best_tier, confidence, reasoning
            
        except Exception as e:
            logger.error("UCB exploration failed", error=str(e))
            return 'A', 0.5, "UCB exploration failed"
    
    async def _get_tier_performance(self, tenant_id: str) -> Dict[str, Dict[str, float]]:
        """Get historical performance for each tier."""
        try:
            performance_key = f"tier_performance:{tenant_id}"
            performance_data = await self.redis.hgetall(performance_key)
            
            tier_performance = {}
            for tier in self.tier_costs.keys():
                tier_key = f"{tier}_performance"
                if tier_key in performance_data:
                    import json
                    tier_performance[tier] = json.loads(performance_data[tier_key])
                else:
                    tier_performance[tier] = {
                        'success_rate': 0.5,
                        'sample_count': 0,
                        'avg_latency': 0.0
                    }
            
            return tier_performance
            
        except Exception as e:
            logger.error("Failed to get tier performance", error=str(e))
            return {}
    
    async def _record_decision(
        self,
        tenant_id: str,
        user_id: Optional[str],
        features: Dict[str, Any],
        tier: str,
        confidence: float
    ) -> None:
        """Record decision for learning."""
        try:
            decision_data = {
                'tenant_id': tenant_id,
                'user_id': user_id,
                'features': features,
                'tier': tier,
                'confidence': confidence,
                'timestamp': time.time()
            }
            
            # Store decision
            decision_key = f"bandit_decisions:{tenant_id}"
            await self.redis.lpush(decision_key, json.dumps(decision_data))
            await self.redis.ltrim(decision_key, 0, 9999)  # Keep last 10k decisions
            
            # Add to samples for model training
            samples_key = f"bandit_samples:{tenant_id}"
            await self.redis.sadd(samples_key, json.dumps(decision_data))
            
        except Exception as e:
            logger.error("Failed to record decision", error=str(e))
    
    async def update_performance(
        self,
        tenant_id: str,
        tier: str,
        success: bool,
        latency: float
    ) -> None:
        """Update tier performance based on outcome."""
        try:
            performance_key = f"tier_performance:{tenant_id}"
            tier_key = f"{tier}_performance"
            
            # Get current performance
            current_data = await self.redis.hget(tier_key, tier_key)
            if current_data:
                import json
                performance = json.loads(current_data)
            else:
                performance = {
                    'success_rate': 0.5,
                    'sample_count': 0,
                    'avg_latency': 0.0
                }
            
            # Update performance
            performance['sample_count'] += 1
            performance['success_rate'] = (
                (performance['success_rate'] * (performance['sample_count'] - 1) + 
                 (1.0 if success else 0.0)) / performance['sample_count']
            )
            performance['avg_latency'] = (
                (performance['avg_latency'] * (performance['sample_count'] - 1) + 
                 latency) / performance['sample_count']
            )
            
            # Store updated performance
            await self.redis.hset(performance_key, tier_key, json.dumps(performance))
            
            logger.info(
                "Tier performance updated",
                tenant_id=tenant_id,
                tier=tier,
                success=success,
                latency=latency,
                new_success_rate=performance['success_rate']
            )
            
        except Exception as e:
            logger.error("Failed to update performance", error=str(e))
    
    async def retrain_model(self, tenant_id: str) -> bool:
        """Retrain model with latest data."""
        try:
            if tenant_id not in self.models:
                return False
            
            # Get training data
            samples_key = f"bandit_samples:{tenant_id}"
            samples = await self.redis.smembers(samples_key)
            
            if len(samples) < self.min_samples:
                logger.warning("Not enough samples for retraining", tenant_id=tenant_id)
                return False
            
            # Parse samples
            X = []
            y = []
            for sample in samples:
                try:
                    import json
                    sample_data = json.loads(sample)
                    feature_vector = self._extract_feature_vector(sample_data['features'])
                    X.append(feature_vector)
                    y.append(sample_data['tier'])
                except Exception as e:
                    logger.error("Failed to parse sample", error=str(e))
                    continue
            
            if len(X) < self.min_samples:
                return False
            
            # Train model
            X = np.array(X)
            y = np.array(y)
            
            self.models[tenant_id].fit(X, y)
            self.calibrated_models[tenant_id].fit(X, y)
            
            logger.info(
                "Model retrained successfully",
                tenant_id=tenant_id,
                sample_count=len(X)
            )
            
            return True
            
        except Exception as e:
            logger.error("Model retraining failed", error=str(e))
            return False
    
    def _extract_feature_vector(self, features: Dict[str, Any]) -> np.ndarray:
        """Extract feature vector from features dict."""
        # Define feature order for consistency
        feature_order = [
            'text_length', 'word_count', 'sentence_count', 'paragraph_count',
            'char_count', 'digit_count', 'punctuation_count', 'uppercase_ratio',
            'has_question', 'has_exclamation', 'has_currency', 'has_email',
            'has_url', 'avg_word_length', 'unique_word_ratio',
            'intent_order', 'intent_support', 'intent_product', 'intent_account',
            'intent_shipping', 'sentiment_positive', 'sentiment_negative',
            'urgency_high', 'technical_complexity', 'user_success_rate',
            'tenant_success_rate', 'hour_of_day', 'day_of_week', 'is_weekend',
            'is_business_hours', 'session_duration', 'session_message_count'
        ]
        
        # Extract features in order
        feature_vector = []
        for feature_name in feature_order:
            value = features.get(feature_name, 0)
            if isinstance(value, bool):
                value = 1.0 if value else 0.0
            elif isinstance(value, str):
                value = 0.0  # Skip string features for now
            feature_vector.append(float(value))
        
        return np.array(feature_vector)
    
    async def _load_tenant_data(self, tenant_id: str) -> None:
        """Load existing data for tenant."""
        try:
            # Load performance data
            performance_key = f"tier_performance:{tenant_id}"
            performance_data = await self.redis.hgetall(performance_key)
            
            # Load samples
            samples_key = f"bandit_samples:{tenant_id}"
            samples = await self.redis.smembers(samples_key)
            
            logger.info(
                "Loaded tenant data",
                tenant_id=tenant_id,
                performance_entries=len(performance_data),
                sample_count=len(samples)
            )
            
        except Exception as e:
            logger.error("Failed to load tenant data", error=str(e))
    
    async def get_bandit_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get bandit statistics for tenant."""
        try:
            # Get tier performance
            tier_performance = await self._get_tier_performance(tenant_id)
            
            # Get sample count
            samples_key = f"bandit_samples:{tenant_id}"
            sample_count = await self.redis.scard(samples_key)
            
            # Get decision count
            decisions_key = f"bandit_decisions:{tenant_id}"
            decision_count = await self.redis.llen(decisions_key)
            
            return {
                'tenant_id': tenant_id,
                'tier_performance': tier_performance,
                'sample_count': sample_count,
                'decision_count': decision_count,
                'lambda_error': self.lambda_error,
                'exploration_rate': self.exploration_rate,
                'min_samples': self.min_samples
            }
            
        except Exception as e:
            logger.error("Failed to get bandit stats", error=str(e))
            return {'tenant_id': tenant_id, 'error': str(e)}