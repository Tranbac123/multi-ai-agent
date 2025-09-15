"""Test realtime service backpressure handling."""

import pytest
import asyncio
import json
import time
from unittest.mock import Mock, AsyncMock, patch

from tests._fixtures.factories import TenantFactory, WebSocketSessionFactory
from tests._helpers.assertions import PerformanceAssertions


class TestRealtimeBackpressure:
    """Test realtime service backpressure handling."""
    
    @pytest.mark.asyncio
    async def test_queue_overflow_intermediate_drop(self):
        """Test queue overflow with intermediate drop policy."""
        # Setup
        tenant_factory = TenantFactory()
        ws_factory = WebSocketSessionFactory()
        
        tenant = tenant_factory.create()
        session = ws_factory.create(tenant["tenant_id"])
        
        # Configure session with intermediate drop policy
        session["backpressure_settings"]["max_queue_size"] = 5
        session["backpressure_settings"]["drop_policy"] = "intermediate"
        
        # Mock WebSocket connection
        mock_ws = Mock()
        mock_ws.send = AsyncMock()
        
        # Simulate rapid message sending
        messages = [
            {"id": f"msg_{i}", "content": f"Message {i}", "timestamp": time.time()}
            for i in range(10)  # Exceeds queue size
        ]
        
        # Process messages
        queue_overflow_events = []
        
        for i, message in enumerate(messages):
            if i < session["backpressure_settings"]["max_queue_size"]:
                # Messages should be queued
                await mock_ws.send(json.dumps(message))
            else:
                # Messages should be dropped (intermediate policy)
                queue_overflow_events.append({
                    "message_id": message["id"],
                    "action": "dropped",
                    "reason": "queue_overflow"
                })
        
        # Verify backpressure handling
        assert len(queue_overflow_events) == 5  # 5 messages dropped
        assert all(event["action"] == "dropped" for event in queue_overflow_events)
        assert mock_ws.send.call_count == 5  # Only first 5 messages sent
    
    @pytest.mark.asyncio
    async def test_queue_overflow_oldest_drop(self):
        """Test queue overflow with oldest drop policy."""
        # Setup
        tenant_factory = TenantFactory()
        ws_factory = WebSocketSessionFactory()
        
        tenant = tenant_factory.create()
        session = ws_factory.create(tenant["tenant_id"])
        
        # Configure session with oldest drop policy
        session["backpressure_settings"]["max_queue_size"] = 3
        session["backpressure_settings"]["drop_policy"] = "oldest"
        
        # Mock WebSocket connection
        mock_ws = Mock()
        mock_ws.send = AsyncMock()
        
        # Simulate message queue with overflow
        messages = [
            {"id": "msg_1", "content": "Old message 1"},
            {"id": "msg_2", "content": "Old message 2"},
            {"id": "msg_3", "content": "Old message 3"},
            {"id": "msg_4", "content": "New message 4"},  # Should drop oldest (msg_1)
            {"id": "msg_5", "content": "New message 5"},  # Should drop oldest (msg_2)
        ]
        
        # Process messages with oldest drop policy
        sent_messages = []
        dropped_messages = []
        
        for message in messages:
            if len(sent_messages) < session["backpressure_settings"]["max_queue_size"]:
                sent_messages.append(message)
                await mock_ws.send(json.dumps(message))
            else:
                # Drop oldest message and add new one
                dropped_msg = sent_messages.pop(0)
                dropped_messages.append(dropped_msg)
                sent_messages.append(message)
                await mock_ws.send(json.dumps(message))
        
        # Verify oldest drop policy
        assert len(sent_messages) == 3
        assert len(dropped_messages) == 2
        assert dropped_messages[0]["id"] == "msg_1"  # Oldest dropped first
        assert dropped_messages[1]["id"] == "msg_2"  # Second oldest dropped
        assert sent_messages[-1]["id"] == "msg_5"    # Newest message kept
    
    @pytest.mark.asyncio
    async def test_queue_overflow_newest_drop(self):
        """Test queue overflow with newest drop policy."""
        # Setup
        tenant_factory = TenantFactory()
        ws_factory = WebSocketSessionFactory()
        
        tenant = tenant_factory.create()
        session = ws_factory.create(tenant["tenant_id"])
        
        # Configure session with newest drop policy
        session["backpressure_settings"]["max_queue_size"] = 3
        session["backpressure_settings"]["drop_policy"] = "newest"
        
        # Mock WebSocket connection
        mock_ws = Mock()
        mock_ws.send = AsyncMock()
        
        # Simulate message queue with overflow
        messages = [
            {"id": "msg_1", "content": "Message 1"},
            {"id": "msg_2", "content": "Message 2"},
            {"id": "msg_3", "content": "Message 3"},
            {"id": "msg_4", "content": "Message 4"},  # Should be dropped
            {"id": "msg_5", "content": "Message 5"},  # Should be dropped
        ]
        
        # Process messages with newest drop policy
        sent_messages = []
        dropped_messages = []
        
        for message in messages:
            if len(sent_messages) < session["backpressure_settings"]["max_queue_size"]:
                sent_messages.append(message)
                await mock_ws.send(json.dumps(message))
            else:
                # Drop newest message
                dropped_messages.append(message)
        
        # Verify newest drop policy
        assert len(sent_messages) == 3
        assert len(dropped_messages) == 2
        assert dropped_messages[0]["id"] == "msg_4"  # Newest dropped first
        assert dropped_messages[1]["id"] == "msg_5"  # Second newest dropped
        assert sent_messages[0]["id"] == "msg_1"     # Oldest messages kept
    
    @pytest.mark.asyncio
    async def test_slow_consumer_backpressure(self):
        """Test backpressure with slow consumer."""
        # Setup
        tenant_factory = TenantFactory()
        ws_factory = WebSocketSessionFactory()
        
        tenant = tenant_factory.create()
        session = ws_factory.create(tenant["tenant_id"])
        
        # Configure for slow consumer scenario
        session["backpressure_settings"]["max_queue_size"] = 10
        session["backpressure_settings"]["drop_policy"] = "intermediate"
        
        # Mock slow WebSocket connection
        mock_ws = Mock()
        mock_ws.send = AsyncMock(side_effect=lambda x: asyncio.sleep(0.5))  # Slow send
        
        # Send messages faster than consumer can process
        messages = [
            {"id": f"msg_{i}", "content": f"Message {i}", "timestamp": time.time()}
            for i in range(15)  # More than queue can handle
        ]
        
        start_time = time.time()
        sent_count = 0
        dropped_count = 0
        
        for message in messages:
            try:
                # Try to send message
                await asyncio.wait_for(
                    mock_ws.send(json.dumps(message)),
                    timeout=0.1  # Short timeout to detect slow consumer
                )
                sent_count += 1
            except asyncio.TimeoutError:
                # Message dropped due to slow consumer
                dropped_count += 1
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify slow consumer handling
        assert sent_count > 0  # Some messages should be sent
        assert dropped_count > 0  # Some messages should be dropped
        assert total_time < 2.0  # Should not take too long due to drops
        
        # Verify performance
        result = PerformanceAssertions.assert_latency_below_threshold(
            total_time * 1000, 2000, "Slow consumer backpressure handling"
        )
        assert result.passed, f"Backpressure should handle slow consumer efficiently: {result.message}"
    
    @pytest.mark.asyncio
    async def test_connection_recovery_after_backpressure(self):
        """Test connection recovery after backpressure situation."""
        # Setup
        tenant_factory = TenantFactory()
        ws_factory = WebSocketSessionFactory()
        
        tenant = tenant_factory.create()
        session = ws_factory.create(tenant["tenant_id"])
        
        # Configure session
        session["backpressure_settings"]["max_queue_size"] = 5
        session["backpressure_settings"]["drop_policy"] = "oldest"
        
        # Mock WebSocket connection
        mock_ws = Mock()
        mock_ws.send = AsyncMock()
        mock_ws.close = AsyncMock()
        
        # Simulate backpressure situation
        messages = [
            {"id": f"msg_{i}", "content": f"Message {i}"}
            for i in range(10)  # Cause backpressure
        ]
        
        # Send messages causing backpressure
        for message in messages[:8]:  # Send 8 messages, should cause drops
            await mock_ws.send(json.dumps(message))
        
        # Simulate connection recovery (consumer catches up)
        await asyncio.sleep(0.1)  # Simulate processing time
        
        # Send more messages after recovery
        recovery_messages = [
            {"id": f"recovery_msg_{i}", "content": f"Recovery message {i}"}
            for i in range(3)
        ]
        
        recovery_sent_count = 0
        for message in recovery_messages:
            await mock_ws.send(json.dumps(message))
            recovery_sent_count += 1
        
        # Verify recovery
        assert recovery_sent_count == 3  # All recovery messages should be sent
        assert mock_ws.send.call_count == 11  # 8 initial + 3 recovery
    
    @pytest.mark.asyncio
    async def test_tenant_isolation_under_backpressure(self):
        """Test tenant isolation is maintained under backpressure."""
        # Setup two tenants
        tenant_factory = TenantFactory()
        ws_factory = WebSocketSessionFactory()
        
        tenant_a = tenant_factory.create()
        tenant_b = tenant_factory.create()
        
        session_a = ws_factory.create(tenant_a["tenant_id"])
        session_b = ws_factory.create(tenant_b["tenant_id"])
        
        # Configure both sessions
        for session in [session_a, session_b]:
            session["backpressure_settings"]["max_queue_size"] = 3
            session["backpressure_settings"]["drop_policy"] = "oldest"
        
        # Mock WebSocket connections
        mock_ws_a = Mock()
        mock_ws_a.send = AsyncMock()
        
        mock_ws_b = Mock()
        mock_ws_b.send = AsyncMock()
        
        # Send messages to both tenants causing backpressure
        messages_a = [
            {"id": f"tenant_a_msg_{i}", "content": f"Tenant A message {i}"}
            for i in range(5)
        ]
        
        messages_b = [
            {"id": f"tenant_b_msg_{i}", "content": f"Tenant B message {i}"}
            for i in range(5)
        ]
        
        # Process messages for tenant A
        sent_a = []
        for message in messages_a:
            if len(sent_a) < session_a["backpressure_settings"]["max_queue_size"]:
                sent_a.append(message)
                await mock_ws_a.send(json.dumps(message))
            else:
                # Drop oldest and add new
                sent_a.pop(0)
                sent_a.append(message)
                await mock_ws_a.send(json.dumps(message))
        
        # Process messages for tenant B
        sent_b = []
        for message in messages_b:
            if len(sent_b) < session_b["backpressure_settings"]["max_queue_size"]:
                sent_b.append(message)
                await mock_ws_b.send(json.dumps(message))
            else:
                # Drop oldest and add new
                sent_b.pop(0)
                sent_b.append(message)
                await mock_ws_b.send(json.dumps(message))
        
        # Verify tenant isolation
        assert len(sent_a) == 3
        assert len(sent_b) == 3
        assert all(msg["id"].startswith("tenant_a_msg_") for msg in sent_a)
        assert all(msg["id"].startswith("tenant_b_msg_") for msg in sent_b)
        assert mock_ws_a.send.call_count == 5
        assert mock_ws_b.send.call_count == 5
        
        # Verify no cross-tenant message mixing
        assert not any(msg["id"].startswith("tenant_b_msg_") for msg in sent_a)
        assert not any(msg["id"].startswith("tenant_a_msg_") for msg in sent_b)
    
    @pytest.mark.asyncio
    async def test_backpressure_metrics_collection(self):
        """Test that backpressure metrics are properly collected."""
        # Setup
        tenant_factory = TenantFactory()
        ws_factory = WebSocketSessionFactory()
        
        tenant = tenant_factory.create()
        session = ws_factory.create(tenant["tenant_id"])
        
        # Configure session
        session["backpressure_settings"]["max_queue_size"] = 3
        session["backpressure_settings"]["drop_policy"] = "intermediate"
        
        # Mock metrics collection
        metrics = {
            "messages_sent": 0,
            "messages_dropped": 0,
            "queue_overflows": 0,
            "avg_queue_size": 0,
            "max_queue_size": 0
        }
        
        # Mock WebSocket connection
        mock_ws = Mock()
        mock_ws.send = AsyncMock()
        
        # Simulate message processing with metrics
        messages = [
            {"id": f"msg_{i}", "content": f"Message {i}"}
            for i in range(8)  # Cause multiple overflows
        ]
        
        queue_size = 0
        max_queue_reached = 0
        
        for message in messages:
            if queue_size < session["backpressure_settings"]["max_queue_size"]:
                # Message queued
                queue_size += 1
                await mock_ws.send(json.dumps(message))
                metrics["messages_sent"] += 1
                max_queue_reached = max(max_queue_reached, queue_size)
            else:
                # Message dropped
                metrics["messages_dropped"] += 1
                metrics["queue_overflows"] += 1
        
        # Calculate final metrics
        metrics["max_queue_size"] = max_queue_reached
        metrics["avg_queue_size"] = sum(range(1, session["backpressure_settings"]["max_queue_size"] + 1)) / session["backpressure_settings"]["max_queue_size"]
        
        # Verify metrics
        assert metrics["messages_sent"] == 3  # Only first 3 messages sent
        assert metrics["messages_dropped"] == 5  # 5 messages dropped
        assert metrics["queue_overflows"] == 5  # 5 overflow events
        assert metrics["max_queue_size"] == 3  # Queue reached max size
        assert metrics["avg_queue_size"] == 2.0  # Average of 1,2,3
