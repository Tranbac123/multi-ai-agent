#!/usr/bin/env bash
set -euo pipefail

echo "🔧 Starting backend services in development mode..."

# Check if virtual environment exists
if [[ ! -d "venv" ]]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Install service dependencies
for service in apps/*/*/; do
    if [[ -f "${service}requirements.txt" ]]; then
        echo "📦 Installing dependencies for ${service}"
        pip install -r "${service}requirements.txt"
    fi
done

echo ""
echo "🎯 Backend services ready for development!"
echo ""
echo "📋 Available services to run:"
echo "   • API Gateway:      cd apps/data-plane/api-gateway && python src/main.py"
echo "   • Model Gateway:    cd apps/data-plane/model-gateway && python src/main.py"
echo "   • Retrieval:        cd apps/data-plane/retrieval-service && python src/main.py"
echo "   • Tools:            cd apps/data-plane/tools-service && python src/main.py"
echo "   • Router:           cd apps/data-plane/router-service && python src/main.py"
echo "   • Config Service:   cd apps/control-plane/config-service && python src/main.py"
echo "   • Policy Adapter:   cd apps/control-plane/policy-adapter && python src/main.py"
echo "   • Admin Portal:     cd frontend/admin-portal && python src/main.py"
echo ""
echo "💡 Tip: Run each service in a separate terminal for full development experience"
