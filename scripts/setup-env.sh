#!/usr/bin/env bash
set -euo pipefail

echo "🔧 Setting up environment variables..."

# Check if .env already exists
if [[ -f .env ]]; then
    echo "⚠️  .env file already exists. Please backup manually if needed."
    echo "   Note: Backup files with API keys should not be committed to git."
fi

# Create .env file with your actual API keys
cat > .env << 'EOF'
# Multi-Tenant AIaaS Platform - Environment Configuration

# Environment
ENVIRONMENT=development
DEBUG=true
APP_NAME=Multi-AI-Agent
APP_VERSION=2.0.0

# API KEYS - REQUIRED
# OpenAI API Key (Required) - Replace with your actual key
OPENAI_API_KEY=your_openai_api_key_here

# Firecrawl API Key (Optional - for web scraping)
FIRECRAWL_API_KEY=your_firecrawl_api_key_here

# Anthropic API Key (Optional)
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_agent
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=3600
DATABASE_ECHO=false

# Redis
REDIS_URL=redis://localhost:6379
REDIS_MAX_CONNECTIONS=20
REDIS_SOCKET_TIMEOUT=5
REDIS_SOCKET_CONNECT_TIMEOUT=5
REDIS_RETRY_ON_TIMEOUT=true

# NATS
NATS_URL=nats://localhost:4222
NATS_MAX_RECONNECT_ATTEMPTS=10
NATS_RECONNECT_TIME_WAIT=2
NATS_MAX_PAYLOAD=1048576
NATS_JETSTREAM_ENABLED=true

# OpenAI Configuration
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MAX_TOKENS=4000
OPENAI_TEMPERATURE=0.7
OPENAI_TIMEOUT=30

# Anthropic Configuration
ANTHROPIC_MAX_TOKENS=4000
ANTHROPIC_TEMPERATURE=0.7
ANTHROPIC_TIMEOUT=30

# Security
SECRET_KEY=your_secret_key_here_change_in_production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:8080,http://localhost:8099
RATE_LIMIT_PER_MINUTE=100
MAX_FILE_SIZE_MB=10

# Observability
OTEL_ENDPOINT=http://localhost:4317
PROMETHEUS_PORT=9090
GRAFANA_URL=http://localhost:3000
LOG_LEVEL=INFO
LOG_FORMAT=json

# Billing (Optional)
STRIPE_SECRET_KEY=your_stripe_secret_key_here
STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret_here
BRAINTREE_MERCHANT_ID=your_braintree_merchant_id_here
BRAINTREE_PUBLIC_KEY=your_braintree_public_key_here
BRAINTREE_PRIVATE_KEY=your_braintree_private_key_here

# Vector Database
VECTOR_DB_PROVIDER=chroma
VECTOR_DB_HOST=localhost
VECTOR_DB_PORT=8000
VECTOR_DB_COLLECTION=documents
VECTOR_DB_EMBEDDING_MODEL=text-embedding-ada-002

# Service Ports (Updated for our microservices)
API_GATEWAY_HOST=0.0.0.0
API_GATEWAY_PORT=8000
MODEL_GATEWAY_HOST=0.0.0.0
MODEL_GATEWAY_PORT=8080
RETRIEVAL_SERVICE_HOST=0.0.0.0
RETRIEVAL_SERVICE_PORT=8081
TOOLS_SERVICE_HOST=0.0.0.0
TOOLS_SERVICE_PORT=8082
ROUTER_SERVICE_HOST=0.0.0.0
ROUTER_SERVICE_PORT=8083
REALTIME_GATEWAY_HOST=0.0.0.0
REALTIME_GATEWAY_PORT=8084
CONFIG_SERVICE_HOST=0.0.0.0
CONFIG_SERVICE_PORT=8090
POLICY_ADAPTER_HOST=0.0.0.0
POLICY_ADAPTER_PORT=8091
FEATURE_FLAGS_SERVICE_HOST=0.0.0.0
FEATURE_FLAGS_SERVICE_PORT=8092
REGISTRY_SERVICE_HOST=0.0.0.0
REGISTRY_SERVICE_PORT=8094
USAGE_METERING_HOST=0.0.0.0
USAGE_METERING_PORT=8095
AUDIT_LOG_HOST=0.0.0.0
AUDIT_LOG_PORT=8096
NOTIFICATION_SERVICE_HOST=0.0.0.0
NOTIFICATION_SERVICE_PORT=8097
ADMIN_PORTAL_HOST=0.0.0.0
ADMIN_PORTAL_PORT=8099

# Frontend URLs
VITE_API_URL=http://localhost:8000
VITE_ADMIN_API_URL=http://localhost:8099
VITE_MODEL_GATEWAY_URL=http://localhost:8080

# Feature Flags
FEATURE_FLAGS_ENABLED=true
REGISTRY_ENABLED=true

# Multi-tenancy
DEFAULT_TENANT_ID=00000000-0000-0000-0000-000000000000
TENANT_ISOLATION_ENABLED=true

# Performance
MAX_CONCURRENT_REQUESTS=100
REQUEST_TIMEOUT=30
WORKER_PROCESSES=1
EOF

echo "✅ Environment variables set up successfully!"
echo ""
echo "🔑 Your API keys are now configured:"
echo "   • OpenAI API Key: [CONFIGURED]"
echo "   • Firecrawl API Key: [CONFIGURED]"
echo ""
echo "💡 To use these in your shell, run:"
echo "   source .env"
echo ""
echo "🚀 Or start the development environment:"
echo "   ./scripts/start-local.sh"
