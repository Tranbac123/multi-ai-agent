#!/usr/bin/env bash
set -euo pipefail

echo "🏗️ Starting infrastructure services..."

# Start PostgreSQL
echo "🐘 Starting PostgreSQL..."
docker-compose -f docker-compose.local.yml up -d postgres
until docker exec multi-ai-agent-postgres-1 pg_isready -U postgres > /dev/null 2>&1; do
  echo "  Waiting for PostgreSQL..."
  sleep 2
done
echo "✅ PostgreSQL is ready"

# Start Redis
echo "🔴 Starting Redis..."
docker-compose -f docker-compose.local.yml up -d redis
until docker exec multi-ai-agent-redis-1 redis-cli ping > /dev/null 2>&1; do
  echo "  Waiting for Redis..."
  sleep 2
done
echo "✅ Redis is ready"

# Start NATS
echo "📡 Starting NATS..."
docker-compose -f docker-compose.local.yml up -d nats
until docker exec multi-ai-agent-nats-1 nats server check server > /dev/null 2>&1; do
  echo "  Waiting for NATS..."
  sleep 2
done
echo "✅ NATS is ready"

echo ""
echo "🎉 Infrastructure services started!"
echo ""
echo "📊 Infrastructure Status:"
echo "=========================="
docker-compose -f docker-compose.local.yml ps postgres redis nats

echo ""
echo "🌐 Infrastructure URLs:"
echo "======================="
echo "🐘 PostgreSQL: localhost:5433"
echo "🔴 Redis:      localhost:6379"
echo "📡 NATS:       localhost:4222"

echo ""
echo "🔧 Next Steps:"
echo "=============="
echo "Start backend services: ./scripts/start-backend.sh"
echo "Start all services:     ./scripts/start-local.sh"
echo "Check health:          ./scripts/test-health.sh"
