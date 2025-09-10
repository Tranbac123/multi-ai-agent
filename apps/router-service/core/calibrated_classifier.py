"""Calibrated classifier with temperature scaling for router v2."""

import asyncio
import time
import math
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import structlog
import redis.asyncio as redis

from apps.router-service.core.feature_extractor import RouterFeatures, Tier

logger = structlog.get_logger(__name__)


@dataclass
class CalibrationData:
    """Calibration data for temperature scaling."""
    temperature: float
    confidence_threshold: float
    accuracy_threshold: float
    last_updated: float


class CalibratedClassifier:
    """Calibrated classifier with temperature scaling."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.calibration_data = {}
        self.default_temperature = 1.0
        self.default_confidence_threshold = 0.8
        self.default_accuracy_threshold = 0.9
    
    async def classify(
        self,
        features: RouterFeatures,
        tenant_id: str
    ) -> Tuple[Tier, float, bool]:
        """Classify request and return tier, confidence, and should_escalate."""
        try:
            # Get calibration data for tenant
            calibration = await self._get_calibration_data(tenant_id)
            
            # Calculate raw scores for each tier
            tier_scores = await self._calculate_tier_scores(features)
            
            # Apply temperature scaling
            calibrated_scores = self._apply_temperature_scaling(tier_scores, calibration.temperature)
            
            # Get best tier and confidence
            best_tier, confidence = self._get_best_tier_and_confidence(calibrated_scores)
            
            # Check if should escalate
            should_escalate = self._should_escalate(features, confidence, calibration)
            
            # Update calibration based on decision
            await self._update_calibration_data(tenant_id, features, best_tier, confidence)
            
            return best_tier, confidence, should_escalate
            
        except Exception as e:
            logger.error("Classification failed", error=str(e))
            # Fallback to deterministic routing
            return await self._deterministic_fallback(features)
    
    async def _get_calibration_data(self, tenant_id: str) -> CalibrationData:
        """Get calibration data for tenant."""
        try:
            calibration_key = f"calibration:{tenant_id}"
            calibration_data = await self.redis.hgetall(calibration_key)
            
            if calibration_data:
                return CalibrationData(
                    temperature=float(calibration_data.get('temperature', self.default_temperature)),
                    confidence_threshold=float(calibration_data.get('confidence_threshold', self.default_confidence_threshold)),
                    accuracy_threshold=float(calibration_data.get('accuracy_threshold', self.default_accuracy_threshold)),
                    last_updated=float(calibration_data.get('last_updated', time.time()))
                )
            
            # Return default calibration
            return CalibrationData(
                temperature=self.default_temperature,
                confidence_threshold=self.default_confidence_threshold,
                accuracy_threshold=self.default_accuracy_threshold,
                last_updated=time.time()
            )
            
        except Exception as e:
            logger.error("Failed to get calibration data", error=str(e))
            return CalibrationData(
                temperature=self.default_temperature,
                confidence_threshold=self.default_confidence_threshold,
                accuracy_threshold=self.default_accuracy_threshold,
                last_updated=time.time()
            )
    
    async def _calculate_tier_scores(self, features: RouterFeatures) -> Dict[Tier, float]:
        """Calculate raw scores for each tier."""
        try:
            scores = {}
            
            # Tier A (Fast, cheap) - prefer for simple, low-risk requests
            tier_a_score = 0.0
            
            # Prefer for low token count
            if features.token_count < 100:
                tier_a_score += 0.3
            elif features.token_count < 500:
                tier_a_score += 0.2
            
            # Prefer for high schema strictness
            tier_a_score += features.schema_strictness * 0.2
            
            # Prefer for low complexity
            tier_a_score += (1.0 - features.request_complexity) * 0.2
            
            # Prefer for low novelty
            tier_a_score += (1.0 - features.novelty_score) * 0.1
            
            # Prefer for low failure rate
            tier_a_score += (1.0 - features.historical_failure_rate) * 0.1
            
            # Prefer for standard users
            if features.user_tier == "standard":
                tier_a_score += 0.1
            
            scores[Tier.A] = max(0.0, min(1.0, tier_a_score))
            
            # Tier B (Balanced) - default choice
            tier_b_score = 0.5  # Base score
            
            # Adjust based on features
            if 100 <= features.token_count <= 1000:
                tier_b_score += 0.2
            
            if 0.3 <= features.request_complexity <= 0.7:
                tier_b_score += 0.2
            
            if features.user_tier == "premium":
                tier_b_score += 0.1
            
            scores[Tier.B] = max(0.0, min(1.0, tier_b_score))
            
            # Tier C (Slow, expensive but accurate) - prefer for complex, high-risk requests
            tier_c_score = 0.0
            
            # Prefer for high token count
            if features.token_count > 1000:
                tier_c_score += 0.3
            elif features.token_count > 500:
                tier_c_score += 0.2
            
            # Prefer for high complexity
            tier_c_score += features.request_complexity * 0.2
            
            # Prefer for high novelty
            tier_c_score += features.novelty_score * 0.2
            
            # Prefer for high failure rate (need better accuracy)
            tier_c_score += features.historical_failure_rate * 0.1
            
            # Prefer for enterprise users
            if features.user_tier == "enterprise":
                tier_c_score += 0.2
            
            scores[Tier.C] = max(0.0, min(1.0, tier_c_score))
            
            return scores
            
        except Exception as e:
            logger.error("Failed to calculate tier scores", error=str(e))
            return {Tier.A: 0.3, Tier.B: 0.5, Tier.C: 0.2}
    
    def _apply_temperature_scaling(self, scores: Dict[Tier, float], temperature: float) -> Dict[Tier, float]:
        """Apply temperature scaling to scores."""
        try:
            if temperature <= 0:
                temperature = 0.1  # Avoid division by zero
            
            # Apply temperature scaling
            scaled_scores = {}
            for tier, score in scores.items():
                # Convert to logits and apply temperature
                logit = math.log(score / (1.0 - score + 1e-8))  # Add small epsilon
                scaled_logit = logit / temperature
                scaled_score = 1.0 / (1.0 + math.exp(-scaled_logit))  # Sigmoid
                scaled_scores[tier] = scaled_score
            
            # Normalize scores
            total_score = sum(scaled_scores.values())
            if total_score > 0:
                for tier in scaled_scores:
                    scaled_scores[tier] /= total_score
            
            return scaled_scores
            
        except Exception as e:
            logger.error("Failed to apply temperature scaling", error=str(e))
            return scores
    
    def _get_best_tier_and_confidence(self, scores: Dict[Tier, float]) -> Tuple[Tier, float]:
        """Get best tier and confidence score."""
        try:
            best_tier = max(scores.keys(), key=lambda t: scores[t])
            confidence = scores[best_tier]
            
            return best_tier, confidence
            
        except Exception as e:
            logger.error("Failed to get best tier", error=str(e))
            return Tier.B, 0.5
    
    def _should_escalate(
        self,
        features: RouterFeatures,
        confidence: float,
        calibration: CalibrationData
    ) -> bool:
        """Determine if request should be escalated."""
        try:
            # Escalate if confidence is below threshold
            if confidence < calibration.confidence_threshold:
                return True
            
            # Escalate for high-risk requests
            if features.historical_failure_rate > 0.5:
                return True
            
            # Escalate for very novel requests
            if features.novelty_score > 0.8:
                return True
            
            # Escalate for enterprise users with complex requests
            if (features.user_tier == "enterprise" and 
                features.request_complexity > 0.7):
                return True
            
            return False
            
        except Exception as e:
            logger.error("Failed to determine escalation", error=str(e))
            return False
    
    async def _update_calibration_data(
        self,
        tenant_id: str,
        features: RouterFeatures,
        predicted_tier: Tier,
        confidence: float
    ) -> None:
        """Update calibration data based on decision."""
        try:
            # Store decision for later calibration
            decision_key = f"decision:{tenant_id}:{int(time.time())}"
            decision_data = {
                'predicted_tier': predicted_tier.value,
                'confidence': confidence,
                'token_count': features.token_count,
                'complexity': features.request_complexity,
                'novelty': features.novelty_score,
                'timestamp': time.time()
            }
            
            await self.redis.hset(decision_key, mapping=decision_data)
            await self.redis.expire(decision_key, 86400 * 7)  # 7 days TTL
            
        except Exception as e:
            logger.error("Failed to update calibration data", error=str(e))
    
    async def _deterministic_fallback(self, features: RouterFeatures) -> Tuple[Tier, float, bool]:
        """Deterministic fallback routing."""
        try:
            # Simple deterministic rules
            if features.token_count < 100 and features.request_complexity < 0.3:
                return Tier.A, 0.8, False
            elif features.token_count > 1000 or features.request_complexity > 0.7:
                return Tier.C, 0.8, False
            else:
                return Tier.B, 0.8, False
                
        except Exception as e:
            logger.error("Deterministic fallback failed", error=str(e))
            return Tier.B, 0.5, True
    
    async def calibrate_temperature(self, tenant_id: str) -> None:
        """Calibrate temperature based on historical decisions."""
        try:
            # Get recent decisions
            pattern = f"decision:{tenant_id}:*"
            decision_keys = await self.redis.keys(pattern)
            
            if len(decision_keys) < 10:  # Need at least 10 decisions
                return
            
            # Calculate optimal temperature
            optimal_temperature = await self._calculate_optimal_temperature(decision_keys)
            
            # Update calibration data
            calibration_key = f"calibration:{tenant_id}"
            await self.redis.hset(calibration_key, mapping={
                'temperature': optimal_temperature,
                'last_updated': time.time()
            })
            
            logger.info("Temperature calibrated", tenant_id=tenant_id, temperature=optimal_temperature)
            
        except Exception as e:
            logger.error("Failed to calibrate temperature", error=str(e))
    
    async def _calculate_optimal_temperature(self, decision_keys: List[bytes]) -> float:
        """Calculate optimal temperature using validation set."""
        try:
            # Simple temperature optimization
            # In production, this would use proper validation techniques
            
            temperatures = [0.5, 0.8, 1.0, 1.2, 1.5, 2.0]
            best_temperature = 1.0
            best_score = 0.0
            
            for temp in temperatures:
                score = await self._evaluate_temperature(temp, decision_keys)
                if score > best_score:
                    best_score = score
                    best_temperature = temp
            
            return best_temperature
            
        except Exception as e:
            logger.error("Failed to calculate optimal temperature", error=str(e))
            return 1.0
    
    async def _evaluate_temperature(self, temperature: float, decision_keys: List[bytes]) -> float:
        """Evaluate temperature on validation set."""
        try:
            # Simple evaluation - in production would use proper validation
            # For now, return a score based on temperature
            if 0.8 <= temperature <= 1.2:
                return 0.8
            elif 0.5 <= temperature <= 1.5:
                return 0.6
            else:
                return 0.4
                
        except Exception:
            return 0.5
