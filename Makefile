# Multi-Tenant AIaaS Platform - Production Makefile

.PHONY: help dev test e2e eval replay clean build deploy

# Default target
help:
	@echo "Multi-Tenant AIaaS Platform - Available Commands:"
	@echo ""
	@echo "Development:"
	@echo "  dev          Start development environment"
	@echo "  dev-services Start only infrastructure services"
	@echo "  dev-apps     Start only application services"
	@echo ""
	@echo "Testing:"
	@echo "  test         Run all tests"
	@echo "  test-unit    Run unit tests"
	@echo "  test-integration Run integration tests"
	@echo "  test-e2e     Run end-to-end tests"
	@echo "  test-contract Run contract tests"
	@echo ""
	@echo "Evaluation:"
	@echo "  eval         Run evaluation suite"
	@echo "  replay       Replay specific run (usage: make replay RUN=<run_id>)"
	@echo ""
	@echo "Quality:"
	@echo "  lint         Run linting (ruff + black)"
	@echo "  type-check   Run type checking (mypy)"
	@echo "  security     Run security scan (trivy)"
	@echo "  security-full Run comprehensive security scans"
	@echo "  container-scan Scan Docker containers for vulnerabilities"
	@echo "  dependency-scan Scan dependencies for vulnerabilities"
	@echo "  format       Format code (black)"
	@echo ""
	@echo "Build & Deploy:"
	@echo "  build        Build all Docker images"
	@echo "  deploy-dev   Deploy to development"
	@echo "  deploy-staging Deploy to staging"
	@echo "  deploy-prod  Deploy to production"
	@echo ""
	@echo "Database:"
	@echo "  db-migrate   Run database migrations"
	@echo "  db-rollback  Rollback last migration"
	@echo "  db-seed      Seed database with sample data"
	@echo ""
	@echo "Monitoring:"
	@echo "  logs         View service logs"
	@echo "  metrics      View Prometheus metrics"
	@echo "  dashboards   Open Grafana dashboards"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean        Clean up containers and volumes"
	@echo "  clean-all    Clean up everything including images"

# Development
dev: dev-services dev-apps

dev-services:
	@echo "Starting infrastructure services..."
	docker-compose -f docker-compose.dev.yml up -d postgres redis nats prometheus grafana

dev-apps:
	@echo "Starting application services..."
	docker-compose -f docker-compose.dev.yml up -d api-gateway orchestrator router-service realtime ingestion analytics billing

# Testing
test: test-unit test-integration test-contract

test-unit:
	@echo "Running unit tests..."
	python -m pytest tests/unit/ -v --cov=apps --cov=libs --cov-report=html

test-integration:
	@echo "Running integration tests..."
	python -m pytest tests/integration/ -v

test-e2e:
	@echo "Running end-to-end tests..."
	python -m pytest tests/e2e/ -v

test-contract:
	@echo "Running contract tests..."
	python -m pytest tests/contract/ -v

# Evaluation
eval:
	@echo "Running evaluation suite..."
	python tests/run_evaluation.py

replay:
	@echo "Replaying run: $(RUN)"
	python tests/run_evaluation.py --replay $(RUN)

# Quality
lint:
	@echo "Running linting..."
	ruff check apps/ libs/ tests/
	black --check apps/ libs/ tests/

type-check:
	@echo "Running type checking..."
	mypy apps/ libs/ --strict

security:
	@echo "🔒 Running security scan..."
	trivy fs .
	@echo "✅ Security scan completed"

# Comprehensive security scans
security-full:
	@echo "🔒 Running comprehensive security scans..."
	bandit -r . -f json -o bandit-report.json
	safety check --json --output safety-report.json
	semgrep --config=auto --json --output=semgrep-report.json .
	@echo "✅ Comprehensive security scans completed"

# Container security scan
container-scan:
	@echo "🐳 Scanning Docker containers for vulnerabilities..."
	docker build -t aiaas-api-gateway:latest -f apps/api-gateway/Dockerfile .
	trivy image aiaas-api-gateway:latest
	@echo "✅ Container scan completed"

# Dependency security scan
dependency-scan:
	@echo "📦 Scanning dependencies for vulnerabilities..."
	pip-audit --format=json --output=pip-audit-report.json
	safety check --json --output=safety-report.json
	@echo "✅ Dependency scan completed"

format:
	@echo "Formatting code..."
	black apps/ libs/ tests/
	ruff --fix apps/ libs/ tests/

# Build & Deploy
build:
	@echo "Building Docker images..."
	docker build -f Dockerfile.api-gateway -t multi-ai-agent/api-gateway:latest .
	docker build -f Dockerfile.orchestrator -t multi-ai-agent/orchestrator:latest .
	docker build -f Dockerfile.router -t multi-ai-agent/router:latest .
	docker build -f Dockerfile.realtime -t multi-ai-agent/realtime:latest .
	docker build -f Dockerfile.ingestion -t multi-ai-agent/ingestion:latest .
	docker build -f Dockerfile.analytics -t multi-ai-agent/analytics:latest .
	docker build -f Dockerfile.billing -t multi-ai-agent/billing:latest .

deploy-dev: build
	@echo "Deploying to development..."
	docker-compose -f docker-compose.dev.yml up -d

deploy-staging: build
	@echo "Deploying to staging..."
	docker-compose -f docker-compose.staging.yml up -d

deploy-prod: build
	@echo "Deploying to production..."
	kubectl apply -f infra/k8s/

# Database
db-migrate:
	@echo "Running database migrations..."
	alembic upgrade head

db-rollback:
	@echo "Rolling back last migration..."
	alembic downgrade -1

db-seed:
	@echo "Seeding database..."
	python data-plane/seed_data.py

# Monitoring
logs:
	@echo "Viewing service logs..."
	docker-compose logs -f

metrics:
	@echo "Opening Prometheus metrics..."
	open http://localhost:9090

dashboards:
	@echo "Opening Grafana dashboards..."
	open http://localhost:3000

# Cleanup
clean:
	@echo "Cleaning up containers and volumes..."
	docker-compose down -v
	docker system prune -f

clean-all: clean
	@echo "Cleaning up everything..."
	docker system prune -a -f
	docker volume prune -f

# Environment setup
setup:
	@echo "Setting up development environment..."
	pip install -r requirements.txt
	cp .env.example .env
	@echo "Please edit .env with your configuration"

# Quick start
start: setup dev
	@echo "Multi-Tenant AIaaS Platform started!"
	@echo "API Gateway: http://localhost:8000"
	@echo "Grafana: http://localhost:3000"
	@echo "Prometheus: http://localhost:9090"