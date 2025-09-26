#!/bin/bash

# Repository Splitting Script for Multi-AI-Agent Platform
# This script splits the monorepo into individual service repositories

set -e

# Configuration
MONOREPO_URL="https://github.com/your-org/multi-ai-agent.git"
ORG_NAME="your-org"
BASE_DIR="/tmp/repo-split"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Data Plane Services
DATA_PLANE_SERVICES=(
    "api-gateway"
    "model-gateway"
    "orchestrator"
    "router-service"
    "realtime-gateway"
    "ingestion-service"
    "analytics-service"
    "retrieval-service"
    "tools-service"
    "memory-service"
    "chat-adapters"
    "semantic-cache-service"
    "event-relay-service"
    "migration-runner"
    "agents-service"
    "eval-service"
    "mcp-rag"
)

# Control Plane Services
CONTROL_PLANE_SERVICES=(
    "config-service"
    "feature-flags-service"
    "registry-service"
    "policy-adapter"
    "usage-metering"
    "audit-log"
    "notification-service"
    "tenant-service"
    "capacity-monitor"
    "billing-service"
)

echo -e "${BLUE}🚀 Multi-AI-Agent Repository Splitting Script${NC}"
echo "================================================"

# Check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}📋 Checking prerequisites...${NC}"
    
    # Check if git filter-repo is installed
    if ! command -v git-filter-repo &> /dev/null; then
        echo -e "${RED}❌ git-filter-repo is not installed${NC}"
        echo "Install it with: pip install git-filter-repo"
        exit 1
    fi
    
    # Check if we can create directories
    if ! mkdir -p "$BASE_DIR" 2>/dev/null; then
        echo -e "${RED}❌ Cannot create base directory: $BASE_DIR${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Prerequisites check passed${NC}"
}

# Function to split a single service
split_service() {
    local service_name=$1
    local service_path=$2
    local plane_type=$3
    
    echo -e "${BLUE}🔧 Processing $service_name...${NC}"
    
    # Create temporary directory
    local temp_dir="$BASE_DIR/${service_name}-temp"
    rm -rf "$temp_dir"
    
    # Clone the monorepo
    echo "  📥 Cloning monorepo..."
    git clone "$MONOREPO_URL" "$temp_dir"
    cd "$temp_dir"
    
    # Extract service-specific files
    echo "  ✂️  Extracting service files..."
    git filter-repo \
        --path "${service_path}/" \
        --path "contracts/" \
        --path "db/" \
        --path "dev-env/" \
        --path ".github/workflows/" \
        --path "scripts/" \
        --path "docs/" \
        --path "README.md" \
        --path "PLAN.md" \
        --path "MIGRATION_GUIDE.md" \
        --path "ONBOARDING.md" \
        --force
    
    # Create service-specific README
    echo "  📝 Creating service README..."
    cat > README.md << EOF
# $service_name

This is the $service_name service extracted from the Multi-AI-Agent platform.

## Quick Start

\`\`\`bash
# Install dependencies
pip install -r requirements.txt

# Run the service
make run

# Run tests
make test

# Run linting
make lint
\`\`\`

## Development

This service is part of the Multi-AI-Agent platform. For full development setup, see the [meta-repository](https://github.com/$ORG_NAME/multi-ai-agent-meta).

## API Documentation

- Health Check: \`GET /healthz\`
- Readiness: \`GET /readyz\`
- Metrics: \`GET /metrics\`

## Environment Variables

See \`.env.example\` for required environment variables.

## Docker

\`\`\`bash
docker build -t $service_name .
docker run -p 8000:8000 $service_name
\`\`\`
EOF
    
    # Add and commit the new README
    git add README.md
    git commit -m "Add service-specific README" || true
    
    # Create new repository URL
    local new_repo_url="https://github.com/$ORG_NAME/$service_name.git"
    
    echo "  🔗 Setting up remote..."
    git remote add origin "$new_repo_url"
    
    echo "  📤 Pushing to new repository..."
    echo "     Repository: $new_repo_url"
    echo "     ⚠️  You need to create this repository on GitHub first!"
    
    # Ask user if they want to push
    read -p "  🤔 Create repository '$new_repo_url' on GitHub and push? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git push -u origin main
        echo -e "  ${GREEN}✅ Successfully pushed $service_name${NC}"
    else
        echo -e "  ${YELLOW}⏭️  Skipped pushing $service_name${NC}"
    fi
    
    # Clean up
    cd ..
    rm -rf "$temp_dir"
    
    echo -e "${GREEN}✅ Completed $service_name${NC}"
    echo
}

# Function to create meta-repository
create_meta_repository() {
    echo -e "${BLUE}🏗️  Creating meta-repository...${NC}"
    
    local meta_dir="$BASE_DIR/multi-ai-agent-meta"
    rm -rf "$meta_dir"
    
    # Clone the monorepo
    echo "  📥 Cloning monorepo for meta-repo..."
    git clone "$MONOREPO_URL" "$meta_dir"
    cd "$meta_dir"
    
    # Remove service-specific code, keep only orchestration files
    echo "  ✂️  Extracting meta-repository files..."
    git filter-repo \
        --path "dev-env/" \
        --path "contracts/" \
        --path "db/" \
        --path "docs/" \
        --path ".github/workflows/" \
        --path "scripts/" \
        --path "README.md" \
        --path "PLAN.md" \
        --path "MIGRATION_GUIDE.md" \
        --path "ONBOARDING.md" \
        --invert-paths
    
    # Create meta-repository README
    echo "  📝 Creating meta-repository README..."
    cat > README.md << EOF
# Multi-AI-Agent Meta-Repository

This is the meta-repository for the Multi-AI-Agent platform. It contains:

- Docker Compose orchestration
- Shared contracts and schemas
- Database migrations
- CI/CD workflows
- Documentation

## Quick Start

\`\`\`bash
# Start core services
make -C dev-env up-core

# Check service health
make -C dev-env health

# View logs
make -C dev-env logs
\`\`\`

## Service Repositories

The platform consists of the following service repositories:

### Data Plane Services
$(printf "• [%s](https://github.com/%s/%s)\n" "${DATA_PLANE_SERVICES[@]}" | sed 's/^/  /' | sed "s/$ORG_NAME/$ORG_NAME/g")

### Control Plane Services
$(printf "• [%s](https://github.com/%s/%s)\n" "${CONTROL_PLANE_SERVICES[@]}" | sed 's/^/  /' | sed "s/$ORG_NAME/$ORG_NAME/g")

## Development

See [ONBOARDING.md](ONBOARDING.md) for detailed development instructions.

## Architecture

See [PLAN.md](PLAN.md) for the complete architecture and migration plan.
EOF
    
    # Add and commit the new README
    git add README.md
    git commit -m "Add meta-repository README" || true
    
    # Create meta-repository URL
    local meta_repo_url="https://github.com/$ORG_NAME/multi-ai-agent-meta.git"
    
    echo "  🔗 Setting up remote..."
    git remote add origin "$meta_repo_url"
    
    echo "  📤 Pushing to meta-repository..."
    echo "     Repository: $meta_repo_url"
    
    # Ask user if they want to push
    read -p "  🤔 Create repository '$meta_repo_url' on GitHub and push? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git push -u origin main
        echo -e "  ${GREEN}✅ Successfully pushed meta-repository${NC}"
    else
        echo -e "  ${YELLOW}⏭️  Skipped pushing meta-repository${NC}"
    fi
    
    # Clean up
    cd ..
    rm -rf "$meta_dir"
    
    echo -e "${GREEN}✅ Completed meta-repository${NC}"
}

# Main execution
main() {
    check_prerequisites
    
    echo -e "${YELLOW}📊 Summary:${NC}"
    echo "  • Data Plane Services: ${#DATA_PLANE_SERVICES[@]}"
    echo "  • Control Plane Services: ${#CONTROL_PLANE_SERVICES[@]}"
    echo "  • Total Services: $((${#DATA_PLANE_SERVICES[@]} + ${#CONTROL_PLANE_SERVICES[@]}))"
    echo
    
    # Ask for confirmation
    read -p "🤔 Proceed with splitting all services? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}❌ Cancelled by user${NC}"
        exit 0
    fi
    
    echo -e "${BLUE}🚀 Starting repository splitting...${NC}"
    echo
    
    # Split data plane services
    echo -e "${YELLOW}📊 Processing Data Plane Services...${NC}"
    for service in "${DATA_PLANE_SERVICES[@]}"; do
        split_service "$service" "apps/data-plane/$service" "data-plane"
    done
    
    # Split control plane services
    echo -e "${YELLOW}🎛️  Processing Control Plane Services...${NC}"
    for service in "${CONTROL_PLANE_SERVICES[@]}"; do
        split_service "$service" "apps/control-plane/$service" "control-plane"
    done
    
    # Create meta-repository
    create_meta_repository
    
    echo -e "${GREEN}🎉 Repository splitting completed!${NC}"
    echo
    echo -e "${BLUE}📋 Next Steps:${NC}"
    echo "  1. Create repositories on GitHub for each service"
    echo "  2. Re-run this script and choose to push when prompted"
    echo "  3. Update CI/CD workflows in each service repository"
    echo "  4. Update documentation links"
    echo "  5. Set up service-specific monitoring"
    echo
    echo -e "${BLUE}📚 Useful Commands:${NC}"
    echo "  • Clone a service: git clone https://github.com/$ORG_NAME/service-name.git"
    echo "  • Start services: make -C dev-env up-core"
    echo "  • Check health: make -C dev-env health"
}

# Run main function
main "$@"

# Repository Splitting Script
# This script splits all services from the monorepo into separate repositories

set -e

# Configuration
MONOREPO_URL="https://github.com/your-org/multi-ai-agent.git"  # Update this URL
ORG_NAME="your-org"  # Update this to your GitHub organization
BASE_DIR=$(pwd)
TEMP_DIR="${BASE_DIR}/temp-split"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check if git filter-repo is installed
    if ! command -v git-filter-repo &> /dev/null; then
        print_error "git-filter-repo is not installed!"
        echo "Install it with:"
        echo "  pip install git-filter-repo"
        echo "  or"
        echo "  brew install git-filter-repo  # macOS"
        echo "  apt install git-filter-repo   # Ubuntu"
        exit 1
    fi
    
    # Check if we're in a git repository
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        print_error "Not in a git repository!"
        exit 1
    fi
    
    print_success "Prerequisites check passed!"
}

# Function to split a single service
split_service() {
    local service_name="$1"
    local service_path="$2"
    local new_repo_url="https://github.com/${ORG_NAME}/${service_name}.git"
    
    print_status "Splitting service: ${service_name}"
    
    # Create temporary directory
    local temp_service_dir="${TEMP_DIR}/${service_name}-temp"
    mkdir -p "${temp_service_dir}"
    
    # Clone the monorepo
    print_status "Cloning monorepo for ${service_name}..."
    git clone "${MONOREPO_URL}" "${temp_service_dir}"
    cd "${temp_service_dir}"
    
    # Extract service-specific files
    print_status "Extracting files for ${service_name}..."
    git filter-repo \
        --path "${service_path}/" \
        --path "contracts/" \
        --path "db/" \
        --path "dev-env/" \
        --path ".github/workflows/" \
        --path "scripts/" \
        --path "docs/" \
        --path "README.md" \
        --path "PLAN.md" \
        --path "MIGRATION_GUIDE.md" \
        --path "ONBOARDING.md" \
        --path "LICENSE_HEADER.txt" \
        --force
    
    # Add new remote
    print_status "Adding remote origin for ${service_name}..."
    git remote add origin "${new_repo_url}"
    
    # Push to new repository
    print_status "Pushing ${service_name} to new repository..."
    git push -u origin main
    
    # Clean up
    cd "${BASE_DIR}"
    rm -rf "${temp_service_dir}"
    
    print_success "Successfully split ${service_name}!"
}

# Function to create meta-repository
create_meta_repo() {
    print_status "Creating meta-repository..."
    
    local meta_repo_url="https://github.com/${ORG_NAME}/multi-ai-agent-meta.git"
    local temp_meta_dir="${TEMP_DIR}/meta-temp"
    mkdir -p "${temp_meta_dir}"
    
    # Clone the monorepo
    print_status "Cloning monorepo for meta-repository..."
    git clone "${MONOREPO_URL}" "${temp_meta_dir}"
    cd "${temp_meta_dir}"
    
    # Extract meta-repository files (invert paths to keep orchestration files)
    print_status "Extracting meta-repository files..."
    git filter-repo \
        --path "dev-env/" \
        --path "contracts/" \
        --path "db/" \
        --path "docs/" \
        --path ".github/workflows/" \
        --path "scripts/" \
        --path "README.md" \
        --path "PLAN.md" \
        --path "MIGRATION_GUIDE.md" \
        --path "ONBOARDING.md" \
        --path "LICENSE_HEADER.txt" \
        --force
    
    # Add new remote
    print_status "Adding remote origin for meta-repository..."
    git remote add origin "${meta_repo_url}"
    
    # Push to new repository
    print_status "Pushing meta-repository..."
    git push -u origin main
    
    # Clean up
    cd "${BASE_DIR}"
    rm -rf "${temp_meta_dir}"
    
    print_success "Successfully created meta-repository!"
}

# Main execution
main() {
    echo "🚀 Starting repository splitting process..."
    echo ""
    
    # Check prerequisites
    check_prerequisites
    
    # Create temporary directory
    mkdir -p "${TEMP_DIR}"
    
    # Data Plane Services
    print_status "Splitting Data Plane Services..."
    echo ""
    
    # Split each data plane service
    split_service "api-gateway" "apps/data-plane/api-gateway"
    split_service "model-gateway" "apps/data-plane/model-gateway"
    split_service "orchestrator" "apps/data-plane/orchestrator"
    split_service "router-service" "apps/data-plane/router-service"
    split_service "realtime-gateway" "apps/data-plane/realtime-gateway"
    split_service "ingestion-service" "apps/data-plane/ingestion-service"
    split_service "analytics-service" "apps/data-plane/analytics-service"
    split_service "retrieval-service" "apps/data-plane/retrieval-service"
    split_service "tools-service" "apps/data-plane/tools-service"
    split_service "memory-service" "apps/data-plane/memory-service"
    split_service "chat-adapters" "apps/data-plane/chat-adapters"
    split_service "semantic-cache-service" "apps/data-plane/semantic-cache-service"
    split_service "event-relay-service" "apps/data-plane/event-relay-service"
    split_service "migration-runner" "apps/data-plane/migration-runner"
    split_service "agents-service" "apps/data-plane/agents-service"
    split_service "eval-service" "apps/data-plane/eval-service"
    
    echo ""
    print_status "Splitting Control Plane Services..."
    echo ""
    
    # Split each control plane service
    split_service "config-service" "apps/control-plane/config-service"
    split_service "feature-flags-service" "apps/control-plane/feature-flags-service"
    split_service "registry-service" "apps/control-plane/registry-service"
    split_service "policy-adapter" "apps/control-plane/policy-adapter"
    split_service "usage-metering" "apps/control-plane/usage-metering"
    split_service "audit-log" "apps/control-plane/audit-log"
    split_service "notification-service" "apps/control-plane/notification-service"
    split_service "tenant-service" "apps/control-plane/tenant-service"
    split_service "capacity-monitor" "apps/control-plane/capacity-monitor"
    split_service "billing-service" "apps/control-plane/billing-service"
    
    echo ""
    print_status "Creating Meta-Repository..."
    echo ""
    
    # Create meta-repository
    create_meta_repo
    
    # Clean up
    rm -rf "${TEMP_DIR}"
    
    echo ""
    print_success "🎉 Repository splitting completed successfully!"
    echo ""
    echo "📋 Created repositories:"
    echo "  • Data Plane Services: 17 repositories"
    echo "  • Control Plane Services: 10 repositories"
    echo "  • Meta-Repository: 1 repository"
    echo ""
    echo "🔗 Next steps:"
    echo "  1. Update repository URLs in the script"
    echo "  2. Set up CI/CD pipelines in each repository"
    echo "  3. Update documentation with new repository links"
    echo "  4. Notify team members of the new repository structure"
}

# Run main function
main "$@"
