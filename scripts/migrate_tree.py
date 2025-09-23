#!/usr/bin/env python3
import argparse, os, re, shutil, sys, textwrap, json
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]

CP_KEYWORDS = {
    "policy","opa","feature","flag","config","registry",
    "usage","meter","audit","tenant","iam","scim","tool-registry"
}
DP_KEYWORDS = {
    "api","gateway","orchestrator","router","retrieval","ingestion",
    "eval","mcp","realtime","worker","model","chat","bff","search"
}

OBS_TEMPLATES_DIR = ROOT / "platform" / "observability-templates"

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

def classify_service(name:str)->str:
    key = re.sub(r"[^a-z0-9]+","-",name.lower())
    if any(k in key for k in CP_KEYWORDS): return "control-plane"
    if any(k in key for k in DP_KEYWORDS): return "data-plane"
    # default to data-plane, but mark unsure
    return "data-plane"

def ensure_dirs(p:Path):
    p.mkdir(parents=True, exist_ok=True)

def move_dir(src:Path, dst:Path, apply:bool):
    if not src.exists(): return False
    if dst.exists():
        # merge move: copytree to *_legacy to avoid overwrite
        dst_legacy = dst.with_name(dst.name + "-legacy")
        if apply:
            shutil.move(str(src), str(dst_legacy))
        log(f"  └─ DEST EXISTS, moved '{src}' → '{dst_legacy}'")
        return True
    if apply:
        ensure_dirs(dst.parent)
        shutil.move(str(src), str(dst))
    log(f"  └─ moved '{src}' → '{dst}'")
    return True

def list_services_under(root:Path)->List[Path]:
    if not root.exists(): return []
    return [p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")]

def ensure_service_layout(svc_path:Path, port:int=8080, apply:bool=False):
    name = svc_path.name
    # src/
    ensure_dirs(svc_path/"src")
    # contracts/
    if not (svc_path/"contracts"/"openapi.yaml").exists():
        ensure_dirs(svc_path/"contracts")
        if apply:
            (svc_path/"contracts"/"openapi.yaml").write_text(OPENAPI_SKELETON.replace("PLACEHOLDER", name))
    # observability/
    ensure_dirs(svc_path/"observability")
    for f in ["dashboards.json","alerts.yaml","SLO.md","runbook.md"]:
        target = svc_path/"observability"/f
        if not target.exists() and (OBS_TEMPLATES_DIR/f).exists() and apply:
            shutil.copyfile(OBS_TEMPLATES_DIR/f, target)
    # deploy/helm chart
    chart_dir = svc_path/"deploy"/"helm"/name
    if not (chart_dir/"Chart.yaml").exists():
        ensure_dirs(chart_dir/"templates")
        if apply:
            (chart_dir/"Chart.yaml").write_text(HELM_CHART.format(name=name))
            (chart_dir/"values.yaml").write_text(HELM_VALUES.format(name=name, port=port))
            (chart_dir/"templates"/"deployment.yaml").write_text(HELM_DEPLOY.format(name=name))
            (chart_dir/"templates"/"service.yaml").write_text(HELM_SVC.format(name=name))
            (chart_dir/"templates"/"hpa.yaml").write_text(HELM_HPA.format(name=name))
            (chart_dir/"templates"/"pdb.yaml").write_text(HELM_PDB.format(name=name))
    # Dockerfile + requirements (best-effort)
    if not (svc_path/"Dockerfile").exists() and apply:
        (svc_path/"Dockerfile").write_text(DOCKERFILE_PY.format(port=port))
    if not (svc_path/"requirements.txt").exists() and apply:
        (svc_path/"requirements.txt").write_text(REQS_MIN)
    # health test
    tests = svc_path/"tests"
    ensure_dirs(tests)
    tf = tests/"test_health.py"
    if not tf.exists() and apply:
        tf.write_text("def test_placeholder():\n    assert True\n")

def migrate_services_folder(apply:bool)->List[Tuple[str,Path]]:
    moved=[]
    legacy_root = ROOT/"services"
    for svc in list_services_under(legacy_root):
        plane = classify_service(svc.name)
        dst = ROOT/"apps"/plane/svc.name
        log(f"- {svc.name}: → {dst}")
        if move_dir(svc, dst, apply):
            moved.append((plane,dst))
            ensure_service_layout(dst, port=8080, apply=apply)
    # remove empty 'services/' if empty
    try:
        if legacy_root.exists() and not any(legacy_root.iterdir()) and apply:
            legacy_root.rmdir()
            log("Removed empty 'services/'")
    except Exception: pass
    return moved

def migrate_eval(apply:bool)->Path|None:
    src = ROOT/"eval"
    if not src.exists(): return None
    signs = ["src","main.py","Dockerfile","pyproject.toml"]
    is_service = any((src/s).exists() for s in signs)
    if not is_service: return None
    dst = ROOT/"apps"/"data-plane"/"eval-service"
    log(f"- eval/: → {dst}")
    move_dir(src, dst, apply)
    ensure_service_layout(dst, port=8087, apply=apply)
    return dst

def ensure_observability_templates(apply:bool):
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
        "SLO.md": "# SLO\n- Latency p95: TBD\n- Error rate: <1%\n",
        "runbook.md": "# Runbook\n1. Check /healthz\n2. Inspect logs\n"
    }
    for f,content in defaults.items():
        target = OBS_TEMPLATES_DIR/f
        if not target.exists() and apply:
            target.write_text(content)

def move_configs_into_services(apply:bool):
    cfg_root = ROOT/"configs"
    if not cfg_root.exists(): return
    # heuristic: if filename contains service name, move to its chart values/
    all_svcs = [p for p in (ROOT/"apps").rglob("*/deploy/helm/*") if (p/"Chart.yaml").exists()]
    unmatched=[]
    for f in cfg_root.rglob("*"):
        if not f.is_file(): continue
        matched=False
        for chart_dir in all_svcs:
            svc = chart_dir.name
            if re.search(rf"(^|[-_]){re.escape(svc)}([-.]|$)", f.name):
                dest = chart_dir/"values-extra.yaml"
                if apply:
                    shutil.copyfile(f, dest)
                log(f"  cfg {f.name} → {dest}")
                matched=True
                break
        if not matched:
            unmatched.append(str(f))
    if unmatched:
        out = ROOT/"apps"/"control-plane"/"config-service"/"MIGRATION_TODO_UNMATCHED_CONFIGS.json"
        ensure_dirs(out.parent)
        if apply:
            out.write_text(json.dumps({"unmatched": unmatched}, indent=2))
        log(f"  Unmatched configs recorded in {out}")

def migrate_contracts(apply:bool):
    root_contracts = ROOT/"contracts"
    if not root_contracts.exists(): return
    # move service-specific OpenAPI into each service if pattern matches
    for f in list(root_contracts.rglob("*.yaml")) + list(root_contracts.rglob("*.yml")):
        name = f.stem.lower()
        # try find service path with same name
        candidates = list((ROOT/"apps").rglob(f"*/{name}/deploy/helm/{name}/Chart.yaml"))
        if candidates:
            svc_dir = Path(str(candidates[0])).parents[2]  # .../<svc>
            dest = svc_dir/"contracts"/"openapi.yaml"
            ensure_dirs(dest.parent)
            if apply:
                shutil.move(str(f), str(dest))
            log(f"  contract {f.name} → {dest}")
    # ensure every service has a contracts/openapi.yaml
    for svc_dir in [p.parent.parent for p in (ROOT/"apps").rglob("deploy/helm/*/Chart.yaml")]:
        if not (svc_dir/"contracts"/"openapi.yaml").exists():
            ensure_service_layout(svc_dir, apply=apply)  # will drop skeleton

def update_workflows_paths(apply:bool):
    wf_dir = ROOT/".github"/"workflows"
    if not wf_dir.exists(): return
    # build list of per-service globs
    globs = []
    for svc_dir in [p.parent.parent for p in (ROOT/"apps").rglob("deploy/helm/*/Chart.yaml")]:
        rel = svc_dir.relative_to(ROOT).as_posix()
        globs.append(f"{rel}/**")
    for wf in wf_dir.glob("*.y*ml"):
        s = wf.read_text()
        # replace legacy 'services/**' with 'apps/**'
        s2 = s.replace("services/**","apps/**")
        # try to extend any 'paths:' blocks with our globs if not present
        if "paths:" in s2:
            block = "\n      - " + "\n      - ".join(globs)
            s2 = re.sub(r"(paths:\s*\[\s*)([^\]]*)(\])", lambda m: m.group(1)+m.group(2)+m.group(3), s2)
            # naive append under 'paths:' YAML list pattern
            s2 = re.sub(r"(paths:\s*\n(?:\s*-\s.*\n)+)", lambda m: m.group(1) + "\n".join([f"      - {g}\n" for g in globs if g not in m.group(1)]) , s2)
        if apply and s2!=s:
            wf.write_text(s2)
            log(f"  updated workflow paths: {wf.name}")

def main():
    ap = argparse.ArgumentParser(description="Migrate services/ → apps/{data,control}-plane + normalize.")
    ap.add_argument("--apply", action="store_true", help="execute changes (default dry-run)")
    args = ap.parse_args()
    apply = args.apply

    log("=== Ensure observability templates ===")
    ensure_observability_templates(apply)

    log("=== Migrate `services/` to apps/<plane>/ ===")
    moved = migrate_services_folder(apply)

    log("=== Handle eval/ as data-plane service if applicable ===")
    migrate_eval(apply)

    log("=== Distribute configs into per-service charts ===")
    move_configs_into_services(apply)

    log("=== Contracts: keep shared at root, move per-service openapi to each service ===")
    migrate_contracts(apply)

    log("=== Update CI path filters ===")
    update_workflows_paths(apply)

    log("=== Ensure per-service observability from templates ===")
    for svc_dir in [p.parent.parent for p in (ROOT/"apps").rglob("deploy/helm/*/Chart.yaml")]:
        ensure_service_layout(svc_dir, apply=apply)

    # Summary
    svcs = [p.parent.parent for p in (ROOT/"apps").rglob("deploy/helm/*/Chart.yaml")]
    print("\\n--- SUMMARY ---")
    print(f"Services detected: {len(svcs)}")
    for d in svcs:
        print(" -", d.relative_to(ROOT))
    print("\\nRun with:  python scripts/migrate_tree.py --apply")
    print("Then review git diff and commit with a clear message.")

if __name__ == "__main__":
    main()
