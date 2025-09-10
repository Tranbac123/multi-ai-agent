# Multi-Tenant AIaaS Platform

A production-grade, multi-tenant AI-as-a-Service platform providing intelligent customer support, workflow orchestration, and real-time analytics across multiple channels.

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   API Gateway   │    │  Orchestrator   │
│   (React)       │◄──►│   (FastAPI)     │◄──►│   (LangGraph)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │  Router Service │    │  YAML Workflows │
                       │  (Intelligent)  │    │  (Declarative)  │
                       └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Event Bus     │    │   Database      │
                       │   (NATS)        │    │  (PostgreSQL)   │
                       └─────────────────┘    └─────────────────┘
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

- **Backend**: Python 3.11 + FastAPI + SQLAlchemy 2.0 (async)
- **AI**: OpenAI API + LangGraph workflows & agents
- **Database**: PostgreSQL 16 + Redis 7 + NATS JetStream
- **Frontend**: React + TypeScript + Tailwind CSS
- **Deployment**: Docker + Kubernetes + Helm
- **Monitoring**: OpenTelemetry + Prometheus + Grafana

## RACI (Responsibility Assignment)

### **Control Plane** (Platform Team)
**Responsible for**: Platform infrastructure, configuration, and governance

- **Feature Flags**: Runtime feature toggling and A/B testing
- **Registries**: Agent/tool manifest management and versioning  
- **Configs**: Environment-specific configuration and secrets
- **Infrastructure**: Kubernetes, monitoring, security policies
- **Data Plane**: Database migrations, event schemas, storage policies

### **Runtime** (Service Teams)
**Responsible for**: Service development, deployment, and operations

- **API Gateway**: Authentication, rate limiting, request routing
- **Orchestrator**: Workflow execution and tool coordination
- **Router Service**: Intelligent routing and cost optimization
- **Realtime Service**: WebSocket management and backpressure
- **Ingestion Service**: Document processing and knowledge indexing
- **Analytics Service**: Metrics aggregation and reporting
- **Billing Service**: Usage metering and invoice generation

### **Observability** (Shared Responsibility)
**Platform Team**: Infrastructure, dashboards, alerting rules
**Service Teams**: Service-specific metrics, health checks, runbooks

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
