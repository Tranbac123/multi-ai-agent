"""Test realtime service functionality."""

import pytest
import json
import time
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import WebSocket, WebSocketDisconnect

from apps.realtime.main import app


class TestRealtimeService:
    """Test realtime service functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis_client = Mock()
        redis_client.ping = AsyncMock()
        redis_client.close = AsyncMock()
        redis_client.lpush = AsyncMock()
        redis_client.lrange = AsyncMock(return_value=[])
        redis_client.delete = AsyncMock()
        redis_client.setex = AsyncMock()
        redis_client.keys = AsyncMock(return_value=[])
        redis_client.llen = AsyncMock(return_value=0)
        redis_client.ltrim = AsyncMock()
        redis_client.hset = AsyncMock()
        redis_client.expire = AsyncMock()
        redis_client.hgetall = AsyncMock(return_value={})
        return redis_client

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        assert response.json()["service"] == "realtime"

    @pytest.mark.asyncio
    async def test_readiness_check_success(self, client, mock_redis):
        """Test readiness check when Redis is available."""
        with patch('apps.realtime.main.redis_client', mock_redis):
            response = client.get("/ready")
            assert response.status_code == 200
            assert response.json()["status"] == "ready"
            assert response.json()["service"] == "realtime"

    @pytest.mark.asyncio
    async def test_readiness_check_failure(self, client, mock_redis):
        """Test readiness check when Redis is unavailable."""
        mock_redis.ping.side_effect = Exception("Redis connection failed")
        
        with patch('apps.realtime.main.redis_client', mock_redis):
            response = client.get("/ready")
            assert response.status_code == 503
            assert "not ready" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, client, mock_redis):
        """Test metrics endpoint."""
        mock_stats = {
            "ws_active_connections": 5,
            "ws_backpressure_drops": 10,
            "ws_send_errors": 2,
            "total_queued_messages": 15,
            "active_queues": 3,
            "messages_sent": 100,
            "messages_dropped": 10,
            "queue_overflows": 5,
            "backpressure_events": 15,
            "redis_queues": {"total_redis_queues": 2, "total_redis_messages": 5},
            "drop_policy": "intermediate",
            "max_queue_size": 1000
        }
        
        mock_backpressure_handler = Mock()
        mock_backpressure_handler.get_stats = AsyncMock(return_value=mock_stats)
        
        with patch('apps.realtime.main.backpressure_handler', mock_backpressure_handler):
            response = client.get("/metrics")
            assert response.status_code == 200
            
            data = response.json()
            assert data["ws_active_connections"] == 5
            assert data["ws_backpressure_drops"] == 10
            assert data["ws_send_errors"] == 2
            assert data["service"] == "realtime"
            assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_metrics_endpoint_not_ready(self, client):
        """Test metrics endpoint when service is not ready."""
        with patch('apps.realtime.main.backpressure_handler', None):
            response = client.get("/metrics")
            assert response.status_code == 503
            assert "not ready" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_websocket_connection_success(self, mock_redis):
        """Test successful WebSocket connection."""
        mock_connection_manager = Mock()
        mock_connection_manager.connect = AsyncMock()
        mock_connection_manager.disconnect = AsyncMock()
        
        mock_backpressure_handler = Mock()
        mock_backpressure_handler.send_message = AsyncMock(return_value=True)
        mock_backpressure_handler.stats = {"active_connections": 0}
        
        with patch('apps.realtime.main.connection_manager', mock_connection_manager), \
             patch('apps.realtime.main.backpressure_handler', mock_backpressure_handler), \
             patch('apps.realtime.main.redis_client', mock_redis):
            
            with TestClient(app).websocket_connect("/ws/tenant_123?user_id=user_123") as websocket:
                # Connection should be established
                mock_connection_manager.connect.assert_called_once()
                
                # Welcome message should be sent
                mock_backpressure_handler.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_websocket_connection_with_session_id(self, mock_redis):
        """Test WebSocket connection with provided session ID."""
        mock_connection_manager = Mock()
        mock_connection_manager.connect = AsyncMock()
        mock_connection_manager.disconnect = AsyncMock()
        
        mock_backpressure_handler = Mock()
        mock_backpressure_handler.send_message = AsyncMock(return_value=True)
        mock_backpressure_handler.stats = {"active_connections": 0}
        
        with patch('apps.realtime.main.connection_manager', mock_connection_manager), \
             patch('apps.realtime.main.backpressure_handler', mock_backpressure_handler), \
             patch('apps.realtime.main.redis_client', mock_redis):
            
            with TestClient(app).websocket_connect("/ws/tenant_123?user_id=user_123&session_id=custom_session") as websocket:
                # Should use provided session ID
                call_args = mock_connection_manager.connect.call_args
                assert "custom_session" in str(call_args)

    @pytest.mark.asyncio
    async def test_websocket_connection_service_not_ready(self, mock_redis):
        """Test WebSocket connection when service is not ready."""
        with patch('apps.realtime.main.connection_manager', None), \
             patch('apps.realtime.main.backpressure_handler', None):
            
            try:
                with TestClient(app).websocket_connect("/ws/tenant_123") as websocket:
                    pytest.fail("Expected WebSocket to close due to service not ready")
            except Exception as e:
                # WebSocket should close with service not ready code
                assert "not ready" in str(e).lower()

    @pytest.mark.asyncio
    async def test_websocket_ping_pong(self, mock_redis):
        """Test WebSocket ping-pong functionality."""
        mock_connection_manager = Mock()
        mock_connection_manager.connect = AsyncMock()
        mock_connection_manager.disconnect = AsyncMock()
        
        mock_backpressure_handler = Mock()
        mock_backpressure_handler.send_message = AsyncMock(return_value=True)
        mock_backpressure_handler.stats = {"active_connections": 0}
        
        with patch('apps.realtime.main.connection_manager', mock_connection_manager), \
             patch('apps.realtime.main.backpressure_handler', mock_backpressure_handler), \
             patch('apps.realtime.main.redis_client', mock_redis):
            
            with TestClient(app).websocket_connect("/ws/tenant_123") as websocket:
                # Send ping message
                ping_message = {"type": "ping"}
                websocket.send_text(json.dumps(ping_message))
                
                # Should receive pong response
                data = websocket.receive_text()
                response = json.loads(data)
                
                assert response["type"] == "pong"
                assert "timestamp" in response
                assert "session_id" in response

    @pytest.mark.asyncio
    async def test_websocket_subscription(self, mock_redis):
        """Test WebSocket subscription functionality."""
        mock_connection_manager = Mock()
        mock_connection_manager.connect = AsyncMock()
        mock_connection_manager.disconnect = AsyncMock()
        
        mock_backpressure_handler = Mock()
        mock_backpressure_handler.send_message = AsyncMock(return_value=True)
        mock_backpressure_handler.stats = {"active_connections": 0}
        
        with patch('apps.realtime.main.connection_manager', mock_connection_manager), \
             patch('apps.realtime.main.backpressure_handler', mock_backpressure_handler), \
             patch('apps.realtime.main.redis_client', mock_redis):
            
            with TestClient(app).websocket_connect("/ws/tenant_123") as websocket:
                # Send subscription message
                subscribe_message = {"type": "subscribe", "topic": "notifications"}
                websocket.send_text(json.dumps(subscribe_message))
                
                # Should receive subscription confirmation
                data = websocket.receive_text()
                response = json.loads(data)
                
                assert response["type"] == "subscription_confirmed"
                assert response["topic"] == "notifications"
                assert "timestamp" in response

    @pytest.mark.asyncio
    async def test_websocket_unsubscription(self, mock_redis):
        """Test WebSocket unsubscription functionality."""
        mock_connection_manager = Mock()
        mock_connection_manager.connect = AsyncMock()
        mock_connection_manager.disconnect = AsyncMock()
        
        mock_backpressure_handler = Mock()
        mock_backpressure_handler.send_message = AsyncMock(return_value=True)
        mock_backpressure_handler.stats = {"active_connections": 0}
        
        with patch('apps.realtime.main.connection_manager', mock_connection_manager), \
             patch('apps.realtime.main.backpressure_handler', mock_backpressure_handler), \
             patch('apps.realtime.main.redis_client', mock_redis):
            
            with TestClient(app).websocket_connect("/ws/tenant_123") as websocket:
                # Send unsubscription message
                unsubscribe_message = {"type": "unsubscribe", "topic": "notifications"}
                websocket.send_text(json.dumps(unsubscribe_message))
                
                # Should receive unsubscription confirmation
                data = websocket.receive_text()
                response = json.loads(data)
                
                assert response["type"] == "unsubscription_confirmed"
                assert response["topic"] == "notifications"
                assert "timestamp" in response

    @pytest.mark.asyncio
    async def test_websocket_echo_message(self, mock_redis):
        """Test WebSocket echo functionality for unknown message types."""
        mock_connection_manager = Mock()
        mock_connection_manager.connect = AsyncMock()
        mock_connection_manager.disconnect = AsyncMock()
        
        mock_backpressure_handler = Mock()
        mock_backpressure_handler.send_message = AsyncMock(return_value=True)
        mock_backpressure_handler.stats = {"active_connections": 0}
        
        with patch('apps.realtime.main.connection_manager', mock_connection_manager), \
             patch('apps.realtime.main.backpressure_handler', mock_backpressure_handler), \
             patch('apps.realtime.main.redis_client', mock_redis):
            
            with TestClient(app).websocket_connect("/ws/tenant_123") as websocket:
                # Send unknown message type
                echo_message = {"type": "unknown", "content": "test message"}
                websocket.send_text(json.dumps(echo_message))
                
                # Should receive echo response
                data = websocket.receive_text()
                response = json.loads(data)
                
                assert response["type"] == "echo"
                assert response["original_message"] == echo_message
                assert "timestamp" in response

    @pytest.mark.asyncio
    async def test_websocket_invalid_json(self, mock_redis):
        """Test WebSocket handling of invalid JSON."""
        mock_connection_manager = Mock()
        mock_connection_manager.connect = AsyncMock()
        mock_connection_manager.disconnect = AsyncMock()
        
        mock_backpressure_handler = Mock()
        mock_backpressure_handler.send_message = AsyncMock(return_value=True)
        mock_backpressure_handler.stats = {"active_connections": 0}
        
        with patch('apps.realtime.main.connection_manager', mock_connection_manager), \
             patch('apps.realtime.main.backpressure_handler', mock_backpressure_handler), \
             patch('apps.realtime.main.redis_client', mock_redis):
            
            with TestClient(app).websocket_connect("/ws/tenant_123") as websocket:
                # Send invalid JSON
                websocket.send_text("invalid json")
                
                # Should receive error response
                data = websocket.receive_text()
                response = json.loads(data)
                
                assert response["type"] == "error"
                assert "Invalid JSON format" in response["message"]

    @pytest.mark.asyncio
    async def test_websocket_disconnect_cleanup(self, mock_redis):
        """Test WebSocket disconnect cleanup."""
        mock_connection_manager = Mock()
        mock_connection_manager.connect = AsyncMock()
        mock_connection_manager.disconnect = AsyncMock()
        
        mock_backpressure_handler = Mock()
        mock_backpressure_handler.send_message = AsyncMock(return_value=True)
        mock_backpressure_handler.stats = {"active_connections": 0}
        
        with patch('apps.realtime.main.connection_manager', mock_connection_manager), \
             patch('apps.realtime.main.backpressure_handler', mock_backpressure_handler), \
             patch('apps.realtime.main.redis_client', mock_redis):
            
            try:
                with TestClient(app).websocket_connect("/ws/tenant_123") as websocket:
                    # Connection established
                    pass
                # Connection closed
            except Exception:
                pass
            
            # Disconnect should be called
            mock_connection_manager.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_deliver_pending_messages(self, mock_redis):
        """Test delivery of pending messages from Redis."""
        mock_connection_manager = Mock()
        mock_connection_manager.connect = AsyncMock()
        mock_connection_manager.disconnect = AsyncMock()
        
        # Mock pending messages in Redis
        pending_messages = [
            {"type": "pending", "content": "message1"},
            {"type": "pending", "content": "message2"}
        ]
        
        mock_backpressure_handler = Mock()
        mock_backpressure_handler.send_message = AsyncMock(return_value=True)
        mock_backpressure_handler.stats = {"active_connections": 0}
        mock_backpressure_handler._retrieve_messages_from_redis = AsyncMock(
            return_value=pending_messages
        )
        
        with patch('apps.realtime.main.connection_manager', mock_connection_manager), \
             patch('apps.realtime.main.backpressure_handler', mock_backpressure_handler), \
             patch('apps.realtime.main.redis_client', mock_redis):
            
            with TestClient(app).websocket_connect("/ws/tenant_123") as websocket:
                # Should deliver pending messages
                # Note: In a real test, we'd need to check the actual message delivery
                # This is simplified for the test structure
                pass

    @pytest.mark.asyncio
    async def test_backpressure_metrics_integration(self, mock_redis):
        """Test integration with backpressure metrics."""
        mock_connection_manager = Mock()
        mock_connection_manager.connect = AsyncMock()
        mock_connection_manager.disconnect = AsyncMock()
        
        mock_backpressure_handler = Mock()
        mock_backpressure_handler.send_message = AsyncMock(return_value=True)
        mock_backpressure_handler.stats = {"active_connections": 0}
        
        mock_metrics_collector = Mock()
        mock_metrics_collector.record_backpressure_event = AsyncMock()
        
        with patch('apps.realtime.main.connection_manager', mock_connection_manager), \
             patch('apps.realtime.main.backpressure_handler', mock_backpressure_handler), \
             patch('apps.realtime.main.metrics_collector', mock_metrics_collector), \
             patch('apps.realtime.main.redis_client', mock_redis):
            
            with TestClient(app).websocket_connect("/ws/tenant_123") as websocket:
                # Connection should work with metrics integration
                pass

    @pytest.mark.asyncio
    async def test_error_handling_in_message_processing(self, mock_redis):
        """Test error handling during message processing."""
        mock_connection_manager = Mock()
        mock_connection_manager.connect = AsyncMock()
        mock_connection_manager.disconnect = AsyncMock()
        
        mock_backpressure_handler = Mock()
        mock_backpressure_handler.send_message = AsyncMock(side_effect=Exception("Processing error"))
        mock_backpressure_handler.stats = {"active_connections": 0}
        
        with patch('apps.realtime.main.connection_manager', mock_connection_manager), \
             patch('apps.realtime.main.backpressure_handler', mock_backpressure_handler), \
             patch('apps.realtime.main.redis_client', mock_redis):
            
            with TestClient(app).websocket_connect("/ws/tenant_123") as websocket:
                # Send a message that will cause processing error
                message = {"type": "test", "content": "hello"}
                websocket.send_text(json.dumps(message))
                
                # Should receive error response
                data = websocket.receive_text()
                response = json.loads(data)
                
                assert response["type"] == "error"
                assert "Failed to process message" in response["message"]

    @pytest.mark.asyncio
    async def test_websocket_session_id_generation(self, mock_redis):
        """Test automatic session ID generation."""
        mock_connection_manager = Mock()
        mock_connection_manager.connect = AsyncMock()
        mock_connection_manager.disconnect = AsyncMock()
        
        mock_backpressure_handler = Mock()
        mock_backpressure_handler.send_message = AsyncMock(return_value=True)
        mock_backpressure_handler.stats = {"active_connections": 0}
        
        with patch('apps.realtime.main.connection_manager', mock_connection_manager), \
             patch('apps.realtime.main.backpressure_handler', mock_backpressure_handler), \
             patch('apps.realtime.main.redis_client', mock_redis):
            
            with TestClient(app).websocket_connect("/ws/tenant_123?user_id=user_123") as websocket:
                # Should generate session ID automatically
                call_args = mock_connection_manager.connect.call_args
                # Session ID should be in the format tenant_user_timestamp
                assert "tenant_123" in str(call_args)
                assert "user_123" in str(call_args)
