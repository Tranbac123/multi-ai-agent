# 🚀 Service Quick Reference Card

## 🌐 **Frontend URLs (Open in Browser)**

| Service             | URL                   | Purpose                |
| ------------------- | --------------------- | ---------------------- |
| 🤖 **AI Chatbot**   | http://localhost:3001 | Main chatbot interface |
| 🌍 **Web Frontend** | http://localhost:3000 | Main web application   |
| 👨‍💼 **Admin Portal** | http://localhost:8099 | System administration  |

---

## 🔧 **Backend API Endpoints**

### **Main Entry Point: API Gateway**

```
http://localhost:8000
```

**Key Endpoints:**

- `GET /healthz` - Health check
- `GET /` - Service info
- `POST /ask` - Main chat interface
- `POST /v1/chat` - OpenAI chat integration

### **All Service Health Checks**

```bash
curl http://localhost:8000/healthz   # API Gateway
curl http://localhost:8080/healthz   # Model Gateway
curl http://localhost:8081/healthz   # Retrieval Service
curl http://localhost:8082/healthz   # Tools Service
curl http://localhost:8083/healthz   # Router Service
curl http://localhost:8090/healthz   # Config Service
curl http://localhost:8091/healthz   # Policy Adapter
curl http://localhost:8099/healthz   # Admin Portal
```

---

## 🧪 **Quick Test Commands**

### **1. Test Chat Functionality**

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Hello, how are you?",
    "user_id": "test_user",
    "session_id": "test_session"
  }'
```

### **2. Test Document Search**

```bash
curl -X POST http://localhost:8081/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "artificial intelligence",
    "limit": 5,
    "user_id": "test_user"
  }'
```

### **3. Test Tool Execution**

```bash
curl -X POST http://localhost:8082/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "calculator",
    "parameters": {"operation": "add", "a": 5, "b": 3},
    "user_id": "test_user"
  }'
```

---

## 🗄️ **Infrastructure Access**

### **Database**

```bash
# PostgreSQL
psql -h localhost -p 5433 -U postgres -d ai_agent

# Redis
redis-cli -h localhost -p 6379
```

### **Message Broker**

```bash
# NATS Monitoring
open http://localhost:8222
```

---

## 📊 **Service Status Check**

### **Docker Services**

```bash
# Check all services
docker-compose -f docker-compose.local.yml ps

# View logs
docker-compose -f docker-compose.local.yml logs -f [service-name]

# Restart service
docker-compose -f docker-compose.local.yml restart [service-name]
```

### **Service Management**

```bash
# Start all services
docker-compose -f docker-compose.local.yml up -d

# Stop all services
docker-compose -f docker-compose.local.yml down

# Rebuild and start
docker-compose -f docker-compose.local.yml up --build -d
```

---

## 🔑 **Environment Variables**

Your services use these key environment variables from `.env`:

```bash
# API Keys
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
FIRECRAWL_API_KEY=your_firecrawl_api_key_here

# Database URLs (automatically configured)
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/ai_agent
REDIS_URL=redis://redis:6379
NATS_URL=nats://nats:4222
```

---

## 🎯 **Service Ports Summary**

| Port | Service           | Type             |
| ---- | ----------------- | ---------------- |
| 3000 | Web Frontend      | Frontend         |
| 3001 | AI Chatbot        | Frontend         |
| 8000 | API Gateway       | Backend          |
| 8080 | Model Gateway     | Backend          |
| 8081 | Retrieval Service | Backend          |
| 8082 | Tools Service     | Backend          |
| 8083 | Router Service    | Backend          |
| 8090 | Config Service    | Control Plane    |
| 8091 | Policy Adapter    | Control Plane    |
| 8099 | Admin Portal      | Frontend/Backend |
| 5433 | PostgreSQL        | Infrastructure   |
| 6379 | Redis             | Infrastructure   |
| 4222 | NATS              | Infrastructure   |
| 8222 | NATS Monitoring   | Infrastructure   |

---

## 🚀 **Ready to Use!**

1. **Open Frontend:** http://localhost:3001 (AI Chatbot)
2. **Test API:** `curl http://localhost:8000/healthz`
3. **Admin Panel:** http://localhost:8099
4. **Web App:** http://localhost:3000

**All services are running and ready for use!** 🎉
