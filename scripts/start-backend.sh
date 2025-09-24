#!/usr/bin/env bash
set -euo pipefail

echo "🔧 Starting backend services..."

# Check if infrastructure is running
echo "🔍 Checking infrastructure services..."
if ! docker exec multi-ai-agent-postgres-1 pg_isready -U postgres > /dev/null 2>&1; then
  echo "❌ PostgreSQL is not ready. Please start infrastructure first:"
  echo "   ./scripts/start-infrastructure.sh"
  exit 1
fi

if ! docker exec multi-ai-agent-redis-1 redis-cli ping > /dev/null 2>&1; then
  echo "❌ Redis is not ready. Please start infrastructure first:"
  echo "   ./scripts/start-infrastructure.sh"
  exit 1
fi

if ! docker exec multi-ai-agent-nats-1 nats server check server > /dev/null 2>&1; then
  echo "❌ NATS is not ready. Please start infrastructure first:"
  echo "   ./scripts/start-infrastructure.sh"
  exit 1
fi

echo "✅ Infrastructure services are ready"

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

# Start Config Service (Optional)
echo "⚙️ Starting Config Service..."
docker-compose -f docker-compose.local.yml up -d config-service
until curl -f http://localhost:8090/healthz > /dev/null 2>&1; do
  echo "  Waiting for Config Service..."
  sleep 3
done
echo "✅ Config Service is ready"

# Start Policy Adapter (Optional)
echo "🛡️ Starting Policy Adapter..."
docker-compose -f docker-compose.local.yml up -d policy-adapter
until curl -f http://localhost:8091/healthz > /dev/null 2>&1; do
  echo "  Waiting for Policy Adapter..."
  sleep 3
done
echo "✅ Policy Adapter is ready"

echo ""
echo "🎉 Backend services started!"
echo ""
echo "📊 Backend Status:"
echo "=================="
docker-compose -f docker-compose.local.yml ps api-gateway model-gateway config-service policy-adapter

echo ""
echo "🌐 Backend URLs:"
echo "================"
echo "🔌 API Gateway:    http://localhost:8000"
echo "🧠 Model Gateway:  http://localhost:8080"
echo "⚙️ Config Service: http://localhost:8090"
echo "🛡️ Policy Adapter: http://localhost:8091"

echo ""
echo "🔧 Next Steps:"
echo "=============="
echo "Start frontend services: ./scripts/start-frontend.sh"
echo "Start all services:      ./scripts/start-local.sh"
echo "Test API endpoints:      ./scripts/test-api.sh"
echo "Check health:           ./scripts/test-health.sh"
