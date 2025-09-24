# 🚀 Quick Start Guide

Get your AI Agent platform running locally in minutes!

## 🎯 One-Command Setup

```bash
./scripts/quick-start.sh
```

This interactive script will guide you through the setup process.

## 🏃‍♂️ Manual Setup

### Option 1: Full Docker (Easiest)

```bash
# 1. Set up environment with API keys
./scripts/setup-env.sh

# 2. Start everything
./scripts/start-local.sh
```

### Option 2: Manual Environment Setup

```bash
# 1. Set up environment
./scripts/dev-setup.sh

# 2. Set API keys (optional)
export OPENAI_API_KEY=your_key_here
export ANTHROPIC_API_KEY=your_key_here
export FIRECRAWL_API_KEY=your_key_here

# 3. Start everything
./scripts/start-local.sh
```

### Option 2: Development Mode

```bash
# 1. Start infrastructure
./scripts/dev-infrastructure.sh

# 2. Set up backend
./scripts/dev-backend.sh

# 3. Set up frontend
./scripts/dev-frontend.sh
```

## 🌐 Access Your Services

| Service             | URL                   | Description            |
| ------------------- | --------------------- | ---------------------- |
| **🌐 Web App**      | http://localhost:3000 | Main user interface    |
| **🤖 AI Chatbot**   | http://localhost:3001 | ChatGPT-like interface |
| **👨‍💼 Admin Portal** | http://localhost:8099 | Admin dashboard        |
| **🔌 API Gateway**  | http://localhost:8000 | Main API               |

## 🛑 Stop Services

```bash
docker-compose -f docker-compose.local.yml down
```

## 🔍 Check Status

```bash
# Check environment and service status
./scripts/env-status.sh

# Test API keys
./scripts/test-api-keys.sh
```

## 🔧 Troubleshooting

- **Port conflicts**: Make sure ports 3000, 8000, 8080-8099 are free
- **Docker issues**: Ensure Docker Desktop is running
- **API errors**: Check that API keys are set correctly
- **Environment issues**: Run `./scripts/setup-env.sh` to reconfigure

## 📚 More Info

- [Full Development Guide](LOCAL_DEVELOPMENT.md)
- [API Documentation](docs/API.md)
- [Architecture Overview](docs/MICROSERVICES_ARCHITECTURE.md)

---

**That's it! Your AI Agent platform is ready to go! 🎉**
