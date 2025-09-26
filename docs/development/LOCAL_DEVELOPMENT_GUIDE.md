# 🚀 Local Development Guide (No Docker)

This guide shows you how to run all services locally without Docker for faster development cycles.

## 📋 Prerequisites

### System Requirements

- **Python 3.11+**
- **Node.js 18+** (for frontend services)
- **PostgreSQL 14+**
- **Redis 6+**
- **NATS Server**

### Install Prerequisites

**macOS (using Homebrew):**

```bash
# Install system dependencies
brew install python@3.11 node postgresql@14 redis nats-server

# Start services
brew services start postgresql@14
brew services start redis
```

**Ubuntu/Debian:**

```bash
# Install system dependencies
sudo apt update
sudo apt install python3.11 python3.11-pip nodejs npm postgresql redis-server

# Start services
sudo systemctl start postgresql
sudo systemctl start redis
```

**Windows:**

```powershell
# Install using Chocolatey
choco install python nodejs postgresql redis nats-server

# Or download from official websites
```

## 🔧 Setup

### 1. Install Python Dependencies

```bash
# Install all development dependencies
pip install -r requirements-dev.txt

# Or install in a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
```

### 2. Setup Environment

```bash
# Create environment file
./scripts/setup-env.sh

# Edit .env file with your API keys
nano .env
```

### 3. Setup Database

```bash
# Create database
createdb ai_agent

# Or using PostgreSQL client
psql -c "CREATE DATABASE ai_agent;"
```

### 4. Install Frontend Dependencies

```bash
# Install chatbot UI dependencies
cd frontend/chatbot-ui
npm install

# Install web frontend dependencies
cd ../web
npm install

# Install admin portal dependencies
cd ../admin-portal
pip install -r requirements.txt
```

## 🚀 Running Services

### Quick Start (All Services)

```bash
# Start all services
./scripts/start-local-dev.sh

# Stop all services
./scripts/stop-local-dev.sh
```

### Individual Services

**Infrastructure Services:**

```bash
# PostgreSQL (if not running)
brew services start postgresql@14

# Redis (if not running)
brew services start redis

# NATS
nats-server --port 4222 --jetstream
```

**Control Plane Services:**

```bash
# Config Service
cd apps/control-plane/config-service
python src/main.py

# Policy Adapter
cd apps/control-plane/policy-adapter
python src/main.py

# Feature Flags Service
cd apps/control-plane/feature-flags-service
python src/main.py

# Registry Service
cd apps/control-plane/registry-service
python src/main.py

# Usage Metering
cd apps/control-plane/usage-metering
python src/main.py

# Audit Log
cd apps/control-plane/audit-log
python src/main.py

# Notification Service
cd apps/control-plane/notification-service
python src/main.py
```

**Data Plane Services:**

```bash
# API Gateway
cd apps/data-plane/api-gateway
python src/main.py

# Model Gateway
cd apps/data-plane/model-gateway
python src/main.py

# Retrieval Service
cd apps/data-plane/retrieval-service
python src/main.py

# Tools Service
cd apps/data-plane/tools-service
python src/main.py

# Router Service
cd apps/data-plane/router-service
python src/main.py

# Realtime Gateway
cd apps/data-plane/realtime-gateway
python src/main.py
```

**Frontend Services:**

```bash
# AI Chatbot
cd frontend/chatbot-ui
npm run dev

# Web Frontend
cd frontend/web
npm run dev

# Admin Portal
cd frontend/admin-portal
python src/main_simple.py
```

## 🌐 Service URLs

| Service               | URL                   | Port | Description              |
| --------------------- | --------------------- | ---- | ------------------------ |
| **AI Chatbot**        | http://localhost:3001 | 3001 | Main chatbot interface   |
| **Web Frontend**      | http://localhost:3000 | 3000 | Web application          |
| **Admin Portal**      | http://localhost:8099 | 8099 | Admin dashboard          |
| **API Gateway**       | http://localhost:8000 | 8000 | Main API endpoint        |
| **Model Gateway**     | http://localhost:8080 | 8080 | AI model routing         |
| **Retrieval Service** | http://localhost:8081 | 8081 | Document retrieval       |
| **Tools Service**     | http://localhost:8082 | 8082 | External tools           |
| **Router Service**    | http://localhost:8083 | 8083 | Request routing          |
| **Realtime Gateway**  | http://localhost:8084 | 8084 | WebSocket connections    |
| **Config Service**    | http://localhost:8090 | 8090 | Configuration management |
| **Policy Adapter**    | http://localhost:8091 | 8091 | Policy enforcement       |
| **Feature Flags**     | http://localhost:8092 | 8092 | Feature toggles          |
| **Registry Service**  | http://localhost:8094 | 8094 | Service registry         |
| **Usage Metering**    | http://localhost:8095 | 8095 | Usage tracking           |
| **Audit Log**         | http://localhost:8096 | 8096 | Audit logging            |
| **Notifications**     | http://localhost:8097 | 8097 | Notification service     |

## 📝 Development Workflow

### 1. Start Development Environment

```bash
# Start all services
./scripts/start-local-dev.sh

# Check service status
curl http://localhost:8000/healthz
```

### 2. Make Changes

```bash
# Edit service code
code apps/data-plane/api-gateway/src/main.py

# Service will auto-reload (if using uvicorn --reload)
```

### 3. Test Changes

```bash
# Run tests
pytest apps/data-plane/api-gateway/tests/

# Test API endpoints
curl http://localhost:8000/
```

### 4. View Logs

```bash
# View all logs
tail -f logs/api-gateway.log

# View specific service logs
tail -f logs/model-gateway.log
```

### 5. Stop Services

```bash
# Stop all services
./scripts/stop-local-dev.sh

# Stop individual service
kill $(cat logs/api-gateway.pid)
```

## 🐛 Troubleshooting

### Common Issues

**Port Already in Use:**

```bash
# Find process using port
lsof -i :8000

# Kill process
kill -9 <PID>
```

**Service Won't Start:**

```bash
# Check logs
tail -f logs/service-name.log

# Check dependencies
pip install -r apps/data-plane/service-name/requirements.txt
```

**Database Connection Issues:**

```bash
# Check PostgreSQL status
pg_isready -h localhost -p 5432

# Check database exists
psql -l | grep ai_agent
```

**Redis Connection Issues:**

```bash
# Check Redis status
redis-cli ping

# Check Redis logs
tail -f /usr/local/var/log/redis.log
```

### Service-Specific Issues

**Frontend Services:**

```bash
# Clear node modules and reinstall
rm -rf node_modules package-lock.json
npm install

# Check Node.js version
node --version  # Should be 18+
```

**Python Services:**

```bash
# Check Python version
python --version  # Should be 3.11+

# Install missing dependencies
pip install -r requirements-dev.txt
```

## 🔧 Configuration

### Environment Variables

Edit `.env` file to configure services:

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_agent

# Redis
REDIS_URL=redis://localhost:6379

# NATS
NATS_URL=nats://localhost:4222

# API Keys
OPENAI_API_KEY=your_openai_api_key_here
FIRECRAWL_API_KEY=your_firecrawl_api_key_here
```

### Service Configuration

Each service can be configured by editing its respective configuration file or environment variables.

## 📊 Monitoring

### Health Checks

```bash
# Check all service health
curl http://localhost:8000/healthz
curl http://localhost:8080/healthz
curl http://localhost:8081/healthz
```

### Logs

```bash
# View all logs
tail -f logs/*.log

# View specific service logs
tail -f logs/api-gateway.log
```

### Performance

```bash
# Monitor system resources
htop

# Monitor specific service
ps aux | grep python
```

## 🚀 Production Considerations

When moving to production:

1. **Use process managers** (PM2, systemd, supervisor)
2. **Set up proper logging** (structured logging, log rotation)
3. **Configure monitoring** (Prometheus, Grafana)
4. **Set up load balancing** (nginx, HAProxy)
5. **Use environment-specific configs**
6. **Set up health checks and auto-restart**

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Uvicorn Documentation](https://www.uvicorn.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/documentation)
- [NATS Documentation](https://docs.nats.io/)
