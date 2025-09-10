# Multi-Tenant AIaaS Platform - Project Structure

## 🏗️ **Project Architecture Overview**

```
multi-ai-agent/
├── 📁 apps/                          # Microservices Architecture
│   ├── 📁 api-gateway/              # Main API Gateway Service
│   │   ├── 📄 main.py               # FastAPI application entry point
│   │   ├── 📄 websocket.py          # WebSocket support
│   │   └── 📁 middleware/           # Middleware components
│   ├── 📁 orchestrator/             # LangGraph Orchestrator Service
│   │   ├── 📄 main.py               # Orchestrator service entry point
│   │   └── 📁 core/                 # Core orchestrator components
│   │       ├── 📄 tools.py          # Agent tools
│   │       └── 📄 resilient_tools.py # Resilient tool adapters
│   ├── 📁 router-service/           # Router v2 with Feature Store
│   │   ├── 📄 main.py               # Router service entry point
│   │   └── 📁 core/                 # Core routing components
│   │       ├── 📄 feature_store.py  # Feature store
│   │       ├── 📄 bandit_policy.py  # Multi-armed bandit policy
│   │       └── 📄 llm_judge.py      # LLM judge
│   ├── 📁 realtime/                 # Realtime Service
│   │   ├── 📄 main.py               # Realtime service entry point
│   │   └── 📁 core/                 # Core realtime components
│   │       ├── 📄 connection_manager.py # WebSocket connection manager
│   │       └── 📄 backpressure_handler.py # Backpressure handling
│   ├── 📁 ingestion/                # Ingestion & Knowledge Service
│   │   ├── 📄 main.py               # Ingestion service entry point
│   │   └── 📁 core/                 # Core ingestion components
│   │       ├── 📄 document_processor.py # Document processing
│   │       ├── 📄 embedding_service.py # Embedding generation
│   │       └── 📄 vector_indexer.py # Vector indexing
│   ├── 📁 analytics-service/        # Analytics Service (CQRS)
│   │   ├── 📄 main.py               # Analytics service entry point
│   │   └── 📁 core/                 # Core analytics components
│   │       ├── 📄 analytics_engine.py # Analytics engine
│   │       └── 📄 dashboard_generator.py # Dashboard generator
│   └── 📁 billing-service/          # Billing Service
│       ├── 📄 main.py               # Billing service entry point
│       └── 📁 core/                 # Core billing components
│           ├── 📄 usage_tracker.py  # Usage tracking
│           └── 📄 billing_engine.py # Billing engine
│
├── 📁 services/                      # Shared Services
│   ├── 📁 agents/                   # Agent Management
│   │   └── 📄 agent_manager.py      # Agent management
│   ├── 📁 tools/                    # Tool Adapters
│   │   ├── 📄 base_adapter.py       # Base tool adapter
│   │   ├── 📄 email_adapter.py      # Email tool adapter
│   │   ├── 📄 payment_adapter.py    # Payment tool adapter
│   │   ├── 📄 crm_adapter.py        # CRM tool adapter
│   │   └── 📄 saga_adapter.py       # Saga pattern adapter
│   └── 📁 memory/                   # Memory & Knowledge Service
│       ├── 📄 knowledge_service.py  # Knowledge service
│       └── 📄 memory_manager.py     # Memory management
│
├── 📁 configs/                      # Configuration Management
│   └── 📁 workflows/               # YAML Workflow Definitions
│       ├── 📄 workflow_registry.yaml        # Central workflow registry
│       ├── 📄 customer_support_workflow.yaml # Main orchestrator workflow
│       ├── 📄 faq_handling.yaml            # FAQ handling workflow
│       ├── 📄 order_management.yaml        # Order management workflow
│       ├── 📄 create_order.yaml            # Order creation workflow
│       ├── 📄 track_order.yaml             # Order tracking workflow
│       ├── 📄 lead_capture.yaml            # Lead capture workflow
│       ├── 📄 complaint_handling.yaml      # Complaint handling workflow
│       ├── 📄 technical_support.yaml       # Technical support workflow
│       ├── 📄 example_workflow.yaml        # Example/tutorial workflow
│       ├── 📄 workflow_loader.py           # YAML workflow loader
│       ├── 📄 demo_workflows.py            # Workflow demonstration
│       └── 📄 README.md                    # Workflow documentation
│
├── 📁 libs/                         # Shared Libraries
│   ├── 📁 adapters/                # Resilient Adapters
│   │   ├── 📄 circuit_breaker.py   # Circuit breaker pattern
│   │   ├── 📄 retry_adapter.py     # Retry strategies
│   │   ├── 📄 saga_pattern.py      # Saga pattern implementation
│   │   └── 📄 resilient_adapter.py # Base resilient adapter
│   ├── 📁 clients/                 # Service Clients
│   │   ├── 📄 database.py          # Database client with RLS
│   │   ├── 📄 rate_limiter.py      # Rate limiter client
│   │   └── 📄 quota_enforcer.py    # Quota enforcement
│   ├── 📁 contracts/               # Pydantic Contracts
│   │   └── 📄 database.py          # Consolidated database models
│   ├── 📁 events/                  # Event System & DLQ
│   │   ├── 📄 __init__.py          # Event system exports
│   │   ├── 📄 nats_client.py       # NATS client with JetStream
│   │   ├── 📄 event_bus.py         # Event bus system
│   │   ├── 📄 event_types.py       # Event type definitions
│   │   ├── 📄 event_handlers.py    # Event handlers
│   │   ├── 📄 dlq_processor.py     # Dead letter queue processor
│   │   └── 📄 event_service.py     # High-level event service
│   ├── 📁 security/                # Security Framework
│   │   ├── 📄 __init__.py          # Security exports
│   │   ├── 📄 auth.py              # Authentication & authorization
│   │   ├── 📄 encryption.py        # Encryption & hashing
│   │   ├── 📄 validation.py        # Input validation
│   │   ├── 📄 middleware.py        # Security middleware
│   │   ├── 📄 threat_detection.py  # Threat detection
│   │   ├── 📄 audit.py             # Security audit
│   │   └── 📄 config.py            # Security configuration
│   └── 📁 workflows/               # Workflow System
│       └── 📄 workflow_loader.py   # YAML workflow loader
│
├── 📁 data-plane/                  # Data Layer
│   └── 📁 migrations/              # Database Migrations
│       ├── 📄 001_multi_tenant_schema.py # Multi-tenant schema
│       ├── 📄 002_consolidated_schema.py # Consolidated schema
│       ├── 📄 003_multi_tenant_complete.py # Complete multi-tenant schema
│       └── 📄 004_events_tables.py # Event system tables
│
├── 📁 web/                         # React Frontend
│   ├── 📄 package.json             # Node.js dependencies
│   ├── 📄 vite.config.ts           # Vite configuration
│   ├── 📄 index.html               # HTML entry point
│   └── 📁 src/                     # React Source Code
│       ├── 📄 main.tsx             # React entry point
│       ├── 📄 App.tsx              # Main App component
│       ├── 📁 components/          # React Components
│       │   ├── 📄 ChatWidget.tsx   # Basic chat widget
│       │   ├── 📄 EnhancedChatWidget.tsx # Enhanced chat widget
│       │   ├── 📄 RegistrationForm.tsx # Registration form
│       │   ├── 📄 PackageSelector.tsx # Package selection
│       │   ├── 📄 Sidebar.tsx      # Navigation sidebar
│       │   └── 📄 SubscriptionDashboard.tsx # Subscription dashboard
│       ├── 📁 pages/               # React Pages
│       │   ├── 📄 AdminDashboard.tsx # Admin dashboard
│       │   ├── 📄 RegisterPage.tsx # Registration page
│       │   └── 📄 SubscriptionPage.tsx # Subscription page
│       └── 📁 types/               # TypeScript Types
│           └── 📄 subscription.ts  # Subscription types
│
├── 📁 tests/                       # Test Suite (Consolidated)
│   ├── 📁 consolidated/            # Consolidated Tests
│   │   ├── 📄 test_router.py       # Router tests
│   │   ├── 📄 test_enhanced_features.py # Enhanced features tests
│   │   └── 📄 test_registration_system.py # Registration tests
│   ├── 📁 unit/                    # Unit Tests
│   │   └── 📄 test_contracts.py    # Contract tests
│   ├── 📁 integration/             # Integration Tests
│   │   ├── 📄 test_orchestrator.py # Orchestrator tests
│   │   ├── 📄 test_resilient_adapters.py # Adapter tests
│   │   └── 📄 test_event_system.py # Event system tests
│   ├── 📁 e2e/                     # End-to-End Tests
│   │   └── 📄 test_agent_workflow.py # Agent workflow tests
│   ├── 📄 run_all_tests.py         # Test runner
│   └── 📄 run_evaluation.py        # Evaluation runner
│
├── 📁 eval/                        # Evaluation Framework
│   ├── 📄 evaluator.py             # Main evaluator
│   ├── 📄 episode_replay.py        # Episode replay system
│   ├── 📄 evaluation_metrics.py    # Evaluation metrics
│   ├── 📁 golden_tasks/            # Golden test tasks
│   │   ├── 📄 customer_support.py  # Customer support tasks
│   │   ├── 📄 faq_handling.py      # FAQ handling tasks
│   │   ├── 📄 order_management.py  # Order management tasks
│   │   └── 📄 lead_capture.py      # Lead capture tasks
│   ├── 📁 judges/                  # Evaluation judges
│   │   ├── 📄 base_judge.py        # Base judge class
│   │   └── 📄 llm_judge.py         # LLM-powered judge
│   └── 📁 reports/                 # Evaluation reports
│       └── 📄 evaluation_report.py # Report generation
│
├── 📁 examples/                    # Example Code
│   └── 📄 resilient_adapters_example.py # Adapter examples
│
├── 📁 infra/                       # Infrastructure Configuration
│   ├── 📁 k8s/                     # Kubernetes Configuration
│   │   ├── 📁 helm/                # Helm Charts
│   │   ├── 📁 autoscaling/         # KEDA/HPA Configuration
│   │   └── 📁 health/              # Health Check Configuration
│   └── 📁 docker/                  # Docker Configuration
│       ├── 📄 compose.dev.yml      # Development compose
│       ├── 📄 Dockerfile.api-gateway # API Gateway Dockerfile
│       └── 📄 Dockerfile.router-service # Router Service Dockerfile
│
├── 📁 observability/               # Observability Stack
│   ├── 📁 otel/                    # OpenTelemetry
│   │   └── 📄 tracing.py           # Distributed tracing
│   ├── 📁 logging/                 # Structured Logging
│   │   └── 📄 logger.py            # Logger configuration
│   ├── 📁 dashboards/              # Grafana Dashboards
│   │   ├── 📄 grafana_dashboards.py # Dashboard generator
│   │   └── 📄 *.json               # Dashboard JSON files
│   ├── 📁 slo/                     # SLO Monitoring
│   │   └── 📄 slo_monitor.py       # SLO monitoring
│   └── 📁 runbooks/                # Operational Runbooks
│       └── 📄 RUNBOOKS.md          # Runbook documentation
│
├── 📁 monitoring/                  # Monitoring Stack
│   └── 📄 prometheus.yml           # Prometheus configuration
│
├── 📁 data-plane/                  # Data Plane
│   ├── 📁 migrations/              # Database Migrations
│   │   ├── 📄 001_multi_tenant_schema.py # Multi-tenant schema
│   │   ├── 📄 002_consolidated_schema.py # Consolidated schema
│   │   ├── 📄 003_multi_tenant_complete.py # Complete multi-tenant schema
│   │   └── 📄 004_events_tables.py # Event system tables
│   ├── 📁 events/                  # Event System
│   │   ├── 📄 nats_event_bus.py    # NATS event bus
│   │   └── 📄 event_handlers.py    # Event handlers
│   └── 📁 storages/                # Storage Layer
│       └── 📄 database.py          # Database client
│
├── 📁 control-plane/              # Control Plane
│   ├── 📁 feature_flags/          # Feature Flag Management
│   │   └── 📄 flag_manager.py     # Feature flag manager
│   ├── 📁 registries/             # Registry Management
│   │   ├── 📄 registry_manager.py # Registry manager
│   │   ├── 📁 agents/             # Agent manifests
│   │   └── 📁 tools/              # Tool manifests
│   └── 📁 configs/                # Configuration Management
│       └── 📄 settings.py         # App settings
│
├── 📁 services/                   # Shared Services
│   └── 📁 memory/                 # Memory & Knowledge Service
│       └── 📄 knowledge_service.py # Knowledge service
│
├── 📁 observability/              # Observability Stack
│   ├── 📁 otel/                   # OpenTelemetry
│   │   └── 📄 tracing.py          # Distributed tracing
│   ├── 📁 logging/                # Structured Logging
│   │   └── 📄 logger.py           # Logger configuration
│   ├── 📁 dashboards/             # Grafana Dashboards
│   │   ├── 📄 grafana_dashboards.py # Dashboard generator
│   │   └── 📄 *.json              # Dashboard JSON files
│   ├── 📁 slo/                    # SLO Monitoring
│   │   └── 📄 slo_monitor.py      # SLO monitoring
│   └── 📁 runbooks/               # Operational Runbooks
│       └── 📄 RUNBOOKS.md         # Runbook documentation
│
├── 📁 .github/                    # GitHub Actions CI/CD
│   ├── 📁 workflows/              # GitHub Workflows
│   │   ├── 📄 ci.yml              # Continuous Integration
│   │   ├── 📄 cd.yml              # Continuous Deployment
│   │   ├── 📄 security.yml        # Security Scanning
│   │   ├── 📄 release.yml         # Release Management
│   │   └── 📄 quality-gate.yml    # Quality Gate
│   └── 📄 dependabot.yml          # Dependency Management
│
├── 📄 docker-compose.yml           # Development Docker Compose
├── 📄 docker-compose.prod.yml      # Production Docker Compose
├── 📄 Dockerfile.api               # API Dockerfile
├── 📄 Dockerfile.web               # Web Dockerfile
├── 📄 Makefile                     # Build and deployment commands
├── 📄 start.sh                     # Quick start script
├── 📄 env.example                  # Environment variables template
├── 📄 README.md                    # Project documentation
├── 📄 COMPREHENSIVE_GUIDE.md       # Comprehensive user guide
├── 📄 PROJECT_CLEANUP_SUMMARY.md   # Cleanup summary
└── 📄 YAML_WORKFLOWS_IMPLEMENTATION.md # YAML workflows guide
```

## 🔄 **Data Flow Architecture**

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

## 🎯 **Key Components**

### **Microservices (apps/)**

- **API Gateway**: Main entry point with WebSocket support
- **Orchestrator**: LangGraph-based workflow execution with resilient tools
- **Router Service**: Router v2 with feature store and bandit policy
- **Realtime Service**: WebSocket service with backpressure handling
- **Ingestion Service**: Document processing and knowledge management
- **Billing Service**: Usage tracking and billing engine

### **YAML Workflows (configs/workflows/)**

- **9 Comprehensive Workflows**: Customer support, FAQ, orders, leads, complaints, technical support
- **Declarative Configuration**: Easy to modify without code changes
- **Workflow Loader**: Python utility for loading and validating workflows

### **Shared Libraries (libs/)**

- **Resilient Adapters**: Circuit breakers, retries, timeouts, bulkheads, saga patterns
- **Event System**: NATS-based event bus with DLQ handling and event sourcing
- **Security Framework**: Authentication, encryption, validation, threat detection
- **Contracts**: Pydantic models for service boundaries
- **Workflow System**: YAML workflow loader with fragments and overlays

### **Data Layer (data-plane/)**

- **Database Migrations**: Alembic migrations for schema management
- **Multi-Tenant Schema**: Row-level security implementation
- **Consolidated Models**: Unified database schema

### **Frontend (web/)**

- **React + TypeScript**: Modern frontend framework
- **Tailwind CSS**: Utility-first styling
- **Component Library**: Reusable UI components
- **Real-time Chat**: WebSocket integration

### **Testing (tests/)**

- **Consolidated Structure**: All tests in organized hierarchy
- **Unit Tests**: Individual component testing
- **Integration Tests**: Service integration testing
- **E2E Tests**: End-to-end workflow testing
- **Evaluation Framework**: AI system evaluation

## 🚀 **Deployment Architecture**

### **Development**

```bash
make dev          # Start development environment
make up           # Start all services with Docker
make test         # Run test suite
```

### **Production**

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### **Kubernetes**

```bash
kubectl apply -f infra/k8s/
```

## 📊 **Monitoring Stack**

- **Prometheus**: Metrics collection
- **Grafana**: Visualization dashboards
- **OpenTelemetry**: Distributed tracing
- **Structured Logging**: JSON-formatted logs

## 🔒 **Security Features**

- **Multi-Tenant Isolation**: Row-Level Security (RLS) with tenant context
- **Authentication & Authorization**: JWT tokens, API keys, RBAC
- **Encryption**: Data at rest and in transit with Fernet encryption
- **Input Validation**: SQL injection, XSS prevention, data sanitization
- **Threat Detection**: Real-time threat analysis and anomaly detection
- **Rate Limiting**: Per-tenant rate limits with token bucket algorithm
- **Security Middleware**: CORS, security headers, tenant isolation
- **Audit Logging**: Comprehensive security event tracking
- **Container Security**: Vulnerability scanning with Trivy and Docker Scout

## 🎉 **Summary**

This is a **production-grade, multi-tenant AIaaS platform** with:

- ✅ **Clean Architecture**: Microservices with clear separation of concerns
- ✅ **YAML Workflows**: Declarative workflow definitions with fragments and overlays
- ✅ **Resilient Design**: Circuit breakers, retries, timeouts, saga patterns
- ✅ **Event System**: NATS-based event bus with DLQ handling
- ✅ **Security Hardening**: Comprehensive security framework with threat detection
- ✅ **Router v2**: Feature store with multi-armed bandit policy
- ✅ **Observability**: Prometheus metrics, Grafana dashboards, runbooks
- ✅ **Evaluation Suite**: Episode replay and LLM-based evaluation
- ✅ **CI/CD Pipeline**: Complete automation with security scanning
- ✅ **Comprehensive Testing**: Unit, integration, E2E, and performance tests
- ✅ **Production Ready**: Docker, Kubernetes, monitoring, autoscaling
- ✅ **Well Documented**: Comprehensive guides and examples

The project structure is now **production-ready, secure, and fully automated** with enterprise-grade features!
