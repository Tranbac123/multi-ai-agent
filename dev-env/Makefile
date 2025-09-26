.PHONY: help up up-core down logs rebuild migrate seed test lint clean

# Default target
help:
	@echo "Available commands:"
	@echo "  up          - Start all services"
	@echo "  up-core     - Start core services only (api-gateway, orchestrator, router-service)"
	@echo "  up-data     - Start data plane services"
	@echo "  up-control  - Start control plane services"
	@echo "  up-realtime - Start realtime services"
	@echo "  up-analytics - Start analytics services"
	@echo "  up-billing  - Start billing services"
	@echo "  up-obs      - Start observability stack"
	@echo "  down        - Stop all services"
	@echo "  logs        - Show logs for all services"
	@echo "  logs-<svc>  - Show logs for specific service"
	@echo "  rebuild     - Rebuild all services"
	@echo "  migrate     - Run database migrations"
	@echo "  seed        - Seed database with test data"
	@echo "  test        - Run all tests"
	@echo "  lint        - Run linting on all services"
	@echo "  clean       - Clean up containers and volumes"
	@echo "  health      - Check health of all services"

# Start all services
up:
	@echo "🚀 Starting all services..."
	docker-compose up -d --build

# Start core services only
up-core:
	@echo "🚀 Starting core services..."
	docker-compose --profile core up -d --build

# Start data plane services
up-data:
	@echo "🚀 Starting data plane services..."
	docker-compose --profile data-plane up -d --build

# Start control plane services
up-control:
	@echo "🚀 Starting control plane services..."
	docker-compose --profile control-plane up -d --build

# Start realtime services
up-realtime:
	@echo "🚀 Starting realtime services..."
	docker-compose --profile realtime up -d --build

# Start analytics services
up-analytics:
	@echo "🚀 Starting analytics services..."
	docker-compose --profile analytics up -d --build

# Start billing services
up-billing:
	@echo "🚀 Starting billing services..."
	docker-compose --profile billing up -d --build

# Start observability stack
up-obs:
	@echo "🚀 Starting observability stack..."
	docker-compose up -d postgres redis nats otel-collector jaeger prometheus grafana

# Stop all services
down:
	@echo "🛑 Stopping all services..."
	docker-compose down

# Show logs for all services
logs:
	docker-compose logs -f

# Show logs for specific service
logs-api-gateway:
	docker-compose logs -f api-gateway

logs-orchestrator:
	docker-compose logs -f orchestrator

logs-router-service:
	docker-compose logs -f router-service

logs-model-gateway:
	docker-compose logs -f model-gateway

logs-retrieval-service:
	docker-compose logs -f retrieval-service

logs-ingestion-service:
	docker-compose logs -f ingestion-service

logs-analytics-service:
	docker-compose logs -f analytics-service

logs-billing-service:
	docker-compose logs -f billing-service

logs-realtime-gateway:
	docker-compose logs -f realtime-gateway

logs-config-service:
	docker-compose logs -f config-service

logs-usage-metering:
	docker-compose logs -f usage-metering

# Rebuild all services
rebuild:
	@echo "🔨 Rebuilding all services..."
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d

# Run database migrations
migrate:
	@echo "🗄️ Running database migrations..."
	docker-compose exec api-gateway python -m alembic upgrade head

# Seed database with test data
seed:
	@echo "🌱 Seeding database with test data..."
	docker-compose exec postgres psql -U postgres -d ai_agent -f /seed.sql

# Run all tests
test:
	@echo "🧪 Running tests for all services..."
	@for service in api-gateway orchestrator router-service model-gateway retrieval-service ingestion-service analytics-service billing-service realtime-gateway config-service usage-metering; do \
		echo "Testing $$service..."; \
		docker-compose exec $$service python -m pytest tests/ -v || true; \
	done

# Run linting on all services
lint:
	@echo "🔍 Running linting on all services..."
	@for service in api-gateway orchestrator router-service model-gateway retrieval-service ingestion-service analytics-service billing-service realtime-gateway config-service usage-metering; do \
		echo "Linting $$service..."; \
		docker-compose exec $$service python -m black src/ tests/ || true; \
		docker-compose exec $$service python -m flake8 src/ tests/ || true; \
		docker-compose exec $$service python -m mypy src/ || true; \
	done

# Clean up containers and volumes
clean:
	@echo "🧹 Cleaning up containers and volumes..."
	docker-compose down -v
	docker system prune -f

# Check health of all services
health:
	@echo "🏥 Checking health of all services..."
	@echo "API Gateway: $$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/healthz || echo 'DOWN')"
	@echo "Orchestrator: $$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8081/healthz || echo 'DOWN')"
	@echo "Router Service: $$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8083/healthz || echo 'DOWN')"
	@echo "Model Gateway: $$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/healthz || echo 'DOWN')"
	@echo "Retrieval Service: $$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8082/healthz || echo 'DOWN')"
	@echo "Ingestion Service: $$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8084/healthz || echo 'DOWN')"
	@echo "Analytics Service: $$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8085/healthz || echo 'DOWN')"
	@echo "Billing Service: $$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8086/healthz || echo 'DOWN')"
	@echo "Realtime Gateway: $$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8087/healthz || echo 'DOWN')"
	@echo "Config Service: $$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8090/healthz || echo 'DOWN')"
	@echo "Usage Metering: $$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8094/healthz || echo 'DOWN')"

# Quick smoke test
smoke-test:
	@echo "💨 Running smoke tests..."
	@echo "Testing API Gateway..."
	curl -f http://localhost:8000/healthz || (echo "API Gateway health check failed" && exit 1)
	@echo "Testing Orchestrator..."
	curl -f http://localhost:8081/healthz || (echo "Orchestrator health check failed" && exit 1)
	@echo "Testing Router Service..."
	curl -f http://localhost:8083/healthz || (echo "Router Service health check failed" && exit 1)
	@echo "✅ All smoke tests passed!"
