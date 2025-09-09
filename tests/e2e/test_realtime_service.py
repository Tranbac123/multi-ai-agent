"""End-to-end tests for Realtime Service."""

import pytest
import asyncio
import json
import time
from typing import List, Dict, Any
import websockets
import redis.asyncio as redis

from apps.realtime.main import app
from apps.realtime.core.connection_manager import ConnectionManager
from apps.realtime.core.backpressure_handler import BackpressureHandler


class TestRealtimeService:
    """Test Realtime Service functionality."""
    
    @pytest.fixture
    async def redis_client(self):
        """Create Redis client for testing."""
        client = redis.Redis(host='localhost', port=6379, db=3)
        yield client
        await client.flushdb()
        await client.close()
    
    @pytest.fixture
    def connection_manager(self, redis_client):
        """Create connection manager."""
        return ConnectionManager(redis_client)
    
    @pytest.fixture
    def backpressure_handler(self, connection_manager):
        """Create backpressure handler."""
        return BackpressureHandler(
            connection_manager=connection_manager,
            max_queue_size=10,
            drop_policy="intermediate"
        )
    
    async def test_websocket_connection_and_welcome_message(self):
        """Test WebSocket connection and welcome message."""
        uri = "ws://localhost:8002/ws/chat?tenant_id=test-tenant&user_id=test-user"
        
        async with websockets.connect(uri) as websocket:
            # Receive welcome message
            message = await websocket.recv()
            data = json.loads(message)
            
            assert data["type"] == "welcome"
            assert data["tenant_id"] == "test-tenant"
            assert data["user_id"] == "test-user"
            assert "session_id" in data
            assert "timestamp" in data
    
    async def test_chat_message_echo(self):
        """Test chat message echo functionality."""
        uri = "ws://localhost:8002/ws/chat?tenant_id=test-tenant&user_id=test-user"
        
        async with websockets.connect(uri) as websocket:
            # Receive welcome message
            welcome = await websocket.recv()
            welcome_data = json.loads(welcome)
            session_id = welcome_data["session_id"]
            
            # Send chat message
            chat_message = {
                "type": "chat",
                "content": "Hello, world!",
                "timestamp": time.time()
            }
            await websocket.send(json.dumps(chat_message))
            
            # Receive response
            response = await websocket.recv()
            response_data = json.loads(response)
            
            assert response_data["type"] == "response"
            assert "Hello, world!" in response_data["content"]
            assert response_data["session_id"] == session_id
    
    async def test_ping_pong(self):
        """Test ping-pong functionality."""
        uri = "ws://localhost:8002/ws/chat?tenant_id=test-tenant&user_id=test-user"
        
        async with websockets.connect(uri) as websocket:
            # Receive welcome message
            await websocket.recv()
            
            # Send ping
            ping_message = {
                "type": "ping",
                "timestamp": time.time()
            }
            await websocket.send(json.dumps(ping_message))
            
            # Receive pong
            response = await websocket.recv()
            response_data = json.loads(response)
            
            assert response_data["type"] == "pong"
            assert "timestamp" in response_data
    
    async def test_typing_indicator(self):
        """Test typing indicator functionality."""
        uri = "ws://localhost:8002/ws/chat?tenant_id=test-tenant&user_id=test-user"
        
        async with websockets.connect(uri) as websocket:
            # Receive welcome message
            await websocket.recv()
            
            # Send typing indicator
            typing_message = {
                "type": "typing",
                "is_typing": True,
                "timestamp": time.time()
            }
            await websocket.send(json.dumps(typing_message))
            
            # Should not receive a response for typing indicator
            # (it's broadcast to other connections)
    
    async def test_invalid_json_handling(self):
        """Test handling of invalid JSON messages."""
        uri = "ws://localhost:8002/ws/chat?tenant_id=test-tenant&user_id=test-user"
        
        async with websockets.connect(uri) as websocket:
            # Receive welcome message
            await websocket.recv()
            
            # Send invalid JSON
            await websocket.send("invalid json")
            
            # Receive error message
            response = await websocket.recv()
            response_data = json.loads(response)
            
            assert response_data["type"] == "error"
            assert "Invalid JSON format" in response_data["message"]
    
    async def test_unknown_message_type(self):
        """Test handling of unknown message types."""
        uri = "ws://localhost:8002/ws/chat?tenant_id=test-tenant&user_id=test-user"
        
        async with websockets.connect(uri) as websocket:
            # Receive welcome message
            await websocket.recv()
            
            # Send unknown message type
            unknown_message = {
                "type": "unknown_type",
                "content": "test",
                "timestamp": time.time()
            }
            await websocket.send(json.dumps(unknown_message))
            
            # Receive error message
            response = await websocket.recv()
            response_data = json.loads(response)
            
            assert response_data["type"] == "error"
            assert "Unknown message type" in response_data["message"]


class TestBackpressureHandling:
    """Test backpressure handling functionality."""
    
    @pytest.fixture
    async def redis_client(self):
        """Create Redis client for testing."""
        client = redis.Redis(host='localhost', port=6379, db=3)
        yield client
        await client.flushdb()
        await client.close()
    
    @pytest.fixture
    def connection_manager(self, redis_client):
        """Create connection manager."""
        return ConnectionManager(redis_client)
    
    @pytest.fixture
    def backpressure_handler(self, connection_manager):
        """Create backpressure handler with small queue size for testing."""
        return BackpressureHandler(
            connection_manager=connection_manager,
            max_queue_size=5,
            drop_policy="intermediate"
        )
    
    async def test_backpressure_drops_intermediate_messages(self, backpressure_handler):
        """Test that backpressure drops intermediate messages under load."""
        # Create mock WebSocket
        class MockWebSocket:
            def __init__(self):
                self.messages = []
                self.closed = False
            
            async def send_text(self, message: str):
                if self.closed:
                    raise Exception("Connection closed")
                self.messages.append(message)
            
            async def close(self):
                self.closed = True
        
        websocket = MockWebSocket()
        tenant_id = "test-tenant"
        user_id = "test-user"
        session_id = "test-session"
        
        # Register connection
        await connection_manager.register_connection(
            websocket, tenant_id, user_id, session_id
        )
        
        # Send many messages to trigger backpressure
        for i in range(10):
            message = {
                "type": "response",
                "content": f"Message {i}",
                "timestamp": time.time()
            }
            await backpressure_handler.send_message(
                websocket, tenant_id, user_id, session_id, message
            )
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        # Check that some messages were dropped
        stats = await backpressure_handler.get_stats()
        assert stats["messages_dropped"] > 0
        assert stats["backpressure_events"] > 0
        
        # Check that we received some messages
        assert len(websocket.messages) > 0
        assert len(websocket.messages) < 10  # Some were dropped
    
    async def test_slow_client_simulation(self, backpressure_handler):
        """Test backpressure handling with slow client."""
        # Create slow mock WebSocket
        class SlowWebSocket:
            def __init__(self):
                self.messages = []
                self.closed = False
                self.delay = 0.1  # 100ms delay per message
            
            async def send_text(self, message: str):
                if self.closed:
                    raise Exception("Connection closed")
                await asyncio.sleep(self.delay)  # Simulate slow client
                self.messages.append(message)
            
            async def close(self):
                self.closed = True
        
        websocket = SlowWebSocket()
        tenant_id = "test-tenant"
        user_id = "test-user"
        session_id = "test-session"
        
        # Register connection
        await connection_manager.register_connection(
            websocket, tenant_id, user_id, session_id
        )
        
        # Send messages faster than client can process
        for i in range(8):
            message = {
                "type": "response",
                "content": f"Message {i}",
                "timestamp": time.time()
            }
            await backpressure_handler.send_message(
                websocket, tenant_id, user_id, session_id, message
            )
        
        # Wait for processing
        await asyncio.sleep(1.0)
        
        # Check that some messages were dropped due to slow client
        stats = await backpressure_handler.get_stats()
        assert stats["messages_dropped"] > 0
        
        # Check that we received some messages
        assert len(websocket.messages) > 0
        assert len(websocket.messages) < 8  # Some were dropped
    
    async def test_final_message_always_delivered(self, backpressure_handler):
        """Test that final message is always delivered even under backpressure."""
        # Create mock WebSocket
        class MockWebSocket:
            def __init__(self):
                self.messages = []
                self.closed = False
            
            async def send_text(self, message: str):
                if self.closed:
                    raise Exception("Connection closed")
                self.messages.append(message)
            
            async def close(self):
                self.closed = True
        
        websocket = MockWebSocket()
        tenant_id = "test-tenant"
        user_id = "test-user"
        session_id = "test-session"
        
        # Register connection
        await connection_manager.register_connection(
            websocket, tenant_id, user_id, session_id
        )
        
        # Send many messages to trigger backpressure
        for i in range(10):
            message = {
                "type": "response",
                "content": f"Message {i}",
                "timestamp": time.time()
            }
            await backpressure_handler.send_message(
                websocket, tenant_id, user_id, session_id, message
            )
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        # Check that we received some messages
        assert len(websocket.messages) > 0
        
        # Check that the last message was delivered
        if websocket.messages:
            last_message = json.loads(websocket.messages[-1])
            assert "Message 9" in last_message["content"]  # Last message should be delivered


class TestConnectionManager:
    """Test Connection Manager functionality."""
    
    @pytest.fixture
    async def redis_client(self):
        """Create Redis client for testing."""
        client = redis.Redis(host='localhost', port=6379, db=3)
        yield client
        await client.flushdb()
        await client.close()
    
    @pytest.fixture
    def connection_manager(self, redis_client):
        """Create connection manager."""
        return ConnectionManager(redis_client)
    
    async def test_connection_registration(self, connection_manager):
        """Test connection registration."""
        # Create mock WebSocket
        class MockWebSocket:
            def __init__(self):
                self.closed = False
            
            async def close(self):
                self.closed = True
        
        websocket = MockWebSocket()
        tenant_id = "test-tenant"
        user_id = "test-user"
        session_id = "test-session"
        
        # Register connection
        await connection_manager.register_connection(
            websocket, tenant_id, user_id, session_id
        )
        
        # Check that connection is registered
        assert await connection_manager.get_connection(session_id) == websocket
        
        # Check tenant connections
        tenant_connections = await connection_manager.get_tenant_connections(tenant_id)
        assert websocket in tenant_connections
        
        # Check user connections
        user_connections = await connection_manager.get_user_connections(user_id)
        assert websocket in user_connections
        
        # Check stats
        stats = await connection_manager.get_connection_stats()
        assert stats["active_connections"] == 1
        assert stats["total_tenants"] == 1
        assert stats["total_users"] == 1
    
    async def test_connection_unregistration(self, connection_manager):
        """Test connection unregistration."""
        # Create mock WebSocket
        class MockWebSocket:
            def __init__(self):
                self.closed = False
            
            async def close(self):
                self.closed = True
        
        websocket = MockWebSocket()
        tenant_id = "test-tenant"
        user_id = "test-user"
        session_id = "test-session"
        
        # Register connection
        await connection_manager.register_connection(
            websocket, tenant_id, user_id, session_id
        )
        
        # Unregister connection
        await connection_manager.unregister_connection(
            websocket, tenant_id, user_id
        )
        
        # Check that connection is unregistered
        assert await connection_manager.get_connection(session_id) is None
        
        # Check stats
        stats = await connection_manager.get_connection_stats()
        assert stats["active_connections"] == 0
        assert stats["total_tenants"] == 0
        assert stats["total_users"] == 0
    
    async def test_broadcast_to_tenant(self, connection_manager):
        """Test broadcasting to tenant."""
        # Create mock WebSockets
        class MockWebSocket:
            def __init__(self, id):
                self.id = id
                self.messages = []
                self.closed = False
            
            async def send_text(self, message: str):
                self.messages.append(message)
            
            async def close(self):
                self.closed = True
        
        websocket1 = MockWebSocket("ws1")
        websocket2 = MockWebSocket("ws2")
        tenant_id = "test-tenant"
        user_id1 = "user1"
        user_id2 = "user2"
        session_id1 = "session1"
        session_id2 = "session2"
        
        # Register connections
        await connection_manager.register_connection(
            websocket1, tenant_id, user_id1, session_id1
        )
        await connection_manager.register_connection(
            websocket2, tenant_id, user_id2, session_id2
        )
        
        # Broadcast message
        message = {
            "type": "broadcast",
            "content": "Hello tenants!",
            "timestamp": time.time()
        }
        
        sent_count = await connection_manager.broadcast_to_tenant(tenant_id, message)
        assert sent_count == 2
        
        # Check that both connections received the message
        assert len(websocket1.messages) == 1
        assert len(websocket2.messages) == 1
        
        # Check message content
        message1 = json.loads(websocket1.messages[0])
        message2 = json.loads(websocket2.messages[0])
        
        assert message1["type"] == "broadcast"
        assert message2["type"] == "broadcast"
        assert message1["content"] == "Hello tenants!"
        assert message2["content"] == "Hello tenants!"
