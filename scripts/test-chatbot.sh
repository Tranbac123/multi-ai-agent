#!/usr/bin/env bash
set -euo pipefail

echo "🤖 Testing AI Chatbot Integration..."

# Source environment variables
if [[ -f .env ]]; then
    export $(grep -v '^#' .env | xargs)
else
    echo "❌ .env file not found. Run ./scripts/setup-env.sh first"
    exit 1
fi

# Test API Gateway health
echo "🔍 Testing API Gateway health..."
if curl -s http://localhost:8000/healthz > /dev/null; then
    echo "✅ API Gateway is healthy"
else
    echo "❌ API Gateway is not responding"
    echo "   Make sure to start services: ./scripts/start-local.sh"
    exit 1
fi

# Test chatbot endpoint
echo "🧪 Testing chatbot /ask endpoint..."
RESPONSE=$(curl -s -X POST http://localhost:8000/ask \
    -H "Content-Type: application/json" \
    -d '{"query": "Hello, how are you?"}' || echo "ERROR")

if [[ "$RESPONSE" == "ERROR" ]]; then
    echo "❌ Chatbot endpoint test failed"
    exit 1
else
    echo "✅ Chatbot endpoint is working"
    echo "📝 Sample response:"
    echo "$RESPONSE" | head -c 200
    echo "..."
fi

# Test chatbot frontend
echo "🌐 Testing chatbot frontend..."
if curl -s http://localhost:3001 > /dev/null; then
    echo "✅ Chatbot frontend is accessible at http://localhost:3001"
else
    echo "⚠️  Chatbot frontend is not responding"
    echo "   Check if the service is running: docker-compose -f docker-compose.local.yml ps"
fi

echo ""
echo "🎉 Chatbot integration test completed!"
echo ""
echo "🎯 Access your chatbot:"
echo "   • Chatbot UI:    http://localhost:3001"
echo "   • API Gateway:   http://localhost:8000"
echo "   • Health Check:  http://localhost:8000/healthz"
echo ""
echo "💡 Try asking questions like:"
echo "   • 'What is artificial intelligence?'"
echo "   • 'How does machine learning work?'"
echo "   • 'Explain quantum computing'"
