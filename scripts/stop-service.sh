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

echo "🛑 Stopping $SERVICE..."

# Stop the service
docker-compose -f docker-compose.local.yml stop "$SERVICE"

# Check if service was stopped
if docker-compose -f docker-compose.local.yml ps "$SERVICE" | grep -q "Exit"; then
  echo "✅ $SERVICE stopped successfully"
else
  echo "⚠️  $SERVICE may still be running"
fi

echo ""
echo "📊 Current service status:"
docker-compose -f docker-compose.local.yml ps "$SERVICE"
