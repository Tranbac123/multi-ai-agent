"""
Enhanced Orchestrator with Loop Safety

Integrates loop safety mechanisms into the main orchestrator workflow.
"""

import asyncio
import uuid
import time
from typing import Dict, List, Optional, Any, Callable, Awaitable
import structlog
from opentelemetry import trace

from .loop_safety import (
    LoopSafetyManager, LoopBudget, LoopStatus, 
    ProgressMetrics, get_safety_manager, get_degradation_manager
)
from .workflow_engine import WorkflowEngine
from .tool_registry import ToolRegistry

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


class EnhancedOrchestrator:
    """Enhanced orchestrator with comprehensive loop safety."""
    
    def __init__(self, 
                 workflow_engine: WorkflowEngine,
                 tool_registry: ToolRegistry,
                 budget: Optional[LoopBudget] = None):
        self.workflow_engine = workflow_engine
        self.tool_registry = tool_registry
        self.safety_manager = get_safety_manager()
        self.degradation_manager = get_degradation_manager()
        
        # Override budget if provided
        if budget:
            self.safety_manager.budget = budget
        
        logger.info("Enhanced Orchestrator initialized", 
                   max_steps=self.safety_manager.budget.max_steps,
                   max_wall_ms=self.safety_manager.budget.max_wall_ms)
    
    async def execute_workflow(self, 
                             tenant_id: str,
                             workflow_id: str,
                             input_data: Dict[str, Any],
                             context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute workflow with comprehensive loop safety."""
        run_id = str(uuid.uuid4())
        
        with tracer.start_as_current_span("orchestrator.execute_workflow") as span:
            span.set_attribute("run_id", run_id)
            span.set_attribute("tenant_id", tenant_id)
            span.set_attribute("workflow_id", workflow_id)
            
            # Start loop tracking
            loop_state = self.safety_manager.start_loop(run_id, tenant_id, workflow_id)
            
            try:
                result = await self._execute_with_safety_checks(
                    run_id, tenant_id, workflow_id, input_data, context, span
                )
                
                self.safety_manager.complete_loop(run_id, success=True)
                span.set_attribute("status", "completed")
                
                return result
                
            except Exception as e:
                logger.error("Workflow execution failed", 
                           run_id=run_id, 
                           error=str(e), 
                           exc_info=True)
                
                self.safety_manager.complete_loop(run_id, success=False)
                span.set_attribute("status", "failed")
                span.set_attribute("error", str(e))
                
                raise
    
    async def _execute_with_safety_checks(self,
                                        run_id: str,
                                        tenant_id: str,
                                        workflow_id: str,
                                        input_data: Dict[str, Any],
                                        context: Optional[Dict[str, Any]],
                                        span) -> Dict[str, Any]:
        """Execute workflow with continuous safety monitoring."""
        
        # Initialize workflow state
        workflow_state = {
            "run_id": run_id,
            "tenant_id": tenant_id,
            "workflow_id": workflow_id,
            "input_data": input_data,
            "context": context or {},
            "current_step": 0,
            "plan_hash": "",
            "goals_left": 0,
            "evidence": [],
            "tools_used": set(),
            "entities": set(),
            "last_progress_time": time.time()
        }
        
        # Main execution loop
        while True:
            # Check loop safety
            should_continue, cut_reason = self.safety_manager.check_loop_safety(run_id)
            if not should_continue:
                logger.warning("Loop cut due to safety check", 
                             run_id=run_id, 
                             reason=cut_reason)
                break
            
            # Apply degradation strategies
            degradation_strategies = self.degradation_manager.get_degradation_strategy(run_id)
            if degradation_strategies:
                logger.info("Applying degradation strategies", 
                          run_id=run_id, 
                          strategies=degradation_strategies)
                workflow_state["degradation_strategies"] = degradation_strategies
            
            # Increment step counter
            self.safety_manager.increment_step(run_id)
            workflow_state["current_step"] += 1
            
            # Execute workflow step
            step_result = await self._execute_workflow_step(
                workflow_state, span
            )
            
            if step_result.get("completed", False):
                break
            
            # Record progress
            self._record_workflow_progress(run_id, workflow_state)
            
            # Small delay to prevent tight loops
            await asyncio.sleep(0.01)
        
        # Return final result
        return {
            "run_id": run_id,
            "status": "completed",
            "final_state": workflow_state,
            "steps_taken": workflow_state["current_step"],
            "total_cost_usd": self.safety_manager.get_loop_state(run_id).total_cost_usd if self.safety_manager.get_loop_state(run_id) else 0.0,
            "tokens_used": self.safety_manager.get_loop_state(run_id).tokens_used if self.safety_manager.get_loop_state(run_id) else 0
        }
    
    async def _execute_workflow_step(self, 
                                   workflow_state: Dict[str, Any], 
                                   span) -> Dict[str, Any]:
        """Execute a single workflow step."""
        
        run_id = workflow_state["run_id"]
        
        with tracer.start_as_current_span("orchestrator.workflow_step") as step_span:
            step_span.set_attribute("run_id", run_id)
            step_span.set_attribute("step", workflow_state["current_step"])
            
            try:
                # Get current workflow plan
                plan = await self.workflow_engine.get_current_plan(
                    workflow_state["workflow_id"], 
                    workflow_state["context"]
                )
                
                workflow_state["plan_hash"] = plan.get("hash", "")
                workflow_state["goals_left"] = len(plan.get("remaining_goals", []))
                
                # Check if workflow is complete
                if workflow_state["goals_left"] == 0:
                    return {"completed": True}
                
                # Execute next action in plan
                action = plan.get("next_action")
                if not action:
                    return {"completed": True}
                
                # Execute action with tool
                tool_name = action.get("tool")
                tool_args = action.get("args", {})
                
                if tool_name:
                    # Get tool from registry
                    tool = self.tool_registry.get_tool(tool_name)
                    if not tool:
                        logger.error("Tool not found", tool_name=tool_name)
                        return {"completed": True, "error": f"Tool {tool_name} not found"}
                    
                    # Apply degradation strategies
                    degradation_strategies = workflow_state.get("degradation_strategies", [])
                    if "shrink_context" in degradation_strategies:
                        tool_args = self._shrink_context(tool_args)
                    
                    # Execute tool
                    tool_result = await self._execute_tool_with_safety(
                        tool, tool_args, workflow_state, step_span
                    )
                    
                    # Update workflow state
                    workflow_state["tools_used"].add(tool_name)
                    workflow_state["evidence"].extend(tool_result.get("evidence", []))
                    workflow_state["entities"].update(tool_result.get("entities", []))
                    
                    # Update cost and tokens
                    self.safety_manager.add_cost(run_id, tool_result.get("cost_usd", 0.0))
                    self.safety_manager.add_tokens(run_id, tool_result.get("tokens_used", 0))
                
                return {"completed": False}
                
            except Exception as e:
                logger.error("Workflow step failed", 
                           run_id=run_id, 
                           step=workflow_state["current_step"],
                           error=str(e))
                
                # Increment repair attempts
                self.safety_manager.increment_repair_attempt(run_id)
                
                # Check if we should abort due to too many repair attempts
                should_continue, _ = self.safety_manager.check_loop_safety(run_id)
                if not should_continue:
                    raise
                
                # Try to recover
                return {"completed": False, "recovered": True}
    
    async def _execute_tool_with_safety(self,
                                      tool: Any,
                                      tool_args: Dict[str, Any],
                                      workflow_state: Dict[str, Any],
                                      span) -> Dict[str, Any]:
        """Execute tool with safety monitoring."""
        
        run_id = workflow_state["run_id"]
        start_time = time.time()
        
        with tracer.start_as_current_span("orchestrator.execute_tool") as tool_span:
            tool_span.set_attribute("run_id", run_id)
            tool_span.set_attribute("tool_name", tool.__class__.__name__)
            
            try:
                # Execute tool
                result = await tool.execute(**tool_args)
                
                # Calculate execution metrics
                execution_time_ms = (time.time() - start_time) * 1000
                tool_span.set_attribute("execution_time_ms", execution_time_ms)
                
                return result
                
            except Exception as e:
                logger.error("Tool execution failed", 
                           run_id=run_id,
                           tool=tool.__class__.__name__,
                           error=str(e))
                
                tool_span.set_attribute("error", str(e))
                raise
    
    def _record_workflow_progress(self, run_id: str, workflow_state: Dict[str, Any]):
        """Record workflow progress for safety monitoring."""
        
        # Calculate progress metrics
        plan_hash = workflow_state["plan_hash"]
        goals_left = workflow_state["goals_left"]
        evidence_size = len(workflow_state["evidence"])
        distinct_tools_used = len(workflow_state["tools_used"])
        new_entities = len(workflow_state["entities"])
        
        # Record progress
        self.safety_manager.record_progress(
            run_id=run_id,
            plan_hash=plan_hash,
            goals_left=goals_left,
            evidence_size=evidence_size,
            distinct_tools_used=distinct_tools_used,
            new_entities=new_entities
        )
    
    def _shrink_context(self, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Shrink context as degradation strategy."""
        # Simple context shrinking - limit text length
        for key, value in tool_args.items():
            if isinstance(value, str) and len(value) > 1000:
                tool_args[key] = value[:1000] + "..."
        
        return tool_args
    
    def get_safety_metrics(self) -> Dict[str, Any]:
        """Get safety manager metrics."""
        return self.safety_manager.get_metrics()
    
    def get_active_loops(self) -> Dict[str, Any]:
        """Get information about active loops."""
        active_info = {}
        for run_id, loop_state in self.safety_manager.active_loops.items():
            active_info[run_id] = {
                "tenant_id": loop_state.tenant_id,
                "workflow_id": loop_state.workflow_id,
                "status": loop_state.status.value,
                "steps_taken": loop_state.steps_taken,
                "elapsed_ms": (time.time() - loop_state.start_time) * 1000,
                "total_cost_usd": loop_state.total_cost_usd,
                "tokens_used": loop_state.tokens_used
            }
        
        return active_info
