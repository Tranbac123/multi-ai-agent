#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Starting local AI chatbot services..."

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
  echo "❌ docker-compose not found. Please install Docker Compose."
  exit 1
fi

# Check if .env file exists
if [[ ! -f .env ]]; then
  echo "⚠️  .env file not found. Creating from template..."
  if [[ -f env.example ]]; then
    cp env.example .env
    echo "📝 Created .env file. Please edit it with your API keys."
  else
    echo "❌ env.example not found. Please create .env file manually."
    exit 1
  fi
fi

# Stop any existing containers
echo "🛑 Stopping existing containers..."
docker-compose -f docker-compose.local.yml down || true

# Start infrastructure services first
echo "🏗️  Starting infrastructure services..."
docker-compose -f docker-compose.local.yml up -d postgres redis nats

# Wait for infrastructure to be ready
echo "⏳ Waiting for infrastructure services to be ready..."
sleep 15

# Check if infrastructure services are healthy
echo "🔍 Checking infrastructure services..."

# Check PostgreSQL
echo "Checking PostgreSQL..."
until docker exec multi-ai-agent-postgres-1 pg_isready -U postgres > /dev/null 2>&1; do
  echo "  Waiting for PostgreSQL..."
  sleep 2
done
echo "✅ PostgreSQL is ready"

# Check Redis
echo "Checking Redis..."
until docker exec multi-ai-agent-redis-1 redis-cli ping > /dev/null 2>&1; do
  echo "  Waiting for Redis..."
  sleep 2
done
echo "✅ Redis is ready"

# Check NATS
echo "Checking NATS..."
until docker exec multi-ai-agent-nats-1 nats server check server > /dev/null 2>&1; do
  echo "  Waiting for NATS..."
  sleep 2
done
echo "✅ NATS is ready"

# Start backend services
echo "🔧 Starting backend services..."
docker-compose -f docker-compose.local.yml up -d api-gateway model-gateway

# Wait for backend services
echo "⏳ Waiting for backend services to be ready..."
sleep 10

# Check backend services
echo "🔍 Checking backend services..."

# Check API Gateway
echo "Checking API Gateway..."
until curl -f http://localhost:8000/healthz > /dev/null 2>&1; do
  echo "  Waiting for API Gateway..."
  sleep 3
done
echo "✅ API Gateway is ready"

# Check Model Gateway
echo "Checking Model Gateway..."
until curl -f http://localhost:8080/healthz > /dev/null 2>&1; do
  echo "  Waiting for Model Gateway..."
  sleep 3
done
echo "✅ Model Gateway is ready"

# Start frontend services
echo "🌐 Starting frontend services..."
docker-compose -f docker-compose.local.yml up -d ai-chatbot admin-portal web-frontend

# Wait for frontend services
echo "⏳ Waiting for frontend services to be ready..."
sleep 10

# Check frontend services
echo "🔍 Checking frontend services..."

# Check AI Chatbot
echo "Checking AI Chatbot..."
until curl -f http://localhost:3001 > /dev/null 2>&1; do
  echo "  Waiting for AI Chatbot..."
  sleep 3
done
echo "✅ AI Chatbot is ready"

# Check Web Frontend
echo "Checking Web Frontend..."
until curl -f http://localhost:3000 > /dev/null 2>&1; do
  echo "  Waiting for Web Frontend..."
  sleep 3
done
echo "✅ Web Frontend is ready"

# Check Admin Portal
echo "Checking Admin Portal..."
until curl -f http://localhost:8099 > /dev/null 2>&1; do
  echo "  Waiting for Admin Portal..."
  sleep 3
done
echo "✅ Admin Portal is ready"

# Show service status
echo ""
echo "📊 Service Status:"
echo "=================="
docker-compose -f docker-compose.local.yml ps

echo ""
echo "🌐 Service URLs:"
echo "================"
echo "🤖 AI Chatbot:     http://localhost:3001"
echo "🌍 Web Frontend:   http://localhost:3000"
echo "👨‍💼 Admin Portal:   http://localhost:8099"
echo "🔌 API Gateway:    http://localhost:8000"
echo "🧠 Model Gateway:  http://localhost:8080"

echo ""
echo "🔧 Management Commands:"
echo "======================="
echo "View logs:           docker-compose -f docker-compose.local.yml logs -f"
echo "Stop services:       docker-compose -f docker-compose.local.yml down"
echo "Restart service:     docker-compose -f docker-compose.local.yml restart <service-name>"
echo "Check status:        docker-compose -f docker-compose.local.yml ps"

echo ""
echo "🧪 Testing Commands:"
echo "===================="
echo "Run health checks:   ./scripts/test-health.sh"
echo "Test API:           ./scripts/test-api.sh"
echo "Test frontend:      ./scripts/test-frontend.sh"
echo "Test end-to-end:    ./scripts/test-e2e.sh"
echo "Run all tests:      ./scripts/run-all-tests.sh"

echo ""
echo "✅ All services started successfully!"
echo "🎉 Your AI chatbot is ready for testing!"