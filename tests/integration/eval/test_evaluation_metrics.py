"""Test evaluation metrics functionality."""

import pytest
import time
from unittest.mock import Mock, AsyncMock

from eval.evaluation_metrics import (
    EvaluationMetrics,
    MetricResult,
    MetricType,
)


class TestMetricResult:
    """Test MetricResult dataclass."""

    def test_metric_result_creation(self):
        """Test MetricResult creation."""
        result = MetricResult(
            metric_name="test_metric",
            metric_type=MetricType.LATENCY,
            value=1.5,
            unit="seconds",
            timestamp=time.time(),
            metadata={"test": True}
        )
        
        assert result.metric_name == "test_metric"
        assert result.metric_type == MetricType.LATENCY
        assert result.value == 1.5
        assert result.unit == "seconds"
        assert result.metadata == {"test": True}

    def test_metric_result_defaults(self):
        """Test MetricResult with default values."""
        result = MetricResult(
            metric_name="test_metric",
            metric_type=MetricType.THROUGHPUT,
            value=100.0,
            unit="ops/sec",
            timestamp=time.time()
        )
        
        assert result.metadata is None


class TestEvaluationMetrics:
    """Test EvaluationMetrics functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis_client = Mock()
        redis_client.hset = AsyncMock()
        redis_client.expire = AsyncMock()
        redis_client.keys = AsyncMock()
        redis_client.hgetall = AsyncMock()
        return redis_client

    @pytest.fixture
    def metrics_calculator(self, mock_redis):
        """Create EvaluationMetrics instance."""
        return EvaluationMetrics(mock_redis)

    @pytest.mark.asyncio
    async def test_calculate_latency_metrics_success(self, metrics_calculator):
        """Test successful latency metrics calculation."""
        execution_times = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        
        result = await metrics_calculator.calculate_latency_metrics(execution_times, "test_latency")
        
        assert result.metric_name == "test_latency"
        assert result.metric_type == MetricType.LATENCY
        assert result.value == 0.55  # Average
        assert result.unit == "seconds"
        
        # Check metadata
        assert result.metadata["min_latency"] == 0.1
        assert result.metadata["max_latency"] == 1.0
        assert result.metadata["p50_latency"] == 0.5  # 50th percentile
        assert result.metadata["p95_latency"] == 0.95  # 95th percentile
        assert result.metadata["p99_latency"] == 0.99  # 99th percentile
        assert result.metadata["sample_count"] == 10

    @pytest.mark.asyncio
    async def test_calculate_latency_metrics_empty(self, metrics_calculator):
        """Test latency metrics calculation with empty data."""
        result = await metrics_calculator.calculate_latency_metrics([], "empty_latency")
        
        assert result.metric_name == "empty_latency"
        assert result.metric_type == MetricType.LATENCY
        assert result.value == 0.0
        assert result.unit == "seconds"
        assert result.metadata is None

    @pytest.mark.asyncio
    async def test_calculate_latency_metrics_error(self, metrics_calculator):
        """Test latency metrics calculation with error."""
        # This test would need to mock an error condition
        # For now, we'll test with None input which should be handled gracefully
        result = await metrics_calculator.calculate_latency_metrics(None, "error_latency")
        
        assert result.metric_name == "error_latency"
        assert result.value == 0.0
        assert "error" in result.metadata

    @pytest.mark.asyncio
    async def test_calculate_throughput_metrics_success(self, metrics_calculator):
        """Test successful throughput metrics calculation."""
        start_time = 1000.0
        end_time = 1010.0  # 10 seconds
        operation_count = 100
        
        result = await metrics_calculator.calculate_throughput_metrics(
            start_time, end_time, operation_count, "test_throughput"
        )
        
        assert result.metric_name == "test_throughput"
        assert result.metric_type == MetricType.THROUGHPUT
        assert result.value == 10.0  # 100 operations / 10 seconds
        assert result.unit == "operations/second"
        
        # Check metadata
        assert result.metadata["operation_count"] == 100
        assert result.metadata["duration"] == 10.0
        assert result.metadata["start_time"] == 1000.0
        assert result.metadata["end_time"] == 1010.0

    @pytest.mark.asyncio
    async def test_calculate_throughput_metrics_zero_duration(self, metrics_calculator):
        """Test throughput metrics calculation with zero duration."""
        result = await metrics_calculator.calculate_throughput_metrics(
            1000.0, 1000.0, 100, "zero_duration_throughput"
        )
        
        assert result.value == 0.0
        assert result.metadata["duration"] == 0.0

    @pytest.mark.asyncio
    async def test_calculate_throughput_metrics_negative_duration(self, metrics_calculator):
        """Test throughput metrics calculation with negative duration."""
        result = await metrics_calculator.calculate_throughput_metrics(
            1010.0, 1000.0, 100, "negative_duration_throughput"
        )
        
        assert result.value == 0.0

    @pytest.mark.asyncio
    async def test_calculate_success_rate_metrics_success(self, metrics_calculator):
        """Test successful success rate metrics calculation."""
        successful_operations = 80
        total_operations = 100
        
        result = await metrics_calculator.calculate_success_rate_metrics(
            successful_operations, total_operations, "test_success_rate"
        )
        
        assert result.metric_name == "test_success_rate"
        assert result.metric_type == MetricType.SUCCESS_RATE
        assert result.value == 80.0  # 80%
        assert result.unit == "percentage"
        
        # Check metadata
        assert result.metadata["successful_operations"] == 80
        assert result.metadata["total_operations"] == 100
        assert result.metadata["failed_operations"] == 20

    @pytest.mark.asyncio
    async def test_calculate_success_rate_metrics_zero_operations(self, metrics_calculator):
        """Test success rate metrics calculation with zero operations."""
        result = await metrics_calculator.calculate_success_rate_metrics(
            0, 0, "zero_operations_success_rate"
        )
        
        assert result.value == 0.0

    @pytest.mark.asyncio
    async def test_calculate_success_rate_metrics_perfect_success(self, metrics_calculator):
        """Test success rate metrics calculation with perfect success."""
        result = await metrics_calculator.calculate_success_rate_metrics(
            100, 100, "perfect_success_rate"
        )
        
        assert result.value == 100.0
        assert result.metadata["failed_operations"] == 0

    @pytest.mark.asyncio
    async def test_calculate_error_rate_metrics_success(self, metrics_calculator):
        """Test successful error rate metrics calculation."""
        error_operations = 20
        total_operations = 100
        
        result = await metrics_calculator.calculate_error_rate_metrics(
            error_operations, total_operations, "test_error_rate"
        )
        
        assert result.metric_name == "test_error_rate"
        assert result.metric_type == MetricType.ERROR_RATE
        assert result.value == 20.0  # 20%
        assert result.unit == "percentage"
        
        # Check metadata
        assert result.metadata["error_operations"] == 20
        assert result.metadata["total_operations"] == 100
        assert result.metadata["successful_operations"] == 80

    @pytest.mark.asyncio
    async def test_calculate_error_rate_metrics_no_errors(self, metrics_calculator):
        """Test error rate metrics calculation with no errors."""
        result = await metrics_calculator.calculate_error_rate_metrics(
            0, 100, "no_errors_rate"
        )
        
        assert result.value == 0.0
        assert result.metadata["successful_operations"] == 100

    @pytest.mark.asyncio
    async def test_calculate_resource_usage_metrics_success(self, metrics_calculator):
        """Test successful resource usage metrics calculation."""
        cpu_usage = 70.0
        memory_usage = 60.0
        disk_usage = 50.0
        
        result = await metrics_calculator.calculate_resource_usage_metrics(
            cpu_usage, memory_usage, disk_usage, "test_resource_usage"
        )
        
        assert result.metric_name == "test_resource_usage"
        assert result.metric_type == MetricType.RESOURCE_USAGE
        assert result.value == 60.0  # (70 + 60 + 50) / 3
        assert result.unit == "percentage"
        
        # Check metadata
        assert result.metadata["cpu_usage"] == 70.0
        assert result.metadata["memory_usage"] == 60.0
        assert result.metadata["disk_usage"] == 50.0

    @pytest.mark.asyncio
    async def test_calculate_resource_usage_metrics_high_usage(self, metrics_calculator):
        """Test resource usage metrics calculation with high usage."""
        result = await metrics_calculator.calculate_resource_usage_metrics(
            90.0, 85.0, 80.0, "high_resource_usage"
        )
        
        assert result.value == 85.0  # (90 + 85 + 80) / 3

    @pytest.mark.asyncio
    async def test_calculate_quality_metrics_success(self, metrics_calculator):
        """Test successful quality metrics calculation."""
        quality_scores = [0.7, 0.8, 0.9, 0.85, 0.75, 0.95]
        
        result = await metrics_calculator.calculate_quality_metrics(
            quality_scores, "test_quality"
        )
        
        assert result.metric_name == "test_quality"
        assert result.metric_type == MetricType.QUALITY
        assert result.value == 0.825  # Average
        assert result.unit == "score"
        
        # Check metadata
        assert result.metadata["min_quality"] == 0.7
        assert result.metadata["max_quality"] == 0.95
        assert result.metadata["sample_count"] == 6

    @pytest.mark.asyncio
    async def test_calculate_quality_metrics_empty(self, metrics_calculator):
        """Test quality metrics calculation with empty data."""
        result = await metrics_calculator.calculate_quality_metrics(
            [], "empty_quality"
        )
        
        assert result.value == 0.0
        assert result.metadata is None

    @pytest.mark.asyncio
    async def test_store_metric_result(self, metrics_calculator):
        """Test storing metric result in Redis."""
        result = MetricResult(
            metric_name="test_metric",
            metric_type=MetricType.LATENCY,
            value=1.5,
            unit="seconds",
            timestamp=time.time(),
            metadata={"test": True}
        )
        
        await metrics_calculator.store_metric_result(result, "tenant_123")
        
        # Verify Redis storage was called
        metrics_calculator.redis.hset.assert_called_once()
        metrics_calculator.redis.expire.assert_called_once()
        
        call_args = metrics_calculator.redis.hset.call_args
        assert call_args[0][0].startswith("metric_result:tenant_123:test_metric:")
        
        # Verify TTL
        expire_call = metrics_calculator.redis.expire.call_args
        assert expire_call[0][1] == 86400 * 7  # 7 days

    @pytest.mark.asyncio
    async def test_store_metric_result_error(self, metrics_calculator):
        """Test storing metric result with Redis error."""
        metrics_calculator.redis.hset.side_effect = Exception("Redis error")
        
        result = MetricResult(
            metric_name="test_metric",
            metric_type=MetricType.LATENCY,
            value=1.5,
            unit="seconds",
            timestamp=time.time()
        )
        
        # Should not raise exception
        await metrics_calculator.store_metric_result(result, "tenant_123")

    @pytest.mark.asyncio
    async def test_get_metric_history_success(self, metrics_calculator):
        """Test getting metric history successfully."""
        # Mock Redis keys
        mock_keys = [b"metric_result:tenant_123:test_metric:1234567890"]
        metrics_calculator.redis.keys.return_value = mock_keys
        
        # Mock Redis data
        metric_data = {
            b"metric_name": b"test_metric",
            b"metric_type": b"latency",
            b"value": b"1.5",
            b"unit": b"seconds",
            b"timestamp": b"1234567890.0",
            b"metadata": b"{}"
        }
        metrics_calculator.redis.hgetall.return_value = metric_data
        
        history = await metrics_calculator.get_metric_history("tenant_123", "test_metric", 24)
        
        assert len(history) == 1
        result = history[0]
        assert result.metric_name == "test_metric"
        assert result.metric_type == MetricType.LATENCY
        assert result.value == 1.5
        assert result.unit == "seconds"

    @pytest.mark.asyncio
    async def test_get_metric_history_no_data(self, metrics_calculator):
        """Test getting metric history with no data."""
        metrics_calculator.redis.keys.return_value = []
        
        history = await metrics_calculator.get_metric_history("tenant_123", "test_metric", 24)
        
        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_get_metric_history_error(self, metrics_calculator):
        """Test getting metric history with Redis error."""
        metrics_calculator.redis.keys.side_effect = Exception("Redis error")
        
        history = await metrics_calculator.get_metric_history("tenant_123", "test_metric", 24)
        
        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_get_metric_summary_success(self, metrics_calculator):
        """Test getting metric summary successfully."""
        # Mock metric history
        mock_history = [
            MetricResult(
                metric_name="test_metric",
                metric_type=MetricType.LATENCY,
                value=1.0,
                unit="seconds",
                timestamp=time.time() - 3600,
                metadata={}
            ),
            MetricResult(
                metric_name="test_metric",
                metric_type=MetricType.LATENCY,
                value=2.0,
                unit="seconds",
                timestamp=time.time() - 1800,
                metadata={}
            ),
            MetricResult(
                metric_name="test_metric",
                metric_type=MetricType.LATENCY,
                value=3.0,
                unit="seconds",
                timestamp=time.time(),
                metadata={}
            )
        ]
        
        with patch.object(metrics_calculator, 'get_metric_history') as mock_get_history:
            mock_get_history.return_value = mock_history
            
            summary = await metrics_calculator.get_metric_summary("tenant_123", "test_metric")
        
        assert summary["metric_name"] == "test_metric"
        assert summary["current_value"] == 3.0
        assert summary["average_value"] == 2.0
        assert summary["min_value"] == 1.0
        assert summary["max_value"] == 3.0
        assert summary["sample_count"] == 3
        assert summary["time_range_hours"] == 24

    @pytest.mark.asyncio
    async def test_get_metric_summary_no_data(self, metrics_calculator):
        """Test getting metric summary with no data."""
        with patch.object(metrics_calculator, 'get_metric_history') as mock_get_history:
            mock_get_history.return_value = []
            
            summary = await metrics_calculator.get_metric_summary("tenant_123", "test_metric")
        
        assert "error" in summary
        assert summary["error"] == "No data available"

    @pytest.mark.asyncio
    async def test_get_metric_summary_error(self, metrics_calculator):
        """Test getting metric summary with error."""
        with patch.object(metrics_calculator, 'get_metric_history') as mock_get_history:
            mock_get_history.side_effect = Exception("History error")
            
            summary = await metrics_calculator.get_metric_summary("tenant_123", "test_metric")
        
        assert "error" in summary
        assert summary["error"] == "History error"

    def test_metric_type_enum_values(self):
        """Test MetricType enum values."""
        assert MetricType.LATENCY.value == "latency"
        assert MetricType.THROUGHPUT.value == "throughput"
        assert MetricType.SUCCESS_RATE.value == "success_rate"
        assert MetricType.ERROR_RATE.value == "error_rate"
        assert MetricType.RESOURCE_USAGE.value == "resource_usage"
        assert MetricType.QUALITY.value == "quality"

    @pytest.mark.asyncio
    async def test_metrics_cache_functionality(self, metrics_calculator):
        """Test metrics cache functionality."""
        # The current implementation doesn't use caching, but we can test the cache attribute exists
        assert hasattr(metrics_calculator, 'metrics_cache')
        assert metrics_calculator.metrics_cache == {}

    @pytest.mark.asyncio
    async def test_multiple_metric_types_integration(self, metrics_calculator):
        """Test integration of multiple metric types."""
        # Calculate different types of metrics
        latency_result = await metrics_calculator.calculate_latency_metrics([0.1, 0.2, 0.3])
        throughput_result = await metrics_calculator.calculate_throughput_metrics(0, 10, 100)
        success_result = await metrics_calculator.calculate_success_rate_metrics(80, 100)
        error_result = await metrics_calculator.calculate_error_rate_metrics(20, 100)
        resource_result = await metrics_calculator.calculate_resource_usage_metrics(70, 60, 50)
        quality_result = await metrics_calculator.calculate_quality_metrics([0.8, 0.9, 0.7])
        
        # Verify all results have correct types
        assert latency_result.metric_type == MetricType.LATENCY
        assert throughput_result.metric_type == MetricType.THROUGHPUT
        assert success_result.metric_type == MetricType.SUCCESS_RATE
        assert error_result.metric_type == MetricType.ERROR_RATE
        assert resource_result.metric_type == MetricType.RESOURCE_USAGE
        assert quality_result.metric_type == MetricType.QUALITY
        
        # Verify all results have valid values
        assert latency_result.value > 0
        assert throughput_result.value > 0
        assert 0 <= success_result.value <= 100
        assert 0 <= error_result.value <= 100
        assert 0 <= resource_result.value <= 100
        assert 0 <= quality_result.value <= 1

    @pytest.mark.asyncio
    async def test_metric_result_with_complex_metadata(self, metrics_calculator):
        """Test metric result with complex metadata."""
        complex_metadata = {
            "percentiles": {"p50": 0.5, "p95": 0.95, "p99": 0.99},
            "distribution": {"low": 10, "medium": 50, "high": 40},
            "tags": ["production", "critical"]
        }
        
        result = MetricResult(
            metric_name="complex_metric",
            metric_type=MetricType.QUALITY,
            value=0.85,
            unit="score",
            timestamp=time.time(),
            metadata=complex_metadata
        )
        
        await metrics_calculator.store_metric_result(result, "tenant_123")
        
        # Verify Redis storage was called
        metrics_calculator.redis.hset.assert_called_once()
        
        # Check that metadata was stored as string
        call_args = metrics_calculator.redis.hset.call_args
        stored_data = call_args[0][1]
        assert "percentiles" in stored_data["metadata"]
        assert "distribution" in stored_data["metadata"]
        assert "tags" in stored_data["metadata"]
