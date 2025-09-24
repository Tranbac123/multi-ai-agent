#!/usr/bin/env bash
set -euo pipefail

echo "🔍 Testing service health checks..."

SERVICES=(
  "http://localhost:8000/healthz:API Gateway"
  "http://localhost:3001:AI Chatbot"
  "http://localhost:3000:Web Frontend"
  "http://localhost:8099:Admin Portal"
  "http://localhost:8080/healthz:Model Gateway"
  "http://localhost:8090/healthz:Config Service"
  "http://localhost:8091/healthz:Policy Adapter"
)

FAILED_SERVICES=()

for service in "${SERVICES[@]}"; do
  URL="${service%%:*}"
  NAME="${service##*:}"
  
  echo -n "Testing $NAME... "
  if curl -f -s --max-time 10 "$URL" > /dev/null; then
    echo "✅ OK"
  else
    echo "❌ FAILED"
    FAILED_SERVICES+=("$NAME")
  fi
done

if [ ${#FAILED_SERVICES[@]} -eq 0 ]; then
  echo ""
  echo "🎉 All services are healthy!"
  exit 0
else
  echo ""
  echo "❌ Failed services:"
  for service in "${FAILED_SERVICES[@]}"; do
    echo "  - $service"
  done
  echo ""
  echo "💡 Troubleshooting tips:"
  echo "  - Check if services are running: docker-compose ps"
  echo "  - Check service logs: docker-compose logs <service-name>"
  echo "  - Restart services: docker-compose restart"
  exit 1
fi
