#!/usr/bin/env bash
set -euo pipefail

echo "🔌 Testing API endpoints..."

# Test chatbot endpoint
echo "Testing /ask endpoint..."
RESPONSE=$(curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "What is artificial intelligence?"}' \
  --max-time 30)

echo "Response received:"
echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"

# Validate response structure
if echo "$RESPONSE" | jq -e '.answer, .citations, .trace' > /dev/null 2>&1; then
  echo "✅ /ask endpoint working correctly"
else
  echo "❌ /ask endpoint response invalid"
  echo "Expected fields: answer, citations, trace"
fi

# Test health endpoint
echo ""
echo "Testing /healthz endpoint..."
HEALTH=$(curl -s http://localhost:8000/healthz --max-time 10)
echo "Health response: $HEALTH"

if echo "$HEALTH" | jq -e '.status' > /dev/null 2>&1; then
  echo "✅ /healthz endpoint working correctly"
else
  echo "❌ /healthz endpoint response invalid"
fi

# Test root endpoint
echo ""
echo "Testing root endpoint..."
ROOT=$(curl -s http://localhost:8000/ --max-time 10)
echo "Root response: $ROOT"

# Test API Gateway endpoints
echo ""
echo "Testing API Gateway endpoints..."

# Test model gateway endpoint
echo "Testing /v1/chat endpoint..."
CHAT_RESPONSE=$(curl -s -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello"}],
    "model": "gpt-4o-mini"
  }' \
  --max-time 30)

if echo "$CHAT_RESPONSE" | jq -e '.content' > /dev/null 2>&1; then
  echo "✅ /v1/chat endpoint working correctly"
else
  echo "❌ /v1/chat endpoint failed or not implemented"
fi

# Test retrieval service endpoint
echo "Testing /v1/query endpoint..."
QUERY_RESPONSE=$(curl -s -X POST http://localhost:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test query"}' \
  --max-time 30)

if echo "$QUERY_RESPONSE" | jq -e '.results' > /dev/null 2>&1; then
  echo "✅ /v1/query endpoint working correctly"
else
  echo "❌ /v1/query endpoint failed or not implemented"
fi

echo ""
echo "🎉 API testing completed!"
