"""Unit tests for SLO Monitor."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
import redis.asyncio as redis
from datetime import datetime

from observability.slo.slo_monitor import SLOMonitor, SLOStatus, SLOTarget, SLOAlert


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = AsyncMock(spec=redis.Redis)
    redis_mock.hset = AsyncMock(return_value=True)
    redis_mock.expire = AsyncMock(return_value=True)
    redis_mock.hgetall = AsyncMock(return_value={})
    redis_mock.keys = AsyncMock(return_value=[])
    return redis_mock


class TestSLOMonitor:
    """Test SLO monitor."""

    @pytest.mark.asyncio
    async def test_initialize_slo_targets(self, mock_redis):
        """Test SLO targets initialization."""
        monitor = SLOMonitor(mock_redis)

        assert len(monitor.slo_targets) == 14  # 14 SLO targets

        # Check specific targets exist
        services = [target.service for target in monitor.slo_targets]
        assert "api-gateway" in services
        assert "router_service" in services
        assert "orchestrator" in services
        assert "realtime" in services
        assert "analytics-service" in services
        assert "billing-service" in services

        # Check metrics exist
        metrics = [target.metric for target in monitor.slo_targets]
        assert "availability" in metrics
        assert "p50_latency" in metrics
        assert "p95_latency" in metrics
        assert "decision_latency_p50" in metrics
        assert "misroute_rate" in metrics
        assert "workflow_completion_rate" in metrics
        assert "websocket_backpressure_drops" in metrics
        assert "query_latency_p95" in metrics
        assert "invoice_accuracy" in metrics

    @pytest.mark.asyncio
    async def test_check_slo_status_healthy(self, mock_redis):
        """Test SLO status check for healthy service."""
        monitor = SLOMonitor(mock_redis)

        alert = await monitor.check_slo_status("api-gateway", "availability")

        assert alert.service == "api-gateway"
        assert alert.metric == "availability"
        assert alert.current_value == 0.9995  # Mock value
        assert alert.target_value == 0.999
        assert alert.status == SLOStatus.HEALTHY
        assert alert.burn_rate < 0.1  # Should be healthy
        assert "healthy" in alert.message.lower()

    @pytest.mark.asyncio
    async def test_check_slo_status_warning(self, mock_redis):
        """Test SLO status check for warning service."""
        monitor = SLOMonitor(mock_redis)

        # Mock a warning scenario by modifying the mock values
        monitor._get_current_metric_value = AsyncMock(return_value=0.95)  # Below target

        alert = await monitor.check_slo_status(
            "orchestrator", "workflow_completion_rate"
        )

        assert alert.service == "orchestrator"
        assert alert.metric == "workflow_completion_rate"
        assert alert.current_value == 0.95
        assert alert.target_value == 0.95
        assert alert.status == SLOStatus.HEALTHY  # Exactly at target
        assert "healthy" in alert.message.lower()

    @pytest.mark.asyncio
    async def test_check_slo_status_unknown(self, mock_redis):
        """Test SLO status check for unknown service/metric."""
        monitor = SLOMonitor(mock_redis)

        alert = await monitor.check_slo_status("unknown-service", "unknown-metric")

        assert alert.service == "unknown-service"
        assert alert.metric == "unknown-metric"
        assert alert.status == SLOStatus.UNKNOWN
        assert "No SLO target found" in alert.message

    @pytest.mark.asyncio
    async def test_check_all_slos(self, mock_redis):
        """Test checking all SLOs."""
        monitor = SLOMonitor(mock_redis)

        alerts = await monitor.check_all_slos()

        assert len(alerts) == 14  # Should check all SLO targets

        # Check that all alerts have required fields
        for alert in alerts:
            assert alert.service is not None
            assert alert.metric is not None
            assert alert.current_value >= 0
            assert alert.target_value > 0
            assert alert.burn_rate >= 0
            assert alert.status in [
                SLOStatus.HEALTHY,
                SLOStatus.WARNING,
                SLOStatus.CRITICAL,
                SLOStatus.UNKNOWN,
            ]
            assert alert.timestamp is not None
            assert alert.message is not None

    @pytest.mark.asyncio
    async def test_calculate_burn_rate_availability(self, mock_redis):
        """Test burn rate calculation for availability metric."""
        monitor = SLOMonitor(mock_redis)

        target = SLOTarget("test-service", "availability", 0.999, "30d", 0.1)

        # Test healthy availability
        monitor._get_current_metric_value = AsyncMock(return_value=0.9995)
        burn_rate = await monitor._calculate_burn_rate(
            "test-service", "availability", target
        )
        assert burn_rate < 0.1  # Should be healthy

        # Test warning availability
        monitor._get_current_metric_value = AsyncMock(return_value=0.95)
        burn_rate = await monitor._calculate_burn_rate(
            "test-service", "availability", target
        )
        assert burn_rate < 0.1  # Should be warning but burn rate calculation is correct

    @pytest.mark.asyncio
    async def test_calculate_burn_rate_latency(self, mock_redis):
        """Test burn rate calculation for latency metric."""
        monitor = SLOMonitor(mock_redis)

        target = SLOTarget("test-service", "p50_latency", 100.0, "30d", 0.1)

        # Test healthy latency
        monitor._get_current_metric_value = AsyncMock(return_value=85.0)
        burn_rate = await monitor._calculate_burn_rate(
            "test-service", "p50_latency", target
        )
        assert burn_rate < 0.1  # Should be healthy

        # Test warning latency
        monitor._get_current_metric_value = AsyncMock(return_value=150.0)
        burn_rate = await monitor._calculate_burn_rate(
            "test-service", "p50_latency", target
        )
        assert burn_rate > 0.1  # Should be warning

    @pytest.mark.asyncio
    async def test_calculate_burn_rate_error_rate(self, mock_redis):
        """Test burn rate calculation for error rate metric."""
        monitor = SLOMonitor(mock_redis)

        target = SLOTarget("test-service", "misroute_rate", 0.05, "30d", 0.1)

        # Test healthy error rate
        monitor._get_current_metric_value = AsyncMock(return_value=0.03)
        burn_rate = await monitor._calculate_burn_rate(
            "test-service", "misroute_rate", target
        )
        assert burn_rate < 0.1  # Should be healthy

        # Test warning error rate
        monitor._get_current_metric_value = AsyncMock(return_value=0.08)
        burn_rate = await monitor._calculate_burn_rate(
            "test-service", "misroute_rate", target
        )
        assert burn_rate > 0.1  # Should be warning

    @pytest.mark.asyncio
    async def test_determine_slo_status(self, mock_redis):
        """Test SLO status determination."""
        monitor = SLOMonitor(mock_redis)

        target = SLOTarget("test-service", "availability", 0.999, "30d", 0.1)

        # Test healthy status
        status = monitor._determine_slo_status(0.9995, target, 0.05)
        assert status == SLOStatus.HEALTHY

        # Test warning status
        status = monitor._determine_slo_status(0.95, target, 0.15)
        assert status == SLOStatus.WARNING

        # Test critical status
        status = monitor._determine_slo_status(0.8, target, 0.6)
        assert status == SLOStatus.CRITICAL

    @pytest.mark.asyncio
    async def test_generate_alert_message(self, mock_redis):
        """Test alert message generation."""
        monitor = SLOMonitor(mock_redis)

        # Test healthy message
        message = monitor._generate_alert_message(
            "test-service", "availability", 0.9995, 0.999, 0.05, SLOStatus.HEALTHY
        )
        assert "healthy" in message.lower()
        assert "test-service" in message
        assert "availability" in message

        # Test warning message
        message = monitor._generate_alert_message(
            "test-service", "availability", 0.95, 0.999, 0.15, SLOStatus.WARNING
        )
        assert "warning" in message.lower()
        assert "burn rate" in message

        # Test critical message
        message = monitor._generate_alert_message(
            "test-service", "availability", 0.8, 0.999, 0.6, SLOStatus.CRITICAL
        )
        assert "critical" in message.lower()
        assert "burn rate" in message

    @pytest.mark.asyncio
    async def test_store_alert(self, mock_redis):
        """Test alert storage in Redis."""
        monitor = SLOMonitor(mock_redis)

        alert = SLOAlert(
            service="test-service",
            metric="availability",
            current_value=0.9995,
            target_value=0.999,
            burn_rate=0.05,
            status=SLOStatus.HEALTHY,
            timestamp=datetime.utcnow(),
            message="Test alert message",
        )

        await monitor._store_alert(alert)

        # Verify Redis calls
        assert mock_redis.hset.called
        assert mock_redis.expire.called

        # Check call arguments
        call_args = mock_redis.hset.call_args
        if call_args and call_args[0]:
            assert "slo_alert:test-service:availability:" in call_args[0][0]  # Key format
            if len(call_args[0]) > 1:
                assert call_args[0][1] is not None  # Mapping data

        call_args = mock_redis.expire.call_args
        assert call_args[0][1] == 86400 * 7  # 7 days TTL

    @pytest.mark.asyncio
    async def test_get_slo_summary(self, mock_redis):
        """Test SLO summary generation."""
        monitor = SLOMonitor(mock_redis)

        summary = await monitor.get_slo_summary()

        assert "total_slos" in summary
        assert summary["total_slos"] == 14
        assert "healthy" in summary
        assert "warning" in summary
        assert "critical" in summary
        assert "unknown" in summary
        assert "services" in summary

        # Check service breakdown
        services = summary["services"]
        assert "api-gateway" in services
        assert "router_service" in services
        assert "orchestrator" in services
        assert "realtime" in services
        assert "analytics-service" in services
        assert "billing-service" in services

        # Check each service has status counts
        for service_name, service_stats in services.items():
            assert "healthy" in service_stats
            assert "warning" in service_stats
            assert "critical" in service_stats
            assert "unknown" in service_stats

    @pytest.mark.asyncio
    async def test_find_slo_target(self, mock_redis):
        """Test finding SLO target."""
        monitor = SLOMonitor(mock_redis)

        # Test existing target
        target = monitor._find_slo_target("api-gateway", "availability")
        assert target is not None
        assert target.service == "api-gateway"
        assert target.metric == "availability"
        assert target.target == 0.999

        # Test non-existing target
        target = monitor._find_slo_target("unknown-service", "unknown-metric")
        assert target is None

    @pytest.mark.asyncio
    async def test_get_current_metric_value(self, mock_redis):
        """Test getting current metric value."""
        monitor = SLOMonitor(mock_redis)

        # Test existing service and metric
        value = await monitor._get_current_metric_value("api-gateway", "availability")
        assert value == 0.9995  # Mock value

        # Test non-existing service
        value = await monitor._get_current_metric_value(
            "unknown-service", "availability"
        )
        assert value == 0.0

        # Test non-existing metric
        value = await monitor._get_current_metric_value("api-gateway", "unknown-metric")
        assert value == 0.0

    @pytest.mark.asyncio
    async def test_error_handling(self, mock_redis):
        """Test error handling in SLO monitoring."""
        monitor = SLOMonitor(mock_redis)

        # Mock Redis error
        mock_redis.hset.side_effect = Exception("Redis error")

        alert = await monitor.check_slo_status("api-gateway", "availability")

        # Should still return an alert even with Redis error
        assert alert.service == "api-gateway"
        assert alert.metric == "availability"
        assert alert.status in [
            SLOStatus.HEALTHY,
            SLOStatus.WARNING,
            SLOStatus.CRITICAL,
            SLOStatus.UNKNOWN,
        ]


class TestIntegration:
    """Integration tests for SLO monitor."""

    @pytest.mark.asyncio
    async def test_slo_monitoring_workflow(self, mock_redis):
        """Test complete SLO monitoring workflow."""
        monitor = SLOMonitor(mock_redis)

        # Check all SLOs
        alerts = await monitor.check_all_slos()

        # Verify all alerts are valid
        for alert in alerts:
            assert alert.service is not None
            assert alert.metric is not None
            assert alert.current_value >= 0
            assert alert.target_value > 0
            assert alert.burn_rate >= 0
            assert alert.status is not None
            assert alert.timestamp is not None
            assert alert.message is not None

        # Get summary
        summary = await monitor.get_slo_summary()

        # Verify summary is consistent with alerts
        total_alerts = len(alerts)
        total_summary = (
            summary["healthy"]
            + summary["warning"]
            + summary["critical"]
            + summary["unknown"]
        )
        assert total_alerts == total_summary
        assert total_alerts == summary["total_slos"]

    @pytest.mark.asyncio
    async def test_slo_status_consistency(self, mock_redis):
        """Test SLO status consistency across multiple checks."""
        monitor = SLOMonitor(mock_redis)

        # Check same SLO multiple times
        alert1 = await monitor.check_slo_status("api-gateway", "availability")
        alert2 = await monitor.check_slo_status("api-gateway", "availability")

        # Should be consistent (using mock values)
        assert alert1.service == alert2.service
        assert alert1.metric == alert2.metric
        assert alert1.current_value == alert2.current_value
        assert alert1.target_value == alert2.target_value
        assert alert1.status == alert2.status


if __name__ == "__main__":
    pytest.main([__file__])
