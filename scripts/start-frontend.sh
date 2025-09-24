#!/usr/bin/env bash
set -euo pipefail

echo "🌐 Starting frontend services..."

# Check if backend is running
echo "🔍 Checking backend services..."
if ! curl -f http://localhost:8000/healthz > /dev/null 2>&1; then
  echo "❌ API Gateway is not ready. Please start backend first:"
  echo "   ./scripts/start-backend.sh"
  exit 1
fi

echo "✅ Backend services are ready"

# Start AI Chatbot
echo "🤖 Starting AI Chatbot..."
docker-compose -f docker-compose.local.yml up -d ai-chatbot
until curl -f http://localhost:3001 > /dev/null 2>&1; do
  echo "  Waiting for AI Chatbot..."
  sleep 3
done
echo "✅ AI Chatbot is ready"

# Start Web Frontend
echo "🌍 Starting Web Frontend..."
docker-compose -f docker-compose.local.yml up -d web-frontend
until curl -f http://localhost:3000 > /dev/null 2>&1; do
  echo "  Waiting for Web Frontend..."
  sleep 3
done
echo "✅ Web Frontend is ready"

# Start Admin Portal
echo "👨‍💼 Starting Admin Portal..."
docker-compose -f docker-compose.local.yml up -d admin-portal
until curl -f http://localhost:8099 > /dev/null 2>&1; do
  echo "  Waiting for Admin Portal..."
  sleep 3
done
echo "✅ Admin Portal is ready"

echo ""
echo "🎉 Frontend services started!"
echo ""
echo "📊 Frontend Status:"
echo "==================="
docker-compose -f docker-compose.local.yml ps ai-chatbot web-frontend admin-portal

echo ""
echo "🌐 Frontend URLs:"
echo "================="
echo "🤖 AI Chatbot:    http://localhost:3001"
echo "🌍 Web Frontend:  http://localhost:3000"
echo "👨‍💼 Admin Portal:  http://localhost:8099"

echo ""
echo "🔧 Next Steps:"
echo "=============="
echo "Test frontend:    ./scripts/test-frontend.sh"
echo "Run E2E tests:    ./scripts/test-e2e.sh"
echo "Check health:     ./scripts/test-health.sh"
echo "Run all tests:    ./scripts/run-all-tests.sh"

echo ""
echo "🚀 Your AI Chatbot is ready to use!"
echo "   Open http://localhost:3001 in your browser"
