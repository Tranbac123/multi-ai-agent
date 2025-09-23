#!/usr/bin/env python3
"""
Workflow Loader for YAML-based agent workflows.

This module provides functionality to load, validate, and manage
YAML workflow configurations for the multi-tenant AIaaS platform.
"""

import yaml
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
import structlog
from opentelemetry import trace

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


class WorkflowStatus(Enum):
    """Workflow status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"
    DEVELOPMENT = "development"


class WorkflowPriority(Enum):
    """Workflow priority enumeration."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class WorkflowNode:
    """Represents a workflow node."""
    name: str
    node_type: str
    config: Dict[str, Any]
    next_node: Optional[str] = None


@dataclass
class WorkflowEdge:
    """Represents a workflow edge."""
    from_node: str
    to_node: str
    condition: Optional[str] = None


@dataclass
class WorkflowConfig:
    """Represents a workflow configuration."""
    name: str
    version: str
    description: str
    category: str
    priority: WorkflowPriority
    status: WorkflowStatus
    metadata: Dict[str, Any]
    config: Dict[str, Any]
    nodes: List[WorkflowNode]
    edges: List[WorkflowEdge]
    error_handling: List[Dict[str, Any]]
    monitoring: Dict[str, Any]


class WorkflowLoader:
    """Loads and manages YAML workflow configurations."""
    
    def __init__(self, workflows_dir: str = "configs/workflows"):
        """Initialize workflow loader.
        
        Args:
            workflows_dir: Directory containing workflow YAML files
        """
        self.workflows_dir = Path(workflows_dir)
        self.workflows: Dict[str, WorkflowConfig] = {}
        self.registry: Optional[Dict[str, Any]] = None
        self._ready = False
    
    def initialize(self) -> None:
        """Initialize the workflow loader."""
        try:
            # Load workflow registry
            self._load_registry()
            
            # Load all workflows
            self._load_workflows()
            
            self._ready = True
            logger.info("Workflow loader initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize workflow loader", error=str(e))
            self._ready = False
            raise
    
    def is_ready(self) -> bool:
        """Check if workflow loader is ready."""
        return self._ready
    
    def _load_registry(self) -> None:
        """Load workflow registry."""
        registry_file = self.workflows_dir / "workflow_registry.yaml"
        
        if not registry_file.exists():
            logger.warning("Workflow registry file not found", file=str(registry_file))
            return
        
        try:
            with open(registry_file, 'r') as f:
                self.registry = yaml.safe_load(f)
            
            logger.info("Workflow registry loaded successfully")
            
        except Exception as e:
            logger.error("Failed to load workflow registry", error=str(e))
            raise
    
    def _load_workflows(self) -> None:
        """Load all workflow configurations."""
        if not self.workflows_dir.exists():
            logger.error("Workflows directory not found", dir=str(self.workflows_dir))
            return
        
        # Load workflow files
        for yaml_file in self.workflows_dir.glob("*.yaml"):
            if yaml_file.name == "workflow_registry.yaml":
                continue
            
            try:
                workflow = self._load_workflow_file(yaml_file)
                if workflow:
                    self.workflows[workflow.name] = workflow
                    logger.info("Workflow loaded", name=workflow.name)
                    
            except Exception as e:
                logger.error(
                    "Failed to load workflow file",
                    file=str(yaml_file),
                    error=str(e)
                )
    
    def _load_workflow_file(self, file_path: Path) -> Optional[WorkflowConfig]:
        """Load a single workflow file.
        
        Args:
            file_path: Path to the workflow YAML file
            
        Returns:
            WorkflowConfig object or None if loading fails
        """
        try:
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
            
            # Validate required fields
            required_fields = ["name", "version", "description", "category", "priority"]
            for field in required_fields:
                if field not in data:
                    logger.error(f"Missing required field: {field}", file=str(file_path))
                    return None
            
            # Parse nodes
            nodes = []
            for node_data in data.get("nodes", []):
                node = WorkflowNode(
                    name=node_data["name"],
                    node_type=node_data["type"],
                    config=node_data.get("config", {}),
                    next_node=node_data.get("config", {}).get("next_node")
                )
                nodes.append(node)
            
            # Parse edges
            edges = []
            for edge_data in data.get("edges", []):
                edge = WorkflowEdge(
                    from_node=edge_data["from"],
                    to_node=edge_data["to"],
                    condition=edge_data.get("condition")
                )
                edges.append(edge)
            
            # Create workflow config
            workflow = WorkflowConfig(
                name=data["name"],
                version=data["version"],
                description=data["description"],
                category=data["category"],
                priority=WorkflowPriority(data["priority"]),
                status=WorkflowStatus(data.get("status", "active")),
                metadata=data.get("metadata", {}),
                config=data.get("config", {}),
                nodes=nodes,
                edges=edges,
                error_handling=data.get("error_handling", []),
                monitoring=data.get("monitoring", {})
            )
            
            return workflow
            
        except Exception as e:
            logger.error("Failed to load workflow file", file=str(file_path), error=str(e))
            return None
    
    def get_workflow(self, name: str) -> Optional[WorkflowConfig]:
        """Get workflow by name.
        
        Args:
            name: Workflow name
            
        Returns:
            WorkflowConfig object or None if not found
        """
        return self.workflows.get(name)
    
    def list_workflows(self) -> List[str]:
        """List all available workflow names.
        
        Returns:
            List of workflow names
        """
        return list(self.workflows.keys())
    
    def list_workflows_by_category(self, category: str) -> List[str]:
        """List workflows by category.
        
        Args:
            category: Workflow category
            
        Returns:
            List of workflow names in the category
        """
        return [
            name for name, workflow in self.workflows.items()
            if workflow.category == category
        ]
    
    def list_workflows_by_status(self, status: WorkflowStatus) -> List[str]:
        """List workflows by status.
        
        Args:
            status: Workflow status
            
        Returns:
            List of workflow names with the status
        """
        return [
            name for name, workflow in self.workflows.items()
            if workflow.status == status
        ]
    
    def get_workflow_dependencies(self, name: str) -> List[str]:
        """Get workflow dependencies.
        
        Args:
            name: Workflow name
            
        Returns:
            List of dependency workflow names
        """
        if not self.registry:
            return []
        
        workflow_info = None
        for workflow in self.registry.get("workflows", []):
            if workflow["name"] == name:
                workflow_info = workflow
                break
        
        if not workflow_info:
            return []
        
        return workflow_info.get("dependencies", [])
    
    def validate_workflow(self, name: str) -> Dict[str, Any]:
        """Validate workflow configuration.
        
        Args:
            name: Workflow name
            
        Returns:
            Validation result dictionary
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        workflow = self.get_workflow(name)
        if not workflow:
            result["valid"] = False
            result["errors"].append(f"Workflow '{name}' not found")
            return result
        
        # Validate nodes
        node_names = {node.name for node in workflow.nodes}
        
        # Check for duplicate node names
        if len(node_names) != len(workflow.nodes):
            result["valid"] = False
            result["errors"].append("Duplicate node names found")
        
        # Check for start node
        start_nodes = [node for node in workflow.nodes if node.node_type == "start"]
        if len(start_nodes) == 0:
            result["valid"] = False
            result["errors"].append("No start node found")
        elif len(start_nodes) > 1:
            result["warnings"].append("Multiple start nodes found")
        
        # Check for end node
        end_nodes = [node for node in workflow.nodes if node.node_type == "end"]
        if len(end_nodes) == 0:
            result["warnings"].append("No end node found")
        
        # Validate edges
        for edge in workflow.edges:
            if edge.from_node not in node_names:
                result["valid"] = False
                result["errors"].append(f"Edge references unknown node: {edge.from_node}")
            
            if edge.to_node not in node_names:
                result["valid"] = False
                result["errors"].append(f"Edge references unknown node: {edge.to_node}")
        
        return result
    
    def export_workflow(self, name: str, format: str = "yaml") -> str:
        """Export workflow configuration.
        
        Args:
            name: Workflow name
            format: Export format (yaml or json)
            
        Returns:
            Exported workflow configuration
        """
        workflow = self.get_workflow(name)
        if not workflow:
            raise ValueError(f"Workflow '{name}' not found")
        
        # Convert workflow to dictionary
        workflow_dict = {
            "name": workflow.name,
            "version": workflow.version,
            "description": workflow.description,
            "category": workflow.category,
            "priority": workflow.priority.value,
            "status": workflow.status.value,
            "metadata": workflow.metadata,
            "config": workflow.config,
            "nodes": [
                {
                    "name": node.name,
                    "type": node.node_type,
                    "config": node.config
                }
                for node in workflow.nodes
            ],
            "edges": [
                {
                    "from": edge.from_node,
                    "to": edge.to_node,
                    "condition": edge.condition
                }
                for edge in workflow.edges
            ],
            "error_handling": workflow.error_handling,
            "monitoring": workflow.monitoring
        }
        
        if format.lower() == "yaml":
            return yaml.dump(workflow_dict, default_flow_style=False)
        elif format.lower() == "json":
            return json.dumps(workflow_dict, indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def get_workflow_statistics(self) -> Dict[str, Any]:
        """Get workflow statistics.
        
        Returns:
            Statistics dictionary
        """
        stats = {
            "total_workflows": len(self.workflows),
            "by_category": {},
            "by_status": {},
            "by_priority": {},
            "total_nodes": 0,
            "total_edges": 0
        }
        
        for workflow in self.workflows.values():
            # Count by category
            category = workflow.category
            stats["by_category"][category] = stats["by_category"].get(category, 0) + 1
            
            # Count by status
            status = workflow.status.value
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
            
            # Count by priority
            priority = workflow.priority.value
            stats["by_priority"][priority] = stats["by_priority"].get(priority, 0) + 1
            
            # Count nodes and edges
            stats["total_nodes"] += len(workflow.nodes)
            stats["total_edges"] += len(workflow.edges)
        
        return stats


# Example usage
if __name__ == "__main__":
    # Initialize workflow loader
    loader = WorkflowLoader()
    loader.initialize()
    
    # List all workflows
    print("Available workflows:")
    for workflow_name in loader.list_workflows():
        print(f"  - {workflow_name}")
    
    # Get workflow statistics
    stats = loader.get_workflow_statistics()
    print(f"\nWorkflow statistics:")
    print(f"  Total workflows: {stats['total_workflows']}")
    print(f"  Total nodes: {stats['total_nodes']}")
    print(f"  Total edges: {stats['total_edges']}")
    
    # Validate a workflow
    if loader.list_workflows():
        workflow_name = loader.list_workflows()[0]
        validation = loader.validate_workflow(workflow_name)
        print(f"\nValidation for '{workflow_name}':")
        print(f"  Valid: {validation['valid']}")
        if validation['errors']:
            print(f"  Errors: {validation['errors']}")
        if validation['warnings']:
            print(f"  Warnings: {validation['warnings']}")
