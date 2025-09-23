#!/usr/bin/env python3
import argparse, os, re, shutil, sys, json, textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# === Explicit mapping from your current tree (screenshot) ===
DATA_PLANE_TARGETS = {
    "api-gateway": "api-gateway",
    "orchestrator": "orchestrator",
    "router-service": "router-service",
    "retrieval-service": "retrieval-service",
    "ingestion": "ingestion-service",         # rename
    "mcp-rag": "mcp-rag",
    "realtime": "realtime-gateway",           # rename
    "tool-service": "tool-service",
    "eval-service": "eval-service",
    "chat-adapters": "chat-adapters",
    "analytics-service": "analytics-service",
}

CONTROL_PLANE_TARGETS = {
    "tenant-service": "tenant-service",
    "billing-service": "billing-service",
    "capacity-monitor": "capacity-monitor",
}

# Frontends should live outside apps/
FRONTENDS = {
    "admin-portal": "admin-portal",
    "web-frontend": "web"   # move into root/web/
}

OBS_TEMPLATES_DIR = ROOT / "platform" / "observability-templates"
DEFAULT_PORTS = {
    # reasonable defaults; adjust later per service if needed
    "api-gateway": 8080, "orchestrator": 8080, "router-service": 8080, "retrieval-service": 8080,
    "ingestion-service": 8081, "mcp-rag": 8765, "realtime-gateway": 8079, "tool-service": 8080,
    "eval-service": 8087, "chat-adapters": 8080, "analytics-service": 8080,
    "tenant-service": 8097, "billing-service": 8098, "capacity-monitor": 8099,
}

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

def move(src:Path, dst:Path, apply:bool):
    if not src.exists(): return False
    if dst.exists():
        legacy = dst.with_name(dst.name + "-legacy")
        if apply:
            shutil.move(str(src), str(legacy))
        log(f"  └─ DEST EXISTS, moved '{src}' → '{legacy}'")
        return True
    if apply:
        ensure_dirs(dst.parent)
        shutil.move(str(src), str(dst))
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

def migrate_group(mapping:dict, plane:str, apply:bool):
    moved=[]
    for src_name, dst_name in mapping.items():
        src = ROOT/"apps"/src_name
        dst = ROOT/"apps"/plane/dst_name
        if src.exists():
            log(f"- {src_name} → apps/{plane}/{dst_name}")
            move(src, dst, apply)
            port = DEFAULT_PORTS.get(dst_name, 8080)
            scaffold_service_layout(dst, port, apply)
            moved.append(dst)
    return moved

def migrate_frontends(apply:bool):
    for src_name, target_root in FRONTENDS.items():
        src = ROOT/"apps"/src_name
        if not src.exists(): continue
        dst = ROOT/target_root if target_root else ROOT/src_name
        log(f"- frontend {src_name} → {dst}")
        if dst.exists():
            legacy = dst.with_name(dst.name + "-legacy")
            if apply: shutil.move(str(src), str(legacy))
            log(f"  └─ DEST EXISTS, moved to {legacy}")
        else:
            if apply:
                ensure_dirs(dst.parent)
                shutil.move(str(src), str(dst))

def migrate_contracts(apply:bool):
    root_contracts = ROOT/"contracts"
    if not root_contracts.exists(): return
    # Move service-named openapi to each service if matches
    for f in list(root_contracts.glob("*.yml")) + list(root_contracts.glob("*.yaml")):
        base = f.stem.lower()
        # find service dir under apps/**/<base>
        candidates = [p.parent.parent for p in (ROOT/"apps").rglob(f"deploy/helm/{base}/Chart.yaml")]
        if candidates:
            svc_dir = candidates[0]
            dest = svc_dir/"contracts"/"openapi.yaml"
            ensure_dirs(dest.parent)
            if apply: shutil.move(str(f), str(dest))
            log(f"  contract {f.name} → {dest}")

def update_workflows_paths(apply:bool):
    wf_dir = ROOT/".github"/"workflows"
    if not wf_dir.exists(): return
    globs = []
    for svc_dir in [p.parent.parent for p in (ROOT/"apps").rglob("deploy/helm/*/Chart.yaml")]:
        rel = svc_dir.relative_to(ROOT).as_posix()
        globs.append(f"{rel}/**")
    for wf in wf_dir.glob("*.y*ml"):
        s = wf.read_text()
        s2 = s.replace("services/**","apps/**")
        if "paths:" in s2:
            # append missing per-service paths
            for g in globs:
                if g not in s2:
                    s2 = re.sub(r"(paths:\s*\n)", r"\\1      - "+g+"\\n", s2)
        if apply and s2 != s:
            wf.write_text(s2)
            log(f"  updated workflow paths: {wf.name}")

def main():
    ap = argparse.ArgumentParser(description="Phase-2: migrate remaining services into apps/{data,control}-plane, scaffold per-service, move contracts & frontends, update CI.")
    ap.add_argument("--apply", action="store_true", help="execute changes (default dry-run)")
    args = ap.parse_args()
    apply = args.apply

    log("=== Ensure observability templates ===")
    ensure_obs_templates(apply)

    log("=== Move DATA-PLANE services into apps/data-plane ===")
    dp_moved = migrate_group(DATA_PLANE_TARGETS, "data-plane", apply)

    log("=== Move CONTROL-PLANE services into apps/control-plane ===")
    cp_moved = migrate_group(CONTROL_PLANE_TARGETS, "control-plane", apply)

    log("=== Move frontends out of apps/ → root ===")
    migrate_frontends(apply)

    log("=== Contracts: move per-service OpenAPI from /contracts → each service ===")
    migrate_contracts(apply)

    log("=== Update CI path filters (.github/workflows) ===")
    update_workflows_paths(apply)

    # Summary
    svcs = [p.parent.parent for p in (ROOT/"apps").rglob("deploy/helm/*/Chart.yaml")]
    print("\\n--- SUMMARY ---")
    print(f"Services detected: {len(svcs)}")
    for d in sorted(svcs):
        print(" -", d.relative_to(ROOT))
    print("\\nDry-run complete." if not apply else "\\nApplied. Review git diff then commit.")
    print("Run:  python scripts/migrate_tree_phase2.py --apply")

if __name__ == "__main__":
    main()
