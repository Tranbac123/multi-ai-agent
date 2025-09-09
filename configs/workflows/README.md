# Agent Workflows Configuration

This directory contains YAML-based workflow configurations for the multi-tenant AIaaS platform. These workflows define the behavior and flow of AI agents in various customer service scenarios.

## Overview

The workflow system uses a graph-based approach where:

- **Nodes** represent individual processing steps (agents, tools, conditions, etc.)
- **Edges** define the flow between nodes with optional conditions
- **YAML files** provide a declarative way to define complex workflows

## Workflow Files

### Main Workflows

1. **`customer_support_workflow.yaml`** - Main orchestrator workflow that routes customer inquiries to appropriate sub-workflows
2. **`faq_handling.yaml`** - Handles FAQ requests using knowledge base search and LLM enhancement
3. **`order_management.yaml`** - Manages order-related inquiries and operations
4. **`create_order.yaml`** - Handles new order creation with product search, inventory check, and payment
5. **`track_order.yaml`** - Provides order tracking and status information
6. **`lead_capture.yaml`** - Collects and processes customer leads for sales
7. **`complaint_handling.yaml`** - Manages customer complaints with escalation logic
8. **`technical_support.yaml`** - Handles technical issues and troubleshooting

### Registry and Utilities

9. **`workflow_registry.yaml`** - Central registry defining all workflows, categories, and metadata
10. **`workflow_loader.py`** - Python utility for loading, validating, and managing workflows

## Workflow Structure

Each workflow YAML file follows this structure:

```yaml
name: "workflow_name"
version: "1.0.0"
description: "Workflow description"
category: "category_name"
priority: "high|medium|low"

metadata:
  author: "Team Name"
  created_at: "2024-01-15"
  tags: ["tag1", "tag2"]

config:
  timeout_seconds: 300
  max_retries: 3
  circuit_breaker:
    failure_threshold: 5
    recovery_timeout: 60

nodes:
  - name: "node_name"
    type: "start|agent|tool|condition|sub_workflow|end"
    config:
      # Node-specific configuration
      next_node: "next_node_name"

edges:
  - from: "node1"
    to: "node2"
    condition: "context.condition == true"

error_handling:
  - error_type: "timeout"
    action: "retry|fallback|escalate"
    max_retries: 2
    fallback_node: "fallback_node"

monitoring:
  metrics:
    - name: "metric_name"
      type: "counter|histogram|gauge"
      labels: ["label1", "label2"]
```

## Node Types

### 1. Start Node

- **Type**: `start`
- **Purpose**: Entry point of the workflow
- **Config**: Basic configuration, `next_node` to specify first processing node

### 2. Agent Node

- **Type**: `agent`
- **Purpose**: LLM-powered processing
- **Config**:
  - `agent_type`: Type of agent (classifier, responder, etc.)
  - `model`: LLM model to use
  - `temperature`: Response creativity (0.0-1.0)
  - `max_tokens`: Maximum response length
  - `prompt_template`: Template for LLM prompts

### 3. Tool Node

- **Type**: `tool`
- **Purpose**: External system integration
- **Config**:
  - `tool_name`: Name of the tool to execute
  - `parameters`: Tool-specific parameters

### 4. Condition Node

- **Type**: `condition`
- **Purpose**: Decision making based on context
- **Config**:
  - `conditions`: List of condition mappings
  - Each condition has a `condition` expression and `next_node`

### 5. Sub-workflow Node

- **Type**: `sub_workflow`
- **Purpose**: Execute another workflow
- **Config**:
  - `workflow_name`: Name of the sub-workflow
  - `timeout_seconds`: Timeout for sub-workflow execution

### 6. End Node

- **Type**: `end`
- **Purpose**: Workflow termination
- **Config**: Basic configuration

## Workflow Categories

- **`customer_service`** - Customer service related workflows
- **`e_commerce`** - E-commerce and order management workflows
- **`sales`** - Sales and lead generation workflows
- **`technical_support`** - Technical support workflows
- **`system`** - System and infrastructure workflows

## Workflow Priorities

- **`critical`** - Must always be available
- **`high`** - High priority workflows
- **`medium`** - Medium priority workflows
- **`low`** - Low priority workflows

## Error Handling

Each workflow can define error handling strategies:

- **`retry`** - Retry the operation with exponential backoff
- **`fallback`** - Execute a fallback node
- **`escalate`** - Escalate to human agents
- **`log_and_continue`** - Log error and continue execution

## Monitoring and Metrics

Workflows support comprehensive monitoring:

- **Execution metrics** - Duration, success rate, error count
- **Custom metrics** - Workflow-specific measurements
- **Alerts** - Automated alerting based on thresholds

## Usage

### Loading Workflows

```python
from configs.workflows.workflow_loader import WorkflowLoader

# Initialize loader
loader = WorkflowLoader("configs/workflows")
loader.initialize()

# Get a workflow
workflow = loader.get_workflow("customer_support_workflow")

# List all workflows
workflows = loader.list_workflows()

# Validate workflow
validation = loader.validate_workflow("customer_support_workflow")
```

### Workflow Execution

Workflows are executed by the LangGraph orchestrator:

```python
from apps.orchestrator.core.workflow import WorkflowEngine

# Initialize workflow engine
engine = WorkflowEngine()
engine.initialize()

# Execute workflow
workflow = await engine.get_workflow("customer_support_workflow")
result = await workflow.execute(agent_run)
```

## Best Practices

### 1. Workflow Design

- Keep workflows focused on specific business processes
- Use clear, descriptive node names
- Minimize complexity by breaking large workflows into sub-workflows
- Always include error handling and fallback paths

### 2. Node Configuration

- Use appropriate node types for each step
- Configure timeouts and retry policies
- Include comprehensive logging and monitoring
- Validate all inputs and outputs

### 3. Error Handling

- Define specific error handling for each workflow
- Use appropriate fallback strategies
- Log errors for debugging and monitoring
- Escalate critical errors to human agents

### 4. Monitoring

- Define relevant metrics for each workflow
- Set appropriate alert thresholds
- Monitor workflow performance and success rates
- Track resource usage and costs

## Development Workflow

1. **Design** - Plan the workflow structure and node flow
2. **Create** - Write the YAML configuration file
3. **Validate** - Use the workflow loader to validate the configuration
4. **Test** - Test the workflow with sample data
5. **Deploy** - Deploy to the orchestrator service
6. **Monitor** - Monitor execution and performance

## Troubleshooting

### Common Issues

1. **Workflow not found** - Check workflow name and registry
2. **Node validation errors** - Verify node configuration and dependencies
3. **Edge validation errors** - Check node names and conditions
4. **Timeout errors** - Adjust timeout settings or optimize workflow
5. **Tool errors** - Verify tool configuration and availability

### Debugging

1. **Enable debug logging** - Set log level to DEBUG
2. **Check workflow validation** - Use `validate_workflow()` method
3. **Monitor execution** - Use workflow monitoring metrics
4. **Review error logs** - Check application logs for detailed error information

## Contributing

When adding new workflows:

1. Follow the established naming conventions
2. Include comprehensive documentation
3. Add appropriate error handling
4. Define monitoring metrics
5. Test thoroughly before deployment
6. Update the workflow registry

## Security Considerations

- Validate all workflow inputs
- Sanitize outputs before sending to customers
- Use appropriate authentication and authorization
- Log security-relevant events
- Follow principle of least privilege for tool access
