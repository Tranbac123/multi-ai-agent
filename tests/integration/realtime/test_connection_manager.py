"""Test connection manager functionality."""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Set

from apps.realtime.core.connection_manager import ConnectionManager


class TestConnectionManager:
    """Test ConnectionManager functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis_client = Mock()
        redis_client.hset = AsyncMock()
        redis_client.expire = AsyncMock()
        redis_client.delete = AsyncMock()
        redis_client.hgetall = AsyncMock(return_value={})
        return redis_client

    @pytest.fixture
    def connection_manager(self, mock_redis):
        """Create ConnectionManager instance."""
        return ConnectionManager(mock_redis)

    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket."""
        websocket = Mock()
        websocket.send_text = AsyncMock()
        return websocket

    @pytest.mark.asyncio
    async def test_register_connection(self, connection_manager, mock_websocket, mock_redis):
        """Test registering a new connection."""
        tenant_id = "tenant_123"
        user_id = "user_123"
        session_id = "session_123"

        await connection_manager.register_connection(
            mock_websocket, tenant_id, user_id, session_id
        )

        # Check in-memory storage
        assert session_id in connection_manager.connections
        assert session_id in connection_manager.tenant_connections[tenant_id]
        assert session_id in connection_manager.user_connections[user_id]

        # Check Redis storage
        mock_redis.hset.assert_called_once()
        mock_redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_connection_without_user_id(self, connection_manager, mock_websocket, mock_redis):
        """Test registering a connection without user_id."""
        tenant_id = "tenant_123"
        session_id = "session_123"

        await connection_manager.register_connection(
            mock_websocket, tenant_id, None, session_id
        )

        # Check in-memory storage
        assert session_id in connection_manager.connections
        assert session_id in connection_manager.tenant_connections[tenant_id]
        assert session_id not in connection_manager.user_connections

    @pytest.mark.asyncio
    async def test_unregister_connection(self, connection_manager, mock_websocket, mock_redis):
        """Test unregistering a connection."""
        tenant_id = "tenant_123"
        user_id = "user_123"
        session_id = "session_123"

        # First register the connection
        await connection_manager.register_connection(
            mock_websocket, tenant_id, user_id, session_id
        )

        # Then unregister it
        await connection_manager.unregister_connection(
            mock_websocket, tenant_id, user_id
        )

        # Check that connection is removed
        assert session_id not in connection_manager.connections
        assert session_id not in connection_manager.tenant_connections.get(tenant_id, set())
        assert session_id not in connection_manager.user_connections.get(user_id, set())

        # Check Redis cleanup
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_connection(self, connection_manager, mock_websocket):
        """Test getting a connection by session ID."""
        session_id = "session_123"
        connection_manager.connections[session_id] = mock_websocket

        result = await connection_manager.get_connection(session_id)
        assert result == mock_websocket

        # Test non-existent connection
        result = await connection_manager.get_connection("non_existent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_tenant_connections(self, connection_manager, mock_websocket):
        """Test getting all connections for a tenant."""
        tenant_id = "tenant_123"
        session_id1 = "session_123"
        session_id2 = "session_124"

        # Register connections
        await connection_manager.register_connection(
            mock_websocket, tenant_id, "user_123", session_id1
        )
        
        websocket2 = Mock()
        await connection_manager.register_connection(
            websocket2, tenant_id, "user_124", session_id2
        )

        connections = await connection_manager.get_tenant_connections(tenant_id)
        assert len(connections) == 2
        assert mock_websocket in connections
        assert websocket2 in connections

    @pytest.mark.asyncio
    async def test_get_user_connections(self, connection_manager, mock_websocket):
        """Test getting all connections for a user."""
        user_id = "user_123"
        tenant_id = "tenant_123"
        session_id1 = "session_123"
        session_id2 = "session_124"

        # Register connections
        await connection_manager.register_connection(
            mock_websocket, tenant_id, user_id, session_id1
        )
        
        websocket2 = Mock()
        await connection_manager.register_connection(
            websocket2, tenant_id, user_id, session_id2
        )

        connections = await connection_manager.get_user_connections(user_id)
        assert len(connections) == 2
        assert mock_websocket in connections
        assert websocket2 in connections

    @pytest.mark.asyncio
    async def test_broadcast_to_tenant(self, connection_manager, mock_websocket):
        """Test broadcasting to all connections in a tenant."""
        tenant_id = "tenant_123"
        session_id1 = "session_123"
        session_id2 = "session_124"

        # Register connections
        await connection_manager.register_connection(
            mock_websocket, tenant_id, "user_123", session_id1
        )
        
        websocket2 = Mock()
        websocket2.send_text = AsyncMock()
        await connection_manager.register_connection(
            websocket2, tenant_id, "user_124", session_id2
        )

        message = {"type": "broadcast", "content": "hello"}

        sent_count = await connection_manager.broadcast_to_tenant(tenant_id, message)

        assert sent_count == 2
        mock_websocket.send_text.assert_called_once()
        websocket2.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_to_tenant_with_exclude(self, connection_manager, mock_websocket):
        """Test broadcasting to tenant with excluded session."""
        tenant_id = "tenant_123"
        session_id1 = "session_123"
        session_id2 = "session_124"

        # Register connections
        await connection_manager.register_connection(
            mock_websocket, tenant_id, "user_123", session_id1
        )
        
        websocket2 = Mock()
        websocket2.send_text = AsyncMock()
        await connection_manager.register_connection(
            websocket2, tenant_id, "user_124", session_id2
        )

        message = {"type": "broadcast", "content": "hello"}

        # Exclude session_id1
        sent_count = await connection_manager.broadcast_to_tenant(
            tenant_id, message, exclude_session=session_id1
        )

        assert sent_count == 1
        mock_websocket.send_text.assert_not_called()
        websocket2.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_to_user(self, connection_manager, mock_websocket):
        """Test broadcasting to all connections for a user."""
        user_id = "user_123"
        tenant_id = "tenant_123"
        session_id1 = "session_123"
        session_id2 = "session_124"

        # Register connections
        await connection_manager.register_connection(
            mock_websocket, tenant_id, user_id, session_id1
        )
        
        websocket2 = Mock()
        websocket2.send_text = AsyncMock()
        await connection_manager.register_connection(
            websocket2, tenant_id, user_id, session_id2
        )

        message = {"type": "broadcast", "content": "hello"}

        sent_count = await connection_manager.broadcast_to_user(user_id, message)

        assert sent_count == 2
        mock_websocket.send_text.assert_called_once()
        websocket2.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_to_session(self, connection_manager, mock_websocket):
        """Test sending message to specific session."""
        session_id = "session_123"
        connection_manager.connections[session_id] = mock_websocket

        message = {"type": "direct", "content": "hello"}

        result = await connection_manager.send_to_session(session_id, message)

        assert result is True
        mock_websocket.send_text.assert_called_once_with(json.dumps(message))

    @pytest.mark.asyncio
    async def test_send_to_nonexistent_session(self, connection_manager):
        """Test sending message to non-existent session."""
        session_id = "non_existent"
        message = {"type": "direct", "content": "hello"}

        result = await connection_manager.send_to_session(session_id, message)

        assert result is False

    @pytest.mark.asyncio
    async def test_get_connection_stats(self, connection_manager, mock_websocket):
        """Test getting connection statistics."""
        tenant_id = "tenant_123"
        user_id = "user_123"
        session_id = "session_123"

        # Register connection
        await connection_manager.register_connection(
            mock_websocket, tenant_id, user_id, session_id
        )

        stats = await connection_manager.get_connection_stats()

        assert stats["active_connections"] == 1
        assert stats["total_tenants"] == 1
        assert stats["total_users"] == 1
        assert tenant_id in stats["tenant_connections"]
        assert user_id in stats["user_connections"]

    @pytest.mark.asyncio
    async def test_cleanup_stale_connections(self, connection_manager, mock_redis):
        """Test cleaning up stale connections."""
        # Create mock connections
        websocket1 = Mock()
        websocket1.send_text = AsyncMock()  # Active connection
        
        websocket2 = Mock()
        websocket2.send_text = AsyncMock(side_effect=Exception("Connection closed"))  # Stale connection

        # Register connections
        await connection_manager.register_connection(
            websocket1, "tenant_123", "user_123", "session_123"
        )
        await connection_manager.register_connection(
            websocket2, "tenant_124", "user_124", "session_124"
        )

        # Mock Redis session data
        mock_redis.hgetall.side_effect = [
            {"tenant_id": "tenant_124", "user_id": "user_124"},
            {"tenant_id": "tenant_124", "user_id": "user_124"}
        ]

        # Clean up stale connections
        with patch.object(connection_manager, 'unregister_connection') as mock_unregister:
            stale_count = await connection_manager.cleanup_stale_connections()

        assert stale_count == 1
        mock_unregister.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_connection_registration(self, connection_manager, mock_redis):
        """Test concurrent connection registration."""
        async def register_connection(websocket, tenant_id, user_id, session_id):
            await connection_manager.register_connection(websocket, tenant_id, user_id, session_id)

        # Create multiple mock websockets
        websockets = [Mock() for _ in range(5)]
        
        # Register connections concurrently
        tasks = [
            register_connection(ws, f"tenant_{i}", f"user_{i}", f"session_{i}")
            for i, ws in enumerate(websockets)
        ]
        
        await asyncio.gather(*tasks)

        # Verify all connections are registered
        assert len(connection_manager.connections) == 5
        assert len(connection_manager.tenant_connections) == 5
        assert len(connection_manager.user_connections) == 5

    @pytest.mark.asyncio
    async def test_broadcast_error_handling(self, connection_manager, mock_websocket):
        """Test broadcast error handling."""
        tenant_id = "tenant_123"
        session_id = "session_123"

        # Register connection
        await connection_manager.register_connection(
            mock_websocket, tenant_id, "user_123", session_id
        )

        # Make send_text raise an exception
        mock_websocket.send_text.side_effect = Exception("Send failed")

        message = {"type": "broadcast", "content": "hello"}

        # Should not raise exception
        sent_count = await connection_manager.broadcast_to_tenant(tenant_id, message)

        assert sent_count == 0  # No messages sent due to error

    @pytest.mark.asyncio
    async def test_connection_lookup_by_websocket(self, connection_manager, mock_websocket):
        """Test finding session_id by websocket during unregistration."""
        tenant_id = "tenant_123"
        user_id = "user_123"
        session_id = "session_123"

        # Register connection
        await connection_manager.register_connection(
            mock_websocket, tenant_id, user_id, session_id
        )

        # Unregister using websocket (should find the session_id)
        await connection_manager.unregister_connection(mock_websocket, tenant_id, user_id)

        # Connection should be removed
        assert session_id not in connection_manager.connections

    @pytest.mark.asyncio
    async def test_multiple_tenants_and_users(self, connection_manager, mock_redis):
        """Test handling multiple tenants and users."""
        # Register connections for different tenants and users
        connections = []
        for i in range(3):
            for j in range(2):
                websocket = Mock()
                tenant_id = f"tenant_{i}"
                user_id = f"user_{j}"
                session_id = f"session_{i}_{j}"
                
                await connection_manager.register_connection(
                    websocket, tenant_id, user_id, session_id
                )
                connections.append(websocket)

        # Check statistics
        stats = await connection_manager.get_connection_stats()
        
        assert stats["active_connections"] == 6
        assert stats["total_tenants"] == 3
        assert stats["total_users"] == 2
        
        # Each tenant should have 2 connections
        for i in range(3):
            assert stats["tenant_connections"][f"tenant_{i}"] == 2
            
        # Each user should have 3 connections
        for j in range(2):
            assert stats["user_connections"][f"user_{j}"] == 3
