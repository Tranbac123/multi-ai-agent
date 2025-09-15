"""Canary manager for per-tenant canary deployments with auto-rollback."""

import asyncio
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import structlog
import redis.asyncio as redis

from .feature_extractor import RouterFeatures, Tier

logger = structlog.get_logger(__name__)


class CanaryStatus(Enum):
    """Canary deployment status."""

    INACTIVE = "inactive"
    ACTIVE = "active"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    PROMOTED = "promoted"


@dataclass
class CanaryConfig:
    """Canary configuration."""

    tenant_id: str
    canary_percentage: float  # 5-10%
    quality_threshold: float  # Quality threshold for auto-rollback
    min_requests: int  # Minimum requests before evaluation
    evaluation_window: int  # Time window for evaluation (seconds)
    rollback_threshold: float  # Quality drop threshold for rollback


@dataclass
class CanaryMetrics:
    """Canary metrics."""

    total_requests: int
    successful_requests: int
    failed_requests: int
    average_latency: float
    quality_score: float
    last_updated: float


class CanaryManager:
    """Canary manager for per-tenant canary deployments."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.default_canary_percentage = 0.1  # 10%
        self.default_quality_threshold = 0.85
        self.default_min_requests = 100
        self.default_evaluation_window = 3600  # 1 hour
        self.default_rollback_threshold = 0.1  # 10% quality drop

    async def should_use_canary(
        self, tenant_id: str, user_id: str, features: RouterFeatures
    ) -> Tuple[bool, Optional[Tier], Dict[str, Any]]:
        """Determine if request should use canary version."""
        try:
            # Get canary configuration
            canary_config = await self._get_canary_config(tenant_id)

            if canary_config.status == CanaryStatus.INACTIVE:
                return False, None, {"reason": "canary_inactive"}

            if canary_config.status == CanaryStatus.ROLLING_BACK:
                return False, None, {"reason": "canary_rolling_back"}

            # Check if user should be in canary
            is_canary_user = await self._is_canary_user(
                tenant_id, user_id, canary_config.canary_percentage
            )

            if not is_canary_user:
                return False, None, {"reason": "not_canary_user"}

            # Get canary tier
            canary_tier = await self._get_canary_tier(tenant_id, features)

            if canary_tier is None:
                return False, None, {"reason": "no_canary_tier"}

            # Record canary selection
            await self._record_canary_selection(tenant_id, user_id, canary_tier)

            return (
                True,
                canary_tier,
                {
                    "canary_percentage": canary_config.canary_percentage,
                    "canary_tier": canary_tier.value,
                    "user_id": user_id,
                },
            )

        except Exception as e:
            logger.error("Canary decision failed", error=str(e))
            return False, None, {"reason": "error", "error": str(e)}

    async def record_canary_outcome(
        self,
        tenant_id: str,
        user_id: str,
        tier: Tier,
        success: bool,
        latency: float,
        quality_score: float,
    ) -> None:
        """Record canary outcome for evaluation."""
        try:
            # Record outcome
            outcome_key = f"canary_outcome:{tenant_id}:{int(time.time())}"
            outcome_data = {
                "user_id": user_id,
                "tier": tier.value,
                "success": success,
                "latency": latency,
                "quality_score": quality_score,
                "timestamp": time.time(),
            }

            await self.redis.hset(outcome_key, mapping=outcome_data)
            await self.redis.expire(outcome_key, 86400 * 7)  # 7 days TTL

            # Update canary metrics
            await self._update_canary_metrics(
                tenant_id, success, latency, quality_score
            )

            # Check if rollback is needed
            await self._check_rollback_conditions(tenant_id)

        except Exception as e:
            logger.error("Failed to record canary outcome", error=str(e))

    async def _get_canary_config(self, tenant_id: str) -> CanaryConfig:
        """Get canary configuration for tenant."""
        try:
            config_key = f"canary_config:{tenant_id}"
            config_data = await self.redis.hgetall(config_key)

            if config_data:
                return CanaryConfig(
                    tenant_id=tenant_id,
                    canary_percentage=float(
                        config_data.get(
                            "canary_percentage", self.default_canary_percentage
                        )
                    ),
                    quality_threshold=float(
                        config_data.get(
                            "quality_threshold", self.default_quality_threshold
                        )
                    ),
                    min_requests=int(
                        config_data.get("min_requests", self.default_min_requests)
                    ),
                    evaluation_window=int(
                        config_data.get(
                            "evaluation_window", self.default_evaluation_window
                        )
                    ),
                    rollback_threshold=float(
                        config_data.get(
                            "rollback_threshold", self.default_rollback_threshold
                        )
                    ),
                )

            # Create default configuration
            default_config = CanaryConfig(
                tenant_id=tenant_id,
                canary_percentage=self.default_canary_percentage,
                quality_threshold=self.default_quality_threshold,
                min_requests=self.default_min_requests,
                evaluation_window=self.default_evaluation_window,
                rollback_threshold=self.default_rollback_threshold,
            )

            # Store default configuration
            await self._store_canary_config(default_config)

            return default_config

        except Exception as e:
            logger.error("Failed to get canary config", error=str(e))
            return CanaryConfig(
                tenant_id=tenant_id,
                canary_percentage=self.default_canary_percentage,
                quality_threshold=self.default_quality_threshold,
                min_requests=self.default_min_requests,
                evaluation_window=self.default_evaluation_window,
                rollback_threshold=self.default_rollback_threshold,
            )

    async def _store_canary_config(self, config: CanaryConfig) -> None:
        """Store canary configuration."""
        try:
            config_key = f"canary_config:{config.tenant_id}"
            await self.redis.hset(
                config_key,
                mapping={
                    "canary_percentage": config.canary_percentage,
                    "quality_threshold": config.quality_threshold,
                    "min_requests": config.min_requests,
                    "evaluation_window": config.evaluation_window,
                    "rollback_threshold": config.rollback_threshold,
                },
            )
            await self.redis.expire(config_key, 86400 * 30)  # 30 days TTL

        except Exception as e:
            logger.error("Failed to store canary config", error=str(e))

    async def _is_canary_user(
        self, tenant_id: str, user_id: str, canary_percentage: float
    ) -> bool:
        """Determine if user should be in canary."""
        try:
            # Use consistent hashing to determine canary users
            user_hash_key = f"user_hash:{tenant_id}:{user_id}"
            user_hash = await self.redis.get(user_hash_key)

            if user_hash is None:
                # Generate hash based on user_id
                import hashlib

                user_hash = hashlib.md5(f"{tenant_id}:{user_id}".encode()).hexdigest()
                await self.redis.setex(
                    user_hash_key, 86400 * 30, user_hash
                )  # 30 days TTL

            # Convert hash to percentage
            hash_int = int(user_hash, 16)
            user_percentage = (hash_int % 10000) / 10000.0

            return user_percentage < canary_percentage

        except Exception as e:
            logger.error("Failed to determine canary user", error=str(e))
            return False

    async def _get_canary_tier(
        self, tenant_id: str, features: RouterFeatures
    ) -> Optional[Tier]:
        """Get canary tier for request."""
        try:
            # Get canary tier mapping
            tier_key = f"canary_tier:{tenant_id}"
            tier_data = await self.redis.hgetall(tier_key)

            if not tier_data:
                # Default canary tier mapping
                if features.token_count < 100:
                    return Tier.A
                elif features.token_count < 500:
                    return Tier.B
                else:
                    return Tier.C

            # Use configured tier mapping
            if features.token_count < int(tier_data.get("tier_a_threshold", 100)):
                return Tier.A
            elif features.token_count < int(tier_data.get("tier_b_threshold", 500)):
                return Tier.B
            else:
                return Tier.C

        except Exception as e:
            logger.error("Failed to get canary tier", error=str(e))
            return None

    async def _record_canary_selection(
        self, tenant_id: str, user_id: str, tier: Tier
    ) -> None:
        """Record canary selection."""
        try:
            selection_key = f"canary_selection:{tenant_id}:{int(time.time())}"
            selection_data = {
                "user_id": user_id,
                "tier": tier.value,
                "timestamp": time.time(),
            }

            await self.redis.hset(selection_key, mapping=selection_data)
            await self.redis.expire(selection_key, 86400 * 7)  # 7 days TTL

        except Exception as e:
            logger.error("Failed to record canary selection", error=str(e))

    async def _update_canary_metrics(
        self, tenant_id: str, success: bool, latency: float, quality_score: float
    ) -> None:
        """Update canary metrics."""
        try:
            metrics_key = f"canary_metrics:{tenant_id}"

            # Update counters
            await self.redis.hincrby(metrics_key, "total_requests", 1)
            if success:
                await self.redis.hincrby(metrics_key, "successful_requests", 1)
            else:
                await self.redis.hincrby(metrics_key, "failed_requests", 1)

            # Update latency (rolling average)
            current_latency = await self.redis.hget(metrics_key, "average_latency")
            if current_latency:
                current_latency = float(current_latency)
                total_requests = int(
                    await self.redis.hget(metrics_key, "total_requests")
                )
                new_latency = (
                    current_latency * (total_requests - 1) + latency
                ) / total_requests
            else:
                new_latency = latency

            await self.redis.hset(metrics_key, "average_latency", new_latency)

            # Update quality score (rolling average)
            current_quality = await self.redis.hget(metrics_key, "quality_score")
            if current_quality:
                current_quality = float(current_quality)
                total_requests = int(
                    await self.redis.hget(metrics_key, "total_requests")
                )
                new_quality = (
                    current_quality * (total_requests - 1) + quality_score
                ) / total_requests
            else:
                new_quality = quality_score

            await self.redis.hset(metrics_key, "quality_score", new_quality)
            await self.redis.hset(metrics_key, "last_updated", time.time())
            await self.redis.expire(metrics_key, 86400 * 7)  # 7 days TTL

        except Exception as e:
            logger.error("Failed to update canary metrics", error=str(e))

    async def _check_rollback_conditions(self, tenant_id: str) -> None:
        """Check if canary should be rolled back."""
        try:
            config = await self._get_canary_config(tenant_id)
            metrics = await self._get_canary_metrics(tenant_id)

            if not metrics or metrics.total_requests < config.min_requests:
                return  # Not enough data

            # Check quality threshold
            if metrics.quality_score < config.quality_threshold:
                await self._initiate_rollback(tenant_id, "quality_threshold")
                return

            # Check if quality dropped significantly
            baseline_quality = await self._get_baseline_quality(tenant_id)
            if baseline_quality > 0:
                quality_drop = baseline_quality - metrics.quality_score
                if quality_drop > config.rollback_threshold:
                    await self._initiate_rollback(tenant_id, "quality_drop")
                    return

        except Exception as e:
            logger.error("Failed to check rollback conditions", error=str(e))

    async def _get_canary_metrics(self, tenant_id: str) -> Optional[CanaryMetrics]:
        """Get canary metrics."""
        try:
            metrics_key = f"canary_metrics:{tenant_id}"
            metrics_data = await self.redis.hgetall(metrics_key)

            if not metrics_data:
                return None

            return CanaryMetrics(
                total_requests=int(metrics_data.get("total_requests", 0)),
                successful_requests=int(metrics_data.get("successful_requests", 0)),
                failed_requests=int(metrics_data.get("failed_requests", 0)),
                average_latency=float(metrics_data.get("average_latency", 0)),
                quality_score=float(metrics_data.get("quality_score", 0)),
                last_updated=float(metrics_data.get("last_updated", time.time())),
            )

        except Exception as e:
            logger.error("Failed to get canary metrics", error=str(e))
            return None

    async def _get_baseline_quality(self, tenant_id: str) -> float:
        """Get baseline quality for comparison."""
        try:
            baseline_key = f"baseline_quality:{tenant_id}"
            baseline_quality = await self.redis.get(baseline_key)

            if baseline_quality:
                return float(baseline_quality)

            # Default baseline quality
            return 0.9

        except Exception as e:
            logger.error("Failed to get baseline quality", error=str(e))
            return 0.9

    async def _initiate_rollback(self, tenant_id: str, reason: str) -> None:
        """Initiate canary rollback."""
        try:
            rollback_key = f"canary_rollback:{tenant_id}"
            await self.redis.hset(
                rollback_key,
                mapping={
                    "status": CanaryStatus.ROLLING_BACK.value,
                    "reason": reason,
                    "initiated_at": time.time(),
                },
            )
            await self.redis.expire(rollback_key, 86400 * 7)  # 7 days TTL

            logger.warning(
                "Canary rollback initiated", tenant_id=tenant_id, reason=reason
            )

        except Exception as e:
            logger.error("Failed to initiate rollback", error=str(e))

    async def get_canary_status(self, tenant_id: str) -> Dict[str, Any]:
        """Get canary status for tenant."""
        try:
            config = await self._get_canary_config(tenant_id)
            metrics = await self._get_canary_metrics(tenant_id)

            # Check rollback status
            rollback_key = f"canary_rollback:{tenant_id}"
            rollback_data = await self.redis.hgetall(rollback_key)

            status = {
                "tenant_id": tenant_id,
                "config": {
                    "canary_percentage": config.canary_percentage,
                    "quality_threshold": config.quality_threshold,
                    "min_requests": config.min_requests,
                    "evaluation_window": config.evaluation_window,
                    "rollback_threshold": config.rollback_threshold,
                },
                "metrics": metrics.__dict__ if metrics else None,
                "rollback_status": rollback_data.get(
                    "status", CanaryStatus.INACTIVE.value
                )
                if rollback_data
                else CanaryStatus.INACTIVE.value,
                "rollback_reason": rollback_data.get("reason")
                if rollback_data
                else None,
            }

            return status

        except Exception as e:
            logger.error("Failed to get canary status", error=str(e))
            return {"error": str(e)}
