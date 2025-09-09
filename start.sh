#!/bin/bash

echo "🚀 AI Customer Agent - Quick Start"
echo "=================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp env.example .env
    echo "⚠️  Please edit .env file with your API keys before continuing!"
    echo "   - OpenAI API key"
    echo "   - JWT secret"
    echo "   - Payment service URL"
    echo ""
    read -p "Press Enter after editing .env file..."
fi

# Build and start services
echo "🔨 Building Docker images..."
make build

echo "🚀 Starting services..."
make up

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 15

# Check if services are running
echo "🔍 Checking service status..."
if curl -s http://localhost:8000/healthz > /dev/null; then
    echo "✅ API is running at http://localhost:8000"
else
    echo "❌ API is not responding"
fi

if curl -s http://localhost:5173 > /dev/null; then
    echo "✅ Web interface is running at http://localhost:5173"
else
    echo "❌ Web interface is not responding"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "📚 Next steps:"
echo "   1. View API documentation: http://localhost:8000/docs"
echo "   2. Access web interface: http://localhost:8000"
echo "   3. Try the demo flow: 'I want to buy T-shirt A size M'"
echo ""
echo "🛠️  Useful commands:"
echo "   make logs          - View service logs"
echo "   make down          - Stop services"
echo "   make seed          - Seed demo data"
echo "   make test          - Run tests"
echo ""
echo "📖 For more information, see README.md"
