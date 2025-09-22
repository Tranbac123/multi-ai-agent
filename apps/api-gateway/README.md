# API Gateway Service

Main entry point with authentication, rate limiting, and intelligent routing to backend services.

## Features

- JWT-based authentication and authorization
- Per-tenant rate limiting with Redis backend
- Request routing and load balancing
- OpenTelemetry instrumentation
- Health checks and metrics exposition

## Quick Start

```bash
# Install dependencies
make dev

# Run tests
make test

# Start development server
make run
```

## Configuration

Key environment variables:

| Variable                | Description                  | Default  |
| ----------------------- | ---------------------------- | -------- |
| `DATABASE_URL`          | PostgreSQL connection string | Required |
| `REDIS_URL`             | Redis connection string      | Required |
| `JWT_SECRET`            | Secret for JWT token signing | Required |
| `RATE_LIMIT_PER_MINUTE` | Default rate limit           | 100      |

## API Documentation

OpenAPI specification: [`contracts/openapi.yaml`](contracts/openapi.yaml)


## 📋 API Contracts & Code Generation

### OpenAPI Specification

The service API is defined in [`contracts/openapi.yaml`](contracts/openapi.yaml).

### Generate Client Libraries

```bash
# Generate all clients (Python, TypeScript, Go)
make generate-clients

# Generate TypeScript client with Orval (alternative)
make generate-orval

# Clean generated code
make clean-generated
```

### Generated Clients

After running `make generate-clients`:

- **Python Client**: `gen/python-client/`
- **TypeScript Client**: `gen/typescript-client/`  
- **Go Client**: `gen/go-client/`

### Using Generated Clients

#### Python
```python
from api_gateway_client import ApiClient, Configuration
from api_gateway_client.api.default_api import DefaultApi

config = Configuration(host="http://localhost:8000")
client = ApiClient(config)
api = DefaultApi(client)

# Check health
health = api.health_check()
print(health.status)
```

#### TypeScript
```typescript
import { DefaultApi, Configuration } from '@company/api-gateway-client';

const config = new Configuration({
  basePath: 'http://localhost:8000'
});
const api = new DefaultApi(config);

// Check health
const health = await api.healthCheck();
console.log(health.data.status);
```

#### Go
```go
package main

import (
    "context"
    "api_gateway"
)

func main() {
    config := api_gateway.NewConfiguration()
    config.BasePath = "http://localhost:8000"
    client := api_gateway.NewAPIClient(config)
    
    health, _, err := client.DefaultApi.HealthCheck(context.Background())
    if err != nil {
        log.Fatal(err)
    }
    fmt.Println(health.Status)
}
```\n\n## Deployment

```bash
# Deploy to development
cd deploy && make deploy ENV=dev

# Deploy to production
cd deploy && make deploy ENV=prod IMAGE_TAG=v1.0.0
```

## Monitoring

- **SLO**: [observability/SLO.md](observability/SLO.md)
- **Runbook**: [observability/runbook.md](observability/runbook.md)
- **Dashboard**: [observability/dashboards/api-gateway.json](observability/dashboards/api-gateway.json)

## 📊 Observability & Monitoring

This service includes comprehensive observability configurations for production monitoring.

### Available Configurations

- **📈 Grafana Dashboard**: `observability/dashboards/api-gateway.json`
  - Request rate, latency percentiles, error rate
  - Resource usage (CPU, memory)
  - Service-specific metrics

- **🚨 Alert Rules**: `observability/alerts.yaml`
  - High error rate (>5%)
  - High latency (P95 threshold)
  - Service down detection
  - Resource exhaustion warnings

- **🎯 Service Level Objectives**: `observability/SLO.md`
  - Availability, latency, and error rate targets
  - Error budget tracking
  - PromQL queries for SLI monitoring

- **📖 Runbook**: `observability/runbook.md`
  - Troubleshooting procedures
  - Common issues and solutions
  - Escalation procedures

### Sync to Monitoring Stack

To deploy observability configurations to your monitoring stack:

```bash
# Sync all configurations for this service
./platform/scripts/sync-observability.sh sync-service api-gateway

# Sync only dashboard
./platform/scripts/sync-observability.sh sync-dashboards

# Sync only alerts
./platform/scripts/sync-observability.sh sync-alerts

# Validate configuration
./platform/scripts/sync-observability.sh validate

# Dry run to see what would be changed
./platform/scripts/sync-observability.sh --dry-run sync-service api-gateway
```

### Environment Variables for Sync

```bash
export GRAFANA_URL="https://grafana.your-company.com"
export GRAFANA_API_KEY="your-grafana-api-key"
export PROMETHEUS_URL="https://prometheus.your-company.com"
export ALERTMANAGER_URL="https://alertmanager.your-company.com"
export ENVIRONMENT="production"  # or staging, development
```

### Quick Links (Production)

- **📈 Dashboard**: [Grafana Dashboard](https://grafana.company.com/d/api-gateway)
- **🔍 Logs**: [Loki Logs](https://grafana.company.com/explore?query={{service="api-gateway"}})
- **🔎 Traces**: [Jaeger UI](https://jaeger.company.com/search?service=api-gateway)
- **🚨 Alerts**: [AlertManager](https://alertmanager.company.com/#/alerts?filter={{service="api-gateway"}})

### Key Metrics to Monitor

```promql
# Request Rate
rate(http_requests_total{{service="api-gateway"}}[5m])

# Error Rate
rate(http_requests_total{{service="api-gateway",status=~"5.."}}[5m]) / rate(http_requests_total{{service="api-gateway"}}[5m]) * 100

# Latency P95
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{{service="api-gateway"}}[5m]))

# CPU Usage
rate(container_cpu_usage_seconds_total{{container="api-gateway"}}[5m]) * 100

# Memory Usage
container_memory_usage_bytes{{container="api-gateway"}} / 1024/1024/1024
```

### Local Development Monitoring

For local development, you can run a lightweight monitoring stack:

```bash
# Start local monitoring stack
make dev-monitoring

# View local dashboard
open http://localhost:3000  # Grafana
open http://localhost:9090  # Prometheus
```