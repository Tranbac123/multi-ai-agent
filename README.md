# Multi-Tenant AIaaS Platform

A production-grade, multi-tenant AI-as-a-Service platform providing intelligent customer support, workflow orchestration, and real-time analytics across multiple channels.

## 📚 **Documentation**

Comprehensive documentation is available in the [`docs/`](docs/) directory:

- **[System Overview](docs/SYSTEM_OVERVIEW.md)** - Production-grade multi-agent platform overview
- **[Visual Architecture](docs/VISUAL_ARCHITECTURE.md)** - Architecture diagrams and illustrations
- **[Runtime Topology](docs/RUNTIME_TOPOLOGY.md)** - Ingress, autoscaling, DLQ, retries, Saga patterns
- **[Test Topology](docs/TEST_TOPOLOGY.md)** - Test dependency mapping (MOCK vs LIVE per suite)
- **[Workflows Index](docs/WORKFLOWS_INDEX.md)** - YAML workflow definitions and registry
- **[API Contracts](docs/CONTRACTS.md)** - Request/response schemas and validation rules
- **[CI/CD Pipeline](docs/CI_CD_PIPELINE.md)** - Pipeline configuration and quality gates
- **[Production-Grade Testing](docs/testing/)** - 13 comprehensive test categories with 1000+ tests

### **Quick Start Documentation**

- **[Testing Overview](docs/testing/TESTING_OVERVIEW.md)** - Production-ready testing framework
- **[Test Matrix](docs/testing/TEST_MATRIX.md)** - Risk-based test categorization and execution
- **[Performance Profiles](docs/testing/PERF_PROFILES.md)** - Load testing and performance validation

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   API Gateway   │    │  Orchestrator   │    │  Router Service │
│   (React)       │◄──►│   (FastAPI)     │◄──►│   (LangGraph)   │◄──►│   (Router v2)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │                       │
         │                       │                       │                       │
         ▼                       ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Realtime      │    │   Ingestion     │    │   Analytics     │    │   Billing       │
│   Service       │    │   Service       │    │   Service       │    │   Service       │
│   (WebSocket)   │    │   (Document)    │    │   (CQRS)        │    │   (Usage)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │                       │
         │                       │                       │                       │
         ▼                       ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Control       │    │   Event Bus     │    │   Database      │    │   Observability │
│   Plane         │    │   (NATS)        │    │   (PostgreSQL)  │    │   (OTel)        │
│   (Feature      │    │   (JetStream)   │    │   (RLS)         │    │   (Prometheus)  │
│    Flags)       │    │   (DLQ)         │    │   (Multi-tenant)│    │   (Grafana)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Core Services

### **Runtime Services**

- **API Gateway**: Main entry point with authentication, rate limiting, and WebSocket support
- **Orchestrator**: LangGraph-based workflow execution with resilient tool adapters
- **Router Service**: Intelligent request routing with feature store and bandit policy
- **Realtime Service**: WebSocket service with backpressure handling
- **Ingestion Service**: Document processing and knowledge management
- **Analytics Service**: CQRS read-only analytics and reporting
- **Billing Service**: Usage tracking and billing engine
- **Chat Adapters**: Multi-channel chat integration (Facebook, Zalo, TikTok, WhatsApp, Telegram)
- **Tenant Service**: Self-serve tenant onboarding, plan management, and lifecycle hooks
- **Admin Portal**: Tenant administration, plan configuration, and system management

## 🌟 Enterprise-Grade Features

The platform now includes **8 advanced enterprise capabilities**:

1. **🌍 Data Residency & Regionalization** - Complete data sovereignty with regional provider selection
2. **⚖️ Fairness & Isolation** - Per-tenant concurrency control with weighted fair queuing
3. **💰 CostGuard** - Intelligent cost management with budget enforcement and drift detection
4. **🔒 Privacy & DLP** - Advanced data protection with PII detection and field-level encryption
5. **⚡ Tail-latency Control** - Request hedging and coordinated cancellation for optimal performance
6. **🌐 Multi-region Active-Active** - Disaster recovery with NATS mirroring and automated failover
7. **🔐 Supply-chain Security** - SBOM generation, image signing, and vulnerability scanning
8. **🛠️ Self-serve Plans** - Complete tenant onboarding with webhooks and admin portal

### **Control Plane**

- **Feature Flags**: Per-tenant feature flag management
- **Registries**: Agent and tool manifest management
- **Configs**: Environment-specific configuration management

### **Data Plane**

- **Migrations**: Database schema management with Alembic
- **Events**: Event sourcing and audit logging
- **Storages**: Multi-tenant data isolation with RLS

### **Observability**

- **OpenTelemetry**: Distributed tracing and metrics
- **Prometheus**: Metrics collection and alerting
- **Grafana**: Visualization dashboards and SLO monitoring
- **Runbooks**: Operational procedures and troubleshooting

## Technology Stack

- **Backend**: Python 3.11 + FastAPI + SQLAlchemy 2.0 (async) + asyncpg
- **AI**: OpenAI API + LangGraph workflows & agents + LangGraph/FSM
- **Database**: PostgreSQL 16 + RLS + Redis 7 + NATS JetStream
- **Frontend**: React + TypeScript + Tailwind CSS
- **Deployment**: Docker + Kubernetes + KEDA + HPA + NetworkPolicy
- **Monitoring**: OpenTelemetry + Prometheus + Grafana + SLOs + Alerts
- **Security**: `ruff` + `black` + `mypy(strict)` + `trivy` + `safety`
- **Testing**: pytest + httpx + Hypothesis + LLM-judge + Episode replay
- **Billing**: Usage tracking + Invoice generation + Payment processing

## 🚀 Production Hardening Complete (11 Commits)

The platform has been comprehensively hardened with enterprise-grade features for production stability, accuracy, safety, and reliability:

### **COMMIT 0 — Repo Audit Helpers**

- **Audit readiness script** with comprehensive codebase scanning for production readiness criteria
- **Loop safety detection** with MAX_STEPS, progress tracking, and oscillation detection validation
- **Contract enforcement verification** with strict Pydantic validation and boundary checking
- **Router guarantees validation** with feature extraction, classification, and canary deployment checks
- **Tool adapter reliability** with timeout, retry, circuit-breaker, and bulkhead pattern verification
- **Performance gates validation** with baseline establishment and cost ceiling enforcement
- **Automated CI integration** with PASS/FAIL reporting and readiness assessment

### **COMMIT 1 — Loop Safety in Orchestrator**

- **MAX_STEPS enforcement** with configurable step limits and automatic loop termination
- **Progress tracking** with state monitoring and no-progress event detection
- **Oscillation detection** via state hashing with automatic loop cutting
- **Budget-aware degradation** with intelligent resource management and fallback strategies
- **Comprehensive metrics** with loop_cut_total, progress_events, and safety_violations
- **Production-ready safety** with automatic escalation and manual intervention hooks
- **12 passing tests** covering loop safety scenarios and edge cases

### **COMMIT 2 — Strict Contracts at All Boundaries**

- **Pydantic strict validation** with strict=True and forbid_extra=True enforcement
- **Comprehensive contract specs** for AgentSpec, MessageSpec, ToolSpec, ErrorSpec, RouterSpec
- **Boundary enforcement** at API Gateway, Orchestrator, Router, and Tool adapters
- **PII redaction** in logs with automatic sensitive data protection
- **Validation error handling** with structured error responses and debugging information
- **Contract middleware** with automatic validation and error reporting
- **15 passing tests** covering contract validation and boundary enforcement

### **COMMIT 3 — Router v2 Guarantees**

- **Feature extractor** with token_count, json_schema_strictness, domain_flags, novelty, historical_failure_rate
- **Calibrated classifier** with temperature scaling and bandit policy optimization
- **Early-exit logic** for strict JSON schema validation with SLM tier locking
- **Per-tenant canary** with 5-10% traffic and automatic rollback on quality drift
- **Comprehensive metrics** with router_decision_latency_ms, router_misroute_rate, tier_distribution
- **Cost optimization** with expected_vs_actual_cost and expected_vs_actual_latency tracking
- **18 passing tests** covering routing guarantees and performance validation

### **COMMIT 4 — Tool Adapter Reliability**

- **Base adapter patterns** with timeouts, retries (exponential backoff + jitter), circuit-breaker, bulkhead
- **Idempotency management** with Redis-based caching and duplicate request handling
- **Write-ahead logging** with comprehensive event tracking and audit trails
- **Compensation logic** for side-effect reversal with automatic rollback capabilities
- **Saga orchestration** for multi-step distributed transactions with compensation management
- **Production reliability** with comprehensive error handling and recovery mechanisms
- **22 passing tests** covering reliability patterns and distributed transaction scenarios

### **COMMIT 5 — Realtime Backpressure**

- **Per-connection queues** with configurable drop policies (oldest, newest, priority-based)
- **WebSocket message buffering** with intelligent backpressure handling and graceful degradation
- **Connection management** with sticky sessions and Redis-based session storage
- **Comprehensive metrics** with ws_active_connections, ws_backpressure_drops, ws_send_errors
- **Production-ready scaling** with automatic connection pooling and resource management
- **Health monitoring** with detailed status reporting and performance analytics
- **14 passing tests** covering backpressure scenarios and WebSocket management

### **COMMIT 6 — Multi-tenant Safety & Fairness**

- **Row-Level Security (RLS)** with strict tenant isolation and data access control
- **Token bucket rate limiting** with per-tenant quotas and burst capacity management
- **Concurrency token management** with Redis-based resource isolation and fair scheduling
- **Weighted fair scheduling** with priority-based queuing and anti-starvation mechanisms
- **Admission control middleware** with multi-layer validation and request queuing
- **Degradation management** with automatic system load monitoring and performance optimization
- **16 passing tests** covering multi-tenant isolation and fairness scenarios

### **COMMIT 7 — RAG & Data Protection**

- **RAG metadata management** with tenant isolation, role-based access, and TTL management
- **Permissioned retrieval** with access validation and sensitivity filtering
- **PII detection engine** with comprehensive pattern matching and redaction capabilities
- **Field-level encryption** with KMS integration and envelope encryption for sensitive data
- **Sensitivity tagging** with automatic document classification and access control
- **Cross-tenant protection** with strict data isolation and leakage prevention
- **20 passing tests** covering RAG security and data protection scenarios

### **COMMIT 8 — Observability & SLOs**

- **OpenTelemetry instrumentation** with comprehensive spans, metrics, and traces
- **SLO management** with error budget tracking, burn rate analysis, and alerting
- **Prometheus metrics** with detailed performance monitoring and cost tracking
- **Grafana dashboards** with real-time visualization and SLO monitoring
- **Service correlation** with distributed tracing and request flow analysis
- **Production monitoring** with comprehensive alerting and performance optimization
- **18 passing tests** covering observability and SLO validation scenarios

### **COMMIT 9 — Eval & Replay**

- **Golden task management** with comprehensive task definitions and lifecycle management
- **LLM judge evaluation** with structured scoring, criteria-based assessment, and confidence metrics
- **Episode replay system** with state tracking, debugging capabilities, and regression testing
- **Evaluation engine** with multiple methods and composite scoring
- **Performance validation** with automated testing and quality assurance
- **Production evaluation** with comprehensive metrics and continuous improvement
- **25 passing tests** covering evaluation functionality and replay scenarios

### **COMMIT 10 — Performance Gates**

- **Performance baseline management** with comprehensive metric tracking and regression detection
- **Cost ceiling management** with spending limits, budget enforcement, and optimization recommendations
- **Locust performance testing** with realistic user scenarios and performance gate validation
- **Performance validation** with threshold enforcement and automatic alerting
- **Cost optimization** with intelligent recommendations and spending analysis
- **Production readiness** with comprehensive performance monitoring and cost management
- **28 passing tests** covering performance gates and cost management scenarios

## RACI (Responsibility Assignment)

### **Control Plane** (Platform Team)

**Responsible for**: Platform infrastructure, configuration, and governance

- **Feature Flags**: Runtime feature toggling and A/B testing
- **Registries**: Agent/tool manifest management and versioning
- **Configs**: Environment-specific configuration and secrets
- **Infrastructure**: Kubernetes, monitoring, security policies
- **Data Plane**: Database migrations, event schemas, storage policies
- **Observability**: Infrastructure, dashboards, alerting rules

### **Runtime** (Service Teams)

**Responsible for**: Service development, deployment, and operations

- **API Gateway**: Authentication, rate limiting, request routing
- **Orchestrator**: Workflow execution and tool coordination
- **Router Service**: Intelligent routing and cost optimization
- **Realtime Service**: WebSocket management and backpressure
- **Ingestion Service**: Document processing and knowledge indexing
- **Analytics Service**: Metrics aggregation and reporting
- **Billing Service**: Usage metering and invoice generation
- **Services**: Agents, tools, memory management

### **On-Call Map**

| **Service**       | **Primary**   | **Secondary** | **Escalation**      |
| ----------------- | ------------- | ------------- | ------------------- |
| API Gateway       | Service Team  | Platform Team | SRE Team            |
| Orchestrator      | Service Team  | Platform Team | SRE Team            |
| Router Service    | Service Team  | Platform Team | SRE Team            |
| Realtime Service  | Service Team  | Platform Team | SRE Team            |
| Ingestion Service | Service Team  | Platform Team | SRE Team            |
| Analytics Service | Service Team  | Platform Team | SRE Team            |
| Billing Service   | Service Team  | Platform Team | SRE Team            |
| Database          | Platform Team | SRE Team      | Database Team       |
| Event Bus         | Platform Team | SRE Team      | Infrastructure Team |
| Observability     | Platform Team | SRE Team      | Infrastructure Team |

## Quick Start

### **🚀 One-Command Setup**

```bash
# Clone and start the platform
git clone <repo-url>
cd multi-ai-agent
./start.sh
```

### **📖 Detailed Setup**

1. **Clone and setup**:

   ```bash
   git clone <repo-url>
   cd multi-ai-agent
   cp .env.example .env
   # Edit .env with your configuration
   ```

2. **Start development environment**:

   ```bash
   make dev
   ```

3. **Access services**:
   - API Gateway: http://localhost:8000
   - Realtime Service: http://localhost:8001
   - Router Service: http://localhost:8002
   - Orchestrator: http://localhost:8003
   - Analytics Service: http://localhost:8004
   - Billing Service: http://localhost:8005
   - Chat Adapters: http://localhost:8006
   - Web Dashboard: http://localhost:5173
   - API Docs: http://localhost:8000/docs
   - WebSocket: ws://localhost:8000/ws/chat
   - Grafana: http://localhost:3000
   - Prometheus: http://localhost:9090
   - Jaeger: http://localhost:16686

### **📚 Documentation**

- **[📖 Complete Documentation](docs/README.md)** - Comprehensive documentation index with organized structure
- **[🎯 Platform Features](docs/FEATURES.md)** - Complete features documentation with capabilities overview
- **[🏗️ Architecture](docs/architecture/)** - System design, patterns, and topology
- **[🚀 Deployment](docs/deployment/)** - Deployment guides and CI/CD pipeline
- **[💻 Development](docs/development/)** - Development guides and workflows
- **[🧪 Testing](docs/testing/)** - Comprehensive testing documentation and guides

## Development

### **Available Commands**

```bash
# Development
make dev          # Start development environment
make dev-stop     # Stop development environment
make dev-logs     # Show development logs
make dev-setup    # Setup development environment

# Testing
make test         # Run all tests
make test-unit    # Run unit tests only
make test-integration # Run integration tests only
make test-e2e     # Run end-to-end tests
make eval         # Run evaluation suite
make eval-episodes # Run episode replay evaluation
make eval-metrics # Run evaluation metrics

# Security
make security     # Run all security checks
make security-bandit # Run Bandit security linter
make security-safety # Run Safety dependency check
make security-semgrep # Run Semgrep security scan

# Code Quality
make format       # Format code with Black and isort
make lint         # Lint code with Ruff
make type-check   # Type checking with MyPy
make all          # Run all quality checks
make ci           # Run CI pipeline

# Build & Deploy
make build        # Build Docker images
make build-dev    # Build development Docker images
make deploy       # Deploy to production
make deploy-staging # Deploy to staging

# Database
make db-migrate   # Run database migrations
make db-rollback  # Rollback database migrations
make db-reset     # Reset database

# Monitoring
make monitor      # Start monitoring stack
make monitor-stop # Stop monitoring stack
make health       # Check service health

# Performance
make perf-test    # Run performance tests
make perf-load    # Run load tests

# Cleanup
make clean        # Clean up Docker resources
make clean-logs   # Clean up log files
make clean-cache  # Clean up cache files

# Documentation
make docs         # Generate documentation
make docs-serve   # Serve documentation locally

# Backup & Updates
make backup       # Backup database and configuration
make update-deps  # Update dependencies
make update-docker # Update Docker images
```

## API Endpoints

- **Chat**: `/api/v1/chat/*` - Customer chat interface
- **Router**: `/api/v1/router/decide` - Intelligent routing
- **Orchestrator**: `/api/v1/orchestrator/*` - Workflow execution
- **Analytics**: `/api/v1/analytics/*` - Metrics and reporting
- **Billing**: `/api/v1/billing/*` - Usage and billing
- **Ingestion**: `/api/v1/ingestion/*` - Document processing
- **Chat Adapters**: `/facebook/webhook`, `/zalo/webhook`, `/tiktok/webhook` - Multi-channel chat integration

## CI/CD Pipeline

The platform includes a comprehensive GitHub Actions CI/CD pipeline with:

### **Pipeline Jobs**

- **Quality Checks**: Format, lint, type checking, security scanning
- **Unit Tests**: Test coverage with pytest and codecov
- **Integration Tests**: Service integration with database dependencies
- **End-to-End Tests**: Full stack testing with Docker Compose
- **Performance Tests**: Load testing with Locust
- **Docker Build**: Multi-service container builds with caching
- **Deployment**: Automated staging and production deployments
- **Security Scan**: Trivy vulnerability scanning and CodeQL analysis

### **Branch Strategy**

- `main`: Production deployments
- `develop`: Staging deployments
- Pull requests: Full CI pipeline validation

## Environment Variables

See `.env.example` for required configuration including:

- Database URLs (PostgreSQL, Redis, NATS)
- OpenAI API key
- JWT secrets and encryption keys
- Monitoring endpoints (Prometheus, Grafana, Jaeger)
- Feature flag configuration
- Docker registry credentials
