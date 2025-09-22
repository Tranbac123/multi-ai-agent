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
