# Workflows Index Documentation

## 📋 **Overview**

This document provides a comprehensive index of all YAML-based workflows in the Multi-AI-Agent platform, including their purposes, configurations, and execution patterns.

## 🗂️ **Workflow Categories**

### **Customer Support Workflows**

#### **FAQ Workflow**

- **File**: `configs/workflows/faq_workflow.yaml`
- **Purpose**: Handle frequently asked questions with knowledge base search
- **Tier**: SLM_A (fast responses for common queries)
- **Steps**: Query → Router → Knowledge Search → Response Generation → Validation
- **Budget**: 100ms max, $0.001 cost limit

#### **Support Ticket Workflow**

- **File**: `configs/workflows/support_ticket_workflow.yaml`
- **Purpose**: Process and route support tickets to appropriate agents
- **Tier**: SLM_B (balanced accuracy and speed)
- **Steps**: Ticket Analysis → Classification → Routing → Agent Assignment → Follow-up
- **Budget**: 500ms max, $0.005 cost limit

#### **Escalation Workflow**

- **File**: `configs/workflows/escalation_workflow.yaml`
- **Purpose**: Escalate complex issues to human agents
- **Tier**: LLM (highest accuracy for complex cases)
- **Steps**: Issue Analysis → Complexity Assessment → Escalation Decision → Human Handoff
- **Budget**: 2000ms max, $0.02 cost limit

### **E-commerce Workflows**

#### **Order Processing Workflow**

- **File**: `configs/workflows/order_processing_workflow.yaml`
- **Purpose**: Complete order processing with payment and fulfillment
- **Tier**: SLM_A → SLM_B → LLM (escalating complexity)
- **Steps**: Order Validation → Payment Processing → Inventory Check → Fulfillment → Confirmation
- **Budget**: 5000ms max, $0.05 cost limit
- **Compensation**: Payment refund, inventory restoration

#### **Order Tracking Workflow**

- **File**: `configs/workflows/order_tracking_workflow.yaml`
- **Purpose**: Provide order status and tracking information
- **Tier**: SLM_A (fast lookups)
- **Steps**: Order Lookup → Status Check → Carrier Integration → Status Update → Notification
- **Budget**: 200ms max, $0.002 cost limit

#### **Return Processing Workflow**

- **File**: `configs/workflows/return_processing_workflow.yaml`
- **Purpose**: Handle product returns and refunds
- **Tier**: SLM_B (balanced processing)
- **Steps**: Return Request → Validation → Approval → Processing → Refund → Notification
- **Budget**: 3000ms max, $0.03 cost limit
- **Compensation**: Refund reversal, inventory restoration

### **Lead Management Workflows**

#### **Lead Capture Workflow**

- **File**: `configs/workflows/lead_capture_workflow.yaml`
- **Purpose**: Capture and qualify sales leads
- **Tier**: SLM_A (fast lead processing)
- **Steps**: Lead Form → Data Validation → Qualification → CRM Integration → Follow-up
- **Budget**: 300ms max, $0.003 cost limit

#### **Lead Qualification Workflow**

- **File**: `configs/workflows/lead_qualification_workflow.yaml`
- **Purpose**: Score and qualify leads based on criteria
- **Tier**: SLM_B (balanced scoring)
- **Steps**: Lead Analysis → Scoring → Qualification → Assignment → CRM Update
- **Budget**: 1000ms max, $0.01 cost limit

#### **Lead Nurturing Workflow**

- **File**: `configs/workflows/lead_nurturing_workflow.yaml`
- **Purpose**: Automated lead nurturing campaigns
- **Tier**: SLM_A (automated responses)
- **Steps**: Lead Status Check → Content Selection → Email Generation → Delivery → Tracking
- **Budget**: 800ms max, $0.008 cost limit

### **Payment Processing Workflows**

#### **Payment Authorization Workflow**

- **File**: `configs/workflows/payment_authorization_workflow.yaml`
- **Purpose**: Authorize and process payments
- **Tier**: SLM_A (fast processing)
- **Steps**: Payment Validation → Fraud Check → Authorization → Processing → Confirmation
- **Budget**: 1500ms max, $0.015 cost limit
- **Compensation**: Authorization reversal

#### **Payment Refund Workflow**

- **File**: `configs/workflows/payment_refund_workflow.yaml`
- **Purpose**: Process payment refunds
- **Tier**: SLM_B (secure processing)
- **Steps**: Refund Request → Validation → Processing → Notification → Reconciliation
- **Budget**: 2000ms max, $0.02 cost limit

### **Multi-Channel Workflows**

#### **Web Chat Workflow**

- **File**: `configs/workflows/web_chat_workflow.yaml`
- **Purpose**: Handle web-based chat interactions
- **Tier**: SLM_A (real-time responses)
- **Steps**: Message Processing → Context Analysis → Response Generation → Delivery
- **Budget**: 200ms max, $0.002 cost limit

#### **Social Media Workflow**

- **File**: `configs/workflows/social_media_workflow.yaml`
- **Purpose**: Process social media interactions (Facebook, Twitter, etc.)
- **Tier**: SLM_B (content moderation)
- **Steps**: Message Reception → Content Analysis → Response Generation → Publishing
- **Budget**: 1000ms max, $0.01 cost limit

#### **Email Workflow**

- **File**: `configs/workflows/email_workflow.yaml`
- **Purpose**: Process incoming and outgoing emails
- **Tier**: SLM_B (email processing)
- **Steps**: Email Parsing → Content Analysis → Response Generation → Delivery
- **Budget**: 1500ms max, $0.015 cost limit

### **Analytics Workflows**

#### **Usage Analytics Workflow**

- **File**: `configs/workflows/usage_analytics_workflow.yaml`
- **Purpose**: Collect and process usage analytics
- **Tier**: SLM_A (fast data processing)
- **Steps**: Data Collection → Aggregation → Analysis → Reporting → Storage
- **Budget**: 500ms max, $0.005 cost limit

#### **Performance Monitoring Workflow**

- **File**: `configs/workflows/performance_monitoring_workflow.yaml`
- **Purpose**: Monitor system performance and generate alerts
- **Tier**: SLM_A (real-time monitoring)
- **Steps**: Metrics Collection → Analysis → Threshold Check → Alert Generation → Notification
- **Budget**: 100ms max, $0.001 cost limit

## 🔧 **Workflow Configuration Schema**

### **Base Workflow Schema**

```yaml
workflow:
  id: string                    # Unique workflow identifier
  name: string                  # Human-readable workflow name
  version: string               # Workflow version (semantic versioning)
  description: string           # Workflow description
  category: string              # Workflow category
  owner: string                 # Workflow owner/team

  # Execution Configuration
  execution:
    tier_preference: string     # SLM_A, SLM_B, or LLM
    timeout_ms: number          # Maximum execution time
    retry_policy: object        # Retry configuration
    compensation_enabled: boolean # Enable compensation actions

  # Budget Configuration
  budget:
    max_cost_usd: number        # Maximum cost per execution
    max_tokens: number          # Maximum tokens per execution
    max_latency_ms: number      # Maximum latency

  # Steps Configuration
  steps: array                  # Array of workflow steps
    - id: string               # Step identifier
      type: string             # Step type
      config: object           # Step-specific configuration
      timeout_ms: number       # Step timeout
      retry_count: number      # Number of retries
      compensation_action: object # Compensation action if step fails

  # Validation Configuration
  validation:
    input_schema: object        # JSON schema for input validation
    output_schema: object       # JSON schema for output validation
    business_rules: array       # Business rule validations

  # Monitoring Configuration
  monitoring:
    metrics_enabled: boolean    # Enable metrics collection
    logging_level: string       # Logging level (DEBUG, INFO, WARN, ERROR)
    alerting_rules: array       # Alerting configuration
```

### **Step Types**

#### **Router Step**

```yaml
type: "router"
config:
  model: "router_v2"
  features:
    - "query_length"
    - "complexity_score"
    - "domain_classification"
  tier_mapping:
    simple: "SLM_A"
    medium: "SLM_B"
    complex: "LLM"
```

#### **Knowledge Search Step**

```yaml
type: "knowledge_search"
config:
  vector_db: "qdrant"
  collection: "tenant_{tenant_id}_knowledge"
  max_results: 5
  similarity_threshold: 0.8
  rerank: true
```

#### **Response Generation Step**

```yaml
type: "response_generation"
config:
  model: "gpt-4"
  temperature: 0.7
  max_tokens: 1000
  system_prompt: "You are a helpful customer support assistant."
  context_window: 4000
```

#### **Tool Execution Step**

```yaml
type: "tool_execution"
config:
  tool_id: "payment_processor"
  parameters:
    amount: "{payment_amount}"
    currency: "USD"
    payment_method: "{payment_method}"
  timeout_ms: 10000
  retry_count: 3
```

#### **Validation Step**

```yaml
type: "validation"
config:
  validators:
    - type: "json_schema"
      schema: "response_schema.json"
    - type: "business_rules"
      rules: ["no_pii_leakage", "positive_sentiment"]
    - type: "critic_call"
      model: "gpt-4"
      criteria: ["accuracy", "helpfulness", "safety"]
```

## 📊 **Workflow Execution Patterns**

### **Sequential Execution**

```yaml
execution_pattern: "sequential"
steps:
  - id: "step_1"
    depends_on: []
  - id: "step_2"
    depends_on: ["step_1"]
  - id: "step_3"
    depends_on: ["step_2"]
```

### **Parallel Execution**

```yaml
execution_pattern: "parallel"
steps:
  - id: "step_1"
    depends_on: []
  - id: "step_2"
    depends_on: ["step_1"]
  - id: "step_3"
    depends_on: ["step_1"]
  - id: "step_4"
    depends_on: ["step_2", "step_3"]
```

### **Conditional Execution**

```yaml
execution_pattern: "conditional"
steps:
  - id: "router_step"
    depends_on: []
  - id: "simple_flow"
    depends_on: ["router_step"]
    condition: "{router_result.tier} == 'SLM_A'"
  - id: "complex_flow"
    depends_on: ["router_step"]
    condition: "{router_result.tier} == 'LLM'"
```

## 🔄 **Saga Compensation Patterns**

### **Order Processing Saga**

```yaml
compensation:
  steps:
    - id: "payment_step"
      compensation_action:
        type: "refund_payment"
        parameters:
          transaction_id: "{payment_result.transaction_id}"
          amount: "{payment_result.amount}"

    - id: "inventory_step"
      compensation_action:
        type: "restore_inventory"
        parameters:
          product_id: "{order.product_id}"
          quantity: "{order.quantity}"

    - id: "notification_step"
      compensation_action:
        type: "send_cancellation_email"
        parameters:
          customer_email: "{order.customer_email}"
          order_id: "{order.order_id}"
```

## 📈 **Workflow Metrics & Monitoring**

### **Key Metrics**

- **Execution Time**: Average and P95 execution times
- **Success Rate**: Percentage of successful executions
- **Error Rate**: Percentage of failed executions
- **Cost per Execution**: Average cost in USD
- **Token Usage**: Average tokens consumed
- **Compensation Rate**: Percentage of executions requiring compensation

### **Alerting Rules**

```yaml
alerts:
  - name: "High Error Rate"
    condition: "error_rate > 5%"
    severity: "warning"

  - name: "High Latency"
    condition: "p95_latency > 2000ms"
    severity: "warning"

  - name: "Cost Exceeded"
    condition: "avg_cost > budget.max_cost_usd"
    severity: "critical"

  - name: "Compensation Rate High"
    condition: "compensation_rate > 10%"
    severity: "warning"
```

## 🚀 **Workflow Deployment**

### **Deployment Configuration**

```yaml
deployment:
  environments:
    - name: "development"
      enabled: true
      version: "latest"

    - name: "staging"
      enabled: true
      version: "stable"

    - name: "production"
      enabled: false
      version: "v1.2.0"

  rollout_strategy:
    type: "canary"
    percentage: 10
    duration: "24h"

  health_checks:
    - endpoint: "/health/workflow/{workflow_id}"
      interval: "30s"
      timeout: "5s"
```

## 📋 **Workflow Index Summary**

| Category           | Workflow Count | Total Steps | Avg Execution Time | Avg Cost   |
| ------------------ | -------------- | ----------- | ------------------ | ---------- |
| Customer Support   | 3              | 15          | 600ms              | $0.006     |
| E-commerce         | 3              | 18          | 1500ms             | $0.025     |
| Lead Management    | 3              | 12          | 700ms              | $0.007     |
| Payment Processing | 2              | 10          | 1750ms             | $0.017     |
| Multi-Channel      | 3              | 12          | 900ms              | $0.009     |
| Analytics          | 2              | 8           | 300ms              | $0.003     |
| **Total**          | **16**         | **75**      | **950ms**          | **$0.011** |

---

**Status**: ✅ Production-Ready Workflows Index Documentation  
**Last Updated**: September 2024  
**Version**: 1.0.0
