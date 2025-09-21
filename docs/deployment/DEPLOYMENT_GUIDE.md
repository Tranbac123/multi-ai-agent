# Deployment Guide - Multi-Tenant AIaaS Platform

## 🚀 **Complete Deployment Guide**

This guide provides comprehensive instructions for deploying the Multi-Tenant AIaaS Platform in development, staging, and production environments.

## 📋 **Prerequisites**

### **System Requirements**

- **Operating System**: Linux (Ubuntu 20.04+), macOS, or Windows with WSL2
- **Memory**: Minimum 8GB RAM (16GB recommended for production)
- **Storage**: Minimum 20GB free disk space (50GB recommended)
- **CPU**: 4+ cores (8+ cores recommended for production)

### **Required Software**

- **Docker**: 20.10+ with Docker Compose 2.0+
- **Python**: 3.11+ with pip
- **Git**: 2.30+
- **Kubectl**: 1.24+ (for Kubernetes deployment)
- **Helm**: 3.8+ (for Kubernetes deployment)

### **External Services**

- **OpenAI API Key**: For LLM functionality
- **PostgreSQL**: 15+ (managed service recommended for production)
- **Redis**: 7+ (managed service recommended for production)
- **NATS**: 2.9+ (managed service recommended for production)

## 🏗️ **Architecture Overview**

The platform consists of 7 microservices with supporting infrastructure:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Gateway   │    │  Orchestrator   │    │  Router Service │
│   Port: 8000    │◄──►│   Port: 8001    │◄──►│   Port: 8002    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Realtime      │    │   Ingestion     │    │   Analytics     │
│   Port: 8003    │    │   Port: 8004    │    │   Port: 8005    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Billing       │    │   Database      │    │   Event Bus     │
│   Port: 8006    │    │   PostgreSQL    │    │   NATS          │
└─────────────────┘    │   Port: 5432    │    │   Port: 4222    │
                       └─────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │     Redis       │    │  Observability  │
                       │   Port: 6379    │    │ Prometheus/Graf │
                       └─────────────────┘    └─────────────────┘
```

## 🔧 **Environment Setup**

### **1. Clone Repository**

```bash
git clone https://github.com/your-org/multi-ai-agent.git
cd multi-ai-agent
```

### **2. Environment Configuration**

```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

**Required Environment Variables:**

```bash
# Database Configuration
POSTGRES_URL=postgresql://user:password@localhost:5432/ai_platform
REDIS_URL=redis://localhost:6379/0
NATS_URL=nats://localhost:4222

# API Keys
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-your-anthropic-key

# Security
JWT_SECRET=your-jwt-secret-key
ENCRYPTION_KEY=your-encryption-key

# Service Configuration
API_GATEWAY_PORT=8000
ORCHESTRATOR_PORT=8001
ROUTER_PORT=8002
REALTIME_PORT=8003
INGESTION_PORT=8004
ANALYTICS_PORT=8005
BILLING_PORT=8006

# Monitoring
PROMETHEUS_URL=http://localhost:9090
GRAFANA_URL=http://localhost:3000
JAEGER_URL=http://localhost:16686

# Feature Flags
ENABLE_FEATURE_FLAGS=true
ENABLE_ANALYTICS=true
ENABLE_BILLING=true

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

## 🐳 **Docker Deployment**

### **Development Environment**

#### **1. Quick Start**

```bash
# Start all services
make dev

# Or use the start script
./start.sh
```

#### **2. Manual Docker Compose**

```bash
# Build images
docker-compose -f docker-compose.dev.yml build

# Start services
docker-compose -f docker-compose.dev.yml up -d

# Check status
docker-compose -f docker-compose.dev.yml ps

# View logs
docker-compose -f docker-compose.dev.yml logs -f
```

#### **3. Individual Service Management**

```bash
# Start specific service
docker-compose -f docker-compose.dev.yml up -d api-gateway

# Stop specific service
docker-compose -f docker-compose.dev.yml stop api-gateway

# Restart service
docker-compose -f docker-compose.dev.yml restart api-gateway

# Scale service
docker-compose -f docker-compose.dev.yml up -d --scale orchestrator=3
```

### **Production Environment**

#### **1. Production Docker Compose**

```bash
# Build production images
docker-compose -f docker-compose.prod.yml build

# Start production services
docker-compose -f docker-compose.prod.yml up -d

# Check health
docker-compose -f docker-compose.prod.yml ps
curl http://localhost:8000/healthz
```

#### **2. Production Configuration**

```yaml
# docker-compose.prod.yml
version: "3.8"

services:
  api-gateway:
    image: ai-platform/api-gateway:latest
    ports:
      - "8000:8000"
    environment:
      - ENV=production
      - LOG_LEVEL=WARNING
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 1G
          cpus: "0.5"
        reservations:
          memory: 512M
          cpus: "0.25"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## ☸️ **Kubernetes Deployment**

### **1. Prerequisites**

```bash
# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"

# Install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Verify installation
kubectl version --client
helm version
```

### **2. Cluster Setup**

#### **Local Development (Minikube)**

```bash
# Start Minikube
minikube start --memory=8192 --cpus=4

# Enable ingress
minikube addons enable ingress

# Check status
kubectl get nodes
```

#### **Production Cluster (AWS EKS)**

```bash
# Create EKS cluster
eksctl create cluster \
  --name ai-platform \
  --region us-west-2 \
  --nodegroup-name workers \
  --node-type t3.medium \
  --nodes 3 \
  --nodes-min 1 \
  --nodes-max 5

# Configure kubectl
aws eks update-kubeconfig --region us-west-2 --name ai-platform
```

### **3. Kubernetes Manifests**

#### **Namespace Setup**

```bash
# Create namespace
kubectl create namespace ai-platform

# Set context
kubectl config set-context --current --namespace=ai-platform
```

#### **ConfigMap and Secrets**

```bash
# Create ConfigMap
kubectl create configmap ai-platform-config \
  --from-env-file=.env \
  --namespace=ai-platform

# Create Secrets
kubectl create secret generic ai-platform-secrets \
  --from-literal=openai-api-key=$OPENAI_API_KEY \
  --from-literal=jwt-secret=$JWT_SECRET \
  --namespace=ai-platform
```

#### **Database Setup**

```bash
# Deploy PostgreSQL
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install postgres bitnami/postgresql \
  --set auth.postgresPassword=your-password \
  --set auth.database=ai_platform \
  --namespace=ai-platform

# Deploy Redis
helm install redis bitnami/redis \
  --set auth.password=your-redis-password \
  --namespace=ai-platform

# Deploy NATS
helm repo add nats https://nats-io.github.io/k8s/helm/charts/
helm install nats nats/nats \
  --namespace=ai-platform
```

#### **Application Deployment**

```bash
# Deploy API Gateway
kubectl apply -f k8s/api-gateway-deployment.yaml
kubectl apply -f k8s/api-gateway-service.yaml
kubectl apply -f k8s/api-gateway-ingress.yaml

# Deploy Orchestrator
kubectl apply -f k8s/orchestrator-deployment.yaml
kubectl apply -f k8s/orchestrator-service.yaml

# Deploy Router Service
kubectl apply -f k8s/router-deployment.yaml
kubectl apply -f k8s/router-service.yaml

# Deploy Realtime Service
kubectl apply -f k8s/realtime-deployment.yaml
kubectl apply -f k8s/realtime.yaml

# Deploy Analytics Service
kubectl apply -f k8s/analytics-deployment.yaml
kubectl apply -f k8s/analytics-service.yaml

# Deploy Billing Service
kubectl apply -f k8s/billing-deployment.yaml
kubectl apply -f k8s/billing-service.yaml
```

### **4. Autoscaling Setup**

```bash
# Deploy KEDA
helm repo add kedacore https://kedacore.github.io/charts
helm install keda kedacore/keda --namespace keda-system --create-namespace

# Deploy HPA configurations
kubectl apply -f k8s/autoscaling/hpa-configs.yaml

# Deploy KEDA ScaledObjects
kubectl apply -f k8s/autoscaling/keda-scaledobjects.yaml
```

### **5. Monitoring Setup**

```bash
# Deploy Prometheus
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace=monitoring \
  --create-namespace

# Deploy Grafana
kubectl apply -f k8s/monitoring/grafana-dashboards.yaml

# Deploy Jaeger
helm repo add jaegertracing https://jaegertracing.github.io/helm-charts
helm install jaeger jaegertracing/jaeger \
  --namespace=monitoring
```

## 🔍 **Health Checks and Monitoring**

### **Service Health Endpoints**

```bash
# Check API Gateway
curl http://localhost:8000/healthz

# Check Orchestrator
curl http://localhost:8001/healthz

# Check Router Service
curl http://localhost:8002/healthz

# Check Realtime Service
curl http://localhost:8003/healthz

# Check Analytics Service
curl http://localhost:8004/healthz

# Check Billing Service
curl http://localhost:8005/healthz
```

### **Health Check Script**

```bash
#!/bin/bash
# health-check.sh

SERVICES=(
  "api-gateway:8000"
  "orchestrator:8001"
  "router:8002"
  "realtime:8003"
  "analytics:8004"
  "billing:8005"
)

echo "🔍 Checking service health..."

for service in "${SERVICES[@]}"; do
  name=$(echo $service | cut -d: -f1)
  port=$(echo $service | cut -d: -f2)

  if curl -s -f http://localhost:$port/healthz > /dev/null; then
    echo "✅ $name is healthy"
  else
    echo "❌ $name is unhealthy"
  fi
done
```

### **Monitoring URLs**

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Jaeger**: http://localhost:16686
- **API Documentation**: http://localhost:8000/docs

## 🧪 **Testing Deployment**

### **1. Unit Tests**

```bash
# Run unit tests
make test-unit

# Run with coverage
make test-unit-coverage
```

### **2. Integration Tests**

```bash
# Run integration tests
make test-integration

# Run E2E tests
make test-e2e
```

### **3. Performance Tests**

```bash
# Run load tests
make test-performance

# Run Locust load tests
locust -f tests/performance/locustfile.py \
  --host=http://localhost:8000 \
  --users=100 \
  --spawn-rate=10 \
  --run-time=5m \
  --headless
```

### **4. Health Validation**

```bash
# Run health checks
make health-check

# Run full validation
make validate-deployment
```

## 🔄 **Deployment Strategies**

### **1. Rolling Deployment**

```bash
# Update deployment
kubectl set image deployment/api-gateway \
  api-gateway=ai-platform/api-gateway:v2.0.0

# Check rollout status
kubectl rollout status deployment/api-gateway

# Rollback if needed
kubectl rollout undo deployment/api-gateway
```

### **2. Blue-Green Deployment**

```bash
# Deploy green environment
kubectl apply -f k8s/green-deployment.yaml

# Switch traffic
kubectl patch service api-gateway \
  -p '{"spec":{"selector":{"version":"green"}}}'

# Cleanup blue environment
kubectl delete -f k8s/blue-deployment.yaml
```

### **3. Canary Deployment**

```bash
# Deploy canary version
kubectl apply -f k8s/canary-deployment.yaml

# Gradually increase traffic
kubectl apply -f k8s/canary-traffic-split.yaml

# Promote to production
kubectl apply -f k8s/production-deployment.yaml
```

## 🔐 **Security Configuration**

### **1. Network Policies**

```bash
# Apply network policies
kubectl apply -f k8s/security/network-policies.yaml

# Verify policies
kubectl get networkpolicies
```

### **2. Pod Security Policies**

```bash
# Apply security policies
kubectl apply -f k8s/security/pod-security-policies.yaml

# Verify policies
kubectl get psp
```

### **3. RBAC Configuration**

```bash
# Create service accounts
kubectl apply -f k8s/security/rbac.yaml

# Verify permissions
kubectl auth can-i get pods --as=system:serviceaccount:ai-platform:api-gateway
```

## 🚨 **Troubleshooting**

### **Common Issues**

#### **1. Service Not Starting**

```bash
# Check pod status
kubectl get pods

# Check pod logs
kubectl logs -f deployment/api-gateway

# Check events
kubectl get events --sort-by=.metadata.creationTimestamp
```

#### **2. Database Connection Issues**

```bash
# Check database connectivity
kubectl exec -it deployment/api-gateway -- psql $POSTGRES_URL

# Check Redis connectivity
kubectl exec -it deployment/api-gateway -- redis-cli -u $REDIS_URL ping

# Check NATS connectivity
kubectl exec -it deployment/api-gateway -- nats-server --help
```

#### **3. Performance Issues**

```bash
# Check resource usage
kubectl top pods
kubectl top nodes

# Check HPA status
kubectl get hpa

# Check KEDA status
kubectl get scaledobjects
```

### **Debug Commands**

```bash
# Get detailed pod information
kubectl describe pod <pod-name>

# Check service endpoints
kubectl get endpoints

# Check ingress status
kubectl get ingress

# Check configmaps and secrets
kubectl get configmaps
kubectl get secrets
```

## 📊 **Production Checklist**

### **Pre-Deployment**

- [ ] Environment variables configured
- [ ] Secrets properly managed
- [ ] Database migrations run
- [ ] Health checks configured
- [ ] Monitoring setup
- [ ] Security policies applied
- [ ] Backup strategy in place

### **Post-Deployment**

- [ ] All services healthy
- [ ] Load balancer configured
- [ ] SSL certificates installed
- [ ] Monitoring alerts configured
- [ ] Log aggregation working
- [ ] Performance benchmarks met
- [ ] Security scan passed

### **Ongoing Maintenance**

- [ ] Regular backups
- [ ] Security updates
- [ ] Performance monitoring
- [ ] Capacity planning
- [ ] Disaster recovery testing

## 📚 **Additional Resources**

- **[System Overview](SYSTEM_OVERVIEW.md)** - Architecture details
- **[Testing Guide](testing/GETTING_STARTED.md)** - Testing instructions
- **[Monitoring Guide](MONITORING_GUIDE.md)** - Observability setup
- **[Security Guide](SECURITY_GUIDE.md)** - Security best practices
- **[API Documentation](API_DOCUMENTATION.md)** - API reference

## 🆘 **Support**

For deployment issues:

1. Check the troubleshooting section above
2. Review service logs
3. Check monitoring dashboards
4. Consult the documentation
5. Contact the platform team

---

**🎉 Congratulations!** Your Multi-Tenant AIaaS Platform is now deployed and ready for production use!
