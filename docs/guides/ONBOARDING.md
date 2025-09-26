# 5-Minute Quickstart Guide

Get the Multi-AI-Agent Platform running locally in 5 minutes.

## Prerequisites

- Docker and Docker Compose
- Git
- Make (optional, for convenience commands)

## Quick Start

### 1. Clone and Setup

```bash
# Clone the meta-repository
git clone https://github.com/your-org/multi-ai-agent-meta.git
cd multi-ai-agent-meta

# Initialize service submodules
git submodule update --init --recursive

# Copy environment configuration
cp dev-env/env.example dev-env/.env
```

### 2. Configure Environment

Edit `dev-env/.env` with your API keys:

```bash
# Required API keys (get from respective providers)
OPENAI_API_KEY=sk-your-openai-api-key-here
ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key-here
FIRECRAWL_API_KEY=fc-your-firecrawl-api-key-here

# Optional: Generate a secure JWT secret
JWT_SECRET_KEY=$(openssl rand -hex 32)
```

### 3. Start Core Services

```bash
# Start core services (API Gateway, Orchestrator, Router Service)
make -C dev-env up-core

# Or using Docker Compose directly
cd dev-env
docker-compose --profile core up -d --build
```

### 4. Verify Services

```bash
# Check service health
make -C dev-env health

# Or manually check each service
curl http://localhost:8000/healthz  # API Gateway
curl http://localhost:8081/healthz  # Orchestrator
curl http://localhost:8083/healthz  # Router Service
```

### 5. Test the Platform

```bash
# Test API Gateway
curl -X GET http://localhost:8000/healthz

# Test with authentication (if configured)
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://localhost:8000/api/v1/status
```

## Service URLs

Once running, services are available at:

| Service           | URL                   | Description              |
| ----------------- | --------------------- | ------------------------ |
| API Gateway       | http://localhost:8000 | Main entry point         |
| Orchestrator      | http://localhost:8081 | Workflow orchestration   |
| Router Service    | http://localhost:8083 | Request routing          |
| Model Gateway     | http://localhost:8080 | AI model gateway         |
| Retrieval Service | http://localhost:8082 | Document retrieval       |
| Ingestion Service | http://localhost:8084 | Document ingestion       |
| Analytics Service | http://localhost:8085 | Analytics processing     |
| Billing Service   | http://localhost:8086 | Usage billing            |
| Realtime Gateway  | http://localhost:8087 | Real-time messaging      |
| Config Service    | http://localhost:8090 | Configuration management |
| Usage Metering    | http://localhost:8094 | Usage tracking           |

## Observability Stack

| Service    | URL                    | Description            |
| ---------- | ---------------------- | ---------------------- |
| Grafana    | http://localhost:3000  | Metrics and dashboards |
| Prometheus | http://localhost:9090  | Metrics collection     |
| Jaeger     | http://localhost:16686 | Distributed tracing    |

## Development Commands

```bash
# Start all services
make -C dev-env up

# Start specific service groups
make -C dev-env up-data      # Data plane services
make -C dev-env up-control   # Control plane services
make -C dev-env up-realtime  # Realtime services
make -C dev-env up-analytics # Analytics services
make -C dev-env up-billing   # Billing services

# View logs
make -C dev-env logs
make -C dev-env logs-api-gateway
make -C dev-env logs-orchestrator

# Stop services
make -C dev-env down

# Rebuild services
make -C dev-env rebuild

# Run database migrations
make -C dev-env migrate

# Seed database with test data
make -C dev-env seed

# Run smoke tests
make -C dev-env smoke-test
```

## Individual Service Development

### Working on a Single Service

```bash
# Navigate to service directory
cd services/api-gateway

# Install dependencies
pip install -r requirements.txt

# Run service locally
make run

# Run tests
make test

# Run linting
make lint
```

### Service-Specific Commands

Each service has its own Makefile with commands:

```bash
# In any service directory
make help        # Show available commands
make run         # Run service locally
make test        # Run tests
make lint        # Run linting
make migrate     # Run database migrations
make build       # Build Docker image
```

## Troubleshooting

### Common Issues

#### Port Conflicts

If you get port conflicts:

```bash
# Check what's using the port
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use different ports in .env
API_GATEWAY_PORT=8001
```

#### Missing Environment Variables

```bash
# Check if .env file exists
ls -la dev-env/.env

# Copy from example if missing
cp dev-env/env.example dev-env/.env

# Edit with your values
nano dev-env/.env
```

#### JetStream Not Ready

If NATS JetStream isn't ready:

```bash
# Check NATS status
curl http://localhost:8222/healthz

# Wait for services to be ready
sleep 30

# Check service logs
docker-compose logs nats
```

#### Database Connection Issues

```bash
# Check PostgreSQL status
docker-compose logs postgres

# Test database connection
docker-compose exec postgres psql -U postgres -d ai_agent -c "SELECT 1;"

# Reset database
docker-compose down -v
docker-compose up -d postgres
```

#### Service Health Check Failures

```bash
# Check individual service health
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz

# Check service logs
docker-compose logs api-gateway

# Restart specific service
docker-compose restart api-gateway
```

### Debug Mode

Enable debug mode for detailed logging:

```bash
# In .env file
DEBUG=true
LOG_LEVEL=DEBUG

# Restart services
docker-compose restart
```

### Performance Issues

If services are slow to start:

```bash
# Check system resources
docker stats

# Increase Docker resources
# Docker Desktop → Settings → Resources

# Use lighter images
# Update Dockerfile to use alpine variants
```

## Next Steps

### 1. Explore the Platform

- Visit Grafana dashboards at http://localhost:3000
- Check Jaeger traces at http://localhost:16686
- View Prometheus metrics at http://localhost:9090

### 2. Run Tests

```bash
# Run all tests
make -C dev-env test

# Run specific service tests
cd services/api-gateway
make test
```

### 3. Develop Features

- Pick a service to work on
- Make changes to the code
- Run tests and linting
- Submit a pull request

### 4. Deploy to Staging

```bash
# Deploy to staging environment
make -C dev-env deploy-staging
```

## Getting Help

### Documentation

- [Architecture Overview](docs/architecture/)
- [API Documentation](docs/api/)
- [Deployment Guide](docs/deployment/)
- [Contributing Guide](CONTRIBUTING.md)

### Support Channels

- GitHub Issues: [Create an issue](https://github.com/your-org/multi-ai-agent-meta/issues)
- Slack: #ai-agent-platform
- Email: platform-team@your-org.com

### Common Tasks

| Task                | Command                   |
| ------------------- | ------------------------- |
| Start core services | `make -C dev-env up-core` |
| View logs           | `make -C dev-env logs`    |
| Run tests           | `make -C dev-env test`    |
| Check health        | `make -C dev-env health`  |
| Stop services       | `make -C dev-env down`    |
| Rebuild services    | `make -C dev-env rebuild` |
| Run migrations      | `make -C dev-env migrate` |
| Seed database       | `make -C dev-env seed`    |

## Environment Variables Reference

### Required Variables

```bash
# API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
FIRECRAWL_API_KEY=fc-...

# Database
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/ai_agent

# Redis
REDIS_URL=redis://redis:6379

# NATS
NATS_URL=nats://nats:4222

# Security
JWT_SECRET_KEY=your-secret-key-here
```

### Optional Variables

```bash
# Logging
LOG_LEVEL=INFO
DEBUG=false

# Observability
ENABLE_TRACING=true
ENABLE_METRICS=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:3001

# Rate Limiting
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_BURST=200
```

## Success! 🎉

You now have the Multi-AI-Agent Platform running locally. You can:

- ✅ Start developing new features
- ✅ Run tests and linting
- ✅ View metrics and traces
- ✅ Deploy to staging
- ✅ Contribute to the project

Happy coding! 🚀
