# TESTING OVERVIEW (Production-Grade, Multi-Agent)

## 1. Scope & Gates

### **Quality Gates**

- **API Performance**: PR fails if p95 API > 500ms, p99 API > 1000ms
- **WebSocket Performance**: PR fails if p95 WS > 100ms, p99 WS > 200ms
- **Router Accuracy**: PR fails if misroute% > 5%
- **Cost Control**: PR fails if cost/run > $0.01
- **Error Rate**: PR fails if error rate > 0.1%
- **Security**: PR fails if any critical security test fails
- **Multi-tenant Isolation**: PR fails if any cross-tenant data access detected

### **Coverage Goals**

- **Line Coverage**: 85% minimum, 90% target
- **Critical Paths**: 95% coverage of business-critical workflows
- **Branch Coverage**: 80% minimum for decision points
- **Integration Coverage**: 100% of service boundaries

## 2. Suite Inventory & Topology

### **Test System Upgrades (T1-T10) - 100% Complete**

The testing framework has been upgraded with **10 comprehensive test system upgrades** bringing it to production-grade quality:

| Upgrade | Status | Category | Tests Added | Key Features |
|---------|--------|----------|-------------|--------------|
| **T1** | ✅ | Test Scaffolding | 4 files | MOCK/GOLDEN/LIVE_SMOKE modes, cassette loader, factories |
| **T2** | ✅ | Contract Tests | 2 files | Strict JSON boundaries, error mapping, PII redaction |
| **T3** | ✅ | E2E Journeys | 6 files | 10+ canonical user journeys across all features |
| **T4** | ✅ | Realtime Tests | 2 files | WebSocket backpressure, Locust load testing |
| **T5** | ✅ | Router Drift Gates | 2 files | Early-exit validation, misroute detection, Hypothesis fuzzing |
| **T6** | ✅ | Multi-tenant Safety | 3 files | RLS isolation, quotas, permissioned RAG, PII/DLP |
| **T7** | ✅ | Chaos & Replay | 3 files | Orchestrator failure, NATS DLQ, episode replay |
| **T8** | ✅ | Performance Gates | 2 files | Baseline JSON, Locust, cost ceilings |
| **T9** | ✅ | Observability | 3 files | Prometheus scraping, OTEL spans, log redaction |
| **T10** | ✅ | Flakiness Management | 3 files | Flaky detection, quarantine, test-impact analysis |

**Total Test System Upgrades**: 30+ new test files with comprehensive production-grade coverage.

### **Test Suite Inventory**

- **Unit Tests**: 979+ tests, component-level validation
- **Contract Tests**: 8+ tests, API schema validation with strict JSON boundaries
- **Integration Tests**: 80+ tests, service boundary validation
- **E2E Tests**: 10+ flows, complete user journey validation across all features
- **Realtime Tests**: 10+ tests, WebSocket backpressure and high-concurrency handling
- **Router Tests**: 12+ tests, ML routing accuracy and drift detection
- **Multi-tenant Tests**: 15+ tests, RLS isolation, quotas, and permissioned RAG
- **Chaos Tests**: 12+ tests, failure scenario validation and episode replay
- **Performance Tests**: 8+ tests, load testing and regression detection
- **Observability Tests**: 25+ tests, metrics, tracing, and log redaction validation
- **Flakiness Tests**: 17+ tests, flaky test detection and management
- **Security Tests**: 120+ tests, multi-tenant and data protection

### **Test Topology**

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              TEST ARCHITECTURE                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   UNIT TESTS    │    │ CONTRACT TESTS  │    │INTEGRATION TESTS│    │   E2E TESTS     │
│                 │    │                 │    │                 │    │                 │
│  MOCK Mode      │    │  MOCK Mode      │    │ GOLDEN Mode     │    │ LIVE_SMOKE Mode │
│  < 30s          │    │  < 60s          │    │  < 5min         │    │  < 15min        │
│  All Mocked     │    │  Schema Only    │    │  Ephemeral DB   │    │  Full Stack     │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │                       │
         │                       │                       │                       │
         ▼                       ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ REALTIME TESTS  │    │  ROUTER TESTS   │    │   RAG TESTS     │    │  TOOLS-SAGA     │
│                 │    │                 │    │                 │    │                 │
│  MOCK Mode      │    │  GOLDEN Mode    │    │ LIVE_SMOKE Mode │    │  GOLDEN Mode    │
│  < 10min        │    │  < 10min        │    │  < 10min        │    │  < 15min        │
│  Mock WS        │    │  Mock Router    │    │  Real Vector DB │    │  Mock Tools     │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │                       │
         │                       │                       │                       │
         ▼                       ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  CHAOS TESTS    │    │ PERFORMANCE     │    │ OBSERVABILITY   │    │  ADVERSARIAL    │
│                 │    │     TESTS       │    │     TESTS       │    │     TESTS       │
│                 │    │                 │    │                 │    │                 │
│ LIVE_SMOKE Mode │    │ LIVE_SMOKE Mode │    │ LIVE_SMOKE Mode │    │  MOCK Mode      │
│  < 20min        │    │  < 30min        │    │  < 5min         │    │  < 10min        │
│  Full Stack     │    │  Load Testing   │    │  Metrics Valid  │    │  Attack Vectors │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

### **Dependency Mocking Strategy**

- **MOCK Mode**: All external dependencies mocked (DB, Redis, NATS, LLMs)
- **GOLDEN Mode**: Ephemeral containers for DB/Redis/NATS, recorded LLM responses
- **LIVE_SMOKE Mode**: Full stack with production-like configuration

## 3. Modes & Data

### **Execution Modes**

- **MOCK Mode**: `seed=42, temp=0.0` - Fast unit tests with deterministic behavior
- **GOLDEN Mode**: `seed=42, temp=0.0` - Deterministic integration tests with recorded responses
- **LIVE_SMOKE Mode**: `seed=42, temp=0.1` - Production-like validation with minimal traffic

### **Cassettes Policy**

- **Recording**: Automatic recording of LLM interactions in GOLDEN mode
- **Normalization**: Timestamps, UUIDs, and dynamic IDs normalized for consistency
- **Retention**: 30 days for active cassettes, 90 days for archived
- **Refresh**: Weekly refresh of outdated cassettes (>30 days old)
- **Validation**: Hash-based integrity checking for cassette files

### **Test Data Management**

- **Synthetic Generator**: Privacy-compliant synthetic data generation
- **Data Retention**: 7 days for test data, 30 days for audit logs
- **Cleanup Policy**: Automatic cleanup after test completion
- **Privacy Compliance**: No real PII, synthetic data only
- **Volume**: 10K tenants, 50K users, 100K documents per test run

## 4. Environments

### **Ephemeral Dependencies**

```yaml
# docker-compose.test.yml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: test_db
      POSTGRES_PASSWORD: test_password
    ports:
      - "5432:5432"

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  nats:
    image: nats:2.9
    ports:
      - "4222:4222"
      - "8222:8222"

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
```

### **Secrets Management**

- **Test Secrets**: `.env.test` file with test-specific credentials
- **Rotation**: Weekly rotation of test secrets
- **Isolation**: Separate secret namespaces per test environment
- **Cleanup**: Automatic secret cleanup after test completion

### **Network Isolation**

- **Test Networks**: Isolated Docker networks per test run
- **Service Discovery**: Internal DNS resolution for test services
- **Port Management**: Dynamic port allocation to prevent conflicts
- **Security**: Network policies preventing external access

## 5. Performance & Realtime

### **Performance Profiles**

- **Baseline**: 100 RPS, 10min duration, p95 < 500ms
- **Stress**: 500 RPS, 5min duration, p95 < 1000ms
- **Spike**: 1000 RPS, 2min duration, p95 < 1500ms
- **Soak**: 200 RPS, 2hrs duration, p95 < 800ms

### **Performance Targets**

- **API Performance**: p50 < 150ms, p95 < 500ms, p99 < 1000ms
- **WebSocket Performance**: p50 < 50ms, p95 < 100ms, p99 < 200ms
- **Throughput**: > 100 RPS sustained, > 500 RPS peak
- **Error Rate**: < 0.1% under normal load, < 1% under stress

### **WebSocket Policy**

- **Backpressure Handling**: Drop intermediate messages, ensure final delivery
- **Connection Management**: Graceful degradation under load
- **Session Recovery**: Automatic reconnection with state restoration
- **Metrics Assertion**: `ws_backpressure_drops < 10/min`, `ws_send_errors < 1%`

## 6. Router Quality & Cost

### **Router Configuration**

- **Early-Exit Threshold**: 0.95 confidence for strict JSON responses
- **Misroute Threshold**: < 5% misroute rate
- **Tier Distribution**: SLM_A > 60%, SLM_B > 30%, LLM < 10%
- **Decision Latency**: p95 < 100ms for routing decisions

### **Cost & Latency Validation**

- **Cost Delta**: ≤ 10% variance from expected cost
- **Latency Delta**: ≤ 50ms variance from expected latency
- **Measurement**: Real-time tracking via Prometheus metrics
- **Alerting**: Immediate alert if thresholds exceeded

## 7. Reliability Invariants

### **Timeout Configuration**

- **API Requests**: 30s timeout, 25s response timeout
- **Tool Execution**: 60s timeout, 55s response timeout
- **Database Queries**: 10s timeout, 5s connection timeout
- **WebSocket Messages**: 30s timeout, 10s connection timeout

### **Retry Configuration**

- **Max Retries**: 3 attempts with exponential backoff
- **Backoff Strategy**: 1s base, 2x multiplier, max 60s
- **Jitter**: ±10% randomization to prevent thundering herd
- **Retryable Errors**: 408, 429, 500, 502, 503, 504

### **Circuit Breaker Configuration**

- **Failure Threshold**: 5 failures before opening
- **Success Threshold**: 3 successes before closing
- **Open Timeout**: 60s before attempting half-open
- **Half-Open Timeout**: 30s in half-open state

### **Bulkhead Limits**

- **Thread Pool**: 10 workers, 100 queue size
- **Connection Pool**: 20 max connections, 5 per route
- **Memory**: 512MB max usage, 64MB per operation
- **CPU**: 80% max usage, 10% per operation

### **Idempotency**

- **Key Format**: `idempotency:{tenant_id}:{user_id}:{operation_hash}:{timestamp}`
- **TTL**: 3600 seconds (1 hour)
- **Storage**: Redis with automatic expiration
- **Validation**: Request hash validation for consistency

### **Write-Ahead Events**

- **Tool Events**: `tool.call.{requested,succeeded,failed}`
- **Workflow Events**: `workflow.{started,completed,failed,compensated}`
- **User Events**: `user.{authenticated,authorized,action_performed}`
- **System Events**: `system.{health_check,metric_collected,alert_triggered}`

### **Saga Compensation Table**

| Step         | Compensation Action | Timeout | Retry Count |
| ------------ | ------------------- | ------- | ----------- |
| Payment      | Refund Transaction  | 30s     | 3           |
| Inventory    | Restore Stock       | 15s     | 3           |
| Email        | Send Cancellation   | 10s     | 2           |
| CRM          | Revert Status       | 20s     | 3           |
| Notification | Send Alert          | 5s      | 2           |

## 8. Security & Multi-Tenant

### **Row-Level Security (RLS)**

- **Policy**: Tenant-based data isolation with user-level access control
- **Validation**: 0 cross-tenant data access allowed
- **Testing**: Automated cross-tenant access prevention tests
- **Audit**: Complete audit trail for all data access

### **Quota Enforcement**

- **Rate Limiting**: 1000 req/min per tenant, 429 after limit
- **Usage Tracking**: Real-time quota monitoring and enforcement
- **Plan-Based Limits**: Different limits per tenant tier
- **Alerting**: Immediate alert when quotas exceeded

### **RAG Permission Filters**

- **Collection Isolation**: Tenant-specific vector collections
- **Document Permissions**: Role-based document access (public, internal, confidential)
- **Query Filtering**: Tenant and role-based query filtering
- **Result Validation**: Cross-tenant hit prevention

### **PII/DLP Configuration**

- **Detection Patterns**: Email, SSN, credit card, phone number regex
- **Redaction Masks**: `[REDACTED]` for full redaction, partial masking for audit
- **Allowlist**: Configurable patterns for business-specific data
- **Compliance**: GDPR, CCPA, SOC 2 compliance validation

## 9. Observability Assertions

### **Prometheus Metrics**

- **agent_run_latency_ms**: p95 < 500ms, p99 < 1000ms
- **router_decision_latency_ms**: p95 < 100ms, p99 < 200ms
- **router_misroute_rate**: < 5% misroute rate
- **expected_vs_actual_cost**: < 10% cost variance
- **ws_backpressure_drops**: < 10 drops/minute
- **tool_error_rate**: < 1% error rate
- **retry_total**: < 5% retry rate

### **OpenTelemetry Attributes**

- **Required Attributes**: run_id, step_id, tenant_id, tool_id, tier, workflow
- **Span Validation**: Parent-child relationship validation
- **Trace Correlation**: End-to-end trace correlation
- **Sampling**: 100% sampling for critical paths, 10% for others

### **Log Redaction Patterns**

- **Email**: `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}` → `[REDACTED]`
- **SSN**: `\d{3}-\d{2}-\d{4}` → `[REDACTED]`
- **Credit Card**: `\d{4}-\d{4}-\d{4}-\d{4}` → `[REDACTED]`
- **Phone**: `\d{3}-\d{3}-\d{4}` → `[REDACTED]`
- **UUID**: `[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}` → `[UUID]`

## 10. CI Orchestration

### **Pipeline Stages**

1. **Unit Tests**: 5min timeout, parallel execution
2. **Contract Tests**: 15min timeout, parallel execution
3. **Integration Tests**: 20min timeout, sequential execution
4. **E2E Tests**: 25min timeout, sequential execution
5. **Performance Tests**: 35min timeout, sequential execution
6. **Security Tests**: 15min timeout, parallel execution
7. **Observability Tests**: 10min timeout, parallel execution
8. **Quality Gates**: 5min timeout, validation and reporting

### **Caching Strategy**

- **Dependencies**: Cache pip dependencies for 24 hours
- **Docker Images**: Cache base images for 7 days
- **Test Artifacts**: Cache test results for 1 hour
- **Build Cache**: Cache build artifacts for 2 hours

### **Fail-Fast Configuration**

- **Early Termination**: Stop pipeline on first critical failure
- **Parallel Execution**: Run independent tests in parallel
- **Resource Limits**: 4GB RAM, 2 CPU cores per test job
- **Timeout Enforcement**: Strict timeout enforcement with cleanup

### **Artifacts Collection**

- **JUnit Reports**: XML format for test results
- **Coverage Reports**: HTML and XML coverage reports
- **Locust HTML**: Performance test reports with charts
- **Baselines JSON**: Performance baseline comparisons
- **Security Reports**: Bandit and Safety scan results
- **Retention**: 30 days for all artifacts

### **Flakiness Management**

- **Auto-Rerun**: `@flaky` decorator with auto-rerun=2
- **Quarantine**: Automatic quarantine of flaky tests
- **Weekly Report**: Automated flakiness trend analysis
- **Threshold**: < 2% flakiness rate acceptable

### **Test Impact Selection**

- **Path-Based**: Run tests affected by changed files
- **Impact Analysis**: Analyze code changes for test impact
- **Smart Selection**: Skip unrelated test suites
- **Fallback**: Run full suite if impact analysis fails

---

**Status**: ✅ Production-Ready Testing Overview  
**Last Updated**: September 2024  
**Version**: 1.0.0
