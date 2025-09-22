"""
Integration tests for realtime backpressure.

Tests per-connection queues, drop policies, slow client detection,
and WebSocket backpressure metrics.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from apps.realtime_service.core.backpressure_manager import (
    BackpressureManager, PerConnectionQueue, OutboundMessage, MessageType,
    ConnectionState, BackpressurePolicy
)
from apps.realtime_service.core.websocket_manager import (
    WebSocketManager, WebSocketConnection
)


class TestBackpressureManager:
    """Test backpressure manager functionality."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis_mock = AsyncMock()
        redis_mock.get.return_value = None
        redis_mock.setex.return_value = True
        redis_mock.keys.return_value = []
        redis_mock.delete.return_value = True
        return redis_mock
    
    @pytest.fixture
    def backpressure_manager(self, mock_redis):
        """Create backpressure manager for testing."""
        return BackpressureManager(mock_redis)
    
    @pytest.mark.asyncio
    async def test_create_connection(self, backpressure_manager):
        """Test creating a new connection."""
        connection_id = "test-conn-1"
        tenant_id = "tenant-123"
        
        queue = await backpressure_manager.create_connection(connection_id, tenant_id)
        
        assert queue.connection_id == connection_id
        assert queue.tenant_id == tenant_id
        assert connection_id in backpressure_manager.connections
        assert connection_id in backpressure_manager.active_connections
    
    @pytest.mark.asyncio
    async def test_send_message_success(self, backpressure_manager):
        """Test successful message sending."""
        connection_id = "test-conn-1"
        tenant_id = "tenant-123"
        
        # Create connection
        await backpressure_manager.create_connection(connection_id, tenant_id)
        
        # Send message
        success = await backpressure_manager.send_message(
            connection_id=connection_id,
            content={"test": "message"},
            message_type=MessageType.INTERMEDIATE
        )
        
        assert success is True
        assert backpressure_manager.total_messages_sent == 1
    
    @pytest.mark.asyncio
    async def test_send_message_connection_not_found(self, backpressure_manager):
        """Test sending message to non-existent connection."""
        connection_id = "non-existent"
        
        success = await backpressure_manager.send_message(
            connection_id=connection_id,
            content={"test": "message"}
        )
        
        assert success is False
    
    @pytest.mark.asyncio
    async def test_acknowledge_message(self, backpressure_manager):
        """Test message acknowledgment."""
        connection_id = "test-conn-1"
        tenant_id = "tenant-123"
        
        # Create connection
        await backpressure_manager.create_connection(connection_id, tenant_id)
        
        # Send message
        await backpressure_manager.send_message(
            connection_id=connection_id,
            content={"test": "message"}
        )
        
        # Acknowledge message
        await backpressure_manager.acknowledge_message(
            connection_id=connection_id,
            message_id="test-msg-1",
            sequence_number=1
        )
        
        # Check that acknowledgment was processed
        queue = backpressure_manager.connections[connection_id]
        assert queue.connection_state.last_acknowledged_sequence == 1
    
    @pytest.mark.asyncio
    async def test_resume_connection(self, backpressure_manager):
        """Test connection resume."""
        connection_id = "test-conn-1"
        tenant_id = "tenant-123"
        
        # Create connection
        await backpressure_manager.create_connection(connection_id, tenant_id)
        
        # Resume connection
        success = await backpressure_manager.resume_connection(
            connection_id=connection_id,
            from_sequence=5
        )
        
        assert success is True
        
        # Check that resume message was sent
        assert backpressure_manager.total_messages_sent >= 1
    
    @pytest.mark.asyncio
    async def test_remove_connection(self, backpressure_manager):
        """Test removing a connection."""
        connection_id = "test-conn-1"
        tenant_id = "tenant-123"
        
        # Create connection
        await backpressure_manager.create_connection(connection_id, tenant_id)
        
        assert connection_id in backpressure_manager.connections
        
        # Remove connection
        await backpressure_manager.remove_connection(connection_id)
        
        assert connection_id not in backpressure_manager.connections
        assert connection_id not in backpressure_manager.active_connections
    
    def test_get_connection_metrics(self, backpressure_manager):
        """Test getting connection metrics."""
        connection_id = "test-conn-1"
        
        # Get metrics for non-existent connection
        metrics = backpressure_manager.get_connection_metrics(connection_id)
        assert metrics is None
    
    def test_get_global_metrics(self, backpressure_manager):
        """Test getting global metrics."""
        metrics = backpressure_manager.get_global_metrics()
        
        assert "total_connections" in metrics
        assert "active_connections" in metrics
        assert "total_messages_sent" in metrics
        assert "total_messages_dropped" in metrics
        assert "drop_rate" in metrics


class TestPerConnectionQueue:
    """Test per-connection queue functionality."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis_mock = AsyncMock()
        redis_mock.get.return_value = None
        redis_mock.setex.return_value = True
        redis_mock.keys.return_value = []
        redis_mock.delete.return_value = True
        return redis_mock
    
    @pytest.fixture
    def connection_queue(self, mock_redis):
        """Create connection queue for testing."""
        return PerConnectionQueue(mock_redis, "test-conn-1", "tenant-123")
    
    @pytest.mark.asyncio
    async def test_enqueue_message_success(self, connection_queue):
        """Test successful message enqueueing."""
        message = OutboundMessage(
            message_id="test-msg-1",
            connection_id="test-conn-1",
            tenant_id="tenant-123",
            message_type=MessageType.INTERMEDIATE,
            content={"test": "content"}
        )
        
        success = await connection_queue.enqueue_message(message)
        
        assert success is True
        assert connection_queue.total_enqueued == 1
        assert connection_queue.connection_state.queue_size == 1
    
    @pytest.mark.asyncio
    async def test_enqueue_final_message_never_dropped(self, connection_queue):
        """Test that final messages are never dropped."""
        message = OutboundMessage(
            message_id="test-msg-1",
            connection_id="test-conn-1",
            tenant_id="tenant-123",
            message_type=MessageType.FINAL,
            content={"test": "content"},
            is_final=True
        )
        
        # Set up conditions that would normally cause dropping
        connection_queue.connection_state.is_slow = True
        connection_queue.connection_state.queue_size = 90  # Above drop threshold
        
        success = await connection_queue.enqueue_message(message)
        
        assert success is True  # Final messages should never be dropped
    
    @pytest.mark.asyncio
    async def test_dequeue_message(self, connection_queue):
        """Test message dequeuing."""
        message = OutboundMessage(
            message_id="test-msg-1",
            connection_id="test-conn-1",
            tenant_id="tenant-123",
            message_type=MessageType.INTERMEDIATE,
            content={"test": "content"}
        )
        
        # Enqueue message
        await connection_queue.enqueue_message(message)
        
        # Dequeue message
        dequeued_message = await connection_queue.dequeue_message()
        
        assert dequeued_message is not None
        assert dequeued_message.message_id == "test-msg-1"
        assert connection_queue.total_dequeued == 1
    
    @pytest.mark.asyncio
    async def test_dequeue_empty_queue(self, connection_queue):
        """Test dequeuing from empty queue."""
        dequeued_message = await connection_queue.dequeue_message()
        
        assert dequeued_message is None
    
    @pytest.mark.asyncio
    async def test_peek_message(self, connection_queue):
        """Test message peeking."""
        message = OutboundMessage(
            message_id="test-msg-1",
            connection_id="test-conn-1",
            tenant_id="tenant-123",
            message_type=MessageType.INTERMEDIATE,
            content={"test": "content"}
        )
        
        # Enqueue message
        await connection_queue.enqueue_message(message)
        
        # Peek at message
        peeked_message = await connection_queue.peek_message()
        
        assert peeked_message is not None
        assert peeked_message.message_id == "test-msg-1"
        
        # Queue size should not change
        assert connection_queue.connection_state.queue_size == 1
    
    @pytest.mark.asyncio
    async def test_acknowledge_message(self, connection_queue):
        """Test message acknowledgment."""
        await connection_queue.acknowledge_message("test-msg-1", 1)
        
        assert connection_queue.connection_state.last_acknowledged_sequence == 1
        assert connection_queue.connection_state.last_activity is not None
    
    def test_get_metrics(self, connection_queue):
        """Test getting queue metrics."""
        metrics = connection_queue.get_metrics()
        
        assert "connection_id" in metrics
        assert "tenant_id" in metrics
        assert "queue_size" in metrics
        assert "is_active" in metrics
        assert "is_slow" in metrics
        assert "total_enqueued" in metrics
        assert "total_dequeued" in metrics
        assert "total_dropped" in metrics


class TestBackpressurePolicy:
    """Test backpressure policy functionality."""
    
    @pytest.fixture
    def policy(self):
        """Create backpressure policy for testing."""
        return BackpressurePolicy()
    
    @pytest.fixture
    def connection_state(self):
        """Create connection state for testing."""
        return ConnectionState(
            connection_id="test-conn-1",
            tenant_id="tenant-123"
        )
    
    def test_should_drop_intermediate_when_slow(self, policy, connection_state):
        """Test dropping intermediate messages when client is slow."""
        message = OutboundMessage(
            message_id="test-msg-1",
            connection_id="test-conn-1",
            tenant_id="tenant-123",
            message_type=MessageType.INTERMEDIATE,
            content={"test": "content"}
        )
        
        connection_state.is_slow = True
        
        should_drop = policy.should_drop_message(message, connection_state)
        
        assert should_drop is True
    
    def test_should_not_drop_final_message_when_slow(self, policy, connection_state):
        """Test that final messages are never dropped when client is slow."""
        message = OutboundMessage(
            message_id="test-msg-1",
            connection_id="test-conn-1",
            tenant_id="tenant-123",
            message_type=MessageType.FINAL,
            content={"test": "content"},
            is_final=True
        )
        
        connection_state.is_slow = True
        
        should_drop = policy.should_drop_message(message, connection_state)
        
        assert should_drop is False
    
    def test_should_drop_intermediate_when_queue_full(self, policy, connection_state):
        """Test dropping intermediate messages when queue is full."""
        message = OutboundMessage(
            message_id="test-msg-1",
            connection_id="test-conn-1",
            tenant_id="tenant-123",
            message_type=MessageType.INTERMEDIATE,
            content={"test": "content"}
        )
        
        connection_state.queue_size = 85  # Above drop threshold
        
        should_drop = policy.should_drop_message(message, connection_state)
        
        assert should_drop is True
    
    def test_should_not_drop_when_conditions_ok(self, policy, connection_state):
        """Test not dropping messages when conditions are OK."""
        message = OutboundMessage(
            message_id="test-msg-1",
            connection_id="test-conn-1",
            tenant_id="tenant-123",
            message_type=MessageType.INTERMEDIATE,
            content={"test": "content"}
        )
        
        connection_state.is_slow = False
        connection_state.queue_size = 50  # Below drop threshold
        
        should_drop = policy.should_drop_message(message, connection_state)
        
        assert should_drop is False
    
    def test_should_drop_old_messages(self, policy, connection_state):
        """Test dropping old messages."""
        old_time = datetime.now() - timedelta(minutes=10)
        
        message = OutboundMessage(
            message_id="test-msg-1",
            connection_id="test-conn-1",
            tenant_id="tenant-123",
            message_type=MessageType.INTERMEDIATE,
            content={"test": "content"},
            timestamp=old_time
        )
        
        should_drop = policy.should_drop_old_messages(message, connection_state)
        
        assert should_drop is True


class TestWebSocketManager:
    """Test WebSocket manager functionality."""
    
    @pytest.fixture
    def mock_websocket(self):
        """Mock WebSocket for testing."""
        websocket_mock = AsyncMock()
        websocket_mock.accept = AsyncMock()
        websocket_mock.send_text = AsyncMock()
        websocket_mock.receive_text = AsyncMock()
        websocket_mock.close = AsyncMock()
        return websocket_mock
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis_mock = AsyncMock()
        redis_mock.get.return_value = None
        redis_mock.setex.return_value = True
        redis_mock.keys.return_value = []
        redis_mock.delete.return_value = True
        return redis_mock
    
    @pytest.fixture
    def websocket_manager(self, mock_redis):
        """Create WebSocket manager for testing."""
        backpressure_manager = BackpressureManager(mock_redis)
        return WebSocketManager(backpressure_manager)
    
    @pytest.mark.asyncio
    async def test_connect(self, websocket_manager, mock_websocket):
        """Test WebSocket connection."""
        tenant_id = "tenant-123"
        
        connection_id = await websocket_manager.connect(mock_websocket, tenant_id)
        
        assert connection_id is not None
        assert connection_id in websocket_manager.connections
        assert connection_id in websocket_manager.tenant_connections[tenant_id]
        assert websocket_manager.active_connections == 1
    
    @pytest.mark.asyncio
    async def test_disconnect(self, websocket_manager, mock_websocket):
        """Test WebSocket disconnection."""
        tenant_id = "tenant-123"
        
        # Connect first
        connection_id = await websocket_manager.connect(mock_websocket, tenant_id)
        
        # Then disconnect
        await websocket_manager.disconnect(connection_id, "test_disconnect")
        
        assert connection_id not in websocket_manager.connections
        assert connection_id not in websocket_manager.tenant_connections[tenant_id]
        assert websocket_manager.active_connections == 0
    
    @pytest.mark.asyncio
    async def test_send_message(self, websocket_manager, mock_websocket):
        """Test sending message via WebSocket."""
        tenant_id = "tenant-123"
        
        # Connect first
        connection_id = await websocket_manager.connect(mock_websocket, tenant_id)
        
        # Send message
        success = await websocket_manager.send_message(
            connection_id=connection_id,
            content={"test": "message"},
            message_type=MessageType.INTERMEDIATE
        )
        
        assert success is True
        assert websocket_manager.total_messages_sent == 1
    
    @pytest.mark.asyncio
    async def test_send_to_tenant(self, websocket_manager, mock_websocket):
        """Test sending message to all tenant connections."""
        tenant_id = "tenant-123"
        
        # Connect first
        connection_id = await websocket_manager.connect(mock_websocket, tenant_id)
        
        # Send to tenant
        sent_count = await websocket_manager.send_to_tenant(
            tenant_id=tenant_id,
            content={"test": "message"},
            message_type=MessageType.INTERMEDIATE
        )
        
        assert sent_count == 1
        assert websocket_manager.total_messages_sent == 1
    
    @pytest.mark.asyncio
    async def test_handle_acknowledgment(self, websocket_manager, mock_websocket):
        """Test handling message acknowledgment."""
        tenant_id = "tenant-123"
        
        # Connect first
        connection_id = await websocket_manager.connect(mock_websocket, tenant_id)
        
        # Handle acknowledgment
        ack_message = json.dumps({
            "type": "ack",
            "message_id": "test-msg-1",
            "sequence_number": 1
        })
        
        await websocket_manager.handle_message(connection_id, ack_message)
        
        # Check that acknowledgment was processed
        queue = websocket_manager.backpressure_manager.connections[connection_id]
        assert queue.connection_state.last_acknowledged_sequence == 1
    
    @pytest.mark.asyncio
    async def test_handle_pong(self, websocket_manager, mock_websocket):
        """Test handling pong response."""
        tenant_id = "tenant-123"
        
        # Connect first
        connection_id = await websocket_manager.connect(mock_websocket, tenant_id)
        
        # Handle pong
        pong_message = json.dumps({"type": "pong"})
        
        await websocket_manager.handle_message(connection_id, pong_message)
        
        # Check that pong was processed
        connection = websocket_manager.connections[connection_id]
        assert connection.last_pong is not None
    
    @pytest.mark.asyncio
    async def test_handle_resume(self, websocket_manager, mock_websocket):
        """Test handling resume request."""
        tenant_id = "tenant-123"
        
        # Connect first
        connection_id = await websocket_manager.connect(mock_websocket, tenant_id)
        
        # Handle resume
        resume_message = json.dumps({
            "type": "resume",
            "from_sequence": 5
        })
        
        await websocket_manager.handle_message(connection_id, resume_message)
        
        # Check that resume was processed
        assert websocket_manager.backpressure_manager.total_messages_sent >= 1
    
    def test_get_tenant_connections(self, websocket_manager, mock_websocket):
        """Test getting tenant connections."""
        tenant_id = "tenant-123"
        
        # Connect first
        asyncio.run(websocket_manager.connect(mock_websocket, tenant_id))
        
        # Get tenant connections
        connection_ids = websocket_manager.get_tenant_connections(tenant_id)
        
        assert len(connection_ids) == 1
        assert connection_ids[0] in websocket_manager.connections
    
    def test_get_metrics(self, websocket_manager):
        """Test getting WebSocket manager metrics."""
        metrics = websocket_manager.get_metrics()
        
        assert "total_connections" in metrics
        assert "active_connections" in metrics
        assert "total_messages_sent" in metrics
        assert "total_messages_received" in metrics
        assert "total_bytes_sent" in metrics
        assert "total_bytes_received" in metrics
        assert "total_send_errors" in metrics
        assert "total_receive_errors" in metrics
        assert "backpressure_metrics" in metrics


@pytest.mark.asyncio
async def test_slow_client_drops_intermediate_final_delivered():
    """Test that slow clients cause intermediate message drops but final messages are delivered."""
    
    # Create backpressure manager
    mock_redis = AsyncMock()
    backpressure_manager = BackpressureManager(mock_redis)
    
    # Create connection
    connection_id = "slow-conn-1"
    tenant_id = "tenant-123"
    await backpressure_manager.create_connection(connection_id, tenant_id)
    
    # Simulate slow client by not acknowledging messages
    queue = backpressure_manager.connections[connection_id]
    queue.connection_state.last_activity = datetime.now() - timedelta(seconds=2)
    queue.connection_state.slow_client_threshold_ms = 1000
    queue.connection_state.is_slow = True
    
    # Send intermediate messages (should be dropped)
    intermediate_sent = 0
    intermediate_dropped = 0
    
    for i in range(5):
        success = await backpressure_manager.send_message(
            connection_id=connection_id,
            content=f"intermediate-{i}",
            message_type=MessageType.INTERMEDIATE
        )
        if success:
            intermediate_sent += 1
        else:
            intermediate_dropped += 1
    
    # Send final message (should be delivered)
    final_success = await backpressure_manager.send_message(
        connection_id=connection_id,
        content="final message",
        message_type=MessageType.FINAL,
        is_final=True
    )
    
    # Verify results
    assert final_success is True  # Final message should always be delivered
    assert intermediate_dropped > 0  # Some intermediate messages should be dropped
    
    # Check metrics
    metrics = backpressure_manager.get_connection_metrics(connection_id)
    assert metrics["total_messages_dropped"] > 0
    assert metrics["is_slow"] is True


@pytest.mark.asyncio
async def test_reconnect_resumes_from_last_sequence():
    """Test that reconnecting resumes from the last acknowledged sequence."""
    
    # Create backpressure manager
    mock_redis = AsyncMock()
    backpressure_manager = BackpressureManager(mock_redis)
    
    # Create connection and send messages
    connection_id = "resume-conn-1"
    tenant_id = "tenant-123"
    await backpressure_manager.create_connection(connection_id, tenant_id)
    
    # Send some messages
    for i in range(3):
        await backpressure_manager.send_message(
            connection_id=connection_id,
            content=f"message-{i}",
            message_type=MessageType.INTERMEDIATE
        )
    
    # Acknowledge first two messages
    await backpressure_manager.acknowledge_message(connection_id, "msg-1", 1)
    await backpressure_manager.acknowledge_message(connection_id, "msg-2", 2)
    
    # Simulate disconnect and reconnect
    await backpressure_manager.remove_connection(connection_id)
    
    # Resume connection
    success = await backpressure_manager.resume_connection(connection_id, from_sequence=2)
    
    assert success is True
    
    # Check that resume message was sent
    assert backpressure_manager.total_messages_sent >= 1


@pytest.mark.asyncio
async def test_metrics_increment_properly():
    """Test that metrics increment properly for WebSocket operations."""
    
    # Create WebSocket manager
    mock_redis = AsyncMock()
    backpressure_manager = BackpressureManager(mock_redis)
    websocket_manager = WebSocketManager(backpressure_manager)
    
    # Create mock WebSocket
    mock_websocket = AsyncMock()
    mock_websocket.accept = AsyncMock()
    mock_websocket.send_text = AsyncMock()
    mock_websocket.receive_text = AsyncMock()
    mock_websocket.close = AsyncMock()
    
    # Connect
    tenant_id = "tenant-123"
    connection_id = await websocket_manager.connect(mock_websocket, tenant_id)
    
    # Send messages
    for i in range(3):
        await websocket_manager.send_message(
            connection_id=connection_id,
            content=f"message-{i}",
            message_type=MessageType.INTERMEDIATE
        )
    
    # Handle messages
    for i in range(2):
        await websocket_manager.handle_message(
            connection_id,
            json.dumps({"type": "message", "content": f"response-{i}"})
        )
    
    # Check metrics
    metrics = websocket_manager.get_metrics()
    
    assert metrics["total_messages_sent"] == 3
    assert metrics["total_messages_received"] == 2
    assert metrics["active_connections"] == 1
    assert metrics["total_connections"] == 1
    
    # Check backpressure metrics
    backpressure_metrics = metrics["backpressure_metrics"]
    assert backpressure_metrics["total_messages_sent"] >= 3
    assert backpressure_metrics["active_connections"] == 1
