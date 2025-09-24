#!/usr/bin/env bash
set -euo pipefail

echo "🌐 Testing frontend applications..."

FAILED_FRONTENDS=()

# Test chatbot UI
echo "Testing AI Chatbot UI..."
CHATBOT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3001 --max-time 10)
if [ "$CHATBOT_STATUS" = "200" ]; then
  echo "✅ Chatbot UI accessible (HTTP $CHATBOT_STATUS)"
else
  echo "❌ Chatbot UI not accessible (HTTP $CHATBOT_STATUS)"
  FAILED_FRONTENDS+=("AI Chatbot UI")
fi

# Test web frontend
echo "Testing Web Frontend..."
WEB_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 --max-time 10)
if [ "$WEB_STATUS" = "200" ]; then
  echo "✅ Web Frontend accessible (HTTP $WEB_STATUS)"
else
  echo "❌ Web Frontend not accessible (HTTP $WEB_STATUS)"
  FAILED_FRONTENDS+=("Web Frontend")
fi

# Test admin portal
echo "Testing Admin Portal..."
ADMIN_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099 --max-time 10)
if [ "$ADMIN_STATUS" = "200" ]; then
  echo "✅ Admin Portal accessible (HTTP $ADMIN_STATUS)"
else
  echo "❌ Admin Portal not accessible (HTTP $ADMIN_STATUS)"
  FAILED_FRONTENDS+=("Admin Portal")
fi

# Test if frontends serve HTML content
echo ""
echo "Testing frontend content..."

# Check if chatbot UI serves HTML
echo "Checking Chatbot UI content..."
CHATBOT_CONTENT=$(curl -s http://localhost:3001 --max-time 10 | head -1)
if [[ "$CHATBOT_CONTENT" == *"<!DOCTYPE html"* ]] || [[ "$CHATBOT_CONTENT" == *"<html"* ]]; then
  echo "✅ Chatbot UI serves HTML content"
else
  echo "❌ Chatbot UI doesn't serve HTML content"
  echo "Content preview: ${CHATBOT_CONTENT:0:100}..."
fi

# Check if web frontend serves HTML
echo "Checking Web Frontend content..."
WEB_CONTENT=$(curl -s http://localhost:3000 --max-time 10 | head -1)
if [[ "$WEB_CONTENT" == *"<!DOCTYPE html"* ]] || [[ "$WEB_CONTENT" == *"<html"* ]]; then
  echo "✅ Web Frontend serves HTML content"
else
  echo "❌ Web Frontend doesn't serve HTML content"
  echo "Content preview: ${WEB_CONTENT:0:100}..."
fi

# Check if admin portal serves HTML
echo "Checking Admin Portal content..."
ADMIN_CONTENT=$(curl -s http://localhost:8099 --max-time 10 | head -1)
if [[ "$ADMIN_CONTENT" == *"<!DOCTYPE html"* ]] || [[ "$ADMIN_CONTENT" == *"<html"* ]]; then
  echo "✅ Admin Portal serves HTML content"
else
  echo "❌ Admin Portal doesn't serve HTML content"
  echo "Content preview: ${ADMIN_CONTENT:0:100}..."
fi

# Test frontend build artifacts
echo ""
echo "Testing frontend build artifacts..."

# Check for static assets
echo "Checking for static assets..."
STATIC_ASSETS=$(curl -s http://localhost:3001/static/ --max-time 10 2>/dev/null || echo "No static assets endpoint")
if [[ "$STATIC_ASSETS" != "No static assets endpoint" ]]; then
  echo "✅ Static assets accessible"
else
  echo "⚠️  Static assets endpoint not found (this may be normal for development)"
fi

# Summary
echo ""
if [ ${#FAILED_FRONTENDS[@]} -eq 0 ]; then
  echo "🎉 All frontend applications are accessible!"
else
  echo "❌ Failed frontend applications:"
  for frontend in "${FAILED_FRONTENDS[@]}"; do
    echo "  - $frontend"
  done
  echo ""
  echo "💡 Troubleshooting tips:"
  echo "  - Check if containers are running: docker-compose ps"
  echo "  - Check frontend logs: docker-compose logs ai-chatbot web-frontend admin-portal"
  echo "  - Restart frontend services: docker-compose restart ai-chatbot web-frontend admin-portal"
  exit 1
fi
