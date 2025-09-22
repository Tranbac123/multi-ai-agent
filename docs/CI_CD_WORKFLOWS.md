# CI/CD Workflows Documentation

## Overview

This document describes the comprehensive CI/CD pipeline for the Multi-AI-Agent platform, designed for microservices with reusable workflows and intelligent change detection.

## Architecture

### 1. Reusable Service CI Template (`platform/ci-templates/service-ci.yaml`)

Central template that handles CI/CD for all services with language-specific support:

**Supported Languages:**

- **Python** (FastAPI services)
- **Node.js** (Frontend applications)
- **Go** (Future expansion)

**Pipeline Stages:**

1. **Change Detection** - Smart path-based filtering
2. **Testing** - Language-specific test execution
3. **Security Scanning** - Trivy, Bandit, npm audit, gosec
4. **Docker Build** - Multi-platform container builds
5. **SBOM Generation** - Software Bill of Materials
6. **Deployment Check** - Kubernetes manifest validation

### 2. Service-Specific Workflows (`apps/<service>/.github/workflows/ci.yaml`)

Each service has its own workflow that:

- Triggers on changes to service-specific paths
- Uses the reusable template with service configuration
- Provides service-specific deployment logic

### 3. Platform-Level Workflows (`.github/workflows/`)

#### Changed Services Detection (`changed-services.yaml`)

- Detects which services changed in a commit/PR
- Triggers appropriate service CI workflows
- Provides comprehensive summary of triggered pipelines

#### Platform Health Check (`platform-health.yaml`)

- Runs hourly to validate platform integrity
- Checks all services have required files
- Validates workflow syntax
- Reports overall platform health

#### Security Scan (`security-scan.yaml`)

- Daily security scanning across all services
- Dependency vulnerability scanning
- Secret detection with TruffleHog
- License compliance checking

## Service CI Pipeline Details

### Path Filters

Each service CI triggers only on relevant changes:

```yaml
on:
  push:
    paths:
      - "apps/<service-name>/**" # Service-specific changes
      - "libs/**" # Shared library changes
      - "contracts/**" # API contract changes
      - "platform/ci-templates/**" # CI template changes
```

### Language-Specific Stages

#### Python Services

```yaml
# Setup
- Python 3.11 with dependency caching
- Install requirements.txt + requirements-dev.txt

# Testing
- Linting: black, ruff, mypy
- Testing: pytest with coverage
- Security: bandit

# Infrastructure
- PostgreSQL + Redis test containers
```

#### Node.js Services

```yaml
# Setup
- Node.js 18 with npm cache
- Install dependencies with npm ci

# Testing
- Linting: ESLint
- Testing: Jest/Vitest
- Security: npm audit

# Build
- Production build validation
```

### Security Integration

#### Vulnerability Scanning

- **Trivy**: Filesystem and container scanning
- **Bandit**: Python security linting
- **npm audit**: Node.js dependency scanning
- **gosec**: Go security scanning (when applicable)

#### SBOM Generation

- Automatic Software Bill of Materials creation
- SPDX-JSON format for compliance
- Artifact storage for audit trails

### Docker Build Process

#### Multi-Platform Support

- **Platforms**: linux/amd64, linux/arm64
- **Caching**: GitHub Actions cache for faster builds
- **Registry**: Configurable container registry

#### Image Tagging Strategy

```yaml
tags:
  - type=ref,event=branch # branch-name
  - type=ref,event=pr # pr-123
  - type=sha,prefix={{branch}}- # main-abc123
  - type=semver,pattern={{version}} # v1.2.3
  - type=raw,value=latest # latest (main only)
```

## Workflow Triggers

### Automatic Triggers

1. **Service Changes**: Any change to `apps/<service>/` triggers that service's CI
2. **Global Changes**: Changes to `libs/`, `contracts/`, or CI templates trigger all services
3. **Scheduled**: Platform health and security scans run on schedule

### Manual Triggers

All workflows support `workflow_dispatch` for manual execution.

## Configuration

### Repository Secrets

Required secrets for full functionality:

```yaml
DOCKER_REGISTRY_URL: "ghcr.io" # Container registry
DOCKER_USERNAME: "${{ github.actor }}" # Registry username
DOCKER_PASSWORD: "${{ secrets.GITHUB_TOKEN }}" # Registry password
```

### Service Configuration

Each service workflow is configured in `scripts/generate_service_workflows.py`:

```python
SERVICES_CONFIG = {
    "api-gateway": {"language": "python", "port": 8000},
    "web-frontend": {"language": "node", "port": 3000},
    # ... other services
}
```

## Monitoring and Observability

### Pipeline Insights

#### Summary Reports

- **Changed Services Detection**: Shows which services triggered
- **Health Checks**: Platform-wide service health status
- **Security Scans**: Vulnerability and compliance reports

#### Artifacts

- **Test Reports**: Coverage and test results
- **Security Reports**: Vulnerability scan results
- **SBOM**: Software Bill of Materials
- **Docker Images**: Multi-platform container builds

### Status Badges

Add status badges to README.md:

```markdown
![Platform Health](https://github.com/org/repo/workflows/Platform%20Health%20Check/badge.svg)
![Security Scan](https://github.com/org/repo/workflows/Platform%20Security%20Scan/badge.svg)
![Changed Services](https://github.com/org/repo/workflows/Changed%20Services%20Detection/badge.svg)
```

## Best Practices

### 1. Service Independence

- Each service CI runs independently
- No cross-service dependencies in CI
- Service-specific test databases

### 2. Efficient Resource Usage

- Path-based filtering prevents unnecessary runs
- Dependency caching for faster builds
- Parallel execution where possible

### 3. Security First

- Automated vulnerability scanning
- Secret detection in commits
- Container image security scanning
- SBOM generation for compliance

### 4. Developer Experience

- Clear pipeline status and summaries
- Artifact storage for debugging
- Fast feedback loops
- Comprehensive error reporting

## Troubleshooting

### Common Issues

#### Service CI Not Triggering

- Check path filters in service workflow
- Verify file changes are in correct service directory
- Check for workflow syntax errors

#### Failed Security Scans

- Review vulnerability reports in artifacts
- Update dependencies to resolve vulnerabilities
- Add exceptions for false positives

#### Docker Build Failures

- Check Dockerfile syntax and paths
- Verify base image availability
- Review build context and .dockerignore

### Debug Commands

```bash
# Validate workflow syntax
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/changed-services.yaml'))"

# Test service locally
cd apps/<service>
make dev && make test && make build

# Validate Kubernetes manifests
cd apps/<service>/deploy
make validate
```

## Future Enhancements

### Planned Features

1. **Deployment Automation**: Auto-deploy to dev on merge
2. **Performance Testing**: Load testing in CI pipeline
3. **Canary Deployments**: Progressive rollouts
4. **Multi-Environment**: Staging and production pipelines
5. **Metrics Collection**: CI/CD performance metrics

### Extension Points

1. **New Languages**: Add Go, Rust, Java support
2. **Custom Scanners**: Integrate additional security tools
3. **Deployment Targets**: Support for different cloud providers
4. **Notification**: Slack/Teams integration for failures
