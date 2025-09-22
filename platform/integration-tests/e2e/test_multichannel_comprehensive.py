"""Comprehensive multi-channel E2E journey tests with production-grade validation."""

import pytest
import asyncio
from typing import Dict, Any, List
from datetime import datetime

from tests.e2e.e2e_framework import e2e_framework, JourneyStatus, JourneyStep
from tests._fixtures.factories import factory, TenantTier
from tests._helpers import test_helpers
from tests.contract.schemas import APIRequest, APIResponse, RequestType


class TestMultiChannelComprehensive:
    """Comprehensive multi-channel journey tests."""
    
    @pytest.fixture
    async def multichannel_setup(self):
        """Setup for multi-channel testing."""
        tenant = factory.create_tenant(name="Multi-Channel Corp", tier=TenantTier.ENTERPRISE)
        user = factory.create_user(tenant_id=tenant.tenant_id, email="customer@multichannel.com")
        
        return {
            'tenant': tenant,
            'user': user,
            'channels': ['web', 'mobile', 'facebook', 'zalo', 'telegram', 'api']
        }
    
    @pytest.mark.asyncio
    async def test_web_to_mobile_continuity(self, multichannel_setup):
        """Test user journey continuity from web to mobile."""
        setup = await multichannel_setup
        
        journey_steps = [
            {
                "step_id": "web_1",
                "step_type": "api_request",
                "endpoint": "/api/web/chat",
                "channel": "web",
                "continue_on_failure": False
            },
            {
                "step_id": "web_2",
                "step_type": "router_decision",
                "expected_tier": "SLM_A",
                "channel": "web",
                "continue_on_failure": False
            },
            {
                "step_id": "web_3",
                "step_type": "tool_execution",
                "tool_id": "faq_search_tool",
                "channel": "web",
                "continue_on_failure": False
            },
            {
                "step_id": "mobile_1",
                "step_type": "api_request",
                "endpoint": "/api/mobile/chat",
                "channel": "mobile",
                "session_transfer": True,
                "continue_on_failure": False
            },
            {
                "step_id": "mobile_2",
                "step_type": "workflow_step",
                "workflow_id": "session_continuation",
                "channel": "mobile",
                "continue_on_failure": False
            },
            {
                "step_id": "mobile_3",
                "step_type": "event_publish",
                "event_type": "session.transferred",
                "channel": "mobile",
                "continue_on_failure": True
            }
        ]
        
        journey_result = await e2e_framework.execute_journey(
            journey_name="web_to_mobile_continuity",
            journey_steps=journey_steps,
            cost_budget=0.05,
            latency_budget=3000
        )
        
        # Validate continuity
        assert journey_result.status == JourneyStatus.COMPLETED
        assert journey_result.metrics.step_count == 6
        
        # Validate session transfer
        session_transfer_steps = [s for s in journey_result.steps if s.step_id == "mobile_1"]
        assert len(session_transfer_steps) == 1
        assert session_transfer_steps[0].status == JourneyStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_facebook_messenger_integration(self, multichannel_setup):
        """Test Facebook Messenger integration journey."""
        setup = await multichannel_setup
        
        journey_steps = [
            {
                "step_id": "fb_1",
                "step_type": "api_request",
                "endpoint": "/api/facebook/webhook",
                "channel": "facebook",
                "continue_on_failure": False
            },
            {
                "step_id": "fb_2",
                "step_type": "router_decision",
                "expected_tier": "SLM_B",
                "channel": "facebook",
                "continue_on_failure": False
            },
            {
                "step_id": "fb_3",
                "step_type": "tool_execution",
                "tool_id": "messenger_response_tool",
                "channel": "facebook",
                "continue_on_failure": False
            },
            {
                "step_id": "fb_4",
                "step_type": "event_publish",
                "event_type": "messenger.message_sent",
                "channel": "facebook",
                "continue_on_failure": True
            }
        ]
        
        journey_result = await e2e_framework.execute_journey(
            journey_name="facebook_messenger",
            journey_steps=journey_steps,
            cost_budget=0.03,
            latency_budget=2000
        )
        
        assert journey_result.status == JourneyStatus.COMPLETED
        assert journey_result.metrics.step_count == 4
    
    @pytest.mark.asyncio
    async def test_zalo_integration_journey(self, multichannel_setup):
        """Test Zalo integration journey."""
        setup = await multichannel_setup
        
        journey_steps = [
            {
                "step_id": "zalo_1",
                "step_type": "api_request",
                "endpoint": "/api/zalo/webhook",
                "channel": "zalo",
                "continue_on_failure": False
            },
            {
                "step_id": "zalo_2",
                "step_type": "router_decision",
                "expected_tier": "SLM_A",
                "channel": "zalo",
                "continue_on_failure": False
            },
            {
                "step_id": "zalo_3",
                "step_type": "tool_execution",
                "tool_id": "zalo_response_tool",
                "channel": "zalo",
                "continue_on_failure": False
            }
        ]
        
        journey_result = await e2e_framework.execute_journey(
            journey_name="zalo_integration",
            journey_steps=journey_steps,
            cost_budget=0.02,
            latency_budget=1500
        )
        
        assert journey_result.status == JourneyStatus.COMPLETED
        assert journey_result.metrics.step_count == 3
    
    @pytest.mark.asyncio
    async def test_telegram_bot_journey(self, multichannel_setup):
        """Test Telegram bot integration journey."""
        setup = await multichannel_setup
        
        journey_steps = [
            {
                "step_id": "tg_1",
                "step_type": "api_request",
                "endpoint": "/api/telegram/webhook",
                "channel": "telegram",
                "continue_on_failure": False
            },
            {
                "step_id": "tg_2",
                "step_type": "router_decision",
                "expected_tier": "SLM_A",
                "channel": "telegram",
                "continue_on_failure": False
            },
            {
                "step_id": "tg_3",
                "step_type": "tool_execution",
                "tool_id": "telegram_bot_tool",
                "channel": "telegram",
                "continue_on_failure": False
            }
        ]
        
        journey_result = await e2e_framework.execute_journey(
            journey_name="telegram_bot",
            journey_steps=journey_steps,
            cost_budget=0.02,
            latency_budget=1500
        )
        
        assert journey_result.status == JourneyStatus.COMPLETED
        assert journey_result.metrics.step_count == 3
    
    @pytest.mark.asyncio
    async def test_api_integration_journey(self, multichannel_setup):
        """Test API integration journey."""
        setup = await multichannel_setup
        
        journey_steps = [
            {
                "step_id": "api_1",
                "step_type": "api_request",
                "endpoint": "/api/v1/chat",
                "channel": "api",
                "continue_on_failure": False
            },
            {
                "step_id": "api_2",
                "step_type": "router_decision",
                "expected_tier": "LLM",
                "channel": "api",
                "continue_on_failure": False
            },
            {
                "step_id": "api_3",
                "step_type": "tool_execution",
                "tool_id": "advanced_ai_tool",
                "channel": "api",
                "continue_on_failure": False
            },
            {
                "step_id": "api_4",
                "step_type": "event_publish",
                "event_type": "api.response_generated",
                "channel": "api",
                "continue_on_failure": True
            }
        ]
        
        journey_result = await e2e_framework.execute_journey(
            journey_name="api_integration",
            journey_steps=journey_steps,
            cost_budget=0.10,
            latency_budget=5000
        )
        
        assert journey_result.status == JourneyStatus.COMPLETED
        assert journey_result.metrics.step_count == 4
    
    @pytest.mark.asyncio
    async def test_cross_channel_escalation(self, multichannel_setup):
        """Test escalation across multiple channels."""
        setup = await multichannel_setup
        
        journey_steps = [
            {
                "step_id": "start_1",
                "step_type": "api_request",
                "endpoint": "/api/web/chat",
                "channel": "web",
                "continue_on_failure": False
            },
            {
                "step_id": "start_2",
                "step_type": "router_decision",
                "expected_tier": "SLM_A",
                "channel": "web",
                "continue_on_failure": False
            },
            {
                "step_id": "escalate_1",
                "step_type": "workflow_step",
                "workflow_id": "escalation_workflow",
                "channel": "web",
                "continue_on_failure": False
            },
            {
                "step_id": "escalate_2",
                "step_type": "tool_execution",
                "tool_id": "human_handoff_tool",
                "channel": "web",
                "continue_on_failure": False
            },
            {
                "step_id": "escalate_3",
                "step_type": "event_publish",
                "event_type": "support.escalated",
                "channel": "web",
                "continue_on_failure": True
            }
        ]
        
        journey_result = await e2e_framework.execute_journey(
            journey_name="cross_channel_escalation",
            journey_steps=journey_steps,
            cost_budget=0.05,
            latency_budget=10000
        )
        
        assert journey_result.status == JourneyStatus.COMPLETED
        assert journey_result.metrics.step_count == 5
        
        # Validate escalation occurred
        escalation_steps = [s for s in journey_result.steps if "escalate" in s.step_id]
        assert len(escalation_steps) == 3
    
    @pytest.mark.asyncio
    async def test_multi_channel_consistency(self, multichannel_setup):
        """Test consistency across multiple channels."""
        setup = await multichannel_setup
        
        # Test same query across different channels
        channels = ['web', 'mobile', 'facebook', 'zalo', 'telegram']
        journey_results = []
        
        for channel in channels:
            journey_steps = [
                {
                    "step_id": f"{channel}_1",
                    "step_type": "api_request",
                    "endpoint": f"/api/{channel}/chat",
                    "channel": channel,
                    "continue_on_failure": False
                },
                {
                    "step_id": f"{channel}_2",
                    "step_type": "router_decision",
                    "expected_tier": "SLM_A",
                    "channel": channel,
                    "continue_on_failure": False
                },
                {
                    "step_id": f"{channel}_3",
                    "step_type": "tool_execution",
                    "tool_id": f"{channel}_response_tool",
                    "channel": channel,
                    "continue_on_failure": False
                }
            ]
            
            journey_result = await e2e_framework.execute_journey(
                journey_name=f"consistency_{channel}",
                journey_steps=journey_steps,
                cost_budget=0.02,
                latency_budget=2000
            )
            
            journey_results.append(journey_result)
        
        # Validate all channels completed successfully
        for result in journey_results:
            assert result.status == JourneyStatus.COMPLETED
            assert result.metrics.step_count == 3
        
        # Validate consistency (all should have similar metrics)
        costs = [r.metrics.total_cost_usd for r in journey_results]
        latencies = [r.metrics.total_duration_ms for r in journey_results if r.metrics.total_duration_ms]
        
        # Costs should be within reasonable range
        assert all(0.001 <= cost <= 0.05 for cost in costs)
        
        # Latencies should be within reasonable range
        if latencies:
            assert all(10 <= latency <= 3000 for latency in latencies)


class TestChannelSpecificFeatures:
    """Test channel-specific features and capabilities."""
    
    @pytest.mark.asyncio
    async def test_web_rich_interactions(self):
        """Test web channel rich interactions."""
        journey_steps = [
            {
                "step_id": "web_rich_1",
                "step_type": "api_request",
                "endpoint": "/api/web/rich-chat",
                "channel": "web",
                "rich_features": ["buttons", "carousel", "quick_replies"],
                "continue_on_failure": False
            },
            {
                "step_id": "web_rich_2",
                "step_type": "tool_execution",
                "tool_id": "rich_response_tool",
                "channel": "web",
                "continue_on_failure": False
            }
        ]
        
        journey_result = await e2e_framework.execute_journey(
            journey_name="web_rich_interactions",
            journey_steps=journey_steps,
            cost_budget=0.03,
            latency_budget=2000
        )
        
        assert journey_result.status == JourneyStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_mobile_push_notifications(self):
        """Test mobile push notification capabilities."""
        journey_steps = [
            {
                "step_id": "mobile_push_1",
                "step_type": "api_request",
                "endpoint": "/api/mobile/push",
                "channel": "mobile",
                "continue_on_failure": False
            },
            {
                "step_id": "mobile_push_2",
                "step_type": "tool_execution",
                "tool_id": "push_notification_tool",
                "channel": "mobile",
                "continue_on_failure": False
            }
        ]
        
        journey_result = await e2e_framework.execute_journey(
            journey_name="mobile_push_notifications",
            journey_steps=journey_steps,
            cost_budget=0.01,
            latency_budget=1000
        )
        
        assert journey_result.status == JourneyStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_social_media_attachments(self):
        """Test social media attachment handling."""
        journey_steps = [
            {
                "step_id": "social_attach_1",
                "step_type": "api_request",
                "endpoint": "/api/facebook/attachment",
                "channel": "facebook",
                "attachment_types": ["image", "video", "document"],
                "continue_on_failure": False
            },
            {
                "step_id": "social_attach_2",
                "step_type": "tool_execution",
                "tool_id": "attachment_processor_tool",
                "channel": "facebook",
                "continue_on_failure": False
            }
        ]
        
        journey_result = await e2e_framework.execute_journey(
            journey_name="social_media_attachments",
            journey_steps=journey_steps,
            cost_budget=0.05,
            latency_budget=5000
        )
        
        assert journey_result.status == JourneyStatus.COMPLETED
