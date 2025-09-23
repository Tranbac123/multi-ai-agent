#!/usr/bin/env bash
set -euo pipefail

echo "🌐 Setting up frontend development environment..."

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 18+ and try again."
    echo "   Download from: https://nodejs.org/"
    exit 1
fi

# Check Node.js version
NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [[ $NODE_VERSION -lt 18 ]]; then
    echo "⚠️  Node.js version $NODE_VERSION detected. Version 18+ recommended."
fi

echo "📦 Setting up Web Frontend (React + Vite)..."
cd frontend/web

# Install dependencies
if [[ ! -d "node_modules" ]]; then
    echo "📥 Installing web frontend dependencies..."
    npm install
else
    echo "✅ Web frontend dependencies already installed"
fi

echo ""
echo "📦 Setting up Admin Portal (FastAPI)..."
cd ../admin-portal

# Check if virtual environment exists
if [[ ! -d "venv" ]]; then
    echo "📦 Creating Python virtual environment for admin portal..."
    python3 -m venv venv
fi

# Activate virtual environment and install dependencies
source venv/bin/activate
echo "📥 Installing admin portal dependencies..."
pip install -r requirements.txt

echo ""
echo "🎉 Frontend development environment ready!"
echo ""
echo "🚀 To start frontend services:"
echo "   • Web Frontend:    cd frontend/web && npm run dev"
echo "   • Admin Portal:    cd frontend/admin-portal && source venv/bin/activate && python src/main.py"
echo ""
echo "📊 Frontend URLs:"
echo "   • Web Frontend:    http://localhost:5173 (Vite dev server)"
echo "   • Admin Portal:    http://localhost:8099"
echo ""
echo "💡 Tip: Run each frontend service in a separate terminal"
