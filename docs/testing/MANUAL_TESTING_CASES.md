# 🧪 Manual Testing Cases for AI Chatbot Services

## 📋 Quick Test Checklist

### ✅ **Infrastructure Tests**

- [ ] PostgreSQL accessible on port 5433
- [ ] Redis accessible on port 6379
- [ ] NATS accessible on ports 4222, 8222

### ✅ **Backend Service Tests**

- [ ] API Gateway health check
- [ ] Model Gateway health check
- [ ] Config Service health check
- [ ] Policy Adapter health check
- [ ] Retrieval Service health check
- [ ] Tools Service health check
- [ ] Router Service health check

### ✅ **Frontend Service Tests**

- [ ] AI Chatbot loads on port 3001
- [ ] Web Frontend loads on port 3000
- [ ] Admin Portal loads on port 8099

---

## 🔧 **Detailed Test Cases**

### 1. **Health Check Tests**

#### Test 1.1: API Gateway Health

```bash
curl http://localhost:8000/healthz
```

**Expected:** `{"status":"healthy","timestamp":...}`

#### Test 1.2: Model Gateway Health

```bash
curl http://localhost:8080/healthz
```

**Expected:** `{"ok":true,"service":"model-gateway"}`

#### Test 1.3: Config Service Health

```bash
curl http://localhost:8090/healthz
```

**Expected:** `{"status":"healthy"}`

#### Test 1.4: Policy Adapter Health

```bash
curl http://localhost:8091/healthz
```

**Expected:** `{"status":"healthy"}`

---

### 2. **Frontend Interface Tests**

#### Test 2.1: AI Chatbot Interface

1. Open browser to `http://localhost:3001`
2. **Expected:** Chat interface loads
3. **Action:** Type "Hello, how are you?"
4. **Expected:** Response from AI (may take a few seconds)

#### Test 2.2: Web Frontend Interface

1. Open browser to `http://localhost:3000`
2. **Expected:** Main web application loads
3. **Action:** Navigate through different pages
4. **Expected:** All pages load without errors

#### Test 2.3: Admin Portal Interface

1. Open browser to `http://localhost:8099`
2. **Expected:** Admin dashboard loads
3. **Action:** Check if dashboard shows system status
4. **Expected:** System information displays

---

### 3. **API Endpoint Tests**

#### Test 3.1: Chat API Test

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What is artificial intelligence?"}
    ]
  }'
```

**Expected:** JSON response with AI-generated content

#### Test 3.2: Ask API Test

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Tell me about machine learning"
  }'
```

**Expected:** JSON response with answer

#### Test 3.3: Model Gateway Direct Test

```bash
curl -X POST http://localhost:8080/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Hello from model gateway"}
    ]
  }'
```

**Expected:** JSON response from model service

---

### 4. **Database Connectivity Tests**

#### Test 4.1: PostgreSQL Connection

```bash
docker exec multi-ai-agent-postgres-1 psql -U postgres -d ai_agent -c "SELECT version();"
```

**Expected:** PostgreSQL version information

#### Test 4.2: Redis Connection

```bash
docker exec multi-ai-agent-redis-1 redis-cli ping
```

**Expected:** `PONG`

#### Test 4.3: Database Operations

```bash
docker exec multi-ai-agent-postgres-1 psql -U postgres -d ai_agent -c "\\dt"
```

**Expected:** List of tables (may be empty if no migrations run)

---

### 5. **Service Integration Tests**

#### Test 5.1: Frontend to Backend Communication

1. Open AI Chatbot at `http://localhost:3001`
2. Send a message
3. **Expected:** Message appears in chat, response received
4. **Check:** Network tab shows API calls to `localhost:8000`

#### Test 5.2: Cross-Service Communication

```bash
# Test if services can communicate internally
docker exec multi-ai-agent-api-gateway-1 curl -s http://model-gateway:8080/healthz
```

**Expected:** Model Gateway health response

---

### 6. **Error Handling Tests**

#### Test 6.1: Invalid API Requests

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"invalid": "data"}'
```

**Expected:** 422 or 400 error with validation message

#### Test 6.2: Non-existent Endpoints

```bash
curl http://localhost:8000/nonexistent
```

**Expected:** 404 Not Found

#### Test 6.3: Service Unavailable

```bash
# Stop a service temporarily
docker-compose -f docker-compose.local.yml stop api-gateway

# Test frontend
curl http://localhost:3001

# Restart service
docker-compose -f docker-compose.local.yml start api-gateway
```

**Expected:** Frontend should handle service unavailability gracefully

---

### 7. **Performance Tests**

#### Test 7.1: Response Time Check

```bash
time curl -s http://localhost:8000/healthz
```

**Expected:** Response within 1 second

#### Test 7.2: Concurrent Requests

```bash
# Run multiple requests simultaneously
for i in {1..5}; do
  curl -s http://localhost:8000/healthz &
done
wait
```

**Expected:** All requests complete successfully

#### Test 7.3: Load Test (Simple)

```bash
# Send 10 requests rapidly
for i in {1..10}; do
  curl -s http://localhost:3001 > /dev/null &
done
wait
```

**Expected:** All requests complete without errors

---

### 8. **Security Tests**

#### Test 8.1: CORS Headers

```bash
curl -I http://localhost:3001
```

**Expected:** Check for CORS headers if needed

#### Test 8.2: Input Sanitization

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "<script>alert('xss')</script>"}
    ]
  }'
```

**Expected:** Response should not contain script tags

---

### 9. **Configuration Tests**

#### Test 9.1: Environment Variables

```bash
docker exec multi-ai-agent-api-gateway-1 env | grep -E "(DATABASE_URL|REDIS_URL|NATS_URL)"
```

**Expected:** Environment variables are properly set

#### Test 9.2: Port Accessibility

```bash
# Test all service ports
for port in 3001 3000 8099 8000 8080 8090 8091 8081 8082 8083 5433 6379 4222; do
  echo "Testing port $port..."
  curl -s --connect-timeout 2 localhost:$port > /dev/null && echo "✅ Port $port accessible" || echo "❌ Port $port not accessible"
done
```

---

### 10. **End-to-End User Journey Tests**

#### Test 10.1: Complete Chat Flow

1. Open `http://localhost:3001`
2. Type: "Hello, I need help with my account"
3. **Expected:** AI responds with helpful message
4. Continue conversation with follow-up questions
5. **Expected:** Context maintained throughout conversation

#### Test 10.2: Web Application Flow

1. Open `http://localhost:3000`
2. Navigate through all available pages
3. Try to interact with any forms or buttons
4. **Expected:** All interactions work smoothly

#### Test 10.3: Admin Portal Flow

1. Open `http://localhost:8099`
2. Check system status and metrics
3. Navigate through admin functions
4. **Expected:** Admin interface shows current system state

---

## 📊 **Test Results Template**

```
Test Date: ___________
Tester: ___________
Environment: Local Development

INFRASTRUCTURE TESTS:
[ ] PostgreSQL (5433) - Status: ✅/❌
[ ] Redis (6379) - Status: ✅/❌
[ ] NATS (4222) - Status: ✅/❌

BACKEND SERVICES:
[ ] API Gateway (8000) - Status: ✅/❌
[ ] Model Gateway (8080) - Status: ✅/❌
[ ] Config Service (8090) - Status: ✅/❌
[ ] Policy Adapter (8091) - Status: ✅/❌
[ ] Retrieval Service (8081) - Status: ✅/❌
[ ] Tools Service (8082) - Status: ✅/❌
[ ] Router Service (8083) - Status: ✅/❌

FRONTEND SERVICES:
[ ] AI Chatbot (3001) - Status: ✅/❌
[ ] Web Frontend (3000) - Status: ✅/❌
[ ] Admin Portal (8099) - Status: ✅/❌

API ENDPOINTS:
[ ] Chat API - Status: ✅/❌
[ ] Ask API - Status: ✅/❌
[ ] Health Checks - Status: ✅/❌

INTEGRATION TESTS:
[ ] Frontend-Backend - Status: ✅/❌
[ ] Service Communication - Status: ✅/❌
[ ] Database Connectivity - Status: ✅/❌

ERROR HANDLING:
[ ] Invalid Requests - Status: ✅/❌
[ ] 404 Handling - Status: ✅/❌
[ ] Service Unavailability - Status: ✅/❌

PERFORMANCE:
[ ] Response Times - Status: ✅/❌
[ ] Concurrent Requests - Status: ✅/❌
[ ] Load Handling - Status: ✅/❌

OVERALL STATUS: ✅ PASS / ❌ FAIL
NOTES: _____________________________
```

---

## 🚀 **Quick Test Commands**

```bash
# Run comprehensive automated tests
./scripts/comprehensive-service-tests.sh

# Quick health check all services
./scripts/test-health.sh

# Test API endpoints
./scripts/test-api.sh

# Test frontend services
./scripts/test-frontend.sh

# Run all tests
./scripts/run-all-tests.sh
```

---

## 💡 **Testing Tips**

1. **Start with health checks** - Ensure all services are running
2. **Test from frontend** - Use the actual UI to verify functionality
3. **Check logs** - Use `docker-compose logs <service>` if tests fail
4. **Test error scenarios** - Don't just test happy paths
5. **Verify data persistence** - Check if data survives service restarts
6. **Monitor resource usage** - Use `docker stats` to check performance

---

**Happy Testing! 🎉**
