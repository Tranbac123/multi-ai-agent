"""Feature store for router v2 with 24+ signals."""

import asyncio
import time
import json
import re
from typing import Dict, List, Any, Optional, Tuple
import structlog
import redis.asyncio as redis
from datetime import datetime, timedelta

logger = structlog.get_logger(__name__)


class FeatureStore:
    """Feature store for router decision making."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.feature_ttl = 3600  # 1 hour

    async def extract_features(
        self,
        message: str,
        tenant_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Extract 24+ features from request."""
        try:
            features = {}

            # Basic text features
            features.update(await self._extract_text_features(message))

            # Domain-specific features
            features.update(await self._extract_domain_features(message))

            # Historical features
            features.update(await self._extract_historical_features(tenant_id, user_id))

            # Context features
            features.update(await self._extract_context_features(context or {}))

            # User preference features
            features.update(await self._extract_user_preferences(tenant_id, user_id))

            # Session features
            features.update(await self._extract_session_features(session_id, tenant_id))

            # Add metadata
            features["extraction_timestamp"] = time.time()
            features["tenant_id"] = tenant_id
            features["user_id"] = user_id
            features["session_id"] = session_id

            # Cache features
            await self._cache_features(tenant_id, user_id, features)

            logger.info(
                "Features extracted successfully",
                tenant_id=tenant_id,
                user_id=user_id,
                feature_count=len(features),
            )

            return features

        except Exception as e:
            logger.error(
                "Feature extraction failed",
                error=str(e),
                tenant_id=tenant_id,
                user_id=user_id,
            )
            return {}

    async def _extract_text_features(self, message: str) -> Dict[str, Any]:
        """Extract basic text features."""
        features = {}

        # Text length features
        features["text_length"] = len(message)
        features["word_count"] = len(message.split())
        features["sentence_count"] = len(re.split(r"[.!?]+", message))
        features["paragraph_count"] = len(message.split("\n\n"))

        # Character features
        features["char_count"] = len(message)
        features["digit_count"] = len(re.findall(r"\d", message))
        features["punctuation_count"] = len(re.findall(r"[^\w\s]", message))
        features["uppercase_ratio"] = len(re.findall(r"[A-Z]", message)) / max(
            len(message), 1
        )

        # Language features
        features["has_question"] = "?" in message
        features["has_exclamation"] = "!" in message
        features["has_currency"] = bool(re.search(r"[$€£¥₹]", message))
        features["has_email"] = bool(
            re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", message)
        )
        features["has_url"] = bool(
            re.search(
                r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
                message,
            )
        )

        # Complexity features
        features["avg_word_length"] = sum(len(word) for word in message.split()) / max(
            len(message.split()), 1
        )
        features["unique_word_ratio"] = len(
            set(word.lower() for word in message.split())
        ) / max(len(message.split()), 1)

        return features

    async def _extract_domain_features(self, message: str) -> Dict[str, Any]:
        """Extract domain-specific features."""
        features = {}

        # Intent keywords
        intent_keywords = {
            "order": ["order", "buy", "purchase", "cart", "checkout", "payment"],
            "support": ["help", "support", "issue", "problem", "error", "bug"],
            "product": ["product", "item", "price", "specification", "feature"],
            "account": ["account", "login", "register", "profile", "settings"],
            "shipping": ["shipping", "delivery", "track", "address", "location"],
        }

        message_lower = message.lower()
        for intent, keywords in intent_keywords.items():
            features[f"intent_{intent}"] = any(
                keyword in message_lower for keyword in keywords
            )

        # Sentiment indicators
        positive_words = [
            "good",
            "great",
            "excellent",
            "amazing",
            "wonderful",
            "perfect",
        ]
        negative_words = [
            "bad",
            "terrible",
            "awful",
            "horrible",
            "disappointed",
            "angry",
        ]

        features["sentiment_positive"] = any(
            word in message_lower for word in positive_words
        )
        features["sentiment_negative"] = any(
            word in message_lower for word in negative_words
        )

        # Urgency indicators
        urgency_words = [
            "urgent",
            "asap",
            "immediately",
            "emergency",
            "critical",
            "rush",
        ]
        features["urgency_high"] = any(word in message_lower for word in urgency_words)

        # Technical complexity
        technical_terms = [
            "api",
            "database",
            "server",
            "code",
            "bug",
            "error",
            "exception",
        ]
        features["technical_complexity"] = any(
            term in message_lower for term in technical_terms
        )

        return features

    async def _extract_historical_features(
        self, tenant_id: str, user_id: Optional[str]
    ) -> Dict[str, Any]:
        """Extract historical features."""
        features = {}

        try:
            # Get user history if available
            if user_id:
                user_history = await self._get_user_history(tenant_id, user_id)
                features.update(user_history)

            # Get tenant history
            tenant_history = await self._get_tenant_history(tenant_id)
            features.update(tenant_history)

        except Exception as e:
            logger.error("Failed to extract historical features", error=str(e))

        return features

    async def _get_user_history(self, tenant_id: str, user_id: str) -> Dict[str, Any]:
        """Get user-specific historical features."""
        try:
            # Get user's recent interactions
            user_key = f"user_history:{tenant_id}:{user_id}"
            history_data = await self.redis.hgetall(user_key)

            if not history_data:
                return {
                    "user_interaction_count": 0,
                    "user_success_rate": 0.0,
                    "user_avg_latency": 0.0,
                    "user_last_interaction": 0,
                }

            return {
                "user_interaction_count": int(history_data.get("interaction_count", 0)),
                "user_success_rate": float(history_data.get("success_rate", 0.0)),
                "user_avg_latency": float(history_data.get("avg_latency", 0.0)),
                "user_last_interaction": float(history_data.get("last_interaction", 0)),
            }

        except Exception as e:
            logger.error("Failed to get user history", error=str(e))
            return {}

    async def _get_tenant_history(self, tenant_id: str) -> Dict[str, Any]:
        """Get tenant-specific historical features."""
        try:
            # Get tenant's recent performance
            tenant_key = f"tenant_history:{tenant_id}"
            history_data = await self.redis.hgetall(tenant_key)

            if not history_data:
                return {
                    "tenant_success_rate": 0.0,
                    "tenant_avg_latency": 0.0,
                    "tenant_error_rate": 0.0,
                    "tenant_throughput": 0.0,
                }

            return {
                "tenant_success_rate": float(history_data.get("success_rate", 0.0)),
                "tenant_avg_latency": float(history_data.get("avg_latency", 0.0)),
                "tenant_error_rate": float(history_data.get("error_rate", 0.0)),
                "tenant_throughput": float(history_data.get("throughput", 0.0)),
            }

        except Exception as e:
            logger.error("Failed to get tenant history", error=str(e))
            return {}

    async def _extract_context_features(
        self, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract context-based features."""
        features = {}

        # Time-based features
        now = datetime.now()
        features["hour_of_day"] = now.hour
        features["day_of_week"] = now.weekday()
        features["is_weekend"] = now.weekday() >= 5
        features["is_business_hours"] = 9 <= now.hour <= 17

        # Request context
        features["has_context"] = bool(context)
        features["context_keys"] = list(context.keys()) if context else []
        features["context_size"] = len(str(context)) if context else 0

        # Source features
        features["source"] = context.get("source", "unknown")
        features["user_agent"] = context.get("user_agent", "")
        features["ip_address"] = context.get("ip_address", "")

        return features

    async def _extract_user_preferences(
        self, tenant_id: str, user_id: Optional[str]
    ) -> Dict[str, Any]:
        """Extract user preference features."""
        features = {}

        if not user_id:
            return features

        try:
            # Get user preferences
            prefs_key = f"user_prefs:{tenant_id}:{user_id}"
            prefs_data = await self.redis.hgetall(prefs_key)

            if prefs_data:
                features["preferred_agent"] = prefs_data.get("preferred_agent", "")
                features["preferred_tier"] = prefs_data.get("preferred_tier", "A")
                features["language"] = prefs_data.get("language", "en")
                features["timezone"] = prefs_data.get("timezone", "UTC")
            else:
                features["preferred_agent"] = ""
                features["preferred_tier"] = "A"
                features["language"] = "en"
                features["timezone"] = "UTC"

        except Exception as e:
            logger.error("Failed to extract user preferences", error=str(e))

        return features

    async def _extract_session_features(
        self, session_id: Optional[str], tenant_id: str
    ) -> Dict[str, Any]:
        """Extract session-based features."""
        features = {}

        if not session_id:
            return features

        try:
            # Get session data
            session_key = f"session:{tenant_id}:{session_id}"
            session_data = await self.redis.hgetall(session_key)

            if session_data:
                features["session_duration"] = float(session_data.get("duration", 0))
                features["session_message_count"] = int(
                    session_data.get("message_count", 0)
                )
                features["session_agent_switches"] = int(
                    session_data.get("agent_switches", 0)
                )
                features["session_escalations"] = int(
                    session_data.get("escalations", 0)
                )
            else:
                features["session_duration"] = 0.0
                features["session_message_count"] = 0
                features["session_agent_switches"] = 0
                features["session_escalations"] = 0

        except Exception as e:
            logger.error("Failed to extract session features", error=str(e))

        return features

    async def _cache_features(
        self, tenant_id: str, user_id: Optional[str], features: Dict[str, Any]
    ) -> None:
        """Cache extracted features."""
        try:
            cache_key = (
                f"features:{tenant_id}:{user_id or 'anonymous'}:{int(time.time())}"
            )
            await self.redis.setex(cache_key, self.feature_ttl, json.dumps(features))
        except Exception as e:
            logger.error("Failed to cache features", error=str(e))

    async def get_feature_importance(self, tenant_id: str) -> Dict[str, float]:
        """Get feature importance scores for a tenant."""
        try:
            # This would typically be calculated from historical data
            # For now, return default importance scores
            return {
                "text_length": 0.1,
                "word_count": 0.1,
                "intent_order": 0.15,
                "intent_support": 0.15,
                "sentiment_negative": 0.1,
                "urgency_high": 0.1,
                "technical_complexity": 0.1,
                "user_success_rate": 0.1,
                "tenant_success_rate": 0.1,
            }
        except Exception as e:
            logger.error("Failed to get feature importance", error=str(e))
            return {}

    async def update_feature_importance(
        self, tenant_id: str, feature_importance: Dict[str, float]
    ) -> bool:
        """Update feature importance scores for a tenant."""
        try:
            importance_key = f"feature_importance:{tenant_id}"
            await self.redis.setex(
                importance_key, 86400, json.dumps(feature_importance)  # 24 hours
            )
            return True
        except Exception as e:
            logger.error("Failed to update feature importance", error=str(e))
            return False
