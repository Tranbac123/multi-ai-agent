#!/usr/bin/env bash
set -euo pipefail

echo "🗄️ Testing database connectivity..."

FAILED_DB=()

# Test PostgreSQL
echo "Testing PostgreSQL..."
if docker exec multi-ai-agent-postgres-1 pg_isready -U postgres > /dev/null 2>&1; then
  echo "✅ PostgreSQL is ready"
else
  echo "❌ PostgreSQL is not ready"
  FAILED_DB+=("PostgreSQL")
fi

# Test Redis
echo "Testing Redis..."
if docker exec multi-ai-agent-redis-1 redis-cli ping > /dev/null 2>&1; then
  echo "✅ Redis is ready"
else
  echo "❌ Redis is not ready"
  FAILED_DB+=("Redis")
fi

# Test NATS
echo "Testing NATS..."
if docker exec multi-ai-agent-nats-1 nats server check server > /dev/null 2>&1; then
  echo "✅ NATS is ready"
else
  echo "❌ NATS is not ready"
  FAILED_DB+=("NATS")
fi

# Test database write/read
echo ""
echo "Testing database write/read operations..."

# Test PostgreSQL write/read
echo "Testing PostgreSQL write/read..."
docker exec multi-ai-agent-postgres-1 psql -U postgres -d ai_agent -c "
  CREATE TABLE IF NOT EXISTS test_table (
    id SERIAL PRIMARY KEY,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
" > /dev/null 2>&1

# Insert test data
docker exec multi-ai-agent-postgres-1 psql -U postgres -d ai_agent -c "
  INSERT INTO test_table (message) VALUES ('Test message');
" > /dev/null 2>&1

# Read test data
RESULT=$(docker exec multi-ai-agent-postgres-1 psql -U postgres -d ai_agent -t -c "
  SELECT message FROM test_table WHERE message = 'Test message';
" 2>/dev/null)

if [[ "$RESULT" == *"Test message"* ]]; then
  echo "✅ PostgreSQL write/read working"
else
  echo "❌ PostgreSQL write/read failed"
  FAILED_DB+=("PostgreSQL write/read")
fi

# Clean up test data
docker exec multi-ai-agent-postgres-1 psql -U postgres -d ai_agent -c "
  DROP TABLE IF EXISTS test_table;
" > /dev/null 2>&1

# Test Redis write/read
echo "Testing Redis write/read..."
docker exec multi-ai-agent-redis-1 redis-cli set test_key "test_value" > /dev/null 2>&1
REDIS_RESULT=$(docker exec multi-ai-agent-redis-1 redis-cli get test_key 2>/dev/null)

if [[ "$REDIS_RESULT" == *"test_value"* ]]; then
  echo "✅ Redis write/read working"
else
  echo "❌ Redis write/read failed"
  FAILED_DB+=("Redis write/read")
fi

# Clean up Redis test data
docker exec multi-ai-agent-redis-1 redis-cli del test_key > /dev/null 2>&1

# Test database performance
echo ""
echo "Testing database performance..."

# PostgreSQL performance
echo "Testing PostgreSQL performance..."
PG_START=$(date +%s.%N)
docker exec multi-ai-agent-postgres-1 psql -U postgres -d ai_agent -c "SELECT COUNT(*) FROM information_schema.tables;" > /dev/null 2>&1
PG_END=$(date +%s.%N)
PG_TIME=$(echo "$PG_END - $PG_START" | bc)
echo "PostgreSQL query time: ${PG_TIME}s"

# Redis performance
echo "Testing Redis performance..."
REDIS_START=$(date +%s.%N)
docker exec multi-ai-agent-redis-1 redis-cli set perf_test "value" > /dev/null 2>&1
docker exec multi-ai-agent-redis-1 redis-cli get perf_test > /dev/null 2>&1
docker exec multi-ai-agent-redis-1 redis-cli del perf_test > /dev/null 2>&1
REDIS_END=$(date +%s.%N)
REDIS_TIME=$(echo "$REDIS_END - $REDIS_START" | bc)
echo "Redis operations time: ${REDIS_TIME}s"

# Test database connections
echo ""
echo "Testing database connections..."

# Test PostgreSQL connection count
echo "Testing PostgreSQL connections..."
PG_CONNECTIONS=$(docker exec multi-ai-agent-postgres-1 psql -U postgres -d ai_agent -t -c "SELECT COUNT(*) FROM pg_stat_activity;" 2>/dev/null)
echo "Active PostgreSQL connections: $PG_CONNECTIONS"

# Test Redis connection
echo "Testing Redis connections..."
REDIS_CONNECTIONS=$(docker exec multi-ai-agent-redis-1 redis-cli info clients | grep connected_clients | cut -d: -f2 | tr -d '\r')
echo "Active Redis connections: $REDIS_CONNECTIONS"

# Test database size
echo ""
echo "Testing database size..."
PG_SIZE=$(docker exec multi-ai-agent-postgres-1 psql -U postgres -d ai_agent -t -c "SELECT pg_size_pretty(pg_database_size('ai_agent'));" 2>/dev/null)
echo "PostgreSQL database size: $PG_SIZE"

# Test database tables
echo ""
echo "Testing database tables..."
TABLES=$(docker exec multi-ai-agent-postgres-1 psql -U postgres -d ai_agent -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null)
echo "Number of tables in ai_agent database: $TABLES"

# Summary
echo ""
if [ ${#FAILED_DB[@]} -eq 0 ]; then
  echo "🎉 All database tests passed!"
  echo "✅ PostgreSQL: Ready and working"
  echo "✅ Redis: Ready and working"
  echo "✅ NATS: Ready and working"
else
  echo "❌ Some database tests failed:"
  for db in "${FAILED_DB[@]}"; do
    echo "  - $db"
  done
  echo ""
  echo "💡 Troubleshooting tips:"
  echo "  - Check container logs: docker-compose logs postgres redis nats"
  echo "  - Restart database services: docker-compose restart postgres redis nats"
  echo "  - Check database configuration in .env file"
  exit 1
fi
