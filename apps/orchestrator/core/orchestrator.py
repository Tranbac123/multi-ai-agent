"""LangGraph-based orchestrator with event sourcing."""

import asyncio
import time
from typing import Dict, Any, Optional, List
from uuid import UUID, uuid4
import structlog
from opentelemetry import trace

from libs.contracts.agent import AgentRun, AgentStep, AgentSpec
from libs.contracts.tool import ToolCall, ToolResult
from libs.contracts.message import MessageSpec, MessageRole
from libs.contracts.error import ErrorSpec, ErrorCode
from libs.clients.event_bus import EventProducer
from .workflow import WorkflowEngine
from .saga import SagaManager
from .event_store import EventStore
from .state_machine import AgentStateMachine

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


class OrchestratorEngine:
    """LangGraph-based orchestrator with event sourcing."""

    def __init__(
        self,
        event_producer: EventProducer,
        workflow_engine: WorkflowEngine,
        saga_manager: SagaManager,
    ):
        self.event_producer = event_producer
        self.workflow_engine = workflow_engine
        self.saga_manager = saga_manager
        self.event_store = EventStore()
        self.state_machine = AgentStateMachine()
        self.active_runs: Dict[UUID, AgentRun] = {}
        self._ready = False
        self._initialize()

    def _initialize(self):
        """Initialize orchestrator engine."""
        try:
            self.workflow_engine.initialize()
            self.saga_manager.initialize()
            self.event_store.initialize()
            self.state_machine.initialize()

            self._ready = True
            logger.info("Orchestrator engine initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize orchestrator engine", error=str(e))
            self._ready = False

    def is_ready(self) -> bool:
        """Check if orchestrator is ready."""
        return self._ready

    async def create_run(
        self, tenant_id: UUID, agent_spec: AgentSpec, context: Dict[str, Any]
    ) -> AgentRun:
        """Create new agent run."""
        with tracer.start_as_current_span("create_run") as span:
            span.set_attribute("tenant_id", str(tenant_id))
            span.set_attribute("agent_name", agent_spec.name)

            try:
                # Create agent run
                run = AgentRun(
                    tenant_id=tenant_id,
                    workflow="default",
                    agent_spec=agent_spec,
                    context=context,
                )

                # Store run
                self.active_runs[run.run_id] = run

                # Emit event
                await self.event_producer.emit(
                    "agent.run.requested",
                    {
                        "run_id": str(run.run_id),
                        "tenant_id": str(tenant_id),
                        "agent_name": agent_spec.name,
                        "workflow": run.workflow,
                    },
                )

                # Store event
                await self.event_store.store_event(
                    run_id=run.run_id,
                    event_type="run_requested",
                    data={
                        "tenant_id": str(tenant_id),
                        "agent_name": agent_spec.name,
                        "context": context,
                    },
                )

                logger.info(
                    "Agent run created",
                    run_id=str(run.run_id),
                    tenant_id=str(tenant_id),
                    agent_name=agent_spec.name,
                )

                return run

            except Exception as e:
                logger.error(
                    "Failed to create run",
                    tenant_id=str(tenant_id),
                    agent_name=agent_spec.name,
                    error=str(e),
                )
                raise

    async def start_run(self, run_id: UUID, tenant_id: UUID) -> None:
        """Start agent run execution."""
        with tracer.start_as_current_span("start_run") as span:
            span.set_attribute("run_id", str(run_id))
            span.set_attribute("tenant_id", str(tenant_id))

            try:
                # Get run
                run = self.active_runs.get(run_id)
                if not run:
                    raise ValueError(f"Run {run_id} not found")

                if run.tenant_id != tenant_id:
                    raise ValueError("Run does not belong to tenant")

                # Update status
                run.status = "running"

                # Emit event
                await self.event_producer.emit(
                    "agent.run.started",
                    {"run_id": str(run_id), "tenant_id": str(tenant_id)},
                )

                # Store event
                await self.event_store.store_event(
                    run_id=run_id, event_type="run_started", data={}
                )

                # Start workflow execution
                await self._execute_workflow(run)

            except Exception as e:
                logger.error(
                    "Failed to start run",
                    run_id=str(run_id),
                    tenant_id=str(tenant_id),
                    error=str(e),
                )
                raise

    async def get_run(self, run_id: UUID, tenant_id: UUID) -> AgentRun:
        """Get agent run."""
        with tracer.start_as_current_span("get_run") as span:
            span.set_attribute("run_id", str(run_id))
            span.set_attribute("tenant_id", str(tenant_id))

            try:
                # Get run
                run = self.active_runs.get(run_id)
                if not run:
                    raise ValueError(f"Run {run_id} not found")

                if run.tenant_id != tenant_id:
                    raise ValueError("Run does not belong to tenant")

                return run

            except Exception as e:
                logger.error(
                    "Failed to get run",
                    run_id=str(run_id),
                    tenant_id=str(tenant_id),
                    error=str(e),
                )
                raise

    async def cancel_run(self, run_id: UUID, tenant_id: UUID) -> None:
        """Cancel agent run."""
        with tracer.start_as_current_span("cancel_run") as span:
            span.set_attribute("run_id", str(run_id))
            span.set_attribute("tenant_id", str(tenant_id))

            try:
                # Get run
                run = self.active_runs.get(run_id)
                if not run:
                    raise ValueError(f"Run {run_id} not found")

                if run.tenant_id != tenant_id:
                    raise ValueError("Run does not belong to tenant")

                # Update status
                run.status = "cancelled"

                # Emit event
                await self.event_producer.emit(
                    "agent.run.cancelled",
                    {"run_id": str(run_id), "tenant_id": str(tenant_id)},
                )

                # Store event
                await self.event_store.store_event(
                    run_id=run_id, event_type="run_cancelled", data={}
                )

                logger.info(
                    "Agent run cancelled", run_id=str(run_id), tenant_id=str(tenant_id)
                )

            except Exception as e:
                logger.error(
                    "Failed to cancel run",
                    run_id=str(run_id),
                    tenant_id=str(tenant_id),
                    error=str(e),
                )
                raise

    async def _execute_workflow(self, run: AgentRun) -> None:
        """Execute workflow for agent run."""
        with tracer.start_as_current_span("execute_workflow") as span:
            span.set_attribute("run_id", str(run.run_id))
            span.set_attribute("workflow", run.workflow)

            try:
                # Get workflow
                workflow = await self.workflow_engine.get_workflow(run.workflow)

                # Execute workflow
                result = await workflow.execute(run)

                # Update run status
                if result.success:
                    run.status = "completed"
                    run.artifacts = result.artifacts
                    run.tokens_in = result.tokens_in
                    run.tokens_out = result.tokens_out
                    run.cost_usd = result.cost_usd
                else:
                    run.status = "failed"
                    run.error = result.error

                run.finished_at = time.time()

                # Emit event
                event_type = (
                    "agent.run.completed" if result.success else "agent.run.failed"
                )
                await self.event_producer.emit(
                    event_type,
                    {
                        "run_id": str(run.run_id),
                        "tenant_id": str(run.tenant_id),
                        "success": result.success,
                        "tokens_in": result.tokens_in,
                        "tokens_out": result.tokens_out,
                        "cost_usd": result.cost_usd,
                    },
                )

                # Store event
                await self.event_store.store_event(
                    run_id=run.run_id,
                    event_type=event_type,
                    data={
                        "success": result.success,
                        "tokens_in": result.tokens_in,
                        "tokens_out": result.tokens_out,
                        "cost_usd": result.cost_usd,
                        "artifacts": result.artifacts,
                        "error": result.error,
                    },
                )

                logger.info(
                    "Workflow execution completed",
                    run_id=str(run.run_id),
                    success=result.success,
                    tokens_in=result.tokens_in,
                    cost_usd=result.cost_usd,
                )

            except Exception as e:
                logger.error(
                    "Workflow execution failed", run_id=str(run.run_id), error=str(e)
                )

                # Update run status
                run.status = "failed"
                run.error = str(e)
                run.finished_at = time.time()

                # Emit event
                await self.event_producer.emit(
                    "agent.run.failed",
                    {
                        "run_id": str(run.run_id),
                        "tenant_id": str(run.tenant_id),
                        "error": str(e),
                    },
                )

                # Store event
                await self.event_store.store_event(
                    run_id=run.run_id, event_type="run_failed", data={"error": str(e)}
                )

    async def get_run_events(
        self, run_id: UUID, tenant_id: UUID
    ) -> List[Dict[str, Any]]:
        """Get events for agent run."""
        with tracer.start_as_current_span("get_run_events") as span:
            span.set_attribute("run_id", str(run_id))
            span.set_attribute("tenant_id", str(tenant_id))

            try:
                # Get run
                run = self.active_runs.get(run_id)
                if not run:
                    raise ValueError(f"Run {run_id} not found")

                if run.tenant_id != tenant_id:
                    raise ValueError("Run does not belong to tenant")

                # Get events from event store
                events = await self.event_store.get_events(run_id)

                return events

            except Exception as e:
                logger.error(
                    "Failed to get run events",
                    run_id=str(run_id),
                    tenant_id=str(tenant_id),
                    error=str(e),
                )
                raise

    async def replay_run(self, run_id: UUID, tenant_id: UUID) -> AgentRun:
        """Replay agent run from events."""
        with tracer.start_as_current_span("replay_run") as span:
            span.set_attribute("run_id", str(run_id))
            span.set_attribute("tenant_id", str(tenant_id))

            try:
                # Get events
                events = await self.get_run_events(run_id, tenant_id)

                # Replay events to reconstruct run state
                run = await self.state_machine.replay_events(events)

                logger.info(
                    "Run replayed successfully",
                    run_id=str(run_id),
                    tenant_id=str(tenant_id),
                )

                return run

            except Exception as e:
                logger.error(
                    "Failed to replay run",
                    run_id=str(run_id),
                    tenant_id=str(tenant_id),
                    error=str(e),
                )
                raise
