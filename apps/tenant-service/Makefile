.PHONY: help dev test lint build migrate run clean type-check

# Default target
help:
	@echo "Tenant-Service Service - Available Commands:"
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
	uvicorn src.main:app --host 0.0.0.0 --port 8008 --reload

# Build Docker image
build:
	docker build -t tenant-service:latest .

# Clean artifacts
clean:
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete
	rm -rf .coverage htmlcov/ .pytest_cache/
# Code generation targets
.PHONY: generate-clients clean-generated

generate-clients: ## Generate API clients from OpenAPI spec
	@echo "Generating API clients from OpenAPI spec..."
	cd contracts && \
	openapi-generator-cli generate -i openapi.yaml -g python -o ../gen/python-client --config codegen.yaml && \
	openapi-generator-cli generate -i openapi.yaml -g typescript-axios -o ../gen/typescript-client --config codegen.yaml && \
	openapi-generator-cli generate -i openapi.yaml -g go -o ../gen/go-client --config codegen.yaml

generate-orval: ## Generate TypeScript client using Orval
	@echo "Generating TypeScript client with Orval..."
	cd contracts && npx orval

clean-generated: ## Clean generated client code
	rm -rf gen/
docker-build: ## Build Docker image
	@echo "🐳 Building Docker image for tenant-service..."
	docker build -t tenant-service:latest .
	docker build -t tenant-service:$$(git rev-parse --short HEAD) .
	@echo "✅ Docker image built: tenant-service:latest"

docker-push: docker-build ## Push Docker image to registry
	@echo "🚀 Pushing Docker image for tenant-service..."
	@if [ -z "$${DOCKER_REGISTRY}" ]; then \
		echo "❌ DOCKER_REGISTRY environment variable not set"; \
		exit 1; \
	fi
	docker tag tenant-service:latest $${DOCKER_REGISTRY}/tenant-service:latest
	docker tag tenant-service:$$(git rev-parse --short HEAD) $${DOCKER_REGISTRY}/tenant-service:$$(git rev-parse --short HEAD)
	docker push $${DOCKER_REGISTRY}/tenant-service:latest
	docker push $${DOCKER_REGISTRY}/tenant-service:$$(git rev-parse --short HEAD)
	@echo "✅ Docker image pushed: $${DOCKER_REGISTRY}/tenant-service:latest"
