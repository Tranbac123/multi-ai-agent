"""Unit tests for autoscaling and health components."""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock
import redis.asyncio as redis

from infra.k8s.autoscaling.keda_scalers import KEDAScaler, KEDAManager, ScalerConfig, ScalerType
from infra.k8s.health.health_checker import HealthChecker, HealthStatus, HealthCheck


@pytest.fixture
async def mock_redis():
    """Mock Redis client."""
    redis_mock = AsyncMock(spec=redis.Redis)
    redis_mock.get.return_value = None
    redis_mock.setex.return_value = True
    redis_mock.llen.return_value = 0
    redis_mock.keys.return_value = []
    return redis_mock


class TestKEDAScaler:
    """Test KEDA scaler."""
    
    @pytest.mark.asyncio
    async def test_nats_queue_scaler(self, mock_redis):
        """Test NATS queue scaler."""
        config = ScalerConfig(
            name="test-nats-scaler",
            scaler_type=ScalerType.NATS_QUEUE,
            min_replicas=1,
            max_replicas=10,
            target_value=5.0,
            scale_up_threshold=10.0,
            scale_down_threshold=2.0
        )
        
        scaler = KEDAScaler(config, mock_redis)
        
        # Mock queue depth
        mock_redis.get.return_value = b"15.0"
        
        decision = await scaler.get_scale_decision()
        
        assert decision['scaler_name'] == "test-nats-scaler"
        assert decision['scaler_type'] == "nats_queue"
        assert decision['current_value'] == 15.0
        assert decision['target_value'] == 5.0
        assert decision['scale_decision'] == "scale_up"
    
    @pytest.mark.asyncio
    async def test_redis_queue_scaler(self, mock_redis):
        """Test Redis queue scaler."""
        config = ScalerConfig(
            name="test-redis-scaler",
            scaler_type=ScalerType.REDIS_QUEUE,
            min_replicas=1,
            max_replicas=5,
            target_value=10.0,
            scale_up_threshold=20.0,
            scale_down_threshold=5.0
        )
        
        scaler = KEDAScaler(config, mock_redis)
        
        # Mock queue length
        mock_redis.llen.return_value = 25
        
        decision = await scaler.get_scale_decision()
        
        assert decision['scaler_name'] == "test-redis-scaler"
        assert decision['scaler_type'] == "redis_queue"
        assert decision['current_value'] == 25.0
        assert decision['target_value'] == 10.0
        assert decision['scale_decision'] == "scale_up"
    
    @pytest.mark.asyncio
    async def test_cpu_scaler(self, mock_redis):
        """Test CPU scaler."""
        config = ScalerConfig(
            name="test-cpu-scaler",
            scaler_type=ScalerType.CPU,
            min_replicas=2,
            max_replicas=10,
            target_value=0.7,
            scale_up_threshold=0.8,
            scale_down_threshold=0.3
        )
        
        scaler = KEDAScaler(config, mock_redis)
        
        # Mock CPU usage
        mock_redis.get.return_value = b"0.9"
        
        decision = await scaler.get_scale_decision()
        
        assert decision['scaler_name'] == "test-cpu-scaler"
        assert decision['scaler_type'] == "cpu"
        assert decision['current_value'] == 0.9
        assert decision['target_value'] == 0.7
        assert decision['scale_decision'] == "scale_up"
    
    @pytest.mark.asyncio
    async def test_memory_scaler(self, mock_redis):
        """Test memory scaler."""
        config = ScalerConfig(
            name="test-memory-scaler",
            scaler_type=ScalerType.MEMORY,
            min_replicas=1,
            max_replicas=8,
            target_value=0.7,
            scale_up_threshold=0.8,
            scale_down_threshold=0.3
        )
        
        scaler = KEDAScaler(config, mock_redis)
        
        # Mock memory usage
        mock_redis.get.return_value = b"0.2"
        
        decision = await scaler.get_scale_decision()
        
        assert decision['scaler_name'] == "test-memory-scaler"
        assert decision['scaler_type'] == "memory"
        assert decision['current_value'] == 0.2
        assert decision['target_value'] == 0.7
        assert decision['scale_decision'] == "scale_down"
    
    @pytest.mark.asyncio
    async def test_cooldown_period(self, mock_redis):
        """Test cooldown period."""
        config = ScalerConfig(
            name="test-cooldown-scaler",
            scaler_type=ScalerType.CPU,
            min_replicas=1,
            max_replicas=10,
            target_value=0.7,
            scale_up_threshold=0.8,
            scale_down_threshold=0.3,
            cooldown_period=1  # 1 second cooldown
        )
        
        scaler = KEDAScaler(config, mock_redis)
        
        # Mock high CPU usage
        mock_redis.get.return_value = b"0.9"
        
        # First decision should be scale_up
        decision1 = await scaler.get_scale_decision()
        assert decision1['scale_decision'] == "scale_up"
        
        # Second decision should be cooldown
        decision2 = await scaler.get_scale_decision()
        assert decision2['scale_decision'] == "cooldown"
        
        # Wait for cooldown period
        await asyncio.sleep(1.1)
        
        # Third decision should be scale_up again
        decision3 = await scaler.get_scale_decision()
        assert decision3['scale_decision'] == "scale_up"
    
    @pytest.mark.asyncio
    async def test_max_replicas_reached(self, mock_redis):
        """Test max replicas reached."""
        config = ScalerConfig(
            name="test-max-replicas-scaler",
            scaler_type=ScalerType.CPU,
            min_replicas=1,
            max_replicas=2,
            target_value=0.7,
            scale_up_threshold=0.8,
            scale_down_threshold=0.3
        )
        
        scaler = KEDAScaler(config, mock_redis)
        scaler.metrics.replicas = 2  # Already at max
        
        # Mock high CPU usage
        mock_redis.get.return_value = b"0.9"
        
        decision = await scaler.get_scale_decision()
        
        assert decision['scale_decision'] == "max_replicas_reached"
    
    @pytest.mark.asyncio
    async def test_min_replicas_reached(self, mock_redis):
        """Test min replicas reached."""
        config = ScalerConfig(
            name="test-min-replicas-scaler",
            scaler_type=ScalerType.CPU,
            min_replicas=2,
            max_replicas=10,
            target_value=0.7,
            scale_up_threshold=0.8,
            scale_down_threshold=0.3
        )
        
        scaler = KEDAScaler(config, mock_redis)
        scaler.metrics.replicas = 2  # Already at min
        
        # Mock low CPU usage
        mock_redis.get.return_value = b"0.1"
        
        decision = await scaler.get_scale_decision()
        
        assert decision['scale_decision'] == "min_replicas_reached"


class TestKEDAManager:
    """Test KEDA manager."""
    
    @pytest.mark.asyncio
    async def test_initialize_scalers(self, mock_redis):
        """Test scaler initialization."""
        manager = KEDAManager(mock_redis)
        
        await manager.initialize_scalers()
        
        assert len(manager.scalers) == 6  # 6 scalers configured
        
        # Check specific scalers exist
        assert "orchestrator-nats" in manager.scalers
        assert "ingestion-nats" in manager.scalers
        assert "router-service-cpu" in manager.scalers
        assert "realtime-cpu" in manager.scalers
        assert "analytics-service-memory" in manager.scalers
        assert "billing-service-redis" in manager.scalers
    
    @pytest.mark.asyncio
    async def test_get_all_scale_decisions(self, mock_redis):
        """Test getting all scale decisions."""
        manager = KEDAManager(mock_redis)
        
        await manager.initialize_scalers()
        
        decisions = await manager.get_all_scale_decisions()
        
        assert len(decisions) == 6
        
        # Check all decisions have required fields
        for decision in decisions:
            assert 'scaler_name' in decision
            assert 'scaler_type' in decision
            assert 'current_value' in decision
            assert 'target_value' in decision
            assert 'scale_decision' in decision
            assert 'current_replicas' in decision
            assert 'min_replicas' in decision
            assert 'max_replicas' in decision
    
    @pytest.mark.asyncio
    async def test_get_scaler_metrics(self, mock_redis):
        """Test getting scaler metrics."""
        manager = KEDAManager(mock_redis)
        
        await manager.initialize_scalers()
        
        metrics = await manager.get_scaler_metrics("orchestrator-nats")
        
        assert metrics is not None
        assert metrics['scaler_name'] == "orchestrator-nats"
        assert metrics['scaler_type'] == "nats_queue"
    
    @pytest.mark.asyncio
    async def test_update_scaler_config(self, mock_redis):
        """Test updating scaler configuration."""
        manager = KEDAManager(mock_redis)
        
        await manager.initialize_scalers()
        
        # Update scaler configuration
        success = await manager.update_scaler_config(
            "orchestrator-nats",
            {"max_replicas": 25, "scale_up_threshold": 15.0}
        )
        
        assert success is True
        
        # Verify configuration was updated
        scaler = manager.scalers["orchestrator-nats"]
        assert scaler.config.max_replicas == 25
        assert scaler.config.scale_up_threshold == 15.0
    
    @pytest.mark.asyncio
    async def test_get_autoscaling_summary(self, mock_redis):
        """Test getting autoscaling summary."""
        manager = KEDAManager(mock_redis)
        
        await manager.initialize_scalers()
        
        summary = await manager.get_autoscaling_summary()
        
        assert 'total_scalers' in summary
        assert summary['total_scalers'] == 6
        assert 'scale_decisions' in summary
        assert 'scalers' in summary
        
        # Check scale decisions structure
        scale_decisions = summary['scale_decisions']
        assert 'scale_up' in scale_decisions
        assert 'scale_down' in scale_decisions
        assert 'none' in scale_decisions
        assert 'cooldown' in scale_decisions
        assert 'error' in scale_decisions


class TestHealthChecker:
    """Test health checker."""
    
    @pytest.mark.asyncio
    async def test_initialize_health_checks(self, mock_redis):
        """Test health check initialization."""
        checker = HealthChecker(mock_redis)
        
        assert len(checker.health_checks) == 12  # 6 services × 2 checks each
        
        # Check specific health checks exist
        check_names = [check.name for check in checker.health_checks]
        assert "api-gateway-readiness" in check_names
        assert "api-gateway-liveness" in check_names
        assert "router-service-readiness" in check_names
        assert "router-service-liveness" in check_names
        assert "orchestrator-readiness" in check_names
        assert "orchestrator-liveness" in check_names
        assert "realtime-readiness" in check_names
        assert "realtime-liveness" in check_names
        assert "analytics-service-readiness" in check_names
        assert "analytics-service-liveness" in check_names
        assert "billing-service-readiness" in check_names
        assert "billing-service-liveness" in check_names
    
    @pytest.mark.asyncio
    async def test_check_health_readiness(self, mock_redis):
        """Test health check for readiness."""
        checker = HealthChecker(mock_redis)
        
        result = await checker.check_health("api-gateway-readiness")
        
        assert result.name == "api-gateway-readiness"
        assert result.status == HealthStatus.HEALTHY
        assert "ready" in result.message.lower()
        assert result.response_time_ms > 0
        assert result.details is not None
    
    @pytest.mark.asyncio
    async def test_check_health_liveness(self, mock_redis):
        """Test health check for liveness."""
        checker = HealthChecker(mock_redis)
        
        result = await checker.check_health("api-gateway-liveness")
        
        assert result.name == "api-gateway-liveness"
        assert result.status == HealthStatus.HEALTHY
        assert "alive" in result.message.lower()
        assert result.response_time_ms > 0
        assert result.details is not None
    
    @pytest.mark.asyncio
    async def test_check_health_unknown_service(self, mock_redis):
        """Test health check for unknown service."""
        checker = HealthChecker(mock_redis)
        
        result = await checker.check_health("unknown-service-readiness")
        
        assert result.name == "unknown-service-readiness"
        assert result.status == HealthStatus.UNKNOWN
        assert "not found" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_store_health_result(self, mock_redis):
        """Test storing health result."""
        checker = HealthChecker(mock_redis)
        
        result = await checker.check_health("api-gateway-readiness")
        
        # Verify result was stored
        assert result.name in checker.health_results
        assert checker.health_results[result.name] == result
        
        # Verify Redis was called
        assert mock_redis.setex.called
    
    @pytest.mark.asyncio
    async def test_get_health_summary(self, mock_redis):
        """Test getting health summary."""
        checker = HealthChecker(mock_redis)
        
        # Check health for all services
        for check in checker.health_checks:
            await checker.check_health(check.name)
        
        summary = await checker.get_health_summary()
        
        assert 'total_checks' in summary
        assert summary['total_checks'] == 12
        assert 'healthy' in summary
        assert 'unhealthy' in summary
        assert 'degraded' in summary
        assert 'unknown' in summary
        assert 'services' in summary
        
        # Check service breakdown
        services = summary['services']
        assert 'api-gateway' in services
        assert 'router-service' in services
        assert 'orchestrator' in services
        assert 'realtime' in services
        assert 'analytics-service' in services
        assert 'billing-service' in services
        
        # Check each service has readiness and liveness
        for service_name, service_health in services.items():
            assert 'readiness' in service_health
            assert 'liveness' in service_health
            assert service_health['readiness'] == 'healthy'
            assert service_health['liveness'] == 'healthy'


class TestIntegration:
    """Integration tests for autoscaling and health."""
    
    @pytest.mark.asyncio
    async def test_autoscaling_with_health_checks(self, mock_redis):
        """Test autoscaling with health checks."""
        # Initialize KEDA manager
        keda_manager = KEDAManager(mock_redis)
        await keda_manager.initialize_scalers()
        
        # Initialize health checker
        health_checker = HealthChecker(mock_redis)
        
        # Get autoscaling decisions
        autoscaling_decisions = await keda_manager.get_all_scale_decisions()
        
        # Check health for all services
        for check in health_checker.health_checks:
            await health_checker.check_health(check.name)
        
        # Get health summary
        health_summary = await health_checker.get_health_summary()
        
        # Verify both systems are working
        assert len(autoscaling_decisions) == 6
        assert health_summary['total_checks'] == 12
        assert health_summary['healthy'] == 12  # All services healthy
    
    @pytest.mark.asyncio
    async def test_scaler_configuration_consistency(self, mock_redis):
        """Test scaler configuration consistency."""
        manager = KEDAManager(mock_redis)
        
        await manager.initialize_scalers()
        
        # Check that all scalers have valid configurations
        for scaler_name, scaler in manager.scalers.items():
            config = scaler.config
            
            assert config.min_replicas > 0
            assert config.max_replicas >= config.min_replicas
            assert config.target_value > 0
            assert config.scale_up_threshold > 0
            assert config.scale_down_threshold >= 0
            assert config.scale_up_period > 0
            assert config.scale_down_period > 0
            assert config.cooldown_period > 0
    
    @pytest.mark.asyncio
    async def test_health_check_consistency(self, mock_redis):
        """Test health check consistency."""
        checker = HealthChecker(mock_redis)
        
        # Check that all health checks have valid configurations
        for check in checker.health_checks:
            assert check.name is not None
            assert check.check_type in ['readiness', 'liveness']
            assert check.timeout_seconds > 0
            assert check.interval_seconds > 0
            assert check.failure_threshold > 0
            assert check.success_threshold > 0
            assert check.initial_delay_seconds >= 0


if __name__ == '__main__':
    pytest.main([__file__])
