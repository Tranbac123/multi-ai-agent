#!/bin/bash
# GitHub Repository Creation Helper
# This script helps create all the required repositories on GitHub

set -e

# Source configuration
source scripts/repo-config.sh

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Function to create a GitHub repository
create_github_repo() {
    local repo_name="$1"
    local description="$2"
    
    print_status "Creating repository: ${repo_name}"
    
    # Create repository using GitHub CLI
    if command -v gh &> /dev/null; then
        gh repo create "${ORG_NAME}/${repo_name}" \
            --description "${description}" \
            --public \
            --clone=false
        print_success "Created ${repo_name} using GitHub CLI"
    else
        print_warning "GitHub CLI not found. Please create repository manually:"
        echo "  Repository: ${ORG_NAME}/${repo_name}"
        echo "  Description: ${description}"
        echo "  URL: https://github.com/${ORG_NAME}/${repo_name}"
        echo ""
    fi
}

# Main function
main() {
    echo "🚀 GitHub Repository Creation Helper"
    echo ""
    
    # Check if GitHub CLI is installed
    if ! command -v gh &> /dev/null; then
        print_warning "GitHub CLI not installed. Install it with:"
        echo "  brew install gh  # macOS"
        echo "  apt install gh   # Ubuntu"
        echo ""
        print_warning "You'll need to create repositories manually or install GitHub CLI"
        echo ""
    fi
    
    print_status "Creating Data Plane Service Repositories..."
    echo ""
    
    # Create data plane repositories
    for service in "${DATA_PLANE_SERVICES[@]}"; do
        repo_name=$(echo "$service" | cut -d':' -f1)
        create_github_repo "$repo_name" "Data Plane Service: $repo_name"
    done
    
    echo ""
    print_status "Creating Control Plane Service Repositories..."
    echo ""
    
    # Create control plane repositories
    for service in "${CONTROL_PLANE_SERVICES[@]}"; do
        repo_name=$(echo "$service" | cut -d':' -f1)
        create_github_repo "$repo_name" "Control Plane Service: $repo_name"
    done
    
    echo ""
    print_status "Creating Meta Repository..."
    echo ""
    
    # Create meta repository
    create_github_repo "meta-agent-repo" "Meta repository for Multi-AI-Agent platform orchestration"
    
    echo ""
    print_success "🎉 Repository creation completed!"
    echo ""
    echo "📋 Created repositories:"
    echo "  • Data Plane Services: ${#DATA_PLANE_SERVICES[@]} repositories"
    echo "  • Control Plane Services: ${#CONTROL_PLANE_SERVICES[@]} repositories"
    echo "  • Meta Repository: 1 repository"
    echo ""
    echo "🔗 Next steps:"
    echo "  1. Verify all repositories were created on GitHub"
    echo "  2. Run the splitting script: ./scripts/split-repositories.sh"
    echo "  3. Set up CI/CD pipelines in each repository"
}

# Run main function
main "$@"
