#!/usr/bin/env bash
set -euo pipefail

echo "📊 Testing performance..."

# Test response times
echo "Testing API response times..."

RESPONSE_TIMES=()

for i in {1..5}; do
  echo "Test $i:"
  START_TIME=$(date +%s.%N)
  curl -s -X POST http://localhost:8000/ask \
    -H "Content-Type: application/json" \
    -d '{"query": "What is artificial intelligence?"}' > /dev/null
  END_TIME=$(date +%s.%N)
  
  RESPONSE_TIME=$(echo "$END_TIME - $START_TIME" | bc)
  RESPONSE_TIMES+=($RESPONSE_TIME)
  echo "  Response time: ${RESPONSE_TIME}s"
done

# Calculate average response time
TOTAL=0
for time in "${RESPONSE_TIMES[@]}"; do
  TOTAL=$(echo "$TOTAL + $time" | bc)
done
AVERAGE=$(echo "scale=3; $TOTAL / ${#RESPONSE_TIMES[@]}" | bc)

echo ""
echo "📈 Performance Summary:"
echo "Average response time: ${AVERAGE}s"

# Check if performance is acceptable
if (( $(echo "$AVERAGE < 5.0" | bc -l) )); then
  echo "✅ Performance is excellent (< 5s)"
elif (( $(echo "$AVERAGE < 10.0" | bc -l) )); then
  echo "✅ Performance is good (< 10s)"
elif (( $(echo "$AVERAGE < 20.0" | bc -l) )); then
  echo "⚠️  Performance is acceptable (< 20s)"
else
  echo "❌ Performance is poor (> 20s)"
fi

# Test concurrent requests
echo ""
echo "Testing concurrent requests..."
CONCURRENT_START=$(date +%s.%N)

for i in {1..10}; do
  curl -s -X POST http://localhost:8000/ask \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"Concurrent test $i\"}" > /dev/null &
done

wait

CONCURRENT_END=$(date +%s.%N)
CONCURRENT_TIME=$(echo "$CONCURRENT_END - $CONCURRENT_START" | bc)

echo "10 concurrent requests completed in: ${CONCURRENT_TIME}s"
echo "Average per request: $(echo "scale=3; $CONCURRENT_TIME / 10" | bc)s"

# Test memory usage
echo ""
echo "Testing memory usage..."
echo "Current Docker container memory usage:"
docker stats --no-stream --format "table {{.Container}}\t{{.MemUsage}}\t{{.MemPerc}}" | grep -E "(ai-chatbot|api-gateway|model-gateway)" || echo "Container stats not available"

# Test CPU usage
echo ""
echo "Testing CPU usage..."
echo "Current Docker container CPU usage:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}" | grep -E "(ai-chatbot|api-gateway|model-gateway)" || echo "Container stats not available"

# Test database performance
echo ""
echo "Testing database performance..."
DB_START=$(date +%s.%N)
docker exec multi-ai-agent-postgres-1 psql -U postgres -d ai_agent -c "SELECT COUNT(*) FROM information_schema.tables;" > /dev/null
DB_END=$(date +%s.%N)
DB_TIME=$(echo "$DB_END - $DB_START" | bc)
echo "Database query time: ${DB_TIME}s"

# Test Redis performance
echo ""
echo "Testing Redis performance..."
REDIS_START=$(date +%s.%N)
docker exec multi-ai-agent-redis-1 redis-cli set test_key "test_value" > /dev/null
docker exec multi-ai-agent-redis-1 redis-cli get test_key > /dev/null
docker exec multi-ai-agent-redis-1 redis-cli del test_key > /dev/null
REDIS_END=$(date +%s.%N)
REDIS_TIME=$(echo "$REDIS_END - $REDIS_START" | bc)
echo "Redis operations time: ${REDIS_TIME}s"

echo ""
echo "🎉 Performance testing completed!"
