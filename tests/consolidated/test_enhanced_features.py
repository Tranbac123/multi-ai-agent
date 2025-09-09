"""
Test suite for enhanced features
"""
import pytest
import asyncio
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from api.main import app
from services.memory import ConversationMemory, ConversationAnalyzer
from services.analytics import AnalyticsService
from services.file_upload import FileUploadService
from core.exceptions import ValidationError, AIProcessingError

client = TestClient(app)

class TestConversationMemory:
    def setup_method(self):
        self.memory = ConversationMemory()
        self.session_id = "test_session_123"
    
    @pytest.mark.asyncio
    async def test_store_message(self):
        """Test storing message in conversation memory"""
        message = {
            "id": "msg_123",
            "text": "Hello, I need help",
            "role": "user",
            "timestamp": "2024-01-01T10:00:00Z"
        }
        
        # Mock Redis operations
        with patch.object(self.memory.redis_client, 'lpush') as mock_lpush:
            await self.memory.store_message(self.session_id, message)
            mock_lpush.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_conversation_history(self):
        """Test getting conversation history"""
        # Mock Redis response
        mock_messages = [
            '{"id": "msg_1", "text": "Hello", "role": "user"}',
            '{"id": "msg_2", "text": "Hi there!", "role": "assistant"}'
        ]
        
        with patch.object(self.memory.redis_client, 'lrange', return_value=mock_messages):
            history = await self.memory.get_conversation_history(self.session_id)
            assert len(history) == 2
            assert history[0]["text"] == "Hello"
            assert history[1]["text"] == "Hi there!"
    
    @pytest.mark.asyncio
    async def test_get_context(self):
        """Test getting conversation context"""
        mock_history = [
            {"role": "user", "text": "Hello"},
            {"role": "assistant", "text": "Hi there!"},
            {"role": "user", "text": "How are you?"}
        ]
        
        with patch.object(self.memory, 'get_conversation_history', return_value=mock_history):
            context = await self.memory.get_context(self.session_id, 2)
            assert "user: Hello" in context
            assert "assistant: Hi there!" in context

class TestConversationAnalyzer:
    def setup_method(self):
        self.analyzer = ConversationAnalyzer()
        self.session_id = "test_session_123"
    
    @pytest.mark.asyncio
    async def test_analyze_sentiment_positive(self):
        """Test positive sentiment analysis"""
        mock_history = [
            {"role": "user", "text": "This is great! I love it!"},
            {"role": "user", "text": "Amazing service, very happy"}
        ]
        
        with patch.object(self.analyzer.memory, 'get_conversation_history', return_value=mock_history):
            sentiment = await self.analyzer.analyze_sentiment(self.session_id)
            assert sentiment["sentiment"] == "positive"
            assert sentiment["confidence"] > 0.5
    
    @pytest.mark.asyncio
    async def test_analyze_sentiment_negative(self):
        """Test negative sentiment analysis"""
        mock_history = [
            {"role": "user", "text": "This is terrible! I hate it!"},
            {"role": "user", "text": "Awful service, very disappointed"}
        ]
        
        with patch.object(self.analyzer.memory, 'get_conversation_history', return_value=mock_history):
            sentiment = await self.analyzer.analyze_sentiment(self.session_id)
            assert sentiment["sentiment"] == "negative"
            assert sentiment["confidence"] > 0.5
    
    @pytest.mark.asyncio
    async def test_extract_intent_history(self):
        """Test intent extraction from conversation"""
        mock_history = [
            {"role": "user", "text": "I want to buy a t-shirt", "timestamp": "2024-01-01T10:00:00Z"},
            {"role": "user", "text": "Where is my order?", "timestamp": "2024-01-01T10:05:00Z"},
            {"role": "user", "text": "I need help with my account", "timestamp": "2024-01-01T10:10:00Z"}
        ]
        
        with patch.object(self.analyzer.memory, 'get_conversation_history', return_value=mock_history):
            intents = await self.analyzer.extract_intent_history(self.session_id)
            assert len(intents) == 3
            assert intents[0]["intent"] == "purchase"
            assert intents[1]["intent"] == "tracking"
            assert intents[2]["intent"] == "support"

class TestAnalyticsService:
    def setup_method(self):
        self.analytics = AnalyticsService()
    
    @pytest.mark.asyncio
    async def test_track_message(self):
        """Test tracking message for analytics"""
        message_data = {
            "role": "user",
            "text": "Hello",
            "channel": "web",
            "response_time": 1.5
        }
        
        with patch.object(self.analytics, '_increment_counter') as mock_increment:
            await self.analytics.track_message("session_123", message_data)
            assert mock_increment.call_count >= 3  # messages_total, messages_user, messages_channel_web
    
    @pytest.mark.asyncio
    async def test_track_workflow_performance(self):
        """Test tracking workflow performance"""
        with patch.object(self.analytics, '_increment_counter') as mock_increment:
            await self.analytics.track_workflow_performance("FAQ_FLOW", True, 2.5)
            assert mock_increment.call_count >= 2  # workflow_FAQ_FLOW_total, workflow_FAQ_FLOW_success
    
    @pytest.mark.asyncio
    async def test_track_conversion(self):
        """Test tracking conversion events"""
        with patch.object(self.analytics, '_increment_counter') as mock_increment:
            await self.analytics.track_conversion("session_123", "lead", 100.0)
            mock_increment.assert_called_with("conversion_lead")
    
    @pytest.mark.asyncio
    async def test_get_dashboard_metrics(self):
        """Test getting dashboard metrics"""
        with patch.object(self.analytics, '_get_message_metrics', return_value={"total": 100}):
            with patch.object(self.analytics, '_get_workflow_metrics', return_value={}):
                with patch.object(self.analytics, '_get_conversion_metrics', return_value={}):
                    with patch.object(self.analytics, '_get_performance_metrics', return_value={}):
                        with patch.object(self.analytics, '_get_customer_metrics', return_value={}):
                            metrics = await self.analytics.get_dashboard_metrics("24h")
                            assert "messages" in metrics
                            assert "workflows" in metrics
                            assert "conversions" in metrics

class TestFileUploadService:
    def setup_method(self):
        self.upload_service = FileUploadService()
    
    def test_validate_file_valid(self):
        """Test file validation with valid file"""
        mock_file = Mock()
        mock_file.filename = "test.jpg"
        mock_file.read.return_value = b"fake image data"
        
        # Mock file size
        with patch('os.path.getsize', return_value=1024):
            result = asyncio.run(self.upload_service._validate_file(mock_file))
            assert result["valid"] == True
    
    def test_validate_file_too_large(self):
        """Test file validation with file too large"""
        mock_file = Mock()
        mock_file.filename = "test.jpg"
        mock_file.read.return_value = b"x" * (11 * 1024 * 1024)  # 11MB
        
        result = asyncio.run(self.upload_service._validate_file(mock_file))
        assert result["valid"] == False
        assert "File size exceeds" in result["error"]
    
    def test_validate_file_invalid_extension(self):
        """Test file validation with invalid extension"""
        mock_file = Mock()
        mock_file.filename = "test.exe"
        mock_file.read.return_value = b"fake data"
        
        result = asyncio.run(self.upload_service._validate_file(mock_file))
        assert result["valid"] == False
        assert "File type not allowed" in result["error"]

class TestWebSocketAPI:
    def test_websocket_connection(self):
        """Test WebSocket connection"""
        with client.websocket_connect("/ws/chat?session_id=test_session") as websocket:
            # Test welcome message
            data = websocket.receive_json()
            assert data["type"] == "welcome"
            assert "session_id" in data
    
    def test_websocket_message_flow(self):
        """Test WebSocket message flow"""
        with client.websocket_connect("/ws/chat?session_id=test_session") as websocket:
            # Send message
            websocket.send_json({
                "type": "message",
                "text": "Hello, I need help"
            })
            
            # Should receive response
            data = websocket.receive_json()
            assert data["type"] in ["response", "error"]

class TestAnalyticsAPI:
    def test_get_dashboard_metrics(self):
        """Test dashboard metrics API"""
        response = client.get("/analytics/dashboard?time_range=24h")
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert "data" in data
    
    def test_get_realtime_metrics(self):
        """Test real-time metrics API"""
        response = client.get("/analytics/realtime")
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert "data" in data
    
    def test_track_conversion(self):
        """Test conversion tracking API"""
        response = client.post("/analytics/track/conversion", params={
            "session_id": "test_session",
            "conversion_type": "lead",
            "value": 100.0
        })
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True

class TestFileUploadAPI:
    def test_upload_file(self):
        """Test file upload API"""
        files = {"file": ("test.jpg", b"fake image data", "image/jpeg")}
        response = client.post("/files/upload?session_id=test_session", files=files)
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert "data" in data
    
    def test_get_upload_stats(self):
        """Test upload stats API"""
        response = client.get("/files/stats/test_session")
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert "data" in data

class TestErrorHandling:
    def test_validation_error(self):
        """Test validation error handling"""
        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError("Invalid input", "INVALID_INPUT")
        
        assert exc_info.value.message == "Invalid input"
        assert exc_info.value.error_code == "INVALID_INPUT"
    
    def test_ai_processing_error(self):
        """Test AI processing error handling"""
        with pytest.raises(AIProcessingError) as exc_info:
            raise AIProcessingError("AI processing failed", "AI_PROCESSING_FAILED")
        
        assert exc_info.value.message == "AI processing failed"
        assert exc_info.value.error_code == "AI_PROCESSING_FAILED"

if __name__ == "__main__":
    pytest.main([__file__])
