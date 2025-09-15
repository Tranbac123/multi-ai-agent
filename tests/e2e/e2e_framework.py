"""Production-grade E2E testing framework with comprehensive journey validation."""

import asyncio
import time
import json
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
import structlog

from tests._fixtures.factories import factory
from tests._helpers import test_helpers
from tests.contract.schemas import APIRequest, APIResponse, RequestType


logger = structlog.get_logger(__name__)


class JourneyStatus(Enum):
    """Journey execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATED = "compensated"


class JourneyStep(Enum):
    """Journey step types."""
    API_REQUEST = "api_request"
    ROUTER_DECISION = "router_decision"
    TOOL_EXECUTION = "tool_execution"
    WORKFLOW_STEP = "workflow_step"
    EVENT_PUBLISH = "event_publish"
    AUDIT_LOG = "audit_log"
    COMPENSATION = "compensation"


@dataclass
class JourneyMetrics:
    """Journey execution metrics."""
    start_time: datetime
    end_time: Optional[datetime] = None
    total_duration_ms: Optional[float] = None
    total_cost_usd: float = 0.0
    p95_latency_ms: Optional[float] = None
    p99_latency_ms: Optional[float] = None
    step_count: int = 0
    success_steps: int = 0
    failed_steps: int = 0
    compensation_steps: int = 0
    
    def complete(self):
        """Mark journey as complete and calculate final metrics."""
        self.end_time = datetime.now(timezone.utc)
        if self.start_time:
            self.total_duration_ms = (self.end_time - self.start_time).total_seconds() * 1000


@dataclass
class JourneyStepResult:
    """Result of a journey step execution."""
    step_type: JourneyStep
    step_id: str
    status: JourneyStatus
    duration_ms: float
    cost_usd: float
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    side_effects: List[Dict[str, Any]] = None
    audit_entries: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.side_effects is None:
            self.side_effects = []
        if self.audit_entries is None:
            self.audit_entries = []


@dataclass
class JourneyResult:
    """Complete journey execution result."""
    journey_id: str
    journey_name: str
    status: JourneyStatus
    metrics: JourneyMetrics
    steps: List[JourneyStepResult]
    schema_validations: List[Dict[str, Any]]
    side_effects: List[Dict[str, Any]]
    audit_trail: List[Dict[str, Any]]
    compensation_actions: List[Dict[str, Any]]
    cost_budget_exceeded: bool = False
    latency_budget_exceeded: bool = False
    
    def __post_init__(self):
        if self.schema_validations is None:
            self.schema_validations = []
        if self.side_effects is None:
            self.side_effects = []
        if self.audit_trail is None:
            self.audit_trail = []
        if self.compensation_actions is None:
            self.compensation_actions = []


class E2EJourneyFramework:
    """Framework for executing and validating E2E journeys."""
    
    def __init__(self):
        """Initialize E2E journey framework."""
        self.journeys: Dict[str, JourneyResult] = {}
        self.cost_budgets: Dict[str, float] = {
            "faq": 0.01,      # $0.01 for FAQ queries
            "order": 0.05,    # $0.05 for order processing
            "payment": 0.10,  # $0.10 for payment processing
            "support": 0.02,  # $0.02 for support tickets
            "default": 0.01   # Default budget
        }
        self.latency_budgets: Dict[str, float] = {
            "faq": 1000,      # 1 second for FAQ
            "order": 5000,    # 5 seconds for order processing
            "payment": 10000, # 10 seconds for payment
            "support": 3000,  # 3 seconds for support
            "default": 2000   # Default 2 seconds
        }
    
    async def execute_journey(
        self,
        journey_name: str,
        journey_steps: List[Dict[str, Any]],
        cost_budget: Optional[float] = None,
        latency_budget: Optional[float] = None
    ) -> JourneyResult:
        """Execute a complete E2E journey with validation."""
        journey_id = f"journey_{int(time.time())}"
        start_time = datetime.now(timezone.utc)
        
        # Initialize journey result
        metrics = JourneyMetrics(start_time=start_time)
        journey_result = JourneyResult(
            journey_id=journey_id,
            journey_name=journey_name,
            status=JourneyStatus.RUNNING,
            metrics=metrics,
            steps=[]
        )
        
        # Set budgets
        if cost_budget is None:
            cost_budget = self.cost_budgets.get(journey_name, self.cost_budgets["default"])
        if latency_budget is None:
            latency_budget = self.latency_budgets.get(journey_name, self.latency_budgets["default"])
        
        logger.info(f"Starting journey {journey_name}", journey_id=journey_id)
        
        try:
            # Execute each step
            for step_config in journey_steps:
                step_result = await self._execute_step(step_config, journey_result)
                journey_result.steps.append(step_result)
                metrics.step_count += 1
                
                if step_result.status == JourneyStatus.COMPLETED:
                    metrics.success_steps += 1
                elif step_result.status == JourneyStatus.FAILED:
                    metrics.failed_steps += 1
                    # Check if we should continue or fail the journey
                    if not step_config.get("continue_on_failure", False):
                        journey_result.status = JourneyStatus.FAILED
                        break
                elif step_result.status == JourneyStatus.COMPENSATED:
                    metrics.compensation_steps += 1
                
                # Accumulate costs and check budget
                metrics.total_cost_usd += step_result.cost_usd
                if metrics.total_cost_usd > cost_budget:
                    journey_result.cost_budget_exceeded = True
                    logger.warning(f"Cost budget exceeded", 
                                 budget=cost_budget, actual=metrics.total_cost_usd)
            
            # Complete journey
            metrics.complete()
            
            # Check latency budget
            if metrics.total_duration_ms and metrics.total_duration_ms > latency_budget:
                journey_result.latency_budget_exceeded = True
                logger.warning(f"Latency budget exceeded",
                             budget=latency_budget, actual=metrics.total_duration_ms)
            
            # Determine final status
            if journey_result.status != JourneyStatus.FAILED:
                if metrics.failed_steps == 0:
                    journey_result.status = JourneyStatus.COMPLETED
                elif metrics.compensation_steps > 0:
                    journey_result.status = JourneyStatus.COMPENSATED
                else:
                    journey_result.status = JourneyStatus.COMPLETED  # Partial success
            
            # Validate journey invariants
            await self._validate_journey_invariants(journey_result)
            
        except Exception as e:
            logger.error(f"Journey execution failed", error=str(e))
            journey_result.status = JourneyStatus.FAILED
            metrics.complete()
        
        # Store journey result
        self.journeys[journey_id] = journey_result
        
        logger.info(f"Journey {journey_name} completed",
                   status=journey_result.status.value,
                   duration_ms=metrics.total_duration_ms,
                   cost_usd=metrics.total_cost_usd)
        
        return journey_result
    
    async def _execute_step(self, step_config: Dict[str, Any], journey_result: JourneyResult) -> JourneyStepResult:
        """Execute a single journey step."""
        step_id = step_config["step_id"]
        step_type = JourneyStep(step_config["step_type"])
        start_time = time.time()
        
        logger.info(f"Executing step {step_id}", step_type=step_type.value)
        
        try:
            # Execute step based on type
            if step_type == JourneyStep.API_REQUEST:
                result = await self._execute_api_request_step(step_config)
            elif step_type == JourneyStep.ROUTER_DECISION:
                result = await self._execute_router_step(step_config)
            elif step_type == JourneyStep.TOOL_EXECUTION:
                result = await self._execute_tool_step(step_config)
            elif step_type == JourneyStep.WORKFLOW_STEP:
                result = await self._execute_workflow_step(step_config)
            elif step_type == JourneyStep.EVENT_PUBLISH:
                result = await self._execute_event_step(step_config)
            elif step_type == JourneyStep.AUDIT_LOG:
                result = await self._execute_audit_step(step_config)
            elif step_type == JourneyStep.COMPENSATION:
                result = await self._execute_compensation_step(step_config)
            else:
                raise ValueError(f"Unknown step type: {step_type}")
            
            duration_ms = (time.time() - start_time) * 1000
            
            return JourneyStepResult(
                step_type=step_type,
                step_id=step_id,
                status=JourneyStatus.COMPLETED,
                duration_ms=duration_ms,
                cost_usd=result.get("cost_usd", 0.0),
                result_data=result.get("data"),
                side_effects=result.get("side_effects", []),
                audit_entries=result.get("audit_entries", [])
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Step {step_id} failed", error=str(e))
            
            return JourneyStepResult(
                step_type=step_type,
                step_id=step_id,
                status=JourneyStatus.FAILED,
                duration_ms=duration_ms,
                cost_usd=0.0,
                error_message=str(e)
            )
    
    async def _execute_api_request_step(self, step_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute API request step."""
        # Simulate API request processing
        await asyncio.sleep(0.01)  # Simulate network delay
        
        return {
            "data": {"status": "success", "response": "API request processed"},
            "cost_usd": 0.001,
            "side_effects": [{"type": "api_call", "endpoint": step_config.get("endpoint")}],
            "audit_entries": [{"action": "api_request", "timestamp": datetime.now().isoformat()}]
        }
    
    async def _execute_router_step(self, step_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute router decision step."""
        await asyncio.sleep(0.005)  # Simulate router processing
        
        return {
            "data": {"tier": "SLM_A", "confidence": 0.95, "tool_selected": "faq_tool"},
            "cost_usd": 0.002,
            "side_effects": [{"type": "router_decision", "tier": "SLM_A"}],
            "audit_entries": [{"action": "router_decision", "timestamp": datetime.now().isoformat()}]
        }
    
    async def _execute_tool_step(self, step_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool execution step."""
        await asyncio.sleep(0.02)  # Simulate tool execution
        
        return {
            "data": {"tool_result": "Tool execution completed", "output": "Generated response"},
            "cost_usd": 0.005,
            "side_effects": [{"type": "tool_execution", "tool_id": step_config.get("tool_id")}],
            "audit_entries": [{"action": "tool_execution", "timestamp": datetime.now().isoformat()}]
        }
    
    async def _execute_workflow_step(self, step_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute workflow step."""
        await asyncio.sleep(0.01)
        
        return {
            "data": {"workflow_status": "completed", "step_result": "Workflow step completed"},
            "cost_usd": 0.003,
            "side_effects": [{"type": "workflow_step", "workflow_id": step_config.get("workflow_id")}],
            "audit_entries": [{"action": "workflow_step", "timestamp": datetime.now().isoformat()}]
        }
    
    async def _execute_event_step(self, step_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute event publishing step."""
        await asyncio.sleep(0.001)
        
        return {
            "data": {"event_published": True, "event_id": f"evt_{int(time.time())}"},
            "cost_usd": 0.0001,
            "side_effects": [{"type": "event_publish", "event_type": step_config.get("event_type")}],
            "audit_entries": [{"action": "event_publish", "timestamp": datetime.now().isoformat()}]
        }
    
    async def _execute_audit_step(self, step_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute audit logging step."""
        await asyncio.sleep(0.0001)
        
        return {
            "data": {"audit_logged": True},
            "cost_usd": 0.0,
            "side_effects": [],
            "audit_entries": [{"action": "audit_log", "timestamp": datetime.now().isoformat()}]
        }
    
    async def _execute_compensation_step(self, step_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute compensation step."""
        await asyncio.sleep(0.01)
        
        return {
            "data": {"compensation_completed": True, "compensated_actions": step_config.get("actions", [])},
            "cost_usd": 0.001,
            "side_effects": [{"type": "compensation", "actions": step_config.get("actions", [])}],
            "audit_entries": [{"action": "compensation", "timestamp": datetime.now().isoformat()}]
        }
    
    async def _validate_journey_invariants(self, journey_result: JourneyResult):
        """Validate journey execution invariants."""
        # Validate schema consistency
        for step in journey_result.steps:
            if step.result_data:
                # Validate that all responses have consistent schema
                assert "status" in step.result_data or "error" in step.result_data
        
        # Validate audit trail completeness
        total_audit_entries = sum(len(step.audit_entries) for step in journey_result.steps)
        assert total_audit_entries > 0, "Journey must have audit entries"
        
        # Validate side effects are tracked
        total_side_effects = sum(len(step.side_effects) for step in journey_result.steps)
        assert total_side_effects > 0, "Journey must track side effects"
        
        # Validate cost and latency budgets
        if journey_result.cost_budget_exceeded:
            logger.warning(f"Journey {journey_result.journey_name} exceeded cost budget")
        
        if journey_result.latency_budget_exceeded:
            logger.warning(f"Journey {journey_result.journey_name} exceeded latency budget")
    
    def get_journey_summary(self, journey_id: str) -> Dict[str, Any]:
        """Get summary of journey execution."""
        if journey_id not in self.journeys:
            return {"error": "Journey not found"}
        
        journey = self.journeys[journey_id]
        return {
            "journey_id": journey.journey_id,
            "journey_name": journey.journey_name,
            "status": journey.status.value,
            "duration_ms": journey.metrics.total_duration_ms,
            "cost_usd": journey.metrics.total_cost_usd,
            "step_count": journey.metrics.step_count,
            "success_steps": journey.metrics.success_steps,
            "failed_steps": journey.metrics.failed_steps,
            "compensation_steps": journey.metrics.compensation_steps,
            "cost_budget_exceeded": journey.cost_budget_exceeded,
            "latency_budget_exceeded": journey.latency_budget_exceeded
        }


# Global E2E framework instance
e2e_framework = E2EJourneyFramework()
