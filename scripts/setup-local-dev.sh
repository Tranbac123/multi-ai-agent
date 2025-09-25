#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔧 Setting up Local Development Environment${NC}"
echo "=================================================="

# Check prerequisites
echo -e "${YELLOW}📋 Checking prerequisites...${NC}"

# Check Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    echo -e "${GREEN}✅ Python ${PYTHON_VERSION} found${NC}"
else
    echo -e "${RED}❌ Python 3.11+ required${NC}"
    exit 1
fi

# Check Node.js
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
    echo -e "${GREEN}✅ Node.js v${NODE_VERSION} found${NC}"
else
    echo -e "${RED}❌ Node.js 18+ required${NC}"
    exit 1
fi

# Check PostgreSQL
if command -v psql &> /dev/null; then
    echo -e "${GREEN}✅ PostgreSQL found${NC}"
else
    echo -e "${YELLOW}⚠️  PostgreSQL not found. Please install it.${NC}"
fi

# Check Redis
if command -v redis-cli &> /dev/null; then
    echo -e "${GREEN}✅ Redis found${NC}"
else
    echo -e "${YELLOW}⚠️  Redis not found. Please install it.${NC}"
fi

# Check NATS
if command -v nats-server &> /dev/null; then
    echo -e "${GREEN}✅ NATS Server found${NC}"
else
    echo -e "${YELLOW}⚠️  NATS Server not found. Please install it.${NC}"
fi

echo ""
echo -e "${BLUE}📦 Installing Python dependencies...${NC}"

# Install Python dependencies
if [[ -f "requirements-dev.txt" ]]; then
    pip install -r requirements-dev.txt
    echo -e "${GREEN}✅ Python dependencies installed${NC}"
else
    echo -e "${YELLOW}⚠️  requirements-dev.txt not found${NC}"
fi

echo ""
echo -e "${BLUE}📦 Installing frontend dependencies...${NC}"

# Install frontend dependencies
if [[ -d "frontend/chatbot-ui" ]]; then
    echo "Installing chatbot-ui dependencies..."
    cd frontend/chatbot-ui
    if [[ -f "package.json" ]]; then
        npm install
        echo -e "${GREEN}✅ Chatbot UI dependencies installed${NC}"
    fi
    cd ../..
fi

if [[ -d "frontend/web" ]]; then
    echo "Installing web frontend dependencies..."
    cd frontend/web
    if [[ -f "package.json" ]]; then
        npm install
        echo -e "${GREEN}✅ Web frontend dependencies installed${NC}"
    fi
    cd ../..
fi

echo ""
echo -e "${BLUE}🗄️  Setting up database...${NC}"

# Create database if it doesn't exist
if command -v createdb &> /dev/null; then
    if createdb ai_agent 2>/dev/null; then
        echo -e "${GREEN}✅ Database 'ai_agent' created${NC}"
    else
        echo -e "${YELLOW}⚠️  Database 'ai_agent' already exists${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Please create database 'ai_agent' manually${NC}"
fi

echo ""
echo -e "${BLUE}🔧 Setting up environment...${NC}"

# Setup environment if not exists
if [[ ! -f ".env" ]]; then
    if [[ -f "scripts/setup-env.sh" ]]; then
        ./scripts/setup-env.sh
        echo -e "${GREEN}✅ Environment file created${NC}"
    else
        echo -e "${YELLOW}⚠️  Please create .env file manually${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  .env file already exists${NC}"
fi

echo ""
echo -e "${BLUE}📁 Creating logs directory...${NC}"
mkdir -p logs
echo -e "${GREEN}✅ Logs directory created${NC}"

echo ""
echo -e "${GREEN}🎉 Local development environment setup complete!${NC}"
echo ""
echo -e "${BLUE}🚀 Next steps:${NC}"
echo "=================================================="
echo "1. Edit .env file with your API keys:"
echo "   nano .env"
echo ""
echo "2. Start all services:"
echo "   ./scripts/start-local-dev.sh"
echo ""
echo "3. Test the setup:"
echo "   curl http://localhost:8000/healthz"
echo ""
echo "4. View logs:"
echo "   tail -f logs/api-gateway.log"
echo ""
echo "5. Stop services when done:"
echo "   ./scripts/stop-local-dev.sh"
echo ""
echo -e "${BLUE}📚 For more details, see: LOCAL_DEVELOPMENT_GUIDE.md${NC}"
