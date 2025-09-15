# Production-Grade Testing Makefile for Multi-Tenant AIaaS Platform

.PHONY: help install lint format test test-unit test-integration test-e2e test-performance test-flakiness test-observability test-chaos test-contract test-realtime test-security test-adversarial clean coverage security-scan all-tests ci perf chaos replay flakiness-report test-impact quality-gates test-setup-verify

# Default target
help:
	@echo "=== Production-Grade Testing Commands ==="
	@echo ""
	@echo "Core Testing:"
	@echo "  test             - Run all tests (MOCK mode)"
	@echo "  test-unit        - Run unit tests"
	@echo "  test-integration - Run integration tests"
	@echo "  test-e2e         - Run E2E tests"
	@echo "  test-performance - Run performance tests"
	@echo "  test-security    - Run security tests"
	@echo "  test-adversarial - Run adversarial tests"
	@echo "  test-contract    - Run contract tests"
	@echo "  test-realtime    - Run realtime/WebSocket tests"
	@echo "  test-observability - Run observability tests"
	@echo "  test-chaos       - Run chaos engineering tests"
	@echo ""
	@echo "Test Modes:"
	@echo "  test-golden      - Run tests in GOLDEN mode (recorded cassettes)"
	@echo "  test-live        - Run tests in LIVE_SMOKE mode (real services)"
	@echo ""
	@echo "Advanced Testing:"
	@echo "  perf             - Run performance tests with regression checking"
	@echo "  chaos            - Run chaos engineering tests"
	@echo "  replay           - Run episode replay (use RUN=<episode_id>)"
	@echo "  flakiness-report - Generate flakiness analysis report"
	@echo "  test-impact      - Run test impact selection (use CHANGED_FILES=...)"
	@echo ""
	@echo "Quality Gates:"
	@echo "  quality-gates    - Check all quality gates"
	@echo "  security-gate    - Check security gate only"
	@echo "  performance-gate - Check performance gate only"
	@echo "  flakiness-gate   - Check flakiness gate only"
	@echo ""
	@echo "Setup & Maintenance:"
	@echo "  install          - Install dependencies and setup"
	@echo "  test-setup-verify - Verify test environment setup"
	@echo "  clean            - Clean up temporary files"
	@echo "  coverage         - Run tests with coverage report"
	@echo "  security-scan    - Run security scans"
	@echo "  ci               - Run full CI pipeline locally"
	@echo ""
	@echo "Examples:"
	@echo "  make test-golden"
	@echo "  make perf"
	@echo "  make chaos"
	@echo "  make replay RUN=episode_12345"
	@echo "  make test-impact CHANGED_FILES='app/api/main.py,app/core/config.py'"
	@echo "  TEST_MODE=GOLDEN make test-e2e"

# Installation and setup
install:
	pip install --upgrade pip
	pip install black ruff mypy pytest pytest-asyncio pytest-cov locust bandit safety
	pip install pre-commit
	pre-commit install
	@echo "Dependencies installed and pre-commit hooks configured"

# Code quality
lint:
	@echo "Running code quality checks..."
	black --check --diff .
	ruff check .
	mypy . --ignore-missing-imports
	@echo "Code quality checks completed"

format:
	@echo "Formatting code..."
	black .
	ruff check --fix .
	@echo "Code formatting completed"

# Test mode configurations
TEST_MODE ?= MOCK
TEST_SEED ?= 42
TEST_TIMEOUT ?= 300
TEST_TEMPERATURE ?= 0

# Test targets
test:
	@echo "Running all tests in $(TEST_MODE) mode..."
	TEST_MODE=$(TEST_MODE) TEST_SEED=$(TEST_SEED) pytest tests/ -v --tb=short --timeout=$(TEST_TIMEOUT)

test-golden:
	@echo "Running tests in GOLDEN mode (recorded cassettes)..."
	TEST_MODE=GOLDEN TEST_SEED=$(TEST_SEED) TEST_TEMPERATURE=0 pytest tests/ -v --tb=short --timeout=$(TEST_TIMEOUT)

test-live:
	@echo "Running tests in LIVE_SMOKE mode (real services)..."
	TEST_MODE=LIVE_SMOKE TEST_SEED=$(TEST_SEED) pytest tests/ -v --tb=short --timeout=$(TEST_TIMEOUT) -m "not slow"

test-unit:
	@echo "Running unit tests..."
	pytest tests/unit/ -v --tb=short

test-integration:
	@echo "Running integration tests..."
	pytest tests/integration/ -v --tb=short

test-e2e:
	@echo "Running E2E tests..."
	pytest tests/e2e/ -v --tb=short

test-performance:
	@echo "Running performance tests..."
	pytest tests/performance/ -v --tb=short
	python scripts/performance_regression_check.py

test-flakiness:
	@echo "Running flakiness detection..."
	python scripts/flakiness_ci_integration.py --max-retries 3

test-observability:
	@echo "Running observability tests..."
	pytest tests/observability/ -v --tb=short

test-chaos:
	@echo "Running chaos engineering tests..."
	pytest tests/chaos/ -v --tb=short

test-contract:
	@echo "Running contract tests..."
	pytest tests/contract/ -v --tb=short

test-realtime:
	@echo "Running realtime/WebSocket tests..."
	pytest tests/realtime/ -v --tb=short

# Combined test targets
test: test-unit test-integration test-e2e
	@echo "Core test suite completed"

all-tests: test-unit test-integration test-e2e test-performance test-observability test-chaos test-contract test-realtime
	@echo "All test suites completed"

# Coverage
coverage:
	@echo "Running tests with coverage..."
	pytest tests/unit/ --cov=. --cov-report=html --cov-report=term-missing --cov-report=xml
	@echo "Coverage report generated in htmlcov/"

# Security scanning
security-scan:
	@echo "Running security scans..."
	mkdir -p reports/security
	bandit -r . -f json -o reports/security/bandit-report.json || true
	safety check --json --output reports/security/safety-report.json || true
	@echo "Security scan completed"

# Advanced testing targets
perf:
	@echo "Running performance tests with regression checking..."
	pytest tests/performance/ -v --tb=short
	python scripts/performance_regression_check.py
	@echo "Performance regression check completed"

chaos:
	@echo "Running chaos engineering tests..."
	pytest tests/chaos/ -v --tb=short -m "not slow"
	@echo "Chaos engineering tests completed"

replay:
	@if [ -z "$(RUN)" ]; then \
		echo "Error: RUN parameter required. Usage: make replay RUN=episode_12345"; \
		exit 1; \
	fi
	@echo "Running episode replay for $(RUN)..."
	python eval/run_evaluation.py --type replay --episode-id $(RUN)
	@echo "Episode replay completed"

flakiness-report:
	@echo "Generating flakiness analysis report..."
	python -c "
import sys
sys.path.append('tests/_plugins')
from flakiness_manager import flakiness_reporter
report = flakiness_reporter.generate_weekly_report()
print('=== Weekly Flakiness Report ===')
print(f'Total Tests: {report[\"metrics\"][\"total_tests\"]}')
print(f'Stable Tests: {report[\"metrics\"][\"stable_tests\"]}')
print(f'Flaky Tests: {report[\"metrics\"][\"flaky_tests\"]}')
print(f'Quarantined Tests: {report[\"metrics\"][\"quarantined_tests\"]}')
print(f'Flakiness Rate: {report[\"metrics\"][\"flakiness_rate\"]:.1f}%')
if report['quarantine_list']:
    print('\n=== Quarantined Tests ===')
    for test in report['quarantine_list']:
        print(f'- {test[\"test_name\"]}: {test[\"quarantine_reason\"]}')
if report['recommendations']:
    print('\n=== Recommendations ===')
    for rec in report['recommendations']:
        print(f'- {rec}')
"

test-impact:
	@if [ -z "$(CHANGED_FILES)" ]; then \
		echo "Error: CHANGED_FILES parameter required. Usage: make test-impact CHANGED_FILES='app/api/main.py,app/core/config.py'"; \
		exit 1; \
	fi
	@echo "Analyzing test impact for changed files: $(CHANGED_FILES)"
	python -c "
import sys
sys.path.append('tests/_plugins')
from flakiness_manager import test_impact_analyzer
changed_files = '$(CHANGED_FILES)'.split(',')
impact_analysis = test_impact_analyzer.analyze_changed_files(changed_files)
impacted_tests = test_impact_analyzer.get_impacted_tests(changed_files)
print(f'Impact Level: {impact_analysis.impact_level.value}')
print(f'Affected Services: {impact_analysis.affected_services}')
print(f'Critical Path: {impact_analysis.critical_path}')
print(f'Coverage Score: {impact_analysis.coverage_score:.2f}')
print(f'Impacted Tests: {len(impacted_tests)}')
for test in impacted_tests[:10]:  # Show first 10
    print(f'  - {test}')
if len(impacted_tests) > 10:
    print(f'  ... and {len(impacted_tests) - 10} more')
"

# Quality gates
quality-gates: security-gate performance-gate flakiness-gate
	@echo "All quality gates passed ✅"

security-gate:
	@echo "Checking security gate..."
	pytest tests/integration/security/ tests/adversarial/ -v --tb=short
	@echo "Security gate passed ✅"

performance-gate:
	@echo "Checking performance gate..."
	pytest tests/performance/ -v --tb=short -m "regression"
	python scripts/performance_regression_check.py
	@echo "Performance gate passed ✅"

flakiness-gate:
	@echo "Checking flakiness gate..."
	python -c "
import sys
sys.path.append('tests/_plugins')
from flakiness_manager import flakiness_detector
metrics = flakiness_detector.get_global_flakiness_metrics()
flakiness_rate = metrics['flakiness_rate']
quarantine_rate = metrics['quarantine_rate']
if flakiness_rate > 5.0:
    print(f'ERROR: Flakiness rate {flakiness_rate:.1f}% exceeds budget of 5%')
    sys.exit(1)
if quarantine_rate > 2.0:
    print(f'ERROR: Quarantine rate {quarantine_rate:.1f}% exceeds budget of 2%')
    sys.exit(1)
print('Flakiness gate passed ✅')
"

# Setup verification
test-setup-verify:
	@echo "Verifying test environment setup..."
	@python -c "import pytest, asyncio, httpx, hypothesis, locust; print('✅ All test dependencies available')"
	@python -c "
import sys
sys.path.append('tests/_plugins')
from flakiness_manager import flakiness_detector, test_impact_analyzer
print('✅ Flakiness detection system ready')
print('✅ Test impact analysis ready')
"
	@echo "Test environment setup verified ✅"

# Enhanced test targets
test-security:
	@echo "Running security tests..."
	pytest tests/integration/security/ -v --tb=short

test-adversarial:
	@echo "Running adversarial tests..."
	pytest tests/adversarial/ -v --tb=short

# Full CI pipeline
ci: lint test all-tests security-scan quality-gates
	@echo "Full CI pipeline completed successfully ✅"

# Clean up
clean:
	@echo "Cleaning up temporary files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name "reports" -exec rm -rf {} +
	@echo "Cleanup completed"

# Development helpers
dev-setup: install
	@echo "Development environment setup completed"

quick-test: test-unit
	@echo "Quick test run completed"

# Docker helpers (if needed)
docker-build:
	docker build -t multi-ai-agent .

docker-test:
	docker run --rm multi-ai-agent make test

# Performance monitoring
benchmark:
	@echo "Running performance benchmarks..."
	python scripts/performance_regression_check.py --baseline-mode

# Documentation
docs:
	@echo "Generating documentation..."
	# Add documentation generation commands here

# Release helpers
version-check:
	@echo "Checking version consistency..."
	# Add version checking logic here

# Database helpers (if needed)
db-migrate:
	@echo "Running database migrations..."
	# Add database migration commands here

db-seed:
	@echo "Seeding database..."
	# Add database seeding commands here