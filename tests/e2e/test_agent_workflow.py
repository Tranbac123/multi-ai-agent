"""End-to-end tests for agent workflows."""

import pytest
import asyncio
from uuid import uuid4
from datetime import datetime

from libs.contracts.agent import AgentSpec, AgentBudgets
from libs.contracts.tool import ToolSpec
from libs.contracts.message import MessageRole
from libs.contracts.router import RouterDecisionRequest, RouterTier
from apps.orchestrator.core.orchestrator import OrchestratorEngine
from apps.router_service.core.router import RouterEngine
from libs.clients.event_bus import EventBus, EventProducer


@pytest.fixture
async def orchestrator():
    """Create orchestrator instance for testing."""
    event_bus = EventBus()
    event_producer = EventProducer(event_bus)
    
    from apps.orchestrator.core.workflow import WorkflowEngine
    from apps.orchestrator.core.saga import SagaManager
    
    workflow_engine = WorkflowEngine()
    saga_manager = SagaManager()
    
    orchestrator = OrchestratorEngine(
        event_producer=event_producer,
        workflow_engine=workflow_engine,
        saga_manager=saga_manager
    )
    
    return orchestrator


@pytest.fixture
async def router():
    """Create router instance for testing."""
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


@pytest.fixture
def sample_agent_spec():
    """Create sample agent specification."""
    budgets = AgentBudgets(
        max_tokens=1000,
        max_cost_usd=0.01,
        wall_ms=5000
    )
    
    return AgentSpec(
        name="customer-support-agent",
        version="1.0.0",
        inputs_schema={
            "type": "object",
            "properties": {
                "user_message": {"type": "string"},
                "conversation_history": {"type": "array"}
            },
            "required": ["user_message"]
        },
        outputs_schema={
            "type": "object",
            "properties": {
                "response": {"type": "string"},
                "confidence": {"type": "number"},
                "actions": {"type": "array"}
            }
        },
        tools_allowed=["search_knowledge_base", "create_ticket", "check_order_status"],
        budgets=budgets,
        role="Customer support agent",
        system_prompt="You are a helpful customer support agent."
    )


@pytest.fixture
def sample_context():
    """Create sample context."""
    return {
        "user_message": "I need help with my order",
        "conversation_history": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi! How can I help you today?"}
        ],
        "user_id": "user123",
        "session_id": str(uuid4())
    }


class TestAgentWorkflowE2E:
    """End-to-end tests for agent workflows."""
    
    @pytest.mark.asyncio
    async def test_simple_customer_support_workflow(
        self, orchestrator, router, sample_agent_spec, sample_context
    ):
        """Test simple customer support workflow."""
        tenant_id = uuid4()
        
        # Create run
        run = await orchestrator.create_run(
            tenant_id=tenant_id,
            agent_spec=sample_agent_spec,
            context=sample_context
        )
        
        # Start run
        await orchestrator.start_run(run.run_id, tenant_id)
        
        # Wait for completion
        await asyncio.sleep(1)
        
        # Verify run completed
        completed_run = await orchestrator.get_run(run.run_id, tenant_id)
        assert completed_run.status in ["completed", "failed"]
        
        # Verify events
        events = await orchestrator.get_run_events(run.run_id, tenant_id)
        event_types = [event["event_type"] for event in events]
        assert "run_requested" in event_types
        assert "run_started" in event_types
    
    @pytest.mark.asyncio
    async def test_router_integration(
        self, orchestrator, router, sample_agent_spec, sample_context
    ):
        """Test router integration with orchestrator."""
        tenant_id = uuid4()
        
        # Create router request
        router_request = RouterDecisionRequest(
            tenant_id=tenant_id,
            task_id=uuid4(),
            requirement="Help customer with order issue",
            text_features={
                "token_count": 50,
                "json_schema_complexity": 0.3,
                "domain_flags": {"ecommerce": True},
                "novelty_score": 0.2,
                "historical_failure_rate": 0.1,
                "reasoning_keywords": ["help"],
                "entity_count": 2,
                "format_strictness": 0.5
            },
            history_stats={
                "total_runs": 100,
                "success_rate": 0.9,
                "avg_latency_ms": 500.0,
                "avg_cost_usd": 0.01,
                "tier_distribution": {"SLM_A": 50, "SLM_B": 30, "LLM": 20}
            }
        )
        
        # Get router decision
        decision = await router.route(router_request)
        
        # Verify decision
        assert decision.tier in [RouterTier.SLM_A, RouterTier.SLM_B, RouterTier.LLM]
        assert 0.0 <= decision.confidence <= 1.0
        assert decision.expected_cost_usd > 0.0
        assert decision.expected_latency_ms > 0
        
        # Create run with router decision
        run = await orchestrator.create_run(
            tenant_id=tenant_id,
            agent_spec=sample_agent_spec,
            context={
                **sample_context,
                "router_decision": decision.dict()
            }
        )
        
        # Start run
        await orchestrator.start_run(run.run_id, tenant_id)
        
        # Wait for completion
        await asyncio.sleep(1)
        
        # Verify run completed
        completed_run = await orchestrator.get_run(run.run_id, tenant_id)
        assert completed_run.status in ["completed", "failed"]
    
    @pytest.mark.asyncio
    async def test_multi_tenant_isolation(
        self, orchestrator, sample_agent_spec, sample_context
    ):
        """Test multi-tenant isolation."""
        tenant1_id = uuid4()
        tenant2_id = uuid4()
        
        # Create runs for different tenants
        run1 = await orchestrator.create_run(
            tenant_id=tenant1_id,
            agent_spec=sample_agent_spec,
            context={**sample_context, "tenant": "tenant1"}
        )
        
        run2 = await orchestrator.create_run(
            tenant_id=tenant2_id,
            agent_spec=sample_agent_spec,
            context={**sample_context, "tenant": "tenant2"}
        )
        
        # Start both runs
        await orchestrator.start_run(run1.run_id, tenant1_id)
        await orchestrator.start_run(run2.run_id, tenant2_id)
        
        # Wait for completion
        await asyncio.sleep(1)
        
        # Verify runs are isolated
        completed_run1 = await orchestrator.get_run(run1.run_id, tenant1_id)
        completed_run2 = await orchestrator.get_run(run2.run_id, tenant2_id)
        
        assert completed_run1.tenant_id == tenant1_id
        assert completed_run2.tenant_id == tenant2_id
        assert completed_run1.run_id != completed_run2.run_id
        
        # Verify tenant 1 cannot access tenant 2's run
        with pytest.raises(ValueError, match="Run does not belong to tenant"):
            await orchestrator.get_run(run2.run_id, tenant1_id)
    
    @pytest.mark.asyncio
    async def test_error_recovery(
        self, orchestrator, sample_agent_spec, sample_context
    ):
        """Test error recovery and compensation."""
        tenant_id = uuid4()
        
        # Create run with error-prone context
        error_context = {
            **sample_context,
            "force_error": True,
            "error_type": "timeout"
        }
        
        run = await orchestrator.create_run(
            tenant_id=tenant_id,
            agent_spec=sample_agent_spec,
            context=error_context
        )
        
        # Start run
        await orchestrator.start_run(run.run_id, tenant_id)
        
        # Wait for completion
        await asyncio.sleep(1)
        
        # Verify run failed gracefully
        failed_run = await orchestrator.get_run(run.run_id, tenant_id)
        assert failed_run.status == "failed"
        assert failed_run.error is not None
        
        # Verify events include error events
        events = await orchestrator.get_run_events(run.run_id, tenant_id)
        event_types = [event["event_type"] for event in events]
        assert "run_failed" in event_types
    
    @pytest.mark.asyncio
    async def test_concurrent_workflows(
        self, orchestrator, sample_agent_spec, sample_context
    ):
        """Test concurrent workflow execution."""
        tenant_id = uuid4()
        
        # Create multiple runs
        runs = []
        for i in range(10):
            run = await orchestrator.create_run(
                tenant_id=tenant_id,
                agent_spec=sample_agent_spec,
                context={**sample_context, "run_number": i}
            )
            runs.append(run)
        
        # Start all runs concurrently
        tasks = []
        for run in runs:
            task = orchestrator.start_run(run.run_id, tenant_id)
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        # Wait for completion
        await asyncio.sleep(2)
        
        # Verify all runs completed
        for run in runs:
            completed_run = await orchestrator.get_run(run.run_id, tenant_id)
            assert completed_run.status in ["completed", "failed", "cancelled"]
    
    @pytest.mark.asyncio
    async def test_workflow_replay(
        self, orchestrator, sample_agent_spec, sample_context
    ):
        """Test workflow replay from events."""
        tenant_id = uuid4()
        
        # Create and execute run
        run = await orchestrator.create_run(
            tenant_id=tenant_id,
            agent_spec=sample_agent_spec,
            context=sample_context
        )
        
        await orchestrator.start_run(run.run_id, tenant_id)
        await asyncio.sleep(1)
        
        # Replay run from events
        replayed_run = await orchestrator.replay_run(run.run_id, tenant_id)
        
        # Verify replayed run matches original
        assert replayed_run.run_id == run.run_id
        assert replayed_run.tenant_id == run.tenant_id
        assert replayed_run.agent_spec.name == run.agent_spec.name
        assert replayed_run.context == run.context
    
    @pytest.mark.asyncio
    async def test_performance_metrics(
        self, orchestrator, sample_agent_spec, sample_context
    ):
        """Test performance metrics collection."""
        tenant_id = uuid4()
        
        # Create run
        run = await orchestrator.create_run(
            tenant_id=tenant_id,
            agent_spec=sample_agent_spec,
            context=sample_context
        )
        
        # Start run and measure time
        start_time = datetime.utcnow()
        await orchestrator.start_run(run.run_id, tenant_id)
        
        # Wait for completion
        await asyncio.sleep(1)
        
        end_time = datetime.utcnow()
        execution_time = (end_time - start_time).total_seconds()
        
        # Verify performance
        assert execution_time < 10.0  # Should complete within 10 seconds
        
        # Verify run has metrics
        completed_run = await orchestrator.get_run(run.run_id, tenant_id)
        assert completed_run.tokens_in >= 0
        assert completed_run.tokens_out >= 0
        assert completed_run.cost_usd >= 0.0
