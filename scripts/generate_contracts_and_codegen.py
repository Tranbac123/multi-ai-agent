#!/usr/bin/env python3
"""
Generate comprehensive contracts and codegen configuration for all services.
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List

# Service configurations
SERVICES_CONFIG = {
    "api-gateway": {
        "port": 8000,
        "protocol": "http",
        "description": "Main entry point with authentication, rate limiting, and routing",
        "endpoints": [
            {"path": "/auth/login", "method": "POST", "description": "User authentication"},
            {"path": "/auth/refresh", "method": "POST", "description": "Refresh token"},
            {"path": "/auth/logout", "method": "POST", "description": "User logout"},
            {"path": "/v1/routes", "method": "GET", "description": "List available routes"},
            {"path": "/v1/tenants/{tenant_id}/quota", "method": "GET", "description": "Get tenant quota"}
        ]
    },
    "analytics-service": {
        "port": 8005,
        "protocol": "http",
        "description": "CQRS read-only analytics and reporting",
        "endpoints": [
            {"path": "/v1/analytics/metrics", "method": "GET", "description": "Get metrics"},
            {"path": "/v1/analytics/reports/{report_id}", "method": "GET", "description": "Get specific report"},
            {"path": "/v1/analytics/dashboards", "method": "GET", "description": "List dashboards"},
            {"path": "/v1/analytics/query", "method": "POST", "description": "Execute analytics query"}
        ]
    },
    "orchestrator": {
        "port": 8002,
        "protocol": "grpc",
        "description": "LangGraph workflow execution with resilient tool adapters",
        "services": [
            {"name": "WorkflowService", "methods": ["ExecuteWorkflow", "GetWorkflowStatus", "CancelWorkflow"]},
            {"name": "ToolService", "methods": ["ListTools", "ExecuteTool", "GetToolStatus"]}
        ]
    },
    "router-service": {
        "port": 8003,
        "protocol": "grpc",
        "description": "Intelligent request routing with feature store and bandit policy",
        "services": [
            {"name": "RouterService", "methods": ["Route", "GetRouteStats", "UpdatePolicy"]},
            {"name": "FeatureService", "methods": ["ExtractFeatures", "GetFeatureStore"]}
        ]
    },
    "realtime": {
        "port": 8004,
        "protocol": "http",
        "description": "WebSocket service with backpressure handling",
        "endpoints": [
            {"path": "/v1/connections", "method": "GET", "description": "List active connections"},
            {"path": "/v1/connections/{connection_id}/send", "method": "POST", "description": "Send message"},
            {"path": "/v1/channels/{channel_id}/broadcast", "method": "POST", "description": "Broadcast to channel"},
            {"path": "/ws", "method": "GET", "description": "WebSocket endpoint"}
        ]
    },
    "ingestion": {
        "port": 8006,
        "protocol": "http",
        "description": "Document processing and knowledge management",
        "endpoints": [
            {"path": "/v1/documents", "method": "POST", "description": "Upload document"},
            {"path": "/v1/documents/{document_id}", "method": "GET", "description": "Get document"},
            {"path": "/v1/documents/{document_id}/process", "method": "POST", "description": "Process document"},
            {"path": "/v1/search", "method": "POST", "description": "Search documents"}
        ]
    },
    "billing-service": {
        "port": 8007,
        "protocol": "http",
        "description": "Usage tracking and billing engine",
        "endpoints": [
            {"path": "/v1/usage", "method": "POST", "description": "Record usage"},
            {"path": "/v1/billing/invoices", "method": "GET", "description": "List invoices"},
            {"path": "/v1/billing/invoices/{invoice_id}", "method": "GET", "description": "Get invoice"},
            {"path": "/v1/billing/preview", "method": "POST", "description": "Preview billing"}
        ]
    },
    "tenant-service": {
        "port": 8008,
        "protocol": "http",
        "description": "Multi-tenant management",
        "endpoints": [
            {"path": "/v1/tenants", "method": "POST", "description": "Create tenant"},
            {"path": "/v1/tenants/{tenant_id}", "method": "GET", "description": "Get tenant"},
            {"path": "/v1/tenants/{tenant_id}", "method": "PUT", "description": "Update tenant"},
            {"path": "/v1/tenants/{tenant_id}/plans", "method": "GET", "description": "Get tenant plans"}
        ]
    },
    "chat-adapters": {
        "port": 8009,
        "protocol": "http",
        "description": "Multi-channel chat integration",
        "endpoints": [
            {"path": "/v1/adapters", "method": "GET", "description": "List chat adapters"},
            {"path": "/v1/adapters/{adapter}/send", "method": "POST", "description": "Send message via adapter"},
            {"path": "/v1/adapters/{adapter}/webhook", "method": "POST", "description": "Handle webhook"},
            {"path": "/v1/conversations/{conversation_id}/messages", "method": "GET", "description": "Get messages"}
        ]
    },
    "tool-service": {
        "port": 8010,
        "protocol": "grpc",
        "description": "Tool execution and management",
        "services": [
            {"name": "ToolExecutionService", "methods": ["ExecuteTool", "GetToolResult", "ListAvailableTools"]},
            {"name": "ToolRegistryService", "methods": ["RegisterTool", "UnregisterTool", "GetToolDefinition"]}
        ]
    },
    "eval-service": {
        "port": 8011,
        "protocol": "http",
        "description": "Model evaluation and quality assurance",
        "endpoints": [
            {"path": "/v1/evaluations", "method": "POST", "description": "Start evaluation"},
            {"path": "/v1/evaluations/{eval_id}", "method": "GET", "description": "Get evaluation results"},
            {"path": "/v1/benchmarks", "method": "GET", "description": "List benchmarks"},
            {"path": "/v1/models/{model_id}/evaluate", "method": "POST", "description": "Evaluate model"}
        ]
    },
    "capacity-monitor": {
        "port": 8012,
        "protocol": "http",
        "description": "Resource monitoring and capacity planning",
        "endpoints": [
            {"path": "/v1/metrics", "method": "GET", "description": "Get system metrics"},
            {"path": "/v1/capacity/forecast", "method": "GET", "description": "Get capacity forecast"},
            {"path": "/v1/alerts", "method": "GET", "description": "List active alerts"},
            {"path": "/v1/resources/{resource_id}/usage", "method": "GET", "description": "Get resource usage"}
        ]
    },
    "admin-portal": {
        "port": 8100,
        "protocol": "http",
        "description": "Backend admin interface for tenant management",
        "endpoints": [
            {"path": "/v1/admin/tenants", "method": "GET", "description": "List all tenants"},
            {"path": "/v1/admin/tenants/{tenant_id}/suspend", "method": "POST", "description": "Suspend tenant"},
            {"path": "/v1/admin/system/status", "method": "GET", "description": "Get system status"},
            {"path": "/v1/admin/reports", "method": "GET", "description": "Get admin reports"}
        ]
    },
    "web-frontend": {
        "port": 3000,
        "protocol": "http",
        "description": "React frontend - API client only",
        "is_frontend": True
    }
}

def create_openapi_contract(service_name: str, config: Dict) -> None:
    """Create OpenAPI contract for HTTP services."""
    contracts_path = Path(f"apps/{service_name}/contracts")
    contracts_path.mkdir(exist_ok=True)
    
    openapi_file = contracts_path / "openapi.yaml"
    
    # Basic OpenAPI structure
    openapi_spec = {
        "openapi": "3.0.3",
        "info": {
            "title": f"{service_name.replace('-', ' ').title()} Service",
            "description": config["description"],
            "version": "1.0.0",
            "contact": {
                "name": "Platform Team",
                "email": "platform@company.com"
            },
            "license": {
                "name": "MIT",
                "url": "https://opensource.org/licenses/MIT"
            }
        },
        "servers": [
            {
                "url": f"http://localhost:{config['port']}",
                "description": "Development server"
            },
            {
                "url": f"https://api.company.com",
                "description": "Production server"
            }
        ],
        "security": [
            {"BearerAuth": []}
        ],
        "paths": {},
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT"
                }
            },
            "schemas": {
                "HealthResponse": {
                    "type": "object",
                    "required": ["status", "timestamp"],
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["healthy", "degraded", "unhealthy"]
                        },
                        "timestamp": {
                            "type": "string",
                            "format": "date-time"
                        },
                        "version": {
                            "type": "string"
                        },
                        "components": {
                            "type": "object",
                            "additionalProperties": {"type": "string"}
                        }
                    }
                },
                "InfoResponse": {
                    "type": "object",
                    "required": ["service", "version"],
                    "properties": {
                        "service": {
                            "type": "string",
                            "example": service_name
                        },
                        "version": {
                            "type": "string",
                            "example": "1.0.0"
                        },
                        "description": {
                            "type": "string",
                            "example": config["description"]
                        },
                        "build_time": {
                            "type": "string",
                            "format": "date-time"
                        },
                        "commit_sha": {
                            "type": "string"
                        }
                    }
                },
                "ErrorResponse": {
                    "type": "object",
                    "required": ["error", "message"],
                    "properties": {
                        "error": {
                            "type": "string"
                        },
                        "message": {
                            "type": "string"
                        },
                        "details": {
                            "type": "object"
                        },
                        "trace_id": {
                            "type": "string"
                        }
                    }
                }
            }
        }
    }
    
    # Add standard endpoints
    openapi_spec["paths"]["/healthz"] = {
        "get": {
            "summary": "Health check endpoint",
            "operationId": "health_check",
            "tags": ["Health"],
            "security": [],
            "responses": {
                "200": {
                    "description": "Service is healthy",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/HealthResponse"}
                        }
                    }
                }
            }
        }
    }
    
    openapi_spec["paths"]["/v1/info"] = {
        "get": {
            "summary": "Service information",
            "operationId": "get_info",
            "tags": ["Info"],
            "security": [],
            "responses": {
                "200": {
                    "description": "Service information",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/InfoResponse"}
                        }
                    }
                }
            }
        }
    }
    
    # Add service-specific endpoints
    if "endpoints" in config:
        for endpoint in config["endpoints"]:
            path = endpoint["path"]
            method = endpoint["method"].lower()
            
            if path not in openapi_spec["paths"]:
                openapi_spec["paths"][path] = {}
            
            openapi_spec["paths"][path][method] = {
                "summary": endpoint["description"],
                "operationId": f"{method}_{path.replace('/', '_').replace('{', '').replace('}', '')}".lower(),
                "tags": [service_name.replace('-', ' ').title()],
                "responses": {
                    "200": {
                        "description": "Success response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {"type": "boolean"},
                                        "data": {"type": "object"}
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Bad request",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        }
                    },
                    "401": {
                        "description": "Unauthorized",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        }
                    },
                    "500": {
                        "description": "Internal server error",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        }
                    }
                }
            }
            
            # Add request body for POST/PUT methods
            if method in ["post", "put", "patch"]:
                openapi_spec["paths"][path][method]["requestBody"] = {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "data": {"type": "object"}
                                }
                            }
                        }
                    }
                }
    
    # Write the OpenAPI spec
    with open(openapi_file, 'w') as f:
        yaml.dump(openapi_spec, f, default_flow_style=False, sort_keys=False)

def create_grpc_contract(service_name: str, config: Dict) -> None:
    """Create gRPC proto files for gRPC services."""
    contracts_path = Path(f"apps/{service_name}/contracts")
    contracts_path.mkdir(exist_ok=True)
    
    # Create health.proto
    health_proto = contracts_path / "health.proto"
    health_content = f'''syntax = "proto3";

package {service_name.replace('-', '_')}.health.v1;
option go_package = "github.com/company/multi-ai-agent/{service_name}/gen/health/v1";

// Health check service
service HealthService {{
  // Check service health
  rpc Check(HealthCheckRequest) returns (HealthCheckResponse);
  
  // Watch service health (streaming)
  rpc Watch(HealthCheckRequest) returns (stream HealthCheckResponse);
}}

message HealthCheckRequest {{
  string service = 1;
}}

message HealthCheckResponse {{
  enum ServingStatus {{
    UNKNOWN = 0;
    SERVING = 1;
    NOT_SERVING = 2;
    SERVICE_UNKNOWN = 3;
  }}
  ServingStatus status = 1;
}}'''
    health_proto.write_text(health_content)
    
    # Create info.proto
    info_proto = contracts_path / "info.proto"
    info_content = f'''syntax = "proto3";

package {service_name.replace('-', '_')}.info.v1;
option go_package = "github.com/company/multi-ai-agent/{service_name}/gen/info/v1";

import "google/protobuf/timestamp.proto";

// Service information
service InfoService {{
  // Get service information
  rpc GetInfo(InfoRequest) returns (InfoResponse);
}}

message InfoRequest {{
  // Empty request
}}

message InfoResponse {{
  string service_name = 1;
  string version = 2;
  string description = 3;
  google.protobuf.Timestamp build_time = 4;
  string commit_sha = 5;
  map<string, string> metadata = 6;
}}'''
    info_proto.write_text(info_content)
    
    # Create service-specific proto
    if "services" in config:
        service_proto = contracts_path / f"{service_name.replace('-', '_')}.proto"
        proto_content = f'''syntax = "proto3";

package {service_name.replace('-', '_')}.v1;
option go_package = "github.com/company/multi-ai-agent/{service_name}/gen/v1";

import "google/protobuf/empty.proto";
import "google/protobuf/timestamp.proto";

'''
        
        # Add service definitions
        for service_def in config["services"]:
            proto_content += f'''// {config["description"]}
service {service_def["name"]} {{
'''
            for method in service_def["methods"]:
                proto_content += f'  rpc {method}({method}Request) returns ({method}Response);\\n'
            
            proto_content += "}\\n\\n"
            
            # Add message definitions
            for method in service_def["methods"]:
                proto_content += f'''message {method}Request {{
  // TODO: Define request fields
  string request_id = 1;
}}

message {method}Response {{
  // TODO: Define response fields
  string response_id = 1;
  bool success = 2;
  string message = 3;
}}

'''
        
        service_proto.write_text(proto_content)

def create_codegen_config(service_name: str, config: Dict) -> None:
    """Create codegen configuration for a service."""
    contracts_path = Path(f"apps/{service_name}/contracts")
    
    if config["protocol"] == "http":
        # Create OpenAPI codegen config
        codegen_config = {
            "generators": {
                "python-client": {
                    "generator": "python",
                    "output": "../gen/python-client",
                    "config": {
                        "packageName": f"{service_name.replace('-', '_')}_client",
                        "projectName": f"{service_name}-client",
                        "packageVersion": "1.0.0"
                    }
                },
                "typescript-client": {
                    "generator": "typescript-axios",
                    "output": "../gen/typescript-client",
                    "config": {
                        "npmName": f"@company/{service_name}-client",
                        "npmVersion": "1.0.0",
                        "supportsES6": True
                    }
                },
                "go-client": {
                    "generator": "go",
                    "output": "../gen/go-client",
                    "config": {
                        "packageName": f"{service_name.replace('-', '_')}",
                        "moduleName": f"github.com/company/multi-ai-agent/{service_name}/gen/go-client"
                    }
                }
            }
        }
        
        codegen_file = contracts_path / "codegen.yaml"
        with open(codegen_file, 'w') as f:
            yaml.dump(codegen_config, f, default_flow_style=False)
        
        # Create orval config for TypeScript (alternative)
        orval_config = {
            service_name: {
                "input": {
                    "target": "./openapi.yaml"
                },
                "output": {
                    "target": "../gen/typescript-orval/api.ts",
                    "schemas": "../gen/typescript-orval/models",
                    "client": "axios",
                    "mode": "split"
                }
            }
        }
        
        orval_file = contracts_path / "orval.config.ts"
        orval_content = f'''import {{ defineConfig }} from 'orval';

export default defineConfig({json.dumps(orval_config, indent=2)});'''
        orval_file.write_text(orval_content)
        
    elif config["protocol"] == "grpc":
        # Create buf.gen.yaml for gRPC
        buf_config = {
            "version": "v1",
            "plugins": [
                {
                    "plugin": "buf.build/protocolbuffers/go",
                    "out": "../gen/go",
                    "opt": ["paths=source_relative"]
                },
                {
                    "plugin": "buf.build/grpc/go", 
                    "out": "../gen/go",
                    "opt": ["paths=source_relative"]
                },
                {
                    "plugin": "buf.build/protocolbuffers/python",
                    "out": "../gen/python"
                },
                {
                    "plugin": "buf.build/grpc/python",
                    "out": "../gen/python"
                },
                {
                    "plugin": "buf.build/timostamm/protobuf-ts",
                    "out": "../gen/typescript"
                }
            ]
        }
        
        buf_file = contracts_path / "buf.gen.yaml"
        with open(buf_file, 'w') as f:
            yaml.dump(buf_config, f, default_flow_style=False)
        
        # Create buf.yaml for proto file management
        buf_yaml = {
            "version": "v1",
            "breaking": {
                "use": ["FILE"]
            },
            "lint": {
                "use": ["DEFAULT"]
            }
        }
        
        buf_file = contracts_path / "buf.yaml"
        with open(buf_file, 'w') as f:
            yaml.dump(buf_yaml, f, default_flow_style=False)

def create_makefile_targets(service_name: str, config: Dict) -> None:
    """Add codegen targets to service Makefile."""
    makefile_path = Path(f"apps/{service_name}/Makefile")
    
    if not makefile_path.exists():
        return
    
    # Read existing Makefile
    with open(makefile_path, 'r') as f:
        makefile_content = f.read()
    
    # Add codegen targets
    if config["protocol"] == "http":
        codegen_targets = '''
# Code generation targets
.PHONY: generate-clients clean-generated

generate-clients: ## Generate API clients from OpenAPI spec
	@echo "Generating API clients from OpenAPI spec..."
	cd contracts && \\
	openapi-generator-cli generate -i openapi.yaml -g python -o ../gen/python-client --config codegen.yaml && \\
	openapi-generator-cli generate -i openapi.yaml -g typescript-axios -o ../gen/typescript-client --config codegen.yaml && \\
	openapi-generator-cli generate -i openapi.yaml -g go -o ../gen/go-client --config codegen.yaml

generate-orval: ## Generate TypeScript client using Orval
	@echo "Generating TypeScript client with Orval..."
	cd contracts && npx orval

clean-generated: ## Clean generated client code
	rm -rf gen/'''
    
    elif config["protocol"] == "grpc":
        codegen_targets = '''
# Code generation targets
.PHONY: generate-clients clean-generated buf-lint buf-breaking

generate-clients: ## Generate gRPC clients from proto files
	@echo "Generating gRPC clients from proto files..."
	cd contracts && buf generate

buf-lint: ## Lint proto files
	cd contracts && buf lint

buf-breaking: ## Check for breaking changes
	cd contracts && buf breaking --against '.git#branch=main'

clean-generated: ## Clean generated client code
	rm -rf gen/'''
    
    # Add to Makefile if not already present
    if "generate-clients" not in makefile_content:
        makefile_content += codegen_targets
        
        with open(makefile_path, 'w') as f:
            f.write(makefile_content)

def update_service_readme(service_name: str, config: Dict) -> None:
    """Update service README with codegen instructions."""
    readme_path = Path(f"apps/{service_name}/README.md")
    
    if not readme_path.exists():
        return
    
    # Read existing README
    with open(readme_path, 'r') as f:
        readme_content = f.read()
    
    # Add codegen section
    if config["protocol"] == "http":
        codegen_section = f'''
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
from {service_name.replace('-', '_')}_client import ApiClient, Configuration
from {service_name.replace('-', '_')}_client.api.default_api import DefaultApi

config = Configuration(host="http://localhost:{config['port']}")
client = ApiClient(config)
api = DefaultApi(client)

# Check health
health = api.health_check()
print(health.status)
```

#### TypeScript
```typescript
import {{ DefaultApi, Configuration }} from '@company/{service_name}-client';

const config = new Configuration({{
  basePath: 'http://localhost:{config['port']}'
}});
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
    "{service_name.replace('-', '_')}"
)

func main() {{
    config := {service_name.replace('-', '_')}.NewConfiguration()
    config.BasePath = "http://localhost:{config['port']}"
    client := {service_name.replace('-', '_')}.NewAPIClient(config)
    
    health, _, err := client.DefaultApi.HealthCheck(context.Background())
    if err != nil {{
        log.Fatal(err)
    }}
    fmt.Println(health.Status)
}}
```'''
    
    elif config["protocol"] == "grpc":
        codegen_section = f'''
## 📋 gRPC Contracts & Code Generation

### Protocol Buffer Definitions

The service gRPC API is defined in:
- [`contracts/health.proto`](contracts/health.proto) - Health check service
- [`contracts/info.proto`](contracts/info.proto) - Service information
- [`contracts/{service_name.replace('-', '_')}.proto`](contracts/{service_name.replace('-', '_')}.proto) - Main service API

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
    healthpb "github.com/company/multi-ai-agent/{service_name}/gen/health/v1"
)

func main() {{
    conn, err := grpc.Dial("localhost:{config['port']}", grpc.WithInsecure())
    if err != nil {{
        log.Fatal(err)
    }}
    defer conn.Close()
    
    client := healthpb.NewHealthServiceClient(conn)
    resp, err := client.Check(context.Background(), &healthpb.HealthCheckRequest{{
        Service: "{service_name}",
    }})
    if err != nil {{
        log.Fatal(err)
    }}
    fmt.Println(resp.Status)
}}
```

#### Python
```python
import grpc
from gen.python.health_pb2 import HealthCheckRequest
from gen.python.health_pb2_grpc import HealthServiceStub

channel = grpc.insecure_channel('localhost:{config['port']}')
client = HealthServiceStub(channel)

request = HealthCheckRequest(service='{service_name}')
response = client.Check(request)
print(response.status)
```

#### TypeScript
```typescript
import {{ GrpcWebFetchTransport }} from "@protobuf-ts/grpcweb-transport";
import {{ HealthServiceClient }} from "./gen/typescript/health";

const transport = new GrpcWebFetchTransport({{
  baseUrl: "http://localhost:{config['port']}"
}});
const client = new HealthServiceClient(transport);

const {{ response }} = await client.check({{
  service: "{service_name}"
}});
console.log(response.status);
```'''
    
    # Add section if not present
    if "API Contracts" not in readme_content and "gRPC Contracts" not in readme_content:
        # Insert before "Deployment" section if it exists, otherwise at the end
        if "## Deployment" in readme_content:
            readme_content = readme_content.replace("## Deployment", codegen_section + "\\n\\n## Deployment")
        else:
            readme_content += codegen_section
        
        with open(readme_path, 'w') as f:
            f.write(readme_content)

def create_shared_contracts() -> None:
    """Create shared contracts directory with truly shared schemas."""
    contracts_path = Path("contracts")
    contracts_path.mkdir(exist_ok=True)
    
    # Create shared OpenAPI schemas
    shared_openapi = contracts_path / "shared.yaml"
    shared_content = {
        "openapi": "3.0.3",
        "info": {
            "title": "Shared Platform Schemas",
            "description": "Common schemas and types used across multiple services",
            "version": "1.0.0"
        },
        "components": {
            "schemas": {
                "TenantContext": {
                    "type": "object",
                    "required": ["tenant_id", "plan_tier"],
                    "properties": {
                        "tenant_id": {
                            "type": "string",
                            "format": "uuid",
                            "description": "Unique tenant identifier"
                        },
                        "plan_tier": {
                            "type": "string",
                            "enum": ["free", "pro", "enterprise"],
                            "description": "Tenant subscription tier"
                        },
                        "region": {
                            "type": "string",
                            "description": "Geographic region"
                        },
                        "features": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Enabled features for this tenant"
                        }
                    }
                },
                "ErrorResponse": {
                    "type": "object",
                    "required": ["error", "message"],
                    "properties": {
                        "error": {
                            "type": "string",
                            "description": "Error code"
                        },
                        "message": {
                            "type": "string",
                            "description": "Human-readable error message"
                        },
                        "details": {
                            "type": "object",
                            "description": "Additional error details"
                        },
                        "trace_id": {
                            "type": "string",
                            "description": "Request trace identifier"
                        }
                    }
                },
                "PaginationRequest": {
                    "type": "object",
                    "properties": {
                        "page": {
                            "type": "integer",
                            "minimum": 1,
                            "default": 1,
                            "description": "Page number"
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 20,
                            "description": "Items per page"
                        },
                        "sort": {
                            "type": "string",
                            "description": "Sort field and direction (e.g., 'created_at:desc')"
                        }
                    }
                },
                "PaginationResponse": {
                    "type": "object",
                    "required": ["total", "page", "limit", "pages"],
                    "properties": {
                        "total": {
                            "type": "integer",
                            "description": "Total number of items"
                        },
                        "page": {
                            "type": "integer",
                            "description": "Current page number"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Items per page"
                        },
                        "pages": {
                            "type": "integer",
                            "description": "Total number of pages"
                        }
                    }
                },
                "AuditMetadata": {
                    "type": "object",
                    "required": ["created_at", "created_by"],
                    "properties": {
                        "created_at": {
                            "type": "string",
                            "format": "date-time",
                            "description": "Creation timestamp"
                        },
                        "created_by": {
                            "type": "string",
                            "description": "User who created the resource"
                        },
                        "updated_at": {
                            "type": "string",
                            "format": "date-time",
                            "description": "Last update timestamp"
                        },
                        "updated_by": {
                            "type": "string",
                            "description": "User who last updated the resource"
                        }
                    }
                }
            }
        }
    }
    
    with open(shared_openapi, 'w') as f:
        yaml.dump(shared_content, f, default_flow_style=False, sort_keys=False)
    
    # Create shared proto definitions
    shared_proto = contracts_path / "shared.proto"
    shared_proto_content = '''syntax = "proto3";

package platform.shared.v1;
option go_package = "github.com/company/multi-ai-agent/contracts/gen/v1";

import "google/protobuf/timestamp.proto";

// Tenant context information
message TenantContext {
  string tenant_id = 1;
  PlanTier plan_tier = 2;
  string region = 3;
  repeated string features = 4;
}

// Subscription plan tiers
enum PlanTier {
  PLAN_TIER_UNSPECIFIED = 0;
  PLAN_TIER_FREE = 1;
  PLAN_TIER_PRO = 2;
  PLAN_TIER_ENTERPRISE = 3;
}

// Standard error response
message ErrorResponse {
  string error = 1;
  string message = 2;
  map<string, string> details = 3;
  string trace_id = 4;
}

// Pagination request
message PaginationRequest {
  int32 page = 1;
  int32 limit = 2;
  string sort = 3;
}

// Pagination response
message PaginationResponse {
  int32 total = 1;
  int32 page = 2;
  int32 limit = 3;
  int32 pages = 4;
}

// Audit metadata
message AuditMetadata {
  google.protobuf.Timestamp created_at = 1;
  string created_by = 2;
  google.protobuf.Timestamp updated_at = 3;
  string updated_by = 4;
}'''
    shared_proto.write_text(shared_proto_content)
    
    # Create README for shared contracts
    contracts_readme = contracts_path / "README.md"
    readme_content = '''# Shared Platform Contracts

This directory contains truly shared schemas and types used across multiple services in the Multi-AI-Agent platform.

## ⚠️ **Important Guidelines**

### What Belongs Here
- **Shared enums** used by 3+ services (e.g., PlanTier, Status codes)
- **Common data structures** (e.g., TenantContext, PaginationRequest)
- **Standard error formats** (e.g., ErrorResponse)
- **Cross-cutting types** (e.g., AuditMetadata)

### What Does NOT Belong Here
- **Service-specific schemas** (belong in `apps/<service>/contracts/`)
- **Internal service models** (not exposed via API)
- **Temporary or experimental types**
- **Single-service enums or types**

## 📁 Files

### `shared.yaml`
OpenAPI 3.0 shared schemas for HTTP services.

### `shared.proto`
Protocol Buffer shared definitions for gRPC services.

## 🔄 Versioning Strategy

### Semantic Versioning
- **Major version** (v2.0.0): Breaking changes requiring all services to update
- **Minor version** (v1.1.0): New optional fields or types
- **Patch version** (v1.0.1): Bug fixes and clarifications

### Breaking Change Process
1. **Deprecation**: Mark old fields as deprecated in v1.x
2. **Transition Period**: Services update to use new fields
3. **Removal**: Remove deprecated fields in v2.0
4. **Communication**: Announce breaking changes 30 days in advance

### Backwards Compatibility
- ✅ **Adding optional fields**: Safe, increment minor version
- ✅ **Adding new enum values**: Safe with proper handling
- ✅ **Deprecating fields**: Safe, mark with `deprecated: true`
- ❌ **Removing fields**: Breaking change, requires major version
- ❌ **Changing field types**: Breaking change
- ❌ **Making optional fields required**: Breaking change

## 🔧 Code Generation

### Generate Clients
```bash
# Generate all language clients
make generate-shared-clients

# Language-specific generation
make generate-go-shared
make generate-python-shared  
make generate-typescript-shared
```

### Using Shared Types

#### In Service OpenAPI Specs
```yaml
# Reference shared schemas
components:
  schemas:
    UserResponse:
      allOf:
        - $ref: '../../../contracts/shared.yaml#/components/schemas/AuditMetadata'
        - type: object
          properties:
            name:
              type: string
```

#### In Service Proto Files
```protobuf
import "contracts/shared.proto";

message User {
  string name = 1;
  platform.shared.v1.AuditMetadata audit = 2;
}
```

## 📊 Usage Tracking

### Current Consumers

| Schema | Services Using | Version |
|--------|---------------|---------|
| `TenantContext` | api-gateway, billing-service, tenant-service | v1.0.0 |
| `ErrorResponse` | All HTTP services | v1.0.0 |
| `PaginationRequest` | analytics-service, admin-portal | v1.0.0 |
| `AuditMetadata` | tenant-service, billing-service | v1.0.0 |

### Change Impact Analysis

Before making changes:
1. Check usage in all services
2. Assess backward compatibility impact
3. Plan migration strategy for breaking changes
4. Update all consuming services simultaneously

## 🚀 Best Practices

### Schema Design
- **Use descriptive names**: `PlanTier` not `Tier`
- **Include descriptions**: Every field should have clear documentation
- **Follow conventions**: Use `snake_case` for fields, `PascalCase` for types
- **Validate constraints**: Use appropriate formats, minimums, maximums

### Evolution Strategy
- **Start restrictive**: Easier to loosen constraints than tighten them
- **Plan for growth**: Consider future use cases in initial design
- **Document decisions**: Include reasoning in schema descriptions
- **Test thoroughly**: Validate with all consuming services

## 📞 Contact

For questions about shared contracts:
- **Platform Team**: platform@company.com
- **Architecture Reviews**: Schedule via #architecture channel
- **Breaking Changes**: Notify #breaking-changes channel'''
    
    contracts_readme.write_text(readme_content)

def main():
    """Generate contracts and codegen for all services."""
    print("🎯 Generating Contracts & Code Generation Configuration...")
    print("=" * 60)
    
    # Create shared contracts first
    print("\\n📋 Creating shared contracts...")
    create_shared_contracts()
    print("  ✅ Shared OpenAPI schemas created")
    print("  ✅ Shared proto definitions created")
    print("  ✅ Contracts README created")
    
    # Process each service
    for service_name, config in SERVICES_CONFIG.items():
        if config.get("is_frontend"):
            print(f"\\n🎨 Skipping {service_name} (frontend service)")
            continue
            
        print(f"\\n🔧 Processing {service_name} ({config['protocol']})...")
        
        if config["protocol"] == "http":
            create_openapi_contract(service_name, config)
            print(f"  ✅ OpenAPI contract created")
        elif config["protocol"] == "grpc":
            create_grpc_contract(service_name, config)
            print(f"  ✅ gRPC proto files created")
        
        create_codegen_config(service_name, config)
        print(f"  ✅ Codegen configuration created")
        
        create_makefile_targets(service_name, config)
        print(f"  ✅ Makefile targets added")
        
        update_service_readme(service_name, config)
        print(f"  ✅ README updated with codegen instructions")
    
    print("\\n🎉 Contracts & Code Generation Complete!")
    print("\\n📊 Summary:")
    http_services = [s for s, c in SERVICES_CONFIG.items() if c.get("protocol") == "http" and not c.get("is_frontend")]
    grpc_services = [s for s, c in SERVICES_CONFIG.items() if c.get("protocol") == "grpc"]
    
    print(f"  • HTTP Services: {len(http_services)} (OpenAPI contracts)")
    print(f"  • gRPC Services: {len(grpc_services)} (Protocol Buffer contracts)")
    print(f"  • Shared Contracts: 1 (OpenAPI + Proto)")
    print(f"  • Total Contracts: {len(http_services) + len(grpc_services) + 1}")
    
    print("\\n🔧 Next Steps:")
    print("  1. Install codegen tools:")
    print("     - npm install -g @openapitools/openapi-generator-cli")
    print("     - npm install -g orval")  
    print("     - go install github.com/bufbuild/buf/cmd/buf@latest")
    print("  2. Generate clients: cd apps/<service> && make generate-clients")
    print("  3. Test generated clients in your applications")

if __name__ == "__main__":
    main()
