# Control-Plane / Data-Plane Migration Guide

This guide explains how to migrate your repository from a `services/` based structure to a production-grade Control-Plane/Data-Plane architecture.

## Overview

The migration utility (`scripts/migrate_tree.py`) reorganizes services into:

- **Control-Plane** (`apps/control-plane/`): Configuration, policies, feature flags, registries, auditing
- **Data-Plane** (`apps/data-plane/`): API gateways, routers, agents, workers, processing services

## Quick Start

### 1. Dry Run (Safe)

```bash
# Preview what will be migrated
python scripts/migrate_tree.py --dry-run
```

### 2. Apply Migration

```bash
# Actually perform the migration
python scripts/migrate_tree.py --apply
```

## Service Classification

Services are automatically classified using keyword heuristics:

### Control-Plane Keywords

- `policy`, `config`, `feature`, `flags`, `registry`, `usage`
- `meter`, `audit`, `tenant`, `iam`, `opa`, `tool-registry`

### Data-Plane Keywords

- `api-gateway`, `gateway`, `router`, `orchestrator`, `ingestion`, `retrieval`
- `mcp`, `realtime`, `eval`, `embedding`, `rerank`, `worker`, `load`
- `agent`, `chat`, `tool`, `search`

**Default**: Services fallback to Data-Plane if no keywords match.

## What Gets Created

For each migrated service, the utility ensures:

### Directory Structure

```
apps/{plane}/{service}/
├── src/                    # Source code
├── tests/                  # Test files
├── contracts/
│   └── openapi.yaml       # API specification
├── deploy/helm/{service}/
│   ├── Chart.yaml         # Helm chart metadata
│   ├── values.yaml        # Default values
│   └── templates/         # K8s manifests
│       ├── deployment.yaml
│       ├── service.yaml
│       ├── hpa.yaml       # Horizontal Pod Autoscaler
│       └── pdb.yaml       # Pod Disruption Budget
├── observability/
│   ├── dashboards.json    # Grafana dashboards
│   ├── alerts.yaml        # Prometheus alerts
│   ├── SLO.md            # Service Level Objectives
│   └── runbook.md        # Incident response guide
├── Dockerfile             # Container definition
└── Makefile              # Development tasks
```

### CI/CD Integration

- Creates `.github/workflows/{service}-ci.yaml`
- Uses reusable template if `platform/ci-templates/python-service-ci.yaml` exists
- Path filtering: only triggers on changes to service directory

## Special Cases

### Eval Directory

If `eval/` contains source code, it's converted to `apps/data-plane/eval-service/` with full service structure.

### Existing Services

- If target directory exists, content is merged
- Git history is preserved where possible
- No data loss - only reorganization

## Revert Procedures

### Git-based Revert

```bash
# Revert all changes (if not committed)
git restore -SW .

# Revert specific commit
git revert <commit-hash>

# Reset to previous state (destructive)
git reset --hard HEAD~1
```

### Manual Revert

```bash
# Move services back to original structure
mkdir -p services/
mv apps/control-plane/* services/
mv apps/data-plane/* services/

# Remove empty directories
rm -rf apps/control-plane apps/data-plane
```

## Validation

After migration, verify the structure:

```bash
# Check service structure
find apps/ -name "Dockerfile" | wc -l  # Should match service count
find apps/ -name "Chart.yaml" | wc -l  # Should match service count

# Test CI workflows
git add -A && git commit -m "test: trigger CI"

# Verify observability files
find apps/ -name "dashboards.json" | wc -l
find apps/ -name "SLO.md" | wc -l
```

## Troubleshooting

### Service Not Classified Correctly

Edit service name or add custom classification logic in `migrate_tree.py`:

```python
# Add custom keywords to CONTROL_PLANE_KEYWORDS or DATA_PLANE_KEYWORDS
CONTROL_PLANE_KEYWORDS = ["policy", "config", "your-custom-keyword"]
```

### Missing Files After Migration

Re-run the migration - it's idempotent and will create missing files:

```bash
python scripts/migrate_tree.py --apply
```

### CI Workflows Not Working

1. Check path filters in `.github/workflows/{service}-ci.yaml`
2. Verify reusable template exists at `platform/ci-templates/python-service-ci.yaml`
3. Update workflow if service path changed

### Helm Charts Not Deploying

1. Verify Chart.yaml syntax
2. Check values.yaml for correct image references
3. Update service names in templates if needed

## Best Practices

### Before Migration

- [ ] Commit all pending changes
- [ ] Create a backup branch: `git checkout -b pre-migration-backup`
- [ ] Run dry-run to review migration plan
- [ ] Ensure CI/CD pipelines are working

### After Migration

- [ ] Test each service individually
- [ ] Update documentation references
- [ ] Verify observability dashboards
- [ ] Check that CI/CD triggers correctly
- [ ] Update deployment scripts/configs

## Migration Checklist

### Pre-Migration

- [ ] Repository is clean (no uncommitted changes)
- [ ] Backup branch created
- [ ] Migration plan reviewed with `--dry-run`
- [ ] Team notified of upcoming changes

### Post-Migration

- [ ] All services in correct planes
- [ ] CI/CD workflows functioning
- [ ] Observability files present
- [ ] Helm charts deployable
- [ ] Documentation updated
- [ ] Team trained on new structure

## Support

For issues or questions:

- Check this documentation first
- Run migration with `--dry-run` to preview changes
- Review generated files for correctness
- Open an issue if migration fails unexpectedly

## Advanced Usage

### Custom Repository Root

```bash
python scripts/migrate_tree.py --repo-root /path/to/repo --apply
```

### Programmatic Usage

```python
from scripts.migrate_tree import RepositoryMigrator

migrator = RepositoryMigrator(repo_root=Path("/path/to/repo"), dry_run=False)
migrator.migrate()
```
