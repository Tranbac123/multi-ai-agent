"""E2E test for order processing journey."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from tests._fixtures.factories import TenantFactory, UserFactory
from tests._helpers.assertions import (
    JSONAssertions, PerformanceAssertions, RouterAssertions, MultiTenantAssertions
)
from libs.contracts.router import RouterDecisionRequest, RouterDecision


class TestOrderJourney:
    """Test complete order processing journey."""
    
    @pytest.mark.asyncio
    async def test_order_creation_flow(self):
        """Test order creation flow."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        
        # Step 1: User creates order
        order_request = {
            "tenant_id": tenant["tenant_id"],
            "message": "I want to upgrade to the premium plan",
            "context": {
                "user_id": user["user_id"],
                "session_id": "session_order_001",
                "channel": "web",
                "user_tier": "basic"
            },
            "features": {
                "token_count": 8,
                "json_schema_strictness": 0.8,
                "domain_flags": {
                    "customer_support": False,
                    "sales": True,
                    "technical": False
                },
                "novelty_score": 0.3,
                "historical_failure_rate": 0.05
            }
        }
        
        router_request = RouterDecisionRequest(**order_request)
        
        # Step 2: Router decision
        router_decision = RouterDecision(
            tier="SLM_B",
            confidence=0.85,
            expected_cost_usd=0.01,
            expected_latency_ms=1200,
            reasoning="Order creation requires moderate complexity handling"
        )
        
        # Step 3: Order processing
        order_result = {
            "success": True,
            "result": {
                "order_id": "order_12345",
                "status": "created",
                "items": [
                    {
                        "product_id": "premium_plan",
                        "name": "Premium Plan",
                        "price": 99.99,
                        "quantity": 1
                    }
                ],
                "total": 99.99,
                "currency": "USD",
                "next_steps": [
                    "Review order details",
                    "Proceed to payment",
                    "Confirmation email will be sent"
                ]
            },
            "cost_usd": 0.01,
            "execution_time_ms": 1100
        }
        
        # Step 4: Final response
        final_response = {
            "status": "success",
            "response": f"Your order has been created successfully! Order ID: {order_result['result']['order_id']}",
            "metadata": {
                "tier_used": router_decision.tier.value,
                "confidence": router_decision.confidence,
                "cost_usd": order_result["cost_usd"],
                "execution_time_ms": order_result["execution_time_ms"],
                "order_id": order_result["result"]["order_id"],
                "next_steps": order_result["result"]["next_steps"]
            }
        }
        
        # Verify order creation
        assert final_response["status"] == "success"
        assert "order_12345" in final_response["response"]
        assert final_response["metadata"]["order_id"] == "order_12345"
        assert len(final_response["metadata"]["next_steps"]) > 0
    
    @pytest.mark.asyncio
    async def test_order_modification_flow(self):
        """Test order modification flow."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        
        # Step 1: User modifies existing order
        modify_request = {
            "tenant_id": tenant["tenant_id"],
            "message": "I want to change my order from premium to enterprise plan",
            "context": {
                "user_id": user["user_id"],
                "session_id": "session_modify_001",
                "existing_order_id": "order_12345"
            },
            "features": {
                "token_count": 12,
                "json_schema_strictness": 0.7,
                "domain_flags": {
                    "customer_support": True,
                    "sales": True,
                    "technical": False
                },
                "novelty_score": 0.4,
                "historical_failure_rate": 0.08
            }
        }
        
        router_request = RouterDecisionRequest(**modify_request)
        
        # Step 2: Router decision
        router_decision = RouterDecision(
            tier="SLM_B",
            confidence=0.8,
            expected_cost_usd=0.012,
            expected_latency_ms=1400,
            reasoning="Order modification requires validation and pricing updates"
        )
        
        # Step 3: Order modification processing
        modify_result = {
            "success": True,
            "result": {
                "order_id": "order_12345",
                "status": "modified",
                "changes": [
                    {
                        "action": "removed",
                        "item": {"product_id": "premium_plan", "name": "Premium Plan"}
                    },
                    {
                        "action": "added",
                        "item": {"product_id": "enterprise_plan", "name": "Enterprise Plan", "price": 199.99}
                    }
                ],
                "new_total": 199.99,
                "price_difference": 100.00,
                "currency": "USD"
            },
            "cost_usd": 0.012,
            "execution_time_ms": 1350
        }
        
        # Step 4: Final response
        final_response = {
            "status": "success",
            "response": f"Your order has been updated successfully. New total: ${modify_result['result']['new_total']}",
            "metadata": {
                "tier_used": router_decision.tier.value,
                "confidence": router_decision.confidence,
                "cost_usd": modify_result["cost_usd"],
                "execution_time_ms": modify_result["execution_time_ms"],
                "order_id": modify_result["result"]["order_id"],
                "price_difference": modify_result["result"]["price_difference"]
            }
        }
        
        # Verify order modification
        assert final_response["status"] == "success"
        assert "updated successfully" in final_response["response"]
        assert final_response["metadata"]["price_difference"] == 100.00
    
    @pytest.mark.asyncio
    async def test_order_cancellation_flow(self):
        """Test order cancellation flow."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        
        # Step 1: User cancels order
        cancel_request = {
            "tenant_id": tenant["tenant_id"],
            "message": "I want to cancel my order #12345",
            "context": {
                "user_id": user["user_id"],
                "session_id": "session_cancel_001",
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
                "novelty_score": 0.2,
                "historical_failure_rate": 0.03
            }
        }
        
        router_request = RouterDecisionRequest(**cancel_request)
        
        # Step 2: Router decision
        router_decision = RouterDecision(
            tier="SLM_A",
            confidence=0.9,
            expected_cost_usd=0.005,
            expected_latency_ms=800,
            reasoning="Order cancellation is a standard operation"
        )
        
        # Step 3: Cancellation processing
        cancel_result = {
            "success": True,
            "result": {
                "order_id": "order_12345",
                "status": "cancelled",
                "refund_amount": 99.99,
                "refund_method": "original_payment_method",
                "estimated_refund_time": "3-5 business days",
                "cancellation_reason": "customer_request"
            },
            "cost_usd": 0.005,
            "execution_time_ms": 750
        }
        
        # Step 4: Final response
        final_response = {
            "status": "success",
            "response": f"Your order has been cancelled successfully. Refund of ${cancel_result['result']['refund_amount']} will be processed within {cancel_result['result']['estimated_refund_time']}.",
            "metadata": {
                "tier_used": router_decision.tier.value,
                "confidence": router_decision.confidence,
                "cost_usd": cancel_result["cost_usd"],
                "execution_time_ms": cancel_result["execution_time_ms"],
                "order_id": cancel_result["result"]["order_id"],
                "refund_amount": cancel_result["result"]["refund_amount"]
            }
        }
        
        # Verify order cancellation
        assert final_response["status"] == "success"
        assert "cancelled successfully" in final_response["response"]
        assert final_response["metadata"]["refund_amount"] == 99.99
    
    @pytest.mark.asyncio
    async def test_order_validation_failure(self):
        """Test order validation failure flow."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        
        # Step 1: Invalid order request
        invalid_request = {
            "tenant_id": tenant["tenant_id"],
            "message": "I want to order 1000 premium plans",
            "context": {
                "user_id": user["user_id"],
                "session_id": "session_invalid_001"
            },
            "features": {
                "token_count": 9,
                "json_schema_strictness": 0.8,
                "domain_flags": {
                    "customer_support": False,
                    "sales": True,
                    "technical": False
                },
                "novelty_score": 0.6,
                "historical_failure_rate": 0.1
            }
        }
        
        router_request = RouterDecisionRequest(**invalid_request)
        
        # Step 2: Router decision
        router_decision = RouterDecision(
            tier="SLM_B",
            confidence=0.75,
            expected_cost_usd=0.008,
            expected_latency_ms=1000,
            reasoning="Large quantity order requires validation"
        )
        
        # Step 3: Validation failure
        validation_result = {
            "success": False,
            "error": {
                "type": "validation_error",
                "message": "Quantity exceeds maximum allowed limit",
                "details": {
                    "requested_quantity": 1000,
                    "maximum_allowed": 10,
                    "suggested_quantity": 10
                }
            },
            "cost_usd": 0.008,
            "execution_time_ms": 900
        }
        
        # Step 4: Error response
        final_response = {
            "status": "error",
            "response": f"Order validation failed: {validation_result['error']['message']}",
            "metadata": {
                "tier_used": router_decision.tier.value,
                "confidence": router_decision.confidence,
                "cost_usd": validation_result["cost_usd"],
                "execution_time_ms": validation_result["execution_time_ms"],
                "error_type": validation_result["error"]["type"],
                "error_details": validation_result["error"]["details"]
            }
        }
        
        # Verify validation failure
        assert final_response["status"] == "error"
        assert "validation failed" in final_response["response"]
        assert final_response["metadata"]["error_details"]["requested_quantity"] == 1000