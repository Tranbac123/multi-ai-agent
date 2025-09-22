# Analytics-Service Service

CQRS read-only analytics and reporting

## Technology Stack

Python + CQRS

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

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `REDIS_URL` | Redis connection string | Required |
| `PORT` | Service port | 8005 |

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
from analytics_service_client import ApiClient, Configuration
from analytics_service_client.api.default_api import DefaultApi

config = Configuration(host="http://localhost:8005")
client = ApiClient(config)
api = DefaultApi(client)

# Check health
health = api.health_check()
print(health.status)
```

#### TypeScript
```typescript
import { DefaultApi, Configuration } from '@company/analytics-service-client';

const config = new Configuration({
  basePath: 'http://localhost:8005'
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
    "analytics_service"
)

func main() {
    config := analytics_service.NewConfiguration()
    config.BasePath = "http://localhost:8005"
    client := analytics_service.NewAPIClient(config)
    
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
- **Dashboard**: [observability/dashboards/analytics-service.json](observability/dashboards/analytics-service.json)
## 📊 Observability & Monitoring

This service includes comprehensive observability configurations for production monitoring.

### Available Configurations

- **📈 Grafana Dashboard**: `observability/dashboards/analytics-service.json`
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
./platform/scripts/sync-observability.sh sync-service analytics-service

# Sync only dashboard
./platform/scripts/sync-observability.sh sync-dashboards

# Sync only alerts
./platform/scripts/sync-observability.sh sync-alerts

# Validate configuration
./platform/scripts/sync-observability.sh validate

# Dry run to see what would be changed
./platform/scripts/sync-observability.sh --dry-run sync-service analytics-service
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

- **📈 Dashboard**: [Grafana Dashboard](https://grafana.company.com/d/analytics-service)
- **🔍 Logs**: [Loki Logs](https://grafana.company.com/explore?query={{service="analytics-service"}})
- **🔎 Traces**: [Jaeger UI](https://jaeger.company.com/search?service=analytics-service)
- **🚨 Alerts**: [AlertManager](https://alertmanager.company.com/#/alerts?filter={{service="analytics-service"}})

### Key Metrics to Monitor

```promql
# Request Rate
rate(http_requests_total{{service="analytics-service"}}[5m])

# Error Rate
rate(http_requests_total{{service="analytics-service",status=~"5.."}}[5m]) / rate(http_requests_total{{service="analytics-service"}}[5m]) * 100

# Latency P95
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{{service="analytics-service"}}[5m]))

# CPU Usage
rate(container_cpu_usage_seconds_total{{container="analytics-service"}}[5m]) * 100

# Memory Usage
container_memory_usage_bytes{{container="analytics-service"}} / 1024/1024/1024
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