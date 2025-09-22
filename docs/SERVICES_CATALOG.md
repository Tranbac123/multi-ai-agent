# Multi-AI-Agent Platform - Services Catalog

## 📋 **Complete Service Directory**

This document provides a comprehensive overview of all services in the Multi-AI-Agent Platform, including their purposes, endpoints, ports, and key features.

---

## 🏗️ **Core Platform Services**

### **1. API Gateway**

- **Location**: `apps/api-gateway/`
- **Port**: `8000`
- **Purpose**: Main entry point with authentication, rate limiting, and request routing
- **Key Features**:
  - JWT authentication and validation
  - Rate limiting and quota enforcement
  - Multi-tenant context injection
  - Request/response validation
  - OpenAPI documentation
  - WebSocket upgrade handling
- **Dependencies**: PostgreSQL, Redis, NATS
- **Endpoints**:
  - `GET /health` - Health check
  - `GET /docs` - OpenAPI documentation
  - `POST /auth/*` - Authentication endpoints
  - `WS /ws/{tenant_id}` - WebSocket connections

### **2. Orchestrator Service**

- **Location**: `apps/orchestrator/`
- **Port**: `8081`
- **Purpose**: LangGraph-based workflow execution with resilient tool adapters
- **Key Features**:
  - FSM/LangGraph workflow orchestration
  - Saga compensation patterns
  - Loop safety with MAX_STEPS enforcement
  - Resilient tool adapters with retry/circuit breaker
  - Event sourcing and state management
  - YAML workflow definitions
- **Dependencies**: PostgreSQL, Redis, NATS, LLM APIs
- **Endpoints**:
  - `POST /workflows/execute` - Execute workflows
  - `GET /workflows/{id}/status` - Get workflow status
  - `GET /workflows/{id}/progress` - Get execution progress

### **3. Router Service v2**

- **Location**: `apps/router-service/`
- **Port**: `8002`
- **Purpose**: Intelligent request routing with feature extraction and bandit policy
- **Key Features**:
  - Difficulty → tier classification
  - Feature extraction and feature store
  - Calibrated classifier with confidence scoring
  - Bandit policy for exploration/exploitation
  - Early exit escalation
  - Canary deployment support
  - Token counting and JSON schema validation
- **Dependencies**: Redis, ML models
- **Endpoints**:
  - `POST /route` - Route requests to optimal tier
  - `GET /features/{tenant_id}` - Get feature analysis
  - `GET /metrics` - Router performance metrics

### **4. Realtime Service**

- **Location**: `apps/realtime/`
- **Port**: `8000` (WebSocket), `8001` (HTTP)
- **Purpose**: Production-grade WebSocket service with advanced backpressure management and Redis persistence
- **Key Features**:
  - **Advanced Backpressure Management**: Per-connection Redis outbound queues with sticky sessions
  - **Intelligent Message Dropping**: Sophisticated policies for intermediate vs final messages
  - **Sequence Tracking**: Message acknowledgments and ordered delivery guarantees
  - **Slow Client Detection**: Adaptive handling for clients with poor connectivity
  - **Resume on Reconnect**: Persistent message queues survive connection drops
  - **Multi-tenant Isolation**: Complete tenant-level message and connection isolation
  - **Production Monitoring**: Comprehensive metrics, health checks, and connection statistics
  - **Priority Queuing**: Message prioritization with TTL and overflow handling
- **Dependencies**: Redis, NATS
- **Endpoints**:
  - `WS /ws/{tenant_id}` - WebSocket connections
  - `GET /connections/stats` - Connection statistics
  - `POST /broadcast/{tenant_id}` - Broadcast messages

### **5. Analytics Service**

- **Location**: `apps/analytics-service/`
- **Port**: `8004`
- **Purpose**: Read-only CQRS analytics, KPIs, and reporting
- **Key Features**:
  - CQRS read-only analytics
  - Real-time KPI calculation
  - Dashboard generation
  - Regional analytics
  - Tenant usage reporting
  - Performance metrics aggregation
- **Dependencies**: PostgreSQL, Redis
- **Endpoints**:
  - `GET /analytics/{tenant_id}/kpis` - Get KPI metrics
  - `GET /analytics/{tenant_id}/usage` - Usage analytics
  - `GET /dashboards/{tenant_id}` - Generate dashboards

### **6. Billing Service**

- **Location**: `apps/billing-service/`
- **Port**: `8006`
- **Purpose**: Usage tracking, billing engine, and quota enforcement
- **Key Features**:
  - Real-time usage tracking
  - Invoice generation and processing
  - Cost drift detection (CostGuard)
  - Budget management with alerts
  - Payment processing integration
  - Webhook aggregation
- **Dependencies**: PostgreSQL, Redis, Payment APIs
- **Endpoints**:
  - `GET /billing/{tenant_id}/usage` - Current usage
  - `GET /billing/{tenant_id}/invoices` - Invoice history
  - `POST /billing/{tenant_id}/budget` - Set budget limits

### **7. Ingestion Service**

- **Location**: `apps/ingestion/`
- **Port**: `8004`
- **Purpose**: Document processing, embedding, and knowledge management
- **Key Features**:
  - Document chunking and processing
  - Text embedding and vector indexing
  - PII detection and redaction
  - Sensitivity tagging
  - Permissioned retrieval
  - RAG metadata management
- **Dependencies**: Vector DB, LLM APIs, PostgreSQL
- **Endpoints**:
  - `POST /documents/upload` - Upload documents
  - `GET /documents/{id}/chunks` - Get document chunks
  - `POST /search/semantic` - Semantic search

### **8. Chat Adapters Service**

- **Location**: `apps/chat-adapters/`
- **Port**: `8006` (configurable via `CHAT_ADAPTER_PORT`)
- **Purpose**: Multi-channel chat integration (Facebook, Zalo, TikTok)
- **Key Features**:
  - Facebook Messenger integration
  - Zalo chat adapter
  - TikTok chat adapter
  - Unified message format
  - Webhook handling
  - Multi-channel broadcasting
- **Dependencies**: External Chat APIs
- **Endpoints**:
  - `POST /facebook/webhook` - Facebook webhook
  - `POST /zalo/webhook` - Zalo webhook
  - `POST /tiktok/webhook` - TikTok webhook

### **9. Tenant Service**

- **Location**: `apps/tenant-service/`
- **Port**: `8006`
- **Purpose**: Self-serve tenant onboarding and plan management
- **Key Features**:
  - Tenant registration and onboarding
  - Plan upgrade/downgrade workflows
  - Webhook management
  - Lifecycle hooks
  - Configuration management
  - Self-service portal
- **Dependencies**: PostgreSQL, Redis
- **Endpoints**:
  - `POST /tenants/register` - Register new tenant
  - `PUT /tenants/{id}/plan` - Update plan
  - `GET /tenants/{id}/status` - Tenant status

### **10. Admin Portal**

- **Location**: `apps/admin-portal/`
- **Port**: `8007`
- **Purpose**: Tenant administration and system management
- **Key Features**:
  - Tenant management dashboard
  - Plan configuration
  - System monitoring
  - Usage analytics
  - Administrative operations
  - Audit logs
- **Dependencies**: PostgreSQL, Redis
- **Endpoints**:
  - `GET /admin/dashboard` - Admin dashboard
  - `GET /admin/tenants` - Tenant list
  - `POST /admin/tenants/{id}/actions` - Admin actions

### **11. Eval Service**

- **Location**: `apps/eval-service/`
- **Port**: Not explicitly configured
- **Purpose**: LLM evaluation, golden tasks, and episode replay
- **Key Features**:
  - Golden task evaluation
  - Episode replay functionality
  - LLM judge implementation
  - Performance benchmarking
  - Quality assessment
  - A/B testing support
- **Dependencies**: LLM APIs, PostgreSQL
- **Endpoints**:
  - `POST /eval/tasks/run` - Run evaluation tasks
  - `GET /eval/results/{id}` - Get evaluation results
  - `POST /eval/replay/{episode_id}` - Replay episodes

### **12. Tool Service**

- **Location**: `apps/tool-service/`
- **Port**: Not explicitly configured
- **Purpose**: Tool execution with resilience patterns
- **Key Features**:
  - Tool adapter management
  - Resilience patterns (retry, circuit breaker)
  - Tool execution monitoring
  - Error handling and recovery
  - Tool registry
- **Dependencies**: Various external APIs
- **Endpoints**:
  - `POST /tools/{name}/execute` - Execute tools
  - `GET /tools/registry` - Tool registry
  - `GET /tools/{name}/status` - Tool status

### **13. Capacity Monitor**

- **Location**: `apps/capacity-monitor/`
- **Port**: `8004`
- **Purpose**: Capacity monitoring and autoscaling decisions
- **Key Features**:
  - Resource utilization monitoring
  - Scaling recommendations
  - Performance tracking
  - Capacity planning
  - Alert generation
- **Dependencies**: Kubernetes APIs, Metrics APIs
- **Endpoints**:
  - `GET /capacity/metrics` - Capacity metrics
  - `GET /capacity/recommendations` - Scaling recommendations
  - `POST /capacity/alerts` - Alert management

---

## 🗄️ **Infrastructure Services**

### **14. PostgreSQL Database**

- **Port**: `5432`
- **Purpose**: Primary data store with multi-tenant RLS
- **Features**: Row Level Security, ACID compliance, JSON support

### **15. Redis Cache**

- **Port**: `6379`
- **Purpose**: Caching, session storage, and pub/sub
- **Features**: In-memory storage, pub/sub, clustering

### **16. NATS JetStream**

- **Port**: `4222` (client), `8222` (management)
- **Purpose**: Event streaming and message queuing
- **Features**: Event sourcing, guaranteed delivery, clustering

### **17. Vector Database**

- **Purpose**: Embeddings and semantic search
- **Features**: Vector similarity, tenant isolation, backups

---

## 🌐 **External Integrations**

### **18. LLM Providers**

- **OpenAI API**: GPT models
- **Anthropic API**: Claude models
- **Purpose**: AI inference and completion

### **19. Payment Processors**

- **Stripe API**: Payment processing
- **Purpose**: Billing and subscription management

### **20. Observability Stack**

- **Prometheus**: Metrics collection
- **Grafana**: Dashboards and visualization
- **Jaeger**: Distributed tracing
- **OpenTelemetry**: Observability framework

---

## 📊 **Service Communication Map**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   API Gateway   │    │  Orchestrator   │
│   (React)       │◄──►│   (Port 8000)   │◄──►│   (Port 8081)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       ▼                       ▼
         ▼             ┌─────────────────┐    ┌─────────────────┐
┌─────────────────┐    │  Router Service │    │  Realtime Svc   │
│   Realtime      │    │   (Port 8002)   │    │  (Port 8000/1)  │
│   (WebSocket)   │    └─────────────────┘    └─────────────────┘
└─────────────────┘             │                       │
         │                      ▼                       ▼
         ▼             ┌─────────────────┐    ┌─────────────────┐
┌─────────────────┐    │  Analytics Svc  │    │  Billing Svc    │
│   Chat Adapters │    │   (Port 8004)   │    │   (Port 8006)   │
│   (Port 8006)   │    └─────────────────┘    └─────────────────┘
└─────────────────┘             │                       │
         │                      ▼                       ▼
         ▼             ┌─────────────────┐    ┌─────────────────┐
┌─────────────────┐    │  Ingestion Svc  │    │  Tenant Svc     │
│   Admin Portal  │    │   (Port 8004)   │    │   (Port 8006)   │
│   (Port 8007)   │    └─────────────────┘    └─────────────────┘
└─────────────────┘
```

---

## 🚀 **Quick Reference Commands**

### **Start All Services**

```bash
# Development
docker-compose -f docker-compose.dev.yml up

# Production
docker-compose -f docker-compose.prod.yml up
```

### **Service Health Checks**

```bash
# API Gateway
curl http://localhost:8000/health

# Analytics Service
curl http://localhost:8004/health

# Billing Service
curl http://localhost:8006/health
```

### **View Service Logs**

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api-gateway
```

---

## 📚 **Additional Documentation**

- **[System Overview](architecture/SYSTEM_OVERVIEW.md)** - Detailed architecture
- **[Features Documentation](FEATURES.md)** - Complete feature list
- **[API Contracts](development/CONTRACTS.md)** - API specifications
- **[Deployment Guide](DEPLOYMENT_PRODUCTION_GUIDE.md)** - Production deployment
- **[Testing Overview](testing/TESTING_OVERVIEW.md)** - Testing framework

---

## 🏷️ **Service Tags & Categories**

### **By Function**

- **Core**: API Gateway, Orchestrator, Router, Realtime
- **Data**: Analytics, Billing, Ingestion
- **Integration**: Chat Adapters, Tool Service
- **Management**: Tenant Service, Admin Portal, Capacity Monitor
- **Quality**: Eval Service

### **By Scaling Strategy**

- **HPA (CPU/Memory)**: API Gateway, Router, Realtime
- **KEDA (Queue-based)**: Orchestrator, Ingestion
- **Static**: Control Plane, Data Plane
- **Read Replicas**: Analytics

### **By Dependencies**

- **Database Heavy**: Analytics, Billing, Tenant Service
- **LLM Dependent**: Orchestrator, Router, Eval Service
- **External APIs**: Chat Adapters, Tool Service, Payment
- **Real-time**: Realtime Service, WebSocket connections

---

_Last Updated: $(date)_
_Total Services: 20+ (13 Core Application Services + 7 Infrastructure Services)_
