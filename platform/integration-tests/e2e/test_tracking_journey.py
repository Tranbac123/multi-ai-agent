"""E2E test for order tracking journey."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from tests._fixtures.factories import TenantFactory, UserFactory
from tests._helpers.assertions import (
    JSONAssertions, PerformanceAssertions, RouterAssertions, MultiTenantAssertions
)
from libs.contracts.router import RouterDecisionRequest, RouterDecision


class TestTrackingJourney:
    """Test complete order tracking journey."""
    
    @pytest.mark.asyncio
    async def test_order_status_tracking_flow(self):
        """Test order status tracking flow."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        
        # Step 1: User checks order status
        tracking_request = {
            "tenant_id": tenant["tenant_id"],
            "message": "What's the status of my order #12345?",
            "context": {
                "user_id": user["user_id"],
                "session_id": "session_track_001",
                "order_id": "order_12345"
            },
            "features": {
                "token_count": 10,
                "json_schema_strictness": 0.9,
                "domain_flags": {
                    "customer_support": True,
                    "sales": False,
                    "technical": False
                },
                "novelty_score": 0.1,
                "historical_failure_rate": 0.02
            }
        }
        
        router_request = RouterDecisionRequest(**tracking_request)
        
        # Step 2: Router decision
        router_decision = RouterDecision(
            tier="SLM_A",
            confidence=0.95,
            expected_cost_usd=0.005,
            expected_latency_ms=500,
            reasoning="Order status check is a standard lookup operation"
        )
        
        # Step 3: Order status lookup
        status_result = {
            "success": True,
            "result": {
                "order_id": "order_12345",
                "status": "shipped",
                "current_location": "Distribution Center - Chicago",
                "estimated_delivery": "2024-01-15",
                "tracking_number": "1Z999AA1234567890",
                "shipping_carrier": "UPS",
                "status_history": [
                    {"status": "placed", "timestamp": "2024-01-10T10:00:00Z"},
                    {"status": "processing", "timestamp": "2024-01-10T14:30:00Z"},
                    {"status": "shipped", "timestamp": "2024-01-11T09:15:00Z"}
                ]
            },
            "cost_usd": 0.005,
            "execution_time_ms": 450
        }
        
        # Step 4: Status response
        final_response = {
            "status": "success",
            "response": f"Your order #{status_result['result']['order_id']} is currently {status_result['result']['status']} and on its way to you. Estimated delivery: {status_result['result']['estimated_delivery']}.",
            "metadata": {
                "tier_used": router_decision.tier.value,
                "confidence": router_decision.confidence,
                "cost_usd": status_result["cost_usd"],
                "execution_time_ms": status_result["execution_time_ms"],
                "order_id": status_result["result"]["order_id"],
                "current_status": status_result["result"]["status"],
                "tracking_number": status_result["result"]["tracking_number"],
                "estimated_delivery": status_result["result"]["estimated_delivery"]
            }
        }
        
        # Verify order tracking
        assert final_response["status"] == "success"
        assert "order #12345" in final_response["response"]
        assert final_response["metadata"]["current_status"] == "shipped"
        assert final_response["metadata"]["tracking_number"] == "1Z999AA1234567890"
    
    @pytest.mark.asyncio
    async def test_delivery_tracking_flow(self):
        """Test delivery tracking flow."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        
        # Step 1: User tracks delivery
        delivery_request = {
            "tenant_id": tenant["tenant_id"],
            "message": "Track my package with tracking number 1Z999AA1234567890",
            "context": {
                "user_id": user["user_id"],
                "session_id": "session_delivery_001",
                "tracking_number": "1Z999AA1234567890"
            },
            "features": {
                "token_count": 12,
                "json_schema_strictness": 0.9,
                "domain_flags": {
                    "customer_support": True,
                    "sales": False,
                    "technical": False
                },
                "novelty_score": 0.1,
                "historical_failure_rate": 0.02
            }
        }
        
        router_request = RouterDecisionRequest(**delivery_request)
        
        # Step 2: Router decision
        router_decision = RouterDecision(
            tier="SLM_A",
            confidence=0.9,
            expected_cost_usd=0.006,
            expected_latency_ms=600,
            reasoning="Package tracking requires carrier API integration"
        )
        
        # Step 3: Delivery tracking
        delivery_result = {
            "success": True,
            "result": {
                "tracking_number": "1Z999AA1234567890",
                "carrier": "UPS",
                "status": "in_transit",
                "current_location": "Memphis, TN",
                "destination": "Chicago, IL",
                "estimated_delivery": "2024-01-15 by 6:00 PM",
                "tracking_events": [
                    {
                        "timestamp": "2024-01-11T09:15:00Z",
                        "location": "Chicago, IL",
                        "status": "Package picked up"
                    },
                    {
                        "timestamp": "2024-01-12T02:30:00Z",
                        "location": "Memphis, TN",
                        "status": "In transit"
                    }
                ]
            },
            "cost_usd": 0.006,
            "execution_time_ms": 550
        }
        
        # Step 4: Delivery response
        final_response = {
            "status": "success",
            "response": f"Your package is currently in transit from Memphis, TN to Chicago, IL. Estimated delivery: {delivery_result['result']['estimated_delivery']}.",
            "metadata": {
                "tier_used": router_decision.tier.value,
                "confidence": router_decision.confidence,
                "cost_usd": delivery_result["cost_usd"],
                "execution_time_ms": delivery_result["execution_time_ms"],
                "tracking_number": delivery_result["result"]["tracking_number"],
                "current_status": delivery_result["result"]["status"],
                "current_location": delivery_result["result"]["current_location"],
                "tracking_events": delivery_result["result"]["tracking_events"]
            }
        }
        
        # Verify delivery tracking
        assert final_response["status"] == "success"
        assert "in transit" in final_response["response"]
        assert final_response["metadata"]["current_location"] == "Memphis, TN"
        assert len(final_response["metadata"]["tracking_events"]) == 2
    
    @pytest.mark.asyncio
    async def test_tracking_not_found_flow(self):
        """Test tracking when order/tracking number not found."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        
        # Step 1: User checks non-existent order
        not_found_request = {
            "tenant_id": tenant["tenant_id"],
            "message": "What's the status of my order #99999?",
            "context": {
                "user_id": user["user_id"],
                "session_id": "session_notfound_001",
                "order_id": "order_99999"
            },
            "features": {}
        }
        
        router_request = RouterDecisionRequest(**not_found_request)
        
        # Step 2: Router decision
        router_decision = RouterDecision(
            tier="SLM_A",
            confidence=0.8,
            expected_cost_usd=0.004,
            expected_latency_ms=400,
            reasoning="Order lookup with potential not found result"
        )
        
        # Step 3: Order not found
        not_found_result = {
            "success": False,
            "error": {
                "type": "order_not_found",
                "message": "Order #99999 not found in our system",
                "details": {
                    "searched_order_id": "order_99999",
                    "possible_reasons": [
                        "Order ID is incorrect",
                        "Order is from a different account",
                        "Order was created very recently"
                    ],
                    "suggested_actions": [
                        "Verify the order ID",
                        "Check your email for order confirmation",
                        "Contact customer support"
                    ]
                }
            },
            "cost_usd": 0.004,
            "execution_time_ms": 350
        }
        
        # Step 4: Not found response
        final_response = {
            "status": "order_not_found",
            "response": f"I couldn't find order #{not_found_request['context']['order_id']} in our system. Please verify the order ID or contact customer support.",
            "metadata": {
                "tier_used": router_decision.tier.value,
                "confidence": router_decision.confidence,
                "cost_usd": not_found_result["cost_usd"],
                "execution_time_ms": not_found_result["execution_time_ms"],
                "error_type": not_found_result["error"]["type"],
                "searched_order_id": not_found_result["error"]["details"]["searched_order_id"],
                "suggested_actions": not_found_result["error"]["details"]["suggested_actions"]
            }
        }
        
        # Verify not found handling
        assert final_response["status"] == "order_not_found"
        assert "couldn't find order" in final_response["response"]
        assert final_response["metadata"]["searched_order_id"] == "order_99999"
        assert len(final_response["metadata"]["suggested_actions"]) > 0
    
    @pytest.mark.asyncio
    async def test_tracking_delivery_delay_flow(self):
        """Test tracking when delivery is delayed."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        
        # Step 1: User checks delayed order
        delay_request = {
            "tenant_id": tenant["tenant_id"],
            "message": "My order was supposed to arrive yesterday but didn't. What's happening?",
            "context": {
                "user_id": user["user_id"],
                "session_id": "session_delay_001",
                "order_id": "order_12346",
                "expected_delivery": "2024-01-14"
            },
            "features": {
                "token_count": 18,
                "json_schema_strictness": 0.8,
                "domain_flags": {
                    "customer_support": True,
                    "sales": False,
                    "technical": False
                },
                "novelty_score": 0.3,
                "historical_failure_rate": 0.05
            }
        }
        
        router_request = RouterDecisionRequest(**delay_request)
        
        # Step 2: Router decision
        router_decision = RouterDecision(
            tier="SLM_B",
            confidence=0.8,
            expected_cost_usd=0.008,
            expected_latency_ms=800,
            reasoning="Delivery delay requires investigation and customer communication"
        )
        
        # Step 3: Delay investigation
        delay_result = {
            "success": True,
            "result": {
                "order_id": "order_12346",
                "status": "delayed",
                "delay_reason": "Weather conditions",
                "new_estimated_delivery": "2024-01-16",
                "delay_duration": "2 days",
                "compensation_offered": {
                    "type": "shipping_refund",
                    "amount": 15.99,
                    "status": "pending"
                },
                "tracking_updates": [
                    {
                        "timestamp": "2024-01-13T14:20:00Z",
                        "location": "Denver, CO",
                        "status": "Delivery delayed due to weather"
                    }
                ]
            },
            "cost_usd": 0.008,
            "execution_time_ms": 750
        }
        
        # Step 4: Delay response
        final_response = {
            "status": "success",
            "response": f"I apologize for the delay. Your order has been delayed due to weather conditions. New estimated delivery: {delay_result['result']['new_estimated_delivery']}. We're offering a shipping refund of ${delay_result['result']['compensation_offered']['amount']} as compensation.",
            "metadata": {
                "tier_used": router_decision.tier.value,
                "confidence": router_decision.confidence,
                "cost_usd": delay_result["cost_usd"],
                "execution_time_ms": delay_result["execution_time_ms"],
                "order_id": delay_result["result"]["order_id"],
                "delay_reason": delay_result["result"]["delay_reason"],
                "new_estimated_delivery": delay_result["result"]["new_estimated_delivery"],
                "compensation_amount": delay_result["result"]["compensation_offered"]["amount"]
            }
        }
        
        # Verify delay handling
        assert final_response["status"] == "success"
        assert "delay" in final_response["response"]
        assert final_response["metadata"]["delay_reason"] == "Weather conditions"
        assert final_response["metadata"]["compensation_amount"] == 15.99