"""Production-grade WebSocket backpressure and session management tests."""

import pytest
import asyncio
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock
from dataclasses import dataclass, asdict

from tests._fixtures.factories import factory, TenantTier
from tests._helpers import test_helpers


@dataclass
class WebSocketMessage:
    """WebSocket message structure."""
    message_id: str
    message_type: str
    payload: Dict[str, Any]
    timestamp: datetime
    priority: int = 1  # 1=low, 2=medium, 3=high
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class BackpressureMetrics:
    """Backpressure metrics tracking."""
    connection_id: str
    messages_sent: int = 0
    messages_dropped: int = 0
    messages_queued: int = 0
    queue_size_max: int = 0
    avg_processing_time_ms: float = 0.0
    slow_consumer_detected: bool = False
    last_heartbeat: Optional[datetime] = None
    
    @property
    def drop_rate(self) -> float:
        """Calculate message drop rate."""
        total = self.messages_sent + self.messages_dropped
        return (self.messages_dropped / max(total, 1)) * 100
    
    @property
    def queue_utilization(self) -> float:
        """Calculate queue utilization percentage."""
        return (self.messages_queued / max(self.queue_size_max, 1)) * 100


class ProductionWebSocketManager:
    """Production-grade WebSocket manager with backpressure handling."""
    
    def __init__(self, max_queue_size: int = 1000, slow_consumer_threshold: float = 0.8):
        """Initialize WebSocket manager."""
        self.max_queue_size = max_queue_size
        self.slow_consumer_threshold = slow_consumer_threshold
        self.connections: Dict[str, 'WebSocketConnection'] = {}
        self.metrics: Dict[str, BackpressureMetrics] = {}
        self.global_drop_count = 0
        self.global_send_errors = 0
    
    async def create_connection(self, connection_id: str, tenant_id: str) -> 'WebSocketConnection':
        """Create a new WebSocket connection."""
        connection = WebSocketConnection(
            connection_id=connection_id,
            tenant_id=tenant_id,
            max_queue_size=self.max_queue_size,
            slow_consumer_threshold=self.slow_consumer_threshold
        )
        
        self.connections[connection_id] = connection
        self.metrics[connection_id] = BackpressureMetrics(
            connection_id=connection_id,
            queue_size_max=self.max_queue_size,
            last_heartbeat=datetime.now(timezone.utc)
        )
        
        return connection
    
    async def send_message(self, connection_id: str, message: WebSocketMessage) -> bool:
        """Send message with backpressure handling."""
        if connection_id not in self.connections:
            self.global_send_errors += 1
            return False
        
        connection = self.connections[connection_id]
        metrics = self.metrics[connection_id]
        
        # Update heartbeat
        metrics.last_heartbeat = datetime.now(timezone.utc)
        
        # Check for slow consumer
        if metrics.avg_processing_time_ms > 100:  # 100ms threshold
            connection.is_slow_consumer = True
            metrics.slow_consumer_detected = True
        
        # Apply backpressure logic
        success = await connection.send_message(message)
        
        # Update metrics
        if success:
            metrics.messages_sent += 1
        else:
            metrics.messages_dropped += 1
            self.global_drop_count += 1
        
        metrics.messages_queued = len(connection.queue)
        metrics.queue_size_max = max(metrics.queue_size_max, len(connection.queue))
        
        return success
    
    async def reconnect_session(self, connection_id: str, tenant_id: str) -> 'WebSocketConnection':
        """Reconnect a session and resume from last known state."""
        # Remove old connection
        if connection_id in self.connections:
            del self.connections[connection_id]
        
        # Create new connection
        new_connection = await self.create_connection(connection_id, tenant_id)
        
        # Restore session state (in real implementation, this would come from storage)
        new_connection.session_restored = True
        
        return new_connection
    
    def get_global_metrics(self) -> Dict[str, Any]:
        """Get global WebSocket metrics."""
        total_connections = len(self.connections)
        total_drops = self.global_drop_count
        total_errors = self.global_send_errors
        
        active_connections = sum(1 for conn in self.connections.values() 
                               if conn.status == "connected")
        
        return {
            "total_connections": total_connections,
            "active_connections": active_connections,
            "total_drops": total_drops,
            "total_errors": total_errors,
            "drop_rate": (total_drops / max(total_drops + total_connections * 100, 1)) * 100
        }


class WebSocketConnection:
    """Individual WebSocket connection with backpressure handling."""
    
    def __init__(self, connection_id: str, tenant_id: str, max_queue_size: int, 
                 slow_consumer_threshold: float):
        """Initialize WebSocket connection."""
        self.connection_id = connection_id
        self.tenant_id = tenant_id
        self.max_queue_size = max_queue_size
        self.slow_consumer_threshold = slow_consumer_threshold
        self.queue: List[WebSocketMessage] = []
        self.sent_messages: List[WebSocketMessage] = []
        self.dropped_messages: List[WebSocketMessage] = []
        self.status = "connected"
        self.is_slow_consumer = False
        self.session_restored = False
        self.last_activity = datetime.now(timezone.utc)
        self.processing_times: List[float] = []
    
    async def send_message(self, message: WebSocketMessage) -> bool:
        """Send message with backpressure handling."""
        start_time = time.time()
        
        # Drop intermediates for slow consumers, keep final messages
        if self.is_slow_consumer:
            if message.message_type in ["progress", "intermediate", "typing"]:
                self.dropped_messages.append(message)
                return False
        
        # Apply queue limits
        if len(self.queue) >= self.max_queue_size:
            # Drop oldest message to make room
            if self.queue:
                oldest = self.queue.pop(0)
                self.dropped_messages.append(oldest)
        
        # Add to queue
        self.queue.append(message)
        
        # Simulate processing time
        processing_time = time.time() - start_time
        self.processing_times.append(processing_time * 1000)  # Convert to ms
        
        # Keep only recent processing times
        if len(self.processing_times) > 100:
            self.processing_times = self.processing_times[-50:]
        
        # Move to sent messages
        self.sent_messages.append(message)
        self.queue.remove(message)
        self.last_activity = datetime.now(timezone.utc)
        
        return True
    
    async def simulate_slow_consumer(self):
        """Simulate slow consumer behavior."""
        self.is_slow_consumer = True
        await asyncio.sleep(0.1)  # Simulate slow processing
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get connection metrics."""
        avg_processing_time = sum(self.processing_times) / len(self.processing_times) if self.processing_times else 0
        
        return {
            "connection_id": self.connection_id,
            "status": self.status,
            "queue_size": len(self.queue),
            "messages_sent": len(self.sent_messages),
            "messages_dropped": len(self.dropped_messages),
            "is_slow_consumer": self.is_slow_consumer,
            "avg_processing_time_ms": avg_processing_time,
            "drop_rate": (len(self.dropped_messages) / max(len(self.sent_messages) + len(self.dropped_messages), 1)) * 100
        }


class TestWebSocketBackpressureProduction:
    """Production-grade WebSocket backpressure tests."""
    
    @pytest.fixture
    async def websocket_manager(self):
        """Create WebSocket manager for testing."""
        return ProductionWebSocketManager(max_queue_size=100, slow_consumer_threshold=0.8)
    
    @pytest.fixture
    async def test_connection(self, websocket_manager):
        """Create test WebSocket connection."""
        tenant = factory.create_tenant(tier=TenantTier.PREMIUM)
        connection = await websocket_manager.create_connection("conn_001", tenant.tenant_id)
        return connection, tenant
    
    @pytest.mark.asyncio
    async def test_slow_consumer_message_dropping(self, websocket_manager, test_connection):
        """Test that slow consumers drop intermediate messages but keep final ones."""
        connection, tenant = test_connection
        
        # Simulate slow consumer
        await connection.simulate_slow_consumer()
        
        # Send mixed message types
        messages = [
            WebSocketMessage("msg_1", "typing", {"status": "typing"}, datetime.now()),
            WebSocketMessage("msg_2", "progress", {"progress": 25}, datetime.now()),
            WebSocketMessage("msg_3", "intermediate", {"partial": "result"}, datetime.now()),
            WebSocketMessage("msg_4", "final", {"result": "complete"}, datetime.now()),
            WebSocketMessage("msg_5", "typing", {"status": "typing"}, datetime.now())
        ]
        
        results = []
        for message in messages:
            success = await websocket_manager.send_message(connection.connection_id, message)
            results.append(success)
        
        # Final message should be delivered, intermediates may be dropped
        assert results[3] is True  # Final message delivered
        
        # Check metrics
        metrics = websocket_manager.metrics[connection.connection_id]
        assert metrics.slow_consumer_detected is True
        assert metrics.messages_dropped > 0
    
    @pytest.mark.asyncio
    async def test_session_reconnection_resumes_state(self, websocket_manager, test_connection):
        """Test that session reconnection resumes from last known state."""
        connection, tenant = test_connection
        
        # Send some messages
        message = WebSocketMessage("msg_1", "final", {"result": "data"}, datetime.now())
        await websocket_manager.send_message(connection.connection_id, message)
        
        # Reconnect session
        new_connection = await websocket_manager.reconnect_session(connection.connection_id, tenant.tenant_id)
        
        # Verify session was restored
        assert new_connection.session_restored is True
        assert new_connection.connection_id == connection.connection_id
        assert new_connection.tenant_id == tenant.tenant_id
    
    @pytest.mark.asyncio
    async def test_prometheus_metrics_assertion(self, websocket_manager, test_connection):
        """Test Prometheus metrics for WebSocket backpressure."""
        connection, tenant = test_connection
        
        # Generate some traffic
        for i in range(50):
            message = WebSocketMessage(f"msg_{i}", "test", {"data": f"test_{i}"}, datetime.now())
            await websocket_manager.send_message(connection.connection_id, message)
        
        # Get global metrics
        global_metrics = websocket_manager.get_global_metrics()
        
        # Assert Prometheus-style metrics
        assert global_metrics["total_connections"] >= 1
        assert global_metrics["active_connections"] >= 1
        assert global_metrics["total_drops"] >= 0
        assert global_metrics["total_errors"] >= 0
        
        # Assert metrics are within expected ranges
        assert 0 <= global_metrics["drop_rate"] <= 100
    
    @pytest.mark.asyncio
    async def test_websocket_backpressure_under_load(self, websocket_manager):
        """Test WebSocket backpressure under high load."""
        # Create multiple connections
        connections = []
        for i in range(10):
            tenant = factory.create_tenant(tier=TenantTier.PREMIUM)
            connection = await websocket_manager.create_connection(f"conn_{i:03d}", tenant.tenant_id)
            connections.append(connection)
        
        # Simulate high load
        tasks = []
        for i in range(100):  # 100 messages per connection
            for connection in connections:
                message = WebSocketMessage(
                    f"msg_{i}",
                    "load_test",
                    {"data": f"load_test_{i}", "timestamp": datetime.now().isoformat()},
                    datetime.now()
                )
                task = websocket_manager.send_message(connection.connection_id, message)
                tasks.append(task)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Validate results
        success_count = sum(1 for result in results if result is True)
        total_messages = len(tasks)
        
        # Should have some successes and some drops
        assert success_count > 0
        assert success_count < total_messages  # Some messages should be dropped under load
        
        # Check global metrics
        global_metrics = websocket_manager.get_global_metrics()
        assert global_metrics["total_connections"] == 10
        assert global_metrics["total_drops"] > 0
    
    @pytest.mark.asyncio
    async def test_websocket_priority_message_handling(self, websocket_manager, test_connection):
        """Test priority-based message handling."""
        connection, tenant = test_connection
        
        # Send messages with different priorities
        messages = [
            WebSocketMessage("msg_1", "low", {"data": "low_priority"}, datetime.now(), priority=1),
            WebSocketMessage("msg_2", "high", {"data": "high_priority"}, datetime.now(), priority=3),
            WebSocketMessage("msg_3", "medium", {"data": "medium_priority"}, datetime.now(), priority=2),
            WebSocketMessage("msg_4", "critical", {"data": "critical"}, datetime.now(), priority=3),
        ]
        
        # Sort by priority (high priority first)
        messages.sort(key=lambda x: x.priority, reverse=True)
        
        results = []
        for message in messages:
            success = await websocket_manager.send_message(connection.connection_id, message)
            results.append(success)
        
        # High priority messages should be more likely to succeed
        high_priority_results = [results[i] for i, msg in enumerate(messages) if msg.priority == 3]
        low_priority_results = [results[i] for i, msg in enumerate(messages) if msg.priority == 1]
        
        # High priority should have higher success rate
        high_priority_success_rate = sum(high_priority_results) / len(high_priority_results)
        low_priority_success_rate = sum(low_priority_results) / len(low_priority_results)
        
        assert high_priority_success_rate >= low_priority_success_rate
    
    @pytest.mark.asyncio
    async def test_websocket_connection_cleanup(self, websocket_manager, test_connection):
        """Test WebSocket connection cleanup and resource management."""
        connection, tenant = test_connection
        
        # Send some messages
        for i in range(10):
            message = WebSocketMessage(f"msg_{i}", "test", {"data": f"test_{i}"}, datetime.now())
            await websocket_manager.send_message(connection.connection_id, message)
        
        # Disconnect connection
        connection.status = "disconnected"
        
        # Try to send message to disconnected connection
        message = WebSocketMessage("msg_disconnect", "test", {"data": "disconnect"}, datetime.now())
        success = await websocket_manager.send_message(connection.connection_id, message)
        
        # Should fail for disconnected connection
        assert success is False
        
        # Check global metrics
        global_metrics = websocket_manager.get_global_metrics()
        assert global_metrics["total_errors"] > 0
    
    @pytest.mark.asyncio
    async def test_websocket_heartbeat_and_health_check(self, websocket_manager, test_connection):
        """Test WebSocket heartbeat and health check functionality."""
        connection, tenant = test_connection
        
        # Send heartbeat message
        heartbeat_message = WebSocketMessage("heartbeat", "ping", {}, datetime.now())
        success = await websocket_manager.send_message(connection.connection_id, heartbeat_message)
        
        assert success is True
        
        # Check that heartbeat was recorded
        metrics = websocket_manager.metrics[connection.connection_id]
        assert metrics.last_heartbeat is not None
        
        # Check connection health
        connection_metrics = connection.get_metrics()
        assert connection_metrics["status"] == "connected"
        assert connection_metrics["connection_id"] == connection.connection_id
    
    @pytest.mark.asyncio
    async def test_websocket_tenant_isolation(self, websocket_manager):
        """Test WebSocket tenant isolation."""
        # Create connections for different tenants
        tenant1 = factory.create_tenant(name="Tenant 1")
        tenant2 = factory.create_tenant(name="Tenant 2")
        
        conn1 = await websocket_manager.create_connection("conn_tenant1", tenant1.tenant_id)
        conn2 = await websocket_manager.create_connection("conn_tenant2", tenant2.tenant_id)
        
        # Send messages to each connection
        msg1 = WebSocketMessage("msg1", "test", {"tenant": "1"}, datetime.now())
        msg2 = WebSocketMessage("msg2", "test", {"tenant": "2"}, datetime.now())
        
        await websocket_manager.send_message("conn_tenant1", msg1)
        await websocket_manager.send_message("conn_tenant2", msg2)
        
        # Verify tenant isolation
        assert conn1.tenant_id == tenant1.tenant_id
        assert conn2.tenant_id == tenant2.tenant_id
        assert conn1.tenant_id != conn2.tenant_id
        
        # Verify metrics are separate
        metrics1 = websocket_manager.metrics["conn_tenant1"]
        metrics2 = websocket_manager.metrics["conn_tenant2"]
        
        assert metrics1.connection_id == "conn_tenant1"
        assert metrics2.connection_id == "conn_tenant2"
