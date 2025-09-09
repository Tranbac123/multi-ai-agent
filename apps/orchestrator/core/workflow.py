"""Workflow engine for LangGraph-based workflows."""

import asyncio
from typing import Dict, Any, Optional, List
from uuid import UUID
import structlog
from opentelemetry import trace

from libs.contracts.agent import AgentRun, AgentStep
from libs.contracts.tool import ToolCall, ToolResult
from libs.contracts.message import MessageSpec, MessageRole
from libs.contracts.error import ErrorSpec, ErrorCode
from .langgraph_workflow import LangGraphWorkflow
from .workflow_registry import WorkflowRegistry

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


class WorkflowEngine:
    """Workflow engine for managing and executing workflows."""
    
    def __init__(self):
        self.registry = WorkflowRegistry()
        self.active_workflows: Dict[UUID, LangGraphWorkflow] = {}
        self._ready = False
    
    def initialize(self):
        """Initialize workflow engine."""
        try:
            self.registry.initialize()
            self._ready = True
            logger.info("Workflow engine initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize workflow engine", error=str(e))
            self._ready = False
    
    def is_ready(self) -> bool:
        """Check if workflow engine is ready."""
        return self._ready
    
    async def get_workflow(self, workflow_name: str) -> LangGraphWorkflow:
        """Get workflow by name."""
        try:
            # Get workflow from registry
            workflow_config = await self.registry.get_workflow(workflow_name)
            
            # Create workflow instance
            workflow = LangGraphWorkflow(
                name=workflow_name,
                config=workflow_config
            )
            
            # Initialize workflow
            await workflow.initialize()
            
            return workflow
            
        except Exception as e:
            logger.error(
                "Failed to get workflow",
                workflow_name=workflow_name,
                error=str(e)
            )
            raise
    
    async def register_workflow(self, name: str, config: Dict[str, Any]) -> None:
        """Register new workflow."""
        try:
            await self.registry.register_workflow(name, config)
            
            logger.info(
                "Workflow registered",
                workflow_name=name
            )
            
        except Exception as e:
            logger.error(
                "Failed to register workflow",
                workflow_name=name,
                error=str(e)
            )
            raise
    
    async def list_workflows(self) -> List[str]:
        """List available workflows."""
        try:
            workflows = await self.registry.list_workflows()
            return workflows
            
        except Exception as e:
            logger.error("Failed to list workflows", error=str(e))
            raise


class WorkflowResult:
    """Result of workflow execution."""
    
    def __init__(
        self,
        success: bool,
        artifacts: Dict[str, Any] = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float = 0.0,
        error: Optional[str] = None
    ):
        self.success = success
        self.artifacts = artifacts or {}
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.cost_usd = cost_usd
        self.error = error


class LangGraphWorkflow:
    """LangGraph-based workflow implementation."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.graph = None
        self.nodes = {}
        self.edges = []
        self._ready = False
    
    async def initialize(self):
        """Initialize workflow."""
        try:
            # Build workflow graph from config
            await self._build_graph()
            
            self._ready = True
            logger.info(
                "Workflow initialized",
                workflow_name=self.name
            )
            
        except Exception as e:
            logger.error(
                "Failed to initialize workflow",
                workflow_name=self.name,
                error=str(e)
            )
            raise
    
    async def _build_graph(self):
        """Build workflow graph from configuration."""
        # Parse nodes from config
        for node_config in self.config.get("nodes", []):
            node = WorkflowNode(
                name=node_config["name"],
                node_type=node_config["type"],
                config=node_config.get("config", {})
            )
            self.nodes[node.name] = node
        
        # Parse edges from config
        for edge_config in self.config.get("edges", []):
            edge = WorkflowEdge(
                from_node=edge_config["from"],
                to_node=edge_config["to"],
                condition=edge_config.get("condition")
            )
            self.edges.append(edge)
    
    async def execute(self, run: AgentRun) -> WorkflowResult:
        """Execute workflow for agent run."""
        with tracer.start_as_current_span("execute_workflow") as span:
            span.set_attribute("workflow_name", self.name)
            span.set_attribute("run_id", str(run.run_id))
            
            try:
                if not self._ready:
                    raise RuntimeError("Workflow not initialized")
                
                # Initialize execution context
                context = WorkflowContext(
                    run=run,
                    current_node=None,
                    state={},
                    artifacts={},
                    tokens_in=0,
                    tokens_out=0,
                    cost_usd=0.0
                )
                
                # Execute workflow
                result = await self._execute_graph(context)
                
                return WorkflowResult(
                    success=result.success,
                    artifacts=result.artifacts,
                    tokens_in=result.tokens_in,
                    tokens_out=result.tokens_out,
                    cost_usd=result.cost_usd,
                    error=result.error
                )
                
            except Exception as e:
                logger.error(
                    "Workflow execution failed",
                    workflow_name=self.name,
                    run_id=str(run.run_id),
                    error=str(e)
                )
                
                return WorkflowResult(
                    success=False,
                    error=str(e)
                )
    
    async def _execute_graph(self, context: 'WorkflowContext') -> WorkflowResult:
        """Execute workflow graph."""
        try:
            # Find start node
            start_node = self._find_start_node()
            if not start_node:
                raise ValueError("No start node found")
            
            # Execute nodes in sequence
            current_node = start_node
            while current_node:
                # Execute current node
                result = await current_node.execute(context)
                
                # Update context
                context.state.update(result.state)
                context.artifacts.update(result.artifacts)
                context.tokens_in += result.tokens_in
                context.tokens_out += result.tokens_out
                context.cost_usd += result.cost_usd
                
                # Check for errors
                if result.error:
                    return WorkflowResult(
                        success=False,
                        artifacts=context.artifacts,
                        tokens_in=context.tokens_in,
                        tokens_out=context.tokens_out,
                        cost_usd=context.cost_usd,
                        error=result.error
                    )
                
                # Find next node
                next_node = self._find_next_node(current_node, context)
                current_node = next_node
            
            return WorkflowResult(
                success=True,
                artifacts=context.artifacts,
                tokens_in=context.tokens_in,
                tokens_out=context.tokens_out,
                cost_usd=context.cost_usd
            )
            
        except Exception as e:
            logger.error(
                "Graph execution failed",
                workflow_name=self.name,
                error=str(e)
            )
            
            return WorkflowResult(
                success=False,
                error=str(e)
            )
    
    def _find_start_node(self) -> Optional['WorkflowNode']:
        """Find start node in workflow."""
        for node in self.nodes.values():
            if node.node_type == "start":
                return node
        return None
    
    def _find_next_node(self, current_node: 'WorkflowNode', context: 'WorkflowContext') -> Optional['WorkflowNode']:
        """Find next node to execute."""
        for edge in self.edges:
            if edge.from_node == current_node.name:
                # Check condition if present
                if edge.condition and not self._evaluate_condition(edge.condition, context):
                    continue
                
                # Return next node
                return self.nodes.get(edge.to_node)
        
        return None
    
    def _evaluate_condition(self, condition: str, context: 'WorkflowContext') -> bool:
        """Evaluate edge condition."""
        # Simple condition evaluation
        # In production, this would use a proper expression evaluator
        try:
            return eval(condition, {"context": context, "state": context.state})
        except:
            return False


class WorkflowContext:
    """Context for workflow execution."""
    
    def __init__(
        self,
        run: AgentRun,
        current_node: Optional[str],
        state: Dict[str, Any],
        artifacts: Dict[str, Any],
        tokens_in: int,
        tokens_out: int,
        cost_usd: float
    ):
        self.run = run
        self.current_node = current_node
        self.state = state
        self.artifacts = artifacts
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.cost_usd = cost_usd


class WorkflowNode:
    """Individual workflow node."""
    
    def __init__(self, name: str, node_type: str, config: Dict[str, Any]):
        self.name = name
        self.node_type = node_type
        self.config = config
    
    async def execute(self, context: WorkflowContext) -> 'NodeResult':
        """Execute node."""
        try:
            if self.node_type == "start":
                return await self._execute_start(context)
            elif self.node_type == "agent":
                return await self._execute_agent(context)
            elif self.node_type == "tool":
                return await self._execute_tool(context)
            elif self.node_type == "condition":
                return await self._execute_condition(context)
            elif self.node_type == "end":
                return await self._execute_end(context)
            else:
                raise ValueError(f"Unknown node type: {self.node_type}")
                
        except Exception as e:
            logger.error(
                "Node execution failed",
                node_name=self.name,
                node_type=self.node_type,
                error=str(e)
            )
            
            return NodeResult(
                success=False,
                error=str(e)
            )
    
    async def _execute_start(self, context: WorkflowContext) -> 'NodeResult':
        """Execute start node."""
        return NodeResult(success=True)
    
    async def _execute_agent(self, context: WorkflowContext) -> 'NodeResult':
        """Execute agent node."""
        # In production, this would call the actual agent
        # For now, return mock result
        return NodeResult(
            success=True,
            state={"agent_result": "mock_result"},
            tokens_in=100,
            tokens_out=50,
            cost_usd=0.01
        )
    
    async def _execute_tool(self, context: WorkflowContext) -> 'NodeResult':
        """Execute tool node."""
        # In production, this would call the actual tool
        # For now, return mock result
        return NodeResult(
            success=True,
            artifacts={"tool_result": "mock_tool_result"},
            tokens_in=50,
            tokens_out=25,
            cost_usd=0.005
        )
    
    async def _execute_condition(self, context: WorkflowContext) -> 'NodeResult':
        """Execute condition node."""
        # In production, this would evaluate the condition
        # For now, return mock result
        return NodeResult(
            success=True,
            state={"condition_result": True}
        )
    
    async def _execute_end(self, context: WorkflowContext) -> 'NodeResult':
        """Execute end node."""
        return NodeResult(success=True)


class NodeResult:
    """Result of node execution."""
    
    def __init__(
        self,
        success: bool,
        state: Dict[str, Any] = None,
        artifacts: Dict[str, Any] = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float = 0.0,
        error: Optional[str] = None
    ):
        self.success = success
        self.state = state or {}
        self.artifacts = artifacts or {}
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.cost_usd = cost_usd
        self.error = error


class WorkflowEdge:
    """Edge between workflow nodes."""
    
    def __init__(self, from_node: str, to_node: str, condition: Optional[str] = None):
        self.from_node = from_node
        self.to_node = to_node
        self.condition = condition
