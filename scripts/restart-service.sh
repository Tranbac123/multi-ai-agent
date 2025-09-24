#!/usr/bin/env bash
set -euo pipefail

SERVICE=${1:-""}

if [[ -z "$SERVICE" ]]; then
  echo "❌ Usage: $0 <service-name>"
  echo ""
  echo "Available services:"
  echo "==================="
  docker-compose -f docker-compose.local.yml config --services | sed 's/^/  - /'
  echo ""
  echo "Examples:"
  echo "  $0 ai-chatbot"
  echo "  $0 api-gateway"
  echo "  $0 postgres"
  exit 1
fi

# Check if service exists
if ! docker-compose -f docker-compose.local.yml config --services | grep -q "^$SERVICE$"; then
  echo "❌ Service '$SERVICE' not found"
  echo ""
  echo "Available services:"
  docker-compose -f docker-compose.local.yml config --services | sed 's/^/  - /'
  exit 1
fi

echo "🔄 Restarting $SERVICE..."

# Restart the service
docker-compose -f docker-compose.local.yml restart "$SERVICE"

# Wait for service to be ready based on service type
case "$SERVICE" in
  "postgres")
    echo "⏳ Waiting for PostgreSQL to be ready..."
    until docker exec multi-ai-agent-postgres-1 pg_isready -U postgres > /dev/null 2>&1; do
      echo "  Waiting for PostgreSQL..."
      sleep 2
    done
    echo "✅ PostgreSQL is ready"
    ;;
  "redis")
    echo "⏳ Waiting for Redis to be ready..."
    until docker exec multi-ai-agent-redis-1 redis-cli ping > /dev/null 2>&1; do
      echo "  Waiting for Redis..."
      sleep 2
    done
    echo "✅ Redis is ready"
    ;;
  "nats")
    echo "⏳ Waiting for NATS to be ready..."
    until docker exec multi-ai-agent-nats-1 nats server check server > /dev/null 2>&1; do
      echo "  Waiting for NATS..."
      sleep 2
    done
    echo "✅ NATS is ready"
    ;;
  "api-gateway")
    echo "⏳ Waiting for API Gateway to be ready..."
    until curl -f http://localhost:8000/healthz > /dev/null 2>&1; do
      echo "  Waiting for API Gateway..."
      sleep 3
    done
    echo "✅ API Gateway is ready"
    ;;
  "model-gateway")
    echo "⏳ Waiting for Model Gateway to be ready..."
    until curl -f http://localhost:8080/healthz > /dev/null 2>&1; do
      echo "  Waiting for Model Gateway..."
      sleep 3
    done
    echo "✅ Model Gateway is ready"
    ;;
  "config-service")
    echo "⏳ Waiting for Config Service to be ready..."
    until curl -f http://localhost:8090/healthz > /dev/null 2>&1; do
      echo "  Waiting for Config Service..."
      sleep 3
    done
    echo "✅ Config Service is ready"
    ;;
  "policy-adapter")
    echo "⏳ Waiting for Policy Adapter to be ready..."
    until curl -f http://localhost:8091/healthz > /dev/null 2>&1; do
      echo "  Waiting for Policy Adapter..."
      sleep 3
    done
    echo "✅ Policy Adapter is ready"
    ;;
  "ai-chatbot")
    echo "⏳ Waiting for AI Chatbot to be ready..."
    until curl -f http://localhost:3001 > /dev/null 2>&1; do
      echo "  Waiting for AI Chatbot..."
      sleep 3
    done
    echo "✅ AI Chatbot is ready"
    ;;
  "web-frontend")
    echo "⏳ Waiting for Web Frontend to be ready..."
    until curl -f http://localhost:3000 > /dev/null 2>&1; do
      echo "  Waiting for Web Frontend..."
      sleep 3
    done
    echo "✅ Web Frontend is ready"
    ;;
  "admin-portal")
    echo "⏳ Waiting for Admin Portal to be ready..."
    until curl -f http://localhost:8099 > /dev/null 2>&1; do
      echo "  Waiting for Admin Portal..."
      sleep 3
    done
    echo "✅ Admin Portal is ready"
    ;;
  *)
    echo "⚠️  Unknown service type, skipping health check"
    ;;
esac

echo ""
echo "✅ $SERVICE restarted successfully!"
echo ""
echo "📊 Service status:"
docker-compose -f docker-compose.local.yml ps "$SERVICE"
