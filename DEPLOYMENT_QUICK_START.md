# 🚀 Quick Deployment Guide

## 📋 Prerequisites

- Google Cloud Platform account
- Google Cloud CLI installed
- Docker installed
- kubectl installed

## ⚡ Quick Start (5 minutes)

### 1. Setup GCP

```bash
# Clone your repository
git clone <your-repo-url>
cd multi-ai-agent

# Setup GCP project and cluster
./scripts/setup-gcp.sh your-project-id

# Follow the instructions to add secrets to CI/CD
```

### 2. Configure Secrets

```bash
# Update secrets in k8s/secrets.yaml
# Generate base64 encoded values:
echo -n "your-openai-key" | base64
echo -n "your-db-password" | base64

# Update the secrets file with your values
```

### 3. Build and Deploy

```bash
# Build and push images
./scripts/build-images.sh your-project-id

# Deploy to Kubernetes
kubectl apply -f k8s/

# Check deployment
kubectl get pods -n ai-chatbot
```

### 4. Verify Deployment

```bash
# Run health checks
./scripts/health-check.sh

# Get external IPs
kubectl get services -n ai-chatbot
```

## 🌐 Access Your Applications

| Service             | URL                    | Description            |
| ------------------- | ---------------------- | ---------------------- |
| **🤖 AI Chatbot**   | `http://<EXTERNAL-IP>` | Main chatbot interface |
| **👨‍💼 Admin Portal** | `http://<ADMIN-IP>`    | Admin dashboard        |
| **🔌 API Gateway**  | `http://<API-IP>:8000` | Backend API            |

## 🔧 Common Commands

```bash
# View logs
kubectl logs -f deployment/ai-chatbot -n ai-chatbot

# Scale deployment
kubectl scale deployment ai-chatbot --replicas=5 -n ai-chatbot

# Update image
kubectl set image deployment/ai-chatbot chatbot=gcr.io/your-project/ai-chatbot:new-tag -n ai-chatbot

# Delete deployment
kubectl delete -f k8s/
```

## 🆘 Troubleshooting

### Pod not starting

```bash
kubectl describe pod <pod-name> -n ai-chatbot
kubectl logs <pod-name> -n ai-chatbot
```

### Service not accessible

```bash
kubectl get services -n ai-chatbot
kubectl get ingress -n ai-chatbot
```

### Database connection issues

```bash
kubectl exec -it deployment/postgres -n ai-chatbot -- psql -U postgres -d ai_agent
```

## 📚 Next Steps

1. **Set up monitoring** - Configure Prometheus and Grafana
2. **Enable SSL** - Set up Let's Encrypt certificates
3. **Configure backup** - Set up automated database backups
4. **Set up alerts** - Configure monitoring alerts
5. **Optimize costs** - Review and optimize resource usage

For detailed instructions, see [CLOUD_DEPLOYMENT_GUIDE.md](CLOUD_DEPLOYMENT_GUIDE.md)
