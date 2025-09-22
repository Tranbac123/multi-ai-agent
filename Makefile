# Multi-AI-Agent Platform Makefile
.PHONY: help dev test lint build clean services

# Default target
help:
	@echo "Multi-AI-Agent Platform - Available Commands:"
	@echo ""
	@echo "Development:"
	@echo "  dev          Set up development environment for all services"
	@echo "  test         Run tests for all services"
	@echo "  lint         Run linting for all services"
	@echo "  build        Build all service Docker images"
	@echo "  clean        Clean build artifacts"
	@echo ""
	@echo "Platform:"
	@echo "  services     List all available services"
	@echo "  deploy-dev   Deploy all services to development"
	@echo "  deploy-prod  Deploy all services to production"

# List of all backend services
BACKEND_SERVICES := api-gateway analytics-service orchestrator router-service realtime \
                    ingestion billing-service tenant-service chat-adapters tool-service \
                    eval-service capacity-monitor

# List of all frontend services (SPA + BFF)
FRONTEND_SERVICES := web-frontend admin-portal

# Note: admin-portal is a BFF (Backend for Frontend) pattern:
# - Server-side FastAPI application with Jinja2 templates
# - Serves both backend logic and frontend presentation
# - Deployed as a microservice but serves frontend functionality

# All services
SERVICES := $(BACKEND_SERVICES) $(FRONTEND_SERVICES)

# Development setup
dev:
	@for service in $(SERVICES); do \
		echo "Setting up $$service..."; \
		cd apps/$$service && make dev && cd ../..; \
	done

# Run tests for all services
test:
	@for service in $(SERVICES); do \
		echo "Testing $$service..."; \
		cd apps/$$service && make test && cd ../..; \
	done

# Lint all services
lint:
	@for service in $(SERVICES); do \
		echo "Linting $$service..."; \
		cd apps/$$service && make lint && cd ../..; \
	done

# Build all Docker images
build:
	@for service in $(SERVICES); do \
		echo "Building $$service..."; \
		cd apps/$$service && make build && cd ../..; \
	done

# Clean all artifacts
clean:
	@for service in $(SERVICES); do \
		echo "Cleaning $$service..."; \
		cd apps/$$service && make clean && cd ../..; \
	done
	docker system prune -f

# List all services
services:
	@echo "Available services:"
	@for service in $(SERVICES); do \
		echo "  - $$service"; \
	done

# Deploy to development
deploy-dev:
	@echo "Deploying all services to development..."
	kubectl apply -k infra/k8s/overlays/dev

# Deploy to production
deploy-prod:
	@echo "Deploying all services to production..."
	kubectl apply -k infra/k8s/overlays/prod

# Contract and codegen targets
.PHONY: generate-all-contracts validate-all-contracts clean-all-generated

generate-all-contracts: ## Generate clients for all services and shared contracts
	@echo "🎯 Generating clients for all services and shared contracts..."
	@echo "Generating shared contracts..."
	@cd contracts && make generate-all
	@echo "Generating service contracts..."
	@for service in api-gateway analytics-service orchestrator router-service realtime ingestion billing-service tenant-service chat-adapters tool-service eval-service capacity-monitor admin-portal; do \
		echo "Generating clients for $$service..."; \
		cd apps/$$service && make generate-clients && cd ../..; \
	done
	@echo "🎉 All contracts and clients generated successfully!"

validate-all-contracts: ## Validate all contracts (shared + service-specific)
	@echo "🔍 Validating all contracts..."
	@echo "Validating shared contracts..."
	@cd contracts && make validate
	@echo "Validating service contracts..."
	@for service in api-gateway analytics-service orchestrator router-service realtime ingestion billing-service tenant-service chat-adapters tool-service eval-service capacity-monitor admin-portal; do \
		echo "Validating $$service contracts..."; \
		if [ -f "apps/$$service/contracts/openapi.yaml" ]; then \
			openapi-generator-cli validate -i apps/$$service/contracts/openapi.yaml; \
		fi; \
		if [ -f "apps/$$service/contracts/buf.yaml" ]; then \
			cd apps/$$service/contracts && buf lint && cd ../../..; \
		fi; \
	done
	@echo "✅ All contracts are valid!"

clean-all-generated: ## Clean all generated client code
	@echo "🧹 Cleaning all generated code..."
	@cd contracts && make clean
	@for service in api-gateway analytics-service orchestrator router-service realtime ingestion billing-service tenant-service chat-adapters tool-service eval-service capacity-monitor admin-portal; do \
		echo "Cleaning generated code for $$service..."; \
		cd apps/$$service && make clean-generated 2>/dev/null || true && cd ../..; \
	done
	@echo "✅ All generated code cleaned!"

install-codegen-tools: ## Install all required code generation tools
	@echo "📦 Installing code generation tools..."
	@cd contracts && make install-tools
	@echo "✅ All code generation tools installed!"