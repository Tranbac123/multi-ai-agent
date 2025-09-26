# 🚀 Repository Splitting Guide

This guide will help you split your monorepo into individual service repositories while preserving git history.

## 📋 Prerequisites

### 1. Install git-filter-repo

```bash
# Option 1: Using pip
pip install git-filter-repo

# Option 2: Using package manager
brew install git-filter-repo  # macOS
apt install git-filter-repo   # Ubuntu
```

### 2. Verify Installation

```bash
git filter-repo --help
```

## 🔧 Step-by-Step Splitting Process

### Step 1: Configure Your Settings

1. **Update the configuration file:**

   ```bash
   nano scripts/repo-config.sh
   ```

2. **Set your GitHub organization and repository URL:**
   ```bash
   export ORG_NAME="your-github-org"  # Replace with your GitHub org
   export MONOREPO_URL="https://github.com/your-github-org/multi-ai-agent.git"
   ```

### Step 2: Create GitHub Repositories

Before running the split script, you need to create empty repositories on GitHub for each service:

#### Data Plane Services (17 repositories):

- `api-gateway`
- `model-gateway`
- `orchestrator`
- `router-service`
- `realtime-gateway`
- `ingestion-service`
- `analytics-service`
- `retrieval-service`
- `tools-service`
- `memory-service`
- `chat-adapters`
- `semantic-cache-service`
- `event-relay-service`
- `migration-runner`
- `agents-service`
- `eval-service`

#### Control Plane Services (10 repositories):

- `config-service`
- `feature-flags-service`
- `registry-service`
- `policy-adapter`
- `usage-metering`
- `audit-log`
- `notification-service`
- `tenant-service`
- `capacity-monitor`
- `billing-service`

#### Meta Repository (1 repository):

- `meta-repo`

### Step 3: Run the Splitting Script

```bash
# Make sure you're in the monorepo root
cd /path/to/multi-ai-agent

# Run the splitting script
./scripts/split-repositories.sh
```

## 🎯 Alternative: Manual Splitting

If you prefer to split services one by one, here's the manual process:

### For Each Service:

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
  --path ONBOARDING.md \
  --path LICENSE_HEADER.txt \
  --force

# Add new remote
git remote add origin ${NEW_REPO_URL}

# Push to new repository
git push -u origin main

# Clean up
cd ..
rm -rf ${SERVICE_NAME}-temp
```

## 📁 What Each Repository Will Contain

Each service repository will include:

- ✅ **Service source code** (`src/`, `apps/data-plane/service-name/`)
- ✅ **Tests** (`tests/`)
- ✅ **Docker configuration** (`Dockerfile`, `docker-compose.yml`)
- ✅ **Dependencies** (`requirements.txt`, `pyproject.toml`)
- ✅ **CI/CD pipelines** (`.github/workflows/`)
- ✅ **Documentation** (`README.md`, `docs/`)
- ✅ **Kubernetes manifests** (`k8s/`)
- ✅ **Shared contracts** (`contracts/`)
- ✅ **Database migrations** (`db/`)
- ✅ **Scripts** (`scripts/`)

## 🔄 Post-Split Setup

### 1. Update CI/CD Pipelines

Each service repository will have its own CI/CD pipeline. Update the workflows to:

- Build and test the specific service
- Deploy to appropriate environments
- Use service-specific secrets and configurations

### 2. Update Documentation

- Update `README.md` files in each repository
- Update service-specific documentation
- Update API documentation
- Update deployment guides

### 3. Set Up Cross-Repository Dependencies

- Use Git submodules for shared contracts
- Set up proper versioning for shared libraries
- Configure dependency management

### 4. Team Communication

- Notify team members of new repository structure
- Update access permissions for each repository
- Set up team-specific notifications
- Update development workflows

## 🚨 Important Considerations

### 1. Backup Your Monorepo

```bash
# Create a backup before splitting
git clone <monorepo-url> multi-ai-agent-backup
```

### 2. Test the Split

- Verify that each repository contains the expected files
- Test that services can still run independently
- Verify that git history is preserved

### 3. Update References

- Update any hardcoded paths in your code
- Update documentation links
- Update deployment scripts

## 🔧 Troubleshooting

### Common Issues:

1. **git-filter-repo not found**

   ```bash
   pip install git-filter-repo
   ```

2. **Repository already exists**

   - Delete the existing repository on GitHub
   - Or use a different name

3. **Permission denied**

   - Check your GitHub access tokens
   - Verify repository permissions

4. **Large repository size**
   - Use `--force` flag with git-filter-repo
   - Consider using `--partial` for very large repositories

## 📊 Repository Structure After Split

```
your-github-org/
├── api-gateway/
├── model-gateway/
├── orchestrator/
├── router-service/
├── realtime-gateway/
├── ingestion-service/
├── analytics-service/
├── retrieval-service/
├── tools-service/
├── memory-service/
├── chat-adapters/
├── semantic-cache-service/
├── event-relay-service/
├── migration-runner/
├── agents-service/
├── eval-service/
├── config-service/
├── feature-flags-service/
├── registry-service/
├── policy-adapter/
├── usage-metering/
├── audit-log/
├── notification-service/
├── tenant-service/
├── capacity-monitor/
├── billing-service/
└── multi-ai-agent-meta/
```

## 🎉 Success Checklist

- [ ] All 28 repositories created successfully
- [ ] Git history preserved in each repository
- [ ] All services can run independently
- [ ] CI/CD pipelines updated
- [ ] Documentation updated
- [ ] Team notified of changes
- [ ] Access permissions configured
- [ ] Backup of original monorepo created

## 📞 Support

If you encounter any issues during the splitting process:

1. Check the troubleshooting section above
2. Review the git-filter-repo documentation
3. Test with a single service first
4. Create a backup before proceeding

Happy splitting! 🚀
