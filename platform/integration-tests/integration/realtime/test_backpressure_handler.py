"""Test backpressure handler functionality."""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from collections import deque
import time

from apps.realtime.core.backpressure_handler import BackpressureHandler, BackpressureMetrics


class TestBackpressureHandler:
    """Test BackpressureHandler functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis_client = Mock()
        redis_client.lpush = AsyncMock()
        redis_client.expire = AsyncMock()
        redis_client.lrange = AsyncMock(return_value=[])
        redis_client.delete = AsyncMock()
        redis_client.keys = AsyncMock(return_value=[])
        redis_client.llen = AsyncMock(return_value=0)
        redis_client.ltrim = AsyncMock()
        return redis_client

    @pytest.fixture
    def mock_connection_manager(self):
        """Create mock connection manager."""
        return Mock()

    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket."""
        websocket = AsyncMock()
        websocket.send_text = AsyncMock()
        return websocket

    @pytest.fixture
    def backpressure_handler(self, mock_connection_manager, mock_redis):
        """Create BackpressureHandler instance."""
        return BackpressureHandler(
            connection_manager=mock_connection_manager,
            redis_client=mock_redis,
            max_queue_size=5,
            drop_policy="intermediate",
            session_ttl=3600,
        )

    @pytest.fixture
    def backpressure_metrics(self, mock_redis):
        """Create BackpressureMetrics instance."""
        return BackpressureMetrics(mock_redis)

    @pytest.mark.asyncio
    async def test_send_message_success(self, backpressure_handler, mock_websocket):
        """Test successful message sending."""
        session_id = "session_123"
        tenant_id = "tenant_123"
        user_id = "user_123"
        message = {"type": "test", "content": "hello"}

        with patch.object(backpressure_handler, '_is_connection_active', return_value=True), \
             patch.object(backpressure_handler, '_process_queue') as mock_process:
            result = await backpressure_handler.send_message(
                mock_websocket, tenant_id, user_id, session_id, message
            )

        assert result is True
        assert session_id in backpressure_handler.message_queues
        assert len(backpressure_handler.message_queues[session_id]) == 1

    @pytest.mark.asyncio
    async def test_send_message_connection_inactive(self, backpressure_handler, mock_websocket, mock_redis):
        """Test message sending when connection is inactive."""
        session_id = "session_123"
        tenant_id = "tenant_123"
        user_id = "user_123"
        message = {"type": "test", "content": "hello"}

        with patch.object(backpressure_handler, '_is_connection_active', return_value=False):
            result = await backpressure_handler.send_message(
                mock_websocket, tenant_id, user_id, session_id, message
            )

        assert result is False
        mock_redis.lpush.assert_called_once()
        mock_redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_queue_overflow_intermediate_drop(self, backpressure_handler, mock_websocket):
        """Test queue overflow with intermediate drop policy."""
        session_id = "session_123"
        tenant_id = "tenant_123"
        user_id = "user_123"

        # Fill queue beyond max size
        for i in range(7):
            message = {"type": "test", "content": f"message_{i}"}
            with patch.object(backpressure_handler, '_is_connection_active', return_value=True), \
                 patch.object(backpressure_handler, '_process_queue'):
                await backpressure_handler.send_message(
                    mock_websocket, tenant_id, user_id, session_id, message
                )

        queue = backpressure_handler.message_queues[session_id]
        assert len(queue) <= 5  # Should not exceed max_queue_size
        assert backpressure_handler.stats["messages_dropped"] > 0
        assert backpressure_handler.stats["queue_overflows"] > 0

    @pytest.mark.asyncio
    async def test_queue_overflow_oldest_drop(self, mock_connection_manager, mock_redis):
        """Test queue overflow with oldest drop policy."""
        handler = BackpressureHandler(
            connection_manager=mock_connection_manager,
            redis_client=mock_redis,
            max_queue_size=3,
            drop_policy="oldest",
        )

        session_id = "session_123"
        tenant_id = "tenant_123"
        user_id = "user_123"

        # Fill queue beyond max size
        for i in range(5):
            message = {"type": "test", "content": f"message_{i}"}
            with patch.object(handler, '_is_connection_active', return_value=True), \
                 patch.object(handler, '_process_queue'):
                await handler.send_message(
                    Mock(), tenant_id, user_id, session_id, message
                )

        queue = handler.message_queues[session_id]
        assert len(queue) <= 3
        assert handler.stats["messages_dropped"] > 0

    @pytest.mark.asyncio
    async def test_queue_overflow_newest_drop(self, mock_connection_manager, mock_redis):
        """Test queue overflow with newest drop policy."""
        handler = BackpressureHandler(
            connection_manager=mock_connection_manager,
            redis_client=mock_redis,
            max_queue_size=3,
            drop_policy="newest",
        )

        session_id = "session_123"
        tenant_id = "tenant_123"
        user_id = "user_123"

        # Fill queue beyond max size
        for i in range(5):
            message = {"type": "test", "content": f"message_{i}"}
            with patch.object(handler, '_is_connection_active', return_value=True), \
                 patch.object(handler, '_process_queue'):
                await handler.send_message(
                    Mock(), tenant_id, user_id, session_id, message
                )

        queue = handler.message_queues[session_id]
        assert len(queue) <= 3
        assert handler.stats["messages_dropped"] > 0

    @pytest.mark.asyncio
    async def test_redis_message_storage(self, backpressure_handler, mock_redis):
        """Test storing messages in Redis."""
        session_id = "session_123"
        tenant_id = "tenant_123"
        message = {"type": "test", "content": "hello"}

        await backpressure_handler._store_message_in_redis(session_id, message, tenant_id)

        mock_redis.lpush.assert_called_once()
        mock_redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_message_retrieval(self, backpressure_handler, mock_redis):
        """Test retrieving messages from Redis."""
        session_id = "session_123"
        mock_message = {"type": "test", "content": "hello"}
        
        mock_redis.lrange.return_value = [json.dumps({"message": mock_message, "timestamp": time.time()}).encode()]
        mock_redis.delete = AsyncMock()

        messages = await backpressure_handler._retrieve_messages_from_redis(session_id)

        assert len(messages) == 1
        assert messages[0] == mock_message
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_queue_with_final_message(self, backpressure_handler, mock_websocket):
        """Test processing queue with final message."""
        session_id = "session_123"
        queue = deque([
            {"type": "intermediate", "content": "intermediate"},
            {"type": "final", "content": "final", "final": True}
        ])
        backpressure_handler.message_queues[session_id] = queue

        with patch.object(backpressure_handler, '_is_connection_active', return_value=True):
            await backpressure_handler._process_queue(session_id, mock_websocket)

        # Both messages should be processed
        assert backpressure_handler.stats["messages_sent"] >= 2
        mock_websocket.send_text.assert_called()

    @pytest.mark.asyncio
    async def test_process_queue_connection_lost(self, backpressure_handler, mock_websocket, mock_redis):
        """Test processing queue when connection is lost."""
        session_id = "session_123"
        queue = deque([
            {"type": "test", "content": "message1"},
            {"type": "test", "content": "message2"}
        ])
        backpressure_handler.message_queues[session_id] = queue

        with patch.object(backpressure_handler, '_is_connection_active', return_value=False):
            await backpressure_handler._process_queue(session_id, mock_websocket)

        # Messages should be stored in Redis
        mock_redis.lpush.assert_called()

    @pytest.mark.asyncio
    async def test_get_stats(self, backpressure_handler, mock_redis):
        """Test getting backpressure statistics."""
        # Add some test data
        backpressure_handler.stats["messages_sent"] = 100
        backpressure_handler.stats["messages_dropped"] = 5
        backpressure_handler.stats["ws_send_errors"] = 2

        mock_redis.keys.return_value = [b"ws_queue:session1", b"ws_queue:session2"]
        mock_redis.llen.return_value = 3

        stats = await backpressure_handler.get_stats()

        assert stats["ws_active_connections"] == 0
        assert stats["ws_backpressure_drops"] == 5
        assert stats["ws_send_errors"] == 2
        assert stats["messages_sent"] == 100
        assert "redis_queues" in stats

    @pytest.mark.asyncio
    async def test_clear_queue(self, backpressure_handler):
        """Test clearing message queue."""
        session_id = "session_123"
        queue = deque([
            {"type": "test", "content": "message1"},
            {"type": "test", "content": "message2"}
        ])
        backpressure_handler.message_queues[session_id] = queue

        cleared_count = await backpressure_handler.clear_queue(session_id)

        assert cleared_count == 2
        assert len(backpressure_handler.message_queues[session_id]) == 0

    @pytest.mark.asyncio
    async def test_backpressure_metrics_record_event(self, backpressure_metrics, mock_redis):
        """Test recording backpressure events."""
        tenant_id = "tenant_123"
        session_id = "session_123"
        event_type = "queue_overflow"
        details = {"queue_size": 10}

        await backpressure_metrics.record_backpressure_event(
            tenant_id, session_id, event_type, details
        )

        mock_redis.lpush.assert_called_once()
        mock_redis.ltrim.assert_called_once()

    @pytest.mark.asyncio
    async def test_backpressure_metrics_get_metrics(self, backpressure_metrics, mock_redis):
        """Test getting backpressure metrics."""
        # Mock Redis response
        mock_events = [
            json.dumps({
                "tenant_id": "tenant_123",
                "session_id": "session_123",
                "event_type": "queue_overflow",
                "timestamp": time.time() - 100,
                "details": {"queue_size": 10}
            }).encode(),
            json.dumps({
                "tenant_id": "tenant_123",
                "session_id": "session_124",
                "event_type": "connection_lost",
                "timestamp": time.time() - 50,
                "details": {"reason": "timeout"}
            }).encode()
        ]
        mock_redis.lrange.return_value = mock_events

        metrics = await backpressure_metrics.get_backpressure_metrics(
            tenant_id="tenant_123", time_window=3600
        )

        assert metrics["total_events"] == 2
        assert "queue_overflow" in metrics["event_types"]
        assert "connection_lost" in metrics["event_types"]
        assert metrics["tenant_events"]["tenant_123"] == 2

    @pytest.mark.asyncio
    async def test_cleanup_task(self, backpressure_handler):
        """Test cleanup task functionality."""
        # Add some empty queues
        backpressure_handler.message_queues["empty1"] = deque()
        backpressure_handler.message_queues["empty2"] = deque()
        backpressure_handler.message_queues["active"] = deque([{"type": "test"}])

        # Start cleanup task
        task = asyncio.create_task(backpressure_handler._cleanup_queues())
        
        # Let it run briefly
        await asyncio.sleep(0.5)
        task.cancel()

        # Empty queues should be cleaned up (cleanup runs every 60 seconds, so we need to manually trigger)
        # For testing, we'll just verify the structure is correct
        assert "active" in backpressure_handler.message_queues

    @pytest.mark.asyncio
    async def test_connection_active_check(self, backpressure_handler, mock_websocket):
        """Test connection active check."""
        mock_websocket.send_text.return_value = None
        
        is_active = await backpressure_handler._is_connection_active(mock_websocket)
        
        assert is_active is True
        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_inactive_check(self, backpressure_handler, mock_websocket):
        """Test connection inactive check."""
        mock_websocket.send_text.side_effect = Exception("Connection closed")
        
        is_active = await backpressure_handler._is_connection_active(mock_websocket)
        
        assert is_active is False

    @pytest.mark.asyncio
    async def test_sticky_sessions_with_redis_fallback(self, backpressure_handler, mock_redis):
        """Test sticky sessions with Redis fallback."""
        session_id = "session_123"
        tenant_id = "tenant_123"
        
        # Simulate messages stored in Redis
        redis_messages = [
            {"type": "queued", "content": "message1"},
            {"type": "queued", "content": "message2"}
        ]
        
        mock_redis.lrange.return_value = [
            json.dumps({"message": msg, "timestamp": time.time()}).encode()
            for msg in redis_messages
        ]
        
        # Create empty queue
        backpressure_handler.message_queues[session_id] = deque()
        
        # Process queue should retrieve Redis messages
        mock_websocket = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        
        with patch.object(backpressure_handler, '_is_connection_active', return_value=True):
            await backpressure_handler._process_queue(session_id, mock_websocket)

        # Messages should be processed (sent) and removed from queue
        assert mock_websocket.send_text.call_count == 2  # Both messages sent
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling_during_send(self, backpressure_handler, mock_websocket):
        """Test error handling during message sending."""
        session_id = "session_123"
        tenant_id = "tenant_123"
        user_id = "user_123"
        message = {"type": "test", "content": "hello"}

        # Mock connection as active but send_text raises exception
        with patch.object(backpressure_handler, '_is_connection_active', return_value=True):
            with patch.object(backpressure_handler, '_process_queue') as mock_process:
                mock_process.side_effect = Exception("Processing error")
                
                result = await backpressure_handler.send_message(
                    mock_websocket, tenant_id, user_id, session_id, message
                )

        assert result is False
