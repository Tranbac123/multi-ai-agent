"""Unit tests for contracts."""

import pytest
from uuid import uuid4
from datetime import datetime

from libs.contracts.agent import AgentSpec, AgentRun, AgentBudgets
from libs.contracts.tool import ToolSpec, ToolCall, ToolResult
from libs.contracts.message import MessageSpec, MessageRole
from libs.contracts.error import ErrorSpec, ErrorCode
from libs.contracts.router import RouterDecisionRequest, RouterDecisionResponse, RouterTier
from libs.contracts.billing import UsageCounter, BillingEvent
from libs.contracts.tenant import Tenant, User, APIKey, Plan


class TestAgentContracts:
    """Test agent contracts."""
    
    def test_agent_spec_creation(self):
        """Test AgentSpec creation."""
        budgets = AgentBudgets(
            max_tokens=1000,
            max_cost_usd=0.01,
            wall_ms=5000
        )
        
        spec = AgentSpec(
            name="test-agent",
            version="1.0.0",
            inputs_schema={"type": "object"},
            outputs_schema={"type": "object"},
            tools_allowed=["tool1", "tool2"],
            budgets=budgets,
            role="Test agent",
            system_prompt="You are a test agent."
        )
        
        assert spec.name == "test-agent"
        assert spec.version == "1.0.0"
        assert spec.budgets.max_tokens == 1000
    
    def test_agent_run_creation(self):
        """Test AgentRun creation."""
        tenant_id = uuid4()
        budgets = AgentBudgets(max_tokens=1000, max_cost_usd=0.01, wall_ms=5000)
        spec = AgentSpec(
            name="test-agent",
            version="1.0.0",
            inputs_schema={"type": "object"},
            outputs_schema={"type": "object"},
            tools_allowed=[],
            budgets=budgets,
            role="Test agent",
            system_prompt="You are a test agent."
        )
        
        run = AgentRun(
            tenant_id=tenant_id,
            workflow="test-workflow",
            agent_spec=spec
        )
        
        assert run.tenant_id == tenant_id
        assert run.workflow == "test-workflow"
        assert run.status == "pending"


class TestToolContracts:
    """Test tool contracts."""
    
    def test_tool_spec_creation(self):
        """Test ToolSpec creation."""
        spec = ToolSpec(
            id="test-tool",
            name="Test Tool",
            description="A test tool",
            request_schema={"type": "object"},
            response_schema={"type": "object"},
            error_schema={"type": "object"},
            timeout_ms=5000,
            idempotent=True,
            has_compensation=True
        )
        
        assert spec.id == "test-tool"
        assert spec.timeout_ms == 5000
        assert spec.idempotent is True
    
    def test_tool_call_creation(self):
        """Test ToolCall creation."""
        tenant_id = uuid4()
        run_id = uuid4()
        step_id = uuid4()
        
        call = ToolCall(
            tool_id="test-tool",
            tenant_id=tenant_id,
            run_id=run_id,
            step_id=step_id,
            request_data={"input": "test"}
        )
        
        assert call.tool_id == "test-tool"
        assert call.tenant_id == tenant_id
        assert call.request_data == {"input": "test"}


class TestMessageContracts:
    """Test message contracts."""
    
    def test_message_spec_creation(self):
        """Test MessageSpec creation."""
        tenant_id = uuid4()
        run_id = uuid4()
        
        message = MessageSpec(
            run_id=run_id,
            tenant_id=tenant_id,
            role=MessageRole.USER,
            payload={"text": "Hello"}
        )
        
        assert message.run_id == run_id
        assert message.tenant_id == tenant_id
        assert message.role == MessageRole.USER


class TestErrorContracts:
    """Test error contracts."""
    
    def test_error_spec_creation(self):
        """Test ErrorSpec creation."""
        error = ErrorSpec(
            code=ErrorCode.TIMEOUT,
            message="Request timeout",
            retriable=True,
            retry_after_ms=5000
        )
        
        assert error.code == ErrorCode.TIMEOUT
        assert error.retriable is True
        assert error.retry_after_ms == 5000


class TestRouterContracts:
    """Test router contracts."""
    
    def test_router_decision_request_creation(self):
        """Test RouterDecisionRequest creation."""
        tenant_id = uuid4()
        task_id = uuid4()
        
        request = RouterDecisionRequest(
            tenant_id=tenant_id,
            task_id=task_id,
            requirement="Test requirement",
            text_features={
                "token_count": 100,
                "json_schema_complexity": 0.5,
                "domain_flags": {"finance": True},
                "novelty_score": 0.3,
                "historical_failure_rate": 0.1,
                "reasoning_keywords": ["analyze"],
                "entity_count": 5,
                "format_strictness": 0.7
            },
            history_stats={
                "total_runs": 100,
                "success_rate": 0.9,
                "avg_latency_ms": 500.0,
                "avg_cost_usd": 0.01,
                "tier_distribution": {"SLM_A": 50, "SLM_B": 30, "LLM": 20}
            }
        )
        
        assert request.tenant_id == tenant_id
        assert request.task_id == task_id
        assert request.requirement == "Test requirement"
    
    def test_router_decision_response_creation(self):
        """Test RouterDecisionResponse creation."""
        request_id = uuid4()
        
        response = RouterDecisionResponse(
            request_id=request_id,
            tier=RouterTier.SLM_B,
            confidence=0.8,
            expected_cost_usd=0.005,
            expected_latency_ms=300,
            reasons=["Medium complexity detected"]
        )
        
        assert response.request_id == request_id
        assert response.tier == RouterTier.SLM_B
        assert response.confidence == 0.8


class TestBillingContracts:
    """Test billing contracts."""
    
    def test_usage_counter_creation(self):
        """Test UsageCounter creation."""
        tenant_id = uuid4()
        counter = UsageCounter(
            tenant_id=tenant_id,
            day=datetime.now().date(),
            tokens_in=1000,
            tokens_out=500,
            tool_calls=10,
            ws_minutes=60,
            storage_mb=100,
            cost_usd=0.05
        )
        
        assert counter.tenant_id == tenant_id
        assert counter.tokens_in == 1000
        assert counter.cost_usd == 0.05
    
    def test_billing_event_creation(self):
        """Test BillingEvent creation."""
        tenant_id = uuid4()
        event = BillingEvent(
            tenant_id=tenant_id,
            event_type="tokens",
            quantity=100,
            unit_cost_usd=0.0001,
            total_cost_usd=0.01
        )
        
        assert event.tenant_id == tenant_id
        assert event.event_type == "tokens"
        assert event.quantity == 100


class TestTenantContracts:
    """Test tenant contracts."""
    
    def test_tenant_creation(self):
        """Test Tenant creation."""
        tenant_id = uuid4()
        plan_id = uuid4()
        
        tenant = Tenant(
            tenant_id=tenant_id,
            name="Test Tenant",
            plan_id=plan_id,
            status="active",
            data_region="us-east-1"
        )
        
        assert tenant.tenant_id == tenant_id
        assert tenant.name == "Test Tenant"
        assert tenant.status == "active"
    
    def test_user_creation(self):
        """Test User creation."""
        user_id = uuid4()
        tenant_id = uuid4()
        
        user = User(
            user_id=user_id,
            tenant_id=tenant_id,
            email="test@example.com",
            role="user"
        )
        
        assert user.user_id == user_id
        assert user.tenant_id == tenant_id
        assert user.email == "test@example.com"
    
    def test_api_key_creation(self):
        """Test APIKey creation."""
        key_id = uuid4()
        tenant_id = uuid4()
        
        api_key = APIKey(
            key_id=key_id,
            tenant_id=tenant_id,
            key_hash="hashed_key",
            scopes=["read", "write"],
            rate_limit=1000
        )
        
        assert api_key.key_id == key_id
        assert api_key.tenant_id == tenant_id
        assert api_key.scopes == ["read", "write"]
    
    def test_plan_creation(self):
        """Test Plan creation."""
        plan_id = uuid4()
        
        plan = Plan(
            plan_id=plan_id,
            name="Test Plan",
            price_usd=29.99,
            quotas={"tokens_per_day": 100000},
            features={"analytics": True}
        )
        
        assert plan.plan_id == plan_id
        assert plan.name == "Test Plan"
        assert plan.price_usd == 29.99
