#!/usr/bin/env bash
set -euo pipefail

echo "🔄 Starting continuous testing..."

# Check if fswatch is available
if ! command -v fswatch &> /dev/null; then
  echo "⚠️  fswatch not installed. Installing fswatch for file watching..."
  
  if [[ "$OSTYPE" == "darwin"* ]]; then
    if command -v brew &> /dev/null; then
      brew install fswatch
    else
      echo "❌ Homebrew not found. Please install fswatch manually"
      echo "   macOS: brew install fswatch"
      echo "   Ubuntu: sudo apt-get install fswatch"
      exit 1
    fi
  else
    # Linux installation
    sudo apt-get update
    sudo apt-get install fswatch
  fi
fi

# Function to run tests
run_tests() {
  echo ""
  echo "🔄 Changes detected, running tests..."
  echo "Time: $(date)"
  echo "=================================="
  
  # Run quick tests first
  ./scripts/test-health.sh
  if [ $? -eq 0 ]; then
    echo "✅ Health checks passed, running full test suite..."
    ./scripts/run-all-tests.sh
  else
    echo "❌ Health checks failed, skipping full test suite"
  fi
  
  echo "=================================="
  echo "Test cycle completed at $(date)"
  echo ""
}

# Watch for changes in key directories
echo "Watching for changes in:"
echo "  - apps/ (backend services)"
echo "  - frontend/ (frontend applications)"
echo "  - docker-compose.local.yml"
echo "  - .env"
echo ""
echo "Press Ctrl+C to stop continuous testing"
echo ""

# Run initial test
run_tests

# Watch for changes
fswatch -o \
  apps/ \
  frontend/ \
  docker-compose.local.yml \
  .env \
  | while read; do
  run_tests
done
