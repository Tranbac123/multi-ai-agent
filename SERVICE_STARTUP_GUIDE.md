# 🚀 Service Startup Guide - One by One

## 📋 Table of Contents

1. [Overview](#overview)
2. [Service Dependencies](#service-dependencies)
3. [Manual Startup Process](#manual-startup-process)
4. [Service-Specific Commands](#service-specific-commands)
5. [Health Check Verification](#health-check-verification)
6. [Troubleshooting](#troubleshooting)
7. [Development Workflow](#development-workflow)
8. [Service Management Scripts](#service-management-scripts)

---

## 🎯 Overview

This guide shows you how to start your AI chatbot services one by one, which is essential for:

- **Debugging**: Isolating issues to specific services
- **Development**: Testing individual components
- **Understanding Dependencies**: Learning service relationships
- **Resource Management**: Starting only what you need
- **Troubleshooting**: Identifying startup problems

---

## 🔗 Service Dependencies

### Dependency Hierarchy

```
┌─────────────────┐
│   Frontend      │
│   Services      │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐
│   Backend       │
│   Services      │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐
│ Infrastructure  │
│   Services      │
└─────────────────┘
```

### Service Dependencies

| Service            | Depends On              | Port | Purpose         |
| ------------------ | ----------------------- | ---- | --------------- |
| **Infrastructure** |                         |      |                 |
| PostgreSQL         | None                    | 5433 | Database        |
| Redis              | None                    | 6379 | Caching         |
| NATS               | None                    | 4222 | Message Queue   |
| **Backend**        |                         |      |                 |
| API Gateway        | PostgreSQL, Redis, NATS | 8000 | Main API        |
| Model Gateway      | API Gateway             | 8080 | AI Models       |
| Config Service     | None                    | 8090 | Configuration   |
| Policy Adapter     | None                    | 8091 | Authorization   |
| **Frontend**       |                         |      |                 |
| AI Chatbot         | API Gateway             | 3001 | Chat Interface  |
| Web Frontend       | API Gateway             | 3000 | Web App         |
| Admin Portal       | API Gateway             | 8099 | Admin Dashboard |

---

## 🔧 Manual Startup Process

### Step 1: Start Infrastructure Services

```bash
# 1. PostgreSQL Database
echo "🐘 Starting PostgreSQL..."
docker-compose -f docker-compose.local.yml up -d postgres

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL..."
until docker exec multi-ai-agent-postgres-1 pg_isready -U postgres > /dev/null 2>&1; do
  echo "  Waiting for PostgreSQL..."
  sleep 2
done
echo "✅ PostgreSQL is ready"

# 2. Redis Cache
echo "🔴 Starting Redis..."
docker-compose -f docker-compose.local.yml up -d redis

# Wait for Redis to be ready
echo "⏳ Waiting for Redis..."
until docker exec multi-ai-agent-redis-1 redis-cli ping > /dev/null 2>&1; do
  echo "  Waiting for Redis..."
  sleep 2
done
echo "✅ Redis is ready"

# 3. NATS Message Queue
echo "📡 Starting NATS..."
docker-compose -f docker-compose.local.yml up -d nats

# Wait for NATS to be ready
echo "⏳ Waiting for NATS..."
until docker exec multi-ai-agent-nats-1 nats server check server > /dev/null 2>&1; do
  echo "  Waiting for NATS..."
  sleep 2
done
echo "✅ NATS is ready"
```

### Step 2: Start Backend Services

```bash
# 1. API Gateway
echo "🔌 Starting API Gateway..."
docker-compose -f docker-compose.local.yml up -d api-gateway

# Wait for API Gateway to be ready
echo "⏳ Waiting for API Gateway..."
until curl -f http://localhost:8000/healthz > /dev/null 2>&1; do
  echo "  Waiting for API Gateway..."
  sleep 3
done
echo "✅ API Gateway is ready"

# 2. Model Gateway
echo "🧠 Starting Model Gateway..."
docker-compose -f docker-compose.local.yml up -d model-gateway

# Wait for Model Gateway to be ready
echo "⏳ Waiting for Model Gateway..."
until curl -f http://localhost:8080/healthz > /dev/null 2>&1; do
  echo "  Waiting for Model Gateway..."
  sleep 3
done
echo "✅ Model Gateway is ready"

# 3. Config Service (Optional)
echo "⚙️ Starting Config Service..."
docker-compose -f docker-compose.local.yml up -d config-service

# Wait for Config Service to be ready
echo "⏳ Waiting for Config Service..."
until curl -f http://localhost:8090/healthz > /dev/null 2>&1; do
  echo "  Waiting for Config Service..."
  sleep 3
done
echo "✅ Config Service is ready"

# 4. Policy Adapter (Optional)
echo "🛡️ Starting Policy Adapter..."
docker-compose -f docker-compose.local.yml up -d policy-adapter

# Wait for Policy Adapter to be ready
echo "⏳ Waiting for Policy Adapter..."
until curl -f http://localhost:8091/healthz > /dev/null 2>&1; do
  echo "  Waiting for Policy Adapter..."
  sleep 3
done
echo "✅ Policy Adapter is ready"
```

### Step 3: Start Frontend Services

```bash
# 1. AI Chatbot
echo "🤖 Starting AI Chatbot..."
docker-compose -f docker-compose.local.yml up -d ai-chatbot

# Wait for AI Chatbot to be ready
echo "⏳ Waiting for AI Chatbot..."
until curl -f http://localhost:3001 > /dev/null 2>&1; do
  echo "  Waiting for AI Chatbot..."
  sleep 3
done
echo "✅ AI Chatbot is ready"

# 2. Web Frontend
echo "🌍 Starting Web Frontend..."
docker-compose -f docker-compose.local.yml up -d web-frontend

# Wait for Web Frontend to be ready
echo "⏳ Waiting for Web Frontend..."
until curl -f http://localhost:3000 > /dev/null 2>&1; do
  echo "  Waiting for Web Frontend..."
  sleep 3
done
echo "✅ Web Frontend is ready"

# 3. Admin Portal
echo "👨‍💼 Starting Admin Portal..."
docker-compose -f docker-compose.local.yml up -d admin-portal

# Wait for Admin Portal to be ready
echo "⏳ Waiting for Admin Portal..."
until curl -f http://localhost:8099 > /dev/null 2>&1; do
  echo "  Waiting for Admin Portal..."
  sleep 3
done
echo "✅ Admin Portal is ready"
```

---

## 🔧 Service-Specific Commands

### Infrastructure Services

#### PostgreSQL

```bash
# Start PostgreSQL
docker-compose -f docker-compose.local.yml up -d postgres

# Check PostgreSQL status
docker-compose -f docker-compose.local.yml ps postgres

# View PostgreSQL logs
docker-compose -f docker-compose.local.yml logs -f postgres

# Connect to PostgreSQL
docker exec -it multi-ai-agent-postgres-1 psql -U postgres -d ai_agent

# Test PostgreSQL connection
docker exec multi-ai-agent-postgres-1 pg_isready -U postgres
```

#### Redis

```bash
# Start Redis
docker-compose -f docker-compose.local.yml up -d redis

# Check Redis status
docker-compose -f docker-compose.local.yml ps redis

# View Redis logs
docker-compose -f docker-compose.local.yml logs -f redis

# Connect to Redis CLI
docker exec -it multi-ai-agent-redis-1 redis-cli

# Test Redis connection
docker exec multi-ai-agent-redis-1 redis-cli ping
```

#### NATS

```bash
# Start NATS
docker-compose -f docker-compose.local.yml up -d nats

# Check NATS status
docker-compose -f docker-compose.local.yml ps nats

# View NATS logs
docker-compose -f docker-compose.local.yml logs -f nats

# Test NATS connection
docker exec multi-ai-agent-nats-1 nats server check server
```

### Backend Services

#### API Gateway

```bash
# Start API Gateway
docker-compose -f docker-compose.local.yml up -d api-gateway

# Check API Gateway status
docker-compose -f docker-compose.local.yml ps api-gateway

# View API Gateway logs
docker-compose -f docker-compose.local.yml logs -f api-gateway

# Test API Gateway health
curl http://localhost:8000/healthz

# Test API Gateway endpoints
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello"}'
```

#### Model Gateway

```bash
# Start Model Gateway
docker-compose -f docker-compose.local.yml up -d model-gateway

# Check Model Gateway status
docker-compose -f docker-compose.local.yml ps model-gateway

# View Model Gateway logs
docker-compose -f docker-compose.local.yml logs -f model-gateway

# Test Model Gateway health
curl http://localhost:8080/healthz

# Test Model Gateway endpoints
curl -X POST http://localhost:8080/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello"}]}'
```

### Frontend Services

#### AI Chatbot

```bash
# Start AI Chatbot
docker-compose -f docker-compose.local.yml up -d ai-chatbot

# Check AI Chatbot status
docker-compose -f docker-compose.local.yml ps ai-chatbot

# View AI Chatbot logs
docker-compose -f docker-compose.local.yml logs -f ai-chatbot

# Test AI Chatbot accessibility
curl -I http://localhost:3001

# Open AI Chatbot in browser
open http://localhost:3001
```

#### Web Frontend

```bash
# Start Web Frontend
docker-compose -f docker-compose.local.yml up -d web-frontend

# Check Web Frontend status
docker-compose -f docker-compose.local.yml ps web-frontend

# View Web Frontend logs
docker-compose -f docker-compose.local.yml logs -f web-frontend

# Test Web Frontend accessibility
curl -I http://localhost:3000

# Open Web Frontend in browser
open http://localhost:3000
```

#### Admin Portal

```bash
# Start Admin Portal
docker-compose -f docker-compose.local.yml up -d admin-portal

# Check Admin Portal status
docker-compose -f docker-compose.local.yml ps admin-portal

# View Admin Portal logs
docker-compose -f docker-compose.local.yml logs -f admin-portal

# Test Admin Portal accessibility
curl -I http://localhost:8099

# Open Admin Portal in browser
open http://localhost:8099
```

---

## 🔍 Health Check Verification

### Automated Health Checks

```bash
# Check all services health
./scripts/test-health.sh

# Check specific service health
curl -f http://localhost:8000/healthz  # API Gateway
curl -f http://localhost:8080/healthz  # Model Gateway
curl -f http://localhost:3001          # AI Chatbot
curl -f http://localhost:3000          # Web Frontend
curl -f http://localhost:8099          # Admin Portal
```

### Manual Health Verification

```bash
# 1. Check container status
docker-compose -f docker-compose.local.yml ps

# 2. Check service logs
docker-compose -f docker-compose.local.yml logs -f

# 3. Check specific service logs
docker-compose -f docker-compose.local.yml logs -f <service-name>

# 4. Check resource usage
docker stats

# 5. Check network connectivity
docker network ls
docker network inspect multi-ai-agent_default
```

---

## 🛠️ Troubleshooting

### Common Startup Issues

#### 1. Port Conflicts

```bash
# Check what's using the ports
lsof -i :3000  # Web Frontend
lsof -i :3001  # AI Chatbot
lsof -i :8000  # API Gateway
lsof -i :8080  # Model Gateway
lsof -i :8099  # Admin Portal
lsof -i :5433  # PostgreSQL
lsof -i :6379  # Redis
lsof -i :4222  # NATS

# Kill processes using ports
sudo kill -9 $(lsof -t -i:8000)
```

#### 2. Container Not Starting

```bash
# Check container logs
docker-compose -f docker-compose.local.yml logs <service-name>

# Check container status
docker-compose -f docker-compose.local.yml ps

# Restart specific service
docker-compose -f docker-compose.local.yml restart <service-name>

# Rebuild and restart
docker-compose -f docker-compose.local.yml up -d --build <service-name>
```

#### 3. Database Connection Issues

```bash
# Check PostgreSQL status
docker exec multi-ai-agent-postgres-1 pg_isready -U postgres

# Check database logs
docker-compose -f docker-compose.local.yml logs postgres

# Reset database
docker-compose -f docker-compose.local.yml down
docker volume rm multi-ai-agent_postgres_data
docker-compose -f docker-compose.local.yml up -d postgres
```

#### 4. Service Dependencies Not Ready

```bash
# Check service dependencies
docker-compose -f docker-compose.local.yml config

# Start services in dependency order
docker-compose -f docker-compose.local.yml up -d postgres redis nats
sleep 10
docker-compose -f docker-compose.local.yml up -d api-gateway
sleep 5
docker-compose -f docker-compose.local.yml up -d ai-chatbot
```

### Debugging Commands

```bash
# Check all container status
docker ps -a

# Check container resource usage
docker stats

# Check container logs
docker logs <container-name>

# Check container environment
docker exec <container-name> env

# Check container network
docker exec <container-name> netstat -tulpn

# Check container processes
docker exec <container-name> ps aux
```

---

## 🔄 Development Workflow

### Minimal Development Setup

```bash
# Start only essential services for development
docker-compose -f docker-compose.local.yml up -d postgres redis nats api-gateway

# Start frontend in development mode (outside Docker)
cd frontend/chatbot-ui
npm start
```

### Testing Individual Services

```bash
# Test only API Gateway
docker-compose -f docker-compose.local.yml up -d postgres redis nats api-gateway
./scripts/test-api.sh

# Test only frontend
docker-compose -f docker-compose.local.yml up -d ai-chatbot
./scripts/test-frontend.sh

# Test specific service
docker-compose -f docker-compose.local.yml up -d <service-name>
curl http://localhost:<port>/healthz
```

### Development with Hot Reload

```bash
# Start infrastructure
docker-compose -f docker-compose.local.yml up -d postgres redis nats

# Start backend services
docker-compose -f docker-compose.local.yml up -d api-gateway

# Run frontend in development mode (with hot reload)
cd frontend/chatbot-ui
npm run dev

# In another terminal, run backend in development mode
cd apps/data-plane/api-gateway
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 📜 Service Management Scripts

### Create Individual Service Scripts

#### `scripts/start-infrastructure.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "🏗️ Starting infrastructure services..."

# Start PostgreSQL
echo "🐘 Starting PostgreSQL..."
docker-compose -f docker-compose.local.yml up -d postgres
until docker exec multi-ai-agent-postgres-1 pg_isready -U postgres > /dev/null 2>&1; do
  echo "  Waiting for PostgreSQL..."
  sleep 2
done
echo "✅ PostgreSQL is ready"

# Start Redis
echo "🔴 Starting Redis..."
docker-compose -f docker-compose.local.yml up -d redis
until docker exec multi-ai-agent-redis-1 redis-cli ping > /dev/null 2>&1; do
  echo "  Waiting for Redis..."
  sleep 2
done
echo "✅ Redis is ready"

# Start NATS
echo "📡 Starting NATS..."
docker-compose -f docker-compose.local.yml up -d nats
until docker exec multi-ai-agent-nats-1 nats server check server > /dev/null 2>&1; do
  echo "  Waiting for NATS..."
  sleep 2
done
echo "✅ NATS is ready"

echo "🎉 Infrastructure services started!"
```

#### `scripts/start-backend.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "🔧 Starting backend services..."

# Start API Gateway
echo "🔌 Starting API Gateway..."
docker-compose -f docker-compose.local.yml up -d api-gateway
until curl -f http://localhost:8000/healthz > /dev/null 2>&1; do
  echo "  Waiting for API Gateway..."
  sleep 3
done
echo "✅ API Gateway is ready"

# Start Model Gateway
echo "🧠 Starting Model Gateway..."
docker-compose -f docker-compose.local.yml up -d model-gateway
until curl -f http://localhost:8080/healthz > /dev/null 2>&1; do
  echo "  Waiting for Model Gateway..."
  sleep 3
done
echo "✅ Model Gateway is ready"

echo "🎉 Backend services started!"
```

#### `scripts/start-frontend.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "🌐 Starting frontend services..."

# Start AI Chatbot
echo "🤖 Starting AI Chatbot..."
docker-compose -f docker-compose.local.yml up -d ai-chatbot
until curl -f http://localhost:3001 > /dev/null 2>&1; do
  echo "  Waiting for AI Chatbot..."
  sleep 3
done
echo "✅ AI Chatbot is ready"

# Start Web Frontend
echo "🌍 Starting Web Frontend..."
docker-compose -f docker-compose.local.yml up -d web-frontend
until curl -f http://localhost:3000 > /dev/null 2>&1; do
  echo "  Waiting for Web Frontend..."
  sleep 3
done
echo "✅ Web Frontend is ready"

# Start Admin Portal
echo "👨‍💼 Starting Admin Portal..."
docker-compose -f docker-compose.local.yml up -d admin-portal
until curl -f http://localhost:8099 > /dev/null 2>&1; do
  echo "  Waiting for Admin Portal..."
  sleep 3
done
echo "✅ Admin Portal is ready"

echo "🎉 Frontend services started!"
```

### Service Control Scripts

#### `scripts/stop-service.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

SERVICE=${1:-""}

if [[ -z "$SERVICE" ]]; then
  echo "Usage: $0 <service-name>"
  echo "Available services:"
  docker-compose -f docker-compose.local.yml config --services
  exit 1
fi

echo "🛑 Stopping $SERVICE..."
docker-compose -f docker-compose.local.yml stop "$SERVICE"
echo "✅ $SERVICE stopped"
```

#### `scripts/restart-service.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

SERVICE=${1:-""}

if [[ -z "$SERVICE" ]]; then
  echo "Usage: $0 <service-name>"
  echo "Available services:"
  docker-compose -f docker-compose.local.yml config --services
  exit 1
fi

echo "🔄 Restarting $SERVICE..."
docker-compose -f docker-compose.local.yml restart "$SERVICE"

# Wait for service to be ready
case "$SERVICE" in
  "postgres")
    until docker exec multi-ai-agent-postgres-1 pg_isready -U postgres > /dev/null 2>&1; do
      echo "  Waiting for PostgreSQL..."
      sleep 2
    done
    ;;
  "redis")
    until docker exec multi-ai-agent-redis-1 redis-cli ping > /dev/null 2>&1; do
      echo "  Waiting for Redis..."
      sleep 2
    done
    ;;
  "nats")
    until docker exec multi-ai-agent-nats-1 nats server check server > /dev/null 2>&1; do
      echo "  Waiting for NATS..."
      sleep 2
    done
    ;;
  "api-gateway")
    until curl -f http://localhost:8000/healthz > /dev/null 2>&1; do
      echo "  Waiting for API Gateway..."
      sleep 3
    done
    ;;
  "model-gateway")
    until curl -f http://localhost:8080/healthz > /dev/null 2>&1; do
      echo "  Waiting for Model Gateway..."
      sleep 3
    done
    ;;
  "ai-chatbot")
    until curl -f http://localhost:3001 > /dev/null 2>&1; do
      echo "  Waiting for AI Chatbot..."
      sleep 3
    done
    ;;
  "web-frontend")
    until curl -f http://localhost:3000 > /dev/null 2>&1; do
      echo "  Waiting for Web Frontend..."
      sleep 3
    done
    ;;
  "admin-portal")
    until curl -f http://localhost:8099 > /dev/null 2>&1; do
      echo "  Waiting for Admin Portal..."
      sleep 3
    done
    ;;
esac

echo "✅ $SERVICE restarted and ready"
```

---

## 📋 Quick Reference

### Service Startup Order

1. **Infrastructure**: PostgreSQL → Redis → NATS
2. **Backend**: API Gateway → Model Gateway
3. **Frontend**: AI Chatbot → Web Frontend → Admin Portal

### Service URLs

- **AI Chatbot**: http://localhost:3001
- **Web Frontend**: http://localhost:3000
- **Admin Portal**: http://localhost:8099
- **API Gateway**: http://localhost:8000
- **Model Gateway**: http://localhost:8080

### Health Check URLs

- **API Gateway**: http://localhost:8000/healthz
- **Model Gateway**: http://localhost:8080/healthz

### Common Commands

```bash
# Start all services
./scripts/start-local.sh

# Start infrastructure only
./scripts/start-infrastructure.sh

# Start backend only
./scripts/start-backend.sh

# Start frontend only
./scripts/start-frontend.sh

# Start specific service
docker-compose -f docker-compose.local.yml up -d <service-name>

# Stop specific service
./scripts/stop-service.sh <service-name>

# Restart specific service
./scripts/restart-service.sh <service-name>

# Check service status
docker-compose -f docker-compose.local.yml ps

# View service logs
docker-compose -f docker-compose.local.yml logs -f <service-name>
```

---

## 🎉 Conclusion

This guide provides comprehensive documentation for starting your AI chatbot services one by one. Use this approach when:

- **Debugging** specific service issues
- **Developing** individual components
- **Testing** service dependencies
- **Optimizing** resource usage
- **Learning** the system architecture

**Remember**: Always start services in dependency order and verify each service is ready before starting the next one!

**Happy developing! 🚀**
