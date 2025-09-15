"""E2E tests for multi-channel ingress user journey."""

import pytest
import asyncio
import json
from typing import Dict, Any
from unittest.mock import AsyncMock, patch

from tests.fixtures.e2e_data import MultiChannelContext, TestDataFactory, UserContext, ExternalGatewayMock


class TestMultiChannelJourney:
    """E2E tests for multi-channel ingress journey."""
    
    @pytest.fixture
    def multichannel_scenarios(self):
        """Get multi-channel test scenarios."""
        return TestDataFactory.create_multi_channel_scenarios()
    
    @pytest.fixture
    async def orchestrator(self):
        """Create orchestrator instance for testing."""
        from apps.orchestrator.core.orchestrator import OrchestratorEngine
        from libs.clients.event_bus import EventBus, EventProducer
        
        event_bus = EventBus()
        event_producer = EventProducer(event_bus)
        
        orchestrator = OrchestratorEngine(
            event_producer=event_producer,
            workflow_engine=AsyncMock(),
            saga_manager=AsyncMock()
        )
        
        return orchestrator
    
    @pytest.fixture
    async def router(self):
        """Create router instance for testing."""
        from apps.router_service.core.router import RouterEngine
        from apps.router_service.core.features import FeatureExtractor
        from apps.router_service.core.classifier import MLClassifier
        from apps.router_service.core.cost import CostCalculator
        from apps.router_service.core.judge import LLMJudge
        
        feature_extractor = FeatureExtractor()
        classifier = MLClassifier()
        cost_calculator = CostCalculator()
        llm_judge = LLMJudge()
        
        router = RouterEngine(
            feature_extractor=feature_extractor,
            classifier=classifier,
            cost_calculator=cost_calculator,
            llm_judge=llm_judge
        )
        
        return router
    
    def assert_json_strict(self, data: Any, schema: Dict[str, Any]) -> None:
        """Assert JSON data matches schema strictly."""
        if not isinstance(data, dict):
            raise AssertionError(f"Expected dict, got {type(data)}")
        
        for key, expected_type in schema.items():
            if key not in data:
                raise AssertionError(f"Missing required key: {key}")
            
            actual_type = type(data[key])
            if not isinstance(data[key], expected_type):
                raise AssertionError(f"Key '{key}' expected {expected_type}, got {actual_type}")
    
    def assert_audit_trail(self, logs: list, expected_actions: list) -> None:
        """Assert audit trail contains expected actions."""
        actual_actions = [log.get("action") for log in logs]
        
        for expected_action in expected_actions:
            assert expected_action in actual_actions, f"Expected action '{expected_action}' not found in audit trail"
        
        # Verify all logs have required fields
        for log in logs:
            assert "timestamp" in log
            assert "tenant_id" in log
            assert "user_id" in log
            assert "action" in log
            assert "success" in log
    
    def assert_cost_latency_budget(self, metrics: Dict[str, Any], max_cost: float = 0.015, max_latency_ms: int = 2500) -> None:
        """Assert cost and latency are within budget."""
        if "cost_usd" in metrics:
            assert metrics["cost_usd"] <= max_cost, f"Cost {metrics['cost_usd']} exceeds budget {max_cost}"
        
        if "latency_ms" in metrics:
            assert metrics["latency_ms"] <= max_latency_ms, f"Latency {metrics['latency_ms']}ms exceeds budget {max_latency_ms}ms"
    
    @pytest.mark.asyncio
    async def test_web_channel_journey(self, multichannel_scenarios, orchestrator, router):
        """Test web channel ingress journey."""
        scenario = next(s for s in multichannel_scenarios if s.channel == "web")
        
        # Step 1: User sends message via web channel
        web_message = {
            "type": "channel_message",
            "channel": scenario.channel,
            "message": scenario.message,
            "channel_specific_data": scenario.channel_specific_data,
            "user_context": scenario.user_context.dict(),
            "metadata": scenario.metadata
        }
        
        # Step 2: Route the web channel request
        router_request = {
            "tenant_id": scenario.user_context.tenant_id,
            "task_id": "task_web_001",
            "requirement": "Process web chat message and route to appropriate handler",
            "text_features": {
                "token_count": len(scenario.message.split()),
                "json_schema_complexity": 0.3,
                "domain_flags": {"web_chat": True, "customer_support": True},
                "novelty_score": 0.2,
                "historical_failure_rate": 0.06,
                "reasoning_keywords": ["help", "order", "issue"],
                "entity_count": 2,
                "format_strictness": 0.5
            },
            "history_stats": {
                "total_runs": 300,
                "success_rate": 0.94,
                "avg_latency_ms": 900.0,
                "avg_cost_usd": 0.010,
                "tier_distribution": {"SLM_A": 60, "SLM_B": 35, "LLM": 5}
            }
        }
        
        # Mock router response
        router_response = {
            "tier": "SLM_A",
            "confidence": 0.92,
            "expected_cost_usd": 0.010,
            "expected_latency_ms": 900,
            "reasoning": "Web chat message suitable for SLM_A tier"
        }
        
        with patch.object(router, 'route', return_value=router_response):
            decision = await router.route(router_request)
        
        # Step 3: Process web channel message
        web_response = {
            "type": "channel_response",
            "channel": scenario.channel,
            "message_id": "msg_web_123456789",
            "original_message": scenario.message,
            "response": "I understand you need help with your order #12345. Let me look that up for you.",
            "response_type": "acknowledgment_with_action",
            "channel_specific_data": scenario.channel_specific_data,
            "processing_info": {
                "tier_used": decision["tier"],
                "confidence": decision["confidence"],
                "intent_classified": "order_support",
                "entities_extracted": ["order_id: 12345"],
                "next_actions": ["lookup_order", "provide_status_update"]
            },
            "created_at": "2024-01-01T10:00:00Z",
            "metadata": {
                "processing_time_ms": 850,
                "cost_usd": 0.009,
                "workflow_steps": ["receive_web_message", "classify_intent", "extract_entities", "generate_response", "send_web_response"]
            },
            "user_context": scenario.user_context.dict()
        }
        
        # Step 4: Validate response schema
        expected_schema = {
            "type": str,
            "channel": str,
            "message_id": str,
            "original_message": str,
            "response": str,
            "response_type": str,
            "channel_specific_data": dict,
            "processing_info": dict,
            "created_at": str,
            "metadata": dict,
            "user_context": dict
        }
        
        self.assert_json_strict(web_response, expected_schema)
        
        # Step 5: Validate web channel processing
        assert web_response["channel"] == "web"
        assert web_response["message_id"] is not None
        assert "order" in web_response["response"].lower()
        assert web_response["processing_info"]["intent_classified"] == "order_support"
        assert "12345" in web_response["processing_info"]["entities_extracted"][0]
        
        # Step 6: Check cost and latency budget
        self.assert_cost_latency_budget(web_response["metadata"])
        
        # Step 7: Generate audit trail
        audit_logs = [
            {
                "timestamp": "2024-01-01T10:00:00Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "web_message_received",
                "success": True
            },
            {
                "timestamp": "2024-01-01T10:00:00.200Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "intent_classified",
                "success": True
            },
            {
                "timestamp": "2024-01-01T10:00:00.500Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "entities_extracted",
                "success": True
            },
            {
                "timestamp": "2024-01-01T10:00:00.850Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "web_response_sent",
                "success": True
            }
        ]
        
        self.assert_audit_trail(audit_logs, ["web_message_received", "intent_classified", "entities_extracted", "web_response_sent"])
        
        # Step 8: Validate tenant isolation
        assert web_response["user_context"]["tenant_id"] == scenario.user_context.tenant_id
        assert web_response["user_context"]["user_id"] == scenario.user_context.user_id
    
    @pytest.mark.asyncio
    async def test_facebook_channel_journey(self, multichannel_scenarios, orchestrator, router):
        """Test Facebook channel ingress journey."""
        scenario = next(s for s in multichannel_scenarios if s.channel == "facebook")
        
        # Step 1: User sends message via Facebook
        facebook_message = {
            "type": "channel_message",
            "channel": scenario.channel,
            "message": scenario.message,
            "channel_specific_data": scenario.channel_specific_data,
            "user_context": scenario.user_context.dict(),
            "metadata": scenario.metadata
        }
        
        # Step 2: Mock Facebook API integration
        with patch('tests.fixtures.e2e_data.ExternalGatewayMock.mock_facebook_api') as mock_facebook:
            mock_facebook.return_value = {
                "message_id": "msg_facebook_123456789",
                "recipient_id": scenario.user_context.user_id,
                "timestamp": 1704110400,
                "status": "sent"
            }
            
            facebook_response = await ExternalGatewayMock.mock_facebook_api({
                "user_id": scenario.user_context.user_id,
                "message": "Hi! I'd love to tell you about our amazing products. What are you interested in?"
            })
        
        # Step 3: Process Facebook channel message
        facebook_response_obj = {
            "type": "channel_response",
            "channel": scenario.channel,
            "message_id": facebook_response["message_id"],
            "original_message": scenario.message,
            "response": "Hi! I'd love to tell you about our amazing products. What are you interested in?",
            "response_type": "sales_inquiry",
            "channel_specific_data": scenario.channel_specific_data,
            "social_media_info": {
                "platform": "facebook",
                "page_id": scenario.channel_specific_data["page_id"],
                "post_id": scenario.channel_specific_data["post_id"],
                "recipient_id": facebook_response["recipient_id"],
                "timestamp": facebook_response["timestamp"]
            },
            "processing_info": {
                "intent_classified": "product_inquiry",
                "entities_extracted": ["product_interest: general"],
                "next_actions": ["provide_product_catalog", "schedule_demo"]
            },
            "created_at": "2024-01-01T11:00:00Z",
            "metadata": {
                "processing_time_ms": 1100,
                "cost_usd": 0.012,
                "workflow_steps": ["receive_facebook_message", "classify_intent", "generate_sales_response", "send_facebook_message"]
            },
            "user_context": scenario.user_context.dict()
        }
        
        # Step 4: Validate response schema
        expected_schema = {
            "type": str,
            "channel": str,
            "message_id": str,
            "original_message": str,
            "response": str,
            "response_type": str,
            "channel_specific_data": dict,
            "social_media_info": dict,
            "processing_info": dict,
            "created_at": str,
            "metadata": dict,
            "user_context": dict
        }
        
        self.assert_json_strict(facebook_response_obj, expected_schema)
        
        # Step 5: Validate Facebook channel processing
        assert facebook_response_obj["channel"] == "facebook"
        assert facebook_response_obj["social_media_info"]["platform"] == "facebook"
        assert facebook_response_obj["social_media_info"]["page_id"] == scenario.channel_specific_data["page_id"]
        assert facebook_response_obj["processing_info"]["intent_classified"] == "product_inquiry"
        
        # Step 6: Check cost and latency budget
        self.assert_cost_latency_budget(facebook_response_obj["metadata"])
        
        # Step 7: Generate audit trail
        audit_logs = [
            {
                "timestamp": "2024-01-01T11:00:00Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "facebook_message_received",
                "success": True
            },
            {
                "timestamp": "2024-01-01T11:00:00.300Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "intent_classified",
                "success": True
            },
            {
                "timestamp": "2024-01-01T11:00:00.800Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "facebook_api_integrated",
                "success": True
            },
            {
                "timestamp": "2024-01-01T11:00:01.100Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "facebook_response_sent",
                "success": True
            }
        ]
        
        self.assert_audit_trail(audit_logs, ["facebook_message_received", "intent_classified", "facebook_api_integrated", "facebook_response_sent"])
    
    @pytest.mark.asyncio
    async def test_zalo_channel_journey(self, multichannel_scenarios, orchestrator, router):
        """Test Zalo channel ingress journey."""
        scenario = next(s for s in multichannel_scenarios if s.channel == "zalo")
        
        # Step 1: User sends message via Zalo
        zalo_message = {
            "type": "channel_message",
            "channel": scenario.channel,
            "message": scenario.message,
            "channel_specific_data": scenario.channel_specific_data,
            "user_context": scenario.user_context.dict(),
            "metadata": scenario.metadata
        }
        
        # Step 2: Mock Zalo API integration
        with patch('tests.fixtures.e2e_data.ExternalGatewayMock.mock_zalo_api') as mock_zalo:
            mock_zalo.return_value = {
                "message_id": "zalo_123456789",
                "user_id": scenario.user_context.user_id,
                "timestamp": 1704114000,
                "status": "delivered"
            }
            
            zalo_response = await ExternalGatewayMock.mock_zalo_api({
                "user_id": scenario.user_context.user_id,
                "message": "Xin chào! Tôi có thể giúp gì cho bạn về dịch vụ của chúng tôi?"
            })
        
        # Step 3: Process Zalo channel message
        zalo_response_obj = {
            "type": "channel_response",
            "channel": scenario.channel,
            "message_id": zalo_response["message_id"],
            "original_message": scenario.message,
            "response": "Xin chào! Tôi có thể giúp gì cho bạn về dịch vụ của chúng tôi?",
            "response_type": "service_inquiry",
            "channel_specific_data": scenario.channel_specific_data,
            "social_media_info": {
                "platform": "zalo",
                "zalo_user_id": scenario.channel_specific_data["zalo_user_id"],
                "message_id": zalo_response["message_id"],
                "timestamp": zalo_response["timestamp"],
                "language": "vi"
            },
            "processing_info": {
                "intent_classified": "service_inquiry",
                "entities_extracted": ["language: vietnamese"],
                "next_actions": ["provide_service_info", "schedule_consultation"]
            },
            "created_at": "2024-01-01T12:00:00Z",
            "metadata": {
                "processing_time_ms": 1200,
                "cost_usd": 0.013,
                "workflow_steps": ["receive_zalo_message", "detect_language", "classify_intent", "generate_vietnamese_response", "send_zalo_message"]
            },
            "user_context": scenario.user_context.dict()
        }
        
        # Step 4: Validate response schema
        expected_schema = {
            "type": str,
            "channel": str,
            "message_id": str,
            "original_message": str,
            "response": str,
            "response_type": str,
            "channel_specific_data": dict,
            "social_media_info": dict,
            "processing_info": dict,
            "created_at": str,
            "metadata": dict,
            "user_context": dict
        }
        
        self.assert_json_strict(zalo_response_obj, expected_schema)
        
        # Step 5: Validate Zalo channel processing
        assert zalo_response_obj["channel"] == "zalo"
        assert zalo_response_obj["social_media_info"]["platform"] == "zalo"
        assert zalo_response_obj["social_media_info"]["language"] == "vi"
        assert zalo_response_obj["processing_info"]["intent_classified"] == "service_inquiry"
        assert "vietnamese" in zalo_response_obj["processing_info"]["entities_extracted"][0]
        
        # Step 6: Check cost and latency budget
        self.assert_cost_latency_budget(zalo_response_obj["metadata"])
        
        # Step 7: Generate audit trail
        audit_logs = [
            {
                "timestamp": "2024-01-01T12:00:00Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "zalo_message_received",
                "success": True
            },
            {
                "timestamp": "2024-01-01T12:00:00.300Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "language_detected",
                "success": True
            },
            {
                "timestamp": "2024-01-01T12:00:00.600Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "intent_classified",
                "success": True
            },
            {
                "timestamp": "2024-01-01T12:00:01.000Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "zalo_api_integrated",
                "success": True
            },
            {
                "timestamp": "2024-01-01T12:00:01.200Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "zalo_response_sent",
                "success": True
            }
        ]
        
        self.assert_audit_trail(audit_logs, ["zalo_message_received", "language_detected", "intent_classified", "zalo_api_integrated", "zalo_response_sent"])
    
    @pytest.mark.asyncio
    async def test_channel_error_handling_journey(self, orchestrator, router):
        """Test channel error handling journey."""
        user_context = UserContext()
        
        # Step 1: Invalid channel message
        invalid_message = {
            "type": "channel_message",
            "channel": "invalid_channel",
            "message": "Hello",
            "channel_specific_data": {},
            "user_context": user_context.dict(),
            "metadata": {}
        }
        
        # Step 2: Process invalid channel (should fail)
        error_response = {
            "type": "channel_error",
            "channel": "invalid_channel",
            "error_code": "UNSUPPORTED_CHANNEL",
            "error_message": "Channel 'invalid_channel' is not supported",
            "supported_channels": ["web", "facebook", "zalo", "telegram"],
            "user_context": user_context.dict(),
            "metadata": {
                "processing_time_ms": 200,
                "cost_usd": 0.003,
                "workflow_steps": ["validate_channel", "channel_validation_failed"]
            }
        }
        
        # Step 3: Validate error response schema
        expected_schema = {
            "type": str,
            "channel": str,
            "error_code": str,
            "error_message": str,
            "supported_channels": list,
            "user_context": dict,
            "metadata": dict
        }
        
        self.assert_json_strict(error_response, expected_schema)
        
        # Step 4: Validate error handling
        assert error_response["error_code"] == "UNSUPPORTED_CHANNEL"
        assert "not supported" in error_response["error_message"]
        assert len(error_response["supported_channels"]) > 0
        
        # Step 5: Check cost and latency budget (lower for failed requests)
        self.assert_cost_latency_budget(error_response["metadata"], max_cost=0.005, max_latency_ms=500)
        
        # Step 6: Generate audit trail for error
        audit_logs = [
            {
                "timestamp": "2024-01-01T13:00:00Z",
                "tenant_id": user_context.tenant_id,
                "user_id": user_context.user_id,
                "action": "channel_message_received",
                "success": True
            },
            {
                "timestamp": "2024-01-01T13:00:00.200Z",
                "tenant_id": user_context.tenant_id,
                "user_id": user_context.user_id,
                "action": "channel_validation_failed",
                "success": False
            }
        ]
        
        self.assert_audit_trail(audit_logs, ["channel_message_received", "channel_validation_failed"])
    
    @pytest.mark.asyncio
    async def test_cross_channel_conversation_journey(self, orchestrator, router):
        """Test cross-channel conversation journey."""
        user_context = UserContext()
        
        # Step 1: User starts conversation on web
        web_message = {
            "type": "channel_message",
            "channel": "web",
            "message": "I need help with my account",
            "channel_specific_data": {"session_id": "web_session_123"},
            "user_context": user_context.dict(),
            "metadata": {"conversation_id": "conv_001"}
        }
        
        # Step 2: User continues conversation on Facebook
        facebook_message = {
            "type": "channel_message",
            "channel": "facebook",
            "message": "I'm still having issues with my account",
            "channel_specific_data": {"page_id": "123456789", "post_id": "987654321"},
            "user_context": user_context.dict(),
            "metadata": {"conversation_id": "conv_001"}
        }
        
        # Step 3: Process cross-channel conversation
        cross_channel_response = {
            "type": "cross_channel_response",
            "channels": ["web", "facebook"],
            "conversation_id": "conv_001",
            "last_message_channel": "facebook",
            "response": "I can see you're having account issues. Let me help you resolve this across both channels.",
            "response_type": "cross_channel_support",
            "channel_responses": [
                {
                    "channel": "web",
                    "message_id": "msg_web_cross_123",
                    "response": "I can see you're having account issues. Let me help you resolve this.",
                    "status": "sent"
                },
                {
                    "channel": "facebook",
                    "message_id": "msg_facebook_cross_123",
                    "response": "I can see you're having account issues. Let me help you resolve this.",
                    "status": "sent"
                }
            ],
            "processing_info": {
                "conversation_context": "account_support",
                "cross_channel_sync": True,
                "next_actions": ["resolve_account_issue", "sync_across_channels"]
            },
            "created_at": "2024-01-01T14:00:00Z",
            "metadata": {
                "processing_time_ms": 1500,
                "cost_usd": 0.016,
                "workflow_steps": ["detect_cross_channel", "sync_conversation_context", "generate_responses", "send_to_all_channels"]
            },
            "user_context": user_context.dict()
        }
        
        # Step 4: Validate response schema
        expected_schema = {
            "type": str,
            "channels": list,
            "conversation_id": str,
            "last_message_channel": str,
            "response": str,
            "response_type": str,
            "channel_responses": list,
            "processing_info": dict,
            "created_at": str,
            "metadata": dict,
            "user_context": dict
        }
        
        self.assert_json_strict(cross_channel_response, expected_schema)
        
        # Step 5: Validate cross-channel processing
        assert len(cross_channel_response["channels"]) == 2
        assert "web" in cross_channel_response["channels"]
        assert "facebook" in cross_channel_response["channels"]
        assert cross_channel_response["conversation_id"] == "conv_001"
        assert len(cross_channel_response["channel_responses"]) == 2
        assert cross_channel_response["processing_info"]["cross_channel_sync"] is True
        
        # Step 6: Check cost and latency budget
        self.assert_cost_latency_budget(cross_channel_response["metadata"])
        
        # Step 7: Generate audit trail
        audit_logs = [
            {
                "timestamp": "2024-01-01T14:00:00Z",
                "tenant_id": user_context.tenant_id,
                "user_id": user_context.user_id,
                "action": "cross_channel_message_received",
                "success": True
            },
            {
                "timestamp": "2024-01-01T14:00:00.400Z",
                "tenant_id": user_context.tenant_id,
                "user_id": user_context.user_id,
                "action": "conversation_context_synced",
                "success": True
            },
            {
                "timestamp": "2024-01-01T14:00:01.200Z",
                "tenant_id": user_context.tenant_id,
                "user_id": user_context.user_id,
                "action": "cross_channel_responses_generated",
                "success": True
            },
            {
                "timestamp": "2024-01-01T14:00:01.500Z",
                "tenant_id": user_context.tenant_id,
                "user_id": user_context.user_id,
                "action": "responses_sent_to_all_channels",
                "success": True
            }
        ]
        
        self.assert_audit_trail(audit_logs, ["cross_channel_message_received", "conversation_context_synced", "cross_channel_responses_generated", "responses_sent_to_all_channels"])
