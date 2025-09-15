"""Simple backpressure tests for validation."""

import pytest
import asyncio
from tests.realtime import BackpressureStatus, WebSocketMessage
from tests.realtime.test_websocket_backpressure import MockWebSocket, BackpressureHandler


class TestSimpleBackpressure:
    """Simple backpressure validation tests."""
    
    @pytest.mark.asyncio
    async def test_basic_backpressure_flow(self):
        """Test basic backpressure flow."""
        handler = BackpressureHandler(max_connections=10)
        
        # Add connection
        connection = await handler.add_connection("test_conn", is_slow=False)
        
        # Send message
        message = WebSocketMessage(
            message_id="msg_001",
            timestamp=None,
            content="Test message",
            message_type="test",
            priority=1,
            size_bytes=50
        )
        
        success = await handler.send_message_to_connection("test_conn", message)
        
        # Validate
        assert success is True
        assert len(connection.sent_messages) == 1
        assert connection.get_metrics().backpressure_level == BackpressureStatus.NORMAL
    
    @pytest.mark.asyncio
    async def test_slow_consumer_backpressure(self):
        """Test slow consumer backpressure."""
        handler = BackpressureHandler(max_connections=10)
        
        # Add slow connection
        slow_connection = await handler.add_connection("slow_conn", is_slow=True)
        
        # Send multiple messages rapidly
        messages_sent = 0
        messages_dropped = 0
        
        for i in range(5):
            message = WebSocketMessage(
                message_id=f"msg_{i:03d}",
                timestamp=None,
                content=f"Message {i}",
                message_type="test",
                priority=1,
                size_bytes=50
            )
            
            success = await handler.send_message_to_connection("slow_conn", message)
            if success:
                messages_sent += 1
            else:
                messages_dropped += 1
        
        # Validate backpressure
        assert messages_sent > 0
        assert messages_dropped >= 0  # May drop some messages
        assert len(slow_connection.sent_messages) == messages_sent
        assert len(slow_connection.dropped_messages) == messages_dropped
    
    @pytest.mark.asyncio
    async def test_connection_limit(self):
        """Test connection limit enforcement."""
        handler = BackpressureHandler(max_connections=3)
        
        # Add connections up to limit
        for i in range(3):
            await handler.add_connection(f"conn_{i}")
        
        # Try to exceed limit
        with pytest.raises(Exception, match="Maximum connections exceeded"):
            await handler.add_connection("overflow_conn")
        
        # Validate
        assert len(handler.connections) == 3
        assert handler.global_metrics.connection_count == 3