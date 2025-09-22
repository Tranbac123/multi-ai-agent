# 🔧 **Microservices Refactor Plan**

## 📊 **Current Repository Analysis**

### **Services Discovered Under `apps/`**

| Service             | Type         | Current Structure                                       | Status              |
| ------------------- | ------------ | ------------------------------------------------------- | ------------------- |
| `api-gateway`       | Backend      | ✅ Migrated (src/, contracts/, deploy/, observability/) | **READY**           |
| `analytics-service` | Backend      | ✅ Migrated (src/, contracts/, deploy/, observability/) | **READY**           |
| `orchestrator`      | Backend      | ✅ Migrated (src/, contracts/, deploy/, observability/) | **READY**           |
| `router-service`    | Backend      | ✅ Migrated (src/, contracts/, deploy/, observability/) | **READY**           |
| `realtime`          | Backend      | ✅ Migrated (src/, contracts/, deploy/, observability/) | **READY**           |
| `ingestion`         | Backend      | ✅ Migrated (src/, contracts/, deploy/, observability/) | **READY**           |
| `billing-service`   | Backend      | ✅ Migrated (src/, contracts/, deploy/, observability/) | **READY**           |
| `tenant-service`    | Backend      | ✅ Migrated (src/, contracts/, deploy/, observability/) | **READY**           |
| `chat-adapters`     | Backend      | ✅ Migrated (src/, contracts/, deploy/, observability/) | **READY**           |
| `tool-service`      | Backend      | ✅ Migrated (src/, contracts/, deploy/, observability/) | **READY**           |
| `eval-service`      | Backend      | ✅ Migrated (src/, contracts/, deploy/, observability/) | **READY**           |
| `capacity-monitor`  | Backend      | ✅ Migrated (src/, contracts/, deploy/, observability/) | **READY**           |
| `admin-portal`      | **Frontend** | 🔄 Needs frontend structure                             | **NEEDS MIGRATION** |
| `web`               | **Frontend** | 🔄 Needs frontend structure                             | **NEEDS MIGRATION** |

### **Duplicates Detected**

| Original            | Duplicate/Legacy           | Proposed Action                                                       |
| ------------------- | -------------------------- | --------------------------------------------------------------------- |
| `apps/api-gateway/` | `apps/api-gateway_legacy/` | ✅ **KEEP** original (migrated), **REMOVE** legacy after verification |

### **Root-Level Assets to Redistribute**

| Asset Type               | Current Location              | Target Destination  | Action Required  |
| ------------------------ | ----------------------------- | ------------------- | ---------------- |
| **Shared Database**      | `infra/database/`             | ✅ Already moved    | **NONE**         |
| **Kubernetes Manifests** | `infra/k8s/`                  | ✅ Already moved    | **NONE**         |
| **Legacy Dockerfiles**   | `infra/dockerfiles/`          | Individual services | **REDISTRIBUTE** |
| **Integration Tests**    | `platform/integration-tests/` | ✅ Already moved    | **NONE**         |
| **Load Tests**           | `platform/load_tests/`        | ✅ Already moved    | **NONE**         |
| **Global Observability** | `observability/`              | Individual services | **REDISTRIBUTE** |
| **Docker Compose**       | Root level                    | Platform level      | **MOVE**         |
| **Global Test Files**    | Root level                    | Platform level      | **MOVE**         |

## 📋 **Detailed Service Mapping**

### **Backend Services (Already Migrated)**

| Service               | Code Paths                       | DB Paths                        | K8s Files                           | Dockerfiles                            | Tests                              | Observability                              |
| --------------------- | -------------------------------- | ------------------------------- | ----------------------------------- | -------------------------------------- | ---------------------------------- | ------------------------------------------ |
| **api-gateway**       | ✅ `apps/api-gateway/src/`       | ✅ `apps/api-gateway/db/`       | ✅ `apps/api-gateway/deploy/`       | ✅ `apps/api-gateway/Dockerfile`       | ✅ `apps/api-gateway/tests/`       | ✅ `apps/api-gateway/observability/`       |
| **analytics-service** | ✅ `apps/analytics-service/src/` | ✅ `apps/analytics-service/db/` | ✅ `apps/analytics-service/deploy/` | ✅ `apps/analytics-service/Dockerfile` | ✅ `apps/analytics-service/tests/` | ✅ `apps/analytics-service/observability/` |
| **orchestrator**      | ✅ `apps/orchestrator/src/`      | ✅ `apps/orchestrator/db/`      | ✅ `apps/orchestrator/deploy/`      | ✅ `apps/orchestrator/Dockerfile`      | ✅ `apps/orchestrator/tests/`      | ✅ `apps/orchestrator/observability/`      |
| **router-service**    | ✅ `apps/router-service/src/`    | ✅ `apps/router-service/db/`    | ✅ `apps/router-service/deploy/`    | ✅ `apps/router-service/Dockerfile`    | ✅ `apps/router-service/tests/`    | ✅ `apps/router-service/observability/`    |
| **realtime**          | ✅ `apps/realtime/src/`          | ✅ `apps/realtime/db/`          | ✅ `apps/realtime/deploy/`          | ✅ `apps/realtime/Dockerfile`          | ✅ `apps/realtime/tests/`          | ✅ `apps/realtime/observability/`          |
| **ingestion**         | ✅ `apps/ingestion/src/`         | ✅ `apps/ingestion/db/`         | ✅ `apps/ingestion/deploy/`         | ✅ `apps/ingestion/Dockerfile`         | ✅ `apps/ingestion/tests/`         | ✅ `apps/ingestion/observability/`         |
| **billing-service**   | ✅ `apps/billing-service/src/`   | ✅ `apps/billing-service/db/`   | ✅ `apps/billing-service/deploy/`   | ✅ `apps/billing-service/Dockerfile`   | ✅ `apps/billing-service/tests/`   | ✅ `apps/billing-service/observability/`   |
| **tenant-service**    | ✅ `apps/tenant-service/src/`    | ✅ `apps/tenant-service/db/`    | ✅ `apps/tenant-service/deploy/`    | ✅ `apps/tenant-service/Dockerfile`    | ✅ `apps/tenant-service/tests/`    | ✅ `apps/tenant-service/observability/`    |
| **chat-adapters**     | ✅ `apps/chat-adapters/src/`     | ✅ `apps/chat-adapters/db/`     | ✅ `apps/chat-adapters/deploy/`     | ✅ `apps/chat-adapters/Dockerfile`     | ✅ `apps/chat-adapters/tests/`     | ✅ `apps/chat-adapters/observability/`     |
| **tool-service**      | ✅ `apps/tool-service/src/`      | ✅ `apps/tool-service/db/`      | ✅ `apps/tool-service/deploy/`      | ✅ `apps/tool-service/Dockerfile`      | ✅ `apps/tool-service/tests/`      | ✅ `apps/tool-service/observability/`      |
| **eval-service**      | ✅ `apps/eval-service/src/`      | ✅ `apps/eval-service/db/`      | ✅ `apps/eval-service/deploy/`      | ✅ `apps/eval-service/Dockerfile`      | ✅ `apps/eval-service/tests/`      | ✅ `apps/eval-service/observability/`      |
| **capacity-monitor**  | ✅ `apps/capacity-monitor/src/`  | ✅ `apps/capacity-monitor/db/`  | ✅ `apps/capacity-monitor/deploy/`  | ✅ `apps/capacity-monitor/Dockerfile`  | ✅ `apps/capacity-monitor/tests/`  | ✅ `apps/capacity-monitor/observability/`  |

### **Frontend Projects (Need Migration)**

| Service          | Type             | Current Code         | Target Structure                    |
| ---------------- | ---------------- | -------------------- | ----------------------------------- |
| **web**          | Frontend (React) | `web/`               | `apps/web/` with frontend structure |
| **admin-portal** | Frontend (React) | `apps/admin-portal/` | Migrate to frontend structure       |

## 🎯 **Target Per-Service Layout**

### **Backend Services (Standard)**

```
apps/<service-name>/
├── src/                    # Source code
├── db/                     # Database migrations
├── contracts/              # OpenAPI specs
├── deploy/                 # Kubernetes manifests
├── observability/          # Dashboards, SLOs, runbooks
├── tests/                  # Unit & integration tests
├── .github/workflows/      # CI/CD
├── Dockerfile
├── Makefile
├── README.md
├── requirements.txt
└── requirements-dev.txt
```

### **Frontend Projects (Standard)**

```
apps/<frontend-name>/
├── src/                    # Source code
├── public/                 # Static assets
├── deploy/                 # Kubernetes manifests
├── tests/                  # Unit & E2E tests
├── .github/workflows/      # CI/CD
├── Dockerfile
├── Makefile
├── README.md
├── package.json
└── package-lock.json
```

## 🚀 **Commit Sequence (Atomic Steps)**

### **COMMIT 1: Clean Up Legacy Duplicates**

**Scope**: Remove verified legacy backups

```bash
# Remove legacy backup after verification
rm -rf apps/api-gateway_legacy/
```

**Rollback**: `git revert HEAD` (backup still in git history)

### **COMMIT 2: Redistribute Legacy Dockerfiles**

**Scope**: Move `infra/dockerfiles/` to individual services

```bash
# Move service-specific Dockerfiles (if not already present)
mv infra/dockerfiles/Dockerfile.analytics-service apps/analytics-service/Dockerfile.legacy
mv infra/dockerfiles/Dockerfile.api-gateway apps/api-gateway/Dockerfile.legacy
# ... (for each service)
```

**Rollback**: `git revert HEAD && mkdir -p infra/dockerfiles`

### **COMMIT 3: Redistribute Global Observability**

**Scope**: Move `observability/` assets to individual services

```bash
# Move shared observability to platform
mv observability/ platform/shared-observability/
# Service-specific assets already in place
```

**Rollback**: `git revert HEAD && mv platform/shared-observability/ observability/`

### **COMMIT 4: Migrate Frontend - Web**

**Scope**: Restructure `web/` to microservices standard

```bash
# Create standard frontend structure
mkdir -p apps/web-frontend/{src,public,deploy,tests,.github/workflows}
mv web/* apps/web-frontend/src/ || true
mv web/public/* apps/web-frontend/public/ || true
# Create frontend-specific files (Dockerfile, Makefile, README)
```

**Rollback**: `git revert HEAD && mkdir web`

### **COMMIT 5: Migrate Frontend - Admin Portal**

**Scope**: Restructure `apps/admin-portal/` to microservices standard

```bash
# Restructure admin-portal
mkdir -p apps/admin-portal/{src,public,deploy,tests,.github/workflows}
mv apps/admin-portal/main.py apps/admin-portal/src/
# Create frontend-specific files
```

**Rollback**: `git revert HEAD`

### **COMMIT 6: Move Docker Compose Files**

**Scope**: Move to platform infrastructure

```bash
# Move compose files to platform
mv docker-compose*.yml platform/compose/
```

**Rollback**: `git revert HEAD && mv platform/compose/*.yml ./`

### **COMMIT 7: Clean Up Root-Level Test Files**

**Scope**: Move global test files to platform

```bash
# Move global test files
mv test_*.py platform/integration-tests/
mv pytest.ini platform/integration-tests/
mv .pytest_cache platform/integration-tests/ || true
```

**Rollback**: `git revert HEAD && mv platform/integration-tests/test_* ./`

### **COMMIT 8: Update Import Paths**

**Scope**: Fix any remaining import statements

```bash
# Run automated import path updates
python scripts/fix_imports.py
```

**Rollback**: `git revert HEAD`

### **COMMIT 9: Update CI/CD Workflows**

**Scope**: Update paths in GitHub Actions

```bash
# Update workflow paths to match new structure
# Edit .github/workflows/platform-ci.yaml
```

**Rollback**: `git revert HEAD`

### **COMMIT 10: Final Cleanup**

**Scope**: Remove empty directories and unused assets

```bash
# Clean up empty directories
find . -type d -empty -delete
```

**Rollback**: `git revert HEAD`

## ⚠️ **Risk Assessment**

| Risk Level | Description            | Mitigation                              |
| ---------- | ---------------------- | --------------------------------------- |
| **LOW**    | Backend services       | ✅ Already migrated and tested          |
| **MEDIUM** | Frontend restructuring | Create backup branches before migration |
| **LOW**    | Docker Compose paths   | Update documentation with new paths     |
| **LOW**    | CI/CD path updates     | Test workflows in feature branch        |

## 📈 **Progress Status**

- ✅ **12/12 Backend Services**: Fully migrated to microservices standard
- 🔄 **2/2 Frontend Projects**: Need migration to frontend standard
- ✅ **Platform Assets**: Moved to appropriate locations
- 🔄 **Legacy Cleanup**: Ready for final cleanup

## 🎯 **Expected Outcome**

After completion:

- **14 independently deployable services** (12 backend + 2 frontend)
- **Zero duplicate directories**
- **Consistent microservices structure**
- **Path-filtered CI/CD for all services**
- **Clean separation of concerns**
