#!/usr/bin/env bash
set -euo pipefail

echo "🔑 Testing API Keys..."

# Source environment variables
if [[ -f .env ]]; then
    export $(grep -v '^#' .env | xargs)
else
    echo "❌ .env file not found. Run ./scripts/setup-env.sh first"
    exit 1
fi

# Test OpenAI API Key
if [[ -n "${OPENAI_API_KEY:-}" && "${OPENAI_API_KEY}" != "your_openai_api_key_here" ]]; then
    echo "✅ OpenAI API Key is set: ${OPENAI_API_KEY:0:20}..."
    
    # Test OpenAI API connectivity
    echo "🧪 Testing OpenAI API connectivity..."
    if curl -s -H "Authorization: Bearer $OPENAI_API_KEY" \
            -H "Content-Type: application/json" \
            https://api.openai.com/v1/models > /dev/null; then
        echo "✅ OpenAI API is accessible"
    else
        echo "⚠️  OpenAI API test failed (check your key or network)"
    fi
else
    echo "❌ OpenAI API Key not set or invalid"
fi

# Test Firecrawl API Key
if [[ -n "${FIRECRAWL_API_KEY:-}" && "${FIRECRAWL_API_KEY}" != "your_firecrawl_api_key_here" ]]; then
    echo "✅ Firecrawl API Key is set: ${FIRECRAWL_API_KEY:0:15}..."
    
    # Test Firecrawl API connectivity
    echo "🧪 Testing Firecrawl API connectivity..."
    if curl -s -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
            -H "Content-Type: application/json" \
            https://api.firecrawl.dev/v0/scrape > /dev/null; then
        echo "✅ Firecrawl API is accessible"
    else
        echo "⚠️  Firecrawl API test failed (check your key or network)"
    fi
else
    echo "❌ Firecrawl API Key not set or invalid"
fi

# Test Anthropic API Key (optional)
if [[ -n "${ANTHROPIC_API_KEY:-}" && "${ANTHROPIC_API_KEY}" != "your_anthropic_api_key_here" ]]; then
    echo "✅ Anthropic API Key is set: ${ANTHROPIC_API_KEY:0:15}..."
else
    echo "ℹ️  Anthropic API Key not set (optional)"
fi

echo ""
echo "🎯 Summary:"
echo "   • OpenAI: ${OPENAI_API_KEY:+✅ Set}${OPENAI_API_KEY:-❌ Not set}"
echo "   • Firecrawl: ${FIRECRAWL_API_KEY:+✅ Set}${FIRECRAWL_API_KEY:-❌ Not set}"
echo "   • Anthropic: ${ANTHROPIC_API_KEY:+✅ Set}${ANTHROPIC_API_KEY:-ℹ️ Optional}"

if [[ -n "${OPENAI_API_KEY:-}" && "${OPENAI_API_KEY}" != "your_openai_api_key_here" ]]; then
    echo ""
    echo "🚀 Ready to start development!"
    echo "   Run: ./scripts/start-local.sh"
else
    echo ""
    echo "⚠️  Please set your OpenAI API key to get started"
    echo "   Run: ./scripts/setup-env.sh"
fi
