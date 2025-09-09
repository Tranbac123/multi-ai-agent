# Multi-Tenant AIaaS Platform - Comprehensive Guide

## 🎯 Overview

This is a production-grade, multi-tenant AI-as-a-Service (AIaaS) platform that provides intelligent customer support, order management, and lead capture across multiple channels. The platform is built with a microservices architecture and supports YAML-based workflow definitions for easy customization.

## 🏗️ Architecture

### Core Components

1. **API Gateway** (`apps/api-gateway/`) - Main entry point with authentication and routing
2. **Orchestrator Service** (`apps/orchestrator/`) - LangGraph-based workflow orchestration
3. **Router Service** (`apps/router-service/`) - Intelligent request routing and cost optimization
4. **YAML Workflows** (`configs/workflows/`) - Declarative workflow definitions
5. **Frontend** (`web/`) - React-based web interface
6. **Database** - PostgreSQL with Row-Level Security (RLS) for multi-tenancy
7. **Cache** - Redis for session management and caching
8. **Event Bus** - NATS for inter-service communication

### Key Features

- **Multi-Tenant Architecture** - Complete tenant isolation with RLS
- **YAML Workflow System** - Declarative workflow definitions
- **Intelligent Routing** - Cost-optimized request routing
- **Event Sourcing** - Complete audit trail and replay capability
- **Resilience Patterns** - Circuit breakers, retries, timeouts, bulkheads
- **Comprehensive Monitoring** - OpenTelemetry, Prometheus, Grafana
- **User Management** - Registration, subscriptions, service packages
- **Real-time Communication** - WebSocket support

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Node.js 18+
- PostgreSQL 16+
- Redis 7+

### Installation

1. **Clone and setup**:

   ```bash
   git clone <repo-url>
   cd multi-ai-agent
   cp env.example .env
   # Edit .env with your API keys
   ```

2. **Start services**:

   ```bash
   make up
   ```

3. **Access services**:
   - API: http://localhost:8000
   - Web Dashboard: http://localhost:5173
   - API Docs: http://localhost:8000/docs
   - WebSocket: ws://localhost:8000/ws/chat

## 📁 Project Structure

```
multi-ai-agent/
├── apps/                          # Microservices
│   ├── api-gateway/              # Main API gateway
│   ├── orchestrator/             # LangGraph orchestrator
│   └── router-service/           # Intelligent routing
├── configs/                      # Configuration files
│   └── workflows/               # YAML workflow definitions
├── libs/                        # Shared libraries
│   ├── adapters/               # Resilient adapters
│   ├── clients/                # Service clients
│   ├── contracts/              # Pydantic contracts
│   ├── events/                 # Event system
│   └── utils/                  # Utility functions
├── web/                        # React frontend
├── tests/                      # Test suite
├── infra/                      # Infrastructure configs
└── monitoring/                 # Monitoring stack
```

## 🔧 Configuration

### Environment Variables

Key environment variables in `.env`:

```bash
# Application
APP_ENV=dev
APP_SECRET=your-secret-key
APP_NAME=AI Customer Agent
APP_VERSION=1.0.0

# Database
DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/app
REDIS_URL=redis://redis:6379/0

# OpenAI
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_MODEL=gpt-4o

# JWT
JWT_SECRET=your-jwt-secret
JWT_ALGORITHM=HS256
JWT_EXPIRES=86400

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

### YAML Workflows

Workflows are defined in `configs/workflows/`:

- `customer_support_workflow.yaml` - Main orchestrator
- `faq_handling.yaml` - FAQ responses
- `order_management.yaml` - Order operations
- `lead_capture.yaml` - Lead collection
- `complaint_handling.yaml` - Complaint management
- `technical_support.yaml` - Technical issues

## 🛠️ Development

### Available Commands

```bash
make dev          # Start development mode
make up           # Start all services
make down         # Stop all services
make build        # Build Docker images
make test         # Run tests
make fmt          # Format code
make lint         # Lint code
make seed         # Seed demo data
make logs         # View logs
```

### Testing

```bash
# Run all tests
make test

# Run specific test types
python tests/run_all_tests.py
python tests/run_evaluation.py

# Test YAML workflows
python configs/workflows/demo_workflows.py
```

## 📊 Monitoring

### Metrics

- **Workflow Execution** - Duration, success rate, error count
- **API Performance** - Request latency, throughput
- **Resource Usage** - CPU, memory, database connections
- **Business Metrics** - Conversion rates, customer satisfaction

### Dashboards

- **Grafana** - http://localhost:3000 (admin/admin)
- **Prometheus** - http://localhost:9090
- **API Documentation** - http://localhost:8000/docs

## 🔒 Security

### Multi-Tenancy

- **Row-Level Security (RLS)** - Database-level tenant isolation
- **JWT Authentication** - Stateless authentication
- **API Gateway** - Centralized authentication and authorization
- **Rate Limiting** - Per-tenant rate limits

### Data Protection

- **Encryption at Rest** - Database encryption
- **Encryption in Transit** - TLS/SSL
- **Input Validation** - Comprehensive input sanitization
- **Audit Logging** - Complete audit trail

## 🚀 Deployment

### Production Deployment

1. **Configure Environment**:

   ```bash
   cp env.example .env.prod
   # Edit production settings
   ```

2. **Deploy with Docker Compose**:

   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

3. **Run Migrations**:

   ```bash
   make db-migrate
   ```

4. **Seed Data**:
   ```bash
   make seed
   ```

### Kubernetes Deployment

Kubernetes manifests are available in `infra/k8s/`:

```bash
kubectl apply -f infra/k8s/
```

## 📈 Scaling

### Horizontal Scaling

- **API Gateway** - Multiple replicas behind load balancer
- **Orchestrator** - Stateless, can scale horizontally
- **Database** - Read replicas for read-heavy workloads
- **Cache** - Redis cluster for high availability

### Performance Optimization

- **Connection Pooling** - Database connection optimization
- **Caching** - Redis for frequently accessed data
- **CDN** - Static asset delivery
- **Load Balancing** - Nginx for request distribution

## 🔧 Troubleshooting

### Common Issues

1. **Database Connection Issues**

   - Check PostgreSQL is running
   - Verify connection string
   - Check network connectivity

2. **Redis Connection Issues**

   - Check Redis is running
   - Verify Redis URL
   - Check memory usage

3. **Workflow Execution Issues**

   - Check YAML syntax
   - Verify workflow validation
   - Check orchestrator logs

4. **Authentication Issues**
   - Verify JWT secret
   - Check token expiration
   - Verify CORS settings

### Debugging

```bash
# View logs
make logs

# Check service health
curl http://localhost:8000/healthz

# Validate workflows
python configs/workflows/demo_workflows.py
```

## 📚 API Reference

### Core Endpoints

- **Chat**: `/chat/messages` - Process customer messages
- **Auth**: `/auth/*` - Authentication and authorization
- **CRM**: `/crm/*` - Customer and lead management
- **Orders**: `/orders/*` - Order management
- **Analytics**: `/analytics/*` - Metrics and reporting
- **Webhooks**: `/webhooks/*` - External integrations

### WebSocket

- **Chat**: `ws://localhost:8000/ws/chat` - Real-time chat

## 🎯 Workflow Development

### Creating New Workflows

1. **Define Workflow** in `configs/workflows/your_workflow.yaml`
2. **Validate Configuration** using workflow loader
3. **Test Workflow** with demo script
4. **Deploy** to orchestrator service

### Workflow Structure

```yaml
name: "workflow_name"
version: "1.0.0"
description: "Workflow description"
category: "category_name"
priority: "high|medium|low"

nodes:
  - name: "start"
    type: "start"
    config:
      next_node: "process"

  - name: "process"
    type: "agent"
    config:
      agent_type: "processor"
      model: "gpt-4o"
      prompt_template: "Process: {message}"

edges:
  - from: "start"
    to: "process"
    condition: null
```

## 🤝 Contributing

### Development Workflow

1. **Fork** the repository
2. **Create** feature branch
3. **Develop** with tests
4. **Validate** workflows
5. **Submit** pull request

### Code Standards

- **Python**: Black, isort, flake8
- **TypeScript**: ESLint, Prettier
- **YAML**: yamllint
- **Tests**: pytest with coverage

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

### Getting Help

- **Documentation**: This comprehensive guide
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Email**: support@example.com

### Resources

- **API Documentation**: http://localhost:8000/docs
- **Workflow Examples**: `configs/workflows/example_workflow.yaml`
- **Demo Scripts**: `configs/workflows/demo_workflows.py`
- **Test Suite**: `tests/run_all_tests.py`

---

## 🎉 Summary

This multi-tenant AIaaS platform provides a complete solution for intelligent customer support with:

- ✅ **Production-Ready Architecture** - Microservices with resilience patterns
- ✅ **YAML Workflow System** - Declarative workflow definitions
- ✅ **Multi-Tenant Support** - Complete tenant isolation
- ✅ **Comprehensive Monitoring** - Full observability stack
- ✅ **User Management** - Registration and subscription system
- ✅ **Real-time Communication** - WebSocket support
- ✅ **Extensive Testing** - Unit, integration, and E2E tests
- ✅ **Complete Documentation** - This comprehensive guide

The platform is ready for production deployment and can be easily extended with additional workflows and features as needed.
