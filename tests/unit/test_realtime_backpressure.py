"""Tests for Realtime service backpressure handling with Redis session storage."""

import pytest
import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import WebSocket
from apps.realtime.core.backpressure_handler import (
    BackpressureHandler,
    BackpressureMetrics,
)
from apps.realtime.main import app


class TestBackpressureHandlerHardening:
    """Test backpressure handler with Redis session storage."""

    @pytest.fixture
    def redis_mock(self):
        """Create mock Redis client."""
        return AsyncMock()

    @pytest.fixture
    def connection_manager_mock(self):
        """Create mock connection manager."""
        return AsyncMock()

    @pytest.fixture
    def backpressure_handler(self, connection_manager_mock, redis_mock):
        """Create backpressure handler with mocks."""
        return BackpressureHandler(
            connection_manager=connection_manager_mock,
            redis_client=redis_mock,
            max_queue_size=10,
            drop_policy="intermediate",
            session_ttl=3600,
        )

    @pytest.fixture
    def websocket_mock(self):
        """Create mock WebSocket."""
        websocket = MagicMock(spec=WebSocket)
        websocket.send_text = AsyncMock()
        return websocket

    @pytest.mark.asyncio
    async def test_redis_message_storage(self, backpressure_handler, redis_mock):
        """Test storing messages in Redis when connection is lost."""
        session_id = "test_session"
        tenant_id = "test_tenant"
        message = {"type": "test", "content": "hello"}

        # Mock Redis responses
        redis_mock.lpush.return_value = 1
        redis_mock.expire.return_value = True

        # Store message in Redis
        await backpressure_handler._store_message_in_redis(
            session_id, message, tenant_id
        )

        # Verify Redis calls
        redis_mock.lpush.assert_called_once()
        redis_mock.expire.assert_called_once()

        # Verify statistics
        assert backpressure_handler.stats["backpressure_events"] == 1

    @pytest.mark.asyncio
    async def test_redis_message_retrieval(self, backpressure_handler, redis_mock):
        """Test retrieving messages from Redis."""
        session_id = "test_session"
        message_data = {
            "message": {"type": "test", "content": "hello"},
            "timestamp": time.time(),
            "tenant_id": "test_tenant",
            "session_id": session_id,
        }

        # Mock Redis responses
        redis_mock.lrange.return_value = [json.dumps(message_data).encode()]
        redis_mock.delete.return_value = 1

        # Retrieve messages
        messages = await backpressure_handler._retrieve_messages_from_redis(session_id)

        # Verify results
        assert len(messages) == 1
        assert messages[0] == {"type": "test", "content": "hello"}

        # Verify Redis calls
        redis_mock.lrange.assert_called_once()
        redis_mock.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_intermediate_message_dropping(
        self, backpressure_handler, websocket_mock
    ):
        """Test that intermediate messages are dropped under backpressure."""
        session_id = "test_session"
        tenant_id = "test_tenant"
        user_id = "test_user"

        # Mock connection as active
        websocket_mock.send_text = AsyncMock()

        # Fill queue beyond max size
        for i in range(15):  # More than max_queue_size of 10
            message = {
                "type": "intermediate" if i < 14 else "final",
                "content": f"message_{i}",
                "final": i == 14,
            }
            await backpressure_handler._add_to_queue(session_id, message)

        # Verify queue size is reduced due to dropping
        queue_size = await backpressure_handler.get_queue_size(session_id)
        assert queue_size <= 10  # Should be at max size

        # Verify statistics
        assert backpressure_handler.stats["messages_dropped"] > 0
        assert backpressure_handler.stats["queue_overflows"] > 0

    @pytest.mark.asyncio
    async def test_final_message_preservation(
        self, backpressure_handler, websocket_mock
    ):
        """Test that final messages are always preserved."""
        session_id = "test_session"
        tenant_id = "test_tenant"
        user_id = "test_user"

        # Mock connection as active
        websocket_mock.send_text = AsyncMock()

        # Add messages with final message at the end
        messages = [
            {"type": "intermediate", "content": "msg1"},
            {"type": "intermediate", "content": "msg2"},
            {"type": "final", "content": "final_msg", "final": True},
        ]

        for message in messages:
            await backpressure_handler._add_to_queue(session_id, message)

        # Process queue
        await backpressure_handler._process_queue(session_id, websocket_mock)

        # Verify final message was sent
        websocket_mock.send_text.assert_called()
        sent_messages = [call[0][0] for call in websocket_mock.send_text.call_args_list]
        sent_texts = [json.loads(msg) for msg in sent_messages]

        # Should have sent the final message
        final_messages = [msg for msg in sent_texts if msg.get("type") == "final"]
        assert len(final_messages) > 0

    @pytest.mark.asyncio
    async def test_connection_lost_message_storage(
        self, backpressure_handler, websocket_mock, redis_mock
    ):
        """Test that messages are stored in Redis when connection is lost."""
        session_id = "test_session"
        tenant_id = "test_tenant"
        user_id = "test_user"

        # Mock connection as inactive
        websocket_mock.send_text.side_effect = Exception("Connection lost")
        redis_mock.lpush.return_value = 1
        redis_mock.expire.return_value = True

        # Add message to queue
        message = {"type": "test", "content": "hello"}
        await backpressure_handler._add_to_queue(session_id, message)

        # Process queue (should fail and store in Redis)
        await backpressure_handler._process_queue(session_id, websocket_mock)

        # Verify message was stored in Redis
        redis_mock.lpush.assert_called()
        redis_mock.expire.assert_called()

    @pytest.mark.asyncio
    async def test_metrics_collection(self, backpressure_handler, redis_mock):
        """Test that proper metrics are collected."""
        # Mock Redis responses
        redis_mock.keys.return_value = [b"ws_queue:session1", b"ws_queue:session2"]
        redis_mock.llen.return_value = 5

        # Simulate some activity
        backpressure_handler.stats["messages_sent"] = 100
        backpressure_handler.stats["messages_dropped"] = 10
        backpressure_handler.stats["ws_send_errors"] = 2

        # Get statistics
        stats = await backpressure_handler.get_stats()

        # Verify metrics
        assert stats["ws_active_connections"] == 0  # No active connections
        assert stats["ws_backpressure_drops"] == 10
        assert stats["ws_send_errors"] == 2
        assert stats["messages_sent"] == 100
        assert stats["redis_queues"]["total_redis_queues"] == 2
        assert stats["redis_queues"]["total_redis_messages"] == 10


class TestRealtimeServiceIntegration:
    """Test realtime service integration."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "realtime"

    def test_metrics_endpoint(self, client):
        """Test metrics endpoint."""
        response = client.get("/metrics")
        # Should return 500 since Redis is not available in test
        assert response.status_code == 500


class TestBackpressureMetrics:
    """Test backpressure metrics collection."""

    @pytest.fixture
    def redis_mock(self):
        """Create mock Redis client."""
        return AsyncMock()

    @pytest.fixture
    def metrics_collector(self, redis_mock):
        """Create metrics collector with mock Redis."""
        return BackpressureMetrics(redis_mock)

    @pytest.mark.asyncio
    async def test_record_backpressure_event(self, metrics_collector, redis_mock):
        """Test recording backpressure events."""
        redis_mock.lpush.return_value = 1
        redis_mock.ltrim.return_value = True

        # Record event
        await metrics_collector.record_backpressure_event(
            tenant_id="test_tenant",
            session_id="test_session",
            event_type="queue_overflow",
            details={"queue_size": 1000},
        )

        # Verify Redis calls
        redis_mock.lpush.assert_called_once()
        redis_mock.ltrim.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_backpressure_metrics(self, metrics_collector, redis_mock):
        """Test getting backpressure metrics."""
        # Mock event data
        event_data = {
            "tenant_id": "test_tenant",
            "session_id": "test_session",
            "event_type": "queue_overflow",
            "details": {"queue_size": 1000},
            "timestamp": time.time() - 100,  # 100 seconds ago
        }

        redis_mock.lrange.return_value = [json.dumps(event_data).encode()]

        # Get metrics
        metrics = await metrics_collector.get_backpressure_metrics(
            tenant_id="test_tenant", time_window=3600
        )

        # Verify metrics
        assert metrics["total_events"] == 1
        assert metrics["event_types"]["queue_overflow"] == 1
        assert metrics["tenant_events"]["test_tenant"] == 1
        assert metrics["time_window_seconds"] == 3600


class TestRealtimePerformance:
    """Test realtime service performance under load."""

    @pytest.fixture
    def backpressure_handler(self):
        """Create backpressure handler for performance tests."""
        redis_mock = AsyncMock()
        connection_manager_mock = AsyncMock()

        return BackpressureHandler(
            connection_manager=connection_manager_mock,
            redis_client=redis_mock,
            max_queue_size=100,
            drop_policy="intermediate",
            session_ttl=3600,
        )

    @pytest.mark.asyncio
    async def test_high_concurrency_message_processing(self, backpressure_handler):
        """Test message processing under high concurrency."""
        session_id = "test_session"
        tenant_id = "test_tenant"
        user_id = "test_user"

        # Create many messages
        num_messages = 1000
        messages = [
            {
                "type": "intermediate" if i < num_messages - 1 else "final",
                "content": f"message_{i}",
                "final": i == num_messages - 1,
            }
            for i in range(num_messages)
        ]

        # Process messages concurrently
        start_time = time.time()

        tasks = []
        for message in messages:
            task = backpressure_handler._add_to_queue(session_id, message)
            tasks.append(task)

        await asyncio.gather(*tasks)

        processing_time = time.time() - start_time

        # Verify performance
        assert processing_time < 1.0  # Should process 1000 messages in under 1 second

        # Verify queue size is reasonable (due to backpressure)
        queue_size = await backpressure_handler.get_queue_size(session_id)
        assert queue_size <= 100  # Should be at max queue size

        # Verify statistics
        stats = await backpressure_handler.get_stats()
        assert stats["messages_dropped"] > 0  # Should have dropped some messages
        assert stats["queue_overflows"] > 0  # Should have had overflows


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
