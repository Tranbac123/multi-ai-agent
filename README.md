# Multi-Tenant AIaaS Platform

A production-grade, multi-tenant AI-as-a-Service platform providing intelligent customer support, workflow orchestration, and real-time analytics across multiple channels.

## 📚 **Documentation**

Comprehensive documentation is available in the [`docs/`](docs/) directory:

- **[Services Catalog](docs/SERVICES_CATALOG.md)** - Complete directory of all platform services
- **[System Overview](docs/SYSTEM_OVERVIEW.md)** - Production-grade multi-agent platform overview
- **[Features Documentation](docs/FEATURES.md)** - Complete platform features and capabilities
- **[Visual Architecture](docs/VISUAL_ARCHITECTURE.md)** - Architecture diagrams and illustrations
- **[Runtime Topology](docs/RUNTIME_TOPOLOGY.md)** - Ingress, autoscaling, DLQ, retries, Saga patterns
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
         │               ┌───────┴───────┐               │                       │
         │               │  SYNC PATH    │               │                       │
         │               │ (Request/     │               │                       │
         │               │  Response)    │               │                       │
         │               └───────────────┘               │                       │
         ▼                       ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Realtime      │    │   Ingestion     │    │   Analytics     │    │   Billing       │
│   Gateway       │    │   Service       │    │   Service       │    │   Service       │
│   (WebSocket)   │    │   (Document)    │    │   (CQRS)        │    │   (Sync+Async)  │
│  [Side Channel] │    │   [Async ETL]   │    │   [Async]       │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │                       │
         │                       │               ┌───────┴───────┐               │
         │                       │               │  ASYNC PATH   │               │
         │                       │               │ (Event-Driven)│               │
         │                       │               └───────────────┘               │
         ▼                       ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────-┐
│                               INFRASTRUCTURE LAYER                                   │
├─────────────────┬─────────────────┬─────────────────┬─────────────────┬─────────────-┤
│   Control       │   Event Bus     │   Database      │   Vector DB     │ Observability│
│   Plane         │   (NATS)        │  (PostgreSQL)   │  (Embeddings)   │   Stack      │
│                 │                 │                 │                 │              │
│ • Config Svc    │ • JetStream     │ • RLS Isolation │ • Semantic      │ • OTel       │
│ • Policy Mgmt   │ • DLQ Pattern   │ • Multi-tenant  │   Search        │ • Prometheus │
│ • Feature Flags │ • Saga Pattern  │ • ACID          │ • RAG Store     │ • Grafana    │
│ • Registry      │ • Pub/Sub       │ • Migrations    │ • Similarity    │ • Tracing    │
│ • Usage Meter   │ • Retries       │ • Backups       │ • Chunking      │ • Metrics    │
│ • Audit Log     │ • Dead Letters  │ • Replication   │ • Indexing      │ • Logs       │
│ • Notifications │ • Ordering      │ • Performance   │ • Retrieval     │ • Alerts     │
└─────────────────┴─────────────────┴─────────────────┴─────────────────┴────────────-─┘

📊 DATA FLOW PATTERNS:
┌─ SYNC: User Request → API Gateway → Router → Model Gateway → Response
├─ ASYNC: Events → NATS → Processing Services → State Updates
├─ REALTIME: WebSocket → Realtime Gateway → Live Updates
└─ BILLING: Sync (quota checks) + Async (usage aggregation)

🏗️ SERVICE ARCHITECTURE:
• All Data Plane services persist via PostgreSQL (RLS)
• All services export telemetry to Observability Stack
• All services consume config/flags from Control Plane
• Event-driven services use NATS for decoupling
• Vector DB provides semantic search capabilities
```

## Core Services

### **Data Plane Services**

- **API Gateway** (Port 8000): Main entry point with authentication, rate limiting, and chat endpoints
- **Model Gateway** (Port 8080): AI model routing and provider management
- **Retrieval Service** (Port 8081): Document retrieval and RAG capabilities
- **Tools Service** (Port 8082): External tools integration with FIRECRAWL web search
- **Router Service** (Port 8083): Intelligent request routing and load balancing
- **Realtime Gateway** (Port 8084): WebSocket connections and real-time communication
- **Chat Adapters Service**: Multi-channel chat integration (Facebook, Zalo, TikTok, WhatsApp, Telegram)
- **Semantic Cache Service**: Intelligent response caching and optimization
- **Migration Runner**: Database schema management and migrations
- **Event Relay Service**: Event processing and webhook delivery

### **Control Plane Services**

- **Config Service** (Port 8090): Configuration management and environment settings
- **Policy Adapter** (Port 8091): Policy enforcement and compliance management
- **Feature Flags Service** (Port 8092): Runtime feature toggles and A/B testing
- **Registry Service** (Port 8094): Service discovery and manifest management
- **Usage Metering** (Port 8095): Usage tracking and billing calculations
- **Audit Log** (Port 8096): Comprehensive audit logging and compliance
- **Notification Service** (Port 8097): Multi-channel notifications and alerts

### **Frontend Services**

- **AI Chatbot UI** (Port 3001): Main chatbot interface with real-time web search
- **Web Frontend** (Port 3000): Web application and user dashboard
- **Admin Portal** (Port 8099): Administrative interface and system management

## 🌟 Key Features

### **🔍 Real-Time Web Search**

- **FIRECRAWL Integration**: Live internet search capabilities
- **Intelligent Detection**: Automatic web search trigger detection
- **Multi-Source Results**: Combines top search results with AI enhancement
- **Citation Support**: Proper attribution and source tracking

### **🏠 Local Development**

- **No Docker Option**: Run all services natively for faster development
- **Auto-Setup Scripts**: One-command local environment setup
- **Service Management**: Start/stop individual or all services
- **Live Reloading**: Instant code changes without container rebuilds

### **🔒 Security & Privacy**

- **API Key Protection**: Secure environment variable management
- **Multi-tenant Isolation**: Row-level security and tenant separation
- **PII Detection**: Automatic sensitive data identification and redaction
- **Audit Logging**: Comprehensive activity tracking and compliance

### **⚡ Performance & Reliability**

- **Circuit Breakers**: Automatic failure detection and recovery
- **Load Balancing**: Intelligent request routing and distribution
- **Caching**: Semantic response caching for improved performance
- **Health Monitoring**: Real-time service health checks and alerts

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

## 🚀 Production-Ready Platform

The platform is production-ready with enterprise-grade features for stability, accuracy, safety, and reliability:

### **Core Capabilities**

- **Loop Safety**: MAX_STEPS enforcement, progress tracking, and oscillation detection
- **Strict Contracts**: Pydantic validation with boundary enforcement and PII redaction
- **Router Intelligence**: Feature extraction, classification, and cost optimization
- **Tool Reliability**: Circuit breakers, retries, and saga orchestration
- **Realtime Backpressure**: WebSocket management with graceful degradation
- **Multi-tenant Isolation**: RLS, rate limiting, and fair scheduling
- **Data Protection**: RAG security, PII detection, and field-level encryption
- **Observability**: OpenTelemetry, SLOs, and comprehensive monitoring
- **Evaluation**: LLM judge evaluation and episode replay system
- **Performance Gates**: Cost ceilings and performance validation

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

### **🐳 Docker Setup (Recommended)**

```bash
# Clone and start with Docker
git clone <repo-url>
cd multi-ai-agent
./scripts/setup-env.sh
docker-compose -f docker-compose.local.yml up -d
```

### **🏠 Local Development (No Docker)**

```bash
# Setup local development environment
git clone <repo-url>
cd multi-ai-agent
./scripts/setup-local-dev.sh
./scripts/start-local-dev.sh
```

### **🌐 Service URLs**

**Frontend Services:**

- AI Chatbot: http://localhost:3001
- Web Frontend: http://localhost:3000
- Admin Portal: http://localhost:8099

**Backend Services:**

- API Gateway: http://localhost:8000
- Model Gateway: http://localhost:8080
- Retrieval Service: http://localhost:8081
- Tools Service: http://localhost:8082
- Router Service: http://localhost:8083
- Realtime Gateway: http://localhost:8084

**Control Plane:**

- Config Service: http://localhost:8090
- Policy Adapter: http://localhost:8091
- Feature Flags: http://localhost:8092
- Registry Service: http://localhost:8094
- Usage Metering: http://localhost:8095
- Audit Log: http://localhost:8096
- Notifications: http://localhost:8097

**Documentation:**

- API Docs: http://localhost:8000/docs
- Local Development Guide: [LOCAL_DEVELOPMENT_GUIDE.md](LOCAL_DEVELOPMENT_GUIDE.md)

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

### **Main API Gateway (Port 8000)**

- **Chat**: `/ask` - Main chatbot endpoint with web search
- **Chat API**: `/v1/chat` - Standard chat completion API
- **Web Scraping**: `/web-scrape` - FIRECRAWL web scraping
- **Health**: `/healthz` - Service health check
- **Docs**: `/docs` - Interactive API documentation

### **Service-Specific Endpoints**

- **Model Gateway**: `/v1/chat` - AI model routing and provider management
- **Retrieval Service**: `/search` - Document retrieval and RAG
- **Tools Service**: `/v1/tools/exec` - External tools execution
- **Router Service**: `/route` - Intelligent request routing
- **Config Service**: `/config` - Configuration management
- **Usage Metering**: `/usage` - Usage tracking and billing
- **Chat Adapters**: `/webhook/*` - Multi-channel chat integration

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
