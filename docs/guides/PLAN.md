# Polyrepo Split Strategy & Implementation Plan

## Overview

This document outlines the strategy for splitting the current monorepo into multiple service repositories while maintaining a meta-repo for local development and orchestration.

## Current Architecture Analysis

### Services Identified

Based on the current structure, we have:

**Data Plane Services (apps/data-plane/):**

- `api-gateway` (FastAPI) - Port 8000 ✅ _Existing_
- `model-gateway` (FastAPI) - Port 8080 ✅ _Existing_
- `orchestrator` (FastAPI) - Port 8081 ✅ _Existing_
- `router-service` (FastAPI) - Port 8083 ✅ _Existing_
- `realtime-gateway` (FastAPI) - Port 8087 ✅ _Existing_
- `ingestion-service` (FastAPI) - Port 8084 ✅ _Existing_
- `analytics-service` (FastAPI) - Port 8085 ✅ _Existing_
- `retrieval-service` (FastAPI) - Port 8082 ✅ _Existing_
- `tools-service` (FastAPI) - Port 8087 ✅ _Existing_
- `memory-service` (FastAPI) - Port 8084 ✅ _Existing_
- `chat-adapters` (FastAPI) - Port 8097 ✅ _Existing_
- `semantic-cache-service` (FastAPI) - Port 8087 ✅ _Existing_
- `event-relay-service` (FastAPI) - Port 8088 ✅ _Existing_
- `migration-runner` (FastAPI) - Port 8089 ✅ _Existing_
- `agents-service` (FastAPI) - Port 8090 ✅ _Existing_
- `eval-service` (FastAPI) - Port 8091 ✅ _Existing_

**Control Plane Services (apps/control-plane/):**

- `config-service` (FastAPI) - Port 8090 ✅ _Existing_
- `feature-flags-service` (FastAPI) - Port 8092 ✅ _Existing_
- `registry-service` (FastAPI) - Port 8093 ✅ _Existing_
- `policy-adapter` (FastAPI) - Port 8091 ✅ _Existing_
- `usage-metering` (FastAPI) - Port 8094 ✅ _Existing_
- `audit-log` (FastAPI) - Port 8095 ✅ _Existing_
- `notification-service` (FastAPI) - Port 8096 ✅ _Existing_
- `tenant-service` (FastAPI) - Port 8098 ✅ _Existing_
- `capacity-monitor` (FastAPI) - Port 8099 ✅ _Existing_
- `billing-service` (FastAPI) - Port 8100 ✅ _Existing_

### Service Boundaries & Ownership

Each service will own:

- **Source Code**: `src/` directory with FastAPI application
- **Tests**: `tests/` directory with unit, integration, and contract tests
- **Contracts**: `schemas/` directory with JSON Schema definitions
- **Deployment**: `k8s/` directory with Kubernetes manifests
- **Configuration**: `Dockerfile`, `requirements.txt`, `.env.example`
- **Documentation**: `README.md` with service-specific documentation

### External Dependencies

**Shared Infrastructure:**

- PostgreSQL 16 with RLS (Row Level Security)
- NATS JetStream for event streaming
- Redis for caching and sessions
- OpenTelemetry Collector for observability
- Prometheus for metrics collection
- Grafana for visualization

**Environment Variables (per service):**

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/ai_agent
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=ai_agent
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Event Streaming
NATS_URL=nats://nats:4222
NATS_JETSTREAM_URL=nats://nats:4222

# Caching
REDIS_URL=redis://redis:6379

# Observability
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_SERVICE_NAME=<service-name>
OTEL_RESOURCE_ATTRIBUTES=service.name=<service-name>,service.version=1.0.0

# API Keys (service-specific)
OPENAI_API_KEY=<key>
ANTHROPIC_API_KEY=<key>
FIRECRAWL_API_KEY=<key>
```

## Git Strategy Options

### Option A: Separate Repositories with git filter-repo (Recommended)

**Pros:**

- Clean service boundaries
- Independent CI/CD pipelines
- Service-specific permissions
- Easier to scale teams

**Cons:**

- More complex dependency management
- Cross-service changes require multiple PRs

**Implementation:**

```bash
# For each service
git clone <monorepo-url> <service-name>
cd <service-name>
git filter-repo --path apps/data-plane/<service-name>/ --path apps/control-plane/<service-name>/
git remote add origin <new-service-repo-url>
git push -u origin main
```

### Option B: Meta-repo with Submodules

**Pros:**

- Single source of truth
- Easier cross-service development
- Simplified dependency management

**Cons:**

- Submodule complexity
- Harder to scale teams
- Complex CI/CD setup

**Implementation:**

```bash
# Keep current repo as meta-repo
# Add services as submodules
git submodule add <service-repo-url> services/<service-name>
```

### Option C: Subtree (Not Recommended)

**Pros:**

- Simpler than submodules
- Single repository

**Cons:**

- No independent history
- Complex merge conflicts
- Hard to scale

## Risk Assessment & Rollback Plan

### High-Risk Areas

1. **Database Schema Changes**: Cross-service migrations
2. **Event Contract Changes**: Breaking changes in shared schemas
3. **Service Dependencies**: Circular dependencies between services
4. **Configuration Management**: Environment variable consistency

### Mitigation Strategies

1. **Database**: Use migration runner service for schema changes
2. **Events**: Version all event schemas, maintain backward compatibility
3. **Dependencies**: Clear dependency graph, avoid circular deps
4. **Configuration**: Centralized config service with validation

### Rollback Plan

1. **Immediate**: Revert to monorepo using git tags
2. **Service-specific**: Individual service rollback via CI/CD
3. **Database**: Migration rollback scripts
4. **Events**: Event schema versioning and compatibility

## Implementation Steps

### Phase 1: Preparation (Week 1)

1. Create service repositories
2. Set up shared infrastructure contracts
3. Create meta-repo structure
4. Set up CI/CD scaffolding

### Phase 2: Service Extraction (Week 2-3)

1. Extract services one by one using git filter-repo
2. Create service-specific CI/CD pipelines
3. Update service dependencies
4. Test individual services

### Phase 3: Integration (Week 4)

1. Set up meta-repo with docker-compose
2. Configure cross-service communication
3. Set up monitoring and observability
4. End-to-end testing

### Phase 4: Production Readiness (Week 5)

1. Security review
2. Performance testing
3. Documentation updates
4. Team training

## Port Mapping Strategy

### Core Services (Always Running)

- `api-gateway`: 8000
- `orchestrator`: 8081
- `router-service`: 8083

### Data Plane Services

- `model-gateway`: 8080
- `retrieval-service`: 8082
- `ingestion-service`: 8084
- `analytics-service`: 8085
- `tools-service`: 8087
- `memory-service`: 8084
- `realtime-gateway`: 8086
- `semantic-cache-service`: 8088
- `event-relay-service`: 8089
- `migration-runner`: 8090
- `chat-adapters`: 8097

### Control Plane Services

- `config-service`: 8091
- `policy-adapter`: 8092
- `feature-flags-service`: 8093
- `registry-service`: 8094
- `usage-metering`: 8095
- `audit-log`: 8096
- `notification-service`: 8097
- `tenant-service`: 8098
- `capacity-monitor`: 8099
- `billing-service`: 8100

### Infrastructure

- `postgres`: 5432
- `redis`: 6379
- `nats`: 4222
- `otel-collector`: 4317
- `prometheus`: 9090
- `grafana`: 3000

## Event Contracts

### Core Events

1. **UsageEvent**: Service usage tracking
2. **OrchestratorStep**: Workflow execution steps
3. **RealtimeMessage**: Real-time communication
4. **IngestEvent**: Document ingestion events
5. **AnalyticsEvent**: Analytics data points

### Event Topics

- `ingest.*`: Document ingestion events
- `orchestrator.step`: Workflow execution events
- `usage.metered`: Usage tracking events
- `realtime.push`: Real-time message events
- `alerts.*`: System alert events

## Success Criteria

1. **Functional**: All services start and pass health checks
2. **Performance**: No degradation in response times
3. **Observability**: Full tracing and metrics collection
4. **Security**: No secrets in code, proper RBAC
5. **Documentation**: Complete setup and operation guides

## Timeline

- **Week 1**: Planning and preparation
- **Week 2-3**: Service extraction and individual testing
- **Week 4**: Integration and end-to-end testing
- **Week 5**: Production readiness and team training

**Total Duration**: 5 weeks

## Next Steps

1. Review and approve this plan
2. Create service repositories
3. Begin Phase 1 implementation
4. Set up CI/CD pipelines
5. Extract first service as proof of concept
