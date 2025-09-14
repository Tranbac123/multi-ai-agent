# SYSTEM OVERVIEW (Production-Grade, Multi-AI-Agent)

## 1) Context & Goals

### Problem & Scope

- **Problem**: Need a production-grade, multi-tenant AI-as-a-Service platform for intelligent customer support, order management, and lead capture across multiple channels
- **Scope**:
  - Multi-tenant architecture with complete tenant isolation
  - YAML-based workflow definitions for easy customization
  - Event-driven microservices with Saga compensation patterns
  - Production-grade testing with 13 comprehensive commits
  - Real-time WebSocket communication with backpressure handling
  - Comprehensive observability and monitoring

### Non-goals

- Single-tenant deployments
- Non-event-driven architectures
- Manual workflow definitions (must be YAML-based)
- Basic testing without production-grade coverage
- Non-scalable WebSocket implementations
- Missing observability or monitoring

### SLO: availability 99.9%, p50 100ms / p95 500ms (API, WS), error budget 0.1%

## 2) Service Map

| Service           | Purpose                                              | Tech               | Scale/HA           | Owner    |
| ----------------- | ---------------------------------------------------- | ------------------ | ------------------ | -------- |
| api-gateway       | Auth, rate-limit, OpenAPI, JWT validation            | FastAPI + JWT      | HPA x3             | Team-A   |
| orchestrator      | FSM/LangGraph, Saga compensation, workflow execution | Python + LangGraph | KEDA (queue depth) | Team-B   |
| router-service    | difficulty → tier, feature extraction, bandit policy | Python + ML        | HPA x2             | Team-B   |
| realtime          | WebSocket + backpressure, session management         | ASGI + Redis       | HPA x3             | Team-C   |
| ingestion         | chunk/embed/index, document processing               | Python Workers     | KEDA (doc queue)   | Team-D   |
| analytics-service | read-only CQRS KPIs, reporting, dashboards           | Python + CQRS      | Read-replica x2    | Data     |
| billing-service   | usage metering, invoices, quota enforcement          | Python + Webhooks  | HPA x2             | FinOps   |
| control-plane     | feature flags, registries, configs                   | Python + Config    | Static x1          | Platform |
| data-plane        | migrations, events, storages                         | Python + SQLAlchemy | Static x1       | Platform |

## 3) Runtime Topology

- **Environments**: Dev/Staging/Prod
- **Regions**: Primary (us-east-1), DR (us-west-2)
- **Ingress**:
  - API Gateway: LoadBalancer service with TLS termination
  - WebSocket: Sticky sessions with Redis affinity
  - Static assets: CDN with edge caching
- **Autoscaling**:
  - KEDA: Queue depth-based scaling (orchestrator, ingestion)
  - HPA: CPU/Memory-based scaling (api-gateway, router, realtime)
- **NetworkPolicy**:
  - Namespace isolation
  - Service mesh with mTLS between services
  - Ingress/egress rules per service

## 4) Data Plane

### PostgreSQL (RLS Multi-tenant)

- **Schemas/Tables**:
  - `tenants`: tenant_id, name, tier, config, created_at
  - `plans`: plan_id, name, limits, pricing, features
  - `api_keys`: key_id, tenant_id, scopes, rate_limits, expires_at
  - `usage_counters`: tenant_id, service, count, window, reset_at
  - `agent_runs`: run_id, tenant_id, workflow, status, metrics
  - `audit_logs`: log_id, tenant_id, action, resource, timestamp
  - `workflow_executions`: execution_id, tenant_id, steps, compensation
- **RLS Policies**: Tenant-level isolation on all tables
- **Indexes**: Composite indexes on (tenant_id, created_at) for time-series queries

### Redis

- **Session Management**: WebSocket session state, user sessions
- **Caching**: API responses, LLM responses, feature flags
- **Rate Limiting**: Token bucket per tenant/API key
- **Pub/Sub**: Real-time notifications, event broadcasting

### Vector Database (Qdrant)

- **Collections**: tenant-specific vector collections
- **Embeddings**: Document chunks, FAQ entries, knowledge base
- **Isolation**: Tenant-level namespace isolation
- **Backups**: Daily snapshots with cross-region replication

### Backups/DR

- **RPO**: 15 minutes (transaction log backups)
- **RTO**: 4 hours (full restore with data replay)
- **DR Strategy**: Active-passive with automated failover

## 5) Messaging/Eventing

### Bus: NATS JetStream

- **Subjects**:
  - `agent.run.requested` - New agent execution requests
  - `agent.run.started` - Agent execution started
  - `agent.run.completed` - Agent execution completed
  - `tool.call.requested` - Tool execution requests
  - `tool.call.succeeded` - Tool execution success
  - `tool.call.failed` - Tool execution failures
  - `ingest.doc.processed` - Document processing events
  - `usage.metered` - Usage metering events
  - `billing.invoice.generated` - Invoice generation events
- **DLQ Policy**:
  - Max retries: 3 with exponential backoff (1s, 5s, 25s)
  - DLQ retention: 7 days
  - Manual inspection required for DLQ processing
- **Retry/Backoff**: Exponential backoff with jitter (max 30s)
- **Idempotency**: Key format: `{service}:{tenant_id}:{resource_id}:{timestamp}`

## 6) APIs & Contracts

### OpenAPI (api-gateway)

```yaml
openapi: 3.0.0
info:
  title: Multi-AI-Agent API
  version: 1.0.0
  description: Production-grade multi-tenant AI-as-a-Service platform
servers:
  - url: https://api.multi-ai-agent.com/v1
paths:
  /chat/message:
    post:
      summary: Send chat message
      requestBody:
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/ChatMessage"
      responses:
        "200":
          description: Chat response
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ChatResponse"
components:
  schemas:
    ChatMessage:
      type: object
      required: [message, tenant_id, user_id]
      properties:
        message:
          type: string
        tenant_id:
          type: string
        user_id:
          type: string
        context:
          type: object
```

### Router IO Schema

```json
{
  "router_request": {
    "query": "string",
    "context": "object",
    "tenant_id": "string",
    "user_id": "string",
    "tier_preference": "fast|balanced|accurate"
  },
  "router_response": {
    "tier": "SLM_A|SLM_B|LLM",
    "confidence": "float",
    "reasoning": "string",
    "cost_estimate": "float",
    "latency_estimate": "int"
  }
}
```

### ToolSpec/MessageSpec/ErrorSpec

- **ToolSpec**: Pydantic models with strict validation
- **MessageSpec**: WebSocket message format with type safety
- **ErrorSpec**: Standardized error responses with error codes
- **Validation**: Strict JSON everywhere with Pydantic V2

## 7) Workflows

### Global Pattern

```
Plan → Route → Work → Verify → Repair → Commit
```

### Use-cases

- **FAQ**: Query → Router → Knowledge Search → Response Generation → Validation
- **Order**: Order Request → Router → Order Processing → Payment → Confirmation
- **Tracking**: Tracking Query → Router → Order Lookup → Status Update → Notification
- **Lead**: Lead Capture → Router → CRM Integration → Follow-up → Qualification
- **Payment**: Payment Request → Router → Payment Gateway → Processing → Confirmation

### Validators/Gates

- **json_schema**: Strict JSON validation for all payloads
- **critic_call**: LLM-based response quality validation
- **factuality**: Fact-checking against knowledge base
- **score_threshold**: Minimum confidence scores (min=0.8)

### Budgets per Step

- **wall_ms**: 5000ms max per step
- **tokens**: 10,000 tokens max per request
- **cost**: $0.10 max per execution

## 8) Reliability & Safety

### Timeouts/Retry

- **Timeouts**: 30s default, 5s for critical paths
- **Retry**: Exponential backoff with jitter (max 3 attempts)
- **Circuit Breaker**: Open after 5 failures, reset after 60s
- **Bulkhead**: Isolated thread pools per service

### Saga/Compensation

- **Saga Pattern**: Distributed transaction management
- **Compensation Actions**:
  - Email: Send cancellation email
  - Payment: Refund transaction
  - CRM: Revert lead status
- **Write-ahead Events**:
  - `tool.call.requested` - Before execution
  - `tool.call.succeeded` - After success
  - `tool.call.failed` - After failure

## 9) Observability & Ops

### OpenTelemetry Attributes

- **run_id**: Unique execution identifier
- **step_id**: Individual step identifier
- **tenant_id**: Tenant isolation tracking
- **tool_id**: Tool execution tracking
- **tier**: Router decision tier
- **workflow**: Workflow type and version

### Prometheus Metrics

- **router_decision_latency_ms**: Router decision timing
- **router_misroute_rate**: Router accuracy tracking
- **ws_backpressure_drops**: WebSocket backpressure events
- **tool_error_rate**: Tool execution error rate
- **retry_total**: Total retry attempts
- **cost_usd_total**: Cumulative cost tracking
- **tokens_total**: Token usage tracking

### Dashboards & Alerts

- **Grafana Dashboards**:
  - System Overview (CPU, Memory, Network)
  - Business Metrics (Requests, Errors, Latency)
  - Cost Tracking (Usage, Billing, Budgets)
- **Alert Rules**:
  - High error rate (>5%)
  - High latency (p95 >500ms)
  - Cost threshold exceeded
  - Service down

### Runbooks

- **TIMEOUT**: Check service health, restart if needed
- **TOOL_DOWN**: Failover to backup tool, notify team
- **VALIDATION_FAIL**: Review validation rules, update if needed
- **WS_OVERLOAD**: Scale WebSocket service, check backpressure

## 10) Security & Compliance

### Authentication/Authorization

- **JWT**: RS256 signed tokens with 1-hour expiry
- **API Keys**: Scoped access with rate limiting
- **RBAC**: Role-based access control per tenant
- **Scopes**: Granular permissions (read, write, admin)

### Data Protection

- **PII/DLP Redaction**: Automatic detection and redaction
- **Secret Management**: Kubernetes secrets with rotation
- **Data Residency**: Tenant data stays in specified regions
- **Encryption**: TLS 1.3 in transit, AES-256 at rest

### Supply Chain Security

- **SBOM**: Software Bill of Materials for all dependencies
- **Scanning**: Automated vulnerability scanning in CI/CD
- **Signing**: Container image signing with cosign
- **Compliance**: SOC 2 Type II, GDPR compliant

---

**Status**: ✅ Production-Ready Multi-Tenant AIaaS Platform
**Last Updated**: September 2024
**Version**: 1.0.0
