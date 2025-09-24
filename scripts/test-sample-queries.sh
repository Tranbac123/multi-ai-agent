#!/usr/bin/env bash
set -euo pipefail

echo "📚 Testing with sample queries..."

QUERIES=(
  "What is artificial intelligence?"
  "How does machine learning work?"
  "Explain neural networks"
  "What are the benefits of AI?"
  "How can I learn programming?"
  "What is Python used for?"
  "Explain quantum computing"
  "What is blockchain technology?"
  "How does cloud computing work?"
  "What is DevOps?"
  "What is Docker?"
  "Explain microservices architecture"
  "What is Kubernetes?"
  "How does CI/CD work?"
  "What is agile development?"
)

PASSED=0
FAILED=0

for query in "${QUERIES[@]}"; do
  echo "Testing: $query"
  
  RESPONSE=$(curl -s -X POST http://localhost:8000/ask \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"$query\"}" \
    --max-time 30)
  
  if echo "$RESPONSE" | jq -e '.answer' > /dev/null 2>&1; then
    echo "✅ Query successful"
    ((PASSED++))
    
    # Show answer preview
    ANSWER=$(echo "$RESPONSE" | jq -r '.answer')
    echo "   Answer preview: ${ANSWER:0:100}..."
    
    # Check for citations
    if echo "$RESPONSE" | jq -e '.citations' > /dev/null 2>&1; then
      CITATIONS=$(echo "$RESPONSE" | jq -r '.citations | length')
      echo "   Citations: $CITATIONS"
    fi
  else
    echo "❌ Query failed"
    echo "   Response: $RESPONSE"
    ((FAILED++))
  fi
  
  echo ""
  sleep 1
done

echo "📊 Sample Query Test Summary:"
echo "============================="
echo "Total queries: ${#QUERIES[@]}"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo "Success rate: $(( (PASSED * 100) / ${#QUERIES[@]} ))%"

if [ $FAILED -eq 0 ]; then
  echo ""
  echo "🎉 All sample queries passed!"
  exit 0
else
  echo ""
  echo "⚠️  Some queries failed. Check the responses above."
  exit 1
fi
