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