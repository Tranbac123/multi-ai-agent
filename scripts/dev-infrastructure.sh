#!/usr/bin/env bash
set -euo pipefail

echo "🗄️  Starting local infrastructure services..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Start only infrastructure services
docker-compose -f docker-compose.local.yml up -d postgres redis nats

echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service health
echo "🔍 Checking service health..."

# Check PostgreSQL
if docker-compose -f docker-compose.local.yml exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
    echo "✅ PostgreSQL is ready"
else
    echo "❌ PostgreSQL is not ready"
fi

# Check Redis
if docker-compose -f docker-compose.local.yml exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis is ready"
else
    echo "❌ Redis is not ready"
fi

# Check NATS
if curl -s http://localhost:8222/healthz > /dev/null 2>&1; then
    echo "✅ NATS is ready"
else
    echo "❌ NATS is not ready"
fi

echo ""
echo "🎉 Infrastructure services are running!"
echo ""
echo "📊 Service URLs:"
echo "   • PostgreSQL:      localhost:5432 (user: postgres, password: postgres, db: ai_agent)"
echo "   • Redis:           localhost:6379"
echo "   • NATS:            localhost:4222 (management: http://localhost:8222)"
echo ""
echo "🔍 Monitor logs: docker-compose -f docker-compose.local.yml logs -f"
echo "🛑 Stop services: docker-compose -f docker-compose.local.yml down"
echo ""
echo "💡 Next: Run backend services with ./scripts/dev-backend.sh"
