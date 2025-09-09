"""
YAML Workflow Engine for LangGraph Orchestrator.

This module integrates YAML workflow configurations with the LangGraph orchestrator,
providing a declarative way to define and execute agent workflows.
"""

import asyncio
from typing import Dict, Any, Optional, List
from uuid import UUID
import structlog
from opentelemetry import trace

from libs.contracts.agent import AgentRun, AgentStep
from libs.contracts.tool import ToolCall, ToolResult
from libs.contracts.message import MessageSpec, MessageRole
from libs.contracts.error import ErrorSpec, ErrorCode
from .workflow import WorkflowEngine, WorkflowResult, WorkflowContext
from .langgraph_workflow import LangGraphWorkflow
from .workflow_registry import WorkflowRegistry

# Import the YAML workflow loader
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from configs.workflows.workflow_loader import WorkflowLoader, WorkflowConfig, WorkflowNode, WorkflowEdge

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


class YAMLWorkflowEngine(WorkflowEngine):
    """YAML-based workflow engine for LangGraph orchestrator."""
    
    def __init__(self, workflows_dir: str = "configs/workflows"):
        """Initialize YAML workflow engine.
        
        Args:
            workflows_dir: Directory containing workflow YAML files
        """
        super().__init__()
        self.yaml_loader = WorkflowLoader(workflows_dir)
        self.yaml_workflows: Dict[str, WorkflowConfig] = {}
        self._ready = False
    
    def initialize(self):
        """Initialize YAML workflow engine."""
        try:
            # Initialize base workflow engine
            super().initialize()
            
            # Initialize YAML loader
            self.yaml_loader.initialize()
            
            # Load YAML workflows
            self._load_yaml_workflows()
            
            self._ready = True
            logger.info("YAML workflow engine initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize YAML workflow engine", error=str(e))
            self._ready = False
    
    def is_ready(self) -> bool:
        """Check if YAML workflow engine is ready."""
        return self._ready and self.yaml_loader.is_ready()
    
    def _load_yaml_workflows(self):
        """Load YAML workflows into the engine."""
        try:
            # Get all YAML workflows
            yaml_workflow_names = self.yaml_loader.list_workflows()
            
            for workflow_name in yaml_workflow_names:
                yaml_workflow = self.yaml_loader.get_workflow(workflow_name)
                if yaml_workflow:
                    self.yaml_workflows[workflow_name] = yaml_workflow
                    
                    # Convert to LangGraph workflow format
                    langgraph_config = self._convert_yaml_to_langgraph(yaml_workflow)
                    
                    # Register with base workflow engine
                    asyncio.create_task(
                        self.register_workflow(workflow_name, langgraph_config)
                    )
            
            logger.info(
                "YAML workflows loaded",
                count=len(self.yaml_workflows)
            )
            
        except Exception as e:
            logger.error("Failed to load YAML workflows", error=str(e))
            raise
    
    def _convert_yaml_to_langgraph(self, yaml_workflow: WorkflowConfig) -> Dict[str, Any]:
        """Convert YAML workflow to LangGraph format.
        
        Args:
            yaml_workflow: YAML workflow configuration
            
        Returns:
            LangGraph workflow configuration
        """
        # Convert nodes
        nodes = []
        for yaml_node in yaml_workflow.nodes:
            node_config = {
                "name": yaml_node.name,
                "type": yaml_node.node_type,
                "config": yaml_node.config
            }
            nodes.append(node_config)
        
        # Convert edges
        edges = []
        for yaml_edge in yaml_workflow.edges:
            edge_config = {
                "from": yaml_edge.from_node,
                "to": yaml_edge.to_node,
                "condition": yaml_edge.condition
            }
            edges.append(edge_config)
        
        # Create LangGraph configuration
        langgraph_config = {
            "name": yaml_workflow.name,
            "version": yaml_workflow.version,
            "description": yaml_workflow.description,
            "category": yaml_workflow.category,
            "priority": yaml_workflow.priority.value,
            "status": yaml_workflow.status.value,
            "metadata": yaml_workflow.metadata,
            "config": yaml_workflow.config,
            "nodes": nodes,
            "edges": edges,
            "error_handling": yaml_workflow.error_handling,
            "monitoring": yaml_workflow.monitoring
        }
        
        return langgraph_config
    
    async def get_yaml_workflow(self, workflow_name: str) -> Optional[WorkflowConfig]:
        """Get YAML workflow by name.
        
        Args:
            workflow_name: Workflow name
            
        Returns:
            YAML workflow configuration or None if not found
        """
        return self.yaml_workflows.get(workflow_name)
    
    async def list_yaml_workflows(self) -> List[str]:
        """List available YAML workflow names.
        
        Returns:
            List of YAML workflow names
        """
        return list(self.yaml_workflows.keys())
    
    async def get_workflow_categories(self) -> Dict[str, List[str]]:
        """Get workflows grouped by category.
        
        Returns:
            Dictionary mapping categories to workflow names
        """
        categories = {}
        for workflow_name, workflow in self.yaml_workflows.items():
            category = workflow.category
            if category not in categories:
                categories[category] = []
            categories[category].append(workflow_name)
        
        return categories
    
    async def validate_yaml_workflow(self, workflow_name: str) -> Dict[str, Any]:
        """Validate YAML workflow configuration.
        
        Args:
            workflow_name: Workflow name
            
        Returns:
            Validation result dictionary
        """
        return self.yaml_loader.validate_workflow(workflow_name)
    
    async def export_yaml_workflow(self, workflow_name: str, format: str = "yaml") -> str:
        """Export YAML workflow configuration.
        
        Args:
            workflow_name: Workflow name
            format: Export format (yaml or json)
            
        Returns:
            Exported workflow configuration
        """
        return self.yaml_loader.export_workflow(workflow_name, format)
    
    async def get_workflow_statistics(self) -> Dict[str, Any]:
        """Get comprehensive workflow statistics.
        
        Returns:
            Statistics dictionary including YAML and LangGraph workflows
        """
        # Get YAML statistics
        yaml_stats = self.yaml_loader.get_workflow_statistics()
        
        # Get LangGraph statistics
        langgraph_workflows = await self.list_workflows()
        
        # Combine statistics
        combined_stats = {
            "yaml_workflows": yaml_stats,
            "langgraph_workflows": {
                "total": len(langgraph_workflows),
                "names": langgraph_workflows
            },
            "total_workflows": yaml_stats["total_workflows"] + len(langgraph_workflows)
        }
        
        return combined_stats
    
    async def execute_yaml_workflow(self, workflow_name: str, run: AgentRun) -> WorkflowResult:
        """Execute YAML workflow.
        
        Args:
            workflow_name: YAML workflow name
            run: Agent run to execute
            
        Returns:
            Workflow execution result
        """
        try:
            # Get YAML workflow
            yaml_workflow = await self.get_yaml_workflow(workflow_name)
            if not yaml_workflow:
                raise ValueError(f"YAML workflow '{workflow_name}' not found")
            
            # Convert to LangGraph workflow
            langgraph_config = self._convert_yaml_to_langgraph(yaml_workflow)
            
            # Create LangGraph workflow instance
            langgraph_workflow = LangGraphWorkflow(
                name=workflow_name,
                config=langgraph_config
            )
            
            # Initialize workflow
            await langgraph_workflow.initialize()
            
            # Execute workflow
            result = await langgraph_workflow.execute(run)
            
            return result
            
        except Exception as e:
            logger.error(
                "YAML workflow execution failed",
                workflow_name=workflow_name,
                run_id=str(run.run_id),
                error=str(e)
            )
            
            return WorkflowResult(
                success=False,
                error=str(e)
            )
    
    async def get_workflow_metrics(self) -> Dict[str, Any]:
        """Get workflow execution metrics.
        
        Returns:
            Metrics dictionary
        """
        metrics = {
            "yaml_workflows": {
                "total": len(self.yaml_workflows),
                "by_category": {},
                "by_priority": {},
                "by_status": {}
            },
            "execution": {
                "active_workflows": len(self.active_workflows),
                "total_executions": 0,  # Would be tracked in production
                "success_rate": 0.0,    # Would be calculated in production
                "average_duration": 0.0  # Would be calculated in production
            }
        }
        
        # Calculate YAML workflow metrics
        for workflow in self.yaml_workflows.values():
            category = workflow.category
            priority = workflow.priority.value
            status = workflow.status.value
            
            # By category
            if category not in metrics["yaml_workflows"]["by_category"]:
                metrics["yaml_workflows"]["by_category"][category] = 0
            metrics["yaml_workflows"]["by_category"][category] += 1
            
            # By priority
            if priority not in metrics["yaml_workflows"]["by_priority"]:
                metrics["yaml_workflows"]["by_priority"][priority] = 0
            metrics["yaml_workflows"]["by_priority"][priority] += 1
            
            # By status
            if status not in metrics["yaml_workflows"]["by_status"]:
                metrics["yaml_workflows"]["by_status"][status] = 0
            metrics["yaml_workflows"]["by_status"][status] += 1
        
        return metrics


# Example usage and testing
async def demo_yaml_workflow_engine():
    """Demonstrate YAML workflow engine functionality."""
    print("🚀 YAML Workflow Engine Demo")
    print("=" * 50)
    
    # Initialize engine
    engine = YAMLWorkflowEngine()
    engine.initialize()
    
    if not engine.is_ready():
        print("❌ YAML workflow engine not ready")
        return
    
    print("✅ YAML workflow engine initialized")
    
    # List workflows
    yaml_workflows = await engine.list_yaml_workflows()
    print(f"\n📋 Available YAML Workflows: {len(yaml_workflows)}")
    for workflow_name in yaml_workflows:
        print(f"   - {workflow_name}")
    
    # Get categories
    categories = await engine.get_workflow_categories()
    print(f"\n📁 Workflow Categories:")
    for category, workflows in categories.items():
        print(f"   {category}: {len(workflows)} workflows")
    
    # Get statistics
    stats = await engine.get_workflow_statistics()
    print(f"\n📊 Statistics:")
    print(f"   Total workflows: {stats['total_workflows']}")
    print(f"   YAML workflows: {stats['yaml_workflows']['total_workflows']}")
    print(f"   LangGraph workflows: {stats['langgraph_workflows']['total']}")
    
    # Get metrics
    metrics = await engine.get_workflow_metrics()
    print(f"\n📈 Metrics:")
    print(f"   Active workflows: {metrics['execution']['active_workflows']}")
    print(f"   By category: {metrics['yaml_workflows']['by_category']}")
    print(f"   By priority: {metrics['yaml_workflows']['by_priority']}")
    
    print("\n🎉 YAML Workflow Engine Demo Complete!")


if __name__ == "__main__":
    asyncio.run(demo_yaml_workflow_engine())
