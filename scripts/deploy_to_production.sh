#!/bin/bash

# Production Deployment Script for Multi-AI-Agent Platform
# This script automates the complete deployment process to production

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="multi-ai-agent-prod"
DOMAIN="${DOMAIN:-your-domain.com}"
REGISTRY="${REGISTRY:-your-registry.com}"
TAG="${TAG:-latest}"
ENVIRONMENT="${ENVIRONMENT:-production}"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check required tools
    local required_tools=("kubectl" "docker" "helm" "python3" "curl")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "$tool is not installed or not in PATH"
            exit 1
        fi
    done
    
    # Check Kubernetes connectivity
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    # Check Docker connectivity
    if ! docker info &> /dev/null; then
        log_error "Cannot connect to Docker daemon"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Validate configuration
validate_config() {
    log_info "Validating configuration..."
    
    if [[ -z "$DOMAIN" || "$DOMAIN" == "your-domain.com" ]]; then
        log_error "DOMAIN environment variable must be set to your actual domain"
        exit 1
    fi
    
    if [[ -z "$REGISTRY" || "$REGISTRY" == "your-registry.com" ]]; then
        log_error "REGISTRY environment variable must be set to your actual registry"
        exit 1
    fi
    
    # Check if config file exists
    if [[ ! -f "k8s/production/config.yaml" ]]; then
        log_error "Production configuration file not found: k8s/production/config.yaml"
        exit 1
    fi
    
    log_success "Configuration validation passed"
}

# Create namespace and secrets
setup_namespace() {
    log_info "Setting up namespace and secrets..."
    
    # Create namespace
    kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
    
    # Create secrets (you should replace these with actual values)
    kubectl create secret generic db-credentials \
        --from-literal=postgres-password='your-secure-password' \
        --from-literal=redis-password='your-redis-password' \
        --namespace="$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -
    
    kubectl create secret generic api-keys \
        --from-literal=openai-api-key='your-openai-key' \
        --from-literal=jwt-secret='your-jwt-secret' \
        --namespace="$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -
    
    log_success "Namespace and secrets setup completed"
}

# Build and push containers
build_and_push_containers() {
    log_info "Building and pushing containers..."
    
    local services=(
        "api-gateway"
        "orchestrator"
        "router_service"
        "realtime-service"
        "analytics_service"
        "billing-service"
        "ingestion"
        "chat-adapters"
        "tenant-service"
        "admin-portal"
        "eval-service"
    )
    
    for service in "${services[@]}"; do
        log_info "Building $service..."
        
        # Build container
        docker build -t "$REGISTRY/multi-ai-agent-$service:$TAG" "apps/$service/"
        
        # Push container
        docker push "$REGISTRY/multi-ai-agent-$service:$TAG"
        
        log_success "$service built and pushed successfully"
    done
    
    log_success "All containers built and pushed"
}

# Deploy to Kubernetes
deploy_to_kubernetes() {
    log_info "Deploying to Kubernetes..."
    
    # Update image tags in deployment files
    find k8s/production/manifests -name "*.yaml" -exec sed -i "s|your-registry.com|$REGISTRY|g" {} \;
    find k8s/production/manifests -name "*.yaml" -exec sed -i "s|your-domain.com|$DOMAIN|g" {} \;
    find k8s/production/manifests -name "*.yaml" -exec sed -i "s|latest|$TAG|g" {} \;
    
    # Deploy services in dependency order
    local deployment_order=(
        "configmaps.yaml"
        "secrets.yaml"
        "api-gateway/"
        "orchestrator/"
        "router_service/"
        "realtime-service/"
        "analytics_service/"
        "billing-service/"
        "ingestion/"
        "chat-adapters/"
        "tenant-service/"
        "admin-portal/"
        "eval-service/"
        "ingress/"
    )
    
    for item in "${deployment_order[@]}"; do
        log_info "Deploying $item..."
        
        if [[ "$item" == *.yaml ]]; then
            kubectl apply -f "k8s/production/manifests/$item" -n "$NAMESPACE"
        else
            kubectl apply -f "k8s/production/manifests/$item" -n "$NAMESPACE"
        fi
        
        if [[ $? -eq 0 ]]; then
            log_success "$item deployed successfully"
        else
            log_warning "$item deployment had issues (may be expected for some resources)"
        fi
    done
    
    log_success "Kubernetes deployment completed"
}

# Wait for deployments to be ready
wait_for_deployments() {
    log_info "Waiting for deployments to be ready..."
    
    local deployments
    deployments=$(kubectl get deployments -n "$NAMESPACE" -o jsonpath='{.items[*].metadata.name}')
    
    for deployment in $deployments; do
        log_info "Waiting for $deployment to be ready..."
        
        kubectl rollout status deployment "$deployment" -n "$NAMESPACE" --timeout=600s
        
        if [[ $? -eq 0 ]]; then
            log_success "$deployment is ready"
        else
            log_error "$deployment failed to become ready"
            exit 1
        fi
    done
    
    log_success "All deployments are ready"
}

# Setup monitoring
setup_monitoring() {
    log_info "Setting up monitoring..."
    
    # Deploy monitoring stack
    local monitoring_components=(
        "prometheus/"
        "grafana/"
        "jaeger/"
        "alertmanager/"
    )
    
    for component in "${monitoring_components[@]}"; do
        log_info "Deploying monitoring component: $component"
        kubectl apply -f "k8s/monitoring/$component"
    done
    
    # Import Grafana dashboards
    log_info "Importing Grafana dashboards..."
    # In production, you would use Grafana API to import dashboards
    # For now, we'll just log the action
    log_info "Dashboard import completed (mock)"
    
    log_success "Monitoring setup completed"
}

# Run validation tests
run_validation_tests() {
    log_info "Running validation tests..."
    
    # Health check validation
    log_info "Running health checks..."
    python3 scripts/health_check_validation.py --namespace="$NAMESPACE" --domain="$DOMAIN"
    
    # Load testing (optional)
    if [[ "${RUN_LOAD_TESTS:-false}" == "true" ]]; then
        log_info "Running load tests..."
        python3 scripts/production_load_test.py --domain="$DOMAIN"
    fi
    
    # End-to-end testing
    log_info "Running end-to-end tests..."
    python3 -m pytest tests/e2e/test_production_e2e.py --env=production --domain="$DOMAIN"
    
    log_success "Validation tests completed"
}

# Setup user experience monitoring
setup_user_experience_monitoring() {
    log_info "Setting up user experience monitoring..."
    
    # Deploy user experience metrics
    kubectl apply -f "k8s/production/user-experience-metrics.yaml" -n "$NAMESPACE"
    
    # Start user experience monitor
    log_info "Starting user experience monitor..."
    nohup python3 scripts/user_experience_monitor.py > logs/user_experience_monitor.log 2>&1 &
    
    log_success "User experience monitoring setup completed"
}

# Enable production traffic
enable_production_traffic() {
    log_info "Enabling production traffic..."
    
    # Update ingress to enable production traffic
    kubectl patch ingress api-gateway -n "$NAMESPACE" \
        -p "{\"spec\":{\"rules\":[{\"host\":\"$DOMAIN\"}]}}"
    
    log_success "Production traffic enabled"
}

# Post-deployment monitoring
post_deployment_monitoring() {
    log_info "Setting up post-deployment monitoring..."
    
    # Start monitoring processes
    log_info "Starting monitoring processes..."
    
    # Setup alerts
    kubectl apply -f "k8s/monitoring/alerts/production-alerts.yaml"
    
    log_success "Post-deployment monitoring setup completed"
}

# Generate deployment report
generate_deployment_report() {
    log_info "Generating deployment report..."
    
    local report_file="deployment_report_$(date +%Y%m%d_%H%M%S).json"
    
    cat > "$report_file" << EOF
{
    "deployment": {
        "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
        "environment": "$ENVIRONMENT",
        "namespace": "$NAMESPACE",
        "domain": "$DOMAIN",
        "registry": "$REGISTRY",
        "tag": "$TAG"
    },
    "services": {
        "deployed": $(kubectl get deployments -n "$NAMESPACE" -o json | jq '.items | length'),
        "ready": $(kubectl get deployments -n "$NAMESPACE" -o json | jq '[.items[] | select(.status.readyReplicas == .status.replicas)] | length')
    },
    "pods": {
        "total": $(kubectl get pods -n "$NAMESPACE" --no-headers | wc -l),
        "running": $(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase=Running --no-headers | wc -l),
        "pending": $(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase=Pending --no-headers | wc -l),
        "failed": $(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase=Failed --no-headers | wc -l)
    },
    "ingress": {
        "hosts": $(kubectl get ingress -n "$NAMESPACE" -o json | jq '.items[].spec.rules[].host')
    },
    "monitoring": {
        "prometheus": $(kubectl get pods -n monitoring --field-selector=status.phase=Running --no-headers | wc -l),
        "grafana": $(kubectl get pods -n monitoring --field-selector=status.phase=Running --no-headers | wc -l),
        "jaeger": $(kubectl get pods -n monitoring --field-selector=status.phase=Running --no-headers | wc -l)
    }
}
EOF
    
    log_success "Deployment report generated: $report_file"
}

# Cleanup function
cleanup() {
    log_info "Cleaning up..."
    
    # Kill background processes
    pkill -f "user_experience_monitor.py" || true
    
    log_success "Cleanup completed"
}

# Main deployment function
main() {
    log_info "Starting production deployment for Multi-AI-Agent Platform"
    log_info "Domain: $DOMAIN"
    log_info "Registry: $REGISTRY"
    log_info "Tag: $TAG"
    log_info "Namespace: $NAMESPACE"
    
    # Set trap for cleanup on exit
    trap cleanup EXIT
    
    # Execute deployment steps
    check_prerequisites
    validate_config
    setup_namespace
    build_and_push_containers
    deploy_to_kubernetes
    wait_for_deployments
    setup_monitoring
    run_validation_tests
    setup_user_experience_monitoring
    enable_production_traffic
    post_deployment_monitoring
    generate_deployment_report
    
    log_success "🎉 Production deployment completed successfully!"
    log_info "Your Multi-AI-Agent Platform is now live at: https://$DOMAIN"
    log_info "Monitor your deployment at: https://grafana.$DOMAIN"
    log_info "View logs at: https://jaeger.$DOMAIN"
}

# Help function
show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy Multi-AI-Agent Platform to production

Environment Variables:
    DOMAIN         Your production domain (required)
    REGISTRY       Your container registry (required)
    TAG            Container image tag (default: latest)
    ENVIRONMENT    Environment name (default: production)
    RUN_LOAD_TESTS Run load tests (default: false)

Options:
    -h, --help     Show this help message
    -d, --domain   Set production domain
    -r, --registry Set container registry
    -t, --tag      Set container image tag

Examples:
    $0 --domain=myapp.com --registry=myregistry.com
    DOMAIN=myapp.com REGISTRY=myregistry.com $0
    $0 -d myapp.com -r myregistry.com -t v1.0.0

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -d|--domain)
            DOMAIN="$2"
            shift 2
            ;;
        -r|--registry)
            REGISTRY="$2"
            shift 2
            ;;
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Run main function
main
