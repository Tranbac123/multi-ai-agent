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

- **Feature Flags**: Runtime feature toggling and A/B testing
- **Registries**: Agent/tool manifest management and versioning
- **Configs**: Environment-specific configuration and secrets

### **Runtime** (Service Teams)

- **API Gateway**: Authentication, rate limiting, request routing
- **Orchestrator**: Workflow execution and tool coordination
- **Router Service**: Intelligent routing and cost optimization
- **Realtime Service**: WebSocket management and backpressure
- **Ingestion Service**: Document processing and knowledge indexing
- **Analytics Service**: Metrics aggregation and reporting
- **Billing Service**: Usage metering and invoice generation

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
   - Web Dashboard: http://localhost:5173
   - API Docs: http://localhost:8000/docs
   - WebSocket: ws://localhost:8000/ws/chat
   - Grafana: http://localhost:3000
   - Prometheus: http://localhost:9090

## Development

```bash
make dev          # Start development environment
make test         # Run test suite
make e2e          # Run end-to-end tests
make eval         # Run evaluation suite
make security     # Run security scans
make format       # Format code
make lint         # Lint code
make type-check   # Type checking
```

## API Endpoints

- **Chat**: `/api/v1/chat/*` - Customer chat interface
- **Router**: `/api/v1/router/decide` - Intelligent routing
- **Orchestrator**: `/api/v1/orchestrator/*` - Workflow execution
- **Analytics**: `/api/v1/analytics/*` - Metrics and reporting
- **Billing**: `/api/v1/billing/*` - Usage and billing
- **Ingestion**: `/api/v1/ingestion/*` - Document processing

## Environment Variables

See `.env.example` for required configuration including:

- Database URLs (PostgreSQL, Redis, NATS)
- OpenAI API key
- JWT secrets and encryption keys
- Monitoring endpoints (Prometheus, Grafana)
- Feature flag configuration
