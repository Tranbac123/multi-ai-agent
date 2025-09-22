.PHONY: help dev test lint build migrate run clean type-check

# Default target
help:
	@echo "Orchestrator Service - Available Commands:"
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
	uvicorn src.main:app --host 0.0.0.0 --port 8002 --reload

# Build Docker image
build:
	docker build -t orchestrator:latest .

# Clean artifacts
clean:
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete
	rm -rf .coverage htmlcov/ .pytest_cache/
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
	rm -rf gen/
docker-build: ## Build Docker image
	@echo "🐳 Building Docker image for orchestrator..."
	docker build -t orchestrator:latest .
	docker build -t orchestrator:$$(git rev-parse --short HEAD) .
	@echo "✅ Docker image built: orchestrator:latest"

docker-push: docker-build ## Push Docker image to registry
	@echo "🚀 Pushing Docker image for orchestrator..."
	@if [ -z "$${DOCKER_REGISTRY}" ]; then \
		echo "❌ DOCKER_REGISTRY environment variable not set"; \
		exit 1; \
	fi
	docker tag orchestrator:latest $${DOCKER_REGISTRY}/orchestrator:latest
	docker tag orchestrator:$$(git rev-parse --short HEAD) $${DOCKER_REGISTRY}/orchestrator:$$(git rev-parse --short HEAD)
	docker push $${DOCKER_REGISTRY}/orchestrator:latest
	docker push $${DOCKER_REGISTRY}/orchestrator:$$(git rev-parse --short HEAD)
	@echo "✅ Docker image pushed: $${DOCKER_REGISTRY}/orchestrator:latest"
