# 🚀 Cloud Deployment Guide for AI Chatbot System

## 📋 Table of Contents

1. [Overview](#overview)
2. [Pre-Deployment Testing](#pre-deployment-testing)
3. [Cloud Provider Selection](#cloud-provider-selection)
4. [Infrastructure Setup](#infrastructure-setup)
5. [Container Orchestration](#container-orchestration)
6. [Database & Storage](#database--storage)
7. [Networking & Security](#networking--security)
8. [CI/CD Pipeline](#cicd-pipeline)
9. [Monitoring & Observability](#monitoring--observability)
10. [Production Deployment](#production-deployment)
11. [Scaling & Performance](#scaling--performance)
12. [Backup & Disaster Recovery](#backup--disaster-recovery)
13. [Cost Optimization](#cost-optimization)
14. [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

This guide covers deploying your AI chatbot microservices architecture to the cloud, including:

- **Frontend**: React chatbot UI, admin portal, web frontend
- **Backend**: API Gateway, model gateway, retrieval service, tools service
- **Control Plane**: Config service, policy adapter, usage metering
- **Infrastructure**: PostgreSQL, Redis, NATS, monitoring

---

## 🧪 Pre-Deployment Testing

### 1. Local Testing Checklist

```bash
# 1. Run all tests
./scripts/run_p0_subset.sh
pytest -q -m p0

# 2. Test API endpoints
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "Test question"}'

# 3. Test frontend applications
curl -I http://localhost:3001  # Chatbot UI
curl -I http://localhost:3000  # Web frontend
curl -I http://localhost:8099  # Admin portal

# 4. Load testing
docker run --rm -it --network host loadimpact/k6 run - <(cat <<EOF
import http from 'k6/http';
import { check } from 'k6';

export default function() {
  const response = http.post('http://localhost:8000/ask',
    JSON.stringify({query: 'Load test question'}),
    { headers: { 'Content-Type': 'application/json' } }
  );
  check(response, {
    'status is 200': (r) => r.status === 200,
    'response time < 5000ms': (r) => r.timings.duration < 5000,
  });
}
EOF)
```

### 2. Security Testing

```bash
# Scan containers for vulnerabilities
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image multi-ai-agent-ai-chatbot

# Test API security
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "<script>alert(\"xss\")</script>"}'
```

### 3. Performance Testing

```bash
# Memory usage test
docker stats

# Database connection test
docker exec multi-ai-agent-postgres-1 psql -U postgres -d ai_agent -c "SELECT 1"

# Redis connection test
docker exec multi-ai-agent-redis-1 redis-cli ping
```

---

## ☁️ Cloud Provider Selection

### Recommended Options:

| Provider           | Pros                                 | Cons              | Best For                      |
| ------------------ | ------------------------------------ | ----------------- | ----------------------------- |
| **AWS**            | Mature services, extensive ecosystem | Complex pricing   | Enterprise, complex workloads |
| **Google Cloud**   | Excellent AI/ML integration          | Smaller ecosystem | AI-focused applications       |
| **Azure**          | Microsoft integration                | Learning curve    | Microsoft shops               |
| **DigitalOcean**   | Simple pricing, good docs            | Limited services  | Startups, simple deployments  |
| **Railway/Render** | Easy deployment                      | Less control      | Quick prototyping             |

### 🎯 Recommended: **Google Cloud Platform (GCP)**

**Why GCP?**

- Excellent AI/ML services integration
- Strong Kubernetes support (GKE)
- Good pricing for small to medium workloads
- Excellent documentation and tools

---

## 🏗️ Infrastructure Setup

### 1. GCP Project Setup

```bash
# Install Google Cloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Authenticate and create project
gcloud auth login
gcloud projects create your-ai-chatbot-project
gcloud config set project your-ai-chatbot-project

# Enable required APIs
gcloud services enable container.googleapis.com
gcloud services enable compute.googleapis.com
gcloud services enable sqladmin.googleapis.com
gcloud services enable redis.googleapis.com
gcloud services enable monitoring.googleapis.com
```

### 2. Container Registry Setup

```bash
# Configure Docker for GCP
gcloud auth configure-docker

# Build and push images
docker build -t gcr.io/your-project/ai-chatbot ./frontend/chatbot-ui
docker push gcr.io/your-project/ai-chatbot

docker build -t gcr.io/your-project/api-gateway ./apps/data-plane/api-gateway
docker push gcr.io/your-project/api-gateway

# Tag and push all services
for service in ai-chatbot api-gateway model-gateway retrieval-service; do
  docker tag multi-ai-agent-$service:latest gcr.io/your-project/$service:latest
  docker push gcr.io/your-project/$service:latest
done
```

---

## 🎛️ Container Orchestration

### 1. Google Kubernetes Engine (GKE) Setup

```bash
# Create GKE cluster
gcloud container clusters create ai-chatbot-cluster \
  --num-nodes=3 \
  --machine-type=e2-standard-2 \
  --zone=us-central1-a \
  --enable-autoscaling \
  --min-nodes=1 \
  --max-nodes=10

# Get credentials
gcloud container clusters get-credentials ai-chatbot-cluster --zone=us-central1-a
```

### 2. Kubernetes Manifests

Create `k8s/namespace.yaml`:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ai-chatbot
```

Create `k8s/configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: ai-chatbot
data:
  OPENAI_API_KEY: "your-openai-key"
  DATABASE_URL: "postgresql://postgres:password@postgres-service:5432/ai_agent"
  REDIS_URL: "redis://redis-service:6379"
  NATS_URL: "nats://nats-service:4222"
```

Create `k8s/postgres-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: ai-chatbot
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
        - name: postgres
          image: postgres:15
          env:
            - name: POSTGRES_DB
              value: ai_agent
            - name: POSTGRES_USER
              value: postgres
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: postgres-secret
                  key: password
          ports:
            - containerPort: 5432
          volumeMounts:
            - name: postgres-storage
              mountPath: /var/lib/postgresql/data
      volumes:
        - name: postgres-storage
          persistentVolumeClaim:
            claimName: postgres-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: postgres-service
  namespace: ai-chatbot
spec:
  selector:
    app: postgres
  ports:
    - port: 5432
      targetPort: 5432
```

Create `k8s/chatbot-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-chatbot
  namespace: ai-chatbot
spec:
  replicas: 2
  selector:
    matchLabels:
      app: ai-chatbot
  template:
    metadata:
      labels:
        app: ai-chatbot
    spec:
      containers:
        - name: chatbot
          image: gcr.io/your-project/ai-chatbot:latest
          ports:
            - containerPort: 3000
          env:
            - name: REACT_APP_API_URL
              value: "http://api-gateway-service:8000"
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: ai-chatbot-service
  namespace: ai-chatbot
spec:
  selector:
    app: ai-chatbot
  ports:
    - port: 80
      targetPort: 3000
  type: LoadBalancer
```

### 3. Deploy to Kubernetes

```bash
# Apply all manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/postgres-deployment.yaml
kubectl apply -f k8s/chatbot-deployment.yaml

# Check deployment status
kubectl get pods -n ai-chatbot
kubectl get services -n ai-chatbot

# Get external IP
kubectl get service ai-chatbot-service -n ai-chatbot
```

---

## 🗄️ Database & Storage

### 1. Managed PostgreSQL (Cloud SQL)

```bash
# Create Cloud SQL instance
gcloud sql instances create ai-chatbot-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --storage-size=10GB \
  --storage-type=SSD

# Create database and user
gcloud sql databases create ai_agent --instance=ai-chatbot-db
gcloud sql users create chatbot-user --instance=ai-chatbot-db --password=secure-password

# Get connection string
gcloud sql instances describe ai-chatbot-db --format="value(connectionName)"
```

### 2. Managed Redis (Memorystore)

```bash
# Create Redis instance
gcloud redis instances create ai-chatbot-cache \
  --size=1 \
  --region=us-central1 \
  --redis-version=redis_7_0

# Get connection details
gcloud redis instances describe ai-chatbot-cache --region=us-central1
```

### 3. Persistent Volumes

```yaml
# k8s/pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc
  namespace: ai-chatbot
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 20Gi
  storageClassName: standard-rwo
```

---

## 🔒 Networking & Security

### 1. Ingress Configuration

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ai-chatbot-ingress
  namespace: ai-chatbot
  annotations:
    kubernetes.io/ingress.class: "gce"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
    - hosts:
        - chatbot.yourdomain.com
        - admin.yourdomain.com
      secretName: chatbot-tls
  rules:
    - host: chatbot.yourdomain.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: ai-chatbot-service
                port:
                  number: 80
    - host: admin.yourdomain.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: admin-portal-service
                port:
                  number: 80
```

### 2. Network Policies

```yaml
# k8s/network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: ai-chatbot-network-policy
  namespace: ai-chatbot
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              name: ai-chatbot
    - to: []
      ports:
        - protocol: TCP
          port: 5432 # PostgreSQL
        - protocol: TCP
          port: 6379 # Redis
        - protocol: TCP
          port: 4222 # NATS
```

### 3. Secrets Management

```bash
# Create secrets
kubectl create secret generic postgres-secret \
  --from-literal=password=secure-password \
  -n ai-chatbot

kubectl create secret generic api-secrets \
  --from-literal=openai-api-key=your-openai-key \
  --from-literal=jwt-secret=your-jwt-secret \
  -n ai-chatbot
```

---

## 🔄 CI/CD Pipeline

### 1. GitHub Actions Workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to GCP

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  PROJECT_ID: your-ai-chatbot-project
  GKE_CLUSTER: ai-chatbot-cluster
  GKE_ZONE: us-central1-a
  DEPLOYMENT_NAME: ai-chatbot

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run tests
        run: |
          docker-compose -f docker-compose.local.yml up -d
          ./scripts/run_p0_subset.sh

      - name: Security scan
        run: |
          docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
            aquasec/trivy image multi-ai-agent-ai-chatbot

  build-and-deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'

    steps:
      - uses: actions/checkout@v3

      - name: Setup Google Cloud CLI
        uses: google-github-actions/setup-gcloud@v1
        with:
          service_account_key: ${{ secrets.GCP_SA_KEY }}
          project_id: ${{ env.PROJECT_ID }}

      - name: Configure Docker
        run: gcloud auth configure-docker

      - name: Build and push images
        run: |
          for service in ai-chatbot api-gateway model-gateway; do
            docker build -t gcr.io/$PROJECT_ID/$service:$GITHUB_SHA ./apps/data-plane/$service
            docker push gcr.io/$PROJECT_ID/$service:$GITHUB_SHA
          done

      - name: Deploy to GKE
        run: |
          gcloud container clusters get-credentials $GKE_CLUSTER --zone=$GKE_ZONE
          kubectl set image deployment/ai-chatbot chatbot=gcr.io/$PROJECT_ID/ai-chatbot:$GITHUB_SHA -n ai-chatbot
          kubectl rollout status deployment/ai-chatbot -n ai-chatbot
```

### 2. Deployment Scripts

Create `scripts/deploy.sh`:

```bash
#!/bin/bash
set -e

PROJECT_ID=${1:-"your-ai-chatbot-project"}
ENVIRONMENT=${2:-"staging"}

echo "🚀 Deploying to $ENVIRONMENT environment..."

# Build and push images
./scripts/build-images.sh $PROJECT_ID

# Deploy to Kubernetes
kubectl apply -f k8s/$ENVIRONMENT/

# Wait for deployment
kubectl rollout status deployment/ai-chatbot -n ai-chatbot

# Run health checks
./scripts/health-check.sh

echo "✅ Deployment completed!"
```

---

## 📊 Monitoring & Observability

### 1. Prometheus & Grafana Setup

```yaml
# monitoring/prometheus.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: ai-chatbot
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
    scrape_configs:
    - job_name: 'ai-chatbot'
      static_configs:
      - targets: ['ai-chatbot-service:80']
    - job_name: 'api-gateway'
      static_configs:
      - targets: ['api-gateway-service:8000']
```

### 2. Logging with ELK Stack

```yaml
# logging/elasticsearch.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: elasticsearch
  namespace: ai-chatbot
spec:
  replicas: 1
  selector:
    matchLabels:
      app: elasticsearch
  template:
    metadata:
      labels:
        app: elasticsearch
    spec:
      containers:
        - name: elasticsearch
          image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
          env:
            - name: discovery.type
              value: single-node
          ports:
            - containerPort: 9200
```

### 3. Health Checks & Alerts

```yaml
# monitoring/health-check.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: health-check-script
  namespace: ai-chatbot
data:
  health-check.sh: |
    #!/bin/bash
    SERVICES=("ai-chatbot" "api-gateway" "model-gateway")

    for service in "${SERVICES[@]}"; do
      if ! curl -f http://$service-service/healthz; then
        echo "❌ $service is unhealthy"
        exit 1
      fi
    done

    echo "✅ All services are healthy"
```

---

## 🚀 Production Deployment

### 1. Blue-Green Deployment

```bash
# Deploy to blue environment
kubectl apply -f k8s/blue/

# Test blue environment
kubectl port-forward service/ai-chatbot-blue 3001:80

# Switch traffic to blue
kubectl patch service ai-chatbot-service -p '{"spec":{"selector":{"version":"blue"}}}'

# Deploy to green environment
kubectl apply -f k8s/green/

# Test green environment
kubectl port-forward service/ai-chatbot-green 3002:80

# Switch traffic to green
kubectl patch service ai-chatbot-service -p '{"spec":{"selector":{"version":"green"}}}'
```

### 2. Canary Deployment

```yaml
# k8s/canary-deployment.yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: ai-chatbot-rollout
  namespace: ai-chatbot
spec:
  replicas: 5
  strategy:
    canary:
      steps:
        - setWeight: 20
        - pause: { duration: 10m }
        - setWeight: 40
        - pause: { duration: 10m }
        - setWeight: 60
        - pause: { duration: 10m }
        - setWeight: 80
        - pause: { duration: 10m }
  selector:
    matchLabels:
      app: ai-chatbot
  template:
    metadata:
      labels:
        app: ai-chatbot
    spec:
      containers:
        - name: chatbot
          image: gcr.io/your-project/ai-chatbot:latest
          ports:
            - containerPort: 3000
```

### 3. Production Checklist

```bash
# 1. Resource limits set
kubectl get pods -n ai-chatbot -o jsonpath='{.items[*].spec.containers[*].resources}'

# 2. Health checks configured
kubectl get deployments -n ai-chatbot -o yaml | grep -A 5 -B 5 readinessProbe

# 3. Secrets properly configured
kubectl get secrets -n ai-chatbot

# 4. Network policies applied
kubectl get networkpolicies -n ai-chatbot

# 5. Monitoring configured
kubectl get pods -n monitoring

# 6. Backup configured
gcloud sql backups list --instance=ai-chatbot-db

# 7. SSL certificates
kubectl get certificates -n ai-chatbot

# 8. Load balancing
kubectl get ingress -n ai-chatbot
```

---

## 📈 Scaling & Performance

### 1. Horizontal Pod Autoscaler

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ai-chatbot-hpa
  namespace: ai-chatbot
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ai-chatbot
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

### 2. Vertical Pod Autoscaler

```yaml
# k8s/vpa.yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: ai-chatbot-vpa
  namespace: ai-chatbot
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ai-chatbot
  updatePolicy:
    updateMode: "Auto"
```

### 3. Performance Testing

```bash
# Load testing with k6
docker run --rm -i loadimpact/k6 run - <(cat <<EOF
import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  stages: [
    { duration: '2m', target: 100 },
    { duration: '5m', target: 100 },
    { duration: '2m', target: 200 },
    { duration: '5m', target: 200 },
    { duration: '2m', target: 0 },
  ],
};

export default function() {
  let response = http.post('https://chatbot.yourdomain.com/ask',
    JSON.stringify({query: 'Performance test question'}),
    { headers: { 'Content-Type': 'application/json' } }
  );
  check(response, {
    'status is 200': (r) => r.status === 200,
    'response time < 5000ms': (r) => r.timings.duration < 5000,
  });
  sleep(1);
}
EOF)
```

---

## 💾 Backup & Disaster Recovery

### 1. Database Backup

```bash
# Automated backup script
#!/bin/bash
BACKUP_NAME="ai-chatbot-backup-$(date +%Y%m%d-%H%M%S)"

# Create Cloud SQL backup
gcloud sql backups create --instance=ai-chatbot-db --description="$BACKUP_NAME"

# Backup to Cloud Storage
gcloud sql export sql ai-chatbot-db gs://your-backup-bucket/$BACKUP_NAME.sql \
  --database=ai_agent
```

### 2. Disaster Recovery Plan

```bash
# 1. Restore database
gcloud sql backups restore BACKUP_ID --restore-instance=ai-chatbot-db

# 2. Restore from Cloud Storage
gcloud sql import sql ai-chatbot-db gs://your-backup-bucket/backup.sql

# 3. Restore Kubernetes resources
kubectl apply -f k8s/backup/

# 4. Verify recovery
./scripts/health-check.sh
```

---

## 💰 Cost Optimization

### 1. Resource Optimization

```yaml
# Optimized resource requests
resources:
  requests:
    memory: "128Mi"
    cpu: "100m"
  limits:
    memory: "256Mi"
    cpu: "200m"
```

### 2. Auto-scaling Configuration

```yaml
# Cost-effective autoscaling
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: cost-optimized-hpa
spec:
  minReplicas: 1 # Minimum for cost
  maxReplicas: 5 # Reasonable maximum
  targetCPUUtilizationPercentage: 80 # Higher threshold
```

### 3. Spot Instances

```yaml
# Use spot instances for non-critical workloads
apiVersion: v1
kind: NodePool
spec:
  config:
    machineType: e2-standard-2
    spot: true # Use spot instances
```

---

## 🔧 Troubleshooting

### Common Issues & Solutions

#### 1. Pod CrashLoopBackOff

```bash
# Check pod logs
kubectl logs -f deployment/ai-chatbot -n ai-chatbot

# Check pod description
kubectl describe pod <pod-name> -n ai-chatbot

# Common fixes:
# - Check environment variables
# - Verify image exists
# - Check resource limits
```

#### 2. Database Connection Issues

```bash
# Test database connectivity
kubectl run -it --rm debug --image=postgres:15 --restart=Never -- \
  psql -h postgres-service -U postgres -d ai_agent

# Check database logs
kubectl logs deployment/postgres -n ai-chatbot
```

#### 3. Service Discovery Issues

```bash
# Test service connectivity
kubectl run -it --rm debug --image=busybox --restart=Never -- \
  nslookup api-gateway-service

# Check service endpoints
kubectl get endpoints -n ai-chatbot
```

#### 4. Performance Issues

```bash
# Check resource usage
kubectl top pods -n ai-chatbot
kubectl top nodes

# Check HPA status
kubectl get hpa -n ai-chatbot

# Analyze slow queries
kubectl exec -it deployment/postgres -n ai-chatbot -- \
  psql -U postgres -d ai_agent -c "SELECT * FROM pg_stat_activity;"
```

---

## 📚 Additional Resources

### Documentation Links

- [Google Cloud Platform Documentation](https://cloud.google.com/docs)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Prometheus Monitoring](https://prometheus.io/docs/)
- [Grafana Dashboards](https://grafana.com/grafana/dashboards/)

### Tools & Utilities

- **Monitoring**: Prometheus, Grafana, Google Cloud Monitoring
- **Logging**: ELK Stack, Google Cloud Logging
- **CI/CD**: GitHub Actions, Google Cloud Build
- **Security**: Trivy, Falco, Google Cloud Security Command Center
- **Performance**: k6, JMeter, Google Cloud Profiler

### Support Channels

- [Google Cloud Support](https://cloud.google.com/support)
- [Kubernetes Community](https://kubernetes.io/community/)
- [Stack Overflow](https://stackoverflow.com/questions/tagged/kubernetes)
- [GitHub Issues](https://github.com/your-repo/issues)

---

## 🎉 Conclusion

This guide provides a comprehensive approach to deploying your AI chatbot system to the cloud. Remember to:

1. **Start small** - Begin with a minimal deployment and scale up
2. **Monitor everything** - Set up comprehensive monitoring from day one
3. **Test thoroughly** - Use automated testing at every stage
4. **Plan for failure** - Implement proper backup and disaster recovery
5. **Optimize costs** - Monitor and optimize resource usage regularly

For questions or issues, refer to the troubleshooting section or reach out to the community support channels.

**Happy deploying! 🚀**
