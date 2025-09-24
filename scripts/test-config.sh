#!/usr/bin/env bash
set -euo pipefail

echo "⚙️ Testing configuration..."

# Test environment variables
echo "Testing environment variables..."
echo "================================"

# Check if .env file exists
if [[ -f .env ]]; then
  echo "✅ .env file exists"
  
  # Check for required environment variables
  REQUIRED_VARS=("DATABASE_URL" "REDIS_URL" "NATS_URL")
  
  for var in "${REQUIRED_VARS[@]}"; do
    if grep -q "^$var=" .env; then
      echo "✅ $var is set"
    else
      echo "❌ $var is missing"
    fi
  done
  
  # Check for API keys
  if grep -q "OPENAI_API_KEY=" .env; then
    echo "✅ OPENAI_API_KEY is set"
  else
    echo "⚠️  OPENAI_API_KEY is not set"
  fi
  
  if grep -q "ANTHROPIC_API_KEY=" .env; then
    echo "✅ ANTHROPIC_API_KEY is set"
  else
    echo "⚠️  ANTHROPIC_API_KEY is not set"
  fi
  
else
  echo "❌ .env file not found"
fi

# Test Docker configuration
echo ""
echo "Testing Docker configuration..."
echo "==============================="

# Check if docker-compose file exists
if [[ -f docker-compose.local.yml ]]; then
  echo "✅ docker-compose.local.yml exists"
else
  echo "❌ docker-compose.local.yml not found"
fi

# Check if Docker is running
if docker info > /dev/null 2>&1; then
  echo "✅ Docker is running"
else
  echo "❌ Docker is not running"
fi

# Test service configuration
echo ""
echo "Testing service configuration..."
echo "==============================="

# Check if services are configured
SERVICES=("ai-chatbot" "api-gateway" "model-gateway" "postgres" "redis" "nats")

for service in "${SERVICES[@]}"; do
  if docker-compose -f docker-compose.local.yml config --services | grep -q "$service"; then
    echo "✅ $service is configured"
  else
    echo "❌ $service is not configured"
  fi
done

# Test API configuration
echo ""
echo "Testing API configuration..."
echo "============================"

# Test API Gateway configuration
echo "Testing API Gateway configuration..."
API_CONFIG=$(curl -s http://localhost:8000/ --max-time 10)
if [[ -n "$API_CONFIG" ]]; then
  echo "✅ API Gateway configuration accessible"
else
  echo "❌ API Gateway configuration not accessible"
fi

# Test Model Gateway configuration
echo "Testing Model Gateway configuration..."
MODEL_CONFIG=$(curl -s http://localhost:8080/ --max-time 10)
if [[ -n "$MODEL_CONFIG" ]]; then
  echo "✅ Model Gateway configuration accessible"
else
  echo "❌ Model Gateway configuration not accessible"
fi

# Test frontend configuration
echo ""
echo "Testing frontend configuration..."
echo "================================="

# Test AI Chatbot configuration
echo "Testing AI Chatbot configuration..."
CHATBOT_CONFIG=$(curl -s http://localhost:3001/ --max-time 10)
if [[ "$CHATBOT_CONFIG" == *"<!DOCTYPE html"* ]] || [[ "$CHATBOT_CONFIG" == *"<html"* ]]; then
  echo "✅ AI Chatbot configuration accessible"
else
  echo "❌ AI Chatbot configuration not accessible"
fi

# Test Web Frontend configuration
echo "Testing Web Frontend configuration..."
WEB_CONFIG=$(curl -s http://localhost:3000/ --max-time 10)
if [[ "$WEB_CONFIG" == *"<!DOCTYPE html"* ]] || [[ "$WEB_CONFIG" == *"<html"* ]]; then
  echo "✅ Web Frontend configuration accessible"
else
  echo "❌ Web Frontend configuration not accessible"
fi

# Test Admin Portal configuration
echo "Testing Admin Portal configuration..."
ADMIN_CONFIG=$(curl -s http://localhost:8099/ --max-time 10)
if [[ "$ADMIN_CONFIG" == *"<!DOCTYPE html"* ]] || [[ "$ADMIN_CONFIG" == *"<html"* ]]; then
  echo "✅ Admin Portal configuration accessible"
else
  echo "❌ Admin Portal configuration not accessible"
fi

# Test database configuration
echo ""
echo "Testing database configuration..."
echo "================================="

# Test PostgreSQL configuration
echo "Testing PostgreSQL configuration..."
if docker exec multi-ai-agent-postgres-1 psql -U postgres -d ai_agent -c "SELECT 1;" > /dev/null 2>&1; then
  echo "✅ PostgreSQL configuration working"
else
  echo "❌ PostgreSQL configuration not working"
fi

# Test Redis configuration
echo "Testing Redis configuration..."
if docker exec multi-ai-agent-redis-1 redis-cli ping > /dev/null 2>&1; then
  echo "✅ Redis configuration working"
else
  echo "❌ Redis configuration not working"
fi

# Test NATS configuration
echo "Testing NATS configuration..."
if docker exec multi-ai-agent-nats-1 nats server check server > /dev/null 2>&1; then
  echo "✅ NATS configuration working"
else
  echo "❌ NATS configuration not working"
fi

# Test network configuration
echo ""
echo "Testing network configuration..."
echo "==============================="

# Test port availability
PORTS=("3000" "3001" "8000" "8099" "8080" "5433" "6379" "4222")

for port in "${PORTS[@]}"; do
  if netstat -tuln | grep -q ":$port " || ss -tuln | grep -q ":$port "; then
    echo "✅ Port $port is in use"
  else
    echo "❌ Port $port is not in use"
  fi
done

# Test service connectivity
echo ""
echo "Testing service connectivity..."
echo "==============================="

# Test API Gateway connectivity
echo "Testing API Gateway connectivity..."
if curl -f http://localhost:8000/healthz > /dev/null 2>&1; then
  echo "✅ API Gateway connectivity working"
else
  echo "❌ API Gateway connectivity not working"
fi

# Test Model Gateway connectivity
echo "Testing Model Gateway connectivity..."
if curl -f http://localhost:8080/healthz > /dev/null 2>&1; then
  echo "✅ Model Gateway connectivity working"
else
  echo "❌ Model Gateway connectivity not working"
fi

# Test frontend connectivity
echo "Testing frontend connectivity..."
if curl -f http://localhost:3001 > /dev/null 2>&1; then
  echo "✅ AI Chatbot connectivity working"
else
  echo "❌ AI Chatbot connectivity not working"
fi

# Summary
echo ""
echo "📊 Configuration Test Summary:"
echo "=============================="
echo "Environment variables: ✅ Checked"
echo "Docker configuration: ✅ Checked"
echo "Service configuration: ✅ Checked"
echo "API configuration: ✅ Checked"
echo "Frontend configuration: ✅ Checked"
echo "Database configuration: ✅ Checked"
echo "Network configuration: ✅ Checked"
echo "Service connectivity: ✅ Checked"

echo ""
echo "🎉 Configuration testing completed!"
echo ""
echo "💡 Configuration Tips:"
echo "  - Ensure all required environment variables are set"
echo "  - Check that all services are running"
echo "  - Verify network connectivity between services"
echo "  - Monitor logs for configuration errors"
echo "  - Test API endpoints for proper configuration"
