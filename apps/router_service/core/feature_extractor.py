"""Feature extraction for router v2 with calibrated bandit policy."""

import asyncio
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import structlog
import redis.asyncio as redis

logger = structlog.get_logger(__name__)


class Tier(Enum):
    """Router tiers."""
    A = "A"  # Fast, cheap
    B = "B"  # Balanced
    C = "C"  # Slow, expensive but accurate


@dataclass
class RouterFeatures:
    """Extracted features for routing decision."""
    token_count: int
    schema_strictness: float  # 0.0 to 1.0
    domain_flags: Dict[str, bool]
    novelty_score: float  # 0.0 to 1.0
    historical_failure_rate: float  # 0.0 to 1.0
    user_tier: str
    time_of_day: int  # 0-23
    day_of_week: int  # 0-6
    request_complexity: float  # 0.0 to 1.0


class FeatureExtractor:
    """Feature extractor for router v2."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.domain_patterns = {
            'customer_support': ['help', 'support', 'issue', 'problem'],
            'sales': ['buy', 'purchase', 'order', 'price'],
            'technical': ['api', 'integration', 'technical', 'bug'],
            'billing': ['payment', 'invoice', 'billing', 'charge']
        }
    
    async def extract_features(
        self,
        request: Dict[str, Any],
        tenant_id: str,
        user_id: str
    ) -> RouterFeatures:
        """Extract features from request for routing decision."""
        try:
            # Token count estimation
            token_count = await self._estimate_token_count(request)
            
            # Schema strictness
            schema_strictness = await self._calculate_schema_strictness(request)
            
            # Domain flags
            domain_flags = await self._extract_domain_flags(request)
            
            # Novelty score
            novelty_score = await self._calculate_novelty_score(request, tenant_id)
            
            # Historical failure rate
            historical_failure_rate = await self._get_historical_failure_rate(tenant_id, user_id)
            
            # User tier
            user_tier = await self._get_user_tier(tenant_id, user_id)
            
            # Time features
            current_time = time.time()
            time_of_day = time.localtime(current_time).tm_hour
            day_of_week = time.localtime(current_time).tm_wday
            
            # Request complexity
            request_complexity = await self._calculate_request_complexity(request)
            
            return RouterFeatures(
                token_count=token_count,
                schema_strictness=schema_strictness,
                domain_flags=domain_flags,
                novelty_score=novelty_score,
                historical_failure_rate=historical_failure_rate,
                user_tier=user_tier,
                time_of_day=time_of_day,
                day_of_week=day_of_week,
                request_complexity=request_complexity
            )
            
        except Exception as e:
            logger.error("Failed to extract features", error=str(e))
            # Return default features
            return RouterFeatures(
                token_count=100,
                schema_strictness=0.5,
                domain_flags={},
                novelty_score=0.5,
                historical_failure_rate=0.1,
                user_tier="standard",
                time_of_day=12,
                day_of_week=1,
                request_complexity=0.5
            )
    
    async def _estimate_token_count(self, request: Dict[str, Any]) -> int:
        """Estimate token count from request."""
        try:
            # Simple estimation based on text length
            text_content = str(request.get('message', ''))
            # Rough estimation: 1 token ≈ 4 characters
            estimated_tokens = len(text_content) // 4
            return max(1, estimated_tokens)
        except Exception:
            return 100  # Default fallback
    
    async def _calculate_schema_strictness(self, request: Dict[str, Any]) -> float:
        """Calculate schema strictness score."""
        try:
            # Check for structured data
            has_structured_data = any(key in request for key in ['json', 'schema', 'format'])
            
            # Check for validation rules
            has_validation = any(key in request for key in ['validation', 'constraints', 'rules'])
            
            # Calculate score
            score = 0.0
            if has_structured_data:
                score += 0.5
            if has_validation:
                score += 0.5
            
            return min(1.0, score)
        except Exception:
            return 0.5  # Default fallback
    
    async def _extract_domain_flags(self, request: Dict[str, Any]) -> Dict[str, bool]:
        """Extract domain-specific flags."""
        try:
            text_content = str(request.get('message', '')).lower()
            domain_flags = {}
            
            for domain, patterns in self.domain_patterns.items():
                domain_flags[domain] = any(pattern in text_content for pattern in patterns)
            
            return domain_flags
        except Exception:
            return {}
    
    async def _calculate_novelty_score(self, request: Dict[str, Any], tenant_id: str) -> float:
        """Calculate novelty score based on historical requests."""
        try:
            # Get recent requests for this tenant
            recent_requests_key = f"recent_requests:{tenant_id}"
            recent_requests = await self.redis.lrange(recent_requests_key, 0, 99)  # Last 100 requests
            
            if not recent_requests:
                return 1.0  # High novelty if no history
            
            # Calculate similarity with recent requests
            current_text = str(request.get('message', '')).lower()
            similarities = []
            
            for recent_request in recent_requests:
                try:
                    recent_text = recent_request.decode().lower()
                    similarity = self._calculate_text_similarity(current_text, recent_text)
                    similarities.append(similarity)
                except Exception:
                    continue
            
            if not similarities:
                return 1.0
            
            # Novelty is inverse of max similarity
            max_similarity = max(similarities)
            novelty_score = 1.0 - max_similarity
            
            return max(0.0, min(1.0, novelty_score))
            
        except Exception as e:
            logger.error("Failed to calculate novelty score", error=str(e))
            return 0.5  # Default fallback
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity."""
        try:
            words1 = set(text1.split())
            words2 = set(text2.split())
            
            if not words1 or not words2:
                return 0.0
            
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            
            return len(intersection) / len(union) if union else 0.0
        except Exception:
            return 0.0
    
    async def _get_historical_failure_rate(self, tenant_id: str, user_id: str) -> float:
        """Get historical failure rate for tenant/user."""
        try:
            failure_key = f"failure_rate:{tenant_id}:{user_id}"
            failure_rate = await self.redis.get(failure_key)
            
            if failure_rate:
                return float(failure_rate)
            
            # Default based on tenant
            tenant_failure_key = f"failure_rate:{tenant_id}"
            tenant_failure_rate = await self.redis.get(tenant_failure_key)
            
            if tenant_failure_rate:
                return float(tenant_failure_rate)
            
            return 0.1  # Default 10% failure rate
        except Exception:
            return 0.1
    
    async def _get_user_tier(self, tenant_id: str, user_id: str) -> str:
        """Get user tier."""
        try:
            tier_key = f"user_tier:{tenant_id}:{user_id}"
            tier = await self.redis.get(tier_key)
            
            if tier:
                return tier.decode()
            
            # Default based on tenant
            tenant_tier_key = f"tenant_tier:{tenant_id}"
            tenant_tier = await self.redis.get(tenant_tier_key)
            
            if tenant_tier:
                return tenant_tier.decode()
            
            return "standard"  # Default tier
        except Exception:
            return "standard"
    
    async def _calculate_request_complexity(self, request: Dict[str, Any]) -> float:
        """Calculate request complexity score."""
        try:
            complexity_score = 0.0
            
            # Text length factor
            text_length = len(str(request.get('message', '')))
            if text_length > 1000:
                complexity_score += 0.3
            elif text_length > 500:
                complexity_score += 0.2
            elif text_length > 100:
                complexity_score += 0.1
            
            # Number of fields
            field_count = len(request)
            if field_count > 10:
                complexity_score += 0.3
            elif field_count > 5:
                complexity_score += 0.2
            elif field_count > 2:
                complexity_score += 0.1
            
            # Nested data
            has_nested = any(isinstance(v, (dict, list)) for v in request.values())
            if has_nested:
                complexity_score += 0.2
            
            return min(1.0, complexity_score)
        except Exception:
            return 0.5
