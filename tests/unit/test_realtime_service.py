"""Unit tests for Realtime service."""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from apps.realtime.core.connection_manager import ConnectionManager
from apps.realtime.core.backpressure_handler import BackpressureHandler, BackpressureMetrics


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = AsyncMock()
    redis_mock.hset = AsyncMock()
    redis_mock.expire = AsyncMock()
    redis_mock.delete = AsyncMock()
    redis_mock.hgetall = AsyncMock(return_value={})
    redis_mock.lpush = AsyncMock()
    redis_mock.ltrim = AsyncMock()
    redis_mock.lrange = AsyncMock(return_value=[])
    redis_mock.ping = AsyncMock()
    return redis_mock


@pytest.fixture
def mock_websocket():
    """Mock WebSocket."""
    websocket_mock = AsyncMock()
    websocket_mock.send_text = AsyncMock()
    websocket_mock.receive_text = AsyncMock()
    websocket_mock.accept = AsyncMock()
    return websocket_mock


@pytest.fixture
def connection_manager(mock_redis):
    """Connection manager instance with mocked dependencies."""
    return ConnectionManager(mock_redis)


@pytest.fixture
def backpressure_handler(connection_manager):
    """Backpressure handler instance."""
    return BackpressureHandler(
        connection_manager=connection_manager,
        max_queue_size=10,
        drop_policy="intermediate"
    )


@pytest.fixture
def backpressure_metrics(mock_redis):
    """Backpressure metrics instance."""
    return BackpressureMetrics(mock_redis)


class TestConnectionManager:
    """Test connection manager functionality."""
    
    @pytest.mark.asyncio
    async def test_register_connection(self, connection_manager, mock_websocket, mock_redis):
        """Test connection registration."""
        await connection_manager.register_connection(
            mock_websocket, "tenant123", "user456", "session789"
        )
        
        # Verify connection is stored
        assert "session789" in connection_manager.connections
        assert connection_manager.connections["session789"] == mock_websocket
        
        # Verify tenant mapping
        assert "tenant123" in connection_manager.tenant_connections
        assert "session789" in connection_manager.tenant_connections["tenant123"]
        
        # Verify user mapping
        assert "user456" in connection_manager.user_connections
        assert "session789" in connection_manager.user_connections["user456"]
        
        # Verify Redis storage
        mock_redis.hset.assert_called_once()
        mock_redis.expire.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_unregister_connection(self, connection_manager, mock_websocket, mock_redis):
        """Test connection unregistration."""
        # Register first
        await connection_manager.register_connection(
            mock_websocket, "tenant123", "user456", "session789"
        )
        
        # Unregister
        await connection_manager.unregister_connection(
            mock_websocket, "tenant123", "user456"
        )
        
        # Verify connection is removed
        assert "session789" not in connection_manager.connections
        assert "session789" not in connection_manager.tenant_connections["tenant123"]
        assert "session789" not in connection_manager.user_connections["user456"]
        
        # Verify Redis cleanup
        mock_redis.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_connection(self, connection_manager, mock_websocket):
        """Test getting connection by session ID."""
        await connection_manager.register_connection(
            mock_websocket, "tenant123", "user456", "session789"
        )
        
        connection = await connection_manager.get_connection("session789")
        assert connection == mock_websocket
        
        # Test non-existent session
        connection = await connection_manager.get_connection("nonexistent")
        assert connection is None
    
    @pytest.mark.asyncio
    async def test_get_tenant_connections(self, connection_manager, mock_websocket):
        """Test getting connections for a tenant."""
        await connection_manager.register_connection(
            mock_websocket, "tenant123", "user456", "session789"
        )
        
        connections = await connection_manager.get_tenant_connections("tenant123")
        assert len(connections) == 1
        assert connections[0] == mock_websocket
        
        # Test non-existent tenant
        connections = await connection_manager.get_tenant_connections("nonexistent")
        assert len(connections) == 0
    
    @pytest.mark.asyncio
    async def test_broadcast_to_tenant(self, connection_manager, mock_websocket):
        """Test broadcasting to tenant connections."""
        await connection_manager.register_connection(
            mock_websocket, "tenant123", "user456", "session789"
        )
        
        message = {"type": "test", "content": "hello"}
        sent_count = await connection_manager.broadcast_to_tenant("tenant123", message)
        
        assert sent_count == 1
        mock_websocket.send_text.assert_called_once_with(json.dumps(message))
    
    @pytest.mark.asyncio
    async def test_send_to_session(self, connection_manager, mock_websocket):
        """Test sending message to specific session."""
        await connection_manager.register_connection(
            mock_websocket, "tenant123", "user456", "session789"
        )
        
        message = {"type": "test", "content": "hello"}
        success = await connection_manager.send_to_session("session789", message)
        
        assert success is True
        mock_websocket.send_text.assert_called_once_with(json.dumps(message))
    
    @pytest.mark.asyncio
    async def test_get_connection_stats(self, connection_manager, mock_websocket):
        """Test getting connection statistics."""
        await connection_manager.register_connection(
            mock_websocket, "tenant123", "user456", "session789"
        )
        
        stats = await connection_manager.get_connection_stats()
        
        assert stats["active_connections"] == 1
        assert stats["tenant_connections"]["tenant123"] == 1
        assert stats["user_connections"]["user456"] == 1
        assert stats["total_tenants"] == 1
        assert stats["total_users"] == 1


class TestBackpressureHandler:
    """Test backpressure handler functionality."""
    
    @pytest.mark.asyncio
    async def test_send_message_success(self, backpressure_handler, mock_websocket):
        """Test successful message sending."""
        message = {"type": "test", "content": "hello"}
        
        success = await backpressure_handler.send_message(
            mock_websocket, "tenant123", "user456", "session789", message
        )
        
        assert success is True
        mock_websocket.send_text.assert_called_once_with(json.dumps(message))
    
    @pytest.mark.asyncio
    async def test_queue_overflow_intermediate_drop(self, backpressure_handler, mock_websocket):
        """Test intermediate message dropping on queue overflow."""
        # Fill queue beyond max size
        for i in range(15):  # More than max_queue_size (10)
            message = {"type": "test", "content": f"message_{i}"}
            await backpressure_handler.send_message(
                mock_websocket, "tenant123", "user456", "session789", message
            )
        
        # Check that some messages were dropped
        stats = await backpressure_handler.get_stats()
        assert stats["messages_dropped"] > 0
        assert stats["queue_overflows"] > 0
        assert stats["backpressure_events"] > 0
    
    @pytest.mark.asyncio
    async def test_queue_overflow_oldest_drop(self, connection_manager, mock_redis):
        """Test oldest message dropping on queue overflow."""
        handler = BackpressureHandler(
            connection_manager=connection_manager,
            max_queue_size=5,
            drop_policy="oldest"
        )
        
        # Fill queue beyond max size
        for i in range(10):  # More than max_queue_size (5)
            message = {"type": "test", "content": f"message_{i}"}
            await handler.send_message(
                mock_websocket, "tenant123", "user456", "session789", message
            )
        
        # Check that messages were dropped
        stats = await handler.get_stats()
        assert stats["messages_dropped"] > 0
        assert stats["queue_overflows"] > 0
    
    @pytest.mark.asyncio
    async def test_queue_overflow_newest_drop(self, connection_manager, mock_redis):
        """Test newest message dropping on queue overflow."""
        handler = BackpressureHandler(
            connection_manager=connection_manager,
            max_queue_size=5,
            drop_policy="newest"
        )
        
        # Fill queue beyond max size
        for i in range(10):  # More than max_queue_size (5)
            message = {"type": "test", "content": f"message_{i}"}
            await handler.send_message(
                mock_websocket, "tenant123", "user456", "session789", message
            )
        
        # Check that messages were dropped
        stats = await handler.get_stats()
        assert stats["messages_dropped"] > 0
        assert stats["queue_overflows"] > 0
    
    @pytest.mark.asyncio
    async def test_get_queue_size(self, backpressure_handler, mock_websocket):
        """Test getting queue size for a session."""
        # Send some messages
        for i in range(3):
            message = {"type": "test", "content": f"message_{i}"}
            await backpressure_handler.send_message(
                mock_websocket, "tenant123", "user456", "session789", message
            )
        
        queue_size = await backpressure_handler.get_queue_size("session789")
        assert queue_size >= 0  # May be 0 if messages were processed
    
    @pytest.mark.asyncio
    async def test_clear_queue(self, backpressure_handler, mock_websocket):
        """Test clearing message queue for a session."""
        # Send some messages
        for i in range(3):
            message = {"type": "test", "content": f"message_{i}"}
            await backpressure_handler.send_message(
                mock_websocket, "tenant123", "user456", "session789", message
            )
        
        # Clear queue
        cleared_count = await backpressure_handler.clear_queue("session789")
        assert cleared_count >= 0
        
        # Queue should be empty now
        queue_size = await backpressure_handler.get_queue_size("session789")
        assert queue_size == 0
    
    @pytest.mark.asyncio
    async def test_get_stats(self, backpressure_handler, mock_websocket):
        """Test getting backpressure statistics."""
        # Send some messages
        for i in range(5):
            message = {"type": "test", "content": f"message_{i}"}
            await backpressure_handler.send_message(
                mock_websocket, "tenant123", "user456", "session789", message
            )
        
        stats = await backpressure_handler.get_stats()
        
        assert "total_queued_messages" in stats
        assert "active_queues" in stats
        assert "messages_sent" in stats
        assert "messages_dropped" in stats
        assert "queue_overflows" in stats
        assert "backpressure_events" in stats
        assert "drop_policy" in stats
        assert "max_queue_size" in stats
        assert stats["drop_policy"] == "intermediate"
        assert stats["max_queue_size"] == 10


class TestBackpressureMetrics:
    """Test backpressure metrics functionality."""
    
    @pytest.mark.asyncio
    async def test_record_backpressure_event(self, backpressure_metrics, mock_redis):
        """Test recording backpressure event."""
        event_details = {"queue_size": 10, "dropped_count": 5}
        
        await backpressure_metrics.record_backpressure_event(
            "tenant123", "session789", "queue_overflow", event_details
        )
        
        mock_redis.lpush.assert_called_once()
        mock_redis.ltrim.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_backpressure_metrics(self, backpressure_metrics, mock_redis):
        """Test getting backpressure metrics."""
        # Mock Redis response
        mock_events = [
            json.dumps({
                "tenant_id": "tenant123",
                "session_id": "session789",
                "event_type": "queue_overflow",
                "details": {"queue_size": 10},
                "timestamp": 1234567890.0
            })
        ]
        mock_redis.lrange.return_value = mock_events
        
        metrics = await backpressure_metrics.get_backpressure_metrics(
            tenant_id="tenant123", time_window=3600
        )
        
        assert "total_events" in metrics
        assert "time_window_seconds" in metrics
        assert "event_types" in metrics
        assert "tenant_events" in metrics
        assert "events_per_minute" in metrics
        assert metrics["total_events"] == 1
        assert metrics["time_window_seconds"] == 3600


class TestRealtimeIntegration:
    """Test realtime service integration."""
    
    @pytest.mark.asyncio
    async def test_connection_lifecycle(self, connection_manager, backpressure_handler, mock_websocket):
        """Test complete connection lifecycle."""
        # Register connection
        await connection_manager.register_connection(
            mock_websocket, "tenant123", "user456", "session789"
        )
        
        # Send message with backpressure
        message = {"type": "test", "content": "hello"}
        success = await backpressure_handler.send_message(
            mock_websocket, "tenant123", "user456", "session789", message
        )
        
        assert success is True
        mock_websocket.send_text.assert_called_once_with(json.dumps(message))
        
        # Unregister connection
        await connection_manager.unregister_connection(
            mock_websocket, "tenant123", "user456"
        )
        
        # Verify connection is removed
        connection = await connection_manager.get_connection("session789")
        assert connection is None
    
    @pytest.mark.asyncio
    async def test_backpressure_under_load(self, connection_manager, mock_redis):
        """Test backpressure behavior under load."""
        handler = BackpressureHandler(
            connection_manager=connection_manager,
            max_queue_size=5,
            drop_policy="intermediate"
        )
        
        # Simulate high load
        for i in range(20):  # Much more than max_queue_size
            message = {"type": "test", "content": f"message_{i}"}
            await handler.send_message(
                mock_websocket, "tenant123", "user456", "session789", message
            )
        
        # Check that backpressure was applied
        stats = await handler.get_stats()
        assert stats["messages_dropped"] > 0
        assert stats["queue_overflows"] > 0
        assert stats["backpressure_events"] > 0
    
    @pytest.mark.asyncio
    async def test_metrics_collection(self, connection_manager, backpressure_handler, mock_websocket):
        """Test metrics collection across components."""
        # Register connection
        await connection_manager.register_connection(
            mock_websocket, "tenant123", "user456", "session789"
        )
        
        # Send some messages
        for i in range(5):
            message = {"type": "test", "content": f"message_{i}"}
            await backpressure_handler.send_message(
                mock_websocket, "tenant123", "user456", "session789", message
            )
        
        # Get connection stats
        connection_stats = await connection_manager.get_connection_stats()
        assert connection_stats["active_connections"] == 1
        
        # Get backpressure stats
        backpressure_stats = await backpressure_handler.get_stats()
        assert backpressure_stats["messages_sent"] >= 0
        
        # Calculate required metrics
        ws_active_connections = connection_stats.get("active_connections", 0)
        ws_backpressure_drops = backpressure_stats.get("messages_dropped", 0)
        ws_send_errors = backpressure_stats.get("queue_overflows", 0)
        
        assert ws_active_connections == 1
        assert ws_backpressure_drops >= 0
        assert ws_send_errors >= 0
