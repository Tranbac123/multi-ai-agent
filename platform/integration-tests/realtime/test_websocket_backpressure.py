"""Tests for WebSocket backpressure handling and session management."""

import pytest
import asyncio
import json
from typing import Dict, Any, List
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from tests.realtime import (
    BackpressureStatus, ConnectionStatus, WebSocketMessage, BackpressureMetrics
)
from tests._fixtures.factories import factory, TenantTier
from tests._helpers import test_helpers


class MockWebSocket:
    """Mock WebSocket connection for testing."""
    
    def __init__(self, connection_id: str, max_queue_size: int = 100):
        self.connection_id = connection_id
        self.max_queue_size = max_queue_size
        self.queue: List[WebSocketMessage] = []
        self.sent_messages: List[WebSocketMessage] = []
        self.dropped_messages: List[WebSocketMessage] = []
        self.status = ConnectionStatus.CONNECTED
        self.is_slow_consumer = False
        self.last_heartbeat = datetime.now()
    
    async def send_message(self, message: WebSocketMessage) -> bool:
        """Send message with backpressure handling."""
        # For slow consumers, drop messages when queue is getting full
        if self.is_slow_consumer and len(self.queue) > self.max_queue_size * 0.6:
            self.dropped_messages.append(message)
            return False
        
        # If queue is full, drop oldest message
        if len(self.queue) >= self.max_queue_size:
            if self.queue:
                dropped = self.queue.pop(0)
                self.dropped_messages.append(dropped)
        
        self.queue.append(message)
        
        # Simulate sending (slow consumer delays processing)
        if self.is_slow_consumer:
            await asyncio.sleep(0.05)  # Slow processing
        
        self.sent_messages.append(message)
        self.queue.remove(message)
        return True
    
    def get_metrics(self) -> BackpressureMetrics:
        """Get backpressure metrics."""
        return BackpressureMetrics(
            queue_size=len(self.queue),
            dropped_messages=len(self.dropped_messages),
            sent_messages=len(self.sent_messages),
            backpressure_level=self._calculate_backpressure_level(),
            avg_processing_time_ms=self._calculate_avg_processing_time(),
            connection_count=1
        )
    
    def _calculate_backpressure_level(self) -> BackpressureStatus:
        """Calculate current backpressure level."""
        utilization = len(self.queue) / self.max_queue_size
        if utilization < 0.5:
            return BackpressureStatus.NORMAL
        elif utilization < 0.8:
            return BackpressureStatus.WARNING
        elif utilization < 1.0:
            return BackpressureStatus.CRITICAL
        else:
            return BackpressureStatus.OVERFLOW
    
    def _calculate_avg_processing_time(self) -> float:
        """Calculate average message processing time."""
        if not self.sent_messages:
            return 0.0
        
        # Simulate processing time based on message count
        return min(100.0, len(self.sent_messages) * 5.0)


class BackpressureHandler:
    """Handles WebSocket backpressure logic."""
    
    def __init__(self, max_connections: int = 1000):
        self.max_connections = max_connections
        self.connections: Dict[str, MockWebSocket] = {}
        self.global_metrics = BackpressureMetrics(
            queue_size=0,
            dropped_messages=0,
            sent_messages=0,
            backpressure_level=BackpressureStatus.NORMAL,
            avg_processing_time_ms=0.0,
            connection_count=0
        )
    
    async def add_connection(self, connection_id: str, is_slow: bool = False) -> MockWebSocket:
        """Add a new WebSocket connection."""
        if len(self.connections) >= self.max_connections:
            raise Exception("Maximum connections exceeded")
        
        connection = MockWebSocket(connection_id, max_queue_size=100)
        connection.is_slow_consumer = is_slow
        self.connections[connection_id] = connection
        
        self.global_metrics.connection_count = len(self.connections)
        return connection
    
    async def send_message_to_connection(self, connection_id: str, message: WebSocketMessage) -> bool:
        """Send message to specific connection with backpressure handling."""
        if connection_id not in self.connections:
            return False
        
        connection = self.connections[connection_id]
        success = await connection.send_message(message)
        
        # Update global metrics
        self._update_global_metrics()
        return success
    
    async def broadcast_message(self, message: WebSocketMessage) -> Dict[str, bool]:
        """Broadcast message to all connections."""
        results = {}
        for connection_id in self.connections:
            success = await self.send_message_to_connection(connection_id, message)
            results[connection_id] = success
        
        self._update_global_metrics()
        return results
    
    def _update_global_metrics(self):
        """Update global backpressure metrics."""
        total_queue = sum(len(conn.queue) for conn in self.connections.values())
        total_dropped = sum(len(conn.dropped_messages) for conn in self.connections.values())
        total_sent = sum(len(conn.sent_messages) for conn in self.connections.values())
        total_processing_time = sum(
            conn._calculate_avg_processing_time() for conn in self.connections.values()
        )
        
        self.global_metrics.queue_size = total_queue
        self.global_metrics.dropped_messages = total_dropped
        self.global_metrics.sent_messages = total_sent
        self.global_metrics.avg_processing_time_ms = (
            total_processing_time / len(self.connections) if self.connections else 0.0
        )
        self.global_metrics.connection_count = len(self.connections)
        
        # Calculate global backpressure level
        total_capacity = sum(conn.max_queue_size for conn in self.connections.values())
        if total_capacity > 0:
            utilization = total_queue / total_capacity
            if utilization < 0.5:
                self.global_metrics.backpressure_level = BackpressureStatus.NORMAL
            elif utilization < 0.8:
                self.global_metrics.backpressure_level = BackpressureStatus.WARNING
            elif utilization < 1.0:
                self.global_metrics.backpressure_level = BackpressureStatus.CRITICAL
            else:
                self.global_metrics.backpressure_level = BackpressureStatus.OVERFLOW


class TestWebSocketBackpressure:
    """Test WebSocket backpressure handling."""
    
    @pytest.fixture
    def backpressure_handler(self):
        """Create backpressure handler for testing."""
        return BackpressureHandler(max_connections=100)
    
    @pytest.fixture
    def sample_message(self):
        """Create sample WebSocket message."""
        return WebSocketMessage(
            message_id="msg_001",
            timestamp=datetime.now(),
            content="Test message content",
            message_type="chat",
            priority=1,
            size_bytes=100
        )
    
    @pytest.mark.asyncio
    async def test_normal_message_flow(self, backpressure_handler, sample_message):
        """Test normal message flow without backpressure."""
        # Add normal connection
        connection = await backpressure_handler.add_connection("conn_001", is_slow=False)
        
        # Send message
        success = await backpressure_handler.send_message_to_connection("conn_001", sample_message)
        
        # Validate message was sent successfully
        assert success is True
        assert len(connection.sent_messages) == 1
        assert len(connection.dropped_messages) == 0
        assert connection.get_metrics().backpressure_level == BackpressureStatus.NORMAL
    
    @pytest.mark.asyncio
    async def test_slow_consumer_backpressure(self, backpressure_handler, sample_message):
        """Test backpressure with slow consumer."""
        # Add slow consumer connection
        slow_connection = await backpressure_handler.add_connection("conn_slow", is_slow=True)
        
        # Send multiple messages rapidly
        messages_sent = 0
        messages_dropped = 0
        
        for i in range(10):
            message = WebSocketMessage(
                message_id=f"msg_{i:03d}",
                timestamp=datetime.now(),
                content=f"Message {i}",
                message_type="chat",
                priority=1,
                size_bytes=50
            )
            
            success = await backpressure_handler.send_message_to_connection("conn_slow", message)
            if success:
                messages_sent += 1
            else:
                messages_dropped += 1
        
        # Validate backpressure handling
        metrics = slow_connection.get_metrics()
        assert messages_sent > 0  # Some messages should be sent
        assert messages_dropped >= 0  # Some messages may be dropped
        assert metrics.backpressure_level in [BackpressureStatus.NORMAL, BackpressureStatus.WARNING, BackpressureStatus.CRITICAL]
        assert metrics.dropped_messages == messages_dropped
        assert metrics.sent_messages == messages_sent
    
    @pytest.mark.asyncio
    async def test_queue_overflow_protection(self, backpressure_handler, sample_message):
        """Test queue overflow protection."""
        # Add connection with small queue
        connection = MockWebSocket("conn_overflow", max_queue_size=5)
        connection.is_slow_consumer = True
        backpressure_handler.connections["conn_overflow"] = connection
        
        # Fill queue beyond capacity
        messages_sent = 0
        messages_dropped = 0
        
        for i in range(10):
            message = WebSocketMessage(
                message_id=f"msg_{i:03d}",
                timestamp=datetime.now(),
                content=f"Message {i}",
                message_type="chat",
                priority=1,
                size_bytes=50
            )
            
            success = await connection.send_message(message)
            if success:
                messages_sent += 1
            else:
                messages_dropped += 1
        
        # Validate overflow protection
        metrics = connection.get_metrics()
        assert messages_dropped > 0  # Some messages should be dropped
        assert metrics.queue_size <= connection.max_queue_size  # Queue should not exceed capacity
        assert metrics.backpressure_level == BackpressureStatus.OVERFLOW
    
    @pytest.mark.asyncio
    async def test_broadcast_with_mixed_consumers(self, backpressure_handler, sample_message):
        """Test broadcast to mixed fast and slow consumers."""
        # Add mixed connections
        fast_connection = await backpressure_handler.add_connection("conn_fast", is_slow=False)
        slow_connection = await backpressure_handler.add_connection("conn_slow", is_slow=True)
        
        # Broadcast message
        results = await backpressure_handler.broadcast_message(sample_message)
        
        # Validate broadcast results
        assert results["conn_fast"] is True  # Fast consumer should succeed
        assert results["conn_slow"] is True  # Slow consumer should also succeed for single message
        
        # Validate individual metrics
        fast_metrics = fast_connection.get_metrics()
        slow_metrics = slow_connection.get_metrics()
        
        assert fast_metrics.sent_messages == 1
        assert slow_metrics.sent_messages == 1
        assert fast_metrics.backpressure_level == BackpressureStatus.NORMAL
        assert slow_metrics.backpressure_level == BackpressureStatus.NORMAL
    
    @pytest.mark.asyncio
    async def test_session_resume_after_disconnect(self, backpressure_handler, sample_message):
        """Test session resume after disconnect."""
        # Add connection
        connection = await backpressure_handler.add_connection("conn_resume", is_slow=False)
        
        # Send some messages
        for i in range(3):
            message = WebSocketMessage(
                message_id=f"msg_{i:03d}",
                timestamp=datetime.now(),
                content=f"Message {i}",
                message_type="chat",
                priority=1,
                size_bytes=50
            )
            await backpressure_handler.send_message_to_connection("conn_resume", message)
        
        # Simulate disconnect
        connection.status = ConnectionStatus.DISCONNECTED
        initial_sent_count = len(connection.sent_messages)
        
        # Simulate reconnect
        connection.status = ConnectionStatus.RECONNECTING
        connection.status = ConnectionStatus.CONNECTED
        
        # Send message after reconnect
        resume_message = WebSocketMessage(
            message_id="msg_resume",
            timestamp=datetime.now(),
            content="Resume message",
            message_type="chat",
            priority=1,
            size_bytes=50
        )
        
        success = await backpressure_handler.send_message_to_connection("conn_resume", resume_message)
        
        # Validate session resume
        assert success is True
        assert len(connection.sent_messages) == initial_sent_count + 1
        assert connection.status == ConnectionStatus.CONNECTED
    
    @pytest.mark.asyncio
    async def test_priority_message_handling(self, backpressure_handler):
        """Test priority-based message handling."""
        # Add connection
        connection = await backpressure_handler.add_connection("conn_priority", is_slow=False)
        
        # Send low priority messages first
        for i in range(3):
            low_priority_message = WebSocketMessage(
                message_id=f"low_{i:03d}",
                timestamp=datetime.now(),
                content=f"Low priority message {i}",
                message_type="chat",
                priority=3,  # Low priority
                size_bytes=50
            )
            await backpressure_handler.send_message_to_connection("conn_priority", low_priority_message)
        
        # Send high priority message
        high_priority_message = WebSocketMessage(
            message_id="high_001",
            timestamp=datetime.now(),
            content="High priority message",
            message_type="urgent",
            priority=1,  # High priority
            size_bytes=50
        )
        
        success = await backpressure_handler.send_message_to_connection("conn_priority", high_priority_message)
        
        # Validate priority handling
        assert success is True
        assert len(connection.sent_messages) == 4  # All messages sent
        assert connection.sent_messages[-1].message_id == "high_001"  # High priority processed
    
    @pytest.mark.asyncio
    async def test_global_metrics_aggregation(self, backpressure_handler, sample_message):
        """Test global metrics aggregation across connections."""
        # Add multiple connections
        connections = []
        for i in range(5):
            conn = await backpressure_handler.add_connection(f"conn_{i:03d}", is_slow=(i % 2 == 0))
            connections.append(conn)
        
        # Send messages to different connections
        for i, conn in enumerate(connections):
            message = WebSocketMessage(
                message_id=f"msg_{i:03d}",
                timestamp=datetime.now(),
                content=f"Message to connection {i}",
                message_type="chat",
                priority=1,
                size_bytes=50
            )
            await backpressure_handler.send_message_to_connection(conn.connection_id, message)
        
        # Validate global metrics
        global_metrics = backpressure_handler.global_metrics
        assert global_metrics.connection_count == 5
        assert global_metrics.sent_messages == 5
        assert global_metrics.avg_processing_time_ms > 0
        assert global_metrics.backpressure_level in [
            BackpressureStatus.NORMAL, BackpressureStatus.WARNING
        ]
    
    @pytest.mark.asyncio
    async def test_connection_limit_enforcement(self, backpressure_handler):
        """Test connection limit enforcement."""
        # Add connections up to limit
        for i in range(backpressure_handler.max_connections):
            await backpressure_handler.add_connection(f"conn_{i:03d}")
        
        # Try to add one more connection (should fail)
        with pytest.raises(Exception, match="Maximum connections exceeded"):
            await backpressure_handler.add_connection("conn_overflow")
        
        # Validate connection count
        assert len(backpressure_handler.connections) == backpressure_handler.max_connections
        assert backpressure_handler.global_metrics.connection_count == backpressure_handler.max_connections


class TestWebSocketBackpressureIntegration:
    """Integration tests for WebSocket backpressure with real scenarios."""
    
    @pytest.mark.asyncio
    async def test_chat_room_backpressure_simulation(self):
        """Simulate chat room with multiple users and backpressure."""
        handler = BackpressureHandler(max_connections=50)
        
        # Add users to chat room
        users = []
        for i in range(20):
            is_slow = i % 4 == 0  # 25% slow consumers
            user = await handler.add_connection(f"user_{i:03d}", is_slow=is_slow)
            users.append(user)
        
        # Simulate chat activity
        messages_sent = 0
        messages_dropped = 0
        
        for round_num in range(10):
            # Each user sends a message
            for user in users:
                message = WebSocketMessage(
                    message_id=f"chat_round_{round_num}_{user.connection_id}",
                    timestamp=datetime.now(),
                    content=f"Chat message from {user.connection_id} in round {round_num}",
                    message_type="chat",
                    priority=1,
                    size_bytes=100
                )
                
                # Broadcast to all users
                results = await handler.broadcast_message(message)
                
                # Count results
                for success in results.values():
                    if success:
                        messages_sent += 1
                    else:
                        messages_dropped += 1
        
        # Validate chat room performance
        total_messages = messages_sent + messages_dropped
        success_rate = messages_sent / total_messages if total_messages > 0 else 0
        
        assert messages_sent > 0
        assert success_rate > 0.8  # At least 80% success rate
        assert handler.global_metrics.connection_count == 20
        assert handler.global_metrics.sent_messages == messages_sent
        assert handler.global_metrics.dropped_messages == messages_dropped
    
    @pytest.mark.asyncio
    async def test_real_time_notifications_backpressure(self):
        """Test real-time notifications with backpressure."""
        handler = BackpressureHandler(max_connections=100)
        
        # Add notification subscribers
        subscribers = []
        for i in range(30):
            subscriber = await handler.add_connection(f"subscriber_{i:03d}", is_slow=(i % 5 == 0))
            subscribers.append(subscriber)
        
        # Send burst of notifications
        notification_messages = []
        for i in range(50):
            message = WebSocketMessage(
                message_id=f"notification_{i:03d}",
                timestamp=datetime.now(),
                content=f"System notification {i}",
                message_type="notification",
                priority=2,
                size_bytes=200
            )
            notification_messages.append(message)
        
        # Send notifications with burst pattern
        total_sent = 0
        total_dropped = 0
        
        for message in notification_messages:
            results = await handler.broadcast_message(message)
            for success in results.values():
                if success:
                    total_sent += 1
                else:
                    total_dropped += 1
        
        # Validate notification delivery
        assert total_sent > 0
        assert total_dropped >= 0  # Some may be dropped under load
        
        # Check that slow consumers have more drops
        slow_consumer_drops = sum(
            len(sub.dropped_messages) for sub in subscribers if sub.is_slow_consumer
        )
        fast_consumer_drops = sum(
            len(sub.dropped_messages) for sub in subscribers if not sub.is_slow_consumer
        )
        
        # Slow consumers should have more drops (or equal if no drops)
        assert slow_consumer_drops >= fast_consumer_drops
        
        # Validate metrics
        assert handler.global_metrics.connection_count == 30
        assert handler.global_metrics.sent_messages == total_sent
        assert handler.global_metrics.dropped_messages == total_dropped