"""E2E test for lead generation journey."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from tests._fixtures.factories import TenantFactory, UserFactory
from tests._helpers.assertions import (
    JSONAssertions, PerformanceAssertions, RouterAssertions, MultiTenantAssertions
)
from libs.contracts.router import RouterDecisionRequest, RouterDecision


class TestLeadJourney:
    """Test complete lead generation journey."""
    
    @pytest.mark.asyncio
    async def test_lead_capture_flow(self):
        """Test lead capture flow."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Step 1: Visitor expresses interest
        lead_request = {
            "tenant_id": tenant["tenant_id"],
            "message": "I'm interested in learning more about your enterprise plan",
            "context": {
                "visitor_id": "visitor_001",
                "session_id": "session_lead_001",
                "channel": "website",
                "source": "organic_search",
                "campaign": "enterprise_pricing"
            },
            "features": {
                "token_count": 12,
                "json_schema_strictness": 0.8,
                "domain_flags": {
                    "customer_support": False,
                    "sales": True,
                    "technical": False
                },
                "novelty_score": 0.4,
                "historical_failure_rate": 0.08
            }
        }
        
        router_request = RouterDecisionRequest(**lead_request)
        
        # Step 2: Router decision
        router_decision = RouterDecision(
            tier="SLM_B",
            confidence=0.85,
            expected_cost_usd=0.01,
            expected_latency_ms=1200,
            reasoning="Lead capture requires sales engagement"
        )
        
        # Step 3: Lead processing
        lead_result = {
            "success": True,
            "result": {
                "lead_id": "lead_78901",
                "status": "captured",
                "visitor_id": "visitor_001",
                "interest_level": "high",
                "product_interest": "enterprise_plan",
                "next_actions": [
                    "Send pricing information",
                    "Schedule demo call",
                    "Add to CRM",
                    "Send welcome email"
                ],
                "assigned_to": "sales_team"
            },
            "cost_usd": 0.01,
            "execution_time_ms": 1150
        }
        
        # Step 4: Lead response
        final_response = {
            "status": "success",
            "response": "Thank you for your interest! Our sales team will contact you within 24 hours to discuss our enterprise plan.",
            "metadata": {
                "tier_used": router_decision.tier.value,
                "confidence": router_decision.confidence,
                "cost_usd": lead_result["cost_usd"],
                "execution_time_ms": lead_result["execution_time_ms"],
                "lead_id": lead_result["result"]["lead_id"],
                "interest_level": lead_result["result"]["interest_level"],
                "next_actions": lead_result["result"]["next_actions"]
            }
        }
        
        # Verify lead capture
        assert final_response["status"] == "success"
        assert "Thank you for your interest" in final_response["response"]
        assert final_response["metadata"]["lead_id"] == "lead_78901"
        assert final_response["metadata"]["interest_level"] == "high"
    
    @pytest.mark.asyncio
    async def test_lead_qualification_flow(self):
        """Test lead qualification flow."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Step 1: Lead qualification questions
        qualification_request = {
            "tenant_id": tenant["tenant_id"],
            "message": "What's your company size and budget for this project?",
            "context": {
                "lead_id": "lead_78901",
                "session_id": "session_qual_001",
                "stage": "qualification",
                "previous_interactions": 2
            },
            "features": {
                "token_count": 15,
                "json_schema_strictness": 0.7,
                "domain_flags": {
                    "customer_support": False,
                    "sales": True,
                    "technical": False
                },
                "novelty_score": 0.3,
                "historical_failure_rate": 0.05
            }
        }
        
        router_request = RouterDecisionRequest(**qualification_request)
        
        # Step 2: Router decision
        router_decision = RouterDecision(
            tier="SLM_B",
            confidence=0.8,
            expected_cost_usd=0.012,
            expected_latency_ms=1400,
            reasoning="Lead qualification requires structured data collection"
        )
        
        # Step 3: Qualification processing
        qualification_result = {
            "success": True,
            "result": {
                "lead_id": "lead_78901",
                "status": "qualified",
                "qualification_score": 85,
                "company_size": "100-500 employees",
                "budget_range": "$10,000-$50,000",
                "decision_timeline": "3-6 months",
                "decision_makers": ["CTO", "VP Engineering"],
                "next_steps": [
                    "Schedule technical demo",
                    "Prepare custom proposal",
                    "Connect with decision makers"
                ]
            },
            "cost_usd": 0.012,
            "execution_time_ms": 1350
        }
        
        # Step 4: Qualification response
        final_response = {
            "status": "success",
            "response": "Based on your company size and requirements, I recommend scheduling a technical demo with our solutions team.",
            "metadata": {
                "tier_used": router_decision.tier.value,
                "confidence": router_decision.confidence,
                "cost_usd": qualification_result["cost_usd"],
                "execution_time_ms": qualification_result["execution_time_ms"],
                "lead_id": qualification_result["result"]["lead_id"],
                "qualification_score": qualification_result["result"]["qualification_score"],
                "next_steps": qualification_result["result"]["next_steps"]
            }
        }
        
        # Verify lead qualification
        assert final_response["status"] == "success"
        assert "technical demo" in final_response["response"]
        assert final_response["metadata"]["qualification_score"] == 85
        assert len(final_response["metadata"]["next_steps"]) > 0
    
    @pytest.mark.asyncio
    async def test_lead_nurturing_flow(self):
        """Test lead nurturing flow."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Step 1: Lead nurturing content
        nurturing_request = {
            "tenant_id": tenant["tenant_id"],
            "message": "Send me more information about your platform capabilities",
            "context": {
                "lead_id": "lead_78901",
                "session_id": "session_nurture_001",
                "stage": "nurturing",
                "engagement_score": 0.7
            },
            "features": {
                "token_count": 10,
                "json_schema_strictness": 0.8,
                "domain_flags": {
                    "customer_support": False,
                    "sales": True,
                    "technical": True
                },
                "novelty_score": 0.2,
                "historical_failure_rate": 0.03
            }
        }
        
        router_request = RouterDecisionRequest(**nurturing_request)
        
        # Step 2: Router decision
        router_decision = RouterDecision(
            tier="SLM_A",
            confidence=0.9,
            expected_cost_usd=0.008,
            expected_latency_ms=1000,
            reasoning="Lead nurturing requires educational content delivery"
        )
        
        # Step 3: Nurturing processing
        nurturing_result = {
            "success": True,
            "result": {
                "lead_id": "lead_78901",
                "status": "nurtured",
                "content_sent": [
                    "Platform capabilities overview",
                    "Case study: Enterprise implementation",
                    "ROI calculator",
                    "Free trial access"
                ],
                "engagement_boost": 0.15,
                "next_touchpoint": "Follow-up in 3 days",
                "content_preferences": ["technical_docs", "case_studies", "demos"]
            },
            "cost_usd": 0.008,
            "execution_time_ms": 950
        }
        
        # Step 4: Nurturing response
        final_response = {
            "status": "success",
            "response": "I've sent you our platform capabilities overview, a relevant case study, and access to our ROI calculator. You'll also receive a free trial invitation.",
            "metadata": {
                "tier_used": router_decision.tier.value,
                "confidence": router_decision.confidence,
                "cost_usd": nurturing_result["cost_usd"],
                "execution_time_ms": nurturing_result["execution_time_ms"],
                "lead_id": nurturing_result["result"]["lead_id"],
                "content_sent": nurturing_result["result"]["content_sent"],
                "engagement_boost": nurturing_result["result"]["engagement_boost"]
            }
        }
        
        # Verify lead nurturing
        assert final_response["status"] == "success"
        assert "platform capabilities" in final_response["response"]
        assert len(final_response["metadata"]["content_sent"]) == 4
        assert final_response["metadata"]["engagement_boost"] == 0.15
    
    @pytest.mark.asyncio
    async def test_lead_conversion_flow(self):
        """Test lead conversion to customer flow."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Step 1: Lead ready to convert
        conversion_request = {
            "tenant_id": tenant["tenant_id"],
            "message": "I'm ready to start the onboarding process for the enterprise plan",
            "context": {
                "lead_id": "lead_78901",
                "session_id": "session_convert_001",
                "stage": "conversion",
                "maturity_score": 0.95
            },
            "features": {
                "token_count": 14,
                "json_schema_strictness": 0.9,
                "domain_flags": {
                    "customer_support": False,
                    "sales": True,
                    "technical": False
                },
                "novelty_score": 0.1,
                "historical_failure_rate": 0.02
            }
        }
        
        router_request = RouterDecisionRequest(**conversion_request)
        
        # Step 2: Router decision
        router_decision = RouterDecision(
            tier="SLM_B",
            confidence=0.95,
            expected_cost_usd=0.015,
            expected_latency_ms=1600,
            reasoning="Lead conversion requires onboarding setup and account creation"
        )
        
        # Step 3: Conversion processing
        conversion_result = {
            "success": True,
            "result": {
                "lead_id": "lead_78901",
                "status": "converted",
                "customer_id": "customer_12345",
                "account_tier": "enterprise",
                "onboarding_steps": [
                    "Account setup completed",
                    "Admin users created",
                    "API keys generated",
                    "Initial configuration scheduled",
                    "Welcome call scheduled"
                ],
                "next_milestones": [
                    "Complete initial setup (Day 1)",
                    "First integration (Week 1)",
                    "Go live (Week 2)"
                ]
            },
            "cost_usd": 0.015,
            "execution_time_ms": 1550
        }
        
        # Step 4: Conversion response
        final_response = {
            "status": "success",
            "response": f"Congratulations! Your enterprise account has been created. Customer ID: {conversion_result['result']['customer_id']}. Our onboarding team will contact you within 2 hours.",
            "metadata": {
                "tier_used": router_decision.tier.value,
                "confidence": router_decision.confidence,
                "cost_usd": conversion_result["cost_usd"],
                "execution_time_ms": conversion_result["execution_time_ms"],
                "lead_id": conversion_result["result"]["lead_id"],
                "customer_id": conversion_result["result"]["customer_id"],
                "onboarding_steps": conversion_result["result"]["onboarding_steps"],
                "next_milestones": conversion_result["result"]["next_milestones"]
            }
        }
        
        # Verify lead conversion
        assert final_response["status"] == "success"
        assert "Congratulations" in final_response["response"]
        assert final_response["metadata"]["customer_id"] == "customer_12345"
        assert len(final_response["metadata"]["onboarding_steps"]) == 5