"""Integration tests for Realtime service."""

import pytest
import asyncio
import json
import websockets
from typing import Dict, Any

from apps.realtime.core.connection_manager import ConnectionManager
from apps.realtime.core.backpressure_handler import BackpressureHandler, BackpressureMetrics


@pytest.fixture
async def connection_manager_with_redis():
    """Connection manager instance with real Redis connection."""
    import redis.asyncio as redis
    
    redis_client = redis.Redis(
        host="localhost",
        port=6379,
        db=6,  # Use different DB for tests
        decode_responses=False
    )
    
    manager = ConnectionManager(redis_client)
    
    yield manager
    
    # Cleanup
    await redis_client.flushdb()
    await redis_client.close()


@pytest.fixture
async def backpressure_handler_with_redis(connection_manager_with_redis):
    """Backpressure handler instance with real Redis connection."""
    handler = BackpressureHandler(
        connection_manager=connection_manager_with_redis,
        max_queue_size=10,
        drop_policy="intermediate"
    )
    
    yield handler
    
    # Cleanup
    await handler.shutdown()


@pytest.fixture
async def backpressure_metrics_with_redis():
    """Backpressure metrics instance with real Redis connection."""
    import redis.asyncio as redis
    
    redis_client = redis.Redis(
        host="localhost",
        port=6379,
        db=7,  # Use different DB for tests
        decode_responses=False
    )
    
    metrics = BackpressureMetrics(redis_client)
    
    yield metrics
    
    # Cleanup
    await redis_client.flushdb()
    await redis_client.close()


class TestRealtimeIntegration:
    """Integration tests for Realtime service."""
    
    @pytest.mark.asyncio
    async def test_connection_registration_with_redis(self, connection_manager_with_redis):
        """Test connection registration with real Redis."""
        # Mock WebSocket
        class MockWebSocket:
            def __init__(self):
                self.sent_messages = []
            
            async def send_text(self, message):
                self.sent_messages.append(message)
        
        websocket = MockWebSocket()
        
        # Register connection
        await connection_manager_with_redis.register_connection(
            websocket, "tenant123", "user456", "session789"
        )
        
        # Verify connection is stored
        assert "session789" in connection_manager_with_redis.connections
        assert connection_manager_with_redis.connections["session789"] == websocket
        
        # Verify tenant mapping
        assert "tenant123" in connection_manager_with_redis.tenant_connections
        assert "session789" in connection_manager_with_redis.tenant_connections["tenant123"]
        
        # Verify user mapping
        assert "user456" in connection_manager_with_redis.user_connections
        assert "session789" in connection_manager_with_redis.user_connections["user456"]
    
    @pytest.mark.asyncio
    async def test_connection_unregistration_with_redis(self, connection_manager_with_redis):
        """Test connection unregistration with real Redis."""
        # Mock WebSocket
        class MockWebSocket:
            def __init__(self):
                self.sent_messages = []
            
            async def send_text(self, message):
                self.sent_messages.append(message)
        
        websocket = MockWebSocket()
        
        # Register connection
        await connection_manager_with_redis.register_connection(
            websocket, "tenant123", "user456", "session789"
        )
        
        # Unregister connection
        await connection_manager_with_redis.unregister_connection(
            websocket, "tenant123", "user456"
        )
        
        # Verify connection is removed
        assert "session789" not in connection_manager_with_redis.connections
        assert "session789" not in connection_manager_with_redis.tenant_connections["tenant123"]
        assert "session789" not in connection_manager_with_redis.user_connections["user456"]
    
    @pytest.mark.asyncio
    async def test_broadcast_to_tenant_with_redis(self, connection_manager_with_redis):
        """Test broadcasting to tenant with real Redis."""
        # Mock WebSockets
        class MockWebSocket:
            def __init__(self, id):
                self.id = id
                self.sent_messages = []
            
            async def send_text(self, message):
                self.sent_messages.append(message)
        
        websocket1 = MockWebSocket("ws1")
        websocket2 = MockWebSocket("ws2")
        
        # Register connections
        await connection_manager_with_redis.register_connection(
            websocket1, "tenant123", "user456", "session1"
        )
        await connection_manager_with_redis.register_connection(
            websocket2, "tenant123", "user789", "session2"
        )
        
        # Broadcast message
        message = {"type": "test", "content": "hello"}
        sent_count = await connection_manager_with_redis.broadcast_to_tenant("tenant123", message)
        
        assert sent_count == 2
        assert len(websocket1.sent_messages) == 1
        assert len(websocket2.sent_messages) == 1
        assert json.loads(websocket1.sent_messages[0]) == message
        assert json.loads(websocket2.sent_messages[0]) == message
    
    @pytest.mark.asyncio
    async def test_backpressure_handling_with_redis(self, backpressure_handler_with_redis):
        """Test backpressure handling with real Redis."""
        # Mock WebSocket
        class MockWebSocket:
            def __init__(self):
                self.sent_messages = []
            
            async def send_text(self, message):
                self.sent_messages.append(message)
        
        websocket = MockWebSocket()
        
        # Send messages within queue limit
        for i in range(5):
            message = {"type": "test", "content": f"message_{i}"}
            success = await backpressure_handler_with_redis.send_message(
                websocket, "tenant123", "user456", "session789", message
            )
            assert success is True
        
        # Verify messages were sent
        assert len(websocket.sent_messages) == 5
        
        # Check stats
        stats = await backpressure_handler_with_redis.get_stats()
        assert stats["messages_sent"] == 5
        assert stats["messages_dropped"] == 0
    
    @pytest.mark.asyncio
    async def test_backpressure_overflow_with_redis(self, backpressure_handler_with_redis):
        """Test backpressure overflow handling with real Redis."""
        # Mock WebSocket
        class MockWebSocket:
            def __init__(self):
                self.sent_messages = []
            
            async def send_text(self, message):
                self.sent_messages.append(message)
        
        websocket = MockWebSocket()
        
        # Send many messages to trigger backpressure
        for i in range(20):  # More than max_queue_size (10)
            message = {"type": "test", "content": f"message_{i}"}
            await backpressure_handler_with_redis.send_message(
                websocket, "tenant123", "user456", "session789", message
            )
        
        # Check that backpressure was applied
        stats = await backpressure_handler_with_redis.get_stats()
        assert stats["messages_dropped"] > 0
        assert stats["queue_overflows"] > 0
        assert stats["backpressure_events"] > 0
    
    @pytest.mark.asyncio
    async def test_backpressure_metrics_with_redis(self, backpressure_metrics_with_redis):
        """Test backpressure metrics with real Redis."""
        # Record some events
        for i in range(5):
            event_details = {"queue_size": 10 + i, "dropped_count": i}
            await backpressure_metrics_with_redis.record_backpressure_event(
                "tenant123", f"session_{i}", "queue_overflow", event_details
            )
        
        # Get metrics
        metrics = await backpressure_metrics_with_redis.get_backpressure_metrics(
            tenant_id="tenant123", time_window=3600
        )
        
        assert metrics["total_events"] == 5
        assert metrics["time_window_seconds"] == 3600
        assert "event_types" in metrics
        assert "tenant_events" in metrics
        assert "events_per_minute" in metrics
        assert metrics["tenant_events"]["tenant123"] == 5
    
    @pytest.mark.asyncio
    async def test_connection_stats_with_redis(self, connection_manager_with_redis):
        """Test connection statistics with real Redis."""
        # Mock WebSockets
        class MockWebSocket:
            def __init__(self, id):
                self.id = id
                self.sent_messages = []
            
            async def send_text(self, message):
                self.sent_messages.append(message)
        
        # Register multiple connections
        for i in range(3):
            websocket = MockWebSocket(f"ws{i}")
            await connection_manager_with_redis.register_connection(
                websocket, "tenant123", f"user{i}", f"session{i}"
            )
        
        # Get stats
        stats = await connection_manager_with_redis.get_connection_stats()
        
        assert stats["active_connections"] == 3
        assert stats["tenant_connections"]["tenant123"] == 3
        assert stats["total_tenants"] == 1
        assert stats["total_users"] == 3
    
    @pytest.mark.asyncio
    async def test_end_to_end_realtime_flow(self, connection_manager_with_redis, backpressure_handler_with_redis):
        """Test end-to-end realtime flow."""
        # Mock WebSocket
        class MockWebSocket:
            def __init__(self):
                self.sent_messages = []
            
            async def send_text(self, message):
                self.sent_messages.append(message)
        
        websocket = MockWebSocket()
        
        # Register connection
        await connection_manager_with_redis.register_connection(
            websocket, "tenant123", "user456", "session789"
        )
        
        # Send messages with backpressure
        messages = [
            {"type": "chat", "content": "Hello"},
            {"type": "typing", "is_typing": True},
            {"type": "chat", "content": "How are you?"},
            {"type": "typing", "is_typing": False},
            {"type": "chat", "content": "Goodbye"}
        ]
        
        for message in messages:
            success = await backpressure_handler_with_redis.send_message(
                websocket, "tenant123", "user456", "session789", message
            )
            assert success is True
        
        # Verify all messages were sent
        assert len(websocket.sent_messages) == len(messages)
        
        # Verify message content
        for i, message in enumerate(messages):
            sent_message = json.loads(websocket.sent_messages[i])
            assert sent_message == message
        
        # Get final stats
        connection_stats = await connection_manager_with_redis.get_connection_stats()
        backpressure_stats = await backpressure_handler_with_redis.get_stats()
        
        assert connection_stats["active_connections"] == 1
        assert backpressure_stats["messages_sent"] == len(messages)
        
        # Calculate required metrics
        ws_active_connections = connection_stats.get("active_connections", 0)
        ws_backpressure_drops = backpressure_stats.get("messages_dropped", 0)
        ws_send_errors = backpressure_stats.get("queue_overflows", 0)
        
        assert ws_active_connections == 1
        assert ws_backpressure_drops == 0  # No drops in this test
        assert ws_send_errors == 0  # No errors in this test
    
    @pytest.mark.asyncio
    async def test_slow_client_simulation(self, backpressure_handler_with_redis):
        """Test backpressure behavior with slow client simulation."""
        # Mock slow WebSocket
        class SlowWebSocket:
            def __init__(self):
                self.sent_messages = []
                self.send_delay = 0.1  # 100ms delay per message
            
            async def send_text(self, message):
                await asyncio.sleep(self.send_delay)
                self.sent_messages.append(message)
        
        websocket = SlowWebSocket()
        
        # Send messages faster than client can process
        start_time = asyncio.get_event_loop().time()
        
        for i in range(15):  # More than max_queue_size (10)
            message = {"type": "test", "content": f"message_{i}"}
            await backpressure_handler_with_redis.send_message(
                websocket, "tenant123", "user456", "session789", message
            )
        
        end_time = asyncio.get_event_loop().time()
        
        # Check that backpressure was applied due to slow client
        stats = await backpressure_handler_with_redis.get_stats()
        assert stats["messages_dropped"] > 0
        assert stats["queue_overflows"] > 0
        
        # Verify that some messages were still sent
        assert len(websocket.sent_messages) > 0
        assert len(websocket.sent_messages) < 15  # Some were dropped
    
    @pytest.mark.asyncio
    async def test_metrics_aggregation(self, connection_manager_with_redis, backpressure_handler_with_redis):
        """Test metrics aggregation across components."""
        # Mock WebSocket
        class MockWebSocket:
            def __init__(self):
                self.sent_messages = []
            
            async def send_text(self, message):
                self.sent_messages.append(message)
        
        websocket = MockWebSocket()
        
        # Register connection
        await connection_manager_with_redis.register_connection(
            websocket, "tenant123", "user456", "session789"
        )
        
        # Send some messages
        for i in range(5):
            message = {"type": "test", "content": f"message_{i}"}
            await backpressure_handler_with_redis.send_message(
                websocket, "tenant123", "user456", "session789", message
            )
        
        # Get aggregated metrics
        connection_stats = await connection_manager_with_redis.get_connection_stats()
        backpressure_stats = await backpressure_handler_with_redis.get_stats()
        
        # Calculate required metrics
        ws_active_connections = connection_stats.get("active_connections", 0)
        ws_backpressure_drops = backpressure_stats.get("messages_dropped", 0)
        ws_send_errors = backpressure_stats.get("queue_overflows", 0)
        
        # Verify metrics
        assert ws_active_connections == 1
        assert ws_backpressure_drops >= 0
        assert ws_send_errors >= 0
        
        # Verify individual stats
        assert connection_stats["active_connections"] == 1
        assert backpressure_stats["messages_sent"] == 5
        assert backpressure_stats["active_queues"] == 1
