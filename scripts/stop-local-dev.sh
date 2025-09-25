#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🛑 Stopping Local Development Environment${NC}"
echo "=================================================="

# Function to stop a service
stop_service() {
    local service_name="$1"
    local pid_file="logs/${service_name}.pid"
    
    if [[ -f "${pid_file}" ]]; then
        local pid=$(cat "${pid_file}")
        if kill -0 "${pid}" 2>/dev/null; then
            echo -e "${BLUE}🛑 Stopping ${service_name} (PID: ${pid})...${NC}"
            kill "${pid}"
            sleep 1
            if kill -0 "${pid}" 2>/dev/null; then
                echo -e "${YELLOW}⚠️  Force killing ${service_name}...${NC}"
                kill -9 "${pid}"
            fi
            echo -e "${GREEN}✅ ${service_name} stopped${NC}"
        else
            echo -e "${YELLOW}⚠️  ${service_name} was not running${NC}"
        fi
        rm -f "${pid_file}"
    else
        echo -e "${YELLOW}⚠️  No PID file found for ${service_name}${NC}"
    fi
}

# Stop all services
echo -e "${YELLOW}🛑 Stopping all services...${NC}"

# Stop Frontend Services
stop_service "ai-chatbot"
stop_service "web-frontend"
stop_service "admin-portal"

# Stop Data Plane Services
stop_service "realtime-gateway"
stop_service "router-service"
stop_service "tools-service"
stop_service "retrieval-service"
stop_service "model-gateway"
stop_service "api-gateway"

# Stop Control Plane Services
stop_service "notification-service"
stop_service "audit-log"
stop_service "usage-metering"
stop_service "registry-service"
stop_service "feature-flags-service"
stop_service "policy-adapter"
stop_service "config-service"

# Stop Infrastructure Services
echo -e "${YELLOW}🛑 Stopping Infrastructure Services...${NC}"

# Stop NATS
if [[ -f "logs/nats.pid" ]]; then
    stop_service "nats"
fi

# Stop Redis (optional - you might want to keep it running)
echo -e "${BLUE}🔴 Redis is still running (you may want to keep it)${NC}"
echo -e "   To stop Redis: brew services stop redis"

# Stop PostgreSQL (optional - you might want to keep it running)
echo -e "${BLUE}🐘 PostgreSQL is still running (you may want to keep it)${NC}"
echo -e "   To stop PostgreSQL: brew services stop postgresql@14"

echo ""
echo -e "${GREEN}🎉 All services stopped successfully!${NC}"
echo ""
echo -e "${BLUE}📊 Cleanup:${NC}"
echo "=================================================="

# Clean up log files (optional)
read -p "🗑️  Remove log files? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -f logs/*.log logs/*.pid
    echo -e "${GREEN}✅ Log files cleaned up${NC}"
else
    echo -e "${BLUE}📁 Log files kept in ./logs/${NC}"
fi

echo ""
echo -e "${BLUE}🚀 To start services again: ./scripts/start-local-dev.sh${NC}"
