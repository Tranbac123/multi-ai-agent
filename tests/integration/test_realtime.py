"""Integration tests for realtime functionality."""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch
from hypothesis import given, strategies as st

from apps.realtime_service.core.websocket_manager import WebSocketManager
from apps.realtime_service.core.backpressure_handler import BackpressureHandler
from apps.realtime_service.core.message_processor import MessageProcessor


class TestWebSocketBackpressure:
    """Test WebSocket backpressure handling."""

    @pytest.mark.asyncio
    async def test_slow_client_drop_intermediates(self):
        """Test dropping intermediate messages for slow clients."""
        manager = WebSocketManager()
        handler = BackpressureHandler(max_queue_size=5)

        # Simulate slow client
        slow_client = AsyncMock()
        slow_client.send = AsyncMock(side_effect=asyncio.sleep(0.1))

        # Send multiple messages rapidly
        messages = [
            {"type": "intermediate", "content": f"Message {i}"} for i in range(10)
        ]

        # Process messages
        for msg in messages:
            await handler.handle_message(slow_client, msg)

        # Should drop intermediate messages, keep only final
        assert handler.dropped_messages > 0
        assert handler.queue_size <= handler.max_queue_size

    @pytest.mark.asyncio
    async def test_deliver_final_message(self):
        """Test that final message is always delivered."""
        manager = WebSocketManager()
        handler = BackpressureHandler(max_queue_size=3)

        slow_client = AsyncMock()
        slow_client.send = AsyncMock(side_effect=asyncio.sleep(0.1))

        # Send intermediate and final messages
        intermediate_messages = [
            {"type": "intermediate", "content": f"Step {i}"} for i in range(5)
        ]

        final_message = {"type": "final", "content": "Complete response"}

        # Process all messages
        for msg in intermediate_messages + [final_message]:
            await handler.handle_message(slow_client, msg)

        # Final message should be delivered
        assert slow_client.send.called
        final_calls = [
            call
            for call in slow_client.send.call_args_list
            if call[0][0].get("type") == "final"
        ]
        assert len(final_calls) > 0

    @pytest.mark.asyncio
    async def test_reconnect_resumes_session(self):
        """Test that reconnection resumes session."""
        manager = WebSocketManager()

        # Create initial session
        session_id = "session_001"
        tenant_id = "tenant_001"
        user_id = "user_001"

        # Store session data
        await manager.create_session(session_id, tenant_id, user_id)
        await manager.store_context(session_id, {"conversation": ["Hello", "Hi there"]})

        # Simulate disconnection
        await manager.disconnect_session(session_id)

        # Reconnect with same session ID
        new_client = AsyncMock()
        resumed_session = await manager.reconnect_session(session_id, new_client)

        assert resumed_session is not None
        assert resumed_session["session_id"] == session_id
        assert resumed_session["tenant_id"] == tenant_id
        assert resumed_session["user_id"] == user_id

        # Context should be restored
        context = await manager.get_context(session_id)
        assert context["conversation"] == ["Hello", "Hi there"]

    @pytest.mark.asyncio
    async def test_backpressure_queue_overflow(self):
        """Test backpressure queue overflow handling."""
        handler = BackpressureHandler(max_queue_size=2)

        slow_client = AsyncMock()
        slow_client.send = AsyncMock(side_effect=asyncio.sleep(1.0))

        # Send more messages than queue can handle
        messages = [
            {"type": "intermediate", "content": f"Message {i}"} for i in range(10)
        ]

        # Process messages
        for msg in messages:
            await handler.handle_message(slow_client, msg)

        # Should not exceed max queue size
        assert handler.queue_size <= handler.max_queue_size
        assert handler.dropped_messages > 0

    @pytest.mark.asyncio
    async def test_priority_message_handling(self):
        """Test priority message handling during backpressure."""
        handler = BackpressureHandler(max_queue_size=3)

        slow_client = AsyncMock()
        slow_client.send = AsyncMock(side_effect=asyncio.sleep(0.1))

        # Send regular and priority messages
        regular_messages = [
            {"type": "intermediate", "content": f"Regular {i}", "priority": "normal"}
            for i in range(5)
        ]

        priority_message = {
            "type": "urgent",
            "content": "Urgent message",
            "priority": "high",
        }

        # Process messages
        for msg in regular_messages + [priority_message]:
            await handler.handle_message(slow_client, msg)

        # Priority message should be delivered
        priority_calls = [
            call
            for call in slow_client.send.call_args_list
            if call[0][0].get("priority") == "high"
        ]
        assert len(priority_calls) > 0

    @pytest.mark.asyncio
    async def test_connection_health_monitoring(self):
        """Test connection health monitoring."""
        manager = WebSocketManager()

        # Create session
        session_id = "session_001"
        tenant_id = "tenant_001"
        user_id = "user_001"

        client = AsyncMock()
        await manager.create_session(session_id, tenant_id, user_id, client)

        # Simulate health check
        health_status = await manager.check_connection_health(session_id)

        assert health_status["connected"] is True
        assert health_status["last_activity"] is not None
        assert health_status["message_count"] >= 0

    @pytest.mark.asyncio
    async def test_session_cleanup(self):
        """Test session cleanup for disconnected clients."""
        manager = WebSocketManager()

        # Create multiple sessions
        sessions = [
            ("session_001", "tenant_001", "user_001"),
            ("session_002", "tenant_001", "user_002"),
            ("session_003", "tenant_002", "user_001"),
        ]

        for session_id, tenant_id, user_id in sessions:
            client = AsyncMock()
            await manager.create_session(session_id, tenant_id, user_id, client)

        # Disconnect one session
        await manager.disconnect_session("session_001")

        # Cleanup should remove disconnected session
        await manager.cleanup_disconnected_sessions()

        # Only active sessions should remain
        active_sessions = await manager.get_active_sessions()
        assert len(active_sessions) == 2
        assert "session_001" not in [s["session_id"] for s in active_sessions]

    @pytest.mark.asyncio
    async def test_message_ordering(self):
        """Test message ordering during backpressure."""
        handler = BackpressureHandler(max_queue_size=5)

        slow_client = AsyncMock()
        slow_client.send = AsyncMock(side_effect=asyncio.sleep(0.1))

        # Send messages with sequence numbers
        messages = [
            {"type": "intermediate", "content": f"Message {i}", "sequence": i}
            for i in range(10)
        ]

        # Process messages
        for msg in messages:
            await handler.handle_message(slow_client, msg)

        # Check that delivered messages maintain order
        delivered_messages = [call[0][0] for call in slow_client.send.call_args_list]
        sequences = [
            msg.get("sequence") for msg in delivered_messages if "sequence" in msg
        ]

        # Sequences should be in order
        for i in range(1, len(sequences)):
            assert sequences[i] >= sequences[i - 1]

    @pytest.mark.asyncio
    async def test_tenant_isolation(self):
        """Test tenant isolation in WebSocket connections."""
        manager = WebSocketManager()

        # Create sessions for different tenants
        session1 = await manager.create_session("session_001", "tenant_001", "user_001")
        session2 = await manager.create_session("session_002", "tenant_002", "user_001")

        # Store tenant-specific data
        await manager.store_context("session_001", {"tenant_data": "tenant1_data"})
        await manager.store_context("session_002", {"tenant_data": "tenant2_data"})

        # Retrieve contexts
        context1 = await manager.get_context("session_001")
        context2 = await manager.get_context("session_002")

        # Contexts should be isolated
        assert context1["tenant_data"] == "tenant1_data"
        assert context2["tenant_data"] == "tenant2_data"
        assert context1["tenant_data"] != context2["tenant_data"]

    @pytest.mark.asyncio
    async def test_message_processing_pipeline(self):
        """Test complete message processing pipeline."""
        processor = MessageProcessor()
        manager = WebSocketManager()

        # Create session
        session_id = "session_001"
        tenant_id = "tenant_001"
        user_id = "user_001"

        client = AsyncMock()
        await manager.create_session(session_id, tenant_id, user_id, client)

        # Process incoming message
        incoming_message = {
            "type": "user_message",
            "content": "Hello, I need help",
            "session_id": session_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
        }

        with patch.object(processor, "_process_message") as mock_process:
            mock_process.return_value = {
                "type": "agent_response",
                "content": "I can help you with that",
                "session_id": session_id,
            }

            result = await processor.process_message(incoming_message)

            assert result["type"] == "agent_response"
            assert result["content"] == "I can help you with that"
            assert result["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_error_handling_during_backpressure(self):
        """Test error handling during backpressure."""
        handler = BackpressureHandler(max_queue_size=3)

        # Client that fails to send
        failing_client = AsyncMock()
        failing_client.send = AsyncMock(side_effect=Exception("Send failed"))

        # Send messages
        messages = [
            {"type": "intermediate", "content": f"Message {i}"} for i in range(5)
        ]

        # Process messages - should handle errors gracefully
        for msg in messages:
            try:
                await handler.handle_message(failing_client, msg)
            except Exception:
                # Should handle errors gracefully
                pass

        # Should not crash and should track errors
        assert handler.error_count > 0
        assert handler.queue_size <= handler.max_queue_size
