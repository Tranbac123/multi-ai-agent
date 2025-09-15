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

## 🚀 Recent Production Hardening (8 Commits)

The platform has been significantly enhanced with production-grade features for high-concurrency production traffic:

### **COMMIT 1 — Router v2 Hardening (calibration, bandit, early-exit, canary)**

- **Feature extractor**: token_count, json_schema_strictness, domain_flags, novelty_score, historical_failure_rate
- **Calibrated classifier** with temperature scaling and deterministic fallback
- **Bandit policy** minimizing E[cost + λ·error] with sophisticated decision making
- **Early-exit logic** accepting SLM_A for strict JSON/schema passes, escalating to B/C otherwise
- **Canary deployments** per-tenant (5-10%) with automatic rollback on quality drops
- **Comprehensive metrics**: router_decision_latency_ms, router_misroute_rate, tier_distribution, expected_vs_actual_cost/latency
- **21 passing tests** covering unit and integration scenarios

### **COMMIT 2 — Realtime Backpressure Policy + Metrics**

- **Redis-based session storage** with sticky sessions and connection management
- **Sophisticated backpressure handling** with intermediate chunk dropping while preserving final messages
- **Enhanced WebSocket management** with connection pooling and graceful degradation
- **Comprehensive metrics**: ws_active_connections, ws_backpressure_drops, ws_send_errors
- **Production-ready health endpoints** with detailed status reporting
- **12 passing tests** covering backpressure scenarios and connection management

### **COMMIT 3 — Analytics-service as read-only CQRS + Dashboards**

- **Read-only CQRS architecture** with warehouse integration (ClickHouse/BigQuery/Postgres read-replica)
- **Comprehensive KPI endpoints** per tenant with success rates, latency percentiles, token usage, and cost analysis
- **Grafana dashboard generation** with JSON panel definitions for visualization
- **Advanced analytics engine** with caching, aggregation, and real-time processing
- **Multi-tenant data isolation** with secure access controls
- **6 passing tests** covering analytics functionality and dashboard generation

### **COMMIT 4 — Reliability as policy: adapters + Saga**

- **Enhanced Base Adapter** with timeouts, retries (exponential backoff + jitter), circuit-breaker, bulkhead, and idempotency
- **Saga Orchestrator** for distributed transactions with automatic compensation
- **Write-ahead events** tracking tool.call.{requested,succeeded,failed}
- **Tool-specific compensation** for email, payment, and CRM operations
- **Comprehensive reliability patterns** enforced across all tool adapters
- **21 passing tests** covering reliability patterns and Saga orchestration

### **COMMIT 5 — Autoscaling & security on K8s**

- **Enhanced KEDA autoscaling** with NATS JetStream queue depth triggers and custom metrics
- **Advanced HPA configuration** with resource-based and custom metric scaling
- **Comprehensive security hardening** with Pod Security Policy, NetworkPolicy, and resource quotas
- **Production-grade health monitoring** with retry logic and timeout handling
- **Network isolation** with east-west traffic control and namespace segmentation
- **6 passing tests** covering autoscaling and security configurations

### **COMMIT 6 — Eval suite + episode replay**

- **Comprehensive golden tasks** across FAQ, Order, Tracking, and Lead categories with JSON assertions
- **Episode replay system** for reproducing runs with frozen model/prompt/tool versions
- **LLM judge integration** with automated evaluation and scoring
- **CI/CD workflow integration** with nightly evaluation runs and PR gating
- **Comprehensive evaluation metrics** with pass rates, score distributions, and recommendations
- **17 passing tests** covering evaluation functionality and CI integration

### **COMMIT 7 — Billing E2E proof**

- **Invoice preview service** with real-time usage-based pricing and quota status
- **Quota enforcement middleware** with 429 responses and retry-after headers
- **Webhook aggregation** for real-time usage counter updates
- **E2E verification endpoints** with comprehensive billing cycle testing
- **Production-ready error handling** and validation
- **8 passing tests** covering billing functionality and E2E verification

### **COMMIT 8 — Capacity levers & configs for peak traffic**

- **Environment-specific configurations** with development, staging, and production optimizations
- **Degrade switches** for overload handling (disable verbose critique/debate, shrink context, prefer SLM tiers)
- **Advanced load testing** with K6 and Locust scripts for peak traffic simulation
- **Capacity monitoring service** with real-time metrics and automatic scaling
- **Intelligent alerting** with threshold-based notifications and recommendations
- **19 passing tests** covering capacity management and load testing

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
   - Web Dashboard: http://localhost:5173
   - API Docs: http://localhost:8000/docs
   - WebSocket: ws://localhost:8000/ws/chat
   - Grafana: http://localhost:3000
   - Prometheus: http://localhost:9090
   - Jaeger: http://localhost:16686

### **📚 Documentation**

- **[📖 Complete Documentation](docs/README.md)** - Comprehensive documentation index with organized structure
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
