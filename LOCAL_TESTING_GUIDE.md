# 🧪 Local Testing Guide for AI Chatbot Services

## 📋 Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Environment Setup](#environment-setup)
4. [Service Testing](#service-testing)
5. [API Testing](#api-testing)
6. [Frontend Testing](#frontend-testing)
7. [Integration Testing](#integration-testing)
8. [Load Testing](#load-testing)
9. [Security Testing](#security-testing)
10. [Performance Testing](#performance-testing)
11. [Database Testing](#database-testing)
12. [Troubleshooting](#troubleshooting)
13. [Test Automation](#test-automation)

---

## 🎯 Overview

This guide covers comprehensive testing of your AI chatbot microservices architecture in your local development environment. It includes:

- **Unit Tests**: Individual service testing
- **Integration Tests**: Service-to-service communication
- **API Tests**: REST endpoint validation
- **Frontend Tests**: UI and user interaction testing
- **Load Tests**: Performance under stress
- **Security Tests**: Vulnerability scanning
- **Database Tests**: Data persistence and queries

---

## ✅ Prerequisites

### Required Tools

```bash
# Check if tools are installed
docker --version
docker-compose --version
curl --version
jq --version
python3 --version
node --version
npm --version

# Install missing tools (macOS)
brew install docker docker-compose curl jq

# Install missing tools (Ubuntu/Debian)
sudo apt update
sudo apt install docker.io docker-compose curl jq python3 python3-pip nodejs npm
```

### Environment Variables

```bash
# Copy environment template
cp env.example .env

# Edit with your values
nano .env
```

---

## 🔧 Environment Setup

### 1. Start All Services

```bash
# Start complete environment
./scripts/start-local.sh

# Or start services individually
docker-compose -f docker-compose.local.yml up -d postgres redis nats
sleep 10
docker-compose -f docker-compose.local.yml up -d api-gateway model-gateway
sleep 5
docker-compose -f docker-compose.local.yml up -d ai-chatbot admin-portal web-frontend
```

### 2. Verify Services are Running

```bash
# Check all containers
docker-compose -f docker-compose.local.yml ps

# Check logs
docker-compose -f docker-compose.local.yml logs -f

# Check specific service logs
docker-compose -f docker-compose.local.yml logs -f ai-chatbot
```

### 3. Wait for Services to be Ready

```bash
# Wait for API Gateway
until curl -f http://localhost:8000/healthz; do
  echo "Waiting for API Gateway..."
  sleep 5
done

# Wait for Chatbot UI
until curl -f http://localhost:3001; do
  echo "Waiting for Chatbot UI..."
  sleep 5
done

echo "✅ All services are ready!"
```

---

## 🔍 Service Testing

### 1. Health Check Tests

```bash
#!/bin/bash
# scripts/test-health.sh

echo "🔍 Testing service health checks..."

SERVICES=(
  "http://localhost:8000/healthz:API Gateway"
  "http://localhost:3001:AI Chatbot"
  "http://localhost:3000:Web Frontend"
  "http://localhost:8099:Admin Portal"
  "http://localhost:8080/healthz:Model Gateway"
  "http://localhost:8090/healthz:Config Service"
  "http://localhost:8091/healthz:Policy Adapter"
)

for service in "${SERVICES[@]}"; do
  URL="${service%%:*}"
  NAME="${service##*:}"

  echo -n "Testing $NAME... "
  if curl -f -s "$URL" > /dev/null; then
    echo "✅ OK"
  else
    echo "❌ FAILED"
  fi
done
```

### 2. Service Discovery Test

```bash
#!/bin/bash
# scripts/test-service-discovery.sh

echo "🔍 Testing service discovery..."

# Test internal service communication
echo "Testing API Gateway -> Model Gateway..."
RESPONSE=$(curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello, test connection"}')

if echo "$RESPONSE" | jq -e '.answer' > /dev/null; then
  echo "✅ Service discovery working"
else
  echo "❌ Service discovery failed"
  echo "Response: $RESPONSE"
fi
```

---

## 🔌 API Testing

### 1. Basic API Tests

```bash
#!/bin/bash
# scripts/test-api.sh

echo "🔌 Testing API endpoints..."

# Test chatbot endpoint
echo "Testing /ask endpoint..."
RESPONSE=$(curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "What is artificial intelligence?"}')

echo "Response:"
echo "$RESPONSE" | jq '.'

# Validate response structure
if echo "$RESPONSE" | jq -e '.answer, .citations, .trace' > /dev/null; then
  echo "✅ /ask endpoint working correctly"
else
  echo "❌ /ask endpoint response invalid"
fi

# Test health endpoint
echo "Testing /healthz endpoint..."
HEALTH=$(curl -s http://localhost:8000/healthz)
echo "Health response: $HEALTH"

# Test root endpoint
echo "Testing root endpoint..."
ROOT=$(curl -s http://localhost:8000/)
echo "Root response: $ROOT"
```

### 2. API Stress Test

```bash
#!/bin/bash
# scripts/test-api-stress.sh

echo "⚡ Testing API under stress..."

# Simple stress test with curl
for i in {1..10}; do
  echo "Request $i..."
  curl -s -X POST http://localhost:8000/ask \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"Test question $i\"}" > /dev/null &
done

wait
echo "✅ Stress test completed"
```

### 3. API Error Handling Test

```bash
#!/bin/bash
# scripts/test-api-errors.sh

echo "🚨 Testing API error handling..."

# Test invalid JSON
echo "Testing invalid JSON..."
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"invalid": json}' || echo "Expected error for invalid JSON"

# Test missing fields
echo "Testing missing query field..."
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{}' || echo "Expected error for missing query"

# Test very long query
echo "Testing very long query..."
LONG_QUERY=$(printf 'a%.0s' {1..10000})
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$LONG_QUERY\"}" || echo "Expected error for long query"

echo "✅ Error handling tests completed"
```

---

## 🌐 Frontend Testing

### 1. Frontend Accessibility Tests

```bash
#!/bin/bash
# scripts/test-frontend.sh

echo "🌐 Testing frontend applications..."

# Test chatbot UI
echo "Testing AI Chatbot UI..."
CHATBOT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3001)
if [ "$CHATBOT_STATUS" = "200" ]; then
  echo "✅ Chatbot UI accessible"
else
  echo "❌ Chatbot UI not accessible (HTTP $CHATBOT_STATUS)"
fi

# Test web frontend
echo "Testing Web Frontend..."
WEB_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000)
if [ "$WEB_STATUS" = "200" ]; then
  echo "✅ Web Frontend accessible"
else
  echo "❌ Web Frontend not accessible (HTTP $WEB_STATUS)"
fi

# Test admin portal
echo "Testing Admin Portal..."
ADMIN_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099)
if [ "$ADMIN_STATUS" = "200" ]; then
  echo "✅ Admin Portal accessible"
else
  echo "❌ Admin Portal not accessible (HTTP $ADMIN_STATUS)"
fi
```

### 2. Frontend Integration Test

```bash
#!/bin/bash
# scripts/test-frontend-integration.sh

echo "🔗 Testing frontend-backend integration..."

# Test chatbot UI can reach API
echo "Testing chatbot UI API connectivity..."
RESPONSE=$(curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -H "Origin: http://localhost:3001" \
  -d '{"query": "Test from frontend"}')

if echo "$RESPONSE" | jq -e '.answer' > /dev/null; then
  echo "✅ Frontend-backend integration working"
else
  echo "❌ Frontend-backend integration failed"
fi

# Test CORS headers
echo "Testing CORS headers..."
CORS_RESPONSE=$(curl -s -I -X OPTIONS http://localhost:8000/ask \
  -H "Origin: http://localhost:3001" \
  -H "Access-Control-Request-Method: POST")

if echo "$CORS_RESPONSE" | grep -i "access-control-allow-origin" > /dev/null; then
  echo "✅ CORS headers present"
else
  echo "❌ CORS headers missing"
fi
```

---

## 🔗 Integration Testing

### 1. End-to-End Flow Test

```bash
#!/bin/bash
# scripts/test-e2e.sh

echo "🔗 Testing end-to-end flow..."

# Simulate complete user flow
echo "1. User opens chatbot UI..."
curl -s http://localhost:3001 > /dev/null && echo "✅ Chatbot UI loaded"

echo "2. User asks a question..."
QUESTION="What is machine learning?"
RESPONSE=$(curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$QUESTION\"}")

if echo "$RESPONSE" | jq -e '.answer' > /dev/null; then
  echo "✅ Question answered"
  ANSWER=$(echo "$RESPONSE" | jq -r '.answer')
  echo "Answer preview: ${ANSWER:0:100}..."
else
  echo "❌ Question failed"
fi

echo "3. User asks follow-up question..."
FOLLOWUP="Can you explain more about that?"
FOLLOWUP_RESPONSE=$(curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$FOLLOWUP\"}")

if echo "$FOLLOWUP_RESPONSE" | jq -e '.answer' > /dev/null; then
  echo "✅ Follow-up answered"
else
  echo "❌ Follow-up failed"
fi

echo "✅ End-to-end flow test completed"
```

### 2. Service Communication Test

```bash
#!/bin/bash
# scripts/test-service-communication.sh

echo "🔗 Testing service communication..."

# Test API Gateway -> Model Gateway
echo "Testing API Gateway -> Model Gateway..."
MODEL_RESPONSE=$(curl -s -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello"}],
    "model": "gpt-4o-mini"
  }')

if echo "$MODEL_RESPONSE" | jq -e '.content' > /dev/null; then
  echo "✅ Model Gateway communication working"
else
  echo "❌ Model Gateway communication failed"
fi

# Test API Gateway -> Config Service
echo "Testing API Gateway -> Config Service..."
CONFIG_RESPONSE=$(curl -s http://localhost:8090/healthz)
if [ "$CONFIG_RESPONSE" = '{"status":"healthy","timestamp":*}' ]; then
  echo "✅ Config Service communication working"
else
  echo "❌ Config Service communication failed"
fi
```

---

## ⚡ Load Testing

### 1. Simple Load Test

```bash
#!/bin/bash
# scripts/test-load.sh

echo "⚡ Running load test..."

# Install k6 if not present
if ! command -v k6 &> /dev/null; then
  echo "Installing k6..."
  # macOS
  if [[ "$OSTYPE" == "darwin"* ]]; then
    brew install k6
  # Linux
  else
    sudo gpg -k
    sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
    echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
    sudo apt-get update
    sudo apt-get install k6
  fi
fi

# Create k6 test script
cat > /tmp/load-test.js << 'EOF'
import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '1m', target: 10 },
    { duration: '30s', target: 20 },
    { duration: '1m', target: 20 },
    { duration: '30s', target: 0 },
  ],
};

export default function() {
  let response = http.post('http://localhost:8000/ask',
    JSON.stringify({query: 'Load test question'}),
    { headers: { 'Content-Type': 'application/json' } }
  );

  check(response, {
    'status is 200': (r) => r.status === 200,
    'response time < 5000ms': (r) => r.timings.duration < 5000,
    'response has answer': (r) => JSON.parse(r.body).answer !== undefined,
  });

  sleep(1);
}
EOF

# Run load test
echo "Starting load test..."
k6 run /tmp/load-test.js

# Cleanup
rm /tmp/load-test.js
```

### 2. Memory and CPU Monitoring

```bash
#!/bin/bash
# scripts/test-resources.sh

echo "📊 Monitoring resource usage..."

# Monitor for 60 seconds
echo "Monitoring Docker containers for 60 seconds..."
timeout 60s docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" || true

# Check specific service resources
echo "Checking API Gateway resources..."
docker stats multi-ai-agent-api-gateway-1 --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

echo "Checking Chatbot UI resources..."
docker stats multi-ai-agent-ai-chatbot-1 --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"
```

---

## 🔒 Security Testing

### 1. Vulnerability Scanning

```bash
#!/bin/bash
# scripts/test-security.sh

echo "🔒 Running security tests..."

# Install Trivy if not present
if ! command -v trivy &> /dev/null; then
  echo "Installing Trivy..."
  if [[ "$OSTYPE" == "darwin"* ]]; then
    brew install trivy
  else
    sudo apt-get update
    sudo apt-get install wget apt-transport-https gnupg lsb-release
    wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | sudo apt-key add -
    echo "deb https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" | sudo tee -a /etc/apt/sources.list.d/trivy.list
    sudo apt-get update
    sudo apt-get install trivy
  fi
fi

# Scan images for vulnerabilities
echo "Scanning AI Chatbot image..."
trivy image multi-ai-agent-ai-chatbot:latest

echo "Scanning API Gateway image..."
trivy image multi-ai-agent-api-gateway:latest

# Scan filesystem
echo "Scanning filesystem..."
trivy fs .
```

### 2. API Security Tests

```bash
#!/bin/bash
# scripts/test-api-security.sh

echo "🔒 Testing API security..."

# Test SQL injection
echo "Testing SQL injection..."
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT * FROM users; DROP TABLE users;"}'

# Test XSS
echo "Testing XSS..."
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "<script>alert(\"xss\")</script>"}'

# Test authentication bypass
echo "Testing authentication bypass..."
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer invalid-token" \
  -d '{"query": "Test"}'

# Test rate limiting (if implemented)
echo "Testing rate limiting..."
for i in {1..100}; do
  curl -s -X POST http://localhost:8000/ask \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"Rate limit test $i\"}" > /dev/null &
done
wait
echo "Rate limit test completed"
```

---

## 📊 Performance Testing

### 1. Response Time Testing

```bash
#!/bin/bash
# scripts/test-performance.sh

echo "📊 Testing performance..."

# Test response times
echo "Testing API response times..."

for i in {1..5}; do
  echo "Test $i:"
  time curl -s -X POST http://localhost:8000/ask \
    -H "Content-Type: application/json" \
    -d '{"query": "What is artificial intelligence?"}' > /dev/null
done

# Test concurrent requests
echo "Testing concurrent requests..."
for i in {1..10}; do
  curl -s -X POST http://localhost:8000/ask \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"Concurrent test $i\"}" > /dev/null &
done
wait
echo "Concurrent test completed"
```

### 2. Database Performance Test

```bash
#!/bin/bash
# scripts/test-db-performance.sh

echo "📊 Testing database performance..."

# Test database connection
echo "Testing database connection..."
docker exec multi-ai-agent-postgres-1 psql -U postgres -d ai_agent -c "SELECT 1;" > /dev/null
if [ $? -eq 0 ]; then
  echo "✅ Database connection working"
else
  echo "❌ Database connection failed"
fi

# Test database performance
echo "Testing database performance..."
time docker exec multi-ai-agent-postgres-1 psql -U postgres -d ai_agent -c "SELECT COUNT(*) FROM information_schema.tables;"

# Test Redis performance
echo "Testing Redis performance..."
docker exec multi-ai-agent-redis-1 redis-cli ping
time docker exec multi-ai-agent-redis-1 redis-cli set test_key "test_value"
time docker exec multi-ai-agent-redis-1 redis-cli get test_key
```

---

## 🗄️ Database Testing

### 1. Database Connectivity Test

```bash
#!/bin/bash
# scripts/test-database.sh

echo "🗄️ Testing database connectivity..."

# Test PostgreSQL
echo "Testing PostgreSQL..."
docker exec multi-ai-agent-postgres-1 pg_isready -U postgres
if [ $? -eq 0 ]; then
  echo "✅ PostgreSQL is ready"
else
  echo "❌ PostgreSQL is not ready"
fi

# Test Redis
echo "Testing Redis..."
docker exec multi-ai-agent-redis-1 redis-cli ping
if [ $? -eq 0 ]; then
  echo "✅ Redis is ready"
else
  echo "❌ Redis is not ready"
fi

# Test NATS
echo "Testing NATS..."
docker exec multi-ai-agent-nats-1 nats server check server
if [ $? -eq 0 ]; then
  echo "✅ NATS is ready"
else
  echo "❌ NATS is not ready"
fi
```

### 2. Data Persistence Test

```bash
#!/bin/bash
# scripts/test-data-persistence.sh

echo "🗄️ Testing data persistence..."

# Test database write/read
echo "Testing database write/read..."
docker exec multi-ai-agent-postgres-1 psql -U postgres -d ai_agent -c "
  CREATE TABLE IF NOT EXISTS test_table (
    id SERIAL PRIMARY KEY,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
"

# Insert test data
docker exec multi-ai-agent-postgres-1 psql -U postgres -d ai_agent -c "
  INSERT INTO test_table (message) VALUES ('Test message');
"

# Read test data
RESULT=$(docker exec multi-ai-agent-postgres-1 psql -U postgres -d ai_agent -t -c "
  SELECT message FROM test_table WHERE message = 'Test message';
")

if [[ "$RESULT" == *"Test message"* ]]; then
  echo "✅ Database persistence working"
else
  echo "❌ Database persistence failed"
fi

# Clean up test data
docker exec multi-ai-agent-postgres-1 psql -U postgres -d ai_agent -c "
  DROP TABLE IF EXISTS test_table;
"
```

---

## 🔧 Troubleshooting

### 1. Common Issues and Solutions

```bash
#!/bin/bash
# scripts/troubleshoot.sh

echo "🔧 Troubleshooting common issues..."

# Check if all containers are running
echo "Checking container status..."
docker-compose -f docker-compose.local.yml ps

# Check for failed containers
echo "Checking for failed containers..."
docker-compose -f docker-compose.local.yml ps --filter "status=exited"

# Check logs for errors
echo "Checking logs for errors..."
docker-compose -f docker-compose.local.yml logs --tail=50 | grep -i error

# Check port conflicts
echo "Checking for port conflicts..."
netstat -tulpn | grep -E ":(3000|3001|8000|8099|5433|6379|4222)" || ss -tulpn | grep -E ":(3000|3001|8000|8099|5433|6379|4222)"

# Check disk space
echo "Checking disk space..."
df -h

# Check memory usage
echo "Checking memory usage..."
free -h || vm_stat

# Check Docker resources
echo "Checking Docker resources..."
docker system df
docker system events --since 1h
```

### 2. Service Restart Script

```bash
#!/bin/bash
# scripts/restart-services.sh

echo "🔄 Restarting services..."

# Stop all services
echo "Stopping all services..."
docker-compose -f docker-compose.local.yml down

# Remove unused containers and networks
echo "Cleaning up..."
docker system prune -f

# Start services one by one
echo "Starting infrastructure services..."
docker-compose -f docker-compose.local.yml up -d postgres redis nats

echo "Waiting for infrastructure to be ready..."
sleep 15

echo "Starting backend services..."
docker-compose -f docker-compose.local.yml up -d api-gateway model-gateway

echo "Waiting for backend to be ready..."
sleep 10

echo "Starting frontend services..."
docker-compose -f docker-compose.local.yml up -d ai-chatbot admin-portal web-frontend

echo "✅ All services restarted"
```

---

## 🤖 Test Automation

### 1. Complete Test Suite

```bash
#!/bin/bash
# scripts/run-all-tests.sh

echo "🤖 Running complete test suite..."

# Create test results directory
mkdir -p test-results
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TEST_LOG="test-results/test_$TIMESTAMP.log"

# Function to run test and log results
run_test() {
  local test_name=$1
  local test_script=$2

  echo "Running $test_name..."
  if bash "$test_script" >> "$TEST_LOG" 2>&1; then
    echo "✅ $test_name PASSED"
    echo "PASS: $test_name" >> "test-results/summary_$TIMESTAMP.txt"
  else
    echo "❌ $test_name FAILED"
    echo "FAIL: $test_name" >> "test-results/summary_$TIMESTAMP.txt"
  fi
}

# Run all tests
run_test "Health Checks" "scripts/test-health.sh"
run_test "Service Discovery" "scripts/test-service-discovery.sh"
run_test "API Tests" "scripts/test-api.sh"
run_test "API Errors" "scripts/test-api-errors.sh"
run_test "Frontend Tests" "scripts/test-frontend.sh"
run_test "Frontend Integration" "scripts/test-frontend-integration.sh"
run_test "End-to-End Flow" "scripts/test-e2e.sh"
run_test "Service Communication" "scripts/test-service-communication.sh"
run_test "Performance Tests" "scripts/test-performance.sh"
run_test "Database Tests" "scripts/test-database.sh"
run_test "Security Tests" "scripts/test-security.sh"

# Generate summary
echo ""
echo "📊 Test Summary:"
echo "================"
cat "test-results/summary_$TIMESTAMP.txt"
echo ""
echo "📄 Detailed logs: $TEST_LOG"
```

### 2. Continuous Testing Script

```bash
#!/bin/bash
# scripts/continuous-test.sh

echo "🔄 Starting continuous testing..."

# Watch for file changes and run tests
if command -v fswatch &> /dev/null; then
  echo "Watching for changes..."
  fswatch -o . | while read; do
    echo "Changes detected, running tests..."
    ./scripts/run-all-tests.sh
  done
else
  echo "fswatch not installed. Install with: brew install fswatch"
  echo "Running tests once..."
  ./scripts/run-all-tests.sh
fi
```

---

## 📚 Test Data and Examples

### 1. Sample Test Queries

```bash
#!/bin/bash
# scripts/test-sample-queries.sh

echo "📚 Testing with sample queries..."

QUERIES=(
  "What is artificial intelligence?"
  "How does machine learning work?"
  "Explain neural networks"
  "What are the benefits of AI?"
  "How can I learn programming?"
  "What is Python used for?"
  "Explain quantum computing"
  "What is blockchain technology?"
  "How does cloud computing work?"
  "What is DevOps?"
)

for query in "${QUERIES[@]}"; do
  echo "Testing: $query"
  RESPONSE=$(curl -s -X POST http://localhost:8000/ask \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"$query\"}")

  if echo "$RESPONSE" | jq -e '.answer' > /dev/null; then
    echo "✅ Query successful"
  else
    echo "❌ Query failed"
  fi
  sleep 1
done
```

### 2. Test Configuration

```bash
#!/bin/bash
# scripts/test-config.sh

echo "⚙️ Testing configuration..."

# Test environment variables
echo "Testing environment variables..."
docker exec multi-ai-agent-api-gateway-1 env | grep -E "(DATABASE_URL|REDIS_URL|NATS_URL)"

# Test configuration files
echo "Testing configuration files..."
docker exec multi-ai-agent-ai-chatbot-1 ls -la /app/

# Test API configuration
echo "Testing API configuration..."
curl -s http://localhost:8000/ | jq '.'

# Test frontend configuration
echo "Testing frontend configuration..."
curl -s http://localhost:3001/ | grep -i "react_app_api_url"
```

---

## 📊 Test Reporting

### 1. Generate Test Report

```bash
#!/bin/bash
# scripts/generate-test-report.sh

echo "📊 Generating test report..."

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="test-results/report_$TIMESTAMP.html"

cat > "$REPORT_FILE" << EOF
<!DOCTYPE html>
<html>
<head>
    <title>AI Chatbot Test Report - $TIMESTAMP</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .pass { color: green; }
        .fail { color: red; }
        .summary { background-color: #f5f5f5; padding: 10px; margin: 10px 0; }
        pre { background-color: #f0f0f0; padding: 10px; overflow-x: auto; }
    </style>
</head>
<body>
    <h1>AI Chatbot Test Report</h1>
    <p>Generated: $(date)</p>

    <div class="summary">
        <h2>Test Summary</h2>
        <pre>$(cat test-results/summary_$TIMESTAMP.txt 2>/dev/null || echo "No summary available")</pre>
    </div>

    <h2>Service Status</h2>
    <pre>$(docker-compose -f docker-compose.local.yml ps)</pre>

    <h2>System Resources</h2>
    <pre>$(docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}")</pre>

    <h2>Test Logs</h2>
    <pre>$(tail -100 test-results/test_$TIMESTAMP.log 2>/dev/null || echo "No logs available")</pre>
</body>
</html>
EOF

echo "📄 Test report generated: $REPORT_FILE"
echo "Open in browser: file://$(pwd)/$REPORT_FILE"
```

---

## 🎯 Quick Test Commands

### Essential Tests (Run These First)

```bash
# 1. Start services
./scripts/start-local.sh

# 2. Quick health check
./scripts/test-health.sh

# 3. Basic API test
./scripts/test-api.sh

# 4. Frontend test
./scripts/test-frontend.sh

# 5. End-to-end test
./scripts/test-e2e.sh
```

### Comprehensive Testing

```bash
# Run all tests
./scripts/run-all-tests.sh

# Generate report
./scripts/generate-test-report.sh

# Continuous testing
./scripts/continuous-test.sh
```

### Troubleshooting

```bash
# Check what's wrong
./scripts/troubleshoot.sh

# Restart everything
./scripts/restart-services.sh

# Check logs
docker-compose -f docker-compose.local.yml logs -f
```

---

## 📋 Testing Checklist

### ✅ Pre-Testing Checklist

- [ ] All services are running (`docker-compose ps`)
- [ ] Environment variables are set (`.env` file)
- [ ] API keys are configured
- [ ] Database is accessible
- [ ] Network connectivity is working

### ✅ Basic Tests

- [ ] Health checks pass
- [ ] API endpoints respond
- [ ] Frontend applications load
- [ ] Database connections work
- [ ] Service discovery functions

### ✅ Integration Tests

- [ ] Frontend can reach backend
- [ ] Services communicate properly
- [ ] End-to-end user flow works
- [ ] Error handling is correct
- [ ] CORS is configured properly

### ✅ Performance Tests

- [ ] Response times are acceptable
- [ ] System handles concurrent users
- [ ] Memory usage is reasonable
- [ ] CPU usage is stable
- [ ] Database performance is good

### ✅ Security Tests

- [ ] No critical vulnerabilities
- [ ] Input validation works
- [ ] Authentication is secure
- [ ] CORS is properly configured
- [ ] Rate limiting works (if implemented)

---

## 🎉 Conclusion

This comprehensive testing guide covers all aspects of testing your AI chatbot services locally. Use the scripts provided to ensure your system is working correctly before deploying to production.

**Remember:**

- Always test locally first
- Run tests after any changes
- Monitor system resources during tests
- Keep test logs for debugging
- Update tests as your system evolves

**Happy testing! 🧪✨**
