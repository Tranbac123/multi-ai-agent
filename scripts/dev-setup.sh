#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Setting up local development environment..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if required environment variables are set
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "⚠️  OPENAI_API_KEY not set. Some model features may not work."
    echo "   Set it with: export OPENAI_API_KEY=your_key_here"
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    echo "⚠️  ANTHROPIC_API_KEY not set. Some model features may not work."
    echo "   Set it with: export ANTHROPIC_API_KEY=your_key_here"
fi

# Create .env file if it doesn't exist
if [[ ! -f .env ]]; then
    echo "📝 Creating .env file..."
    cat > .env << EOF
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_agent

# Redis
REDIS_URL=redis://localhost:6379

# NATS
NATS_URL=nats://localhost:4222

# API Keys (set these with your actual keys)
OPENAI_API_KEY=${OPENAI_API_KEY:-}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}

# Frontend URLs
VITE_API_URL=http://localhost:8000
VITE_ADMIN_API_URL=http://localhost:8099
EOF
fi

echo "✅ Environment setup complete!"
echo ""
echo "🎯 Next steps:"
echo "   1. Set your API keys: export OPENAI_API_KEY=your_key"
echo "   2. Start services: ./scripts/start-local.sh"
echo "   3. Or run individual services: ./scripts/dev-*.sh"
