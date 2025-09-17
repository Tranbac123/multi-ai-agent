# Multi-Tenant AIaaS Platform Makefile

.PHONY: help install test lint format type-check audit clean build deploy dup dead comp qa

# Default target
help:
	@echo "Multi-Tenant AIaaS Platform - Available Commands:"
	@echo ""
	@echo "Development:"
	@echo "  install      Install dependencies"
	@echo "  test         Run all tests"
	@echo "  lint         Run linting checks"
	@echo "  format       Format code with black and ruff"
	@echo "  type-check   Run type checking with mypy"
	@echo "  audit        Run platform readiness audit"
	@echo ""
	@echo "Code Quality Analysis:"
	@echo "  dup          Detect code duplication (jscpd)"
	@echo "  dead         Detect dead code (vulture + ts-prune)"
	@echo "  comp         Analyze code complexity (radon)"
	@echo "  qa           Run all quality analysis tools"
	@echo ""
	@echo "Build & Deploy:"
	@echo "  build        Build Docker images"
	@echo "  deploy       Deploy to production"
	@echo ""
	@echo "Quality Gates:"
	@echo "  ci           Run full CI pipeline"
	@echo "  security     Run security scans"
	@echo "  performance  Run performance tests"
	@echo ""
	@echo "Utilities:"
	@echo "  clean        Clean build artifacts"
	@echo "  docs         Generate documentation"

# Development commands
install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

test:
	@echo "Running tests..."
	pytest tests/ -v --cov=apps --cov=libs --cov-report=html --cov-report=term

test-unit:
	@echo "Running unit tests..."
	pytest tests/unit/ -v

test-integration:
	@echo "Running integration tests..."
	pytest tests/integration/ -v

test-e2e:
	@echo "Running end-to-end tests..."
	pytest tests/e2e/ -v

lint:
	@echo "Running linting checks..."
	ruff check apps/ libs/ tests/
	black --check apps/ libs/ tests/

format:
	@echo "Formatting code..."
	black apps/ libs/ tests/
	ruff --fix apps/ libs/ tests/

type-check:
	@echo "Running type checking..."
	mypy apps/ libs/ --strict --ignore-missing-imports

audit:
	@echo "Running platform readiness audit..."
	python scripts/audit_readiness.py --verbose

# Quality gates
ci: lint type-check test audit
	@echo "✅ CI pipeline completed successfully"

security:
	@echo "Running security scans..."
	bandit -r apps/ libs/ -f json -o security-report.json
	safety check --json --output security-deps.json

performance:
	@echo "Running performance tests..."
	locust -f tests/performance/locustfile.py --headless -u 100 -r 10 -t 60s --html performance-report.html

# Build and deployment
build:
	@echo "Building Docker images..."
	docker-compose build

deploy:
	@echo "Deploying to production..."
	docker-compose -f docker-compose.prod.yml up -d

# Utilities
clean:
	@echo "Cleaning build artifacts..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ .coverage htmlcov/ .pytest_cache/
	rm -f security-report.json security-deps.json performance-report.html

docs:
	@echo "Generating documentation..."
	sphinx-build -b html docs/ docs/_build/html

# Database commands
db-migrate:
	@echo "Running database migrations..."
	alembic upgrade head

db-rollback:
	@echo "Rolling back database migration..."
	alembic downgrade -1

db-reset:
	@echo "Resetting database..."
	alembic downgrade base
	alembic upgrade head

# Service management
services-up:
	@echo "Starting all services..."
	docker-compose up -d

services-down:
	@echo "Stopping all services..."
	docker-compose down

services-logs:
	@echo "Viewing service logs..."
	docker-compose logs -f

# Monitoring
monitor:
	@echo "Opening monitoring dashboard..."
	open http://localhost:3000  # Grafana

metrics:
	@echo "Viewing Prometheus metrics..."
	open http://localhost:9090  # Prometheus

# Development helpers
dev-setup:
	@echo "Setting up development environment..."
	cp .env.example .env
	make install
	make db-migrate
	make services-up
	@echo "Development environment ready!"

dev-reset:
	@echo "Resetting development environment..."
	make services-down
	make clean
	make dev-setup

# Platform hardening commands (for Staff Engineer tasks)
harden: audit test security performance
	@echo "✅ Platform hardening completed"

harden-loop-safety:
	@echo "Checking loop safety implementation..."
	python scripts/audit_readiness.py --verbose | grep -E "(LOOP_SAFETY|PASS|FAIL)"

harden-contracts:
	@echo "Checking strict contracts..."
	python scripts/audit_readiness.py --verbose | grep -E "(CONTRACTS|PASS|FAIL)"

harden-router:
	@echo "Checking router guarantees..."
	python scripts/audit_readiness.py --verbose | grep -E "(ROUTER|PASS|FAIL)"

harden-tools:
	@echo "Checking tool adapter reliability..."
	python scripts/audit_readiness.py --verbose | grep -E "(TOOL_ADAPTER|PASS|FAIL)"

harden-websocket:
	@echo "Checking WebSocket backpressure..."
	python scripts/audit_readiness.py --verbose | grep -E "(WEBSOCKET|PASS|FAIL)"

harden-rls:
	@echo "Checking RLS policies..."
	python scripts/audit_readiness.py --verbose | grep -E "(RLS|PASS|FAIL)"

# Code Quality Analysis
dup:
	@echo "🔍 Detecting code duplication..."
	@mkdir -p reports/duplication
	jscpd --config .jscpd.json
	@echo "📊 Duplication report saved to reports/duplication/"

dead:
	@echo "💀 Detecting dead code..."
	@mkdir -p reports/dead-code
	@echo "Python dead code analysis:"
	vulture apps/ libs/ control-plane/ data-plane/ services/ --min-confidence 80 --sort-by-size > reports/dead-code/python-dead-code.txt || true
	@echo "TypeScript dead code analysis:"
	cd web && npm run dead-code || true
	@echo "📊 Dead code reports saved to reports/dead-code/"

comp:
	@echo "📈 Analyzing code complexity..."
	@mkdir -p reports/complexity
	radon cc apps/ libs/ control-plane/ data-plane/ services/ -nc -j > reports/complexity/complexity.json
	radon cc apps/ libs/ control-plane/ data-plane/ services/ -nc -a > reports/complexity/complexity-average.txt
	@echo "📊 Complexity reports saved to reports/complexity/"

qa: dup dead comp
	@echo "🎯 Quality Analysis Summary:"
	@echo "================================"
	@echo "📊 Duplication Report: reports/duplication/"
	@echo "💀 Dead Code Report: reports/dead-code/"
	@echo "📈 Complexity Report: reports/complexity/"
	@echo "🔍 Linting Report: Above output"
	@echo "================================"
	@echo "✅ Quality analysis complete!"

qa-comprehensive:
	@echo "🔍 Running comprehensive quality analysis..."
	@mkdir -p reports
	python3 scripts/quality_analysis_report.py --verbose --html
	@echo "📊 Comprehensive report saved to reports/quality_analysis_report.html"

# Test specific hardening criteria
test-loop-safety:
	@echo "Testing loop safety..."
	pytest tests/integration/test_loop_safety.py -v

test-contracts:
	@echo "Testing strict contracts..."
	pytest tests/integration/test_contracts.py -v

test-router-guarantees:
	@echo "Testing router guarantees..."
	pytest tests/integration/test_router_guarantees.py -v

test-tool-adapter:
	@echo "Testing tool adapter reliability..."
	pytest tests/integration/test_tool_adapter.py -v

test-realtime-backpressure:
	@echo "Testing realtime backpressure..."
	pytest tests/integration/test_realtime_backpressure.py -v

test-multi-tenant-safety:
	@echo "Testing multi-tenant safety..."
	pytest tests/integration/test_multi_tenant_safety.py -v

test-rag-protection:
	@echo "Testing RAG protection..."
	pytest tests/integration/test_rag_protection.py -v

test-observability:
	@echo "Testing observability..."
	pytest tests/integration/test_observability.py -v

test-eval-replay:
	@echo "Testing eval and replay..."
	pytest tests/integration/test_eval_replay.py -v

test-performance-gates:
	@echo "Testing performance gates..."
	locust -f tests/performance/test_performance_gates.py --headless -u 50 -r 5 -t 30s

# Acceptance criteria validation
acceptance-all:
	@echo "Running all acceptance criteria tests..."
	make test-loop-safety
	make test-contracts
	make test-router-guarantees
	make test-tool-adapter
	make test-realtime-backpressure
	make test-multi-tenant-safety
	make test-rag-protection
	make test-observability
	make test-eval-replay
	make test-performance-gates
	@echo "✅ All acceptance criteria validated!"