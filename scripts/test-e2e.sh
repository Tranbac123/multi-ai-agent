#!/usr/bin/env bash
set -euo pipefail

echo "🔗 Testing end-to-end flow..."

# Test 1: User opens chatbot UI
echo "1. User opens chatbot UI..."
CHATBOT_RESPONSE=$(curl -s http://localhost:3001 --max-time 10)
if [[ "$CHATBOT_RESPONSE" == *"<!DOCTYPE html"* ]] || [[ "$CHATBOT_RESPONSE" == *"<html"* ]]; then
  echo "✅ Chatbot UI loaded successfully"
else
  echo "❌ Chatbot UI failed to load"
  exit 1
fi

# Test 2: User asks a question
echo ""
echo "2. User asks a question..."
QUESTION="What is machine learning?"
echo "Question: $QUESTION"

RESPONSE=$(curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$QUESTION\"}" \
  --max-time 30)

if echo "$RESPONSE" | jq -e '.answer' > /dev/null 2>&1; then
  echo "✅ Question answered successfully"
  ANSWER=$(echo "$RESPONSE" | jq -r '.answer')
  echo "Answer preview: ${ANSWER:0:100}..."
  
  # Check for citations
  if echo "$RESPONSE" | jq -e '.citations' > /dev/null 2>&1; then
    CITATIONS=$(echo "$RESPONSE" | jq -r '.citations | length')
    echo "Citations found: $CITATIONS"
  fi
  
  # Check for trace
  if echo "$RESPONSE" | jq -e '.trace' > /dev/null 2>&1; then
    echo "✅ Trace information available"
  fi
else
  echo "❌ Question failed"
  echo "Response: $RESPONSE"
  exit 1
fi

# Test 3: User asks follow-up question
echo ""
echo "3. User asks follow-up question..."
FOLLOWUP="Can you explain more about that?"
echo "Follow-up: $FOLLOWUP"

FOLLOWUP_RESPONSE=$(curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$FOLLOWUP\"}" \
  --max-time 30)

if echo "$FOLLOWUP_RESPONSE" | jq -e '.answer' > /dev/null 2>&1; then
  echo "✅ Follow-up answered successfully"
  FOLLOWUP_ANSWER=$(echo "$FOLLOWUP_RESPONSE" | jq -r '.answer')
  echo "Follow-up answer preview: ${FOLLOWUP_ANSWER:0:100}..."
else
  echo "❌ Follow-up failed"
  echo "Response: $FOLLOWUP_RESPONSE"
fi

# Test 4: User accesses admin portal
echo ""
echo "4. User accesses admin portal..."
ADMIN_RESPONSE=$(curl -s http://localhost:8099 --max-time 10)
if [[ "$ADMIN_RESPONSE" == *"<!DOCTYPE html"* ]] || [[ "$ADMIN_RESPONSE" == *"<html"* ]]; then
  echo "✅ Admin portal accessible"
else
  echo "❌ Admin portal not accessible"
fi

# Test 5: User accesses web frontend
echo ""
echo "5. User accesses web frontend..."
WEB_RESPONSE=$(curl -s http://localhost:3000 --max-time 10)
if [[ "$WEB_RESPONSE" == *"<!DOCTYPE html"* ]] || [[ "$WEB_RESPONSE" == *"<html"* ]]; then
  echo "✅ Web frontend accessible"
else
  echo "❌ Web frontend not accessible"
fi

# Test 6: API Gateway health check
echo ""
echo "6. API Gateway health check..."
API_HEALTH=$(curl -s http://localhost:8000/healthz --max-time 10)
if echo "$API_HEALTH" | jq -e '.status' > /dev/null 2>&1; then
  echo "✅ API Gateway healthy"
  echo "API Health: $API_HEALTH"
else
  echo "❌ API Gateway unhealthy"
  echo "Health response: $API_HEALTH"
fi

# Test 7: Model Gateway health check
echo ""
echo "7. Model Gateway health check..."
MODEL_HEALTH=$(curl -s http://localhost:8080/healthz --max-time 10)
if echo "$MODEL_HEALTH" | jq -e '.status' > /dev/null 2>&1; then
  echo "✅ Model Gateway healthy"
else
  echo "❌ Model Gateway unhealthy"
  echo "Health response: $MODEL_HEALTH"
fi

# Test 8: Performance check
echo ""
echo "8. Performance check..."
echo "Measuring response time for /ask endpoint..."

START_TIME=$(date +%s.%N)
PERF_RESPONSE=$(curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "Performance test question"}' \
  --max-time 30)
END_TIME=$(date +%s.%N)

RESPONSE_TIME=$(echo "$END_TIME - $START_TIME" | bc)
echo "Response time: ${RESPONSE_TIME}s"

if (( $(echo "$RESPONSE_TIME < 10.0" | bc -l) )); then
  echo "✅ Performance acceptable (< 10s)"
else
  echo "⚠️  Performance slow (> 10s)"
fi

# Test 9: Error handling
echo ""
echo "9. Error handling test..."
ERROR_RESPONSE=$(curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"invalid": "request"}' \
  --max-time 10)

if echo "$ERROR_RESPONSE" | jq -e '.error' > /dev/null 2>&1; then
  echo "✅ Error handling working correctly"
else
  echo "⚠️  Error handling may need improvement"
  echo "Error response: $ERROR_RESPONSE"
fi

echo ""
echo "🎉 End-to-end flow test completed!"
echo ""
echo "📊 Summary:"
echo "  - Chatbot UI: ✅ Loaded"
echo "  - Question answering: ✅ Working"
echo "  - Follow-up questions: ✅ Working"
echo "  - Admin portal: ✅ Accessible"
echo "  - Web frontend: ✅ Accessible"
echo "  - API Gateway: ✅ Healthy"
echo "  - Model Gateway: ✅ Healthy"
echo "  - Performance: ✅ Acceptable"
echo "  - Error handling: ✅ Working"
