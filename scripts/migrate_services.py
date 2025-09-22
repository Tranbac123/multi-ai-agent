#!/usr/bin/env python3
"""
Script to migrate existing services to the new microservices-standard structure.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict

# Service configuration
SERVICES_CONFIG = {
    "analytics-service": {
        "port": 8005,
        "description": "CQRS read-only analytics and reporting",
        "tech": "Python + CQRS"
    },
    "orchestrator": {
        "port": 8002,
        "description": "FSM/LangGraph workflow execution with resilient tool adapters",
        "tech": "Python + LangGraph"
    },
    "router-service": {
        "port": 8003,
        "description": "Intelligent request routing with feature store and bandit policy",
        "tech": "Python + ML"
    },
    "realtime": {
        "port": 8004,
        "description": "WebSocket service with backpressure handling",
        "tech": "ASGI + Redis"
    },
    "ingestion": {
        "port": 8006,
        "description": "Document processing and knowledge management",
        "tech": "Python Workers"
    },
    "billing-service": {
        "port": 8007,
        "description": "Usage tracking and billing engine",
        "tech": "Python + Webhooks"
    },
    "tenant-service": {
        "port": 8008,
        "description": "Self-serve tenant onboarding and management",
        "tech": "Python + FastAPI"
    },
    "chat-adapters": {
        "port": 8009,
        "description": "Multi-channel chat integration",
        "tech": "Python + FastAPI"
    },
    "tool-service": {
        "port": 8010,
        "description": "Tool execution and management",
        "tech": "Python + AsyncIO"
    },
    "eval-service": {
        "port": 8011,
        "description": "Model evaluation and quality assurance",
        "tech": "Python + ML"
    },
    "capacity-monitor": {
        "port": 8012,
        "description": "Resource monitoring and capacity planning",
        "tech": "Python + Prometheus"
    }
}

def create_service_structure(service_name: str, config: Dict) -> None:
    """Create the standardized directory structure for a service."""
    base_path = Path(f"apps/{service_name}")
    
    # Create directories
    directories = [
        "src", "db", "contracts", "deploy", "observability", "tests",
        "deploy/base", "deploy/overlays/dev", "deploy/overlays/staging", "deploy/overlays/prod",
        "observability/dashboards"
    ]
    
    for directory in directories:
        (base_path / directory).mkdir(parents=True, exist_ok=True)
    
    # Move existing source code if it exists
    old_path = Path(f"apps/{service_name}")
    if old_path.exists() and not (old_path / "src").exists():
        # Move existing files to src/
        for item in old_path.iterdir():
            if item.is_file() and item.suffix == ".py":
                shutil.move(str(item), str(base_path / "src" / item.name))
    
    # Create basic files
    create_dockerfile(base_path, service_name)
    create_requirements(base_path)
    create_makefile(base_path, service_name)
    create_readme(base_path, service_name, config)
    create_ci_workflow(base_path, service_name)
    create_openapi_contract(base_path, service_name, config)
    create_kustomize_files(base_path, service_name, config)
    create_observability_files(base_path, service_name, config)

def create_dockerfile(base_path: Path, service_name: str) -> None:
    """Create service Dockerfile."""
    dockerfile_content = f'''FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    build-essential \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements*.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY libs/ ./libs/

# Set Python path
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:{SERVICES_CONFIG[service_name]["port"]}/health || exit 1

# Run the application
CMD ["python", "-m", "src.main"]'''
    
    with open(base_path / "Dockerfile", "w") as f:
        f.write(dockerfile_content)

def create_requirements(base_path: Path) -> None:
    """Create requirements files."""
    requirements = """fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy[asyncio]==2.0.23
asyncpg==0.29.0
redis[hiredis]==5.0.1
pydantic==2.5.0
structlog==23.2.0
opentelemetry-api==1.21.0
opentelemetry-sdk==1.21.0
prometheus-client==0.19.0"""
    
    requirements_dev = """pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
httpx==0.25.2
pytest-mock==3.12.0
testcontainers==3.7.1
black==23.11.0
ruff==0.1.7
mypy==1.7.1
bandit==1.7.5"""
    
    with open(base_path / "requirements.txt", "w") as f:
        f.write(requirements)
    
    with open(base_path / "requirements-dev.txt", "w") as f:
        f.write(requirements_dev)

def create_makefile(base_path: Path, service_name: str) -> None:
    """Create service Makefile."""
    makefile_content = f'''.PHONY: help dev test lint build migrate run clean type-check

# Default target
help:
	@echo "{service_name.title()} Service - Available Commands:"
	@echo ""
	@echo "Development:"
	@echo "  dev          Install dependencies for development"
	@echo "  test         Run all tests with coverage"
	@echo "  lint         Run linting and formatting checks"
	@echo "  type-check   Run type checking with mypy"
	@echo "  migrate      Run database migrations"
	@echo "  run          Run the service locally"
	@echo ""
	@echo "Build & Deploy:"
	@echo "  build        Build Docker image"
	@echo "  clean        Clean build artifacts"

# Install dependencies
dev:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

# Run tests
test:
	pytest tests/ -v --cov=src --cov-report=html --cov-report=xml --cov-report=term

# Linting and formatting
lint:
	black --check src/ tests/
	ruff check src/ tests/
	bandit -r src/

# Type checking
type-check:
	mypy src/ --strict --ignore-missing-imports

# Database migrations
migrate:
	cd db && python migrate.py

# Run service locally
run:
	uvicorn src.main:app --host 0.0.0.0 --port {SERVICES_CONFIG[service_name]["port"]} --reload

# Build Docker image
build:
	docker build -t {service_name}:latest .

# Clean artifacts
clean:
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete
	rm -rf .coverage htmlcov/ .pytest_cache/'''
    
    with open(base_path / "Makefile", "w") as f:
        f.write(makefile_content)

def create_readme(base_path: Path, service_name: str, config: Dict) -> None:
    """Create service README."""
    readme_content = f'''# {service_name.title()} Service

{config["description"]}

## Technology Stack

{config["tech"]}

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
| `PORT` | Service port | {config["port"]} |

## API Documentation

OpenAPI specification: [`contracts/openapi.yaml`](contracts/openapi.yaml)

## Deployment

```bash
# Deploy to development
cd deploy && make deploy ENV=dev

# Deploy to production
cd deploy && make deploy ENV=prod IMAGE_TAG=v1.0.0
```

## Monitoring

- **SLO**: [observability/SLO.md](observability/SLO.md)
- **Runbook**: [observability/runbook.md](observability/runbook.md)
- **Dashboard**: [observability/dashboards/{service_name}.json](observability/dashboards/{service_name}.json)'''
    
    with open(base_path / "README.md", "w") as f:
        f.write(readme_content)

def create_ci_workflow(base_path: Path, service_name: str) -> None:
    """Create service CI workflow."""
    ci_content = f'''name: '{service_name.title()} CI/CD'

on:
  push:
    paths:
      - 'apps/{service_name}/**'
      - 'libs/**'
      - 'contracts/**'
      - '.github/workflows/{service_name}-ci.yaml'
  pull_request:
    paths:
      - 'apps/{service_name}/**'
      - 'libs/**'
      - 'contracts/**'

jobs:
  service-ci:
    uses: ./.github/workflows/service-ci.yaml
    with:
      service-name: {service_name}
      service-path: apps/{service_name}
      python-version: '3.11'
      enable-docker: true
      enable-helm: true
    secrets:
      DOCKER_REGISTRY_URL: ${{{{ secrets.DOCKER_REGISTRY_URL }}}}
      DOCKER_USERNAME: ${{{{ secrets.DOCKER_USERNAME }}}}
      DOCKER_PASSWORD: ${{{{ secrets.DOCKER_PASSWORD }}}}'''
    
    (base_path / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    with open(base_path / ".github" / "workflows" / "ci.yaml", "w") as f:
        f.write(ci_content)

def create_openapi_contract(base_path: Path, service_name: str, config: Dict) -> None:
    """Create basic OpenAPI contract."""
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
      responses:
        '200':
          description: Service is healthy
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/HealthResponse'

components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

  schemas:
    HealthResponse:
      type: object
      properties:
        status:
          type: string
          enum: [healthy, degraded, unhealthy]
        timestamp:
          type: string
          format: date-time
        version:
          type: string'''
    
    with open(base_path / "contracts" / "openapi.yaml", "w") as f:
        f.write(openapi_content)

def create_kustomize_files(base_path: Path, service_name: str, config: Dict) -> None:
    """Create Kustomize deployment files."""
    # Base kustomization
    base_kustomization = f'''apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

metadata:
  name: {service_name}-base

resources:
  - deployment.yaml
  - service.yaml
  - configmap.yaml
  - hpa.yaml

commonLabels:
  app: {service_name}
  component: backend'''
    
    with open(base_path / "deploy" / "base" / "kustomization.yaml", "w") as f:
        f.write(base_kustomization)
    
    # Base deployment
    deployment = f'''apiVersion: apps/v1
kind: Deployment
metadata:
  name: {service_name}
spec:
  replicas: 2
  selector:
    matchLabels:
      app: {service_name}
  template:
    metadata:
      labels:
        app: {service_name}
    spec:
      containers:
      - name: {service_name}
        image: {service_name}:IMAGE_TAG
        ports:
        - containerPort: {config["port"]}
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: database-secret
              key: url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: redis-secret
              key: url
        envFrom:
        - configMapRef:
            name: {service_name}-config
        livenessProbe:
          httpGet:
            path: /health
            port: {config["port"]}
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: {config["port"]}
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"'''
    
    with open(base_path / "deploy" / "base" / "deployment.yaml", "w") as f:
        f.write(deployment)

def create_observability_files(base_path: Path, service_name: str, config: Dict) -> None:
    """Create observability files."""
    # SLO document
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

### Error Rate
```promql
(
  sum(rate(http_requests_total{{service="{service_name}",status=~"5.."}}[5m])) /
  sum(rate(http_requests_total{{service="{service_name}"}}[5m]))
) * 100
```'''
    
    with open(base_path / "observability" / "SLO.md", "w") as f:
        f.write(slo_content)

def main():
    """Main migration function."""
    print("Starting service migration to microservices-standard structure...")
    
    for service_name, config in SERVICES_CONFIG.items():
        print(f"Migrating {service_name}...")
        create_service_structure(service_name, config)
    
    print("Migration completed!")
    print("\\nNext steps:")
    print("1. Review generated files")
    print("2. Move existing source code to src/ directories")
    print("3. Update import paths")
    print("4. Test each service")

if __name__ == "__main__":
    main()
