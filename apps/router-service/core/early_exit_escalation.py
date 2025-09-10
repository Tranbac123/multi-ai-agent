"""Early exit and escalation logic for router v2."""

import asyncio
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import structlog
import redis.asyncio as redis

from apps.router-service.core.feature_extractor import RouterFeatures, Tier

logger = structlog.get_logger(__name__)


class EscalationReason(Enum):
    """Escalation reasons."""
    LOW_CONFIDENCE = "low_confidence"
    HIGH_RISK = "high_risk"
    NOVEL_REQUEST = "novel_request"
    ENTERPRISE_COMPLEX = "enterprise_complex"
    SCHEMA_VALIDATION_FAILED = "schema_validation_failed"
    JSON_VALIDATION_FAILED = "json_validation_failed"


@dataclass
class EscalationDecision:
    """Escalation decision result."""
    should_escalate: bool
    reason: Optional[EscalationReason]
    target_tier: Optional[Tier]
    confidence: float
    early_exit_tier: Optional[Tier]
    early_exit_confidence: float


class EarlyExitEscalation:
    """Early exit and escalation logic for router v2."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.escalation_thresholds = {
            'confidence_threshold': 0.8,
            'risk_threshold': 0.5,
            'novelty_threshold': 0.8,
            'complexity_threshold': 0.7
        }
    
    async def make_escalation_decision(
        self,
        features: RouterFeatures,
        predicted_tier: Tier,
        confidence: float,
        tenant_id: str
    ) -> EscalationDecision:
        """Make escalation decision based on features and prediction."""
        try:
            # Check for early exit conditions
            early_exit_result = await self._check_early_exit(features, tenant_id)
            
            if early_exit_result['can_exit']:
                return EscalationDecision(
                    should_escalate=False,
                    reason=None,
                    target_tier=early_exit_result['tier'],
                    confidence=early_exit_result['confidence'],
                    early_exit_tier=early_exit_result['tier'],
                    early_exit_confidence=early_exit_result['confidence']
                )
            
            # Check escalation conditions
            escalation_result = await self._check_escalation_conditions(
                features, predicted_tier, confidence, tenant_id
            )
            
            return EscalationDecision(
                should_escalate=escalation_result['should_escalate'],
                reason=escalation_result['reason'],
                target_tier=escalation_result['target_tier'],
                confidence=confidence,
                early_exit_tier=None,
                early_exit_confidence=0.0
            )
            
        except Exception as e:
            logger.error("Escalation decision failed", error=str(e))
            return EscalationDecision(
                should_escalate=True,
                reason=EscalationReason.HIGH_RISK,
                target_tier=Tier.C,
                confidence=0.5,
                early_exit_tier=None,
                early_exit_confidence=0.0
            )
    
    async def _check_early_exit(
        self,
        features: RouterFeatures,
        tenant_id: str
    ) -> Dict[str, Any]:
        """Check if request can use early exit to Tier A."""
        try:
            # Early exit conditions for Tier A (SLM_A)
            can_exit_to_a = True
            exit_confidence = 1.0
            
            # Check JSON schema strictness
            if features.schema_strictness < 0.8:
                can_exit_to_a = False
                exit_confidence *= 0.5
            
            # Check token count
            if features.token_count > 200:
                can_exit_to_a = False
                exit_confidence *= 0.3
            
            # Check complexity
            if features.request_complexity > 0.3:
                can_exit_to_a = False
                exit_confidence *= 0.2
            
            # Check novelty
            if features.novelty_score > 0.5:
                can_exit_to_a = False
                exit_confidence *= 0.4
            
            # Check historical failure rate
            if features.historical_failure_rate > 0.2:
                can_exit_to_a = False
                exit_confidence *= 0.3
            
            # Check domain-specific rules
            if not await self._check_domain_early_exit_rules(features, tenant_id):
                can_exit_to_a = False
                exit_confidence *= 0.6
            
            if can_exit_to_a and exit_confidence >= 0.8:
                return {
                    'can_exit': True,
                    'tier': Tier.A,
                    'confidence': exit_confidence
                }
            
            return {'can_exit': False, 'tier': None, 'confidence': 0.0}
            
        except Exception as e:
            logger.error("Early exit check failed", error=str(e))
            return {'can_exit': False, 'tier': None, 'confidence': 0.0}
    
    async def _check_domain_early_exit_rules(
        self,
        features: RouterFeatures,
        tenant_id: str
    ) -> bool:
        """Check domain-specific early exit rules."""
        try:
            # Get tenant-specific early exit rules
            rules_key = f"early_exit_rules:{tenant_id}"
            rules = await self.redis.hgetall(rules_key)
            
            if not rules:
                # Default rules
                return True
            
            # Check customer support domain
            if features.domain_flags.get('customer_support', False):
                # Allow early exit for simple customer support
                if features.token_count < 100 and features.request_complexity < 0.2:
                    return True
            
            # Check sales domain
            if features.domain_flags.get('sales', False):
                # Allow early exit for simple sales queries
                if features.token_count < 150 and features.request_complexity < 0.3:
                    return True
            
            # Check technical domain
            if features.domain_flags.get('technical', False):
                # Technical requests usually need higher tier
                return False
            
            # Check billing domain
            if features.domain_flags.get('billing', False):
                # Billing requests need higher accuracy
                return False
            
            return True
            
        except Exception as e:
            logger.error("Domain early exit rules check failed", error=str(e))
            return True
    
    async def _check_escalation_conditions(
        self,
        features: RouterFeatures,
        predicted_tier: Tier,
        confidence: float,
        tenant_id: str
    ) -> Dict[str, Any]:
        """Check escalation conditions."""
        try:
            escalation_reasons = []
            target_tier = predicted_tier
            
            # Check confidence threshold
            if confidence < self.escalation_thresholds['confidence_threshold']:
                escalation_reasons.append(EscalationReason.LOW_CONFIDENCE)
                target_tier = self._escalate_tier(target_tier)
            
            # Check risk threshold
            if features.historical_failure_rate > self.escalation_thresholds['risk_threshold']:
                escalation_reasons.append(EscalationReason.HIGH_RISK)
                target_tier = self._escalate_tier(target_tier)
            
            # Check novelty threshold
            if features.novelty_score > self.escalation_thresholds['novelty_threshold']:
                escalation_reasons.append(EscalationReason.NOVEL_REQUEST)
                target_tier = self._escalate_tier(target_tier)
            
            # Check enterprise complexity
            if (features.user_tier == "enterprise" and 
                features.request_complexity > self.escalation_thresholds['complexity_threshold']):
                escalation_reasons.append(EscalationReason.ENTERPRISE_COMPLEX)
                target_tier = self._escalate_tier(target_tier)
            
            # Check schema validation
            if not await self._validate_schema(features, tenant_id):
                escalation_reasons.append(EscalationReason.SCHEMA_VALIDATION_FAILED)
                target_tier = self._escalate_tier(target_tier)
            
            # Check JSON validation
            if not await self._validate_json(features, tenant_id):
                escalation_reasons.append(EscalationReason.JSON_VALIDATION_FAILED)
                target_tier = self._escalate_tier(target_tier)
            
            should_escalate = len(escalation_reasons) > 0
            primary_reason = escalation_reasons[0] if escalation_reasons else None
            
            return {
                'should_escalate': should_escalate,
                'reason': primary_reason,
                'target_tier': target_tier,
                'all_reasons': escalation_reasons
            }
            
        except Exception as e:
            logger.error("Escalation conditions check failed", error=str(e))
            return {
                'should_escalate': True,
                'reason': EscalationReason.HIGH_RISK,
                'target_tier': Tier.C,
                'all_reasons': [EscalationReason.HIGH_RISK]
            }
    
    def _escalate_tier(self, current_tier: Tier) -> Tier:
        """Escalate tier to next level."""
        if current_tier == Tier.A:
            return Tier.B
        elif current_tier == Tier.B:
            return Tier.C
        else:
            return Tier.C  # Already at highest tier
    
    async def _validate_schema(self, features: RouterFeatures, tenant_id: str) -> bool:
        """Validate schema strictness."""
        try:
            # Get tenant-specific schema requirements
            schema_key = f"schema_requirements:{tenant_id}"
            requirements = await self.redis.hgetall(schema_key)
            
            if not requirements:
                # Default: require high schema strictness
                return features.schema_strictness >= 0.7
            
            min_strictness = float(requirements.get('min_strictness', 0.7))
            return features.schema_strictness >= min_strictness
            
        except Exception as e:
            logger.error("Schema validation failed", error=str(e))
            return False
    
    async def _validate_json(self, features: RouterFeatures, tenant_id: str) -> bool:
        """Validate JSON structure."""
        try:
            # Simple JSON validation based on features
            # In production, this would parse actual JSON
            
            # Check if request has JSON structure
            has_json_structure = features.schema_strictness > 0.5
            
            # Check complexity
            not_too_complex = features.request_complexity < 0.8
            
            return has_json_structure and not_too_complex
            
        except Exception as e:
            logger.error("JSON validation failed", error=str(e))
            return False
    
    async def record_escalation_outcome(
        self,
        tenant_id: str,
        original_tier: Tier,
        escalated_tier: Tier,
        reason: EscalationReason,
        success: bool,
        latency: float
    ) -> None:
        """Record escalation outcome for learning."""
        try:
            outcome_key = f"escalation_outcome:{tenant_id}:{int(time.time())}"
            outcome_data = {
                'original_tier': original_tier.value,
                'escalated_tier': escalated_tier.value,
                'reason': reason.value,
                'success': success,
                'latency': latency,
                'timestamp': time.time()
            }
            
            await self.redis.hset(outcome_key, mapping=outcome_data)
            await self.redis.expire(outcome_key, 86400 * 30)  # 30 days TTL
            
            # Update escalation statistics
            stats_key = f"escalation_stats:{tenant_id}"
            await self.redis.hincrby(stats_key, 'total_escalations', 1)
            await self.redis.hincrby(stats_key, f'escalations_{reason.value}', 1)
            if success:
                await self.redis.hincrby(stats_key, 'successful_escalations', 1)
            await self.redis.expire(stats_key, 86400 * 7)  # 7 days TTL
            
        except Exception as e:
            logger.error("Failed to record escalation outcome", error=str(e))
    
    async def get_escalation_statistics(self, tenant_id: str) -> Dict[str, Any]:
        """Get escalation statistics for tenant."""
        try:
            stats_key = f"escalation_stats:{tenant_id}"
            stats_data = await self.redis.hgetall(stats_key)
            
            if not stats_data:
                return {'tenant_id': tenant_id, 'no_data': True}
            
            total_escalations = int(stats_data.get('total_escalations', 0))
            successful_escalations = int(stats_data.get('successful_escalations', 0))
            
            success_rate = (successful_escalations / total_escalations) if total_escalations > 0 else 0
            
            return {
                'tenant_id': tenant_id,
                'total_escalations': total_escalations,
                'successful_escalations': successful_escalations,
                'success_rate': success_rate,
                'escalation_reasons': {
                    reason.value: int(stats_data.get(f'escalations_{reason.value}', 0))
                    for reason in EscalationReason
                }
            }
            
        except Exception as e:
            logger.error("Failed to get escalation statistics", error=str(e))
            return {'error': str(e)}
