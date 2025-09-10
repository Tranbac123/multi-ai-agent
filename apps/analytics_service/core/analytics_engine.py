"""Analytics engine for CQRS read-only analytics."""

import asyncio
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import structlog
import redis.asyncio as redis

logger = structlog.get_logger(__name__)


@dataclass
class KPIMetrics:
    """KPI metrics for analytics."""
    tenant_id: str
    time_window: str
    success_rate: float
    p50_latency: float
    p95_latency: float
    tokens_in: int
    tokens_out: int
    cost_per_run: float
    tier_distribution: Dict[str, int]
    router_misroute_rate: float
    expected_vs_actual_cost: float
    expected_vs_actual_latency: float
    timestamp: datetime


class AnalyticsEngine:
    """Analytics engine for CQRS read-only analytics."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.cache_ttl = 300  # 5 minutes cache TTL
    
    async def get_kpi_metrics(
        self,
        tenant_id: str,
        time_window: str = "1h"
    ) -> KPIMetrics:
        """Get KPI metrics for tenant."""
        try:
            # Check cache first
            cache_key = f"kpi_metrics:{tenant_id}:{time_window}"
            cached_metrics = await self._get_cached_metrics(cache_key)
            
            if cached_metrics:
                return cached_metrics
            
            # Get metrics from data source (Postgres read-replica)
            metrics = await self._get_postgres_metrics(tenant_id, time_window)
            
            # Cache results
            await self._cache_metrics(cache_key, metrics)
            
            return metrics
            
        except Exception as e:
            logger.error("Failed to get KPI metrics", error=str(e), tenant_id=tenant_id)
            return self._get_default_metrics(tenant_id, time_window)
    
    async def _get_postgres_metrics(
        self,
        tenant_id: str,
        time_window: str
    ) -> KPIMetrics:
        """Get metrics from Postgres read-replica."""
        try:
            # Query Postgres for metrics
            # This would use actual SQL queries in production
            # For now, return default metrics
            return self._get_default_metrics(tenant_id, time_window)
            
        except Exception as e:
            logger.error("Failed to get Postgres metrics", error=str(e))
            return self._get_default_metrics(tenant_id, time_window)
    
    def _get_default_metrics(self, tenant_id: str, time_window: str) -> KPIMetrics:
        """Get default metrics when data is unavailable."""
        return KPIMetrics(
            tenant_id=tenant_id,
            time_window=time_window,
            success_rate=0.95,
            p50_latency=50.0,
            p95_latency=200.0,
            tokens_in=100,
            tokens_out=150,
            cost_per_run=0.01,
            tier_distribution={'A': 50, 'B': 30, 'C': 20},
            router_misroute_rate=0.02,
            expected_vs_actual_cost=1.0,
            expected_vs_actual_latency=1.0,
            timestamp=datetime.utcnow()
        )
    
    async def _get_cached_metrics(self, cache_key: str) -> Optional[KPIMetrics]:
        """Get cached metrics from Redis."""
        try:
            cached_data = await self.redis.get(cache_key)
            if cached_data:
                import json
                data = json.loads(cached_data)
                return KPIMetrics(**data)
            return None
        except Exception:
            return None
    
    async def _cache_metrics(self, cache_key: str, metrics: KPIMetrics) -> None:
        """Cache metrics in Redis."""
        try:
            import json
            data = json.dumps(metrics.__dict__, default=str)
            await self.redis.setex(cache_key, self.cache_ttl, data)
        except Exception as e:
            logger.error("Failed to cache metrics", error=str(e))