"""LangGraph-based orchestrator with event sourcing."""

import asyncio
import time
from typing import Dict, Any, Optional, List
from uuid import UUID, uuid4
import structlog
from opentelemetry import trace

from libs.contracts.agent import AgentRun, AgentSpec
from libs.contracts.tool import ToolCall, ToolResult
from libs.contracts.message import MessageSpec, MessageRole
from libs.contracts.error import ErrorSpec, ErrorCode
from libs.clients.event_bus import EventProducer
from src.workflow import WorkflowEngine
from src.saga import SagaManager
from src.event_store import EventStore
from src.state_machine import AgentStateMachine

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
        
        # Loop safety configuration
        self.MAX_STEPS = 100  # Maximum number of steps per run
        self.MAX_WALL_MS = 300000  # 5 minutes maximum wall time
        self.MAX_REPAIR_ATTEMPTS = 3  # Maximum repair attempts per step
        
        # Loop safety tracking
        self.step_counts: Dict[UUID, int] = {}
        self.start_times: Dict[UUID, float] = {}
        self.repair_attempts: Dict[UUID, int] = {}
        self.oscillation_detection: Dict[UUID, List[str]] = {}  # Track state history
        
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

    def progress(self, run_id: UUID) -> Dict[str, Any]:
        """Get progress information for a run."""
        if run_id not in self.active_runs:
            return {"error": "Run not found"}
        
        current_time = time.time()
        start_time = self.start_times.get(run_id, current_time)
        elapsed_ms = (current_time - start_time) * 1000
        
        return {
            "run_id": str(run_id),
            "status": self.active_runs[run_id].status,
            "step_count": self.step_counts.get(run_id, 0),
            "max_steps": self.MAX_STEPS,
            "elapsed_ms": elapsed_ms,
            "max_wall_ms": self.MAX_WALL_MS,
            "repair_attempts": self.repair_attempts.get(run_id, 0),
            "max_repair_attempts": self.MAX_REPAIR_ATTEMPTS,
            "progress_percentage": min(100, (self.step_counts.get(run_id, 0) / self.MAX_STEPS) * 100),
            "time_remaining_ms": max(0, self.MAX_WALL_MS - elapsed_ms),
            "oscillation_detected": self._detect_oscillation(run_id)
        }
    
    def _check_loop_safety(self, run_id: UUID) -> Dict[str, Any]:
        """Check loop safety constraints."""
        current_time = time.time()
        start_time = self.start_times.get(run_id, current_time)
        elapsed_ms = (current_time - start_time) * 1000
        
        safety_status = {
            "step_limit_exceeded": self.step_counts.get(run_id, 0) >= self.MAX_STEPS,
            "wall_time_exceeded": elapsed_ms >= self.MAX_WALL_MS,
            "repair_limit_exceeded": self.repair_attempts.get(run_id, 0) >= self.MAX_REPAIR_ATTEMPTS,
            "oscillation_detected": self._detect_oscillation(run_id)
        }
        
        return safety_status
    
    def _detect_oscillation(self, run_id: UUID) -> bool:
        """Detect oscillation in state transitions."""
        state_history = self.oscillation_detection.get(run_id, [])
        
        if len(state_history) < 6:  # Need at least 6 states to detect oscillation
            return False
        
        # Check for A->B->A->B->A->B pattern (simple oscillation)
        recent_states = state_history[-6:]
        if (recent_states[0] == recent_states[2] == recent_states[4] and
            recent_states[1] == recent_states[3] == recent_states[5] and
            recent_states[0] != recent_states[1]):
            return True
        
        # Check for more complex oscillation patterns
        if len(state_history) >= 10:
            # Look for repeated 3-state cycles
            for i in range(len(state_history) - 9):
                cycle = state_history[i:i+3]
                if (state_history[i+3:i+6] == cycle and 
                    state_history[i+6:i+9] == cycle):
                    return True
        
        return False
    
    def _increment_step(self, run_id: UUID, new_state: str = None):
        """Increment step count and track state for oscillation detection."""
        self.step_counts[run_id] = self.step_counts.get(run_id, 0) + 1
        
        if new_state:
            self.oscillation_detection[run_id].append(new_state)
            # Keep only last 20 states to prevent memory bloat
            if len(self.oscillation_detection[run_id]) > 20:
                self.oscillation_detection[run_id] = self.oscillation_detection[run_id][-20:]
    
    def _increment_repair_attempts(self, run_id: UUID):
        """Increment repair attempt count."""
        self.repair_attempts[run_id] = self.repair_attempts.get(run_id, 0) + 1
    
    def _cleanup_run_tracking(self, run_id: UUID):
        """Clean up tracking data for completed run."""
        self.step_counts.pop(run_id, None)
        self.start_times.pop(run_id, None)
        self.repair_attempts.pop(run_id, None)
        self.oscillation_detection.pop(run_id, None)
    
    async def _execute_with_loop_safety(self, workflow, run: AgentRun):
        """Execute workflow with loop safety checks."""
        while True:
            # Check loop safety constraints
            safety_status = self._check_loop_safety(run.run_id)
            
            if safety_status["step_limit_exceeded"]:
                logger.error("Step limit exceeded", run_id=str(run.run_id))
                run.status = "failed"
                run.error = "Step limit exceeded"
                return type('Result', (), {
                    'success': False,
                    'error': 'Step limit exceeded',
                    'artifacts': {},
                    'tokens_in': 0,
                    'tokens_out': 0,
                    'cost_usd': 0.0
                })()
            
            if safety_status["wall_time_exceeded"]:
                logger.error("Wall time exceeded", run_id=str(run.run_id))
                run.status = "failed"
                run.error = "Wall time exceeded"
                return type('Result', (), {
                    'success': False,
                    'error': 'Wall time exceeded',
                    'artifacts': {},
                    'tokens_in': 0,
                    'tokens_out': 0,
                    'cost_usd': 0.0
                })()
            
            if safety_status["oscillation_detected"]:
                logger.error("Oscillation detected", run_id=str(run.run_id))
                run.status = "failed"
                run.error = "Oscillation detected"
                return type('Result', (), {
                    'success': False,
                    'error': 'Oscillation detected',
                    'artifacts': {},
                    'tokens_in': 0,
                    'tokens_out': 0,
                    'cost_usd': 0.0
                })()
            
            # Increment step count
            self._increment_step(run.run_id, run.status)
            
            try:
                # Execute workflow step
                result = await workflow.execute(run)
                
                if result.success:
                    # Clean up tracking on success
                    self._cleanup_run_tracking(run.run_id)
                    return result
                else:
                    # Check repair attempts for failed steps
                    if self.repair_attempts.get(run.run_id, 0) >= self.MAX_REPAIR_ATTEMPTS:
                        logger.error("Max repair attempts exceeded", run_id=str(run.run_id))
                        run.status = "failed"
                        run.error = "Max repair attempts exceeded"
                        return type('Result', (), {
                            'success': False,
                            'error': 'Max repair attempts exceeded',
                            'artifacts': {},
                            'tokens_in': 0,
                            'tokens_out': 0,
                            'cost_usd': 0.0
                        })()
                    
                    # Increment repair attempts and retry
                    self._increment_repair_attempts(run.run_id)
                    logger.warning("Step failed, retrying", 
                                 run_id=str(run.run_id),
                                 attempt=self.repair_attempts.get(run.run_id, 0))
                    
            except Exception as e:
                logger.error("Workflow execution error", 
                           run_id=str(run.run_id),
                           error=str(e))
                
                if self.repair_attempts.get(run.run_id, 0) >= self.MAX_REPAIR_ATTEMPTS:
                    run.status = "failed"
                    run.error = f"Workflow execution failed: {str(e)}"
                    return type('Result', (), {
                        'success': False,
                        'error': f'Workflow execution failed: {str(e)}',
                        'artifacts': {},
                        'tokens_in': 0,
                        'tokens_out': 0,
                        'cost_usd': 0.0
                    })()
                
                self._increment_repair_attempts(run.run_id)

    async def _execute_workflow(self, run: AgentRun) -> None:
        """Execute workflow for agent run with loop safety."""
        with tracer.start_as_current_span("execute_workflow") as span:
            span.set_attribute("run_id", str(run.run_id))
            span.set_attribute("workflow", run.workflow)

            # Initialize loop safety tracking
            self.step_counts[run.run_id] = 0
            self.start_times[run.run_id] = time.time()
            self.repair_attempts[run.run_id] = 0
            self.oscillation_detection[run.run_id] = []

            try:
                # Get workflow
                workflow = await self.workflow_engine.get_workflow(run.workflow)

                # Execute workflow with loop safety
                result = await self._execute_with_loop_safety(workflow, run)

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
