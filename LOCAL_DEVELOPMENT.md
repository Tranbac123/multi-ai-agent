# 🚀 Local Development Guide

This guide will help you set up and run the full AI Agent platform locally for development.

## 📋 Prerequisites

- **Docker & Docker Compose** - For infrastructure services
- **Node.js 18+** - For frontend development
- **Python 3.11+** - For backend services
- **Git** - For version control

## 🎯 Quick Start

### Option 1: Full Stack with Docker (Recommended)

```bash
# 1. Set up environment
./scripts/dev-setup.sh

# 2. Set your API keys (optional but recommended)
export OPENAI_API_KEY=your_openai_key_here
export ANTHROPIC_API_KEY=your_anthropic_key_here

# 3. Start everything
./scripts/start-local.sh
```

### Option 2: Manual Setup

```bash
# 1. Start infrastructure only
./scripts/dev-infrastructure.sh

# 2. Set up backend development
./scripts/dev-backend.sh

# 3. Set up frontend development
./scripts/dev-frontend.sh
```

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Frontend  │    │  Admin Portal   │    │   API Gateway   │
│   (React+Vite)  │    │   (FastAPI)     │    │   (FastAPI)     │
│   Port: 3000    │    │   Port: 8099    │    │   Port: 8000    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │  Backend Services │
                    └─────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Model Gateway   │    │ Retrieval Svc   │    │  Tools Service  │
│  Port: 8080     │    │  Port: 8081     │    │  Port: 8082     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │ Infrastructure  │
                    └─────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │     Redis       │    │      NATS       │
│   Port: 5432    │    │   Port: 6379    │    │   Port: 4222    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🌐 Service URLs

| Service               | URL                   | Description                 |
| --------------------- | --------------------- | --------------------------- |
| **Web Frontend**      | http://localhost:3000 | Main user interface (React) |
| **Admin Portal**      | http://localhost:8099 | Admin interface (FastAPI)   |
| **API Gateway**       | http://localhost:8000 | Main API gateway            |
| **Model Gateway**     | http://localhost:8080 | LLM model routing           |
| **Retrieval Service** | http://localhost:8081 | Document retrieval          |
| **Tools Service**     | http://localhost:8082 | Tool execution              |
| **Router Service**    | http://localhost:8083 | Request routing             |
| **Config Service**    | http://localhost:8090 | Configuration management    |
| **Policy Adapter**    | http://localhost:8091 | Policy enforcement          |

## 🗄️ Infrastructure Services

| Service             | URL                   | Credentials                                            |
| ------------------- | --------------------- | ------------------------------------------------------ |
| **PostgreSQL**      | localhost:5432        | user: `postgres`, password: `postgres`, db: `ai_agent` |
| **Redis**           | localhost:6379        | No auth required                                       |
| **NATS**            | localhost:4222        | No auth required                                       |
| **NATS Management** | http://localhost:8222 | Web UI for monitoring                                  |

## 🔧 Development Workflow

### Backend Development

```bash
# Start infrastructure
./scripts/dev-infrastructure.sh

# Set up backend environment
./scripts/dev-backend.sh

# Run individual services (in separate terminals)
cd apps/data-plane/api-gateway && python src/main.py
cd apps/data-plane/model-gateway && python src/main.py
cd apps/data-plane/retrieval-service && python src/main.py
```

### Frontend Development

```bash
# Set up frontend environment
./scripts/dev-frontend.sh

# Run frontend services (in separate terminals)
cd frontend/web && npm run dev
cd frontend/admin-portal && source venv/bin/activate && python src/main.py
```

### Running Tests

```bash
# Run all P0 tests
./scripts/run_p0_subset.sh

# Run specific service tests
PYTHONPATH=. pytest apps/data-plane/tools-service/tests/ -v
```

## 🔑 Environment Variables

Create a `.env` file with:

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_agent

# Redis
REDIS_URL=redis://localhost:6379

# NATS
NATS_URL=nats://localhost:4222

# API Keys (get these from respective providers)
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here

# Frontend URLs
VITE_API_URL=http://localhost:8000
VITE_ADMIN_API_URL=http://localhost:8099
```

## 🐛 Troubleshooting

### Common Issues

1. **Port conflicts**: Make sure ports 3000, 8000, 8080-8099, 5432, 6379, 4222 are available
2. **Docker not running**: Start Docker Desktop
3. **Permission denied**: Run `chmod +x scripts/*.sh`
4. **Node.js version**: Ensure Node.js 18+ is installed
5. **Python version**: Ensure Python 3.11+ is installed

### Useful Commands

```bash
# View all running services
docker-compose -f docker-compose.local.yml ps

# View logs
docker-compose -f docker-compose.local.yml logs -f [service_name]

# Stop all services
docker-compose -f docker-compose.local.yml down

# Rebuild services
docker-compose -f docker-compose.local.yml build --no-cache

# Clean up everything
docker-compose -f docker-compose.local.yml down -v
docker system prune -f
```

## 📚 Additional Resources

- [API Documentation](docs/API.md)
- [Frontend Architecture](docs/FRONTEND_ARCHITECTURE.md)
- [Microservices Architecture](docs/MICROSERVICES_ARCHITECTURE.md)
- [Testing Guide](docs/TESTING.md)

## 🤝 Contributing

1. Make your changes
2. Run tests: `./scripts/run_p0_subset.sh`
3. Test locally: `./scripts/start-local.sh`
4. Submit a pull request

---

**Happy coding! 🎉**
