#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting E2E Tests for AI Chatbot System${NC}"
echo "=================================================="

# Check if services are running
echo -e "${YELLOW}🔍 Checking if services are running...${NC}"
if ! docker-compose -f docker-compose.local.yml ps | grep -q "Up"; then
    echo -e "${RED}❌ Services are not running. Please start them first:${NC}"
    echo "   docker-compose -f docker-compose.local.yml up -d"
    exit 1
fi

# Wait for services to be ready
echo -e "${YELLOW}⏳ Waiting for services to be ready...${NC}"
sleep 10

# Check if E2E test dependencies are installed
echo -e "${YELLOW}📦 Checking E2E test dependencies...${NC}"
if ! python -c "import pytest, httpx" 2>/dev/null; then
    echo -e "${YELLOW}📥 Installing E2E test dependencies...${NC}"
    pip install -r tests/e2e/requirements.txt
fi

# Create test results directory
mkdir -p test-results/e2e

# Run E2E tests with different configurations
echo -e "${BLUE}🧪 Running E2E Test Suites${NC}"
echo "================================"

# Test 1: User Workflows
echo -e "${YELLOW}📋 Running User Workflow Tests...${NC}"
pytest tests/e2e/test_user_workflows.py \
    -v \
    --tb=short \
    --html=test-results/e2e/user-workflows-report.html \
    --self-contained-html \
    --junitxml=test-results/e2e/user-workflows-results.xml \
    || echo -e "${RED}⚠️ Some user workflow tests failed${NC}"

echo ""

# Test 2: Service Integration
echo -e "${YELLOW}🔗 Running Service Integration Tests...${NC}"
pytest tests/e2e/test_service_integration.py \
    -v \
    --tb=short \
    --html=test-results/e2e/service-integration-report.html \
    --self-contained-html \
    --junitxml=test-results/e2e/service-integration-results.xml \
    || echo -e "${RED}⚠️ Some service integration tests failed${NC}"

echo ""

# Test 3: Performance Tests
echo -e "${YELLOW}⚡ Running Performance Tests...${NC}"
pytest tests/e2e/test_performance_e2e.py \
    -v \
    --tb=short \
    --html=test-results/e2e/performance-report.html \
    --self-contained-html \
    --junitxml=test-results/e2e/performance-results.xml \
    -m "not slow" \
    || echo -e "${RED}⚠️ Some performance tests failed${NC}"

echo ""

# Run all E2E tests together
echo -e "${BLUE}🎯 Running Complete E2E Test Suite${NC}"
echo "===================================="

pytest tests/e2e/ \
    -v \
    --tb=short \
    --html=test-results/e2e/complete-e2e-report.html \
    --self-contained-html \
    --junitxml=test-results/e2e/complete-e2e-results.xml \
    --durations=10 \
    -m "not slow" \
    || echo -e "${RED}⚠️ Some E2E tests failed${NC}"

echo ""

# Generate summary report
echo -e "${BLUE}📊 E2E Test Summary${NC}"
echo "===================="

if [ -f "test-results/e2e/complete-e2e-results.xml" ]; then
    echo -e "${GREEN}✅ E2E test results saved to:${NC}"
    echo "   📄 HTML Report: test-results/e2e/complete-e2e-report.html"
    echo "   📄 XML Results: test-results/e2e/complete-e2e-results.xml"
    echo "   📄 Individual Reports: test-results/e2e/*.html"
else
    echo -e "${RED}❌ No test results generated${NC}"
fi

echo ""
echo -e "${BLUE}🌐 Service URLs for Manual E2E Testing:${NC}"
echo "============================================="
echo "🤖 AI Chatbot:     http://localhost:3001"
echo "🌍 Web Frontend:   http://localhost:3000"
echo "👨‍💼 Admin Portal:   http://localhost:8099"
echo "🔌 API Gateway:    http://localhost:8000"
echo "🧠 Model Gateway:  http://localhost:8080"
echo "⚙️ Config Service: http://localhost:8090"
echo "🛡️ Policy Adapter: http://localhost:8091"
echo "🔍 Retrieval:      http://localhost:8081"
echo "🛠️ Tools Service:  http://localhost:8082"
echo "🔀 Router Service: http://localhost:8083"

echo ""
echo -e "${YELLOW}💡 E2E Test Tips:${NC}"
echo "==================="
echo "1. Open HTML reports in browser for detailed results"
echo "2. Check individual service health endpoints"
echo "3. Test user workflows manually in browsers"
echo "4. Monitor logs: docker-compose -f docker-compose.local.yml logs -f"
echo "5. Run specific test categories:"
echo "   pytest tests/e2e/test_user_workflows.py -v"
echo "   pytest tests/e2e/test_service_integration.py -v"
echo "   pytest tests/e2e/test_performance_e2e.py -v"

echo ""
echo -e "${GREEN}🎉 E2E Test Suite Complete!${NC}"
