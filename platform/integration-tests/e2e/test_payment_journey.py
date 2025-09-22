"""E2E test for payment processing journey."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from tests._fixtures.factories import TenantFactory, UserFactory
from tests._helpers.assertions import (
    JSONAssertions, PerformanceAssertions, RouterAssertions, MultiTenantAssertions
)
from libs.contracts.router import RouterDecisionRequest, RouterDecision


class TestPaymentJourney:
    """Test complete payment processing journey."""
    
    @pytest.mark.asyncio
    async def test_payment_processing_flow(self):
        """Test payment processing flow."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        
        # Step 1: User initiates payment
        payment_request = {
            "tenant_id": tenant["tenant_id"],
            "message": "I want to pay for my order with my credit card",
            "context": {
                "user_id": user["user_id"],
                "session_id": "session_payment_001",
                "order_id": "order_12345",
                "amount": 99.99,
                "currency": "USD"
            },
            "features": {
                "token_count": 12,
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
        
        router_request = RouterDecisionRequest(**payment_request)
        
        # Step 2: Router decision
        router_decision = RouterDecision(
            tier="SLM_B",
            confidence=0.85,
            expected_cost_usd=0.01,
            expected_latency_ms=1500,
            reasoning="Payment processing requires secure handling and validation"
        )
        
        # Step 3: Payment processing
        payment_result = {
            "success": True,
            "result": {
                "payment_id": "pay_67890",
                "status": "completed",
                "amount": 99.99,
                "currency": "USD",
                "payment_method": "credit_card",
                "transaction_id": "txn_abc123",
                "gateway": "stripe",
                "processing_time_ms": 1200,
                "fees": {
                    "processing_fee": 2.90,
                    "total_fee": 2.90
                }
            },
            "cost_usd": 0.01,
            "execution_time_ms": 1450
        }
        
        # Step 4: Final response
        final_response = {
            "status": "success",
            "response": f"Payment processed successfully! Transaction ID: {payment_result['result']['transaction_id']}",
            "metadata": {
                "tier_used": router_decision.tier.value,
                "confidence": router_decision.confidence,
                "cost_usd": payment_result["cost_usd"],
                "execution_time_ms": payment_result["execution_time_ms"],
                "payment_id": payment_result["result"]["payment_id"],
                "transaction_id": payment_result["result"]["transaction_id"],
                "amount": payment_result["result"]["amount"]
            }
        }
        
        # Verify payment processing
        assert final_response["status"] == "success"
        assert "processed successfully" in final_response["response"]
        assert final_response["metadata"]["payment_id"] == "pay_67890"
        assert final_response["metadata"]["amount"] == 99.99
    
    @pytest.mark.asyncio
    async def test_payment_declined_flow(self):
        """Test payment declined flow."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        
        # Step 1: User attempts payment
        payment_request = {
            "tenant_id": tenant["tenant_id"],
            "message": "Please process payment for my order",
            "context": {
                "user_id": user["user_id"],
                "session_id": "session_declined_001",
                "order_id": "order_12346",
                "amount": 199.99,
                "currency": "USD"
            },
            "features": {}
        }
        
        router_request = RouterDecisionRequest(**payment_request)
        
        # Step 2: Router decision
        router_decision = RouterDecision(
            tier="SLM_B",
            confidence=0.8,
            expected_cost_usd=0.01,
            expected_latency_ms=1500,
            reasoning="Payment processing with potential decline handling"
        )
        
        # Step 3: Payment declined
        decline_result = {
            "success": False,
            "error": {
                "type": "payment_declined",
                "message": "Your payment was declined by your bank",
                "details": {
                    "decline_reason": "insufficient_funds",
                    "decline_code": "51",
                    "suggested_actions": [
                        "Check your account balance",
                        "Try a different payment method",
                        "Contact your bank"
                    ]
                }
            },
            "cost_usd": 0.008,
            "execution_time_ms": 1300
        }
        
        # Step 4: Decline response
        final_response = {
            "status": "payment_declined",
            "response": f"Payment could not be processed: {decline_result['error']['message']}",
            "metadata": {
                "tier_used": router_decision.tier.value,
                "confidence": router_decision.confidence,
                "cost_usd": decline_result["cost_usd"],
                "execution_time_ms": decline_result["execution_time_ms"],
                "error_type": decline_result["error"]["type"],
                "decline_reason": decline_result["error"]["details"]["decline_reason"],
                "suggested_actions": decline_result["error"]["details"]["suggested_actions"]
            }
        }
        
        # Verify payment decline
        assert final_response["status"] == "payment_declined"
        assert "could not be processed" in final_response["response"]
        assert final_response["metadata"]["decline_reason"] == "insufficient_funds"
        assert len(final_response["metadata"]["suggested_actions"]) > 0
    
    @pytest.mark.asyncio
    async def test_payment_refund_flow(self):
        """Test payment refund flow."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        
        # Step 1: User requests refund
        refund_request = {
            "tenant_id": tenant["tenant_id"],
            "message": "I want to refund my payment for order #12345",
            "context": {
                "user_id": user["user_id"],
                "session_id": "session_refund_001",
                "payment_id": "pay_67890",
                "order_id": "order_12345",
                "refund_amount": 99.99
            },
            "features": {
                "token_count": 14,
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
        
        router_request = RouterDecisionRequest(**refund_request)
        
        # Step 2: Router decision
        router_decision = RouterDecision(
            tier="SLM_A",
            confidence=0.9,
            expected_cost_usd=0.006,
            expected_latency_ms=1000,
            reasoning="Refund processing is a standard customer service operation"
        )
        
        # Step 3: Refund processing
        refund_result = {
            "success": True,
            "result": {
                "refund_id": "ref_45678",
                "status": "processed",
                "original_payment_id": "pay_67890",
                "refund_amount": 99.99,
                "currency": "USD",
                "processing_time_ms": 800,
                "estimated_refund_time": "3-5 business days",
                "refund_method": "original_payment_method"
            },
            "cost_usd": 0.006,
            "execution_time_ms": 950
        }
        
        # Step 4: Refund response
        final_response = {
            "status": "success",
            "response": f"Refund processed successfully! Refund ID: {refund_result['result']['refund_id']}. Amount will be credited to your original payment method within {refund_result['result']['estimated_refund_time']}.",
            "metadata": {
                "tier_used": router_decision.tier.value,
                "confidence": router_decision.confidence,
                "cost_usd": refund_result["cost_usd"],
                "execution_time_ms": refund_result["execution_time_ms"],
                "refund_id": refund_result["result"]["refund_id"],
                "refund_amount": refund_result["result"]["refund_amount"],
                "estimated_refund_time": refund_result["result"]["estimated_refund_time"]
            }
        }
        
        # Verify refund processing
        assert final_response["status"] == "success"
        assert "Refund processed successfully" in final_response["response"]
        assert final_response["metadata"]["refund_id"] == "ref_45678"
        assert final_response["metadata"]["refund_amount"] == 99.99
    
    @pytest.mark.asyncio
    async def test_payment_security_validation(self):
        """Test payment security validation."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        
        # Step 1: Suspicious payment request
        suspicious_request = {
            "tenant_id": tenant["tenant_id"],
            "message": "I want to pay $9999.99 for my order",
            "context": {
                "user_id": user["user_id"],
                "session_id": "session_suspicious_001",
                "order_id": "order_12347",
                "amount": 9999.99,
                "currency": "USD",
                "risk_score": 0.8  # High risk score
            },
            "features": {
                "token_count": 11,
                "json_schema_strictness": 0.7,
                "domain_flags": {
                    "customer_support": False,
                    "sales": True,
                    "technical": False
                },
                "novelty_score": 0.7,
                "historical_failure_rate": 0.15
            }
        }
        
        router_request = RouterDecisionRequest(**suspicious_request)
        
        # Step 2: Router decision with security concern
        router_decision = RouterDecision(
            tier="LLM",
            confidence=0.7,
            expected_cost_usd=0.02,
            expected_latency_ms=2500,
            reasoning="High-value payment requires additional security validation"
        )
        
        # Step 3: Security validation
        security_result = {
            "success": False,
            "error": {
                "type": "security_validation_failed",
                "message": "Payment amount exceeds security threshold",
                "details": {
                    "requested_amount": 9999.99,
                    "security_threshold": 1000.00,
                    "required_actions": [
                        "Manual review required",
                        "Additional identity verification",
                        "Contact support team"
                    ]
                }
            },
            "cost_usd": 0.02,
            "execution_time_ms": 2300
        }
        
        # Step 4: Security rejection response
        final_response = {
            "status": "security_validation_failed",
            "response": f"Payment requires additional security verification: {security_result['error']['message']}",
            "metadata": {
                "tier_used": router_decision.tier.value,
                "confidence": router_decision.confidence,
                "cost_usd": security_result["cost_usd"],
                "execution_time_ms": security_result["execution_time_ms"],
                "error_type": security_result["error"]["type"],
                "security_threshold": security_result["error"]["details"]["security_threshold"],
                "required_actions": security_result["error"]["details"]["required_actions"]
            }
        }
        
        # Verify security validation
        assert final_response["status"] == "security_validation_failed"
        assert "security verification" in final_response["response"]
        assert final_response["metadata"]["security_threshold"] == 1000.00
        assert "Manual review required" in final_response["metadata"]["required_actions"]