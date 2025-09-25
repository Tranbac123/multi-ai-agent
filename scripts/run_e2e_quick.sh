#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}⚡ Quick E2E Tests${NC}"
echo "==================="

# Check if services are running
if ! docker-compose -f docker-compose.local.yml ps | grep -q "Up"; then
    echo -e "${RED}❌ Services are not running. Please start them first.${NC}"
    exit 1
fi

# Install dependencies if needed
if ! python -c "import pytest, httpx" 2>/dev/null; then
    echo -e "${YELLOW}📦 Installing E2E dependencies...${NC}"
    pip install -r tests/e2e/requirements.txt
fi

# Create results directory
mkdir -p test-results/e2e

# Run quick E2E tests (excluding slow performance tests)
echo -e "${YELLOW}🧪 Running Quick E2E Tests...${NC}"

pytest tests/e2e/ \
    -v \
    --tb=short \
    --html=test-results/e2e/quick-e2e-report.html \
    --self-contained-html \
    -m "not slow" \
    --durations=5 \
    || echo -e "${RED}⚠️ Some quick E2E tests failed${NC}"

echo ""
echo -e "${GREEN}✅ Quick E2E tests complete!${NC}"
echo -e "${BLUE}📄 Report: test-results/e2e/quick-e2e-report.html${NC}"
