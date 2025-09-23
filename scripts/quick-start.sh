#!/usr/bin/env bash
set -euo pipefail

echo "🚀 AI Agent Platform - Quick Start"
echo "=================================="
echo ""

# Check prerequisites
echo "🔍 Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker and try again."
    exit 1
fi

if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

echo "✅ Docker is available"

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 18+ and try again."
    exit 1
fi

NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [[ $NODE_VERSION -lt 18 ]]; then
    echo "⚠️  Node.js version $NODE_VERSION detected. Version 18+ recommended."
else
    echo "✅ Node.js $(node -v) is available"
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.11+ and try again."
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✅ Python $PYTHON_VERSION is available"

echo ""
echo "🎯 Choose your setup method:"
echo ""
echo "1. 🐳 Full Docker Setup (Recommended)"
echo "   - Runs everything in containers"
echo "   - Easiest to get started"
echo "   - Good for testing and demos"
echo ""
echo "2. 🔧 Development Setup"
echo "   - Runs services natively"
echo "   - Better for active development"
echo "   - More control over debugging"
echo ""
echo "3. 📚 View Documentation"
echo "   - See detailed setup instructions"
echo ""

read -p "Enter your choice (1-3): " choice

case $choice in
    1)
        echo ""
        echo "🐳 Starting Full Docker Setup..."
        echo ""
        ./scripts/dev-setup.sh
        echo ""
        read -p "Set API keys now? (y/n): " set_keys
        if [[ $set_keys == "y" || $set_keys == "Y" ]]; then
            echo ""
            echo "Enter your API keys (press Enter to skip):"
            read -p "OpenAI API Key: " openai_key
            read -p "Anthropic API Key: " anthropic_key
            
            if [[ -n "$openai_key" ]]; then
                export OPENAI_API_KEY="$openai_key"
            fi
            if [[ -n "$anthropic_key" ]]; then
                export ANTHROPIC_API_KEY="$anthropic_key"
            fi
        fi
        echo ""
        echo "🚀 Starting all services..."
        ./scripts/start-local.sh
        ;;
    2)
        echo ""
        echo "🔧 Starting Development Setup..."
        echo ""
        echo "Step 1: Infrastructure services..."
        ./scripts/dev-infrastructure.sh
        echo ""
        echo "Step 2: Backend services..."
        ./scripts/dev-backend.sh
        echo ""
        echo "Step 3: Frontend services..."
        ./scripts/dev-frontend.sh
        echo ""
        echo "✅ Development environment ready!"
        echo ""
        echo "Next steps:"
        echo "1. Start infrastructure: ./scripts/dev-infrastructure.sh"
        echo "2. Run backend services in separate terminals"
        echo "3. Run frontend services in separate terminals"
        ;;
    3)
        echo ""
        echo "📚 Opening documentation..."
        if command -v code &> /dev/null; then
            code LOCAL_DEVELOPMENT.md
        elif command -v open &> /dev/null; then
            open LOCAL_DEVELOPMENT.md
        else
            echo "Please open LOCAL_DEVELOPMENT.md in your preferred editor"
        fi
        ;;
    *)
        echo "❌ Invalid choice. Please run the script again and choose 1, 2, or 3."
        exit 1
        ;;
esac
