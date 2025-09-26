# 🚀 Service Management Quick Start

## 📋 Quick Commands

### Start Services by Layer

```bash
# 1. Infrastructure (Database, Cache, Message Queue)
./scripts/start-infrastructure.sh

# 2. Backend (API, Model Gateway)
./scripts/start-backend.sh

# 3. Frontend (UI Applications)
./scripts/start-frontend.sh

# 4. All services at once
./scripts/start-local.sh
```

### Individual Service Control

```bash
# Start specific service
docker-compose -f docker-compose.local.yml up -d <service-name>

# Stop specific service
./scripts/stop-service.sh <service-name>

# Restart specific service
./scripts/restart-service.sh <service-name>

# Check service status
docker-compose -f docker-compose.local.yml ps
```

## 🔧 Available Services

| Service            | Port | Purpose         | Dependencies          |
| ------------------ | ---- | --------------- | --------------------- |
| **postgres**       | 5433 | Database        | None                  |
| **redis**          | 6379 | Cache           | None                  |
| **nats**           | 4222 | Message Queue   | None                  |
| **api-gateway**    | 8000 | Main API        | postgres, redis, nats |
| **model-gateway**  | 8080 | AI Models       | api-gateway           |
| **config-service** | 8090 | Configuration   | None                  |
| **policy-adapter** | 8091 | Authorization   | None                  |
| **ai-chatbot**     | 3001 | Chat Interface  | api-gateway           |
| **web-frontend**   | 3000 | Web App         | api-gateway           |
| **admin-portal**   | 8099 | Admin Dashboard | api-gateway           |

## 🌐 Service URLs

| Service            | URL                   | Health Check                  |
| ------------------ | --------------------- | ----------------------------- |
| **AI Chatbot**     | http://localhost:3001 | -                             |
| **Web Frontend**   | http://localhost:3000 | -                             |
| **Admin Portal**   | http://localhost:8099 | -                             |
| **API Gateway**    | http://localhost:8000 | http://localhost:8000/healthz |
| **Model Gateway**  | http://localhost:8080 | http://localhost:8080/healthz |
| **Config Service** | http://localhost:8090 | http://localhost:8090/healthz |
| **Policy Adapter** | http://localhost:8091 | http://localhost:8091/healthz |

## 🔍 Health Checks

```bash
# Check all services
./scripts/test-health.sh

# Check specific service
curl http://localhost:8000/healthz  # API Gateway
curl http://localhost:8080/healthz  # Model Gateway
curl http://localhost:3001          # AI Chatbot
curl http://localhost:3000          # Web Frontend
curl http://localhost:8099          # Admin Portal
```

## 🛠️ Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose -f docker-compose.local.yml logs <service-name>

# Check status
docker-compose -f docker-compose.local.yml ps

# Restart service
./scripts/restart-service.sh <service-name>
```

### Port Conflicts

```bash
# Check what's using ports
lsof -i :3000  # Web Frontend
lsof -i :3001  # AI Chatbot
lsof -i :8000  # API Gateway
lsof -i :8080  # Model Gateway

# Kill processes
sudo kill -9 $(lsof -t -i:8000)
```

### Dependencies Not Ready

```bash
# Start in correct order
./scripts/start-infrastructure.sh
sleep 10
./scripts/start-backend.sh
sleep 5
./scripts/start-frontend.sh
```

## 📊 Service Status

```bash
# View all services
docker-compose -f docker-compose.local.yml ps

# View specific service
docker-compose -f docker-compose.local.yml ps <service-name>

# View logs
docker-compose -f docker-compose.local.yml logs -f <service-name>

# View resource usage
docker stats
```

## 🔄 Development Workflow

### Minimal Setup (Backend Only)

```bash
# Start infrastructure + backend
./scripts/start-infrastructure.sh
./scripts/start-backend.sh

# Test API
./scripts/test-api.sh
```

### Frontend Development

```bash
# Start infrastructure + backend
./scripts/start-infrastructure.sh
./scripts/start-backend.sh

# Run frontend in development mode (outside Docker)
cd frontend/chatbot-ui
npm run dev
```

### Full Development

```bash
# Start everything
./scripts/start-local.sh

# Run tests
./scripts/run-all-tests.sh
```

## 🎯 Common Scenarios

### Debug API Issues

```bash
# Start only infrastructure + API Gateway
./scripts/start-infrastructure.sh
docker-compose -f docker-compose.local.yml up -d api-gateway

# Test API
./scripts/test-api.sh

# Check logs
docker-compose -f docker-compose.local.yml logs -f api-gateway
```

### Test Frontend Only

```bash
# Start infrastructure + backend
./scripts/start-infrastructure.sh
./scripts/start-backend.sh

# Start frontend
./scripts/start-frontend.sh

# Test frontend
./scripts/test-frontend.sh
```

### Database Issues

```bash
# Stop all services
docker-compose -f docker-compose.local.yml down

# Reset database
docker volume rm multi-ai-agent_postgres_data

# Start infrastructure
./scripts/start-infrastructure.sh
```

## 📚 More Information

For detailed documentation, see:

- [SERVICE_STARTUP_GUIDE.md](SERVICE_STARTUP_GUIDE.md) - Complete startup guide
- [LOCAL_TESTING_GUIDE.md](LOCAL_TESTING_GUIDE.md) - Testing documentation
- [TESTING_QUICK_START.md](TESTING_QUICK_START.md) - Quick testing guide
