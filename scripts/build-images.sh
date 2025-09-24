#!/usr/bin/env bash
set -euo pipefail

# Build and push Docker images for cloud deployment
PROJECT_ID=${1:-"your-ai-chatbot-project"}
TAG=${2:-"latest"}

echo "🏗️  Building and pushing images to GCR..."

# Enable Docker for GCR
gcloud auth configure-docker

# Build and push frontend services
echo "📦 Building chatbot-ui..."
docker build -t gcr.io/$PROJECT_ID/ai-chatbot:$TAG ./frontend/chatbot-ui
docker push gcr.io/$PROJECT_ID/ai-chatbot:$TAG

echo "📦 Building web-frontend..."
docker build -t gcr.io/$PROJECT_ID/web-frontend:$TAG ./frontend/web
docker push gcr.io/$PROJECT_ID/web-frontend:$TAG

echo "📦 Building admin-portal..."
docker build -t gcr.io/$PROJECT_ID/admin-portal:$TAG ./frontend/admin-portal
docker push gcr.io/$PROJECT_ID/admin-portal:$TAG

# Build and push backend services
echo "📦 Building api-gateway..."
docker build -t gcr.io/$PROJECT_ID/api-gateway:$TAG ./apps/data-plane/api-gateway
docker push gcr.io/$PROJECT_ID/api-gateway:$TAG

echo "📦 Building model-gateway..."
docker build -t gcr.io/$PROJECT_ID/model-gateway:$TAG ./apps/data-plane/model-gateway
docker push gcr.io/$PROJECT_ID/model-gateway:$TAG

echo "📦 Building retrieval-service..."
docker build -t gcr.io/$PROJECT_ID/retrieval-service:$TAG ./apps/data-plane/retrieval-service
docker push gcr.io/$PROJECT_ID/retrieval-service:$TAG

echo "📦 Building tools-service..."
docker build -t gcr.io/$PROJECT_ID/tools-service:$TAG ./apps/data-plane/tools-service
docker push gcr.io/$PROJECT_ID/tools-service:$TAG

echo "📦 Building router-service..."
docker build -t gcr.io/$PROJECT_ID/router-service:$TAG ./apps/data-plane/router-service
docker push gcr.io/$PROJECT_ID/router-service:$TAG

# Build and push control plane services
echo "📦 Building config-service..."
docker build -t gcr.io/$PROJECT_ID/config-service:$TAG ./apps/control-plane/config-service
docker push gcr.io/$PROJECT_ID/config-service:$TAG

echo "📦 Building policy-adapter..."
docker build -t gcr.io/$PROJECT_ID/policy-adapter:$TAG ./apps/control-plane/policy-adapter
docker push gcr.io/$PROJECT_ID/policy-adapter:$TAG

echo "✅ All images built and pushed successfully!"
echo "📋 Images pushed to: gcr.io/$PROJECT_ID/"
echo "🏷️  Tag: $TAG"
