# 🚀 Service Usage Guide

## 📋 **Complete Service URLs and APIs**

Your `docker-compose.local.yml` is running the following services:

---

## 🌐 **Frontend Services (Web Interfaces)**

### 1. **AI Chatbot Frontend**

- **URL:** http://localhost:3001
- **Purpose:** Main chatbot interface for users
- **Environment Variables:**
  - `REACT_APP_API_URL=http://localhost:8000`
  - `REACT_APP_ENVIRONMENT=development`
  - `REACT_APP_NAME=AI Search Agent`
  - `REACT_APP_DEBUG=true`

### 2. **Web Frontend**

- **URL:** http://localhost:3000
- **Purpose:** Main web application interface
- **Environment Variables:**
  - `VITE_API_URL=http://localhost:8000`
  - `VITE_ADMIN_API_URL=http://localhost:8099`
  - `VITE_MODEL_GATEWAY_URL=http://localhost:8080`

### 3. **Admin Portal**

- **URL:** http://localhost:8099
- **Purpose:** Administrative interface for system management
- **Environment Variables:**
  - `DATABASE_URL=postgresql://postgres:postgres@postgres:5432/ai_agent`
  - `REDIS_URL=redis://redis:6379`

---

## 🔧 **Backend Services (APIs)**

### 1. **API Gateway** (Main Entry Point)

- **URL:** http://localhost:8000
- **Purpose:** Central API gateway for all requests
- **Environment Variables:**
  - `DATABASE_URL=postgresql://postgres:postgres@postgres:5432/ai_agent`
  - `REDIS_URL=redis://redis:6379`
  - `NATS_URL=nats://nats:4222`

#### **API Endpoints:**

```bash
# Health Check
GET http://localhost:8000/healthz

# Root Information
GET http://localhost:8000/

# Ask Question (Main Chat Interface)
POST http://localhost:8000/ask
Content-Type: application/json
{
  "query": "Your question here",
  "user_id": "user123",
  "session_id": "session456"
}

# Chat Endpoint (OpenAI Integration)
POST http://localhost:8000/v1/chat
Content-Type: application/json
{
  "messages": [
    {"role": "user", "content": "Hello, how can you help me?"}
  ],
  "model": "gpt-3.5-turbo",
  "temperature": 0.7,
  "max_tokens": 100
}
```

### 2. **Model Gateway**

- **URL:** http://localhost:8080
- **Purpose:** AI model integration and management
- **Environment Variables:**
  - `OPENAI_API_KEY=${OPENAI_API_KEY:-}`
  - `ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}`
  - `FIRECRAWL_API_KEY=${FIRECRAWL_API_KEY:-}`

#### **API Endpoints:**

```bash
# Health Check
GET http://localhost:8080/healthz

# Model Information
GET http://localhost:8080/models

# Model Inference
POST http://localhost:8080/inference
Content-Type: application/json
{
  "model": "gpt-3.5-turbo",
  "prompt": "Your prompt here",
  "user_id": "user123"
}
```

### 3. **Retrieval Service**

- **URL:** http://localhost:8081
- **Purpose:** Document search and retrieval
- **Environment Variables:**
  - `DATABASE_URL=postgresql://postgres:postgres@postgres:5432/ai_agent`

#### **API Endpoints:**

```bash
# Health Check
GET http://localhost:8081/healthz

# Search Documents
POST http://localhost:8081/search
Content-Type: application/json
{
  "query": "search term",
  "limit": 10,
  "user_id": "user123"
}

# Index Documents
POST http://localhost:8081/index
Content-Type: application/json
{
  "documents": [
    {"content": "Document content", "metadata": {"title": "Title"}}
  ],
  "user_id": "user123"
}
```

### 4. **Tools Service**

- **URL:** http://localhost:8082
- **Purpose:** Tool execution and management
- **Environment Variables:** Loaded from .env

#### **API Endpoints:**

```bash
# Health Check
GET http://localhost:8082/healthz

# List Available Tools
GET http://localhost:8082/tools

# Execute Tool
POST http://localhost:8082/execute
Content-Type: application/json
{
  "tool_name": "calculator",
  "parameters": {"operation": "add", "a": 5, "b": 3},
  "user_id": "user123"
}
```

### 5. **Router Service**

- **URL:** http://localhost:8083
- **Purpose:** Request routing and load balancing
- **Environment Variables:** Loaded from .env

#### **API Endpoints:**

```bash
# Health Check
GET http://localhost:8083/healthz

# Route Request
POST http://localhost:8083/route
Content-Type: application/json
{
  "request_type": "chat",
  "user_id": "user123",
  "data": {"message": "Hello"}
}
```

---

## ⚙️ **Control Plane Services**

### 1. **Config Service**

- **URL:** http://localhost:8090
- **Purpose:** Configuration management
- **Environment Variables:** Loaded from .env with `CFG_` prefix

#### **API Endpoints:**

```bash
# Health Check
GET http://localhost:8090/healthz

# Get Configuration
GET http://localhost:8090/config?key=your_key&env=production

# Set Configuration
POST http://localhost:8090/config
Content-Type: application/json
{
  "env": "production",
  "key": "your_key",
  "value": "your_value"
}
```

### 2. **Policy Adapter**

- **URL:** http://localhost:8091
- **Purpose:** Policy evaluation and enforcement
- **Environment Variables:** Loaded from .env

#### **API Endpoints:**

```bash
# Health Check
GET http://localhost:8091/healthz

# Evaluate Policy
POST http://localhost:8091/evaluate
Content-Type: application/json
{
  "user_id": "user123",
  "action": "read",
  "resource": "document123"
}
```

---

## 🗄️ **Infrastructure Services**

### 1. **PostgreSQL Database**

- **URL:** localhost:5433 (external), postgres:5432 (internal)
- **Database:** ai_agent
- **User:** postgres
- **Password:** postgres

### 2. **Redis Cache**

- **URL:** localhost:6379 (external), redis:6379 (internal)
- **Purpose:** Caching and session storage

### 3. **NATS Message Broker**

- **URL:** localhost:4222 (external), nats:4222 (internal)
- **Monitoring:** http://localhost:8222
- **Purpose:** Message queuing and event streaming

---

## 🧪 **Testing Your Services**

### **Health Checks**

```bash
# Test all services
curl http://localhost:8000/healthz  # API Gateway
curl http://localhost:8080/healthz  # Model Gateway
curl http://localhost:8081/healthz  # Retrieval Service
curl http://localhost:8082/healthz  # Tools Service
curl http://localhost:8083/healthz  # Router Service
curl http://localhost:8090/healthz  # Config Service
curl http://localhost:8091/healthz  # Policy Adapter
curl http://localhost:8099/healthz  # Admin Portal
```

### **Frontend Access**

```bash
# Open in browser
open http://localhost:3001  # AI Chatbot
open http://localhost:3000  # Web Frontend
open http://localhost:8099  # Admin Portal
```

### **Database Connection**

```bash
# Connect to PostgreSQL
psql -h localhost -p 5433 -U postgres -d ai_agent

# Connect to Redis
redis-cli -h localhost -p 6379
```

---

## 🔑 **Environment Variables**

Your services load environment variables from:

1. **`.env` file** (via `env_file` in docker-compose)
2. **Direct environment variables** in docker-compose
3. **Pydantic Settings** classes in each service

### **Key Environment Variables:**

```bash
# API Keys (from .env file)
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
FIRECRAWL_API_KEY=your_firecrawl_api_key_here

# Database URLs
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/ai_agent
REDIS_URL=redis://redis:6379
NATS_URL=nats://nats:4222

# Service URLs (for inter-service communication)
MODEL_GATEWAY_URL=http://model-gateway:8080
RETRIEVAL_SERVICE_URL=http://retrieval-service:8081
```

---

## 🚀 **Quick Start Commands**

### **Start All Services**

```bash
docker-compose -f docker-compose.local.yml up -d
```

### **Check Service Status**

```bash
docker-compose -f docker-compose.local.yml ps
```

### **View Service Logs**

```bash
docker-compose -f docker-compose.local.yml logs -f [service-name]
```

### **Stop All Services**

```bash
docker-compose -f docker-compose.local.yml down
```

---

## 📱 **Usage Examples**

### **1. Chat with AI**

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is artificial intelligence?",
    "user_id": "user123",
    "session_id": "session456"
  }'
```

### **2. Search Documents**

```bash
curl -X POST http://localhost:8081/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning",
    "limit": 5,
    "user_id": "user123"
  }'
```

### **3. Execute Tool**

```bash
curl -X POST http://localhost:8082/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "calculator",
    "parameters": {"operation": "multiply", "a": 7, "b": 8},
    "user_id": "user123"
  }'
```

### **4. Get Configuration**

```bash
curl "http://localhost:8090/config?key=app_name&env=production"
```

---

## 🎯 **Service Dependencies**

```
Frontend Services
├── AI Chatbot (3001) → API Gateway (8000)
├── Web Frontend (3000) → API Gateway (8000) + Admin Portal (8099)
└── Admin Portal (8099) → Database + Redis

Backend Services
├── API Gateway (8000) → Database + Redis + NATS
├── Model Gateway (8080) → API Gateway (8000)
├── Retrieval Service (8081) → Database
├── Tools Service (8082) → API Gateway (8000)
└── Router Service (8083) → API Gateway (8000)

Control Plane
├── Config Service (8090) → Redis
└── Policy Adapter (8091) → Redis

Infrastructure
├── PostgreSQL (5433) ← All backend services
├── Redis (6379) ← API Gateway, Config, Policy, Admin
└── NATS (4222) ← API Gateway
```

---

**🎉 Your AI chatbot system is ready to use! Start with the frontend interfaces or test the APIs directly.**
