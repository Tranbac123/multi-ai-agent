.PHONY: help dev test lint build run clean type-check

# Default target
help:
	@echo "Web Frontend - Available Commands:"
	@echo ""
	@echo "Development:"
	@echo "  dev          Install dependencies for development"
	@echo "  test         Run all tests"
	@echo "  lint         Run linting and formatting checks"
	@echo "  type-check   Run TypeScript type checking"
	@echo "  run          Run the development server"
	@echo ""
	@echo "Build & Deploy:"
	@echo "  build        Build for production"
	@echo "  clean        Clean build artifacts"

# Install dependencies
dev:
	npm install

# Run tests
test:
	npm run test

# Linting and formatting
lint:
	npm run lint

# Type checking
type-check:
	npm run type-check

# Run development server
run:
	npm run dev

# Build for production
build:
	npm run build

# Clean artifacts
clean:
	rm -rf dist/ node_modules/ .vite/

migrate: ## No-op migrate for frontend service
	@echo "⚠️ No database migrations needed for frontend service"

docker-build: ## Build Docker image
	@echo "🐳 Building Docker image for web-frontend..."
	docker build -t web-frontend:latest .
	docker build -t web-frontend:$$(git rev-parse --short HEAD) .
	@echo "✅ Docker image built: web-frontend:latest"

docker-push: docker-build ## Push Docker image to registry
	@echo "🚀 Pushing Docker image for web-frontend..."
	@if [ -z "$${DOCKER_REGISTRY}" ]; then \
		echo "❌ DOCKER_REGISTRY environment variable not set"; \
		exit 1; \
	fi
	docker tag web-frontend:latest $${DOCKER_REGISTRY}/web-frontend:latest
	docker tag web-frontend:$$(git rev-parse --short HEAD) $${DOCKER_REGISTRY}/web-frontend:$$(git rev-parse --short HEAD)
	docker push $${DOCKER_REGISTRY}/web-frontend:latest
	docker push $${DOCKER_REGISTRY}/web-frontend:$$(git rev-parse --short HEAD)
	@echo "✅ Docker image pushed: $${DOCKER_REGISTRY}/web-frontend:latest"
