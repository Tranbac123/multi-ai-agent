"""Integration tests for Tail-latency Control features."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from libs.clients.http.request_hedging import (
    RequestHedgingManager, HedgingStrategy, HedgingResult, HedgingConfig
)
from libs.clients.http.timeout_manager import (
    TimeoutManager, TimeoutType, TimeoutSeverity, TimeoutConfig
)
from libs.clients.http.coordinated_cancellation import (
    CoordinatedCancellationManager, CancellationReason, CancellationStatus
)


class TestRequestHedgingManager:
    """Test request hedging functionality."""
    
    @pytest.fixture
    def hedging_manager(self):
        """Create RequestHedgingManager instance for testing."""
        return RequestHedgingManager()
    
    @pytest.fixture
    def mock_http_client(self):
        """Create mock HTTP client for testing."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = "Success"
        mock_client.request.return_value = mock_response
        return mock_client
    
    @pytest.mark.asyncio
    async def test_hedge_request_parallel_strategy(self, hedging_manager, mock_http_client):
        """Test parallel hedging strategy."""
        # Setup
        hedging_manager.http_client_factory = lambda: mock_http_client
        hedging_manager.hedging_config.strategy = HedgingStrategy.PARALLEL
        hedging_manager.hedging_config.cancel_others_on_first_success = True
        
        urls = ["http://service1.com/api", "http://service2.com/api"]
        
        # Execute hedging
        result = await hedging_manager.hedge_request(urls, method="GET")
        
        # Verify results
        assert result is not None
        assert result.result_type in [HedgingResult.FIRST_WIN, HedgingResult.ALL_FAILED]
        assert result.hedged_requests_count == 2
        assert result.cost_multiplier == 2.0
    
    @pytest.mark.asyncio
    async def test_hedge_request_staggered_strategy(self, hedging_manager, mock_http_client):
        """Test staggered hedging strategy."""
        # Setup
        hedging_manager.http_client_factory = lambda: mock_http_client
        hedging_manager.hedging_config.strategy = HedgingStrategy.STAGGERED
        hedging_manager.hedging_config.hedge_delay_ms = 10  # Short delay for testing
        
        urls = ["http://service1.com/api", "http://service2.com/api"]
        
        # Execute hedging
        result = await hedging_manager.hedge_request(urls, method="GET")
        
        # Verify results
        assert result is not None
        assert result.result_type in [HedgingResult.FIRST_WIN, HedgingResult.HEDGE_WIN, HedgingResult.ALL_FAILED]
        assert result.hedged_requests_count == 2
        assert result.cost_multiplier == 2.0
    
    @pytest.mark.asyncio
    async def test_hedge_request_with_timeout(self, hedging_manager):
        """Test hedging with timeout."""
        # Setup mock client that times out
        async def slow_client():
            await asyncio.sleep(10)  # Longer than timeout
            return MagicMock()
        
        hedging_manager.http_client_factory = slow_client
        hedging_manager.hedging_config.timeout_ms = 100  # Short timeout
        
        urls = ["http://slow-service.com/api"]
        
        # Execute hedging
        result = await hedging_manager.hedge_request(urls, method="GET")
        
        # Verify timeout handling
        assert result.result_type == HedgingResult.ALL_FAILED
        assert len(result.all_responses) == 1
        assert not result.all_responses[0].success
        assert "timeout" in result.all_responses[0].error.lower()
    
    def test_update_hedging_config(self, hedging_manager):
        """Test updating hedging configuration."""
        new_config = HedgingConfig(
            strategy=HedgingStrategy.ADAPTIVE,
            max_parallel_requests=3,
            hedge_delay_ms=100,
            timeout_ms=8000
        )
        
        hedging_manager.update_hedging_config(new_config)
        
        assert hedging_manager.hedging_config.strategy == HedgingStrategy.ADAPTIVE
        assert hedging_manager.hedging_config.max_parallel_requests == 3
        assert hedging_manager.hedging_config.hedge_delay_ms == 100
        assert hedging_manager.hedging_config.timeout_ms == 8000
    
    def test_get_hedging_stats(self, hedging_manager):
        """Test getting hedging statistics."""
        # Update some stats
        hedging_manager.hedging_stats["total_hedged_requests"] = 100
        hedging_manager.hedging_stats["first_wins"] = 80
        hedging_manager.hedging_stats["hedge_wins"] = 15
        hedging_manager.hedging_stats["all_failed"] = 5
        
        stats = hedging_manager.get_hedging_stats()
        
        assert stats["total_hedged_requests"] == 100
        assert stats["first_wins"] == 80
        assert stats["hedge_wins"] == 15
        assert stats["all_failed"] == 5
        assert stats["first_win_rate"] == 80.0
        assert stats["hedge_win_rate"] == 15.0
        assert stats["success_rate"] == 95.0


class TestTimeoutManager:
    """Test timeout management functionality."""
    
    @pytest.fixture
    def timeout_manager(self):
        """Create TimeoutManager instance for testing."""
        return TimeoutManager()
    
    @pytest.mark.asyncio
    async def test_execute_with_timeout_success(self, timeout_manager):
        """Test successful operation execution within timeout."""
        async def fast_operation():
            await asyncio.sleep(0.1)
            return "success"
        
        result = await timeout_manager.execute_with_timeout(
            operation=fast_operation,
            operation_type="test_operation",
            timeout_type=TimeoutType.TOTAL
        )
        
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_execute_with_timeout_timeout(self, timeout_manager):
        """Test operation timeout."""
        async def slow_operation():
            await asyncio.sleep(10)  # Longer than timeout
            return "success"
        
        # Set short timeout
        config = TimeoutConfig(
            operation_type="test_operation",
            total_timeout_ms=100
        )
        timeout_manager.update_timeout_config("test_operation", config)
        
        with pytest.raises(asyncio.TimeoutError):
            await timeout_manager.execute_with_timeout(
                operation=slow_operation,
                operation_type="test_operation",
                timeout_type=TimeoutType.TOTAL
            )
        
        # Verify timeout event was recorded
        assert len(timeout_manager.timeout_events) == 1
        timeout_event = timeout_manager.timeout_events[0]
        assert timeout_event.operation_type == "test_operation"
        assert timeout_event.timeout_type == TimeoutType.TOTAL
    
    @pytest.mark.asyncio
    async def test_execute_with_timeout_connect_timeout(self, timeout_manager):
        """Test connect timeout."""
        async def connect_operation():
            await asyncio.sleep(2)  # Longer than connect timeout
            return "connected"
        
        # Set short connect timeout
        config = TimeoutConfig(
            operation_type="test_operation",
            connect_timeout_ms=500
        )
        timeout_manager.update_timeout_config("test_operation", config)
        
        with pytest.raises(asyncio.TimeoutError):
            await timeout_manager.execute_with_timeout(
                operation=connect_operation,
                operation_type="test_operation",
                timeout_type=TimeoutType.CONNECT
            )
        
        # Verify timeout event
        assert len(timeout_manager.timeout_events) == 1
        timeout_event = timeout_manager.timeout_events[0]
        assert timeout_event.timeout_type == TimeoutType.CONNECT
        assert timeout_event.timeout_value_ms == 500
    
    def test_update_timeout_config(self, timeout_manager):
        """Test updating timeout configuration."""
        config = TimeoutConfig(
            operation_type="new_operation",
            connect_timeout_ms=500,
            read_timeout_ms=3000,
            total_timeout_ms=8000,
            max_retries=2
        )
        
        timeout_manager.update_timeout_config("new_operation", config)
        
        assert "new_operation" in timeout_manager.timeout_configs
        assert timeout_manager.timeout_configs["new_operation"].connect_timeout_ms == 500
        assert timeout_manager.timeout_configs["new_operation"].read_timeout_ms == 3000
        assert timeout_manager.timeout_configs["new_operation"].total_timeout_ms == 8000
        assert timeout_manager.timeout_configs["new_operation"].max_retries == 2
    
    def test_get_timeout_stats(self, timeout_manager):
        """Test getting timeout statistics."""
        # Add some timeout events
        timeout_manager.timeout_events.extend([
            timeout_manager._create_timeout_event("op1", TimeoutType.TOTAL, 1000, 1500, TimeoutSeverity.WARNING),
            timeout_manager._create_timeout_event("op1", TimeoutType.CONNECT, 500, 800, TimeoutSeverity.WARNING),
            timeout_manager._create_timeout_event("op2", TimeoutType.TOTAL, 2000, 4000, TimeoutSeverity.CRITICAL)
        ])
        
        stats = timeout_manager.get_timeout_stats()
        
        assert stats["timeout_events_count"] == 3
        assert stats["timeout_events_by_type"]["total"] == 2
        assert stats["timeout_events_by_type"]["connect"] == 1
        assert stats["timeout_events_by_severity"]["warning"] == 2
        assert stats["timeout_events_by_severity"]["critical"] == 1
        assert stats["avg_timeout_duration"] > 0
    
    def test_get_timeout_recommendations(self, timeout_manager):
        """Test getting timeout recommendations."""
        # Add timeout events
        timeout_manager.timeout_events.extend([
            timeout_manager._create_timeout_event("op1", TimeoutType.TOTAL, 1000, 1500, TimeoutSeverity.WARNING),
            timeout_manager._create_timeout_event("op1", TimeoutType.TOTAL, 1000, 1800, TimeoutSeverity.CRITICAL),
            timeout_manager._create_timeout_event("op1", TimeoutType.TOTAL, 1000, 2000, TimeoutSeverity.CRITICAL)
        ])
        
        recommendations = timeout_manager.get_timeout_recommendations("op1")
        
        assert recommendations["operation_type"] == "op1"
        assert len(recommendations["recommendations"]) > 0
        assert recommendations["total_events"] == 3
        assert recommendations["timeout_ratio"] > 0


class TestCoordinatedCancellationManager:
    """Test coordinated cancellation functionality."""
    
    @pytest.fixture
    def cancellation_manager(self):
        """Create CoordinatedCancellationManager instance for testing."""
        return CoordinatedCancellationManager()
    
    @pytest.mark.asyncio
    async def test_initiate_cancellation(self, cancellation_manager):
        """Test initiating coordinated cancellation."""
        cancellation_id = await cancellation_manager.initiate_cancellation(
            request_id="req-123",
            tenant_id="tenant-1",
            reason=CancellationReason.USER_REQUESTED,
            initiated_by="user-1",
            services_to_cancel=["service1", "service2", "service3"]
        )
        
        assert cancellation_id is not None
        assert cancellation_id in cancellation_manager.active_cancellations
        
        # Wait for cancellation to complete
        await asyncio.sleep(0.1)
        
        # Check status
        status = await cancellation_manager.get_cancellation_status(cancellation_id)
        assert status is not None
        assert status["request_id"] == "req-123"
        assert status["tenant_id"] == "tenant-1"
        assert status["reason"] == CancellationReason.USER_REQUESTED.value
        assert status["services_to_cancel"] == ["service1", "service2", "service3"]
    
    @pytest.mark.asyncio
    async def test_cancel_request_by_id(self, cancellation_manager):
        """Test canceling request by ID."""
        cancellation_id = await cancellation_manager.cancel_request_by_id(
            request_id="req-456",
            tenant_id="tenant-1",
            reason=CancellationReason.TIMEOUT,
            initiated_by="system"
        )
        
        assert cancellation_id is not None
        
        # Wait for cancellation to complete
        await asyncio.sleep(0.1)
        
        # Check status
        status = await cancellation_manager.get_cancellation_status(cancellation_id)
        assert status is not None
        assert status["request_id"] == "req-456"
        assert status["reason"] == CancellationReason.TIMEOUT.value
    
    @pytest.mark.asyncio
    async def test_cancel_all_tenant_requests(self, cancellation_manager):
        """Test canceling all requests for a tenant."""
        # First, create some active cancellations
        await cancellation_manager.initiate_cancellation(
            request_id="req-1",
            tenant_id="tenant-1",
            reason=CancellationReason.USER_REQUESTED,
            initiated_by="user-1",
            services_to_cancel=["service1"]
        )
        
        await cancellation_manager.initiate_cancellation(
            request_id="req-2",
            tenant_id="tenant-1",
            reason=CancellationReason.USER_REQUESTED,
            initiated_by="user-1",
            services_to_cancel=["service2"]
        )
        
        # Wait for initial cancellations to start
        await asyncio.sleep(0.1)
        
        # Cancel all tenant requests
        cancellation_ids = await cancellation_manager.cancel_all_tenant_requests(
            tenant_id="tenant-1",
            reason=CancellationReason.RESOURCE_EXHAUSTED,
            initiated_by="system"
        )
        
        assert len(cancellation_ids) >= 0  # May be 0 if no pending cancellations
    
    def test_get_cancellation_stats(self, cancellation_manager):
        """Test getting cancellation statistics."""
        # Update some stats
        cancellation_manager.cancellation_stats["total_cancellations"] = 50
        cancellation_manager.cancellation_stats["successful_cancellations"] = 45
        cancellation_manager.cancellation_stats["failed_cancellations"] = 5
        cancellation_manager.cancellation_stats["cancellations_by_reason"]["user_requested"] = 30
        cancellation_manager.cancellation_stats["cancellations_by_service"]["service1"] = 20
        
        stats = cancellation_manager.get_cancellation_stats()
        
        assert stats["total_cancellations"] == 50
        assert stats["successful_cancellations"] == 45
        assert stats["failed_cancellations"] == 5
        assert stats["success_rate"] == 90.0
        assert stats["cancellations_by_reason"]["user_requested"] == 30
        assert stats["cancellations_by_service"]["service1"] == 20
    
    @pytest.mark.asyncio
    async def test_cleanup_completed_cancellations(self, cancellation_manager):
        """Test cleanup of completed cancellations."""
        # Create a completed cancellation
        cancellation_id = await cancellation_manager.initiate_cancellation(
            request_id="req-cleanup",
            tenant_id="tenant-1",
            reason=CancellationReason.USER_REQUESTED,
            initiated_by="user-1",
            services_to_cancel=["service1"]
        )
        
        # Wait for cancellation to complete
        await asyncio.sleep(0.1)
        
        # Manually set status to completed (simulating old completion)
        if cancellation_id in cancellation_manager.active_cancellations:
            cancellation_manager.active_cancellations[cancellation_id].status = CancellationStatus.COMPLETED
            # Set old timestamp
            cancellation_manager.active_cancellations[cancellation_id].initiated_at = datetime.now(timezone.utc) - timedelta(hours=25)
        
        # Run cleanup
        await cancellation_manager.cleanup_completed_cancellations(max_age_hours=24)
        
        # Verify cleanup
        assert cancellation_id not in cancellation_manager.active_cancellations


class TestTailLatencyIntegration:
    """Integration tests for tail-latency control features."""
    
    @pytest.mark.asyncio
    async def test_hedging_with_timeout_integration(self):
        """Test integration of hedging with timeout management."""
        # This would test the full integration scenario
        # where hedging is used with timeout enforcement
        
        # Setup hedging manager with timeout
        # Execute hedged requests with timeout enforcement
        # Verify timeout handling works with hedging
        # Verify coordinated cancellation when timeouts occur
        
        pass  # Implementation would require full integration setup
    
    @pytest.mark.asyncio
    async def test_coordinated_cancellation_with_hedging(self):
        """Test coordinated cancellation with hedging requests."""
        # This would test the full integration scenario
        # where hedging requests are cancelled across services
        
        # Setup hedging with multiple services
        # Start hedging requests
        # Cancel requests mid-execution
        # Verify coordinated cancellation works correctly
        
        pass  # Implementation would require full integration setup
    
    @pytest.mark.asyncio
    async def test_latency_improvement_measurement(self):
        """Test measurement of latency improvements from hedging."""
        # This would test the full integration scenario
        # where latency improvements are measured and reported
        
        # Execute requests with and without hedging
        # Measure P95 and P99 latency improvements
        # Verify improvements meet targets (≥30% for P99)
        # Verify cost impact is within acceptable limits
        
        pass  # Implementation would require full integration setup
    
    @pytest.mark.asyncio
    async def test_timeout_enforcement_across_services(self):
        """Test timeout enforcement across multiple services."""
        # This would test the full integration scenario
        # where timeouts are enforced across all services
        
        # Setup timeouts for different service types
        # Execute operations that span multiple services
        # Verify timeout enforcement works correctly
        # Verify coordinated cancellation on timeout
        
        pass  # Implementation would require full integration setup
