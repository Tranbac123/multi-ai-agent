#!/usr/bin/env bash
set -euo pipefail

echo "🔧 Environment Status Check"
echo "=========================="

# Source environment variables
if [[ -f .env ]]; then
    export $(grep -v '^#' .env | xargs)
    echo "✅ .env file loaded"
else
    echo "❌ .env file not found"
    echo "   Run: ./scripts/setup-env.sh"
    exit 1
fi

echo ""
echo "🔑 API Keys Status:"
echo "-------------------"

# Check OpenAI
if [[ -n "${OPENAI_API_KEY:-}" && "${OPENAI_API_KEY}" != "your_openai_api_key_here" ]]; then
    echo "✅ OpenAI API Key: ${OPENAI_API_KEY:0:20}..."
else
    echo "❌ OpenAI API Key: Not set"
fi

# Check Firecrawl
if [[ -n "${FIRECRAWL_API_KEY:-}" && "${FIRECRAWL_API_KEY}" != "your_firecrawl_api_key_here" ]]; then
    echo "✅ Firecrawl API Key: ${FIRECRAWL_API_KEY:0:15}..."
else
    echo "❌ Firecrawl API Key: Not set"
fi

# Check Anthropic
if [[ -n "${ANTHROPIC_API_KEY:-}" && "${ANTHROPIC_API_KEY}" != "your_anthropic_api_key_here" ]]; then
    echo "✅ Anthropic API Key: ${ANTHROPIC_API_KEY:0:15}..."
else
    echo "ℹ️  Anthropic API Key: Not set (optional)"
fi

echo ""
echo "🗄️  Infrastructure Status:"
echo "-------------------------"

# Check if Docker is running
if docker info > /dev/null 2>&1; then
    echo "✅ Docker: Running"
else
    echo "❌ Docker: Not running"
fi

# Check if services are running
if docker-compose -f docker-compose.local.yml ps | grep -q "Up"; then
    echo "✅ Services: Some are running"
    echo ""
    echo "📊 Running Services:"
    docker-compose -f docker-compose.local.yml ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
else
    echo "ℹ️  Services: Not running"
    echo "   Run: ./scripts/start-local.sh"
fi

echo ""
echo ""
echo "🌐 Frontend Applications:"
echo "------------------------"
echo "   • Web Frontend:           http://localhost:3000"
echo "   • AI Chatbot:             http://localhost:3001"
echo "   • Admin Portal:           http://localhost:8099"

echo ""
echo "🎯 Quick Commands:"
echo "-----------------"
echo "   • Start all services:     ./scripts/start-local.sh"
echo "   • Test API keys:          ./scripts/test-api-keys.sh"
echo "   • Setup environment:      ./scripts/setup-env.sh"
echo "   • Run P0 tests:           ./scripts/run_p0_subset.sh"
echo "   • Stop services:          docker-compose -f docker-compose.local.yml down"
