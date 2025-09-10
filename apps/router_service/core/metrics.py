"""Metrics collection for Router v2."""

import time
from typing import Dict, Any, Optional
import structlog
import redis.asyncio as redis
from dataclasses import dataclass

from .feature_extractor import Tier

logger = structlog.get_logger(__name__)


@dataclass
class RouterMetrics:
    """Router metrics data structure."""
    decision_latency_ms: float
    misroute_rate: float
    tier_distribution: Dict[str, int]
    expected_vs_actual_cost: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    last_updated: float


class MetricsCollector:
    """Collects and exposes router metrics."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.metrics_prefix = "router_metrics"
    
    async def record_decision(
        self,
        tenant_id: str,
        tier: Tier,
        decision_time_ms: float,
        success: bool,
        expected_cost: float,
        actual_cost: float
    ) -> None:
        """Record a routing decision."""
        try:
            timestamp = time.time()
            
            # Record decision latency
            await self._record_latency(tenant_id, decision_time_ms, timestamp)
            
            # Record tier distribution
            await self._record_tier_distribution(tenant_id, tier, timestamp)
            
            # Record success/failure
            await self._record_success_failure(tenant_id, success, timestamp)
            
            # Record cost comparison
            await self._record_cost_comparison(tenant_id, expected_cost, actual_cost, timestamp)
            
            # Update total requests
            await self._increment_total_requests(tenant_id, timestamp)
            
        except Exception as e:
            logger.error("Failed to record decision metrics", error=str(e))
    
    async def get_metrics(self, tenant_id: str) -> RouterMetrics:
        """Get current metrics for tenant."""
        try:
            # Get latency metrics
            latency_metrics = await self._get_latency_metrics(tenant_id)
            
            # Get tier distribution
            tier_distribution = await self._get_tier_distribution(tenant_id)
            
            # Get success/failure metrics
            success_metrics = await self._get_success_metrics(tenant_id)
            
            # Get cost comparison
            cost_comparison = await self._get_cost_comparison(tenant_id)
            
            # Calculate misroute rate
            misroute_rate = await self._calculate_misroute_rate(tenant_id)
            
            return RouterMetrics(
                decision_latency_ms=latency_metrics.get('p50', 0.0),
                misroute_rate=misroute_rate,
                tier_distribution=tier_distribution,
                expected_vs_actual_cost=cost_comparison,
                total_requests=success_metrics.get('total', 0),
                successful_requests=success_metrics.get('successful', 0),
                failed_requests=success_metrics.get('failed', 0),
                last_updated=time.time()
            )
            
        except Exception as e:
            logger.error("Failed to get metrics", error=str(e))
            return RouterMetrics(
                decision_latency_ms=0.0,
                misroute_rate=0.0,
                tier_distribution={},
                expected_vs_actual_cost=0.0,
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                last_updated=time.time()
            )
    
    async def _record_latency(self, tenant_id: str, latency_ms: float, timestamp: float) -> None:
        """Record decision latency."""
        try:
            latency_key = f"{self.metrics_prefix}:latency:{tenant_id}"
            
            # Store latency with timestamp
            await self.redis.zadd(latency_key, {str(timestamp): latency_ms})
            
            # Keep only last 1000 measurements
            await self.redis.zremrangebyrank(latency_key, 0, -1001)
            
            # Set TTL
            await self.redis.expire(latency_key, 86400 * 7)  # 7 days
            
        except Exception as e:
            logger.error("Failed to record latency", error=str(e))
    
    async def _record_tier_distribution(self, tenant_id: str, tier: Tier, timestamp: float) -> None:
        """Record tier distribution."""
        try:
            tier_key = f"{self.metrics_prefix}:tier_distribution:{tenant_id}"
            
            # Increment tier counter
            await self.redis.hincrby(tier_key, tier.value, 1)
            
            # Set TTL
            await self.redis.expire(tier_key, 86400 * 7)  # 7 days
            
        except Exception as e:
            logger.error("Failed to record tier distribution", error=str(e))
    
    async def _record_success_failure(self, tenant_id: str, success: bool, timestamp: float) -> None:
        """Record success/failure."""
        try:
            success_key = f"{self.metrics_prefix}:success:{tenant_id}"
            
            if success:
                await self.redis.hincrby(success_key, 'successful', 1)
            else:
                await self.redis.hincrby(success_key, 'failed', 1)
            
            # Set TTL
            await self.redis.expire(success_key, 86400 * 7)  # 7 days
            
        except Exception as e:
            logger.error("Failed to record success/failure", error=str(e))
    
    async def _record_cost_comparison(self, tenant_id: str, expected_cost: float, actual_cost: float, timestamp: float) -> None:
        """Record cost comparison."""
        try:
            cost_key = f"{self.metrics_prefix}:cost:{tenant_id}"
            
            # Store cost comparison
            cost_data = {
                'expected': expected_cost,
                'actual': actual_cost,
                'timestamp': timestamp
            }
            
            await self.redis.hset(cost_key, mapping=cost_data)
            
            # Set TTL
            await self.redis.expire(cost_key, 86400 * 7)  # 7 days
            
        except Exception as e:
            logger.error("Failed to record cost comparison", error=str(e))
    
    async def _increment_total_requests(self, tenant_id: str, timestamp: float) -> None:
        """Increment total requests counter."""
        try:
            total_key = f"{self.metrics_prefix}:total:{tenant_id}"
            await self.redis.hincrby(total_key, 'total', 1)
            await self.redis.hset(total_key, 'last_updated', timestamp)
            await self.redis.expire(total_key, 86400 * 7)  # 7 days
            
        except Exception as e:
            logger.error("Failed to increment total requests", error=str(e))
    
    async def _get_latency_metrics(self, tenant_id: str) -> Dict[str, float]:
        """Get latency metrics."""
        try:
            latency_key = f"{self.metrics_prefix}:latency:{tenant_id}"
            
            # Get all latency values
            latency_values = await self.redis.zrange(latency_key, 0, -1, withscores=True)
            
            if not latency_values:
                return {'p50': 0.0, 'p95': 0.0, 'p99': 0.0, 'avg': 0.0}
            
            # Extract values
            values = [float(score) for _, score in latency_values]
            values.sort()
            
            # Calculate percentiles
            n = len(values)
            p50 = values[int(n * 0.5)] if n > 0 else 0.0
            p95 = values[int(n * 0.95)] if n > 0 else 0.0
            p99 = values[int(n * 0.99)] if n > 0 else 0.0
            avg = sum(values) / n if n > 0 else 0.0
            
            return {
                'p50': p50,
                'p95': p95,
                'p99': p99,
                'avg': avg
            }
            
        except Exception as e:
            logger.error("Failed to get latency metrics", error=str(e))
            return {'p50': 0.0, 'p95': 0.0, 'p99': 0.0, 'avg': 0.0}
    
    async def _get_tier_distribution(self, tenant_id: str) -> Dict[str, int]:
        """Get tier distribution."""
        try:
            tier_key = f"{self.metrics_prefix}:tier_distribution:{tenant_id}"
            tier_data = await self.redis.hgetall(tier_key)
            
            distribution = {}
            for tier in Tier:
                distribution[tier.value] = int(tier_data.get(tier.value, 0))
            
            return distribution
            
        except Exception as e:
            logger.error("Failed to get tier distribution", error=str(e))
            return {tier.value: 0 for tier in Tier}
    
    async def _get_success_metrics(self, tenant_id: str) -> Dict[str, int]:
        """Get success metrics."""
        try:
            success_key = f"{self.metrics_prefix}:success:{tenant_id}"
            success_data = await self.redis.hgetall(success_key)
            
            return {
                'total': int(success_data.get('total', 0)),
                'successful': int(success_data.get('successful', 0)),
                'failed': int(success_data.get('failed', 0))
            }
            
        except Exception as e:
            logger.error("Failed to get success metrics", error=str(e))
            return {'total': 0, 'successful': 0, 'failed': 0}
    
    async def _get_cost_comparison(self, tenant_id: str) -> float:
        """Get cost comparison ratio."""
        try:
            cost_key = f"{self.metrics_prefix}:cost:{tenant_id}"
            cost_data = await self.redis.hgetall(cost_key)
            
            if not cost_data:
                return 0.0
            
            expected = float(cost_data.get('expected', 0))
            actual = float(cost_data.get('actual', 0))
            
            if expected == 0:
                return 0.0
            
            return actual / expected
            
        except Exception as e:
            logger.error("Failed to get cost comparison", error=str(e))
            return 0.0
    
    async def _calculate_misroute_rate(self, tenant_id: str) -> float:
        """Calculate misroute rate."""
        try:
            # Get recent outcomes to calculate misroute rate
            # This is a simplified calculation - in production, you'd want more sophisticated logic
            success_metrics = await self._get_success_metrics(tenant_id)
            
            total = success_metrics.get('total', 0)
            failed = success_metrics.get('failed', 0)
            
            if total == 0:
                return 0.0
            
            return failed / total
            
        except Exception as e:
            logger.error("Failed to calculate misroute rate", error=str(e))
            return 0.0
    
    async def reset_metrics(self, tenant_id: str) -> None:
        """Reset metrics for tenant."""
        try:
            # Get all metric keys for tenant
            pattern = f"{self.metrics_prefix}:*:{tenant_id}"
            keys = await self.redis.keys(pattern)
            
            if keys:
                await self.redis.delete(*keys)
            
            logger.info("Metrics reset", tenant_id=tenant_id)
            
        except Exception as e:
            logger.error("Failed to reset metrics", error=str(e))
