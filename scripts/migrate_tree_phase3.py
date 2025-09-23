#!/usr/bin/env python3
import argparse, os, re, shutil, sys, json, textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# === Decisions from user analysis ===
# Note: Services have already been renamed in previous phases
RENAMES = {
    # These renames have already been completed
    # "apps/data-plane/agents": "apps/data-plane/agents-service",
    # "apps/data-plane/tools": "apps/data-plane/tools-service", 
    # "apps/data-plane/memory": "apps/data-plane/memory-service",
}

# Per-service default ports (adjust later if needed)
DEFAULT_PORTS = {
    "agents-service": 8084,
    "tools-service": 8085,
    "memory-service": 8086,
}

OBS_TEMPLATES_DIR = ROOT / "platform" / "observability-templates"

# ---- Scaffolding templates ---------------------------------------------------
OPENAPI_SKELETON = """openapi: 3.0.3
info: { title: PLACEHOLDER, version: "0.1.0" }
paths:
  /healthz: { get: { responses: { "200": { description: ok } } } }
"""

DOCKERFILE_PY = """FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt || true
COPY src ./src
EXPOSE {port}
CMD ["uvicorn","src.main:app","--host","0.0.0.0","--port","{port}"]
"""

REQS_MIN = "fastapi>=0.115.0\\nuvicorn>=0.30.6\\n"

HELM_CHART = """apiVersion: v2
name: {name}
type: application
version: 0.1.0
appVersion: "0.1.0"
"""

HELM_VALUES = """image:
  repository: ghcr.io/OWNER/{name}
  tag: "latest"
  pullPolicy: IfNotPresent
service:
  port: {port}
resources:
  limits: {{ cpu: 300m, memory: 256Mi }}
  requests: {{ cpu: 50m, memory: 128Mi }}
env: []
hpa:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
pdb: {{ minAvailable: 1 }}
"""

HELM_DEPLOY = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
spec:
  replicas: 2
  selector:
    matchLabels:
      app: {name}
  template:
    metadata:
      labels:
        app: {name}
    spec:
      containers:
        - name: app
          image: "{{{{ .Values.image.repository }}}}:{{{{ .Values.image.tag }}}}"
          imagePullPolicy: "{{{{ .Values.image.pullPolicy }}}}"
          ports:
            - containerPort: {{{{ .Values.service.port }}}}
          env:
            {{{{- range .Values.env }}}}
            - name: {{{{ .name }}}}
              value: "{{{{ .value }}}}"
            {{{{- end }}}}
          readinessProbe:
            httpGet:
              path: /healthz
              port: {{{{ .Values.service.port }}}}
            initialDelaySeconds: 3
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /healthz
              port: {{{{ .Values.service.port }}}}
            initialDelaySeconds: 3
            periodSeconds: 5
          resources:
            {{{{- toYaml .Values.resources.limits | nindent 12 }}}}
"""

HELM_SVC = """apiVersion: v1
kind: Service
metadata:
  name: {name}
spec:
  selector:
    app: {name}
  ports:
    - port: 80
      targetPort: {{{{ .Values.service.port }}}}
      name: http
"""

HELM_HPA = """{{{{- if .Values.hpa.enabled }}}}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {name}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {name}
  minReplicas: {{{{ .Values.hpa.minReplicas }}}}
  maxReplicas: {{{{ .Values.hpa.maxReplicas }}}}
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{{{ .Values.hpa.targetCPUUtilizationPercentage }}}}
{{{{- end }}}}
"""

HELM_PDB = """apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {name}
spec:
  minAvailable: {{{{ .Values.pdb.minAvailable }}}}
  selector:
    matchLabels:
      app: {name}
"""

def log(msg): print(msg)
def ensure_dirs(p:Path): p.mkdir(parents=True, exist_ok=True)

def safe_move(src:Path, dst:Path, apply:bool):
    if not src.exists(): return False
    if dst.exists():
        legacy = dst.with_name(dst.name + "-legacy")
        if apply: shutil.move(str(src), str(legacy))
        log(f"  └─ DEST EXISTS, moved '{src}' → '{legacy}'")
        return True
    if apply:
        ensure_dirs(dst.parent); shutil.move(str(src), str(dst))
    log(f"  └─ moved '{src}' → '{dst}'")
    return True

def ensure_obs_templates(apply:bool):
    ensure_dirs(OBS_TEMPLATES_DIR)
    defaults = {
        "dashboards.json": "[]\n",
        "alerts.yaml": textwrap.dedent("""
          groups:
          - name: placeholder
            rules:
            - alert: HighErrorRate
              expr: sum(rate(http_requests_total{status=~"5.."}[5m])) > 0
              for: 2m
              labels: { severity: warning }
              annotations: { summary: "High 5xx rate" }
        """).lstrip(),
        "SLO.md": "# SLO\\n- Latency p95: TBD\\n- Error rate: <1%\\n",
        "runbook.md": "# Runbook\\n1. Check /healthz\\n2. Inspect logs\\n"
    }
    for f,c in defaults.items():
        t = OBS_TEMPLATES_DIR/f
        if not t.exists() and apply:
            t.write_text(c)

def scaffold_service_layout(svc_dir:Path, port:int, apply:bool):
    name = svc_dir.name
    ensure_dirs(svc_dir/"src")
    # contracts
    cpath = svc_dir/"contracts"/"openapi.yaml"
    ensure_dirs(cpath.parent)
    if not cpath.exists() and apply:
        cpath.write_text(OPENAPI_SKELETON.replace("PLACEHOLDER", name))
    # observability
    ensure_dirs(svc_dir/"observability")
    for f in ["dashboards.json","alerts.yaml","SLO.md","runbook.md"]:
        target = svc_dir/"observability"/f
        src = OBS_TEMPLATES_DIR/f
        if not target.exists():
            if src.exists() and apply:
                shutil.copyfile(src, target)
            elif apply:
                target.write_text("TODO")
    # helm
    chart = svc_dir/"deploy"/"helm"/name
    ensure_dirs(chart/"templates")
    if apply:
        (chart/"Chart.yaml").write_text(HELM_CHART.format(name=name))
        (chart/"values.yaml").write_text(HELM_VALUES.format(name=name, port=port))
        (chart/"templates"/"deployment.yaml").write_text(HELM_DEPLOY.format(name=name))
        (chart/"templates"/"service.yaml").write_text(HELM_SVC.format(name=name))
        (chart/"templates"/"hpa.yaml").write_text(HELM_HPA.format(name=name))
        (chart/"templates"/"pdb.yaml").write_text(HELM_PDB.format(name=name))
    # docker + reqs (best effort)
    if apply and not (svc_dir/"Dockerfile").exists():
        (svc_dir/"Dockerfile").write_text(DOCKERFILE_PY.format(port=port))
    if apply and not (svc_dir/"requirements.txt").exists():
        (svc_dir/"requirements.txt").write_text(REQS_MIN)
    # tests placeholder
    ensure_dirs(svc_dir/"tests")
    tf = svc_dir/"tests"/"test_health.py"
    if not tf.exists() and apply:
        tf.write_text("def test_placeholder():\\n    assert True\\n")

def rename_services(apply:bool):
    changed=[]
    for src_str, dst_str in RENAMES.items():
        src = ROOT/src_str
        dst = ROOT/dst_str
        if src.exists():
            log(f"- rename {src} → {dst}")
            safe_move(src, dst, apply)
            port = DEFAULT_PORTS.get(Path(dst).name, 8080)
            scaffold_service_layout(dst, port, apply)
            changed.append(dst)
    return changed

def move_configs_into_services(apply:bool):
    cfg_root = ROOT/"configs"
    if not cfg_root.exists(): return
    # helm charts under apps/**
    charts = [p for p in (ROOT/"apps").rglob("deploy/helm/*/Chart.yaml")]
    for f in cfg_root.rglob("*"):
        if not f.is_file(): continue
        fname = f.name.lower()
        matched=False
        for chart in charts:
            svc = chart.parent.name
            svc_dir = chart.parents[2]
            # heuristic match on filename containing service name
            if re.search(rf"(^|[-_]){re.escape(svc)}([-.]|$)", fname):
                dest = chart.parent/"values-extra.yaml"
                ensure_dirs(dest.parent)
                if apply: shutil.copyfile(f, dest)
                log(f"  cfg {f.name} → {dest}")
                matched=True
                break
        if not matched:
            # keep track for manual triage
            todo = ROOT/"apps"/"control-plane"/"config-service"/"MIGRATION_TODO_UNMATCHED_CONFIGS.json"
            ensure_dirs(todo.parent)
            data = {"unmatched": []}
            if todo.exists():
                try: data = json.loads(todo.read_text())
                except Exception: pass
            if str(f) not in data["unmatched"]:
                data["unmatched"].append(str(f))
                if apply: todo.write_text(json.dumps(data, indent=2))

def migrate_contracts(apply:bool):
    root_contracts = ROOT/"contracts"
    if not root_contracts.exists(): return
    # Build service name list
    service_dirs = [p.parent.parent for p in (ROOT/"apps").rglob("deploy/helm/*/Chart.yaml")]
    map_name_to_dir = {d.name.lower(): d for d in service_dirs}
    # Move files whose stem contains a service name
    for f in list(root_contracts.glob("*.yml")) + list(root_contracts.glob("*.yaml")):
        stem = f.stem.lower()
        target_dir = None
        for svc_name, svc_dir in map_name_to_dir.items():
            if svc_name in stem:
                target_dir = svc_dir; break
        if target_dir:
            dest = target_dir/"contracts"/("openapi.yaml" if f.suffix in [".yml",".yaml"] else f.name)
            ensure_dirs(dest.parent)
            if apply: shutil.move(str(f), str(dest))
            log(f"  contract {f.name} → {dest}")

def organize_monitoring(apply:bool):
    mon_root = ROOT/"monitoring"
    if not mon_root.exists(): return
    plat = mon_root/"platform"
    ensure_dirs(plat)
    # if dashboards.json / alerts.yaml found at root, move to platform/
    for name in ["dashboards.json","alerts.yaml","README.md"]:
        src = mon_root/name
        if src.exists():
            dst = plat/name
            if apply and not dst.exists():
                shutil.move(str(src), str(dst))
            log(f"  monitoring: placed {name} under monitoring/platform/")

def update_workflows_paths(apply:bool):
    wf_dir = ROOT/".github"/"workflows"
    if not wf_dir.exists(): return
    globs = []
    for svc_dir in [p.parent.parent for p in (ROOT/"apps").rglob("deploy/helm/*/Chart.yaml")]:
        rel = svc_dir.relative_to(ROOT).as_posix()
        globs.append(f"{rel}/**")
    for wf in wf_dir.glob("*.y*ml"):
        s = wf.read_text()
        s2 = s
        # replace legacy references if any
        s2 = s2.replace("services/**","apps/**")
        # ensure new service paths are present
        if "paths:" in s2:
            for g in globs:
                if g not in s2:
                    s2 = re.sub(r"(paths:\s*\n)", r"\\1      - "+g+"\\n", s2)
        if apply and s2 != s:
            wf.write_text(s2)
            log(f"  updated workflow paths: {wf.name}")

def main():
    ap = argparse.ArgumentParser(description="Phase-3: rename agents/tools/memory to *-service, relocate configs/contracts, organize monitoring, update CI.")
    ap.add_argument("--apply", action="store_true", help="execute changes (default dry-run)")
    args = ap.parse_args()
    apply = args.apply

    log("=== Ensure observability templates ===")
    ensure_obs_templates(apply)

    log("=== Rename services to *-service ===")
    changed = rename_services(apply)

    log("=== Move configs → per-service Helm values ===")
    move_configs_into_services(apply)

    log("=== Contracts: keep shared at root; move service-specific into each service ===")
    migrate_contracts(apply)

    log("=== Organize monitoring/ (platform-level) ===")
    organize_monitoring(apply)

    log("=== Update CI path filters (.github/workflows) ===")
    update_workflows_paths(apply)

    # Final pass: scaffold observability for all services (skip if corrupted)
    for chart in (ROOT/"apps").rglob("deploy/helm/*/Chart.yaml"):
        svc_dir = chart.parents[2]
        name = svc_dir.name
        port = DEFAULT_PORTS.get(name, 8080)
        # Skip scaffolding for services with corrupted structures
        if "deploy/deploy" in str(chart):
            log(f"  Skipping {name}: corrupted directory structure detected")
            continue
        scaffold_service_layout(svc_dir, port, apply)

    # Summary
    svcs = [p.parent.parent for p in (ROOT/"apps").rglob("deploy/helm/*/Chart.yaml")]
    print("\\n--- SUMMARY ---")
    print(f"Services detected: {len(svcs)}")
    for d in sorted(svcs):
        print(" -", d.relative_to(ROOT))
    print("\\nDry-run complete." if not apply else "\\nApplied. Review git diff then commit.")
    print("Run:  python scripts/migrate_tree_phase3.py --apply")

if __name__ == "__main__":
    main()
