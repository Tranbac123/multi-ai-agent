#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Interactive Service Tests${NC}"
echo "================================"
echo "This script will help you test your services interactively"
echo ""

# Function to test a service
test_service() {
    local service_name="$1"
    local url="$2"
    local description="$3"
    
    echo -e "${YELLOW}🔍 Testing $service_name${NC}"
    echo "   URL: $url"
    echo "   Description: $description"
    echo ""
    
    if curl -s -f "$url" > /dev/null 2>&1; then
        echo -e "   ${GREEN}✅ SUCCESS${NC} - $service_name is responding"
        echo "   Response:"
        curl -s "$url" | head -c 200
        echo ""
    else
        echo -e "   ${RED}❌ FAILED${NC} - $service_name is not responding"
        echo "   Error: $(curl -s -w '%{http_code}' -o /dev/null "$url" 2>&1)"
    fi
    echo ""
}

# Function to test API endpoint
test_api() {
    local service_name="$1"
    local url="$2"
    local method="$3"
    local data="$4"
    local description="$5"
    
    echo -e "${YELLOW}🔍 Testing $service_name API${NC}"
    echo "   URL: $url"
    echo "   Method: $method"
    echo "   Description: $description"
    echo ""
    
    if [[ "$method" == "GET" ]]; then
        if curl -s -f "$url" > /dev/null 2>&1; then
            echo -e "   ${GREEN}✅ SUCCESS${NC} - $service_name API is responding"
            echo "   Response:"
            curl -s "$url" | head -c 200
            echo ""
        else
            echo -e "   ${RED}❌ FAILED${NC} - $service_name API is not responding"
        fi
    else
        if curl -s -X "$method" -H "Content-Type: application/json" -d "$data" "$url" > /dev/null 2>&1; then
            echo -e "   ${GREEN}✅ SUCCESS${NC} - $service_name API is responding"
            echo "   Response:"
            curl -s -X "$method" -H "Content-Type: application/json" -d "$data" "$url" | head -c 200
            echo ""
        else
            echo -e "   ${RED}❌ FAILED${NC} - $service_name API is not responding"
        fi
    fi
    echo ""
}

echo -e "${BLUE}📊 1. INFRASTRUCTURE TESTS${NC}"
echo "==============================="

# Test PostgreSQL
echo -e "${YELLOW}🔍 Testing PostgreSQL${NC}"
if docker exec multi-ai-agent-postgres-1 pg_isready -U postgres > /dev/null 2>&1; then
    echo -e "   ${GREEN}✅ SUCCESS${NC} - PostgreSQL is ready"
    echo "   Database version:"
    docker exec multi-ai-agent-postgres-1 psql -U postgres -d ai_agent -c "SELECT version();" | head -2
else
    echo -e "   ${RED}❌ FAILED${NC} - PostgreSQL is not ready"
fi
echo ""

# Test Redis
echo -e "${YELLOW}🔍 Testing Redis${NC}"
if docker exec multi-ai-agent-redis-1 redis-cli ping > /dev/null 2>&1; then
    echo -e "   ${GREEN}✅ SUCCESS${NC} - Redis is responding"
    echo "   Response: $(docker exec multi-ai-agent-redis-1 redis-cli ping)"
else
    echo -e "   ${RED}❌ FAILED${NC} - Redis is not responding"
fi
echo ""

# Test NATS
echo -e "${YELLOW}🔍 Testing NATS${NC}"
if curl -s http://localhost:8222/varz > /dev/null 2>&1; then
    echo -e "   ${GREEN}✅ SUCCESS${NC} - NATS is responding"
    echo "   JetStream enabled: $(curl -s http://localhost:8222/varz | grep -o '"jetstream":true' || echo 'false')"
else
    echo -e "   ${RED}❌ FAILED${NC} - NATS is not responding"
fi
echo ""

echo -e "${BLUE}🔧 2. BACKEND SERVICE TESTS${NC}"
echo "================================="

# Test API Gateway
test_service "API Gateway Health" "http://localhost:8000/healthz" "API Gateway health check"
test_api "API Gateway Ask" "http://localhost:8000/ask" "POST" '{"query": "Hello, how are you?"}' "API Gateway ask endpoint"

# Test Model Gateway
test_service "Model Gateway Health" "http://localhost:8080/healthz" "Model Gateway health check"
test_api "Model Gateway Chat" "http://localhost:8080/v1/chat" "POST" '{"messages": [{"role": "user", "content": "Hello"}]}' "Model Gateway chat endpoint"

# Test Config Service
test_service "Config Service Health" "http://localhost:8090/healthz" "Config Service health check"

# Test Policy Adapter
test_service "Policy Adapter Health" "http://localhost:8091/healthz" "Policy Adapter health check"
test_api "Policy Adapter Check" "http://localhost:8091/v1/check" "POST" '{"user": "test", "resource": "test"}' "Policy Adapter authorization check"

# Test Retrieval Service
test_service "Retrieval Service Health" "http://localhost:8081/healthz" "Retrieval Service health check"

# Test Tools Service
test_service "Tools Service Health" "http://localhost:8082/healthz" "Tools Service health check"

# Test Router Service
test_service "Router Service Health" "http://localhost:8083/healthz" "Router Service health check"

echo -e "${BLUE}🌐 3. FRONTEND SERVICE TESTS${NC}"
echo "================================="

# Test AI Chatbot
test_service "AI Chatbot" "http://localhost:3001" "AI Chatbot frontend"

# Test Web Frontend
test_service "Web Frontend Root" "http://localhost:3000" "Web Frontend root path"
test_service "Web Frontend Index" "http://localhost:3000/index.html" "Web Frontend index.html"

# Test Admin Portal
test_service "Admin Portal" "http://localhost:8099" "Admin Portal frontend"

echo -e "${BLUE}🔗 4. INTEGRATION TESTS${NC}"
echo "============================="

# Test service-to-service communication
echo -e "${YELLOW}🔍 Testing Service-to-Service Communication${NC}"
echo "   Testing API Gateway to Model Gateway..."

if docker exec multi-ai-agent-api-gateway-1 curl -s http://model-gateway:8080/healthz > /dev/null 2>&1; then
    echo -e "   ${GREEN}✅ SUCCESS${NC} - API Gateway can reach Model Gateway"
    echo "   Response:"
    docker exec multi-ai-agent-api-gateway-1 curl -s http://model-gateway:8080/healthz | head -c 100
    echo ""
else
    echo -e "   ${RED}❌ FAILED${NC} - API Gateway cannot reach Model Gateway"
fi
echo ""

echo -e "${BLUE}📈 5. PERFORMANCE TESTS${NC}"
echo "============================="

# Test response times
echo -e "${YELLOW}🔍 Testing Response Times${NC}"

# API Gateway response time
echo "   API Gateway response time:"
time curl -s http://localhost:8000/healthz > /dev/null 2>&1 && echo -e "   ${GREEN}✅ Fast response${NC}" || echo -e "   ${RED}❌ Slow response${NC}"

# Model Gateway response time
echo "   Model Gateway response time:"
time curl -s http://localhost:8080/healthz > /dev/null 2>&1 && echo -e "   ${GREEN}✅ Fast response${NC}" || echo -e "   ${RED}❌ Slow response${NC}"

# Frontend response time
echo "   AI Chatbot response time:"
time curl -s http://localhost:3001 > /dev/null 2>&1 && echo -e "   ${GREEN}✅ Fast response${NC}" || echo -e "   ${RED}❌ Slow response${NC}"

echo ""

echo -e "${BLUE}🎯 6. MANUAL TESTING SUGGESTIONS${NC}"
echo "====================================="
echo ""
echo -e "${YELLOW}🌐 Open these URLs in your browser:${NC}"
echo "   🤖 AI Chatbot:     http://localhost:3001"
echo "   🌍 Web Frontend:   http://localhost:3000/index.html"
echo "   👨‍💼 Admin Portal:   http://localhost:8099"
echo ""
echo -e "${YELLOW}🔧 Test these API endpoints:${NC}"
echo "   🔌 API Gateway:    http://localhost:8000/healthz"
echo "   🧠 Model Gateway:  http://localhost:8080/healthz"
echo "   🛡️ Policy Adapter: http://localhost:8091/healthz"
echo ""
echo -e "${YELLOW}💡 Try these manual tests:${NC}"
echo "   1. Open AI Chatbot and send a message"
echo "   2. Test Web Frontend by navigating through pages"
echo "   3. Check Admin Portal dashboard"
echo "   4. Test API endpoints with curl or Postman"
echo "   5. Verify database operations through services"
echo ""

echo -e "${BLUE}📊 7. SERVICE STATUS SUMMARY${NC}"
echo "================================="
echo ""
echo "Current service status:"
docker-compose -f docker-compose.local.yml ps
echo ""

echo -e "${GREEN}🎉 Interactive testing complete!${NC}"
echo "Check the results above and try the manual tests in your browser."
