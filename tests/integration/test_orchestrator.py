"""Integration tests for orchestrator service."""

import pytest
import asyncio
from uuid import uuid4
from datetime import datetime

from libs.contracts.agent import AgentSpec, AgentBudgets
from libs.contracts.tool import ToolSpec
from libs.contracts.message import MessageRole
from apps.orchestrator.core.orchestrator import OrchestratorEngine
from apps.orchestrator.core.workflow import WorkflowEngine
from apps.orchestrator.core.saga import SagaManager
from apps.orchestrator.core.event_store import EventStore
from libs.clients.event_bus import EventBus, EventProducer


@pytest.fixture
async def orchestrator():
    """Create orchestrator instance for testing."""
    event_bus = EventBus()
    event_producer = EventProducer(event_bus)
    workflow_engine = WorkflowEngine()
    saga_manager = SagaManager()

    orchestrator = OrchestratorEngine(
        event_producer=event_producer,
        workflow_engine=workflow_engine,
        saga_manager=saga_manager,
    )

    return orchestrator


@pytest.fixture
def sample_agent_spec():
    """Create sample agent specification."""
    budgets = AgentBudgets(max_tokens=1000, max_cost_usd=0.01, wall_ms=5000)

    return AgentSpec(
        name="test-agent",
        version="1.0.0",
        inputs_schema={"type": "object"},
        outputs_schema={"type": "object"},
        tools_allowed=["tool1", "tool2"],
        budgets=budgets,
        role="Test agent",
        system_prompt="You are a test agent.",
    )


@pytest.fixture
def sample_context():
    """Create sample context."""
    return {
        "user_input": "Hello, world!",
        "session_id": str(uuid4()),
        "metadata": {"test": True},
    }


class TestOrchestratorIntegration:
    """Integration tests for orchestrator."""

    @pytest.mark.asyncio
    async def test_create_run(self, orchestrator, sample_agent_spec, sample_context):
        """Test creating a new run."""
        tenant_id = uuid4()

        # Create run
        run = await orchestrator.create_run(
            tenant_id=tenant_id, agent_spec=sample_agent_spec, context=sample_context
        )

        # Verify run
        assert run.tenant_id == tenant_id
        assert run.agent_spec.name == "test-agent"
        assert run.context == sample_context
        assert run.status == "pending"
        assert run.run_id is not None

    @pytest.mark.asyncio
    async def test_start_run(self, orchestrator, sample_agent_spec, sample_context):
        """Test starting a run."""
        tenant_id = uuid4()

        # Create run
        run = await orchestrator.create_run(
            tenant_id=tenant_id, agent_spec=sample_agent_spec, context=sample_context
        )

        # Start run
        await orchestrator.start_run(run.run_id, tenant_id)

        # Verify run status
        updated_run = await orchestrator.get_run(run.run_id, tenant_id)
        assert updated_run.status == "running"

    @pytest.mark.asyncio
    async def test_cancel_run(self, orchestrator, sample_agent_spec, sample_context):
        """Test cancelling a run."""
        tenant_id = uuid4()

        # Create run
        run = await orchestrator.create_run(
            tenant_id=tenant_id, agent_spec=sample_agent_spec, context=sample_context
        )

        # Cancel run
        await orchestrator.cancel_run(run.run_id, tenant_id)

        # Verify run status
        updated_run = await orchestrator.get_run(run.run_id, tenant_id)
        assert updated_run.status == "cancelled"

    @pytest.mark.asyncio
    async def test_get_run_events(
        self, orchestrator, sample_agent_spec, sample_context
    ):
        """Test getting run events."""
        tenant_id = uuid4()

        # Create run
        run = await orchestrator.create_run(
            tenant_id=tenant_id, agent_spec=sample_agent_spec, context=sample_context
        )

        # Get events
        events = await orchestrator.get_run_events(run.run_id, tenant_id)

        # Verify events
        assert len(events) > 0
        assert events[0]["event_type"] == "run_requested"
        assert events[0]["run_id"] == str(run.run_id)

    @pytest.mark.asyncio
    async def test_replay_run(self, orchestrator, sample_agent_spec, sample_context):
        """Test replaying a run from events."""
        tenant_id = uuid4()

        # Create run
        run = await orchestrator.create_run(
            tenant_id=tenant_id, agent_spec=sample_agent_spec, context=sample_context
        )

        # Start run
        await orchestrator.start_run(run.run_id, tenant_id)

        # Replay run
        replayed_run = await orchestrator.replay_run(run.run_id, tenant_id)

        # Verify replayed run
        assert replayed_run.run_id == run.run_id
        assert replayed_run.tenant_id == tenant_id
        assert replayed_run.agent_spec.name == "test-agent"

    @pytest.mark.asyncio
    async def test_tenant_isolation(
        self, orchestrator, sample_agent_spec, sample_context
    ):
        """Test tenant isolation."""
        tenant1_id = uuid4()
        tenant2_id = uuid4()

        # Create run for tenant 1
        run1 = await orchestrator.create_run(
            tenant_id=tenant1_id, agent_spec=sample_agent_spec, context=sample_context
        )

        # Create run for tenant 2
        run2 = await orchestrator.create_run(
            tenant_id=tenant2_id, agent_spec=sample_agent_spec, context=sample_context
        )

        # Verify tenant 1 cannot access tenant 2's run
        with pytest.raises(ValueError, match="Run does not belong to tenant"):
            await orchestrator.get_run(run2.run_id, tenant1_id)

        # Verify tenant 2 cannot access tenant 1's run
        with pytest.raises(ValueError, match="Run does not belong to tenant"):
            await orchestrator.get_run(run1.run_id, tenant2_id)

    @pytest.mark.asyncio
    async def test_concurrent_runs(
        self, orchestrator, sample_agent_spec, sample_context
    ):
        """Test concurrent run execution."""
        tenant_id = uuid4()

        # Create multiple runs
        runs = []
        for i in range(5):
            run = await orchestrator.create_run(
                tenant_id=tenant_id,
                agent_spec=sample_agent_spec,
                context={**sample_context, "run_number": i},
            )
            runs.append(run)

        # Start all runs concurrently
        tasks = []
        for run in runs:
            task = orchestrator.start_run(run.run_id, tenant_id)
            tasks.append(task)

        await asyncio.gather(*tasks)

        # Verify all runs are running
        for run in runs:
            updated_run = await orchestrator.get_run(run.run_id, tenant_id)
            assert updated_run.status == "running"

    @pytest.mark.asyncio
    async def test_error_handling(
        self, orchestrator, sample_agent_spec, sample_context
    ):
        """Test error handling."""
        tenant_id = uuid4()

        # Test getting non-existent run
        with pytest.raises(ValueError, match="Run .* not found"):
            await orchestrator.get_run(uuid4(), tenant_id)

        # Test cancelling non-existent run
        with pytest.raises(ValueError, match="Run .* not found"):
            await orchestrator.cancel_run(uuid4(), tenant_id)

        # Test getting events for non-existent run
        with pytest.raises(ValueError, match="Run .* not found"):
            await orchestrator.get_run_events(uuid4(), tenant_id)

    @pytest.mark.asyncio
    async def test_run_lifecycle(self, orchestrator, sample_agent_spec, sample_context):
        """Test complete run lifecycle."""
        tenant_id = uuid4()

        # Create run
        run = await orchestrator.create_run(
            tenant_id=tenant_id, agent_spec=sample_agent_spec, context=sample_context
        )

        # Verify initial state
        assert run.status == "pending"
        assert run.finished_at is None

        # Start run
        await orchestrator.start_run(run.run_id, tenant_id)

        # Verify running state
        running_run = await orchestrator.get_run(run.run_id, tenant_id)
        assert running_run.status == "running"

        # Cancel run
        await orchestrator.cancel_run(run.run_id, tenant_id)

        # Verify cancelled state
        cancelled_run = await orchestrator.get_run(run.run_id, tenant_id)
        assert cancelled_run.status == "cancelled"
        assert cancelled_run.finished_at is not None

        # Verify events
        events = await orchestrator.get_run_events(run.run_id, tenant_id)
        event_types = [event["event_type"] for event in events]
        assert "run_requested" in event_types
        assert "run_started" in event_types
        assert "run_cancelled" in event_types
