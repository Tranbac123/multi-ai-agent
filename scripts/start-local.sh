#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Starting local development environment..."

# Check if .env exists
if [[ ! -f .env ]]; then
    echo "📝 Running dev setup first..."
    ./scripts/dev-setup.sh
fi

# Start infrastructure services first
echo "🗄️  Starting infrastructure services..."
docker-compose -f docker-compose.local.yml up -d postgres redis nats

# Wait for infrastructure to be ready
echo "⏳ Waiting for infrastructure services to be ready..."
sleep 10

# Start backend services
echo "🔧 Starting backend services..."
docker-compose -f docker-compose.local.yml up -d \
    config-service \
    policy-adapter \
    api-gateway \
    model-gateway \
    retrieval-service \
    tools-service \
    router-service

# Start admin portal
echo "👨‍💼 Starting admin portal..."
docker-compose -f docker-compose.local.yml up -d admin-portal

# Start web frontend
echo "🌐 Starting web frontend..."
docker-compose -f docker-compose.local.yml up -d web-frontend

echo ""
echo "🎉 Local development environment started!"
echo ""
echo "📊 Service Status:"
echo "   • Web Frontend:    http://localhost:3000"
echo "   • Admin Portal:    http://localhost:8099"
echo "   • API Gateway:     http://localhost:8000"
echo "   • Model Gateway:   http://localhost:8080"
echo "   • Retrieval:       http://localhost:8081"
echo "   • Tools:           http://localhost:8082"
echo "   • Router:          http://localhost:8083"
echo "   • Config Service:  http://localhost:8090"
echo "   • Policy Adapter:  http://localhost:8091"
echo ""
echo "🔍 Monitor logs: docker-compose -f docker-compose.local.yml logs -f"
echo "🛑 Stop services: docker-compose -f docker-compose.local.yml down"
