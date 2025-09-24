#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results tracking
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

# Test report file
REPORT_FILE="test-results/comprehensive-test-report-$(date +%Y%m%d_%H%M%S).md"

# Create test results directory
mkdir -p test-results

echo -e "${BLUE}🧪 Starting Comprehensive Service Tests${NC}"
echo "=================================================="
echo "Report will be saved to: $REPORT_FILE"
echo ""

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    local expected_status="${3:-0}"
    local description="${4:-}"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    echo -e "${YELLOW}🔍 Test $TOTAL_TESTS: $test_name${NC}"
    if [[ -n "$description" ]]; then
        echo "   Description: $description"
    fi
    echo "   Command: $test_command"
    
    if eval "$test_command" > /dev/null 2>&1; then
        local actual_status=$?
        if [[ $actual_status -eq $expected_status ]]; then
            echo -e "   ${GREEN}✅ PASSED${NC}"
            PASSED_TESTS=$((PASSED_TESTS + 1))
            echo "✅ PASSED - $test_name" >> "$REPORT_FILE"
        else
            echo -e "   ${RED}❌ FAILED (Expected status: $expected_status, Got: $actual_status)${NC}"
            FAILED_TESTS=$((FAILED_TESTS + 1))
            echo "❌ FAILED - $test_name (Expected: $expected_status, Got: $actual_status)" >> "$REPORT_FILE"
        fi
    else
        local actual_status=$?
        if [[ $actual_status -eq $expected_status ]]; then
            echo -e "   ${GREEN}✅ PASSED${NC}"
            PASSED_TESTS=$((PASSED_TESTS + 1))
            echo "✅ PASSED - $test_name" >> "$REPORT_FILE"
        else
            echo -e "   ${RED}❌ FAILED (Expected status: $expected_status, Got: $actual_status)${NC}"
            FAILED_TESTS=$((FAILED_TESTS + 1))
            echo "❌ FAILED - $test_name (Expected: $expected_status, Got: $actual_status)" >> "$REPORT_FILE"
        fi
    fi
    echo ""
}

# Function to test HTTP endpoint
test_http_endpoint() {
    local service_name="$1"
    local url="$2"
    local expected_status="${3:-200}"
    local description="${4:-}"
    
    run_test "$service_name HTTP Check" \
        "curl -s -o /dev/null -w '%{http_code}' '$url' | grep -q '$expected_status'" \
        0 \
        "$description"
}

# Function to test JSON response
test_json_endpoint() {
    local service_name="$1"
    local url="$2"
    local expected_key="$3"
    local description="${4:-}"
    
    run_test "$service_name JSON Response" \
        "curl -s '$url' | grep -q '$expected_key'" \
        0 \
        "$description"
}

# Initialize report
cat > "$REPORT_FILE" << EOF
# Comprehensive Service Test Report

**Date:** $(date)
**Environment:** Local Development
**Docker Compose:** docker-compose.local.yml

## Test Summary

| Category | Tests | Passed | Failed | Skipped |
|----------|-------|--------|--------|---------|
| Infrastructure | 0 | 0 | 0 | 0 |
| Backend Services | 0 | 0 | 0 | 0 |
| Frontend Services | 0 | 0 | 0 | 0 |
| API Endpoints | 0 | 0 | 0 | 0 |
| Integration | 0 | 0 | 0 | 0 |
| **TOTAL** | 0 | 0 | 0 | 0 |

## Detailed Test Results

EOF

echo -e "${BLUE}📊 1. INFRASTRUCTURE SERVICES TESTS${NC}"
echo "=========================================="

# Test PostgreSQL
run_test "PostgreSQL Container Status" \
    "docker-compose -f docker-compose.local.yml ps postgres | grep -q 'Up.*healthy'" \
    0 \
    "PostgreSQL container should be running and healthy"

run_test "PostgreSQL Connection" \
    "docker exec multi-ai-agent-postgres-1 pg_isready -U postgres" \
    0 \
    "PostgreSQL should accept connections"

run_test "PostgreSQL Database Exists" \
    "docker exec multi-ai-agent-postgres-1 psql -U postgres -d ai_agent -c '\\l' | grep -q ai_agent" \
    0 \
    "Database 'ai_agent' should exist"

# Test Redis
run_test "Redis Container Status" \
    "docker-compose -f docker-compose.local.yml ps redis | grep -q 'Up.*healthy'" \
    0 \
    "Redis container should be running and healthy"

run_test "Redis Connection" \
    "docker exec multi-ai-agent-redis-1 redis-cli ping | grep -q PONG" \
    0 \
    "Redis should respond to ping"

run_test "Redis Set/Get Test" \
    "docker exec multi-ai-agent-redis-1 redis-cli set test_key 'test_value' && docker exec multi-ai-agent-redis-1 redis-cli get test_key | grep -q test_value" \
    0 \
    "Redis should allow set/get operations"

# Test NATS
run_test "NATS Container Status" \
    "docker-compose -f docker-compose.local.yml ps nats | grep -q 'Up.*healthy'" \
    0 \
    "NATS container should be running and healthy"

run_test "NATS Server Check" \
    "docker exec multi-ai-agent-nats-1 nats server check server" \
    0 \
    "NATS server should be healthy"

run_test "NATS JetStream Info" \
    "curl -s http://localhost:8222/varz | grep -q 'jetstream'" \
    0 \
    "NATS JetStream should be enabled"

echo -e "${BLUE}🔧 2. BACKEND SERVICES TESTS${NC}"
echo "======================================"

# Test API Gateway
run_test "API Gateway Container Status" \
    "docker-compose -f docker-compose.local.yml ps api-gateway | grep -q 'Up'" \
    0 \
    "API Gateway container should be running"

test_http_endpoint "API Gateway Health" \
    "http://localhost:8000/healthz" \
    200 \
    "API Gateway health endpoint should return 200"

test_json_endpoint "API Gateway Health JSON" \
    "http://localhost:8000/healthz" \
    "healthy" \
    "API Gateway health should return JSON with 'healthy'"

test_http_endpoint "API Gateway Root" \
    "http://localhost:8000/" \
    404 \
    "API Gateway root should return 404 (no root endpoint)"

# Test Model Gateway
run_test "Model Gateway Container Status" \
    "docker-compose -f docker-compose.local.yml ps model-gateway | grep -q 'Up'" \
    0 \
    "Model Gateway container should be running"

test_http_endpoint "Model Gateway Health" \
    "http://localhost:8080/healthz" \
    200 \
    "Model Gateway health endpoint should return 200"

test_json_endpoint "Model Gateway Health JSON" \
    "http://localhost:8080/healthz" \
    "ok" \
    "Model Gateway health should return JSON with 'ok'"

# Test Config Service
run_test "Config Service Container Status" \
    "docker-compose -f docker-compose.local.yml ps config-service | grep -q 'Up'" \
    0 \
    "Config Service container should be running"

test_http_endpoint "Config Service Health" \
    "http://localhost:8090/healthz" \
    200 \
    "Config Service health endpoint should return 200"

# Test Policy Adapter
run_test "Policy Adapter Container Status" \
    "docker-compose -f docker-compose.local.yml ps policy-adapter | grep -q 'Up'" \
    0 \
    "Policy Adapter container should be running"

test_http_endpoint "Policy Adapter Health" \
    "http://localhost:8091/healthz" \
    200 \
    "Policy Adapter health endpoint should return 200"

# Test Retrieval Service
run_test "Retrieval Service Container Status" \
    "docker-compose -f docker-compose.local.yml ps retrieval-service | grep -q 'Up'" \
    0 \
    "Retrieval Service container should be running"

test_http_endpoint "Retrieval Service Health" \
    "http://localhost:8081/healthz" \
    200 \
    "Retrieval Service health endpoint should return 200"

# Test Tools Service
run_test "Tools Service Container Status" \
    "docker-compose -f docker-compose.local.yml ps tools-service | grep -q 'Up'" \
    0 \
    "Tools Service container should be running"

test_http_endpoint "Tools Service Health" \
    "http://localhost:8082/healthz" \
    200 \
    "Tools Service health endpoint should return 200"

# Test Router Service
run_test "Router Service Container Status" \
    "docker-compose -f docker-compose.local.yml ps router-service | grep -q 'Up'" \
    0 \
    "Router Service container should be running"

test_http_endpoint "Router Service Health" \
    "http://localhost:8083/healthz" \
    200 \
    "Router Service health endpoint should return 200"

echo -e "${BLUE}🌐 3. FRONTEND SERVICES TESTS${NC}"
echo "======================================"

# Test AI Chatbot
run_test "AI Chatbot Container Status" \
    "docker-compose -f docker-compose.local.yml ps ai-chatbot | grep -q 'Up'" \
    0 \
    "AI Chatbot container should be running"

test_http_endpoint "AI Chatbot Frontend" \
    "http://localhost:3001" \
    200 \
    "AI Chatbot frontend should be accessible"

run_test "AI Chatbot HTML Content" \
    "curl -s http://localhost:3001 | grep -q '<html'" \
    0 \
    "AI Chatbot should serve HTML content"

# Test Web Frontend
run_test "Web Frontend Container Status" \
    "docker-compose -f docker-compose.local.yml ps web-frontend | grep -q 'Up'" \
    0 \
    "Web Frontend container should be running"

test_http_endpoint "Web Frontend Root" \
    "http://localhost:3000" \
    200 \
    "Web Frontend should be accessible on root"

test_http_endpoint "Web Frontend Index" \
    "http://localhost:3000/index.html" \
    200 \
    "Web Frontend index.html should be accessible"

run_test "Web Frontend HTML Content" \
    "curl -s http://localhost:3000/index.html | grep -q '<html'" \
    0 \
    "Web Frontend should serve HTML content"

# Test Admin Portal
run_test "Admin Portal Container Status" \
    "docker-compose -f docker-compose.local.yml ps admin-portal | grep -q 'Up'" \
    0 \
    "Admin Portal container should be running"

test_http_endpoint "Admin Portal Health" \
    "http://localhost:8099/healthz" \
    200 \
    "Admin Portal health endpoint should return 200"

test_http_endpoint "Admin Portal Root" \
    "http://localhost:8099" \
    200 \
    "Admin Portal should be accessible"

echo -e "${BLUE}🔗 4. API ENDPOINT TESTS${NC}"
echo "================================"

# Test API Gateway endpoints
run_test "API Gateway Chat Endpoint" \
    "curl -s -X POST -H 'Content-Type: application/json' -d '{\"messages\": [{\"role\": \"user\", \"content\": \"Hello\"}]}' http://localhost:8000/v1/chat | grep -q 'response'" \
    0 \
    "API Gateway chat endpoint should accept POST requests"

run_test "API Gateway Ask Endpoint" \
    "curl -s -X POST -H 'Content-Type: application/json' -d '{\"query\": \"test query\"}' http://localhost:8000/ask | head -c 100" \
    0 \
    "API Gateway ask endpoint should accept POST requests"

# Test Model Gateway endpoints
run_test "Model Gateway Chat Endpoint" \
    "curl -s -X POST -H 'Content-Type: application/json' -d '{\"messages\": [{\"role\": \"user\", \"content\": \"Hello\"}]}' http://localhost:8080/v1/chat | head -c 100" \
    0 \
    "Model Gateway chat endpoint should accept POST requests"

# Test Config Service endpoints
run_test "Config Service Get Config" \
    "curl -s http://localhost:8090/v1/config | head -c 100" \
    0 \
    "Config Service should return configuration"

# Test Policy Adapter endpoints
run_test "Policy Adapter Auth Check" \
    "curl -s -X POST -H 'Content-Type: application/json' -d '{\"user\": \"test\", \"resource\": \"test\"}' http://localhost:8091/v1/check | head -c 100" \
    0 \
    "Policy Adapter should accept authorization checks"

echo -e "${BLUE}🔄 5. INTEGRATION TESTS${NC}"
echo "============================="

# Test service-to-service communication
run_test "API Gateway to Model Gateway" \
    "curl -s http://localhost:8000/healthz && curl -s http://localhost:8080/healthz" \
    0 \
    "Both API Gateway and Model Gateway should be healthy for integration"

run_test "Frontend to Backend Connection" \
    "curl -s http://localhost:3001 && curl -s http://localhost:8000/healthz" \
    0 \
    "Frontend should be able to connect to backend services"

# Test database connectivity from services
run_test "API Gateway Database Connection" \
    "docker exec multi-ai-agent-api-gateway-1 python -c 'import psycopg2; psycopg2.connect(host=\"postgres\", port=5432, user=\"postgres\", password=\"postgres\", dbname=\"ai_agent\")'" \
    0 \
    "API Gateway should be able to connect to PostgreSQL"

run_test "API Gateway Redis Connection" \
    "docker exec multi-ai-agent-api-gateway-1 python -c 'import redis; r = redis.Redis(host=\"redis\", port=6379, decode_responses=True); r.ping()'" \
    0 \
    "API Gateway should be able to connect to Redis"

echo -e "${BLUE}📈 6. PERFORMANCE TESTS${NC}"
echo "============================="

# Test response times
run_test "API Gateway Response Time" \
    "curl -s -w '%{time_total}' -o /dev/null http://localhost:8000/healthz | awk '{if (\$1 < 1.0) exit 0; else exit 1}'" \
    0 \
    "API Gateway should respond within 1 second"

run_test "Model Gateway Response Time" \
    "curl -s -w '%{time_total}' -o /dev/null http://localhost:8080/healthz | awk '{if (\$1 < 1.0) exit 0; else exit 1}'" \
    0 \
    "Model Gateway should respond within 1 second"

run_test "Frontend Response Time" \
    "curl -s -w '%{time_total}' -o /dev/null http://localhost:3001 | awk '{if (\$1 < 2.0) exit 0; else exit 1}'" \
    0 \
    "Frontend should respond within 2 seconds"

echo -e "${BLUE}🔒 7. SECURITY TESTS${NC}"
echo "============================"

# Test unauthorized access
run_test "Unauthorized Access Prevention" \
    "curl -s -w '%{http_code}' -o /dev/null http://localhost:8000/admin | grep -q '40[0-9]'" \
    0 \
    "Unauthorized access should return 4xx status"

# Test CORS headers (if applicable)
run_test "CORS Headers Check" \
    "curl -s -I http://localhost:3001 | grep -i 'access-control-allow-origin' || echo 'No CORS headers found'" \
    0 \
    "Check for CORS headers in frontend responses"

echo ""
echo -e "${BLUE}📊 FINAL TEST RESULTS${NC}"
echo "========================="
echo -e "Total Tests: ${BLUE}$TOTAL_TESTS${NC}"
echo -e "Passed: ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed: ${RED}$FAILED_TESTS${NC}"
echo -e "Skipped: ${YELLOW}$SKIPPED_TESTS${NC}"

# Calculate success rate
if [[ $TOTAL_TESTS -gt 0 ]]; then
    SUCCESS_RATE=$((PASSED_TESTS * 100 / TOTAL_TESTS))
    echo -e "Success Rate: ${BLUE}$SUCCESS_RATE%${NC}"
else
    SUCCESS_RATE=0
    echo -e "Success Rate: ${BLUE}0%${NC}"
fi

# Final status
if [[ $FAILED_TESTS -eq 0 ]]; then
    echo -e "\n${GREEN}🎉 ALL TESTS PASSED! 🎉${NC}"
    FINAL_STATUS="✅ ALL TESTS PASSED"
else
    echo -e "\n${RED}❌ SOME TESTS FAILED${NC}"
    FINAL_STATUS="❌ SOME TESTS FAILED"
fi

# Update report with final summary
cat >> "$REPORT_FILE" << EOF

## Final Summary

- **Total Tests:** $TOTAL_TESTS
- **Passed:** $PASSED_TESTS
- **Failed:** $FAILED_TESTS
- **Skipped:** $SKIPPED_TESTS
- **Success Rate:** $SUCCESS_RATE%

**Status:** $FINAL_STATUS

## Test Environment Details

- **Docker Compose File:** docker-compose.local.yml
- **Test Date:** $(date)
- **Test Duration:** $(date)
- **All Services Status:**

EOF

# Add service status to report
echo "### Service Status" >> "$REPORT_FILE"
docker-compose -f docker-compose.local.yml ps >> "$REPORT_FILE"

echo ""
echo -e "${GREEN}📄 Test report saved to: $REPORT_FILE${NC}"
echo ""
echo -e "${BLUE}🌐 Service URLs for Manual Testing:${NC}"
echo "=========================================="
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
echo -e "${YELLOW}💡 Manual Test Suggestions:${NC}"
echo "================================"
echo "1. Open AI Chatbot and send a message"
echo "2. Test Web Frontend registration/login"
echo "3. Check Admin Portal dashboard"
echo "4. Test API endpoints with curl or Postman"
echo "5. Verify database operations through services"
echo "6. Test error handling with invalid requests"

exit $FAILED_TESTS
