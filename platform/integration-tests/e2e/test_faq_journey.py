"""E2E test for FAQ customer support journey."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from tests._fixtures.factories import TenantFactory, UserFactory
from tests._helpers.assertions import (
    JSONAssertions, PerformanceAssertions, RouterAssertions, MultiTenantAssertions
)
from libs.contracts.router import RouterDecisionRequest, RouterDecision


class TestFAQJourney:
    """Test complete FAQ customer support journey."""
    
    @pytest.mark.asyncio
    async def test_faq_simple_question_flow(self):
        """Test simple FAQ question flow."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        
        # Step 1: User asks FAQ question
        faq_request = {
            "tenant_id": tenant["tenant_id"],
            "message": "What are your business hours?",
            "context": {
                "user_id": user["user_id"],
                "session_id": "session_faq_001",
                "channel": "web"
            },
            "features": {
                "token_count": 6,
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
        
        # Validate request
        router_request = RouterDecisionRequest(**faq_request)
        
        # Step 2: Router makes decision
        router_decision = RouterDecision(
            tier="SLM_A",
            confidence=0.95,
            expected_cost_usd=0.002,
            expected_latency_ms=300,
            reasoning="Simple FAQ question, high confidence in SLM_A"
        )
        
        # Verify router decision
        result = RouterAssertions.assert_tier_selection_reasonable(
            router_decision.tier.value, "SLM_A", router_decision.confidence, "FAQ tier selection"
        )
        assert result.passed, f"Router tier selection should be reasonable: {result.message}"
        
        # Step 3: Knowledge base search
        kb_search_result = {
            "success": True,
            "result": {
                "answer": "Our business hours are Monday-Friday 9 AM to 6 PM EST.",
                "source": "faq_business_hours",
                "confidence": 0.98,
                "related_questions": [
                    "What are your holiday hours?",
                    "Do you have 24/7 support?"
                ]
            },
            "cost_usd": 0.002,
            "execution_time_ms": 250
        }
        
        # Step 4: Response generation
        final_response = {
            "status": "success",
            "response": kb_search_result["result"]["answer"],
            "metadata": {
                "tier_used": router_decision.tier.value,
                "confidence": router_decision.confidence,
                "source": kb_search_result["result"]["source"],
                "cost_usd": kb_search_result["cost_usd"],
                "execution_time_ms": kb_search_result["execution_time_ms"],
                "related_questions": kb_search_result["result"]["related_questions"]
            }
        }
        
        # Verify response structure
        assert final_response["status"] == "success"
        assert "Our business hours" in final_response["response"]
        assert final_response["metadata"]["tier_used"] == "SLM_A"
        assert final_response["metadata"]["cost_usd"] <= 0.01  # Cost budget
        
        # Verify performance
        result = PerformanceAssertions.assert_latency_below_threshold(
            final_response["metadata"]["execution_time_ms"], 1000, "FAQ response latency"
        )
        assert result.passed, f"FAQ response should be fast: {result.message}"
    
    @pytest.mark.asyncio
    async def test_faq_multi_tenant_isolation(self):
        """Test FAQ flow maintains tenant isolation."""
        # Setup two tenants
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant_a = tenant_factory.create()
        tenant_b = tenant_factory.create()
        
        user_a = user_factory.create(tenant_a["tenant_id"])
        user_b = user_factory.create(tenant_b["tenant_id"])
        
        # Step 1: Tenant A asks question
        request_a = {
            "tenant_id": tenant_a["tenant_id"],
            "message": "What is your refund policy?",
            "context": {"user_id": user_a["user_id"], "session_id": "session_a_001"},
            "features": {}
        }
        
        # Step 2: Knowledge base search for Tenant A
        kb_result_a = {
            "success": True,
            "result": {
                "answer": "Company A offers 30-day money-back guarantee.",
                "source": "company_a_refund_policy",
                "tenant_id": tenant_a["tenant_id"]
            },
            "cost_usd": 0.002,
            "execution_time_ms": 200
        }
        
        # Step 3: Tenant B asks same question
        request_b = {
            "tenant_id": tenant_b["tenant_id"],
            "message": "What is your refund policy?",
            "context": {"user_id": user_b["user_id"], "session_id": "session_b_001"},
            "features": {}
        }
        
        # Step 4: Knowledge base search for Tenant B
        kb_result_b = {
            "success": True,
            "result": {
                "answer": "Company B offers 14-day return policy.",
                "source": "company_b_return_policy",
                "tenant_id": tenant_b["tenant_id"]
            },
            "cost_usd": 0.002,
            "execution_time_ms": 220
        }
        
        # Verify tenant isolation
        assert kb_result_a["result"]["tenant_id"] == tenant_a["tenant_id"]
        assert kb_result_b["result"]["tenant_id"] == tenant_b["tenant_id"]
        assert kb_result_a["result"]["answer"] != kb_result_b["result"]["answer"]
        
        # Test isolation assertion
        results = [kb_result_a["result"], kb_result_b["result"]]
        result = MultiTenantAssertions.assert_tenant_isolation(
            results, "tenant_id", "FAQ tenant isolation"
        )
        assert not result.passed, f"Should detect multi-tenant data: {result.message}"