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
