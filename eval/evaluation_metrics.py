"""Evaluation metrics for episode replay and testing."""

import asyncio
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import structlog
import redis.asyncio as redis

logger = structlog.get_logger(__name__)


class MetricType(Enum):
    """Metric types."""

    LATENCY = "latency"
    THROUGHPUT = "throughput"
    SUCCESS_RATE = "success_rate"
    ERROR_RATE = "error_rate"
    RESOURCE_USAGE = "resource_usage"
    QUALITY = "quality"


@dataclass
class MetricResult:
    """Metric evaluation result."""

    metric_name: str
    metric_type: MetricType
    value: float
    unit: str
    timestamp: float
    metadata: Dict[str, Any] = None


class EvaluationMetrics:
    """Evaluation metrics calculator."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.metrics_cache = {}

    async def calculate_latency_metrics(
        self, execution_times: List[float], metric_name: str = "latency"
    ) -> MetricResult:
        """Calculate latency metrics."""
        try:
            if not execution_times:
                return MetricResult(
                    metric_name=metric_name,
                    metric_type=MetricType.LATENCY,
                    value=0.0,
                    unit="seconds",
                    timestamp=time.time(),
                )

            avg_latency = sum(execution_times) / len(execution_times)
            min_latency = min(execution_times)
            max_latency = max(execution_times)

            # Calculate percentiles
            sorted_times = sorted(execution_times)
            p50 = sorted_times[int(len(sorted_times) * 0.5)]
            p95 = sorted_times[int(len(sorted_times) * 0.95)]
            p99 = sorted_times[int(len(sorted_times) * 0.99)]

            return MetricResult(
                metric_name=metric_name,
                metric_type=MetricType.LATENCY,
                value=avg_latency,
                unit="seconds",
                timestamp=time.time(),
                metadata={
                    "min_latency": min_latency,
                    "max_latency": max_latency,
                    "p50_latency": p50,
                    "p95_latency": p95,
                    "p99_latency": p99,
                    "sample_count": len(execution_times),
                },
            )

        except Exception as e:
            logger.error("Failed to calculate latency metrics", error=str(e))
            return MetricResult(
                metric_name=metric_name,
                metric_type=MetricType.LATENCY,
                value=0.0,
                unit="seconds",
                timestamp=time.time(),
                metadata={"error": str(e)},
            )

    async def calculate_throughput_metrics(
        self,
        start_time: float,
        end_time: float,
        operation_count: int,
        metric_name: str = "throughput",
    ) -> MetricResult:
        """Calculate throughput metrics."""
        try:
            duration = end_time - start_time
            if duration <= 0:
                return MetricResult(
                    metric_name=metric_name,
                    metric_type=MetricType.THROUGHPUT,
                    value=0.0,
                    unit="operations/second",
                    timestamp=time.time(),
                )

            throughput = operation_count / duration

            return MetricResult(
                metric_name=metric_name,
                metric_type=MetricType.THROUGHPUT,
                value=throughput,
                unit="operations/second",
                timestamp=time.time(),
                metadata={
                    "operation_count": operation_count,
                    "duration": duration,
                    "start_time": start_time,
                    "end_time": end_time,
                },
            )

        except Exception as e:
            logger.error("Failed to calculate throughput metrics", error=str(e))
            return MetricResult(
                metric_name=metric_name,
                metric_type=MetricType.THROUGHPUT,
                value=0.0,
                unit="operations/second",
                timestamp=time.time(),
                metadata={"error": str(e)},
            )

    async def calculate_success_rate_metrics(
        self,
        successful_operations: int,
        total_operations: int,
        metric_name: str = "success_rate",
    ) -> MetricResult:
        """Calculate success rate metrics."""
        try:
            if total_operations == 0:
                return MetricResult(
                    metric_name=metric_name,
                    metric_type=MetricType.SUCCESS_RATE,
                    value=0.0,
                    unit="percentage",
                    timestamp=time.time(),
                )

            success_rate = (successful_operations / total_operations) * 100

            return MetricResult(
                metric_name=metric_name,
                metric_type=MetricType.SUCCESS_RATE,
                value=success_rate,
                unit="percentage",
                timestamp=time.time(),
                metadata={
                    "successful_operations": successful_operations,
                    "total_operations": total_operations,
                    "failed_operations": total_operations - successful_operations,
                },
            )

        except Exception as e:
            logger.error("Failed to calculate success rate metrics", error=str(e))
            return MetricResult(
                metric_name=metric_name,
                metric_type=MetricType.SUCCESS_RATE,
                value=0.0,
                unit="percentage",
                timestamp=time.time(),
                metadata={"error": str(e)},
            )

    async def calculate_error_rate_metrics(
        self,
        error_operations: int,
        total_operations: int,
        metric_name: str = "error_rate",
    ) -> MetricResult:
        """Calculate error rate metrics."""
        try:
            if total_operations == 0:
                return MetricResult(
                    metric_name=metric_name,
                    metric_type=MetricType.ERROR_RATE,
                    value=0.0,
                    unit="percentage",
                    timestamp=time.time(),
                )

            error_rate = (error_operations / total_operations) * 100

            return MetricResult(
                metric_name=metric_name,
                metric_type=MetricType.ERROR_RATE,
                value=error_rate,
                unit="percentage",
                timestamp=time.time(),
                metadata={
                    "error_operations": error_operations,
                    "total_operations": total_operations,
                    "successful_operations": total_operations - error_operations,
                },
            )

        except Exception as e:
            logger.error("Failed to calculate error rate metrics", error=str(e))
            return MetricResult(
                metric_name=metric_name,
                metric_type=MetricType.ERROR_RATE,
                value=0.0,
                unit="percentage",
                timestamp=time.time(),
                metadata={"error": str(e)},
            )

    async def calculate_resource_usage_metrics(
        self,
        cpu_usage: float,
        memory_usage: float,
        disk_usage: float,
        metric_name: str = "resource_usage",
    ) -> MetricResult:
        """Calculate resource usage metrics."""
        try:
            # Calculate overall resource usage score
            resource_score = (cpu_usage + memory_usage + disk_usage) / 3

            return MetricResult(
                metric_name=metric_name,
                metric_type=MetricType.RESOURCE_USAGE,
                value=resource_score,
                unit="percentage",
                timestamp=time.time(),
                metadata={
                    "cpu_usage": cpu_usage,
                    "memory_usage": memory_usage,
                    "disk_usage": disk_usage,
                },
            )

        except Exception as e:
            logger.error("Failed to calculate resource usage metrics", error=str(e))
            return MetricResult(
                metric_name=metric_name,
                metric_type=MetricType.RESOURCE_USAGE,
                value=0.0,
                unit="percentage",
                timestamp=time.time(),
                metadata={"error": str(e)},
            )

    async def calculate_quality_metrics(
        self, response_quality_scores: List[float], metric_name: str = "quality"
    ) -> MetricResult:
        """Calculate quality metrics."""
        try:
            if not response_quality_scores:
                return MetricResult(
                    metric_name=metric_name,
                    metric_type=MetricType.QUALITY,
                    value=0.0,
                    unit="score",
                    timestamp=time.time(),
                )

            avg_quality = sum(response_quality_scores) / len(response_quality_scores)
            min_quality = min(response_quality_scores)
            max_quality = max(response_quality_scores)

            return MetricResult(
                metric_name=metric_name,
                metric_type=MetricType.QUALITY,
                value=avg_quality,
                unit="score",
                timestamp=time.time(),
                metadata={
                    "min_quality": min_quality,
                    "max_quality": max_quality,
                    "sample_count": len(response_quality_scores),
                },
            )

        except Exception as e:
            logger.error("Failed to calculate quality metrics", error=str(e))
            return MetricResult(
                metric_name=metric_name,
                metric_type=MetricType.QUALITY,
                value=0.0,
                unit="score",
                timestamp=time.time(),
                metadata={"error": str(e)},
            )

    async def store_metric_result(self, result: MetricResult, tenant_id: str) -> None:
        """Store metric result in Redis."""
        try:
            metric_key = f"metric_result:{tenant_id}:{result.metric_name}:{int(result.timestamp)}"

            metric_data = {
                "metric_name": result.metric_name,
                "metric_type": result.metric_type.value,
                "value": result.value,
                "unit": result.unit,
                "timestamp": result.timestamp,
                "metadata": str(result.metadata) if result.metadata else "{}",
            }

            await self.redis.hset(metric_key, mapping=metric_data)
            await self.redis.expire(metric_key, 86400 * 7)  # 7 days TTL

        except Exception as e:
            logger.error("Failed to store metric result", error=str(e))

    async def get_metric_history(
        self, tenant_id: str, metric_name: str, hours: int = 24
    ) -> List[MetricResult]:
        """Get metric history for a time period."""
        try:
            end_time = int(time.time())
            start_time = end_time - (hours * 3600)

            history = []

            pattern = f"metric_result:{tenant_id}:{metric_name}:*"
            keys = await self.redis.keys(pattern)

            for key in keys:
                try:
                    timestamp_str = key.decode().split(":")[-1]
                    timestamp = int(timestamp_str)

                    if start_time <= timestamp <= end_time:
                        metric_data = await self.redis.hgetall(key)
                        if metric_data:
                            history.append(
                                MetricResult(
                                    metric_name=metric_data["metric_name"],
                                    metric_type=MetricType(metric_data["metric_type"]),
                                    value=float(metric_data["value"]),
                                    unit=metric_data["unit"],
                                    timestamp=float(metric_data["timestamp"]),
                                    metadata=eval(metric_data["metadata"])
                                    if metric_data["metadata"] != "{}"
                                    else {},
                                )
                            )
                except Exception as e:
                    logger.error("Failed to parse metric key", error=str(e), key=key)

            history.sort(key=lambda x: x.timestamp)
            return history

        except Exception as e:
            logger.error("Failed to get metric history", error=str(e))
            return []

    async def get_metric_summary(
        self, tenant_id: str, metric_name: str
    ) -> Dict[str, Any]:
        """Get metric summary statistics."""
        try:
            history = await self.get_metric_history(tenant_id, metric_name, 24)

            if not history:
                return {"metric_name": metric_name, "error": "No data available"}

            values = [result.value for result in history]

            return {
                "metric_name": metric_name,
                "current_value": values[-1] if values else 0,
                "average_value": sum(values) / len(values) if values else 0,
                "min_value": min(values) if values else 0,
                "max_value": max(values) if values else 0,
                "sample_count": len(values),
                "time_range_hours": 24,
            }

        except Exception as e:
            logger.error("Failed to get metric summary", error=str(e))
            return {"metric_name": metric_name, "error": str(e)}
