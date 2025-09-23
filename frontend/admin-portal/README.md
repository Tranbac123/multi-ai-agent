# Admin Portal Service

FastAPI-based administration interface for tenant management, plan configuration, and system monitoring.

## Technology Stack

- FastAPI
- Jinja2 Templates
- SQLAlchemy 2.0
- PostgreSQL
- Redis

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

| Variable       | Description                  | Default  |
| -------------- | ---------------------------- | -------- |
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `REDIS_URL`    | Redis connection string      | Required |
| `PORT`         | Service port                 | 8100     |

## Features

- Tenant administration
- Plan configuration
- System monitoring
- User management
- Analytics dashboard

## API Documentation

Available at: http://localhost:8100/docs


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
from admin_portal_client import ApiClient, Configuration
from admin_portal_client.api.default_api import DefaultApi

config = Configuration(host="http://localhost:8100")
client = ApiClient(config)
api = DefaultApi(client)

# Check health
health = api.health_check()
print(health.status)
```

#### TypeScript
```typescript
import { DefaultApi, Configuration } from '@company/admin-portal-client';

const config = new Configuration({
  basePath: 'http://localhost:8100'
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
    "admin_portal"
)

func main() {
    config := admin_portal.NewConfiguration()
    config.BasePath = "http://localhost:8100"
    client := admin_portal.NewAPIClient(config)
    
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
cd deploy && make deploy ENV=prod
```

## 📊 Observability & Monitoring

This service includes comprehensive observability configurations for production monitoring.

### Available Configurations

- **📈 Grafana Dashboard**: `observability/dashboards/admin-portal.json`
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
./platform/scripts/sync-observability.sh sync-service admin-portal

# Sync only dashboard
./platform/scripts/sync-observability.sh sync-dashboards

# Sync only alerts
./platform/scripts/sync-observability.sh sync-alerts

# Validate configuration
./platform/scripts/sync-observability.sh validate

# Dry run to see what would be changed
./platform/scripts/sync-observability.sh --dry-run sync-service admin-portal
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

- **📈 Dashboard**: [Grafana Dashboard](https://grafana.company.com/d/admin-portal)
- **🔍 Logs**: [Loki Logs](https://grafana.company.com/explore?query={{service="admin-portal"}})
- **🔎 Traces**: [Jaeger UI](https://jaeger.company.com/search?service=admin-portal)
- **🚨 Alerts**: [AlertManager](https://alertmanager.company.com/#/alerts?filter={{service="admin-portal"}})

### Key Metrics to Monitor

```promql
# Request Rate
rate(http_requests_total{{service="admin-portal"}}[5m])

# Error Rate
rate(http_requests_total{{service="admin-portal",status=~"5.."}}[5m]) / rate(http_requests_total{{service="admin-portal"}}[5m]) * 100

# Latency P95
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{{service="admin-portal"}}[5m]))

# CPU Usage
rate(container_cpu_usage_seconds_total{{container="admin-portal"}}[5m]) * 100

# Memory Usage
container_memory_usage_bytes{{container="admin-portal"}} / 1024/1024/1024
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