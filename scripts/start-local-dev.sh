#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Local Development Environment (No Docker)${NC}"
echo "=================================================="

# Check if .env exists
if [[ ! -f .env ]]; then
    echo -e "${RED}❌ .env file not found!${NC}"
    echo "Please run: ./scripts/setup-env.sh"
    exit 1
fi

# Load environment variables
source .env

# Create logs directory
mkdir -p logs

# Function to start a service
start_service() {
    local service_name="$1"
    local service_path="$2"
    local port="$3"
    local log_file="logs/${service_name}.log"
    
    echo -e "${BLUE}📦 Starting ${service_name} on port ${port}...${NC}"
    
    # Check if service is already running
    if lsof -Pi :${port} -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Port ${port} is already in use. Skipping ${service_name}.${NC}"
        return
    fi
    
    # Start the service in background
    cd "${service_path}"
    if [[ -f "requirements.txt" ]]; then
        # Install dependencies if needed
        python -m pip install -r requirements.txt >/dev/null 2>&1 || true
    fi
    
    # Start the service
    nohup python src/main.py > "../../${log_file}" 2>&1 &
    local pid=$!
    echo $pid > "../../logs/${service_name}.pid"
    
    cd - >/dev/null
    echo -e "${GREEN}✅ ${service_name} started (PID: ${pid})${NC}"
    sleep 2
}

# Function to start frontend service
start_frontend() {
    local service_name="$1"
    local service_path="$2"
    local port="$3"
    local log_file="logs/${service_name}.log"
    
    echo -e "${BLUE}🌐 Starting ${service_name} on port ${port}...${NC}"
    
    # Check if service is already running
    if lsof -Pi :${port} -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Port ${port} is already in use. Skipping ${service_name}.${NC}"
        return
    fi
    
    cd "${service_path}"
    
    # Install dependencies if needed
    if [[ -f "package.json" ]]; then
        if [[ ! -d "node_modules" ]]; then
            echo "Installing dependencies..."
            npm install >/dev/null 2>&1 || true
        fi
    fi
    
    # Start the frontend service
    if [[ -f "package.json" ]]; then
        # React/Vite frontend
        nohup npm run dev -- --port ${port} --host 0.0.0.0 > "../../${log_file}" 2>&1 &
    elif [[ -f "src/main.py" ]]; then
        # Python frontend
        nohup python src/main.py > "../../${log_file}" 2>&1 &
    fi
    
    local pid=$!
    echo $pid > "../../logs/${service_name}.pid"
    
    cd - >/dev/null
    echo -e "${GREEN}✅ ${service_name} started (PID: ${pid})${NC}"
    sleep 2
}

# Start Infrastructure Services First
echo -e "${YELLOW}🏗️  Starting Infrastructure Services...${NC}"

# Start PostgreSQL (if not running)
if ! pg_isready -h localhost -p 5432 >/dev/null 2>&1; then
    echo -e "${BLUE}🐘 Starting PostgreSQL...${NC}"
    # Try to start PostgreSQL (adjust command based on your setup)
    brew services start postgresql@14 2>/dev/null || \
    sudo service postgresql start 2>/dev/null || \
    echo -e "${YELLOW}⚠️  Please start PostgreSQL manually${NC}"
fi

# Start Redis (if not running)
if ! redis-cli ping >/dev/null 2>&1; then
    echo -e "${BLUE}🔴 Starting Redis...${NC}"
    brew services start redis 2>/dev/null || \
    sudo service redis-server start 2>/dev/null || \
    echo -e "${YELLOW}⚠️  Please start Redis manually${NC}"
fi

# Start NATS (if not running)
if ! nc -z localhost 4222 2>/dev/null; then
    echo -e "${BLUE}📡 Starting NATS...${NC}"
    nohup nats-server --port 4222 --jetstream > logs/nats.log 2>&1 &
    echo $! > logs/nats.pid
    echo -e "${GREEN}✅ NATS started${NC}"
fi

sleep 3

# Start Control Plane Services
echo -e "${YELLOW}🎛️  Starting Control Plane Services...${NC}"

start_service "config-service" "apps/control-plane/config-service" "8090"
start_service "policy-adapter" "apps/control-plane/policy-adapter" "8091"
start_service "feature-flags-service" "apps/control-plane/feature-flags-service" "8092"
start_service "registry-service" "apps/control-plane/registry-service" "8094"
start_service "usage-metering" "apps/control-plane/usage-metering" "8095"
start_service "audit-log" "apps/control-plane/audit-log" "8096"
start_service "notification-service" "apps/control-plane/notification-service" "8097"

# Start Data Plane Services
echo -e "${YELLOW}⚡ Starting Data Plane Services...${NC}"

start_service "api-gateway" "apps/data-plane/api-gateway" "8000"
start_service "model-gateway" "apps/data-plane/model-gateway" "8080"
start_service "retrieval-service" "apps/data-plane/retrieval-service" "8081"
start_service "tools-service" "apps/data-plane/tools-service" "8082"
start_service "router-service" "apps/data-plane/router-service" "8083"
start_service "realtime-gateway" "apps/data-plane/realtime-gateway" "8084"

# Start Frontend Services
echo -e "${YELLOW}🌐 Starting Frontend Services...${NC}"

start_frontend "ai-chatbot" "frontend/chatbot-ui" "3001"
start_frontend "web-frontend" "frontend/web" "3000"
start_frontend "admin-portal" "frontend/admin-portal" "8099"

echo ""
echo -e "${GREEN}🎉 All services started successfully!${NC}"
echo ""
echo -e "${BLUE}📊 Service Status:${NC}"
echo "=================================================="

# Check service status
check_service() {
    local service_name="$1"
    local port="$2"
    local pid_file="logs/${service_name}.pid"
    
    if [[ -f "${pid_file}" ]]; then
        local pid=$(cat "${pid_file}")
        if kill -0 "${pid}" 2>/dev/null; then
            if nc -z localhost ${port} 2>/dev/null; then
                echo -e "${GREEN}✅ ${service_name} (Port ${port}) - Running${NC}"
            else
                echo -e "${YELLOW}⚠️  ${service_name} (Port ${port}) - Starting...${NC}"
            fi
        else
            echo -e "${RED}❌ ${service_name} (Port ${port}) - Stopped${NC}"
        fi
    else
        echo -e "${RED}❌ ${service_name} (Port ${port}) - Not started${NC}"
    fi
}

check_service "config-service" "8090"
check_service "policy-adapter" "8091"
check_service "feature-flags-service" "8092"
check_service "registry-service" "8094"
check_service "usage-metering" "8095"
check_service "audit-log" "8096"
check_service "notification-service" "8097"
check_service "api-gateway" "8000"
check_service "model-gateway" "8080"
check_service "retrieval-service" "8081"
check_service "tools-service" "8082"
check_service "router-service" "8083"
check_service "realtime-gateway" "8084"
check_service "ai-chatbot" "3001"
check_service "web-frontend" "3000"
check_service "admin-portal" "8099"

echo ""
echo -e "${BLUE}🔗 Service URLs:${NC}"
echo "=================================================="
echo -e "🌐 AI Chatbot:     http://localhost:3001"
echo -e "🌐 Web Frontend:   http://localhost:3000"
echo -e "🌐 Admin Portal:   http://localhost:8099"
echo -e "🔌 API Gateway:    http://localhost:8000"
echo -e "🤖 Model Gateway:  http://localhost:8080"
echo -e "🔍 Retrieval:      http://localhost:8081"
echo -e "🛠️  Tools Service:  http://localhost:8082"
echo -e "🚦 Router:         http://localhost:8083"
echo -e "⚡ Realtime:       http://localhost:8084"
echo ""
echo -e "${BLUE}📝 Logs:${NC}"
echo "=================================================="
echo -e "📁 Log files: ./logs/"
echo -e "📊 View logs: tail -f logs/<service-name>.log"
echo ""
echo -e "${YELLOW}🛑 To stop all services: ./scripts/stop-local-dev.sh${NC}"
echo -e "${YELLOW}🔄 To restart a service: kill \$(cat logs/<service>.pid) && ./scripts/start-local-dev.sh${NC}"
