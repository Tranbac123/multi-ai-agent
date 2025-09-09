"""Analytics engine for CQRS read-only analytics."""

import asyncio
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import structlog
import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class AnalyticsEngine:
    """Analytics engine for processing and aggregating metrics."""
    
    def __init__(self, redis_client: redis.Redis, db_session: AsyncSession):
        self.redis = redis_client
        self.db_session = db_session
        self.cache_ttl = 300  # 5 minutes
    
    async def get_success_rate(
        self,
        tenant_id: str,
        time_window: str = "1h",
        workflow: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get success rate for agent runs."""
        try:
            cache_key = f"analytics:success_rate:{tenant_id}:{time_window}:{workflow or 'all'}"
            
            # Check cache first
            cached_result = await self.redis.get(cache_key)
            if cached_result:
                import json
                return json.loads(cached_result)
            
            # Calculate time range
            end_time = datetime.utcnow()
            start_time = self._get_start_time(end_time, time_window)
            
            # Build query
            query = """
                SELECT 
                    COUNT(*) as total_runs,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_runs,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_runs
                FROM agent_runs 
                WHERE tenant_id = :tenant_id 
                AND created_at >= :start_time 
                AND created_at <= :end_time
            """
            
            params = {
                'tenant_id': tenant_id,
                'start_time': start_time,
                'end_time': end_time
            }
            
            if workflow:
                query += " AND workflow = :workflow"
                params['workflow'] = workflow
            
            result = await self.db_session.execute(text(query), params)
            row = result.fetchone()
            
            total_runs = row[0] or 0
            successful_runs = row[1] or 0
            failed_runs = row[2] or 0
            
            success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0
            
            analytics_data = {
                'tenant_id': tenant_id,
                'time_window': time_window,
                'workflow': workflow,
                'total_runs': total_runs,
                'successful_runs': successful_runs,
                'failed_runs': failed_runs,
                'success_rate': round(success_rate, 2),
                'timestamp': time.time()
            }
            
            # Cache result
            await self.redis.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(analytics_data)
            )
            
            return analytics_data
            
        except Exception as e:
            logger.error(
                "Failed to get success rate",
                error=str(e),
                tenant_id=tenant_id,
                time_window=time_window
            )
            return {
                'tenant_id': tenant_id,
                'success_rate': 0,
                'error': str(e)
            }
    
    async def get_latency_metrics(
        self,
        tenant_id: str,
        time_window: str = "1h",
        workflow: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get latency metrics (p50, p95, p99)."""
        try:
            cache_key = f"analytics:latency:{tenant_id}:{time_window}:{workflow or 'all'}"
            
            # Check cache first
            cached_result = await self.redis.get(cache_key)
            if cached_result:
                import json
                return json.loads(cached_result)
            
            # Calculate time range
            end_time = datetime.utcnow()
            start_time = self._get_start_time(end_time, time_window)
            
            # Build query
            query = """
                SELECT 
                    AVG(EXTRACT(EPOCH FROM (finished_at - created_at)) * 1000) as avg_latency_ms,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (finished_at - created_at)) * 1000) as p50_latency_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (finished_at - created_at)) * 1000) as p95_latency_ms,
                    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (finished_at - created_at)) * 1000) as p99_latency_ms,
                    MIN(EXTRACT(EPOCH FROM (finished_at - created_at)) * 1000) as min_latency_ms,
                    MAX(EXTRACT(EPOCH FROM (finished_at - created_at)) * 1000) as max_latency_ms
                FROM agent_runs 
                WHERE tenant_id = :tenant_id 
                AND created_at >= :start_time 
                AND created_at <= :end_time
                AND finished_at IS NOT NULL
            """
            
            params = {
                'tenant_id': tenant_id,
                'start_time': start_time,
                'end_time': end_time
            }
            
            if workflow:
                query += " AND workflow = :workflow"
                params['workflow'] = workflow
            
            result = await self.db_session.execute(text(query), params)
            row = result.fetchone()
            
            analytics_data = {
                'tenant_id': tenant_id,
                'time_window': time_window,
                'workflow': workflow,
                'avg_latency_ms': round(float(row[0] or 0), 2),
                'p50_latency_ms': round(float(row[1] or 0), 2),
                'p95_latency_ms': round(float(row[2] or 0), 2),
                'p99_latency_ms': round(float(row[3] or 0), 2),
                'min_latency_ms': round(float(row[4] or 0), 2),
                'max_latency_ms': round(float(row[5] or 0), 2),
                'timestamp': time.time()
            }
            
            # Cache result
            await self.redis.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(analytics_data)
            )
            
            return analytics_data
            
        except Exception as e:
            logger.error(
                "Failed to get latency metrics",
                error=str(e),
                tenant_id=tenant_id,
                time_window=time_window
            )
            return {
                'tenant_id': tenant_id,
                'avg_latency_ms': 0,
                'error': str(e)
            }
    
    async def get_cost_metrics(
        self,
        tenant_id: str,
        time_window: str = "1h",
        workflow: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get cost metrics for agent runs."""
        try:
            cache_key = f"analytics:cost:{tenant_id}:{time_window}:{workflow or 'all'}"
            
            # Check cache first
            cached_result = await self.redis.get(cache_key)
            if cached_result:
                import json
                return json.loads(cached_result)
            
            # Calculate time range
            end_time = datetime.utcnow()
            start_time = self._get_start_time(end_time, time_window)
            
            # Build query
            query = """
                SELECT 
                    SUM(cost_usd) as total_cost_usd,
                    AVG(cost_usd) as avg_cost_per_run_usd,
                    SUM(tokens_in) as total_tokens_in,
                    SUM(tokens_out) as total_tokens_out,
                    COUNT(*) as total_runs
                FROM agent_runs 
                WHERE tenant_id = :tenant_id 
                AND created_at >= :start_time 
                AND created_at <= :end_time
            """
            
            params = {
                'tenant_id': tenant_id,
                'start_time': start_time,
                'end_time': end_time
            }
            
            if workflow:
                query += " AND workflow = :workflow"
                params['workflow'] = workflow
            
            result = await self.db_session.execute(text(query), params)
            row = result.fetchone()
            
            analytics_data = {
                'tenant_id': tenant_id,
                'time_window': time_window,
                'workflow': workflow,
                'total_cost_usd': round(float(row[0] or 0), 4),
                'avg_cost_per_run_usd': round(float(row[1] or 0), 4),
                'total_tokens_in': int(row[2] or 0),
                'total_tokens_out': int(row[3] or 0),
                'total_runs': int(row[4] or 0),
                'timestamp': time.time()
            }
            
            # Cache result
            await self.redis.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(analytics_data)
            )
            
            return analytics_data
            
        except Exception as e:
            logger.error(
                "Failed to get cost metrics",
                error=str(e),
                tenant_id=tenant_id,
                time_window=time_window
            )
            return {
                'tenant_id': tenant_id,
                'total_cost_usd': 0,
                'error': str(e)
            }
    
    async def get_router_metrics(
        self,
        tenant_id: str,
        time_window: str = "1h"
    ) -> Dict[str, Any]:
        """Get router performance metrics."""
        try:
            cache_key = f"analytics:router:{tenant_id}:{time_window}"
            
            # Check cache first
            cached_result = await self.redis.get(cache_key)
            if cached_result:
                import json
                return json.loads(cached_result)
            
            # Calculate time range
            end_time = datetime.utcnow()
            start_time = self._get_start_time(end_time, time_window)
            
            # Get router decisions from events (simplified)
            # In a real implementation, this would query router decision events
            analytics_data = {
                'tenant_id': tenant_id,
                'time_window': time_window,
                'total_decisions': 0,
                'tier_distribution': {'A': 0, 'B': 0, 'C': 0},
                'avg_decision_latency_ms': 0,
                'misroute_rate': 0,
                'timestamp': time.time()
            }
            
            # Cache result
            await self.redis.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(analytics_data)
            )
            
            return analytics_data
            
        except Exception as e:
            logger.error(
                "Failed to get router metrics",
                error=str(e),
                tenant_id=tenant_id,
                time_window=time_window
            )
            return {
                'tenant_id': tenant_id,
                'total_decisions': 0,
                'error': str(e)
            }
    
    async def get_tenant_kpis(
        self,
        tenant_id: str,
        time_window: str = "24h"
    ) -> Dict[str, Any]:
        """Get comprehensive KPIs for a tenant."""
        try:
            # Get all metrics in parallel
            success_rate_task = self.get_success_rate(tenant_id, time_window)
            latency_task = self.get_latency_metrics(tenant_id, time_window)
            cost_task = self.get_cost_metrics(tenant_id, time_window)
            router_task = self.get_router_metrics(tenant_id, time_window)
            
            success_rate, latency, cost, router = await asyncio.gather(
                success_rate_task, latency_task, cost_task, router_task
            )
            
            # Calculate derived metrics
            efficiency_score = self._calculate_efficiency_score(success_rate, latency, cost)
            
            kpis = {
                'tenant_id': tenant_id,
                'time_window': time_window,
                'success_rate': success_rate,
                'latency': latency,
                'cost': cost,
                'router': router,
                'efficiency_score': efficiency_score,
                'timestamp': time.time()
            }
            
            return kpis
            
        except Exception as e:
            logger.error(
                "Failed to get tenant KPIs",
                error=str(e),
                tenant_id=tenant_id,
                time_window=time_window
            )
            return {
                'tenant_id': tenant_id,
                'error': str(e)
            }
    
    def _calculate_efficiency_score(
        self,
        success_rate: Dict[str, Any],
        latency: Dict[str, Any],
        cost: Dict[str, Any]
    ) -> float:
        """Calculate efficiency score based on success rate, latency, and cost."""
        try:
            success_score = success_rate.get('success_rate', 0) / 100
            latency_score = max(0, 1 - (latency.get('p95_latency_ms', 0) / 10000))  # Normalize to 10s
            cost_score = max(0, 1 - (cost.get('avg_cost_per_run_usd', 0) / 1.0))  # Normalize to $1
            
            efficiency_score = (success_score * 0.5 + latency_score * 0.3 + cost_score * 0.2) * 100
            return round(efficiency_score, 2)
            
        except Exception as e:
            logger.error("Failed to calculate efficiency score", error=str(e))
            return 0.0
    
    def _get_start_time(self, end_time: datetime, time_window: str) -> datetime:
        """Get start time based on time window."""
        if time_window == "1h":
            return end_time - timedelta(hours=1)
        elif time_window == "24h":
            return end_time - timedelta(days=1)
        elif time_window == "7d":
            return end_time - timedelta(days=7)
        elif time_window == "30d":
            return end_time - timedelta(days=30)
        else:
            return end_time - timedelta(hours=1)  # Default to 1 hour
