#!/usr/bin/env python3
"""
Demo script for YAML-based agent workflows.

This script demonstrates how to load, validate, and work with
YAML workflow configurations in the multi-tenant AIaaS platform.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from configs.workflows.workflow_loader import WorkflowLoader, WorkflowStatus, WorkflowPriority


async def demo_workflow_loading():
    """Demonstrate workflow loading and validation."""
    print("🚀 YAML Agent Workflows Demo")
    print("=" * 50)
    
    # Initialize workflow loader
    print("\n1. Initializing Workflow Loader...")
    loader = WorkflowLoader("configs/workflows")
    loader.initialize()
    
    if not loader.is_ready():
        print("❌ Failed to initialize workflow loader")
        return
    
    print("✅ Workflow loader initialized successfully")
    
    # List all workflows
    print("\n2. Available Workflows:")
    workflows = loader.list_workflows()
    for i, workflow_name in enumerate(workflows, 1):
        print(f"   {i}. {workflow_name}")
    
    # Get workflow statistics
    print("\n3. Workflow Statistics:")
    stats = loader.get_workflow_statistics()
    print(f"   Total workflows: {stats['total_workflows']}")
    print(f"   Total nodes: {stats['total_nodes']}")
    print(f"   Total edges: {stats['total_edges']}")
    
    print("\n   By Category:")
    for category, count in stats['by_category'].items():
        print(f"     - {category}: {count}")
    
    print("\n   By Status:")
    for status, count in stats['by_status'].items():
        print(f"     - {status}: {count}")
    
    print("\n   By Priority:")
    for priority, count in stats['by_priority'].items():
        print(f"     - {priority}: {count}")
    
    # Validate workflows
    print("\n4. Workflow Validation:")
    for workflow_name in workflows:
        validation = loader.validate_workflow(workflow_name)
        status = "✅" if validation['valid'] else "❌"
        print(f"   {status} {workflow_name}")
        
        if validation['errors']:
            for error in validation['errors']:
                print(f"      Error: {error}")
        
        if validation['warnings']:
            for warning in validation['warnings']:
                print(f"      Warning: {warning}")
    
    # Demonstrate workflow details
    print("\n5. Workflow Details:")
    for workflow_name in workflows[:3]:  # Show first 3 workflows
        workflow = loader.get_workflow(workflow_name)
        if workflow:
            print(f"\n   📋 {workflow.name}")
            print(f"      Description: {workflow.description}")
            print(f"      Category: {workflow.category}")
            print(f"      Priority: {workflow.priority.value}")
            print(f"      Status: {workflow.status.value}")
            print(f"      Nodes: {len(workflow.nodes)}")
            print(f"      Edges: {len(workflow.edges)}")
            
            # Show node types
            node_types = {}
            for node in workflow.nodes:
                node_type = node.node_type
                node_types[node_type] = node_types.get(node_type, 0) + 1
            
            print(f"      Node Types: {dict(node_types)}")
    
    # Demonstrate workflow categories
    print("\n6. Workflows by Category:")
    categories = ["customer_service", "e_commerce", "sales", "technical_support", "system"]
    for category in categories:
        category_workflows = loader.list_workflows_by_category(category)
        if category_workflows:
            print(f"\n   📁 {category.title()}:")
            for workflow_name in category_workflows:
                workflow = loader.get_workflow(workflow_name)
                if workflow:
                    print(f"      - {workflow.name} ({workflow.priority.value})")
    
    # Demonstrate workflow dependencies
    print("\n7. Workflow Dependencies:")
    for workflow_name in workflows:
        dependencies = loader.get_workflow_dependencies(workflow_name)
        if dependencies:
            print(f"   {workflow_name} depends on: {', '.join(dependencies)}")
    
    # Export workflow example
    print("\n8. Workflow Export Example:")
    if workflows:
        workflow_name = workflows[0]
        try:
            yaml_export = loader.export_workflow(workflow_name, "yaml")
            print(f"   Exported {workflow_name} (first 500 chars):")
            print("   " + "=" * 50)
            print("   " + yaml_export[:500] + "...")
        except Exception as e:
            print(f"   Error exporting {workflow_name}: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 YAML Workflows Demo Complete!")
    print("\nKey Features Demonstrated:")
    print("✅ Workflow loading and validation")
    print("✅ Statistics and categorization")
    print("✅ Error handling and warnings")
    print("✅ Workflow dependencies")
    print("✅ Export functionality")
    print("✅ Comprehensive monitoring setup")


async def demo_workflow_execution():
    """Demonstrate workflow execution concepts."""
    print("\n🔄 Workflow Execution Concepts")
    print("=" * 50)
    
    # Load workflow
    loader = WorkflowLoader("configs/workflows")
    loader.initialize()
    
    if not loader.is_ready():
        print("❌ Workflow loader not ready")
        return
    
    # Get a sample workflow
    workflows = loader.list_workflows()
    if not workflows:
        print("❌ No workflows available")
        return
    
    workflow_name = workflows[0]
    workflow = loader.get_workflow(workflow_name)
    
    if not workflow:
        print(f"❌ Workflow {workflow_name} not found")
        return
    
    print(f"\n📋 Executing Workflow: {workflow.name}")
    print(f"   Description: {workflow.description}")
    print(f"   Nodes: {len(workflow.nodes)}")
    print(f"   Edges: {len(workflow.edges)}")
    
    # Simulate workflow execution
    print("\n🔄 Simulated Execution Flow:")
    
    # Find start node
    start_nodes = [node for node in workflow.nodes if node.node_type == "start"]
    if not start_nodes:
        print("❌ No start node found")
        return
    
    current_node = start_nodes[0]
    execution_path = [current_node.name]
    
    print(f"   1. Start: {current_node.name}")
    
    # Simulate execution through nodes
    step = 2
    max_steps = 10  # Prevent infinite loops
    
    while current_node and step <= max_steps:
        # Find next node based on edges
        next_node_name = None
        for edge in workflow.edges:
            if edge.from_node == current_node.name:
                # In a real implementation, we would evaluate the condition
                next_node_name = edge.to_node
                break
        
        if not next_node_name:
            break
        
        # Find next node
        next_node = None
        for node in workflow.nodes:
            if node.name == next_node_name:
                next_node = node
                break
        
        if not next_node:
            break
        
        current_node = next_node
        execution_path.append(current_node.name)
        
        print(f"   {step}. {current_node.node_type.title()}: {current_node.name}")
        step += 1
        
        # Stop at end node
        if current_node.node_type == "end":
            break
    
    print(f"\n📊 Execution Summary:")
    print(f"   Path: {' → '.join(execution_path)}")
    print(f"   Steps: {len(execution_path)}")
    
    # Show workflow structure
    print(f"\n🏗️  Workflow Structure:")
    print(f"   Nodes by Type:")
    node_types = {}
    for node in workflow.nodes:
        node_type = node.node_type
        if node_type not in node_types:
            node_types[node_type] = []
        node_types[node_type].append(node.name)
    
    for node_type, node_names in node_types.items():
        print(f"     {node_type}: {', '.join(node_names)}")
    
    print(f"\n   Edges:")
    for edge in workflow.edges:
        condition = f" (if {edge.condition})" if edge.condition else ""
        print(f"     {edge.from_node} → {edge.to_node}{condition}")


async def main():
    """Main demo function."""
    try:
        await demo_workflow_loading()
        await demo_workflow_execution()
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
