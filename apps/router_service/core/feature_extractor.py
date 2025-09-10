"""Feature extraction for router v2 with calibrated bandit policy."""

import asyncio
import time
import hashlib
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import structlog
import redis.asyncio as redis
from functools import lru_cache

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
    """Feature extractor for router v2 with high-concurrency optimizations."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.domain_patterns = {
            'customer_support': ['help', 'support', 'issue', 'problem'],
            'sales': ['buy', 'purchase', 'order', 'price'],
            'technical': ['api', 'integration', 'technical', 'bug'],
            'billing': ['payment', 'invoice', 'billing', 'charge']
        }
        # Cache for frequently accessed data
        self._cache_ttl = 300  # 5 minutes
        self._batch_size = 100
    
    async def extract_features(
        self,
        request: Dict[str, Any],
        tenant_id: str,
        user_id: str
    ) -> RouterFeatures:
        """Extract features from request for routing decision with high-concurrency optimizations."""
        try:
            # Create request hash for caching
            request_hash = self._create_request_hash(request)
            cache_key = f"features:{tenant_id}:{user_id}:{request_hash}"
            
            # Try to get from cache first
            cached_features = await self._get_cached_features(cache_key)
            if cached_features:
                return cached_features
            
            # Extract features in parallel for better performance
            tasks = [
                self._estimate_token_count(request),
                self._calculate_schema_strictness(request),
                self._extract_domain_flags(request),
                self._calculate_novelty_score(request, tenant_id),
                self._get_historical_failure_rate(tenant_id, user_id),
                self._get_user_tier(tenant_id, user_id),
                self._calculate_request_complexity(request)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle any exceptions in parallel tasks
            token_count = results[0] if not isinstance(results[0], Exception) else 100
            schema_strictness = results[1] if not isinstance(results[1], Exception) else 0.5
            domain_flags = results[2] if not isinstance(results[2], Exception) else {}
            novelty_score = results[3] if not isinstance(results[3], Exception) else 0.5
            historical_failure_rate = results[4] if not isinstance(results[4], Exception) else 0.1
            user_tier = results[5] if not isinstance(results[5], Exception) else "standard"
            request_complexity = results[6] if not isinstance(results[6], Exception) else 0.5
            
            # Time features (computed locally)
            current_time = time.time()
            time_of_day = time.localtime(current_time).tm_hour
            day_of_week = time.localtime(current_time).tm_wday
            
            features = RouterFeatures(
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
            
            # Cache the features
            await self._cache_features(cache_key, features)
            
            return features
            
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
    
    def _create_request_hash(self, request: Dict[str, Any]) -> str:
        """Create a hash for request caching."""
        try:
            # Create a stable hash of the request for caching
            request_str = json.dumps(request, sort_keys=True)
            return hashlib.md5(request_str.encode()).hexdigest()[:16]
        except Exception:
            return "default"
    
    async def _get_cached_features(self, cache_key: str) -> Optional[RouterFeatures]:
        """Get cached features from Redis."""
        try:
            cached_data = await self.redis.get(cache_key)
            if cached_data:
                data = json.loads(cached_data)
                return RouterFeatures(**data)
            return None
        except Exception:
            return None
    
    async def _cache_features(self, cache_key: str, features: RouterFeatures) -> None:
        """Cache features in Redis."""
        try:
            # Convert to dict for JSON serialization
            features_dict = {
                'token_count': features.token_count,
                'schema_strictness': features.schema_strictness,
                'domain_flags': features.domain_flags,
                'novelty_score': features.novelty_score,
                'historical_failure_rate': features.historical_failure_rate,
                'user_tier': features.user_tier,
                'time_of_day': features.time_of_day,
                'day_of_week': features.day_of_week,
                'request_complexity': features.request_complexity
            }
            
            await self.redis.setex(
                cache_key, 
                self._cache_ttl, 
                json.dumps(features_dict)
            )
        except Exception as e:
            logger.warning("Failed to cache features", error=str(e))
    
    @lru_cache(maxsize=1000)
    def _calculate_text_similarity_cached(self, text1: str, text2: str) -> float:
        """Cached version of text similarity calculation."""
        return self._calculate_text_similarity(text1, text2)
    
    async def batch_extract_features(
        self, 
        requests: List[Tuple[Dict[str, Any], str, str]]
    ) -> List[RouterFeatures]:
        """Extract features for multiple requests in batch for better performance."""
        try:
            # Process in batches to avoid overwhelming Redis
            results = []
            for i in range(0, len(requests), self._batch_size):
                batch = requests[i:i + self._batch_size]
                batch_tasks = [
                    self.extract_features(request, tenant_id, user_id)
                    for request, tenant_id, user_id in batch
                ]
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                # Handle exceptions in batch
                for result in batch_results:
                    if isinstance(result, Exception):
                        logger.warning("Failed to extract features in batch", error=str(result))
                        # Add default features for failed extractions
                        results.append(RouterFeatures(
                            token_count=100,
                            schema_strictness=0.5,
                            domain_flags={},
                            novelty_score=0.5,
                            historical_failure_rate=0.1,
                            user_tier="standard",
                            time_of_day=12,
                            day_of_week=1,
                            request_complexity=0.5
                        ))
                    else:
                        results.append(result)
            
            return results
        except Exception as e:
            logger.error("Failed to batch extract features", error=str(e))
            # Return default features for all requests
            return [
                RouterFeatures(
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
                for _ in requests
            ]
