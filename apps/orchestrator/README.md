# Orchestrator Service

FSM/LangGraph workflow execution with resilient tool adapters

## Technology Stack

Python + LangGraph

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
| `PORT` | Service port | 8002 |

## API Documentation

OpenAPI specification: [`contracts/openapi.yaml`](contracts/openapi.yaml)


## 📋 gRPC Contracts & Code Generation

### Protocol Buffer Definitions

The service gRPC API is defined in:
- [`contracts/health.proto`](contracts/health.proto) - Health check service
- [`contracts/info.proto`](contracts/info.proto) - Service information
- [`contracts/orchestrator.proto`](contracts/orchestrator.proto) - Main service API

### Generate Client Libraries

```bash
# Generate all clients (Go, Python, TypeScript)
make generate-clients

# Lint proto files
make buf-lint

# Check for breaking changes
make buf-breaking

# Clean generated code
make clean-generated
```

### Generated Clients

After running `make generate-clients`:

- **Go Client**: `gen/go/`
- **Python Client**: `gen/python/`
- **TypeScript Client**: `gen/typescript/`

### Using Generated Clients

#### Go
```go
package main

import (
    "context"
    "google.golang.org/grpc"
    healthpb "github.com/company/multi-ai-agent/orchestrator/gen/health/v1"
)

func main() {
    conn, err := grpc.Dial("localhost:8002", grpc.WithInsecure())
    if err != nil {
        log.Fatal(err)
    }
    defer conn.Close()
    
    client := healthpb.NewHealthServiceClient(conn)
    resp, err := client.Check(context.Background(), &healthpb.HealthCheckRequest{
        Service: "orchestrator",
    })
    if err != nil {
        log.Fatal(err)
    }
    fmt.Println(resp.Status)
}
```

#### Python
```python
import grpc
from gen.python.health_pb2 import HealthCheckRequest
from gen.python.health_pb2_grpc import HealthServiceStub

channel = grpc.insecure_channel('localhost:8002')
client = HealthServiceStub(channel)

request = HealthCheckRequest(service='orchestrator')
response = client.Check(request)
print(response.status)
```

#### TypeScript
```typescript
import { GrpcWebFetchTransport } from "@protobuf-ts/grpcweb-transport";
import { HealthServiceClient } from "./gen/typescript/health";

const transport = new GrpcWebFetchTransport({
  baseUrl: "http://localhost:8002"
});
const client = new HealthServiceClient(transport);

const { response } = await client.check({
  service: "orchestrator"
});
console.log(response.status);
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
- **Dashboard**: [observability/dashboards/orchestrator.json](observability/dashboards/orchestrator.json)
## 📊 Observability & Monitoring

This service includes comprehensive observability configurations for production monitoring.

### Available Configurations

- **📈 Grafana Dashboard**: `observability/dashboards/orchestrator.json`
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
./platform/scripts/sync-observability.sh sync-service orchestrator

# Sync only dashboard
./platform/scripts/sync-observability.sh sync-dashboards

# Sync only alerts
./platform/scripts/sync-observability.sh sync-alerts

# Validate configuration
./platform/scripts/sync-observability.sh validate

# Dry run to see what would be changed
./platform/scripts/sync-observability.sh --dry-run sync-service orchestrator
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

- **📈 Dashboard**: [Grafana Dashboard](https://grafana.company.com/d/orchestrator)
- **🔍 Logs**: [Loki Logs](https://grafana.company.com/explore?query={{service="orchestrator"}})
- **🔎 Traces**: [Jaeger UI](https://jaeger.company.com/search?service=orchestrator)
- **🚨 Alerts**: [AlertManager](https://alertmanager.company.com/#/alerts?filter={{service="orchestrator"}})

### Key Metrics to Monitor

```promql
# Request Rate
rate(http_requests_total{{service="orchestrator"}}[5m])

# Error Rate
rate(http_requests_total{{service="orchestrator",status=~"5.."}}[5m]) / rate(http_requests_total{{service="orchestrator"}}[5m]) * 100

# Latency P95
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{{service="orchestrator"}}[5m]))

# CPU Usage
rate(container_cpu_usage_seconds_total{{container="orchestrator"}}[5m]) * 100

# Memory Usage
container_memory_usage_bytes{{container="orchestrator"}} / 1024/1024/1024
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