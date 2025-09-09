"""Feature store for router decision making."""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
import structlog
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update

logger = structlog.get_logger(__name__)


class FeatureStore:
    """Feature store for storing and retrieving request features."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.feature_ttl = 3600  # 1 hour
        self.batch_size = 100
    
    async def extract_features(
        self,
        request_text: str,
        context: Dict[str, Any],
        tenant_id: UUID
    ) -> Dict[str, Any]:
        """Extract features from request and context."""
        try:
            features = {}
            
            # Text-based features
            features.update(self._extract_text_features(request_text))
            
            # Context features
            features.update(self._extract_context_features(context))
            
            # Tenant features
            features.update(await self._extract_tenant_features(tenant_id))
            
            # Historical features
            features.update(await self._extract_historical_features(tenant_id, request_text))
            
            # Domain features
            features.update(self._extract_domain_features(request_text))
            
            # Add timestamp
            features["timestamp"] = time.time()
            features["tenant_id"] = str(tenant_id)
            
            logger.debug("Features extracted", 
                        feature_count=len(features), 
                        tenant_id=tenant_id)
            
            return features
            
        except Exception as e:
            logger.error("Feature extraction failed", 
                        tenant_id=tenant_id, 
                        error=str(e))
            return {}
    
    def _extract_text_features(self, text: str) -> Dict[str, Any]:
        """Extract text-based features."""
        features = {}
        
        # Basic text features
        features["text_length"] = len(text)
        features["word_count"] = len(text.split())
        features["sentence_count"] = text.count('.') + text.count('!') + text.count('?')
        features["char_count"] = len(text.replace(' ', ''))
        
        # Complexity features
        features["avg_word_length"] = features["char_count"] / max(features["word_count"], 1)
        features["avg_sentence_length"] = features["word_count"] / max(features["sentence_count"], 1)
        
        # Special characters
        features["question_marks"] = text.count('?')
        features["exclamation_marks"] = text.count('!')
        features["numbers"] = sum(c.isdigit() for c in text)
        features["uppercase_ratio"] = sum(c.isupper() for c in text) / max(len(text), 1)
        
        # Language patterns
        features["has_greeting"] = any(word in text.lower() for word in ['hello', 'hi', 'hey', 'good morning', 'good afternoon'])
        features["has_question"] = '?' in text
        features["has_urgency"] = any(word in text.lower() for word in ['urgent', 'asap', 'immediately', 'emergency'])
        features["has_politeness"] = any(word in text.lower() for word in ['please', 'thank you', 'thanks', 'appreciate'])
        
        return features
    
    def _extract_context_features(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract context-based features."""
        features = {}
        
        # Session features
        features["session_length"] = context.get("session_length", 0)
        features["message_count"] = context.get("message_count", 0)
        features["time_since_last_message"] = context.get("time_since_last_message", 0)
        
        # Channel features
        features["channel"] = context.get("channel", "unknown")
        features["is_mobile"] = context.get("is_mobile", False)
        features["is_web"] = context.get("is_web", False)
        
        # User features
        features["user_type"] = context.get("user_type", "unknown")
        features["is_returning_user"] = context.get("is_returning_user", False)
        features["user_plan"] = context.get("user_plan", "free")
        
        # Time features
        current_hour = datetime.now().hour
        features["hour_of_day"] = current_hour
        features["is_business_hours"] = 9 <= current_hour <= 17
        features["is_weekend"] = datetime.now().weekday() >= 5
        
        return features
    
    async def _extract_tenant_features(self, tenant_id: UUID) -> Dict[str, Any]:
        """Extract tenant-specific features."""
        features = {}
        
        try:
            # Get tenant info from cache
            tenant_key = f"tenant_features:{tenant_id}"
            cached_features = await self.redis.hgetall(tenant_key)
            
            if cached_features:
                features.update({
                    "tenant_plan": cached_features.get("plan", "free"),
                    "tenant_region": cached_features.get("region", "us-east-1"),
                    "tenant_created_at": float(cached_features.get("created_at", 0)),
                    "tenant_message_count": int(cached_features.get("message_count", 0)),
                    "tenant_success_rate": float(cached_features.get("success_rate", 0.0))
                })
            else:
                # Default values if not cached
                features.update({
                    "tenant_plan": "free",
                    "tenant_region": "us-east-1",
                    "tenant_created_at": time.time(),
                    "tenant_message_count": 0,
                    "tenant_success_rate": 0.0
                })
            
        except Exception as e:
            logger.error("Failed to extract tenant features", 
                        tenant_id=tenant_id, 
                        error=str(e))
            # Use default values
            features.update({
                "tenant_plan": "free",
                "tenant_region": "us-east-1",
                "tenant_created_at": time.time(),
                "tenant_message_count": 0,
                "tenant_success_rate": 0.0
            })
        
        return features
    
    async def _extract_historical_features(
        self, 
        tenant_id: UUID, 
        request_text: str
    ) -> Dict[str, Any]:
        """Extract historical features based on past requests."""
        features = {}
        
        try:
            # Get recent request patterns
            pattern_key = f"request_patterns:{tenant_id}"
            patterns = await self.redis.hgetall(pattern_key)
            
            if patterns:
                features.update({
                    "avg_request_length": float(patterns.get("avg_length", 0)),
                    "common_intent": patterns.get("common_intent", "unknown"),
                    "success_rate_24h": float(patterns.get("success_rate_24h", 0.0)),
                    "escalation_rate": float(patterns.get("escalation_rate", 0.0))
                })
            else:
                features.update({
                    "avg_request_length": 0,
                    "common_intent": "unknown",
                    "success_rate_24h": 0.0,
                    "escalation_rate": 0.0
                })
            
            # Check for similar requests
            similar_requests = await self._find_similar_requests(tenant_id, request_text)
            features["similar_request_count"] = len(similar_requests)
            features["has_similar_requests"] = len(similar_requests) > 0
            
        except Exception as e:
            logger.error("Failed to extract historical features", 
                        tenant_id=tenant_id, 
                        error=str(e))
            features.update({
                "avg_request_length": 0,
                "common_intent": "unknown",
                "success_rate_24h": 0.0,
                "escalation_rate": 0.0,
                "similar_request_count": 0,
                "has_similar_requests": False
            })
        
        return features
    
    def _extract_domain_features(self, text: str) -> Dict[str, Any]:
        """Extract domain-specific features."""
        features = {}
        
        # Intent keywords
        intent_keywords = {
            "faq": ["what", "how", "why", "when", "where", "can you", "do you know"],
            "order": ["order", "purchase", "buy", "checkout", "payment", "shipping"],
            "support": ["help", "problem", "issue", "error", "bug", "fix"],
            "billing": ["bill", "invoice", "payment", "charge", "refund", "cancel"],
            "technical": ["api", "integration", "code", "technical", "developer"]
        }
        
        text_lower = text.lower()
        for intent, keywords in intent_keywords.items():
            features[f"has_{intent}_keywords"] = any(keyword in text_lower for keyword in keywords)
        
        # Sentiment indicators
        positive_words = ["good", "great", "excellent", "amazing", "love", "perfect"]
        negative_words = ["bad", "terrible", "awful", "hate", "worst", "disappointed"]
        
        features["positive_sentiment"] = any(word in text_lower for word in positive_words)
        features["negative_sentiment"] = any(word in text_lower for word in negative_words)
        
        # Complexity indicators
        features["has_technical_terms"] = any(term in text_lower for term in ["api", "json", "xml", "database", "server"])
        features["has_business_terms"] = any(term in text_lower for term in ["revenue", "profit", "customer", "business", "strategy"])
        
        return features
    
    async def _find_similar_requests(
        self, 
        tenant_id: UUID, 
        request_text: str, 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Find similar requests from history."""
        try:
            # Simple similarity based on word overlap
            request_words = set(request_text.lower().split())
            similar_requests = []
            
            # Get recent requests from cache
            history_key = f"request_history:{tenant_id}"
            recent_requests = await self.redis.lrange(history_key, 0, 100)
            
            for request_data in recent_requests:
                try:
                    import json
                    data = json.loads(request_data)
                    history_words = set(data.get("text", "").lower().split())
                    
                    # Calculate word overlap
                    overlap = len(request_words.intersection(history_words))
                    total_words = len(request_words.union(history_words))
                    
                    if total_words > 0:
                        similarity = overlap / total_words
                        if similarity > 0.3:  # 30% similarity threshold
                            similar_requests.append({
                                "text": data.get("text", ""),
                                "similarity": similarity,
                                "timestamp": data.get("timestamp", 0)
                            })
                except Exception:
                    continue
            
            # Sort by similarity and return top results
            similar_requests.sort(key=lambda x: x["similarity"], reverse=True)
            return similar_requests[:limit]
            
        except Exception as e:
            logger.error("Failed to find similar requests", 
                        tenant_id=tenant_id, 
                        error=str(e))
            return []
    
    async def store_features(
        self,
        request_id: str,
        features: Dict[str, Any],
        tenant_id: UUID
    ):
        """Store features for later analysis."""
        try:
            # Store in Redis with TTL
            feature_key = f"features:{request_id}"
            await self.redis.hset(feature_key, mapping=features)
            await self.redis.expire(feature_key, self.feature_ttl)
            
            # Store in request history
            history_key = f"request_history:{tenant_id}"
            request_data = {
                "request_id": request_id,
                "text": features.get("text", ""),
                "timestamp": time.time(),
                "features": features
            }
            
            import json
            await self.redis.lpush(history_key, json.dumps(request_data))
            await self.redis.ltrim(history_key, 0, 1000)  # Keep last 1000 requests
            await self.redis.expire(history_key, 86400)  # 24 hours
            
            logger.debug("Features stored", 
                        request_id=request_id, 
                        tenant_id=tenant_id)
            
        except Exception as e:
            logger.error("Failed to store features", 
                        request_id=request_id, 
                        error=str(e))
    
    async def get_features(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get stored features for request."""
        try:
            feature_key = f"features:{request_id}"
            features = await self.redis.hgetall(feature_key)
            
            if features:
                # Convert string values back to appropriate types
                converted_features = {}
                for key, value in features.items():
                    try:
                        # Try to convert to float
                        converted_features[key] = float(value)
                    except ValueError:
                        try:
                            # Try to convert to int
                            converted_features[key] = int(value)
                        except ValueError:
                            # Keep as string
                            converted_features[key] = value
                
                return converted_features
            
            return None
            
        except Exception as e:
            logger.error("Failed to get features", 
                        request_id=request_id, 
                        error=str(e))
            return None
