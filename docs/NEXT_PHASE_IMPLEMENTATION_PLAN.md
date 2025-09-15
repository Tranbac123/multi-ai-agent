# NEXT-PHASE Implementation Plan

## 🎯 **Overview**

This document outlines the detailed implementation plan for the 8 NEXT-PHASE commits to transform the Multi-Tenant AIaaS Platform into an enterprise-grade, globally-distributed system with advanced governance, security, and scalability features.

## 📊 **Current Platform Status**

### ✅ **Completed Foundation**

- **8 Core Services**: API Gateway, Orchestrator, Router, Realtime, Analytics, Billing, Ingestion, Chat Adapters
- **Multi-Tenant Architecture**: RLS-based tenant isolation with comprehensive security
- **Event-Driven Design**: NATS JetStream with event sourcing and Saga patterns
- **Production Testing**: 1000+ tests across 10 categories with quality gates
- **Observability**: OTEL + Prometheus + Grafana integration
- **CI/CD Pipeline**: GitHub Actions with automated quality gates

### ❌ **Missing NEXT-PHASE Features**

- **Multi-Region Deployment**: Data residency and regional isolation
- **Advanced Fairness**: Per-tenant concurrency and priority management
- **Cost Governance**: Budget protection and drift detection
- **Enhanced Privacy**: Advanced PII/DLP and encryption
- **Tail-Latency Control**: Request hedging and timeout optimization
- **Supply-Chain Security**: SBOM, signing, and provenance
- **Self-Serve Management**: Tenant lifecycle and plan management

---

## 🗺️ **Implementation Roadmap**

### **COMMIT 1 - Data Residency & Regionalization**

**Priority**: HIGH | **Estimated Time**: 2-3 days | **Dependencies**: None

#### **Scope & Objectives**

Implement per-tenant data residency controls with regional provider selection and cross-region access enforcement.

#### **Detailed Tasks**

##### **1.1 Database Schema Updates**

```sql
-- Add regional configuration to tenants table
ALTER TABLE tenants ADD COLUMN data_region VARCHAR(50) NOT NULL DEFAULT 'us-east-1';
ALTER TABLE tenants ADD COLUMN allowed_regions TEXT[] DEFAULT ARRAY['us-east-1'];
ALTER TABLE tenants ADD COLUMN regional_config JSONB DEFAULT '{}';

-- Create regional providers table
CREATE TABLE regional_providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    region VARCHAR(50) NOT NULL,
    provider_type VARCHAR(50) NOT NULL, -- 'llm', 'vector', 'storage'
    provider_name VARCHAR(100) NOT NULL,
    endpoint_url TEXT NOT NULL,
    credentials JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Add regional partitioning for analytics
CREATE TABLE analytics_events_regional (
    LIKE analytics_events INCLUDING ALL
) PARTITION BY LIST (data_region);
```

##### **1.2 RegionRouter Implementation**

```python
# apps/api-gateway/core/region_router.py
class RegionRouter:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.regional_providers = {}

    async def get_tenant_region(self, tenant_id: str) -> str:
        """Get tenant's data region from database."""

    async def select_provider(self, tenant_id: str, provider_type: str) -> ProviderConfig:
        """Select region-specific provider based on tenant policy."""

    async def enforce_regional_access(self, tenant_id: str, resource_region: str) -> bool:
        """Enforce cross-region access policies."""
```

##### **1.3 Header Propagation**

```python
# libs/middleware/regional_middleware.py
class RegionalMiddleware:
    async def __call__(self, request: Request, call_next):
        # Extract tenant from JWT
        tenant_id = get_tenant_from_jwt(request)
        region = await region_router.get_tenant_region(tenant_id)

        # Add regional headers
        request.state.data_region = region
        response = await call_next(request)
        response.headers["X-Data-Region"] = region
        return response
```

##### **1.4 Regional Analytics Setup**

```python
# apps/analytics_service/core/regional_analytics.py
class RegionalAnalyticsEngine:
    def __init__(self):
        self.regional_read_replicas = {}

    async def setup_regional_replicas(self):
        """Setup read replicas per region."""

    async def route_analytics_query(self, tenant_id: str, query: str):
        """Route analytics queries to appropriate regional replica."""
```

#### **Acceptance Criteria**

- [ ] Tenant in `ap-southeast-1` cannot read `eu-west-1` artifacts
- [ ] Dashboards show request counts by region
- [ ] Traces include `tenant_id` + `region` attributes
- [ ] Regional provider selection works correctly
- [ ] Cross-region access is properly denied

#### **Files to Create/Modify**

- `data-plane/migrations/006_regional_schema.py`
- `apps/api-gateway/core/region_router.py`
- `libs/middleware/regional_middleware.py`
- `apps/analytics_service/core/regional_analytics.py`
- `tests/integration/regional/test_data_residency.py`

---

### **COMMIT 2 - Fairness & Isolation: Per-tenant Concurrency**

**Priority**: HIGH | **Estimated Time**: 3-4 days | **Dependencies**: COMMIT 1

#### **Scope & Objectives**

Implement per-tenant concurrency tokens, weighted fair queuing, and overload protection with graceful degradation.

#### **Detailed Tasks**

##### **2.1 Concurrency Token System**

```python
# apps/api-gateway/core/concurrency_manager.py
class ConcurrencyManager:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.token_pools = {}  # Per-tenant token pools

    async def acquire_token(self, tenant_id: str, plan: str) -> bool:
        """Acquire concurrency token for tenant based on plan limits."""

    async def release_token(self, tenant_id: str):
        """Release concurrency token when request completes."""

    async def get_tenant_limits(self, tenant_id: str) -> ConcurrencyLimits:
        """Get tenant's concurrency limits based on plan."""
```

##### **2.2 Weighted Fair Queuing**

```python
# apps/api-gateway/core/fair_scheduler.py
class WeightedFairScheduler:
    def __init__(self):
        self.queues = {}  # Per-tenant queues
        self.weights = {"free": 1, "pro": 3, "enterprise": 10}

    async def schedule_request(self, tenant_id: str, request: Request) -> bool:
        """Schedule request with weighted fair queuing."""

    async def process_next_request(self) -> Optional[Request]:
        """Process next request based on weighted scheduling."""
```

##### **2.3 Pre-admission Checks**

```python
# apps/api-gateway/middleware/admission_control.py
class AdmissionControlMiddleware:
    async def __call__(self, request: Request, call_next):
        tenant_id = get_tenant_from_request(request)

        # Check concurrency limits
        if not await concurrency_manager.acquire_token(tenant_id):
            return JSONResponse(
                status_code=429,
                content={"error": "Tenant concurrency limit exceeded"}
            )

        # Check budget limits
        if not await budget_manager.check_tenant_budget(tenant_id):
            return JSONResponse(
                status_code=402,
                content={"error": "Tenant budget exceeded"}
            )

        return await call_next(request)
```

##### **2.4 Overload Degrade Switches**

```python
# apps/orchestrator/core/degradation_manager.py
class DegradationManager:
    def __init__(self):
        self.degrade_switches = {
            "verbose_critique": True,
            "debate_mode": True,
            "context_size": "full",
            "llm_tier": "premium"
        }

    async def check_system_load(self) -> SystemLoad:
        """Check current system load metrics."""

    async def apply_degradation(self, load_level: SystemLoad):
        """Apply degradation based on system load."""
```

#### **Acceptance Criteria**

- [ ] Premium tenants keep p95 < target while free tier sheds load
- [ ] Degrade switches reduce p95 and cost at >80% CPU without errors
- [ ] Metrics show `tenant_queue_depth`, `tenant_tokens_in_flight`, `dropped_due_to_overload`
- [ ] Weighted fair queuing prevents starvation

#### **Files to Create/Modify**

- `apps/api-gateway/core/concurrency_manager.py`
- `apps/api-gateway/core/fair_scheduler.py`
- `apps/api-gateway/middleware/admission_control.py`
- `apps/orchestrator/core/degradation_manager.py`
- `observability/dashboards/tenant_fairness.json`

---

### **COMMIT 3 - CostGuard: Budget Protection**

**Priority**: HIGH | **Estimated Time**: 2-3 days | **Dependencies**: COMMIT 2

#### **Scope & Objectives**

Implement per-tenant budget controls, cost ceiling enforcement, and drift detection with automatic alerts.

#### **Detailed Tasks**

##### **3.1 Budget Management Schema**

```sql
-- Add budget controls to tenants
ALTER TABLE tenants ADD COLUMN monthly_budget_usd DECIMAL(10,2) DEFAULT 100.00;
ALTER TABLE tenants ADD COLUMN max_request_cost_usd DECIMAL(6,4) DEFAULT 0.50;
ALTER TABLE tenants ADD COLUMN budget_alert_threshold DECIMAL(5,2) DEFAULT 80.00;

-- Create budget tracking table
CREATE TABLE tenant_budgets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    month_year VARCHAR(7) NOT NULL, -- '2024-01'
    allocated_budget DECIMAL(10,2) NOT NULL,
    spent_amount DECIMAL(10,2) DEFAULT 0.00,
    projected_spend DECIMAL(10,2) DEFAULT 0.00,
    alert_sent BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

##### **3.2 Cost Ceiling Enforcement**

```python
# apps/router_service/core/cost_guard.py
class CostGuard:
    def __init__(self, billing_client: BillingClient):
        self.billing = billing_client
        self.cost_models = {}

    async def check_request_cost(self, tenant_id: str, request: Request) -> CostCheck:
        """Check if request exceeds tenant's cost ceiling."""

    async def estimate_request_cost(self, request: Request) -> float:
        """Estimate cost of processing request."""

    async def enforce_cost_ceiling(self, tenant_id: str, estimated_cost: float) -> bool:
        """Enforce cost ceiling for tenant."""
```

##### **3.3 Drift Detection Job**

```python
# apps/billing_service/core/drift_detector.py
class DriftDetector:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def run_nightly_drift_check(self):
        """Run nightly comparison of expected vs actual costs."""

    async def calculate_cost_drift(self, tenant_id: str) -> DriftReport:
        """Calculate cost drift for tenant."""

    async def send_drift_alert(self, tenant_id: str, drift_report: DriftReport):
        """Send alert if drift exceeds threshold."""
```

##### **3.4 Safe Mode Implementation**

```python
# apps/router_service/core/safe_mode.py
class SafeModeManager:
    def __init__(self):
        self.safe_mode_configs = {
            "strict_json": {"llm_tier": "SLM_A", "context_size": "minimal"},
            "simple_qa": {"llm_tier": "SLM_A", "context_size": "small"},
            "complex_reasoning": {"llm_tier": "SLM_B", "context_size": "medium"}
        }

    async def apply_safe_mode(self, tenant_id: str, task_type: str):
        """Apply safe mode configuration based on task type."""
```

#### **Acceptance Criteria**

- [ ] Router switches to cheaper tier on price drift and raises alert
- [ ] Dashboards show budget burn and expected-vs-actual deltas
- [ ] Cost ceilings prevent overspending
- [ ] Safe mode reduces costs without breaking SLAs

#### **Files to Create/Modify**

- `data-plane/migrations/007_budget_schema.py`
- `apps/router_service/core/cost_guard.py`
- `apps/billing_service/core/drift_detector.py`
- `apps/router_service/core/safe_mode.py`
- `observability/dashboards/cost_governance.json`

---

### **COMMIT 4 - Privacy & DLP: Advanced Protection**

**Priority**: MEDIUM | **Estimated Time**: 4-5 days | **Dependencies**: COMMIT 3

#### **Scope & Objectives**

Implement comprehensive PII detection, field-level encryption, and cross-tenant leakage prevention.

#### **Detailed Tasks**

##### **4.1 PII Detection System**

```python
# libs/security/pii_detector.py
class PIIDetector:
    def __init__(self):
        self.detectors = {
            "email": EmailDetector(),
            "phone": PhoneDetector(),
            "credit_card": CreditCardDetector(),
            "ssn": SSNDetector(),
            "government_id": GovernmentIDDetector()
        }

    async def detect_pii(self, text: str) -> List[PIIToken]:
        """Detect PII in text with confidence scores."""

    async def redact_pii(self, text: str, policy: PIIPolicy) -> str:
        """Redact PII based on tenant policy."""
```

##### **4.2 Field-Level Encryption**

```python
# libs/security/encryption.py
class FieldEncryption:
    def __init__(self, kms_client):
        self.kms = kms_client
        self.dek_cache = {}

    async def encrypt_field(self, data: str, field_name: str) -> EncryptedData:
        """Encrypt sensitive field using envelope encryption."""

    async def decrypt_field(self, encrypted_data: EncryptedData) -> str:
        """Decrypt field using envelope encryption."""

    async def rotate_dek(self, field_name: str):
        """Rotate Data Encryption Key for field."""
```

##### **4.3 Sensitivity Tagging**

```python
# apps/ingestion/core/sensitivity_tagger.py
class SensitivityTagger:
    def __init__(self, pii_detector: PIIDetector):
        self.pii_detector = pii_detector
        self.sensitivity_levels = ["public", "internal", "confidential", "restricted"]

    async def tag_document(self, document: Document) -> SensitivityTag:
        """Tag document with appropriate sensitivity level."""

    async def enforce_access_policy(self, tenant_id: str, document: Document) -> bool:
        """Enforce access policy based on sensitivity and tenant."""
```

##### **4.4 Cross-Tenant Leakage Prevention**

```python
# apps/ingestion/core/leakage_prevention.py
class LeakagePrevention:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def validate_rag_query(self, tenant_id: str, query: str) -> ValidationResult:
        """Validate RAG query for cross-tenant leakage."""

    async def filter_search_results(self, tenant_id: str, results: List[Document]) -> List[Document]:
        """Filter search results to prevent cross-tenant data leakage."""
```

#### **Acceptance Criteria**

- [ ] Contract tests prove PII is redacted in logs and responses
- [ ] KMS-backed key rotation test passes (old DEKs decrypt historical rows)
- [ ] Cross-tenant leakage prevention works in RAG queries
- [ ] Sensitivity tagging is applied correctly in ingestion

#### **Files to Create/Modify**

- `libs/security/pii_detector.py`
- `libs/security/encryption.py`
- `apps/ingestion/core/sensitivity_tagger.py`
- `apps/ingestion/core/leakage_prevention.py`
- `tests/security/test_pii_detection.py`
- `tests/security/test_encryption.py`

---

### **COMMIT 5 - Tail-latency Control: Request Hedging**

**Priority**: MEDIUM | **Estimated Time**: 3-4 days | **Dependencies**: COMMIT 4

#### **Scope & Objectives**

Implement request hedging with coordinated cancellation and timeout enforcement for improved tail latency.

#### **Detailed Tasks**

##### **5.1 Request Hedging Implementation**

```python
# libs/clients/hedged_client.py
class HedgedHTTPClient:
    def __init__(self, base_timeout: float = 5.0, hedge_delay: float = 1.0):
        self.base_timeout = base_timeout
        self.hedge_delay = hedge_delay
        self.active_requests = {}

    async def hedged_request(self, url: str, **kwargs) -> Response:
        """Make hedged request with coordinated cancellation."""

    async def _make_hedge_request(self, url: str, request_id: str, **kwargs):
        """Make individual hedge request."""

    async def _cancel_other_requests(self, request_id: str, winner_response: Response):
        """Cancel other hedge requests when one succeeds."""
```

##### **5.2 Timeout Enforcement**

```python
# apps/orchestrator/core/timeout_manager.py
class TimeoutManager:
    def __init__(self):
        self.workflow_timeouts = {
            "simple_qa": 5.0,
            "complex_reasoning": 30.0,
            "document_processing": 60.0,
            "multi_step_workflow": 120.0
        }

    async def enforce_workflow_timeout(self, workflow_type: str, coro: Coroutine):
        """Enforce timeout for workflow step."""

    async def attach_timeout_to_trace(self, trace_id: str, timeout: float):
        """Attach timeout information to trace."""
```

##### **5.3 Idempotency Preservation**

```python
# libs/utils/idempotency.py
class IdempotencyManager:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    async def preserve_idempotency(self, request_id: str, operation: str):
        """Preserve idempotency key across hedged requests."""

    async def get_idempotency_result(self, request_id: str) -> Optional[Any]:
        """Get cached result for idempotency key."""
```

##### **5.4 Metrics Collection**

```python
# observability/metrics/hedging_metrics.py
class HedgingMetrics:
    def __init__(self):
        self.hedged_requests_total = Counter("hedged_requests_total")
        self.hedge_wins_total = Counter("hedge_wins_total")
        self.hedge_latency = Histogram("hedge_latency_seconds")

    def record_hedged_request(self, endpoint: str):
        """Record hedged request metric."""

    def record_hedge_win(self, endpoint: str, latency: float):
        """Record hedge win metric."""
```

#### **Acceptance Criteria**

- [ ] Under induced 99th-percentile slowness, p99 latency improves ≥30%
- [ ] Minimal extra cost from hedging (< 5% overhead)
- [ ] Idempotency keys preserved across hedged requests
- [ ] Metrics show hedging effectiveness

#### **Files to Create/Modify**

- `libs/clients/hedged_client.py`
- `apps/orchestrator/core/timeout_manager.py`
- `libs/utils/idempotency.py`
- `observability/metrics/hedging_metrics.py`
- `tests/performance/test_hedging.py`

---

### **COMMIT 6 - Multi-region Active-Active & DR**

**Priority**: HIGH | **Estimated Time**: 4-5 days | **Dependencies**: COMMIT 5

#### **Scope & Objectives**

Implement multi-region active-active deployment with disaster recovery capabilities and automated failover.

#### **Detailed Tasks**

##### **6.1 NATS Cross-Region Mirroring**

```yaml
# infra/k8s/helm/nats-cluster/templates/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: nats-cluster-config
data:
  nats.conf: |
    server_name: nats-{{ .Values.region }}
    cluster {
      name: global-cluster
      routes: [
        nats://nats-eu-west-1:6222
        nats://nats-us-east-1:6222
        nats://nats-ap-southeast-1:6222
      ]
    }
    jetstream {
      store_dir: /data
      max_memory: 1GB
      max_file: 10GB
      sync: true
    }
```

##### **6.2 Postgres Logical Replication**

```sql
-- Setup logical replication slots
SELECT pg_create_logical_replication_slot('region_replication', 'pgoutput');

-- Create publication for cross-region replication
CREATE PUBLICATION region_publication FOR ALL TABLES;

-- Configure replica for receiving changes
-- (On replica region)
CREATE SUBSCRIPTION region_subscription
CONNECTION 'host=primary-region port=5432 dbname=multitenant user=replicator'
PUBLICATION region_publication
WITH (copy_data = true);
```

##### **6.3 Health-Checked Failover**

```python
# apps/api-gateway/core/region_failover.py
class RegionFailover:
    def __init__(self):
        self.regions = ["us-east-1", "eu-west-1", "ap-southeast-1"]
        self.region_health = {}
        self.sticky_sessions = {}

    async def check_region_health(self, region: str) -> HealthStatus:
        """Check health of region services."""

    async def initiate_failover(self, failed_region: str):
        """Initiate failover to healthy region."""

    async def update_sticky_sessions(self, tenant_id: str, new_region: str):
        """Update tenant's sticky session to new region."""
```

##### **6.4 DR Drill Automation**

```python
# scripts/dr_drill.py
class DRDrill:
    def __init__(self):
        self.regions = ["us-east-1", "eu-west-1", "ap-southeast-1"]

    async def run_dr_drill(self):
        """Run complete disaster recovery drill."""

    async def simulate_region_failure(self, region: str):
        """Simulate region failure for testing."""

    async def validate_failover(self, failed_region: str) -> DrillResult:
        """Validate failover meets RTO/RPO targets."""
```

##### **6.5 DR Runbooks**

```markdown
# docs/runbooks/DISASTER_RECOVERY.md

## Disaster Recovery Procedures

### RTO/RPO Targets

- RTO (Recovery Time Objective): 5 minutes
- RPO (Recovery Point Objective): 30 seconds

### Failover Procedures

1. Detect region failure
2. Update DNS/load balancer configuration
3. Redirect traffic to healthy regions
4. Validate service health
5. Monitor for issues

### Recovery Procedures

1. Restore failed region
2. Sync data from active regions
3. Validate data consistency
4. Gradually restore traffic
5. Monitor system stability
```

#### **Acceptance Criteria**

- [ ] DR drill script passes: region A taken down → region B serves traffic within RTO/RPO
- [ ] Cross-region NATS mirroring works correctly
- [ ] Postgres logical replication maintains consistency
- [ ] Health-checked failover works automatically

#### **Files to Create/Modify**

- `infra/k8s/helm/nats-cluster/templates/configmap.yaml`
- `data-plane/migrations/008_replication_setup.sql`
- `apps/api-gateway/core/region_failover.py`
- `scripts/dr_drill.py`
- `docs/runbooks/DISASTER_RECOVERY.md`
- `.github/workflows/dr-drill.yml`

---

### **COMMIT 7 - Supply-chain Security & Provenance**

**Priority**: MEDIUM | **Estimated Time**: 2-3 days | **Dependencies**: COMMIT 6

#### **Scope & Objectives**

Implement comprehensive supply-chain security with SBOM generation, image signing, and CVE scanning.

#### **Detailed Tasks**

##### **7.1 SBOM Generation with Syft**

```yaml
# .github/workflows/security.yml
name: Supply Chain Security
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  sbom-generation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Generate SBOM with Syft
        uses: anchore/sbom-action@v0
        with:
          path: .
          format: spdx-json
          output-file: sbom.spdx.json

      - name: Upload SBOM
        uses: actions/upload-artifact@v3
        with:
          name: sbom
          path: sbom.spdx.json
```

##### **7.2 Image Signing with Cosign**

```yaml
# .github/workflows/build-and-sign.yml
name: Build and Sign Images
on:
  push:
    tags: ["v*"]

jobs:
  build-and-sign:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: |
          docker build -t ${{ github.repository }}:${{ github.ref_name }} .

      - name: Sign image with Cosign
        uses: sigstore/cosign-installer@v2

      - name: Sign the image
        run: |
          cosign sign --yes ${{ github.repository }}:${{ github.ref_name }}
```

##### **7.3 CVE Scanning with Trivy**

```yaml
# .github/workflows/vulnerability-scan.yml
name: Vulnerability Scan
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  trivy-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: "multitenant:latest"
          format: "sarif"
          output: "trivy-results.sarif"

      - name: Upload Trivy scan results
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: "trivy-results.sarif"
```

##### **7.4 SLSA Provenance**

```yaml
# .github/workflows/slsa-provenance.yml
name: SLSA Provenance
on:
  push:
    tags: ["v*"]

jobs:
  provenance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Generate SLSA provenance
        uses: slsa-framework/slsa-github-generator/.github/workflows/generator_generic_slsa3.yml@v1.9.0
        with:
          base64-subjects: "${{ hashFiles('**/Dockerfile') }}"
          upload-assets: true
```

##### **7.5 Base Image Pinning**

```dockerfile
# Dockerfile.api
# Pin base image with specific digest
FROM python:3.11-slim@sha256:abc123...def456

# Pin all package versions
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Security scanning
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*
```

#### **Acceptance Criteria**

- [ ] CI fails on unsigned images or critical CVEs
- [ ] SBOMs attached to all releases
- [ ] SLSA level evidence recorded per build
- [ ] Base images pinned with digests

#### **Files to Create/Modify**

- `.github/workflows/security.yml`
- `.github/workflows/build-and-sign.yml`
- `.github/workflows/vulnerability-scan.yml`
- `.github/workflows/slsa-provenance.yml`
- `Dockerfile.api` (update with pinned images)
- `SECURITY.md` (update with security policies)

---

### **COMMIT 8 - Self-serve Plans & Lifecycle Hooks**

**Priority**: LOW | **Estimated Time**: 3-4 days | **Dependencies**: COMMIT 7

#### **Scope & Objectives**

Implement self-serve tenant management with plan selection, upgrades, and lifecycle automation.

#### **Detailed Tasks**

##### **8.1 Tenant Signup Flow**

```python
# apps/api-gateway/routes/tenant_management.py
class TenantManagementAPI:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    @router.post("/signup")
    async def create_tenant_signup(self, signup_data: TenantSignupRequest):
        """Create new tenant with verification."""

    @router.post("/verify")
    async def verify_tenant(self, verification_data: VerificationRequest):
        """Verify tenant email/domain."""

    @router.post("/plan/select")
    async def select_plan(self, tenant_id: str, plan_data: PlanSelectionRequest):
        """Select initial plan for tenant."""
```

##### **8.2 Plan Upgrade System**

```python
# apps/billing_service/core/plan_manager.py
class PlanManager:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def upgrade_plan(self, tenant_id: str, new_plan: str) -> UpgradeResult:
        """Upgrade tenant plan with proration."""

    async def calculate_proration(self, tenant_id: str, new_plan: str) -> ProrationDetails:
        """Calculate proration for plan upgrade."""

    async def process_plan_change(self, tenant_id: str, plan_change: PlanChange):
        """Process plan change and update quotas."""
```

##### **8.3 Trial Management**

```python
# apps/billing_service/core/trial_manager.py
class TrialManager:
    def __init__(self, feature_flags: FeatureFlagManager):
        self.feature_flags = feature_flags

    async def start_trial(self, tenant_id: str, trial_type: str) -> Trial:
        """Start trial period for tenant."""

    async def check_trial_expiry(self, tenant_id: str) -> TrialStatus:
        """Check if trial is expired and needs conversion."""

    async def convert_trial(self, tenant_id: str, plan: str) -> ConversionResult:
        """Convert trial to paid plan."""
```

##### **8.4 Webhook System**

```python
# apps/billing_service/core/webhook_manager.py
class WebhookManager:
    def __init__(self, http_client: AsyncClient):
        self.http_client = http_client

    async def send_plan_changed_webhook(self, tenant_id: str, plan_change: PlanChange):
        """Send webhook when tenant plan changes."""

    async def send_trial_expired_webhook(self, tenant_id: str):
        """Send webhook when trial expires."""

    async def send_quota_exceeded_webhook(self, tenant_id: str, quota_type: str):
        """Send webhook when quota is exceeded."""
```

##### **8.5 Admin Portal**

```typescript
// web/src/components/admin/TenantManagement.tsx
export const TenantManagement: React.FC = () => {
  const [tenants, setTenants] = useState<Tenant[]>([]);

  const handlePlanOverride = async (tenantId: string, newPlan: string) => {
    // Handle admin plan override
  };

  const handleImpersonation = async (tenantId: string) => {
    // Handle admin impersonation
  };

  return (
    <div className="tenant-management">
      {/* Admin interface for tenant management */}
    </div>
  );
};
```

##### **8.6 Audit Logging**

```python
# libs/audit/audit_logger.py
class AuditLogger:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def log_plan_change(self, tenant_id: str, old_plan: str, new_plan: str, admin_id: str):
        """Log plan change for audit trail."""

    async def log_admin_action(self, admin_id: str, action: str, target: str):
        """Log admin actions for audit."""

    async def log_impersonation(self, admin_id: str, target_tenant_id: str):
        """Log admin impersonation."""
```

#### **Acceptance Criteria**

- [ ] E2E: create trial → upgrade to pro → quotas & weights update live
- [ ] Audit logs recorded for all admin actions
- [ ] Webhooks fire correctly for plan changes
- [ ] Admin portal allows overrides and impersonation

#### **Files to Create/Modify**

- `apps/api-gateway/routes/tenant_management.py`
- `apps/billing_service/core/plan_manager.py`
- `apps/billing_service/core/trial_manager.py`
- `apps/billing_service/core/webhook_manager.py`
- `web/src/components/admin/TenantManagement.tsx`
- `libs/audit/audit_logger.py`
- `tests/e2e/test_tenant_lifecycle.py`

---

## 📅 **Implementation Timeline**

### **Phase 1: Core Infrastructure (Weeks 1-2)**

- **COMMIT 1**: Data Residency & Regionalization
- **COMMIT 2**: Fairness & Isolation

### **Phase 2: Governance & Security (Weeks 3-4)**

- **COMMIT 3**: CostGuard
- **COMMIT 4**: Privacy & DLP

### **Phase 3: Performance & Reliability (Weeks 5-6)**

- **COMMIT 5**: Tail-latency Control
- **COMMIT 6**: Multi-region Active-Active

### **Phase 4: Security & Operations (Weeks 7-8)**

- **COMMIT 7**: Supply-chain Security
- **COMMIT 8**: Self-serve Plans

## 🎯 **Success Metrics**

### **Technical Metrics**

- **RTO/RPO**: < 5 minutes / < 30 seconds
- **Tail Latency**: 30% improvement in p99
- **Cost Efficiency**: 20% reduction through optimization
- **Security**: Zero critical CVEs, 100% signed images

### **Business Metrics**

- **Tenant Satisfaction**: 99%+ uptime SLA
- **Cost Governance**: < 5% budget drift
- **Compliance**: 100% audit trail coverage
- **Scalability**: Support 1000+ concurrent tenants

## 🔧 **Implementation Guidelines**

### **Development Process**

1. **Small Commits**: Each commit should be testable and deployable
2. **Test Coverage**: Minimum 90% test coverage for new code
3. **Documentation**: Update docs with each commit
4. **Monitoring**: Add metrics and dashboards for new features

### **Quality Gates**

1. **Unit Tests**: All new code must have unit tests
2. **Integration Tests**: Cross-service integration tests
3. **Performance Tests**: Load testing for new features
4. **Security Tests**: Security validation for sensitive features

### **Deployment Strategy**

1. **Feature Flags**: Use feature flags for gradual rollout
2. **Canary Deployment**: Deploy to small percentage first
3. **Monitoring**: Watch metrics during deployment
4. **Rollback Plan**: Always have rollback capability

---

**This implementation plan provides a comprehensive roadmap for transforming the Multi-Tenant AIaaS Platform into an enterprise-grade, globally-distributed system with advanced governance, security, and scalability features.**
