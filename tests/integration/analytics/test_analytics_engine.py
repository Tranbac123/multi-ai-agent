"""Test analytics engine functionality."""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from dataclasses import asdict

from apps.analytics_service.core.analytics_engine import (
    AnalyticsEngine,
    DataSource,
    TimeWindow,
    KPIMetrics,
    TenantAnalytics,
)


class TestAnalyticsEngine:
    """Test AnalyticsEngine functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis_client = Mock()
        redis_client.get = AsyncMock()
        redis_client.setex = AsyncMock()
        redis_client.keys = AsyncMock(return_value=[])
        redis_client.delete = AsyncMock()
        return redis_client

    @pytest.fixture
    def analytics_engine(self, mock_redis):
        """Create AnalyticsEngine instance."""
        return AnalyticsEngine(
            redis_client=mock_redis,
            data_source=DataSource.CLICKHOUSE,
            warehouse_config={
                "host": "localhost",
                "port": 9000,
                "project_id": "test-project",
            },
        )

    @pytest.mark.asyncio
    async def test_get_kpi_metrics_from_cache(self, analytics_engine, mock_redis):
        """Test getting KPI metrics from cache."""
        tenant_id = "tenant_123"
        time_window = "1h"
        
        # Mock cached metrics
        cached_metrics = KPIMetrics(
            tenant_id=tenant_id,
            time_window=time_window,
            success_rate=0.98,
            p50_latency=45.0,
            p95_latency=180.0,
            p99_latency=300.0,
            tokens_in=120,
            tokens_out=180,
            cost_per_run=0.008,
            total_cost=120.0,
            tier_distribution={"A": 60, "B": 25, "C": 15},
            router_misroute_rate=0.015,
            expected_vs_actual_cost=0.98,
            expected_vs_actual_latency=1.02,
            total_requests=1500,
            successful_requests=1470,
            failed_requests=30,
            avg_tokens_per_request=150.0,
            cost_efficiency=0.98,
            latency_efficiency=1.02,
            data_source=DataSource.CLICKHOUSE.value,
            timestamp=datetime.utcnow(),
        )
        
        mock_redis.get.return_value = json.dumps(asdict(cached_metrics), default=str)
        
        result = await analytics_engine.get_kpi_metrics(tenant_id, time_window)
        
        assert result.tenant_id == tenant_id
        assert result.time_window == time_window
        assert result.success_rate == 0.98
        assert result.p50_latency == 45.0
        assert result.cost_efficiency == 0.98

    @pytest.mark.asyncio
    async def test_get_kpi_metrics_from_warehouse(self, analytics_engine, mock_redis):
        """Test getting KPI metrics from warehouse when not cached."""
        tenant_id = "tenant_123"
        time_window = "1h"
        
        # No cached data
        mock_redis.get.return_value = None
        
        with patch.object(analytics_engine, '_get_clickhouse_metrics') as mock_warehouse:
            mock_metrics = KPIMetrics(
                tenant_id=tenant_id,
                time_window=time_window,
                success_rate=0.97,
                p50_latency=40.0,
                p95_latency=160.0,
                p99_latency=280.0,
                tokens_in=110,
                tokens_out=170,
                cost_per_run=0.007,
                total_cost=110.0,
                tier_distribution={"A": 65, "B": 20, "C": 15},
                router_misroute_rate=0.012,
                expected_vs_actual_cost=0.97,
                expected_vs_actual_latency=1.03,
                total_requests=1400,
                successful_requests=1358,
                failed_requests=42,
                avg_tokens_per_request=145.0,
                cost_efficiency=0.97,
                latency_efficiency=1.03,
                data_source=DataSource.CLICKHOUSE.value,
                timestamp=datetime.utcnow(),
            )
            mock_warehouse.return_value = mock_metrics
            
            result = await analytics_engine.get_kpi_metrics(tenant_id, time_window)
            
            assert result.tenant_id == tenant_id
            assert result.success_rate == 0.97
            assert result.cost_efficiency == 0.97
            mock_warehouse.assert_called_once_with(tenant_id, time_window)

    @pytest.mark.asyncio
    async def test_get_comprehensive_analytics(self, analytics_engine, mock_redis):
        """Test getting comprehensive analytics."""
        tenant_id = "tenant_123"
        time_window = "24h"
        
        with patch.object(analytics_engine, 'get_kpi_metrics') as mock_kpi, \
             patch.object(analytics_engine, '_get_usage_trends') as mock_trends, \
             patch.object(analytics_engine, '_get_performance_insights') as mock_insights, \
             patch.object(analytics_engine, '_get_cost_analysis') as mock_cost, \
             patch.object(analytics_engine, '_get_reliability_metrics') as mock_reliability:
            
            # Mock KPI metrics
            mock_kpi_metrics = KPIMetrics(
                tenant_id=tenant_id,
                time_window=time_window,
                success_rate=0.96,
                p50_latency=50.0,
                p95_latency=200.0,
                p99_latency=400.0,
                tokens_in=100,
                tokens_out=150,
                cost_per_run=0.01,
                total_cost=100.0,
                tier_distribution={"A": 50, "B": 30, "C": 20},
                router_misroute_rate=0.02,
                expected_vs_actual_cost=1.0,
                expected_vs_actual_latency=1.0,
                total_requests=1000,
                successful_requests=960,
                failed_requests=40,
                avg_tokens_per_request=125.0,
                cost_efficiency=1.0,
                latency_efficiency=1.0,
                data_source=DataSource.CLICKHOUSE.value,
                timestamp=datetime.utcnow(),
            )
            mock_kpi.return_value = mock_kpi_metrics
            
            # Mock other analytics components
            mock_trends.return_value = {
                "requests_per_hour": [100, 120, 110, 130],
                "growth_rate": 0.15,
            }
            mock_insights.return_value = {
                "latency_improvement": 0.12,
                "cost_optimization": 0.08,
                "reliability_score": 0.97,
            }
            mock_cost.return_value = {
                "total_cost": 100.0,
                "cost_breakdown": {"tier_a": 50.0, "tier_b": 30.0, "tier_c": 20.0},
            }
            mock_reliability.return_value = {
                "uptime": 0.999,
                "error_rate": 0.01,
                "mean_time_to_recovery": 120,
            }
            
            result = await analytics_engine.get_comprehensive_analytics(tenant_id, time_window)
            
            assert isinstance(result, TenantAnalytics)
            assert result.tenant_id == tenant_id
            assert result.time_window == time_window
            assert result.kpi_metrics.success_rate == 0.96
            assert "requests_per_hour" in result.usage_trends
            assert "latency_improvement" in result.performance_insights
            assert "total_cost" in result.cost_analysis
            assert "uptime" in result.reliability_metrics

    @pytest.mark.asyncio
    async def test_get_clickhouse_metrics(self, analytics_engine):
        """Test getting metrics from ClickHouse warehouse."""
        tenant_id = "tenant_123"
        time_window = "1h"
        
        result = await analytics_engine._get_clickhouse_metrics(tenant_id, time_window)
        
        assert isinstance(result, KPIMetrics)
        assert result.tenant_id == tenant_id
        assert result.time_window == time_window
        assert result.data_source == DataSource.CLICKHOUSE.value
        assert result.success_rate > 0.9  # Enhanced metrics should be better

    @pytest.mark.asyncio
    async def test_get_bigquery_metrics(self, analytics_engine):
        """Test getting metrics from BigQuery warehouse."""
        tenant_id = "tenant_123"
        time_window = "7d"
        
        result = await analytics_engine._get_bigquery_metrics(tenant_id, time_window)
        
        assert isinstance(result, KPIMetrics)
        assert result.tenant_id == tenant_id
        assert result.time_window == time_window
        assert result.data_source == DataSource.BIGQUERY.value

    @pytest.mark.asyncio
    async def test_get_postgres_metrics(self, analytics_engine):
        """Test getting metrics from Postgres read-replica."""
        tenant_id = "tenant_123"
        time_window = "24h"
        
        result = await analytics_engine._get_postgres_metrics(tenant_id, time_window)
        
        assert isinstance(result, KPIMetrics)
        assert result.tenant_id == tenant_id
        assert result.time_window == time_window
        assert result.data_source == analytics_engine.data_source.value

    @pytest.mark.asyncio
    async def test_cache_metrics(self, analytics_engine, mock_redis):
        """Test caching metrics in Redis."""
        tenant_id = "tenant_123"
        time_window = "1h"
        cache_key = f"kpi_metrics:{tenant_id}:{time_window}"
        
        metrics = KPIMetrics(
            tenant_id=tenant_id,
            time_window=time_window,
            success_rate=0.95,
            p50_latency=50.0,
            p95_latency=200.0,
            p99_latency=400.0,
            tokens_in=100,
            tokens_out=150,
            cost_per_run=0.01,
            total_cost=100.0,
            tier_distribution={"A": 50, "B": 30, "C": 20},
            router_misroute_rate=0.02,
            expected_vs_actual_cost=1.0,
            expected_vs_actual_latency=1.0,
            total_requests=1000,
            successful_requests=950,
            failed_requests=50,
            avg_tokens_per_request=125.0,
            cost_efficiency=1.0,
            latency_efficiency=1.0,
            data_source=DataSource.CLICKHOUSE.value,
            timestamp=datetime.utcnow(),
        )
        
        await analytics_engine._cache_metrics(cache_key, metrics)
        
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == cache_key
        assert call_args[0][1] == analytics_engine.cache_ttl
        assert isinstance(call_args[0][2], str)  # JSON string

    @pytest.mark.asyncio
    async def test_get_cached_metrics(self, analytics_engine, mock_redis):
        """Test retrieving cached metrics from Redis."""
        cache_key = "kpi_metrics:tenant_123:1h"
        
        cached_data = {
            "tenant_id": "tenant_123",
            "time_window": "1h",
            "success_rate": 0.95,
            "p50_latency": 50.0,
            "p95_latency": 200.0,
            "p99_latency": 400.0,
            "tokens_in": 100,
            "tokens_out": 150,
            "cost_per_run": 0.01,
            "total_cost": 100.0,
            "tier_distribution": {"A": 50, "B": 30, "C": 20},
            "router_misroute_rate": 0.02,
            "expected_vs_actual_cost": 1.0,
            "expected_vs_actual_latency": 1.0,
            "total_requests": 1000,
            "successful_requests": 950,
            "failed_requests": 50,
            "avg_tokens_per_request": 125.0,
            "cost_efficiency": 1.0,
            "latency_efficiency": 1.0,
            "data_source": "clickhouse",
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        mock_redis.get.return_value = json.dumps(cached_data)
        
        result = await analytics_engine._get_cached_metrics(cache_key)
        
        assert isinstance(result, KPIMetrics)
        assert result.tenant_id == "tenant_123"
        assert result.success_rate == 0.95

    @pytest.mark.asyncio
    async def test_get_usage_trends(self, analytics_engine):
        """Test getting usage trends."""
        tenant_id = "tenant_123"
        time_window = "24h"
        
        result = await analytics_engine._get_usage_trends(tenant_id, time_window)
        
        assert isinstance(result, dict)
        assert "requests_per_hour" in result
        assert "tokens_per_hour" in result
        assert "cost_per_hour" in result
        assert "growth_rate" in result
        assert len(result["requests_per_hour"]) == 7

    @pytest.mark.asyncio
    async def test_get_performance_insights(self, analytics_engine):
        """Test getting performance insights."""
        tenant_id = "tenant_123"
        time_window = "7d"
        
        result = await analytics_engine._get_performance_insights(tenant_id, time_window)
        
        assert isinstance(result, dict)
        assert "latency_improvement" in result
        assert "cost_optimization" in result
        assert "reliability_score" in result
        assert "bottlenecks" in result
        assert "recommendations" in result
        assert "slo_compliance" in result

    @pytest.mark.asyncio
    async def test_get_cost_analysis(self, analytics_engine):
        """Test getting cost analysis."""
        tenant_id = "tenant_123"
        time_window = "30d"
        
        result = await analytics_engine._get_cost_analysis(tenant_id, time_window)
        
        assert isinstance(result, dict)
        assert "total_cost" in result
        assert "cost_breakdown" in result
        assert "cost_per_request" in result
        assert "cost_efficiency" in result
        assert "savings_opportunities" in result
        assert "budget_utilization" in result

    @pytest.mark.asyncio
    async def test_get_reliability_metrics(self, analytics_engine):
        """Test getting reliability metrics."""
        tenant_id = "tenant_123"
        time_window = "1h"
        
        result = await analytics_engine._get_reliability_metrics(tenant_id, time_window)
        
        assert isinstance(result, dict)
        assert "uptime" in result
        assert "error_rate" in result
        assert "mean_time_to_recovery" in result
        assert "circuit_breaker_trips" in result
        assert "retry_success_rate" in result
        assert "escalation_rate" in result

    @pytest.mark.asyncio
    async def test_warehouse_connection_initialization(self, mock_redis):
        """Test warehouse connection initialization."""
        # Test ClickHouse initialization
        engine = AnalyticsEngine(
            redis_client=mock_redis,
            data_source=DataSource.CLICKHOUSE,
            warehouse_config={"host": "localhost", "port": 9000},
        )
        
        assert engine.warehouse_client is not None
        assert engine.warehouse_client["type"] == "clickhouse"
        
        # Test BigQuery initialization
        engine = AnalyticsEngine(
            redis_client=mock_redis,
            data_source=DataSource.BIGQUERY,
            warehouse_config={"project_id": "test-project"},
        )
        
        assert engine.warehouse_client is not None
        assert engine.warehouse_client["type"] == "bigquery"

    @pytest.mark.asyncio
    async def test_error_handling_fallback_to_default(self, analytics_engine, mock_redis):
        """Test error handling with fallback to default metrics."""
        tenant_id = "tenant_123"
        time_window = "1h"
        
        # Mock Redis error
        mock_redis.get.side_effect = Exception("Redis connection failed")
        
        with patch.object(analytics_engine, '_get_clickhouse_metrics') as mock_warehouse:
            mock_warehouse.side_effect = Exception("Warehouse connection failed")
            
            result = await analytics_engine.get_kpi_metrics(tenant_id, time_window)
            
            # Should return default metrics
            assert isinstance(result, KPIMetrics)
            assert result.tenant_id == tenant_id
            assert result.time_window == time_window
            assert result.data_source == analytics_engine.data_source.value

    @pytest.mark.asyncio
    async def test_comprehensive_analytics_error_handling(self, analytics_engine, mock_redis):
        """Test comprehensive analytics error handling."""
        tenant_id = "tenant_123"
        time_window = "1h"
        
        # Mock all methods to raise exceptions
        with patch.object(analytics_engine, 'get_kpi_metrics') as mock_kpi, \
             patch.object(analytics_engine, '_get_usage_trends') as mock_trends, \
             patch.object(analytics_engine, '_get_performance_insights') as mock_insights, \
             patch.object(analytics_engine, '_get_cost_analysis') as mock_cost, \
             patch.object(analytics_engine, '_get_reliability_metrics') as mock_reliability:
            
            mock_kpi.side_effect = Exception("KPI metrics failed")
            mock_trends.side_effect = Exception("Trends failed")
            mock_insights.side_effect = Exception("Insights failed")
            mock_cost.side_effect = Exception("Cost analysis failed")
            mock_reliability.side_effect = Exception("Reliability metrics failed")
            
            result = await analytics_engine.get_comprehensive_analytics(tenant_id, time_window)
            
            # Should return default analytics
            assert isinstance(result, TenantAnalytics)
            assert result.tenant_id == tenant_id
            assert result.time_window == time_window
            assert result.data_source == analytics_engine.data_source.value

    @pytest.mark.asyncio
    async def test_data_source_enum_values(self):
        """Test DataSource enum values."""
        assert DataSource.POSTGRES_READ_REPLICA.value == "postgres_read_replica"
        assert DataSource.CLICKHOUSE.value == "clickhouse"
        assert DataSource.BIGQUERY.value == "bigquery"
        assert DataSource.REDIS_CACHE.value == "redis_cache"

    @pytest.mark.asyncio
    async def test_time_window_enum_values(self):
        """Test TimeWindow enum values."""
        assert TimeWindow.LAST_HOUR.value == "1h"
        assert TimeWindow.LAST_DAY.value == "24h"
        assert TimeWindow.LAST_WEEK.value == "7d"
        assert TimeWindow.LAST_MONTH.value == "30d"

    @pytest.mark.asyncio
    async def test_kpi_metrics_dataclass(self):
        """Test KPIMetrics dataclass structure."""
        metrics = KPIMetrics(
            tenant_id="tenant_123",
            time_window="1h",
            success_rate=0.95,
            p50_latency=50.0,
            p95_latency=200.0,
            p99_latency=400.0,
            tokens_in=100,
            tokens_out=150,
            cost_per_run=0.01,
            total_cost=100.0,
            tier_distribution={"A": 50, "B": 30, "C": 20},
            router_misroute_rate=0.02,
            expected_vs_actual_cost=1.0,
            expected_vs_actual_latency=1.0,
            total_requests=1000,
            successful_requests=950,
            failed_requests=50,
            avg_tokens_per_request=125.0,
            cost_efficiency=1.0,
            latency_efficiency=1.0,
            data_source="clickhouse",
            timestamp=datetime.utcnow(),
        )
        
        # Test conversion to dict
        metrics_dict = asdict(metrics)
        assert metrics_dict["tenant_id"] == "tenant_123"
        assert metrics_dict["success_rate"] == 0.95
        assert metrics_dict["tier_distribution"] == {"A": 50, "B": 30, "C": 20}
