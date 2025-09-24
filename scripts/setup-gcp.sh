#!/usr/bin/env bash
set -euo pipefail

# Setup Google Cloud Platform for AI Chatbot deployment
PROJECT_ID=${1:-"your-ai-chatbot-project"}
REGION=${2:-"us-central1"}
ZONE=${3:-"us-central1-a"}

echo "🚀 Setting up Google Cloud Platform for AI Chatbot..."

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Google Cloud CLI is not installed. Please install it first:"
    echo "   curl https://sdk.cloud.google.com | bash"
    echo "   exec -l \$SHELL"
    exit 1
fi

# Authenticate
echo "🔐 Authenticating with Google Cloud..."
gcloud auth login

# Set project
echo "📋 Setting project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

# Create project if it doesn't exist
echo "📦 Creating project if it doesn't exist..."
gcloud projects create $PROJECT_ID --name="AI Chatbot Project" || echo "Project already exists"

# Enable required APIs
echo "🔌 Enabling required APIs..."
gcloud services enable container.googleapis.com
gcloud services enable compute.googleapis.com
gcloud services enable sqladmin.googleapis.com
gcloud services enable redis.googleapis.com
gcloud services enable monitoring.googleapis.com
gcloud services enable logging.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Create GKE cluster
echo "🎛️  Creating GKE cluster..."
gcloud container clusters create ai-chatbot-cluster \
  --zone=$ZONE \
  --num-nodes=3 \
  --machine-type=e2-standard-2 \
  --enable-autoscaling \
  --min-nodes=1 \
  --max-nodes=10 \
  --enable-autorepair \
  --enable-autoupgrade \
  --disk-size=20GB \
  --disk-type=pd-standard \
  --enable-ip-alias \
  --network=default \
  --subnetwork=default \
  --enable-network-policy

# Get credentials
echo "🔑 Getting cluster credentials..."
gcloud container clusters get-credentials ai-chatbot-cluster --zone=$ZONE

# Create namespace
echo "📁 Creating Kubernetes namespace..."
kubectl create namespace ai-chatbot || echo "Namespace already exists"

# Create Cloud SQL instance
echo "🗄️  Creating Cloud SQL instance..."
gcloud sql instances create ai-chatbot-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=$REGION \
  --storage-size=10GB \
  --storage-type=SSD \
  --backup-start-time=03:00 \
  --enable-bin-log \
  --maintenance-window-day=SUN \
  --maintenance-window-hour=04 \
  --maintenance-release-channel=production \
  --deletion-protection || echo "Database instance already exists"

# Create database and user
echo "👤 Creating database and user..."
gcloud sql databases create ai_agent --instance=ai-chatbot-db || echo "Database already exists"
gcloud sql users create chatbot-user --instance=ai-chatbot-db --password=SecurePassword123! || echo "User already exists"

# Create Redis instance
echo "🔴 Creating Redis instance..."
gcloud redis instances create ai-chatbot-cache \
  --size=1 \
  --region=$REGION \
  --redis-version=redis_7_0 \
  --tier=basic \
  --network=default || echo "Redis instance already exists"

# Configure Docker for GCR
echo "🐳 Configuring Docker for Google Container Registry..."
gcloud auth configure-docker

# Create service account for CI/CD
echo "🔧 Creating service account for CI/CD..."
gcloud iam service-accounts create ai-chatbot-ci \
  --display-name="AI Chatbot CI/CD Service Account" \
  --description="Service account for AI Chatbot CI/CD pipeline" || echo "Service account already exists"

# Grant necessary permissions
echo "🔐 Granting permissions to service account..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:ai-chatbot-ci@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/container.developer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:ai-chatbot-ci@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:ai-chatbot-ci@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/cloudbuild.builds.builder"

# Create and download service account key
echo "🔑 Creating service account key..."
gcloud iam service-accounts keys create gcp-key.json \
  --iam-account=ai-chatbot-ci@$PROJECT_ID.iam.gserviceaccount.com

echo "✅ GCP setup completed!"
echo ""
echo "📋 Next steps:"
echo "1. Add the service account key to your CI/CD secrets:"
echo "   cat gcp-key.json | base64 -w 0"
echo ""
echo "2. Update your environment variables:"
echo "   export PROJECT_ID=$PROJECT_ID"
echo "   export REGION=$REGION"
echo "   export ZONE=$ZONE"
echo ""
echo "3. Build and push your images:"
echo "   ./scripts/build-images.sh $PROJECT_ID"
echo ""
echo "4. Deploy to Kubernetes:"
echo "   kubectl apply -f k8s/"
echo ""
echo "5. Run health checks:"
echo "   ./scripts/health-check.sh"
echo ""
echo "🔒 Remember to keep your service account key secure!"
