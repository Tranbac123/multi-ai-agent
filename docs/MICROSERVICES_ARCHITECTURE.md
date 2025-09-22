# Microservices Architecture Guide

## Overview

This repository has been refactored into a microservices-standard structure where each service is independently buildable, testable, deployable, and observable.

## Repository Structure

```
├── apps/                           # 🏗️ Application Services
│   ├── api-gateway/               # Main entry point & routing
│   ├── analytics-service/         # CQRS analytics & reporting
│   ├── orchestrator/              # LangGraph workflow execution
│   ├── router-service/            # Intelligent request routing
│   ├── realtime/                  # WebSocket & real-time features
│   ├── ingestion/                 # Document processing
│   ├── billing-service/           # Usage tracking & billing
│   ├── tenant-service/            # Multi-tenant management
│   ├── chat-adapters/             # Multi-channel chat integration
│   ├── tool-service/              # Tool execution management
│   ├── eval-service/              # Model evaluation & QA
│   ├── capacity-monitor/          # Resource monitoring
│   ├── admin-portal/              # Backend admin interface
│   └── web-frontend/              # Frontend user interface
│
├── contracts/                      # 📋 Shared API Contracts
│   └── shared.yaml                # Common schemas & types
│
├── platform/                      # 🛠️ Platform Shared Assets
│   ├── ci-templates/              # Reusable GitHub Actions
│   ├── helm-lib/                  # Shared Helm charts
│   ├── opa-policies/              # Policy as Code
│   ├── integration-tests/         # Cross-service integration tests
│   └── load_tests/                # Performance & load testing
│
├── infra/                         # 🏢 Infrastructure as Code
│   ├── database/                  # Shared database schemas
│   ├── k8s/                       # Kubernetes manifests
│   └── dockerfiles/               # Legacy dockerfiles (deprecated)
│
├── libs/                          # 📚 Shared Libraries
│   ├── clients/                   # Service clients & adapters
│   ├── contracts/                 # Contract validation
│   ├── resilience/                # Resilience patterns
│   ├── router/                    # Routing logic
│   └── utils/                     # Common utilities
│
├── docs/                          # 📖 Documentation
├── scripts/                       # 🔧 Utility scripts
└── .github/workflows/             # ⚙️ CI/CD Pipelines
```

## Service Structure Standard

Each service follows this standardized structure:

```
apps/<service-name>/
├── src/                           # 🐍 Source Code
│   ├── main.py                   # Application entry point
│   ├── core/                     # Core business logic
│   ├── api/                      # API routes & handlers
│   ├── models/                   # Data models
│   └── services/                 # Business services
├── db/                           # 🗄️ Database
│   ├── migrations/               # Database migrations
│   └── seeds/                    # Test data
├── contracts/                    # 📋 API Contracts
│   └── openapi.yaml             # OpenAPI specification
├── deploy/                       # 🚀 Deployment
│   ├── base/                     # Base Kustomize manifests
│   ├── overlays/                 # Environment-specific overlays
│   │   ├── dev/
│   │   ├── staging/
│   │   └── prod/
│   └── Makefile                  # Deployment commands
├── observability/                # 📊 Monitoring & Observability
│   ├── dashboards/               # Grafana dashboards
│   ├── SLO.md                   # Service Level Objectives
│   └── runbook.md               # Operational runbook
├── tests/                        # 🧪 Tests
│   ├── unit/                     # Unit tests
│   ├── integration/              # Integration tests
│   └── fixtures/                 # Test fixtures
├── .github/                      # ⚙️ CI/CD
│   └── workflows/
│       └── ci.yaml              # Service-specific CI workflow
├── Dockerfile                    # 🐳 Container definition
├── Makefile                      # 📋 Service commands
├── README.md                     # 📖 Service documentation
├── requirements.txt              # 📦 Python dependencies
└── requirements-dev.txt          # 🔧 Development dependencies
```

## Service Standards

### Build & Test Commands

Each service implements these standardized `make` targets:

```bash
make help        # Show available commands
make dev         # Set up development environment
make test        # Run all tests with coverage
make lint        # Run linting and formatting
make type-check  # Run type checking
make migrate     # Run database migrations
make run         # Run service locally
make build       # Build Docker image
make clean       # Clean build artifacts
```

### API Contracts

- Each service defines its API in `contracts/openapi.yaml`
- Shared schemas are in `contracts/shared.yaml`
- Contract validation is enforced in CI/CD

### Observability

- **SLO**: Each service defines SLIs/SLOs in `observability/SLO.md`
- **Monitoring**: Grafana dashboards in `observability/dashboards/`
- **Runbooks**: Operational procedures in `observability/runbook.md`

### Deployment

- **Kustomize**: Environment-specific configurations
- **Helm**: Optional library charts in `platform/helm-lib/`
- **CI/CD**: Path-filtered workflows for efficient builds

## CI/CD Pipeline

### Path-Filtered Builds

Only services affected by changes are built and tested:

```yaml
# .github/workflows/platform-ci.yaml
on:
  push:
    paths:
      - "apps/api-gateway/**" # Triggers API Gateway CI
      - "apps/orchestrator/**" # Triggers Orchestrator CI
      - "libs/**" # Triggers all services
```

### Security Scanning

- **Trivy**: Vulnerability scanning
- **Bandit**: Python security linting
- **Dependency scanning**: Automated security updates

### Testing Strategy

1. **Unit Tests**: Per-service isolated testing
2. **Integration Tests**: Cross-service testing in `platform/integration-tests/`
3. **Performance Tests**: Load testing in `platform/load_tests/`
4. **Contract Testing**: API contract validation

## Migration Benefits

### ✅ **Achieved Standards**

1. **Independent Services**: Each service is buildable, testable, deployable
2. **Standardized Structure**: Consistent layout across all services
3. **Path-Filtered CI**: Efficient builds only for changed services
4. **Observability**: Comprehensive monitoring per service
5. **Contract-First**: API contracts with validation
6. **Security**: Automated vulnerability scanning
7. **Documentation**: Service-specific documentation

### ✅ **Operational Improvements**

1. **Faster CI/CD**: Only build what changed
2. **Independent Deployment**: Deploy services individually
3. **Clear Ownership**: Service-specific teams and responsibilities
4. **Improved Debugging**: Service-specific logs and metrics
5. **Better Testing**: Isolated unit tests + integration tests

## Service Catalog

| Service               | Port | Purpose                        | Technology          |
| --------------------- | ---- | ------------------------------ | ------------------- |
| **api-gateway**       | 8000 | Main entry point & routing     | FastAPI + JWT       |
| **analytics-service** | 8005 | CQRS analytics & reporting     | Python + CQRS       |
| **orchestrator**      | 8002 | LangGraph workflow execution   | Python + LangGraph  |
| **router-service**    | 8003 | Intelligent request routing    | Python + ML         |
| **realtime**          | 8004 | WebSocket & real-time features | ASGI + Redis        |
| **ingestion**         | 8006 | Document processing            | Python Workers      |
| **billing-service**   | 8007 | Usage tracking & billing       | Python + Webhooks   |
| **tenant-service**    | 8008 | Multi-tenant management        | Python + FastAPI    |
| **chat-adapters**     | 8009 | Multi-channel chat integration | Python + FastAPI    |
| **tool-service**      | 8010 | Tool execution management      | Python + AsyncIO    |
| **eval-service**      | 8011 | Model evaluation & QA          | Python + ML         |
| **capacity-monitor**  | 8012 | Resource monitoring            | Python + Prometheus |
| **admin-portal**      | 8100 | Backend admin interface        | FastAPI + Jinja2    |
| **web-frontend**      | 3000 | Frontend user interface        | React + TypeScript  |

## Next Steps

1. **Review Generated Files**: Verify service configurations
2. **Update Import Paths**: Fix any remaining import statements
3. **Test Services**: Run `make test` for each service
4. **Update CI/CD**: Verify path-filtered workflows
5. **Remove Legacy**: Clean up `*_legacy` directories after verification

## Commands

```bash
# Platform-level operations
make services        # List all services
make dev            # Set up all services for development
make test           # Test all services
make build          # Build all Docker images
make deploy-dev     # Deploy to development
make deploy-prod    # Deploy to production

# Service-level operations
cd apps/<service-name>
make dev            # Set up this service
make test           # Test this service
make run            # Run this service locally
```
