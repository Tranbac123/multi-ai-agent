# Monorepo to Polyrepo Migration Guide

This guide provides step-by-step instructions for splitting the monorepo into multiple service repositories while preserving git history.

## Overview

We'll split the monorepo into individual service repositories, each containing:

- Service-specific source code
- Tests and documentation
- Docker configuration
- Kubernetes manifests
- CI/CD pipelines

## Prerequisites

- Git with `git filter-repo` installed
- Access to create new repositories
- Backup of the current monorepo

## Migration Strategies

### Option A: Separate Repositories with git filter-repo (Recommended)

This approach creates completely independent repositories for each service.

#### Step 1: Install git filter-repo

```bash
# Install git filter-repo
pip install git-filter-repo

# Or via package manager
brew install git-filter-repo  # macOS
apt install git-filter-repo   # Ubuntu
```

#### Step 2: Create Service Repositories

For each service, run the following commands:

```bash
# Set variables
SERVICE_NAME="api-gateway"
SERVICE_PATH="apps/data-plane/api-gateway"
NEW_REPO_URL="https://github.com/your-org/api-gateway.git"

# Clone the monorepo
git clone <monorepo-url> ${SERVICE_NAME}-temp
cd ${SERVICE_NAME}-temp

# Extract service-specific files
git filter-repo \
  --path ${SERVICE_PATH}/ \
  --path contracts/ \
  --path db/ \
  --path dev-env/ \
  --path .github/workflows/ \
  --path scripts/ \
  --path docs/ \
  --path README.md \
  --path PLAN.md \
  --path MIGRATION_GUIDE.md \
  --path ONBOARDING.md

# Add new remote
git remote add origin ${NEW_REPO_URL}

# Push to new repository
git push -u origin main

# Clean up
cd ..
rm -rf ${SERVICE_NAME}-temp
```

#### Step 3: Create Meta-Repository

```bash
# Create meta-repo
git clone <monorepo-url> multi-ai-agent-meta
cd multi-ai-agent-meta

# Remove service-specific code, keep only orchestration files
git filter-repo \
  --path dev-env/ \
  --path contracts/ \
  --path db/ \
  --path docs/ \
  --path .github/workflows/ \
  --path scripts/ \
  --path README.md \
  --path PLAN.md \
  --path MIGRATION_GUIDE.md \
  --invert-paths

# Add service repositories as submodules (optional)
git submodule add https://github.com/your-org/api-gateway.git services/api-gateway
git submodule add https://github.com/your-org/orchestrator.git services/orchestrator
# ... repeat for all services

# Commit submodule changes
git add .gitmodules services/
git commit -m "Add service repositories as submodules"

# Push meta-repo
git remote add origin https://github.com/your-org/multi-ai-agent-meta.git
git push -u origin main
```

### Option B: Meta-repo with Submodules

This approach keeps the current repository as a meta-repo and adds services as submodules.

#### Step 1: Prepare Service Repositories

For each service:

```bash
# Create new repository on GitHub/GitLab
# Then clone and prepare

SERVICE_NAME="api-gateway"
SERVICE_PATH="apps/data-plane/api-gateway"
NEW_REPO_URL="https://github.com/your-org/api-gateway.git"

# Clone monorepo
git clone <monorepo-url> ${SERVICE_NAME}-temp
cd ${SERVICE_NAME}-temp

# Create new branch for service
git checkout -b ${SERVICE_NAME}-extraction

# Remove everything except service files
git filter-branch --index-filter \
  'git rm -r --cached --ignore-unmatch . && \
   git reset -- $GIT_COMMIT -- ${SERVICE_PATH} contracts/ db/ dev-env/ .github/ scripts/ docs/ README.md PLAN.md MIGRATION_GUIDE.md' \
  --prune-empty -- ${SERVICE_NAME}-extraction

# Push to new repository
git remote add origin ${NEW_REPO_URL}
git push -u origin ${SERVICE_NAME}-extraction

# Clean up
cd ..
rm -rf ${SERVICE_NAME}-temp
```

#### Step 2: Update Meta-repo

```bash
# In the original monorepo
cd multi-ai-agent

# Add service repositories as submodules
git submodule add https://github.com/your-org/api-gateway.git services/api-gateway
git submodule add https://github.com/your-org/orchestrator.git services/orchestrator
git submodule add https://github.com/your-org/router-service.git services/router-service
git submodule add https://github.com/your-org/model-gateway.git services/model-gateway
git submodule add https://github.com/your-org/retrieval-service.git services/retrieval-service
git submodule add https://github.com/your-org/ingestion-service.git services/ingestion-service
git submodule add https://github.com/your-org/analytics-service.git services/analytics-service
git submodule add https://github.com/your-org/billing-service.git services/billing-service
git submodule add https://github.com/your-org/realtime-gateway.git services/realtime-gateway
git submodule add https://github.com/your-org/config-service.git services/config-service
git submodule add https://github.com/your-org/usage-metering.git services/usage-metering

# Commit submodule changes
git add .gitmodules services/
git commit -m "Add service repositories as submodules"

# Remove old service directories
git rm -r apps/data-plane/ apps/control-plane/
git commit -m "Remove old service directories"

# Push changes
git push origin main
```

## Service-Specific Migration Commands

### API Gateway

```bash
SERVICE_NAME="api-gateway"
SERVICE_PATH="apps/data-plane/api-gateway"
NEW_REPO_URL="https://github.com/your-org/api-gateway.git"

git clone <monorepo-url> ${SERVICE_NAME}-temp
cd ${SERVICE_NAME}-temp
git filter-repo \
  --path ${SERVICE_PATH}/ \
  --path contracts/ \
  --path db/ \
  --path dev-env/ \
  --path .github/workflows/ \
  --path scripts/ \
  --path docs/ \
  --path README.md
git remote add origin ${NEW_REPO_URL}
git push -u origin main
cd .. && rm -rf ${SERVICE_NAME}-temp
```

### Orchestrator

```bash
SERVICE_NAME="orchestrator"
SERVICE_PATH="apps/data-plane/orchestrator"
NEW_REPO_URL="https://github.com/your-org/orchestrator.git"

git clone <monorepo-url> ${SERVICE_NAME}-temp
cd ${SERVICE_NAME}-temp
git filter-repo \
  --path ${SERVICE_PATH}/ \
  --path contracts/ \
  --path db/ \
  --path dev-env/ \
  --path .github/workflows/ \
  --path scripts/ \
  --path docs/ \
  --path README.md
git remote add origin ${NEW_REPO_URL}
git push -u origin main
cd .. && rm -rf ${SERVICE_NAME}-temp
```

### Router Service

```bash
SERVICE_NAME="router-service"
SERVICE_PATH="apps/data-plane/router-service"
NEW_REPO_URL="https://github.com/your-org/router-service.git"

git clone <monorepo-url> ${SERVICE_NAME}-temp
cd ${SERVICE_NAME}-temp
git filter-repo \
  --path ${SERVICE_PATH}/ \
  --path contracts/ \
  --path db/ \
  --path dev-env/ \
  --path .github/workflows/ \
  --path scripts/ \
  --path docs/ \
  --path README.md
git remote add origin ${NEW_REPO_URL}
git push -u origin main
cd .. && rm -rf ${SERVICE_NAME}-temp
```

### Model Gateway

```bash
SERVICE_NAME="model-gateway"
SERVICE_PATH="apps/data-plane/model-gateway"
NEW_REPO_URL="https://github.com/your-org/model-gateway.git"

git clone <monorepo-url> ${SERVICE_NAME}-temp
cd ${SERVICE_NAME}-temp
git filter-repo \
  --path ${SERVICE_PATH}/ \
  --path contracts/ \
  --path db/ \
  --path dev-env/ \
  --path .github/workflows/ \
  --path scripts/ \
  --path docs/ \
  --path README.md
git remote add origin ${NEW_REPO_URL}
git push -u origin main
cd .. && rm -rf ${SERVICE_NAME}-temp
```

### Retrieval Service

```bash
SERVICE_NAME="retrieval-service"
SERVICE_PATH="apps/data-plane/retrieval-service"
NEW_REPO_URL="https://github.com/your-org/retrieval-service.git"

git clone <monorepo-url> ${SERVICE_NAME}-temp
cd ${SERVICE_NAME}-temp
git filter-repo \
  --path ${SERVICE_PATH}/ \
  --path contracts/ \
  --path db/ \
  --path dev-env/ \
  --path .github/workflows/ \
  --path scripts/ \
  --path docs/ \
  --path README.md
git remote add origin ${NEW_REPO_URL}
git push -u origin main
cd .. && rm -rf ${SERVICE_NAME}-temp
```

### Ingestion Service

```bash
SERVICE_NAME="ingestion-service"
SERVICE_PATH="apps/data-plane/ingestion-service"
NEW_REPO_URL="https://github.com/your-org/ingestion-service.git"

git clone <monorepo-url> ${SERVICE_NAME}-temp
cd ${SERVICE_NAME}-temp
git filter-repo \
  --path ${SERVICE_PATH}/ \
  --path contracts/ \
  --path db/ \
  --path dev-env/ \
  --path .github/workflows/ \
  --path scripts/ \
  --path docs/ \
  --path README.md
git remote add origin ${NEW_REPO_URL}
git push -u origin main
cd .. && rm -rf ${SERVICE_NAME}-temp
```

### Analytics Service

```bash
SERVICE_NAME="analytics-service"
SERVICE_PATH="apps/data-plane/analytics-service"
NEW_REPO_URL="https://github.com/your-org/analytics-service.git"

git clone <monorepo-url> ${SERVICE_NAME}-temp
cd ${SERVICE_NAME}-temp
git filter-repo \
  --path ${SERVICE_PATH}/ \
  --path contracts/ \
  --path db/ \
  --path dev-env/ \
  --path .github/workflows/ \
  --path scripts/ \
  --path docs/ \
  --path README.md
git remote add origin ${NEW_REPO_URL}
git push -u origin main
cd .. && rm -rf ${SERVICE_NAME}-temp
```

### Billing Service

```bash
SERVICE_NAME="billing-service"
SERVICE_PATH="apps/control-plane/billing-service"
NEW_REPO_URL="https://github.com/your-org/billing-service.git"

git clone <monorepo-url> ${SERVICE_NAME}-temp
cd ${SERVICE_NAME}-temp
git filter-repo \
  --path ${SERVICE_PATH}/ \
  --path contracts/ \
  --path db/ \
  --path dev-env/ \
  --path .github/workflows/ \
  --path scripts/ \
  --path docs/ \
  --path README.md
git remote add origin ${NEW_REPO_URL}
git push -u origin main
cd .. && rm -rf ${SERVICE_NAME}-temp
```

### Realtime Gateway

```bash
SERVICE_NAME="realtime-gateway"
SERVICE_PATH="apps/data-plane/realtime-gateway"
NEW_REPO_URL="https://github.com/your-org/realtime-gateway.git"

git clone <monorepo-url> ${SERVICE_NAME}-temp
cd ${SERVICE_NAME}-temp
git filter-repo \
  --path ${SERVICE_PATH}/ \
  --path contracts/ \
  --path db/ \
  --path dev-env/ \
  --path .github/workflows/ \
  --path scripts/ \
  --path docs/ \
  --path README.md
git remote add origin ${NEW_REPO_URL}
git push -u origin main
cd .. && rm -rf ${SERVICE_NAME}-temp
```

### Config Service

```bash
SERVICE_NAME="config-service"
SERVICE_PATH="apps/control-plane/config-service"
NEW_REPO_URL="https://github.com/your-org/config-service.git"

git clone <monorepo-url> ${SERVICE_NAME}-temp
cd ${SERVICE_NAME}-temp
git filter-repo \
  --path ${SERVICE_PATH}/ \
  --path contracts/ \
  --path db/ \
  --path dev-env/ \
  --path .github/workflows/ \
  --path scripts/ \
  --path docs/ \
  --path README.md
git remote add origin ${NEW_REPO_URL}
git push -u origin main
cd .. && rm -rf ${SERVICE_NAME}-temp
```

### Usage Metering

```bash
SERVICE_NAME="usage-metering"
SERVICE_PATH="apps/control-plane/usage-metering"
NEW_REPO_URL="https://github.com/your-org/usage-metering.git"

git clone <monorepo-url> ${SERVICE_NAME}-temp
cd ${SERVICE_NAME}-temp
git filter-repo \
  --path ${SERVICE_PATH}/ \
  --path contracts/ \
  --path db/ \
  --path dev-env/ \
  --path .github/workflows/ \
  --path scripts/ \
  --path docs/ \
  --path README.md
git remote add origin ${NEW_REPO_URL}
git push -u origin main
cd .. && rm -rf ${SERVICE_NAME}-temp
```

## Post-Migration Steps

### 1. Update Service Configurations

For each service repository:

```bash
# Update Docker build context
# Update CI/CD workflows
# Update service discovery configurations
# Update documentation
```

### 2. Update Meta-repo

```bash
# Update docker-compose.yml to use service repositories
# Update CI/CD workflows
# Update documentation
# Update scripts
```

### 3. Test the Migration

```bash
# Clone meta-repo
git clone https://github.com/your-org/multi-ai-agent-meta.git
cd multi-ai-agent-meta

# Initialize submodules
git submodule update --init --recursive

# Start services
make up-core

# Run smoke tests
make smoke-test
```

### 4. Update Team Workflows

- Update documentation
- Train team on new repository structure
- Update CI/CD access permissions
- Set up monitoring and alerting

## Rollback Plan

If issues arise, you can rollback by:

1. **Immediate Rollback**: Revert to the original monorepo
2. **Partial Rollback**: Move specific services back to monorepo
3. **Gradual Rollback**: Move services back one by one

### Rollback Commands

```bash
# Revert to original monorepo
git checkout <original-monorepo-tag>
git push --force origin main

# Or restore from backup
git clone <backup-repo-url> multi-ai-agent-restored
cd multi-ai-agent-restored
git remote add origin <original-monorepo-url>
git push --force origin main
```

## Verification Checklist

- [ ] All services have their own repositories
- [ ] Git history is preserved
- [ ] All services can be built independently
- [ ] Docker Compose works with new structure
- [ ] CI/CD pipelines are updated
- [ ] Documentation is updated
- [ ] Team is trained on new structure
- [ ] Monitoring and alerting are configured
- [ ] Backup and rollback procedures are tested

## Troubleshooting

### Common Issues

1. **Large repository size**: Use `git filter-repo` with `--strip-blobs-bigger-than` option
2. **Missing files**: Check filter-repo paths and adjust as needed
3. **Submodule issues**: Use `git submodule update --init --recursive`
4. **Permission issues**: Check repository access and CI/CD permissions

### Support

For issues during migration:

1. Check the troubleshooting section
2. Review git filter-repo documentation
3. Contact the platform team
4. Use the rollback plan if necessary

## Conclusion

This migration will provide:

- **Independent service development**
- **Faster CI/CD pipelines**
- **Better team autonomy**
- **Easier scaling**
- **Improved security boundaries**

The migration process preserves git history while creating clean service boundaries for better maintainability and scalability.
