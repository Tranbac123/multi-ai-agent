#!/bin/bash
# Install dependencies using constraints.txt for reproducible builds

set -e

echo "Installing dependencies with constraints..."

# Install from requirements.txt respecting constraints.txt
pip install -r requirements.txt -c constraints.txt

echo "Dependencies installed successfully!"
echo "Running security checks..."

# Run safety check
echo "Running safety check..."
safety check

# Run bandit security linter
echo "Running bandit security linter..."
bandit -r . -f json -o bandit-report.json || true

echo "Security checks completed!"
