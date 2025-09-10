# Multi-Tenant AIaaS Platform

A production-grade, multi-tenant AI-as-a-Service platform providing intelligent customer support, workflow orchestration, and real-time analytics across multiple channels.

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

## 🚀 Recent Production Hardening (9 Commits)

The platform has been significantly enhanced with production-grade features:

### **Router v2 Hardening**

- Feature extraction (token_count, json_schema_strictness, domain_flags, novelty_score)
- Calibrated classifier with temperature scaling and deterministic fallback
- Bandit policy minimizing E[cost + λ·error]
- Early-exit logic and canary deployments with auto-rollback
- Metrics: `router_decision_latency_ms`, `router_misroute_rate`, `tier_distribution`

### **Analytics & Dashboards**

- Read-only CQRS API for KPIs per tenant
- Grafana dashboard JSON configurations
- Warehouse integration (ClickHouse/BigQuery) or Postgres read-replica

### **Reliability & Resilience**

- Tool adapters with timeouts, retries (exponential backoff + jitter)
- Circuit-breaker, bulkhead, idempotency patterns
- Write-ahead events: tool.call.requested/succeeded/failed
- Saga compensation for side-effects

### **Realtime & Backpressure**

- Dedicated ASGI WS app with sticky sessions
- Redis session store and outbound Redis queue
- Backpressure policies with metrics: `ws_active_connections`, `ws_backpressure_drops`

### **Kubernetes & Security**

- KEDA autoscaling for orchestrator/ingestion (NATS queue depth)
- HPA for router/realtime (CPU/memory)
- Readiness/liveness probes for all services
- NetworkPolicy for east-west traffic control

### **Evaluation & Testing**

- Golden tasks per use-case (FAQ, Order, Lead) with JSON assertions
- Episode replay system (EXACT, PARAMETRIC, STRESS modes)
- LLM-judge rubric with CI gate (fails if score < threshold)
- Comprehensive test suite: unit, contract, integration, E2E, chaos

### **Billing & Usage**

- Webhook aggregation of usage_counters
- Invoice preview endpoint with cost calculations
- Plan enforcement in API Gateway (HTTP 429 when over quota)
- Payment processing with Stripe/Braintree support

### **Dependency & Security Hygiene**

- `constraints.txt` for reproducible builds
- Security tools: `trivy`, `safety`, `bandit` in CI
- Dependency deduplication and validation
- No plaintext secrets with `.env.example` only

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
