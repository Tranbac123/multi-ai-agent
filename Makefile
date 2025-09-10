# Multi-Tenant AIaaS Platform Makefile

.PHONY: help dev test e2e eval security format lint type-check build deploy clean

# Default target
help: ## Show this help message
	@echo "Multi-Tenant AIaaS Platform - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Development Commands
dev: ## Start development environment
	@echo "Starting development environment..."
	docker-compose -f docker-compose.dev.yml up -d
	@echo "Development environment started. Access services at:"
	@echo "  - API Gateway: http://localhost:8000"
	@echo "  - Realtime Service: http://localhost:8001"
	@echo "  - Router Service: http://localhost:8002"
	@echo "  - Orchestrator: http://localhost:8003"
	@echo "  - Analytics Service: http://localhost:8004"
	@echo "  - Billing Service: http://localhost:8005"
	@echo "  - Grafana: http://localhost:3000"
	@echo "  - Prometheus: http://localhost:9090"

dev-stop: ## Stop development environment
	@echo "Stopping development environment..."
	docker-compose -f docker-compose.dev.yml down

dev-logs: ## Show development environment logs
	docker-compose -f docker-compose.dev.yml logs -f

# Testing Commands
test: ## Run all tests
	@echo "Running unit tests..."
	python -m pytest tests/unit/ -v --cov=apps --cov=libs --cov-report=html --cov-report=term
	@echo "Running integration tests..."
	python -m pytest tests/integration/ -v
	@echo "All tests completed."

test-unit: ## Run unit tests only
	@echo "Running unit tests..."
	python -m pytest tests/unit/ -v --cov=apps --cov=libs --cov-report=html --cov-report=term

test-integration: ## Run integration tests only
	@echo "Running integration tests..."
	python -m pytest tests/integration/ -v

test-e2e: ## Run end-to-end tests
	@echo "Running end-to-end tests..."
	python -m pytest tests/e2e/ -v --timeout=300

# Evaluation Commands
eval: ## Run evaluation suite
	@echo "Running evaluation suite..."
	python -m pytest eval/ -v --timeout=600

eval-episodes: ## Run episode replay evaluation
	@echo "Running episode replay evaluation..."
	python -m pytest eval/test_episode_replay.py -v

eval-metrics: ## Run evaluation metrics
	@echo "Running evaluation metrics..."
	python -m pytest eval/test_evaluation_metrics.py -v

# Security Commands
security: ## Run security checks
	@echo "Running security checks..."
	@echo "Running Bandit security linter..."
	bandit -r apps/ libs/ -f json -o security-report.json
	@echo "Running Safety dependency check..."
	safety check --json --output safety-report.json
	@echo "Running Semgrep security scan..."
	semgrep --config=auto apps/ libs/ --json --output=semgrep-report.json
	@echo "Security checks completed. Reports saved to security-*.json"

security-bandit: ## Run Bandit security linter
	bandit -r apps/ libs/ -f json -o security-report.json

security-safety: ## Run Safety dependency check
	safety check --json --output safety-report.json

security-semgrep: ## Run Semgrep security scan
	semgrep --config=auto apps/ libs/ --json --output=semgrep-report.json

# Code Quality Commands
format: ## Format code with Black and isort
	@echo "Formatting code..."
	black apps/ libs/ tests/ eval/
	isort apps/ libs/ tests/ eval/
	@echo "Code formatting completed."

lint: ## Run linting with Ruff
	@echo "Running linting..."
	ruff check apps/ libs/ tests/ eval/
	@echo "Linting completed."

type-check: ## Run type checking with MyPy
	@echo "Running type checking..."
	mypy apps/ libs/ --ignore-missing-imports
	@echo "Type checking completed."

# Build Commands
build: ## Build Docker images
	@echo "Building Docker images..."
	docker-compose -f docker-compose.prod.yml build
	@echo "Docker images built successfully."

build-dev: ## Build development Docker images
	@echo "Building development Docker images..."
	docker-compose -f docker-compose.dev.yml build
	@echo "Development Docker images built successfully."

# Deployment Commands
deploy: ## Deploy to production
	@echo "Deploying to production..."
	docker-compose -f docker-compose.prod.yml up -d
	@echo "Production deployment completed."

deploy-staging: ## Deploy to staging
	@echo "Deploying to staging..."
	docker-compose -f docker-compose.staging.yml up -d
	@echo "Staging deployment completed."

# Database Commands
db-migrate: ## Run database migrations
	@echo "Running database migrations..."
	cd data-plane && alembic upgrade head
	@echo "Database migrations completed."

db-rollback: ## Rollback database migrations
	@echo "Rollback database migrations..."
	cd data-plane && alembic downgrade -1
	@echo "Database rollback completed."

db-reset: ## Reset database
	@echo "Resetting database..."
	docker-compose -f docker-compose.dev.yml down -v
	docker-compose -f docker-compose.dev.yml up -d postgres
	sleep 10
	make db-migrate
	@echo "Database reset completed."

# Monitoring Commands
monitor: ## Start monitoring stack
	@echo "Starting monitoring stack..."
	docker-compose -f docker-compose.monitoring.yml up -d
	@echo "Monitoring stack started. Access at:"
	@echo "  - Grafana: http://localhost:3000"
	@echo "  - Prometheus: http://localhost:9090"
	@echo "  - Jaeger: http://localhost:16686"

monitor-stop: ## Stop monitoring stack
	@echo "Stopping monitoring stack..."
	docker-compose -f docker-compose.monitoring.yml down

# Performance Commands
perf-test: ## Run performance tests
	@echo "Running performance tests..."
	locust -f tests/performance/locustfile.py --host=http://localhost:8000 --users=100 --spawn-rate=10 --run-time=5m
	@echo "Performance tests completed."

perf-load: ## Run load tests
	@echo "Running load tests..."
	locust -f tests/performance/locustfile.py --host=http://localhost:8000 --users=1000 --spawn-rate=50 --run-time=10m
	@echo "Load tests completed."

# Cleanup Commands
clean: ## Clean up Docker resources
	@echo "Cleaning up Docker resources..."
	docker-compose -f docker-compose.dev.yml down -v
	docker-compose -f docker-compose.prod.yml down -v
	docker-compose -f docker-compose.staging.yml down -v
	docker-compose -f docker-compose.monitoring.yml down -v
	docker system prune -f
	@echo "Cleanup completed."

clean-logs: ## Clean up log files
	@echo "Cleaning up log files..."
	find . -name "*.log" -type f -delete
	find . -name "*.log.*" -type f -delete
	@echo "Log files cleaned."

clean-cache: ## Clean up cache files
	@echo "Cleaning up cache files..."
	find . -name "__pycache__" -type d -exec rm -rf {} +
	find . -name "*.pyc" -type f -delete
	find . -name ".pytest_cache" -type d -exec rm -rf {} +
	find . -name ".coverage" -type f -delete
	find . -name "htmlcov" -type d -exec rm -rf {} +
	@echo "Cache files cleaned."

# Documentation Commands
docs: ## Generate documentation
	@echo "Generating documentation..."
	pdoc --html apps/ libs/ --output-dir docs/
	@echo "Documentation generated in docs/ directory."

docs-serve: ## Serve documentation locally
	@echo "Serving documentation..."
	pdoc --http :8080 apps/ libs/

# Health Check Commands
health: ## Check service health
	@echo "Checking service health..."
	@echo "API Gateway:"
	curl -f http://localhost:8000/health || echo "API Gateway: DOWN"
	@echo "Realtime Service:"
	curl -f http://localhost:8001/health || echo "Realtime Service: DOWN"
	@echo "Router Service:"
	curl -f http://localhost:8002/health || echo "Router Service: DOWN"
	@echo "Orchestrator:"
	curl -f http://localhost:8003/health || echo "Orchestrator: DOWN"
	@echo "Analytics Service:"
	curl -f http://localhost:8004/health || echo "Analytics Service: DOWN"
	@echo "Billing Service:"
	curl -f http://localhost:8005/health || echo "Billing Service: DOWN"

# Backup Commands
backup: ## Backup database and configuration
	@echo "Creating backup..."
	mkdir -p backups/$(shell date +%Y%m%d_%H%M%S)
	docker-compose -f docker-compose.dev.yml exec postgres pg_dump -U postgres aiaas > backups/$(shell date +%Y%m%d_%H%M%S)/database.sql
	cp -r data-plane/migrations backups/$(shell date +%Y%m%d_%H%M%S)/
	cp docker-compose*.yml backups/$(shell date +%Y%m%d_%H%M%S)/
	@echo "Backup completed."

# Update Commands
update-deps: ## Update dependencies
	@echo "Updating dependencies..."
	pip-compile requirements.in
	pip-compile requirements-dev.in
	@echo "Dependencies updated."

update-docker: ## Update Docker images
	@echo "Updating Docker images..."
	docker-compose -f docker-compose.dev.yml pull
	docker-compose -f docker-compose.prod.yml pull
	@echo "Docker images updated."

# All-in-one Commands
all: format lint type-check test security ## Run all quality checks
	@echo "All quality checks completed."

ci: format lint type-check test security build ## Run CI pipeline
	@echo "CI pipeline completed."

dev-setup: ## Setup development environment
	@echo "Setting up development environment..."
	pip install -r requirements-dev.txt
	make db-migrate
	make dev
	@echo "Development environment setup completed."