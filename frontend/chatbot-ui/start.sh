#!/usr/bin/env bash
set -e

echo "🚀 Starting AI Search Agent Frontend..."

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Copy environment file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📋 Setting up environment..."
    cp env.example .env
fi

echo "🎨 Starting development server..."
npm start




