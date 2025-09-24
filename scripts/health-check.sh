#!/usr/bin/env bash
set -euo pipefail

# Health check script for cloud deployment
NAMESPACE=${1:-"ai-chatbot"}
TIMEOUT=${2:-"300"}

echo "🔍 Running health checks for $NAMESPACE namespace..."

# Function to check if a service is healthy
check_service() {
    local service_name=$1
    local endpoint=$2
    local max_attempts=$3
    local attempt=1
    
    echo "🔍 Checking $service_name..."
    
    while [ $attempt -le $max_attempts ]; do
        if kubectl exec -n $NAMESPACE deployment/$service_name -- curl -f -s $endpoint > /dev/null 2>&1; then
            echo "✅ $service_name is healthy"
            return 0
        else
            echo "⏳ $service_name not ready (attempt $attempt/$max_attempts)"
            sleep 10
            ((attempt++))
        fi
    done
    
    echo "❌ $service_name failed health check after $max_attempts attempts"
    return 1
}

# Function to check external endpoint
check_external_endpoint() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    echo "🔍 Checking external endpoint: $service_name ($url)..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f -s -m 10 "$url" > /dev/null 2>&1; then
            echo "✅ $service_name external endpoint is accessible"
            return 0
        else
            echo "⏳ $service_name external endpoint not ready (attempt $attempt/$max_attempts)"
            sleep 10
            ((attempt++))
        fi
    done
    
    echo "❌ $service_name external endpoint failed after $max_attempts attempts"
    return 1
}

# Check if namespace exists
if ! kubectl get namespace $NAMESPACE > /dev/null 2>&1; then
    echo "❌ Namespace $NAMESPACE does not exist"
    exit 1
fi

echo "📊 Checking deployment status..."
kubectl get deployments -n $NAMESPACE

echo "📊 Checking pod status..."
kubectl get pods -n $NAMESPACE

echo "📊 Checking service status..."
kubectl get services -n $NAMESPACE

# Wait for deployments to be ready
echo "⏳ Waiting for deployments to be ready..."
kubectl wait --for=condition=available --timeout=${TIMEOUT}s deployment/ai-chatbot -n $NAMESPACE || true
kubectl wait --for=condition=available --timeout=${TIMEOUT}s deployment/api-gateway -n $NAMESPACE || true

# Internal health checks
echo "🔍 Running internal health checks..."

# Check API Gateway
if kubectl get deployment api-gateway -n $NAMESPACE > /dev/null 2>&1; then
    check_service "api-gateway" "http://localhost:8000/healthz" 30
else
    echo "⚠️  API Gateway deployment not found, skipping internal check"
fi

# Check AI Chatbot
if kubectl get deployment ai-chatbot -n $NAMESPACE > /dev/null 2>&1; then
    check_service "ai-chatbot" "http://localhost:3000" 30
else
    echo "⚠️  AI Chatbot deployment not found, skipping internal check"
fi

# Get external endpoints
echo "🌐 Checking external endpoints..."

# Get LoadBalancer IPs
CHATBOT_IP=$(kubectl get service ai-chatbot-service -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
ADMIN_IP=$(kubectl get service admin-portal-service -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")

# Check external endpoints if LoadBalancer IPs are available
if [ -n "$CHATBOT_IP" ]; then
    check_external_endpoint "http://$CHATBOT_IP" "AI Chatbot"
else
    echo "⚠️  AI Chatbot LoadBalancer IP not available"
fi

if [ -n "$ADMIN_IP" ]; then
    check_external_endpoint "http://$ADMIN_IP" "Admin Portal"
else
    echo "⚠️  Admin Portal LoadBalancer IP not available"
fi

# Performance check
echo "⚡ Running performance check..."
if [ -n "$CHATBOT_IP" ]; then
    echo "Testing API response time..."
    RESPONSE_TIME=$(curl -w "%{time_total}" -s -o /dev/null "http://$CHATBOT_IP" || echo "timeout")
    echo "Response time: ${RESPONSE_TIME}s"
    
    if (( $(echo "$RESPONSE_TIME < 5.0" | bc -l) )); then
        echo "✅ Performance check passed"
    else
        echo "⚠️  Performance check failed - response time too high"
    fi
fi

# Resource usage check
echo "📊 Checking resource usage..."
kubectl top pods -n $NAMESPACE 2>/dev/null || echo "⚠️  Metrics server not available"

# Final status
echo "🎯 Health check summary:"
echo "📋 Deployments:"
kubectl get deployments -n $NAMESPACE -o wide

echo "📋 Services:"
kubectl get services -n $NAMESPACE -o wide

echo "📋 Pods:"
kubectl get pods -n $NAMESPACE -o wide

echo "✅ Health check completed!"
