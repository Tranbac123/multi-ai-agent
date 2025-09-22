#!/usr/bin/env python3
"""
Complete microservices structure for all services based on approved plan.
"""

import os
import json
from pathlib import Path
from typing import Dict, List

# Service configurations
SERVICES_CONFIG = {
    "api-gateway": {
        "port": 8000,
        "description": "Main entry point with authentication, rate limiting, and routing",
        "tech": "FastAPI + JWT",
        "type": "backend"
    },
    "analytics-service": {
        "port": 8005,
        "description": "CQRS read-only analytics and reporting", 
        "tech": "Python + CQRS",
        "type": "backend"
    },
    "orchestrator": {
        "port": 8002,
        "description": "FSM/LangGraph workflow execution with resilient tool adapters",
        "tech": "Python + LangGraph",
        "type": "backend"
    },
    "router-service": {
        "port": 8003,
        "description": "Intelligent request routing with feature store and bandit policy",
        "tech": "Python + ML",
        "type": "backend"
    },
    "realtime": {
        "port": 8004,
        "description": "WebSocket service with backpressure handling",
        "tech": "ASGI + Redis",
        "type": "backend"
    },
    "ingestion": {
        "port": 8006,
        "description": "Document processing and knowledge management",
        "tech": "Python Workers",
        "type": "backend"
    },
    "billing-service": {
        "port": 8007,
        "description": "Usage tracking and billing engine",
        "tech": "Python + Webhooks",
        "type": "backend"
    },
    "tenant-service": {
        "port": 8008,
        "description": "Self-serve tenant onboarding and management",
        "tech": "Python + FastAPI",
        "type": "backend"
    },
    "chat-adapters": {
        "port": 8009,
        "description": "Multi-channel chat integration",
        "tech": "Python + FastAPI",
        "type": "backend"
    },
    "tool-service": {
        "port": 8010,
        "description": "Tool execution and management",
        "tech": "Python + AsyncIO",
        "type": "backend"
    },
    "eval-service": {
        "port": 8011,
        "description": "Model evaluation and quality assurance",
        "tech": "Python + ML",
        "type": "backend"
    },
    "capacity-monitor": {
        "port": 8012,
        "description": "Resource monitoring and capacity planning",
        "tech": "Python + Prometheus",
        "type": "backend"
    },
    "admin-portal": {
        "port": 8100,
        "description": "Backend admin interface for tenant management",
        "tech": "FastAPI + Jinja2",
        "type": "backend"
    },
    "web-frontend": {
        "port": 3000,
        "description": "Frontend user interface",
        "tech": "React + TypeScript",
        "type": "frontend"
    }
}

def ensure_directory_structure(service_name: str) -> None:
    """Ensure complete directory structure for a service."""
    base_path = Path(f"apps/{service_name}")
    base_path.mkdir(exist_ok=True)
    
    # Required directories
    directories = [
        "src", "db", "contracts", "deploy", "observability", "tests",
        "deploy/base", "deploy/overlays/dev", "deploy/overlays/staging", "deploy/overlays/prod",
        "observability/dashboards", ".github/workflows"
    ]
    
    for directory in directories:
        (base_path / directory).mkdir(parents=True, exist_ok=True)

def create_tests_structure(service_name: str) -> None:
    """Create tests structure for a service."""
    base_path = Path(f"apps/{service_name}")
    tests_path = base_path / "tests"
    
    # Create test directories
    test_dirs = ["unit", "integration", "fixtures"]
    for test_dir in test_dirs:
        (tests_path / test_dir).mkdir(exist_ok=True)
    
    # Create __init__.py files
    for test_dir in ["", "unit", "integration", "fixtures"]:
        init_file = tests_path / test_dir / "__init__.py" if test_dir else tests_path / "__init__.py"
        if not init_file.exists():
            init_file.write_text("")
    
    # Create basic test files
    config = SERVICES_CONFIG[service_name]
    
    # Unit test example
    unit_test = tests_path / "unit" / f"test_{service_name.replace('-', '_')}.py"
    if not unit_test.exists():
        unit_test.write_text(f'''"""
Unit tests for {service_name.title()} service.
"""

import pytest
from fastapi.testclient import TestClient


class Test{service_name.replace('-', '').title()}Service:
    """Test suite for {service_name} service."""
    
    def test_health_endpoint(self):
        """Test health check endpoint."""
        # TODO: Implement health check test
        pass
    
    def test_service_initialization(self):
        """Test service can be initialized properly."""
        # TODO: Implement initialization test
        pass
''')
    
    # Integration test example
    integration_test = tests_path / "integration" / f"test_{service_name.replace('-', '_')}_integration.py"
    if not integration_test.exists():
        integration_test.write_text(f'''"""
Integration tests for {service_name.title()} service.
"""

import pytest
import asyncio


class Test{service_name.replace('-', '').title()}Integration:
    """Integration test suite for {service_name} service."""
    
    @pytest.mark.asyncio
    async def test_database_connection(self):
        """Test database connectivity."""
        # TODO: Implement database connection test
        pass
    
    @pytest.mark.asyncio
    async def test_redis_connection(self):
        """Test Redis connectivity."""
        # TODO: Implement Redis connection test
        pass
''')
    
    # Create conftest.py
    conftest = tests_path / "conftest.py"
    if not conftest.exists():
        conftest.write_text(f'''"""
Test configuration for {service_name.title()} service.
"""

import pytest
import asyncio
from typing import Generator


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_config():
    """Test configuration."""
    return {{
        "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
        "REDIS_URL": "redis://localhost:6379/1",
        "ENVIRONMENT": "test"
    }}
''')

def create_observability_files(service_name: str, config: Dict) -> None:
    """Create observability files for a service."""
    base_path = Path(f"apps/{service_name}")
    obs_path = base_path / "observability"
    
    # Create dashboards.json
    dashboards_file = obs_path / "dashboards" / f"{service_name}.json"
    if not dashboards_file.exists():
        dashboard_content = {
            "dashboard": {
                "id": None,
                "title": f"{service_name.title()} Metrics",
                "tags": [service_name, "microservices"],
                "timezone": "browser",
                "panels": [
                    {
                        "id": 1,
                        "title": "Request Rate",
                        "type": "graph",
                        "targets": [
                            {
                                "expr": f"rate(http_requests_total{{service=\"{service_name}\"}}[5m])",
                                "legendFormat": "{{method}} {{status}}"
                            }
                        ]
                    },
                    {
                        "id": 2,
                        "title": "Response Time P95",
                        "type": "graph",
                        "targets": [
                            {
                                "expr": f"histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{{service=\"{service_name}\"}}[5m]))",
                                "legendFormat": "95th percentile"
                            }
                        ]
                    },
                    {
                        "id": 3,
                        "title": "Error Rate",
                        "type": "singlestat",
                        "targets": [
                            {
                                "expr": f"rate(http_requests_total{{service=\"{service_name}\",status=~\"5..\"}}[5m]) / rate(http_requests_total{{service=\"{service_name}\"}}[5m]) * 100"
                            }
                        ],
                        "format": "percent"
                    }
                ],
                "time": {
                    "from": "now-1h",
                    "to": "now"
                },
                "refresh": "5s"
            }
        }
        dashboards_file.write_text(json.dumps(dashboard_content, indent=2))
    
    # Create alerts.yaml
    alerts_file = obs_path / "alerts.yaml"
    if not alerts_file.exists():
        alerts_content = f'''groups:
  - name: {service_name}_alerts
    rules:
      - alert: {service_name.replace('-', '_').title()}HighErrorRate
        expr: rate(http_requests_total{{service="{service_name}",status=~"5.."}}[5m]) / rate(http_requests_total{{service="{service_name}"}}[5m]) > 0.01
        for: 5m
        labels:
          severity: critical
          service: {service_name}
        annotations:
          summary: "High error rate on {service_name}"
          description: "Error rate is above 1% for 5 minutes"

      - alert: {service_name.replace('-', '_').title()}HighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m])) > 1.0
        for: 5m
        labels:
          severity: warning
          service: {service_name}
        annotations:
          summary: "High latency on {service_name}"
          description: "P95 latency is above 1 second for 5 minutes"

      - alert: {service_name.replace('-', '_').title()}ServiceDown
        expr: up{{service="{service_name}"}} == 0
        for: 2m
        labels:
          severity: critical
          service: {service_name}
        annotations:
          summary: "{service_name} service is down"
          description: "Service has been down for more than 2 minutes"
'''
        alerts_file.write_text(alerts_content)
    
    # Create SLO.md
    slo_file = obs_path / "SLO.md"
    if not slo_file.exists():
        slo_content = f'''# {service_name.title()} Service Level Objectives (SLO)

## Service Level Indicators (SLIs)

| Metric | Description | Target | Error Budget |
|--------|-------------|---------|--------------|
| **Availability** | Percentage of successful requests | 99.9% | 0.1% |
| **Latency (p50)** | 50th percentile response time | < 100ms | < 200ms |
| **Latency (p95)** | 95th percentile response time | < 500ms | < 1000ms |
| **Error Rate** | Percentage of 5xx responses | < 0.1% | < 1% |

## Monitoring Queries

### Availability
```promql
(
  sum(rate(http_requests_total{{service="{service_name}",status!~"5.."}}[5m])) /
  sum(rate(http_requests_total{{service="{service_name}"}}[5m]))
) * 100
```

### Latency P95
```promql
histogram_quantile(0.95,
  rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m])
) * 1000
```

### Error Rate
```promql
(
  sum(rate(http_requests_total{{service="{service_name}",status=~"5.."}}[5m])) /
  sum(rate(http_requests_total{{service="{service_name}"}}[5m]))
) * 100
```

## Alerting Rules

### Critical Alerts
- **High Error Rate**: Error rate > 1% for 5 minutes
- **High Latency**: P95 latency > 1000ms for 5 minutes
- **Service Down**: Availability < 95% for 2 minutes

### Warning Alerts
- **Elevated Error Rate**: Error rate > 0.5% for 10 minutes
- **Elevated Latency**: P95 latency > 500ms for 10 minutes
- **Low Availability**: Availability < 99% for 5 minutes

## Error Budget Burn Rate

| Period | Budget Consumption | Alert Threshold |
|--------|-------------------|-----------------|
| 1 hour | 5% | Page immediately |
| 6 hours | 10% | Page immediately |
| 24 hours | 25% | Ticket creation |
| 72 hours | 50% | Review required |
'''
        slo_file.write_text(slo_content)
    
    # Create runbook.md
    runbook_file = obs_path / "runbook.md"
    if not runbook_file.exists():
        runbook_content = f'''# {service_name.title()} Service Runbook

## Service Overview
{config["description"]}

**Technology**: {config["tech"]}
**Port**: {config["port"]}

## Common Issues

### High Error Rate (5xx responses)

**Symptoms:**
- Increased 5xx error rate
- Client complaints about service unavailability

**Investigation:**
1. Check service logs: `kubectl logs -l app={service_name} -n production`
2. Verify database connectivity
3. Check Redis connectivity (if applicable)
4. Review recent deployments

**Resolution:**
- If database issues: Check connection pool settings
- If Redis issues: Restart Redis or check memory usage
- If application issues: Rollback recent deployment

### High Latency

**Symptoms:**
- P95 latency > 1000ms
- Slow response times reported by clients

**Investigation:**
1. Check downstream service health
2. Review database query performance
3. Examine Redis response times (if applicable)
4. Check CPU/Memory utilization

**Resolution:**
- Scale up replicas if CPU/Memory high
- Optimize slow queries
- Add caching for frequently accessed data

### Service Down

**Symptoms:**
- Service not responding to health checks
- 0% availability

**Investigation:**
1. Check pod status: `kubectl get pods -l app={service_name} -n production`
2. Check logs: `kubectl logs -l app={service_name} -n production --tail=100`
3. Check resource limits and usage
4. Verify configuration

**Resolution:**
- Restart service: `kubectl rollout restart deployment/{service_name} -n production`
- Scale up if resource constrained
- Fix configuration issues if found

## Emergency Procedures

### Circuit Breaker Activation
```bash
# Enable maintenance mode
kubectl patch configmap {service_name}-config -p '{{"data":{{"MAINTENANCE_MODE":"true"}}}}'
kubectl rollout restart deployment/{service_name}
```

### Scaling Under Load
```bash
# Emergency scale up
kubectl scale deployment {service_name} --replicas=10
```

## Monitoring Links
- [Grafana Dashboard](http://grafana.company.com/d/{service_name})
- [Prometheus Alerts](http://prometheus.company.com/alerts)
- [Log Aggregation](http://logs.company.com/{service_name})

## On-call Checklist
- [ ] Check service health endpoint
- [ ] Verify database connectivity
- [ ] Check Redis connectivity (if applicable)
- [ ] Review recent deployments
- [ ] Check resource utilization
- [ ] Verify downstream service health
'''
        runbook_file.write_text(runbook_content)

def create_contracts(service_name: str, config: Dict) -> None:
    """Create OpenAPI contract for a service."""
    base_path = Path(f"apps/{service_name}")
    contracts_path = base_path / "contracts"
    
    # Skip if already exists
    openapi_file = contracts_path / "openapi.yaml"
    if openapi_file.exists():
        return
        
    if config["type"] == "frontend":
        # Frontend doesn't need OpenAPI, create a simple spec
        spec_content = f'''# {service_name.title()} Frontend Specification

## Technology Stack
- **Framework**: React 18
- **Language**: TypeScript
- **Build Tool**: Vite
- **Styling**: TailwindCSS

## Environment Variables
- `VITE_API_BASE_URL`: Backend API URL
- `VITE_WS_URL`: WebSocket URL

## Build Commands
- `npm run dev`: Development server
- `npm run build`: Production build
- `npm run test`: Run tests
- `npm run lint`: Lint code
'''
        spec_file = contracts_path / "spec.md"
        spec_file.write_text(spec_content)
        return
    
    # Create OpenAPI spec for backend services
    openapi_content = f'''openapi: 3.0.3
info:
  title: {service_name.title()} Service
  description: {config["description"]}
  version: 1.0.0
  contact:
    name: Platform Team
    email: platform@company.com

servers:
  - url: http://localhost:{config["port"]}
    description: Development server
  - url: https://api.company.com
    description: Production server

security:
  - BearerAuth: []

paths:
  /health:
    get:
      summary: Health check endpoint
      operationId: health_check
      tags:
        - Health
      security: []
      responses:
        "200":
          description: Service is healthy
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/HealthResponse"

  /metrics:
    get:
      summary: Prometheus metrics endpoint
      operationId: metrics
      tags:
        - Monitoring
      security: []
      responses:
        "200":
          description: Prometheus metrics
          content:
            text/plain:
              schema:
                type: string

components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

  schemas:
    HealthResponse:
      type: object
      required:
        - status
        - timestamp
      properties:
        status:
          type: string
          enum: [healthy, degraded, unhealthy]
        timestamp:
          type: string
          format: date-time
        version:
          type: string
        components:
          type: object
          additionalProperties:
            type: string

    ErrorResponse:
      type: object
      required:
        - error
        - message
      properties:
        error:
          type: string
        message:
          type: string
        details:
          type: object
        trace_id:
          type: string
'''
    openapi_file.write_text(openapi_content)

def main():
    """Main function to complete service structures."""
    print("Completing microservices structure for all services...")
    
    for service_name, config in SERVICES_CONFIG.items():
        print(f"\\nProcessing {service_name}...")
        
        # 1. Ensure directory structure
        ensure_directory_structure(service_name)
        print(f"  ✓ Directory structure completed")
        
        # 2. Create tests structure
        create_tests_structure(service_name)
        print(f"  ✓ Tests structure created")
        
        # 3. Create observability files
        create_observability_files(service_name, config)
        print(f"  ✓ Observability files created")
        
        # 4. Create contracts
        create_contracts(service_name, config)
        print(f"  ✓ Contracts created")
    
    print("\\n🎉 All services have complete microservices structure!")
    print("\\nNext steps:")
    print("1. Review generated files in each service")
    print("2. Customize contracts and tests for each service")
    print("3. Test each service: cd apps/<service> && make test")

if __name__ == "__main__":
    main()
