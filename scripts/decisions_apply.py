#!/usr/bin/env python3
import argparse, os, re, shutil, sys, json, textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS = ROOT/"apps"
WF_DIR = ROOT/".github"/"workflows"
OBS_TPL = ROOT/"platform"/"observability-templates"

# Decisions
PORTS = {
  "model-gateway": 8083,
  "chat-adapters-service": 8082,
  "semantic-cache-service": 8088,   # DP
  "notification-service": 8097,     # CP
}
RENAMES = {
  "apps/data-plane/chat-adapters": "apps/data-plane/chat-adapters-service"
}
MOVE_EVAL = {"from": ROOT/"eval", "to": ROOT/"docs"/"evaluation"}

REQS_MIN = "fastapi>=0.115.0\nuvicorn>=0.30.6\npydantic>=2.8.2\npydantic-settings>=2.3.4\nhttpx>=0.27.0\npytest>=8.2.0\n"

OPENAPI_SKELETON = "openapi: 3.0.3\ninfo: { title: PLACEHOLDER, version: '0.1.0' }\npaths:\n  /healthz: { get: { responses: { '200': { description: ok } } } }\n"
DOCKERFILE = "FROM python:3.11-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install -r requirements.txt\nCOPY src ./src\nEXPOSE {port}\nCMD ['uvicorn','src.main:app','--host','0.0.0.0','--port','{port}']\n"
HELM_CHART = "apiVersion: v2\nname: {name}\ntype: application\nversion: 0.1.0\nappVersion: '0.1.0'\n"
HELM_VALUES = """image:
  repository: ghcr.io/OWNER/{name}
  tag: "latest"
  pullPolicy: IfNotPresent
service:
  port: {port}
resources:
  limits:
    cpu: 300m
    memory: 256Mi
  requests:
    cpu: 50m
    memory: 128Mi
env: []
hpa:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
pdb:
  minAvailable: 1
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
            {{{{ toYaml .Values.resources | nindent 12 }}}}
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
HELM_HPA = """{{- if .Values.hpa.enabled }}
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
{{- end }}
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

def log(m): print(m)
def ensure(p:Path): p.mkdir(parents=True, exist_ok=True)

def write_if_missing(p:Path, content:str, apply:bool):
    if p.exists(): return
    if apply:
        ensure(p.parent); p.write_text(content)

def scaffold_service(svc_dir:Path, port:int, apply:bool):
    name = svc_dir.name
    # src + contracts + tests + helm + docker + reqs + observability
    ensure(svc_dir/"src")
    write_if_missing(svc_dir/"contracts"/"openapi.yaml", OPENAPI_SKELETON.replace("PLACEHOLDER", name), apply)
    ensure(svc_dir/"tests"); write_if_missing(svc_dir/"tests"/"test_health.py","def test_ok(): assert True\n", apply)
    write_if_missing(svc_dir/"Dockerfile", DOCKERFILE.format(port=port), apply)
    write_if_missing(svc_dir/"requirements.txt", REQS_MIN, apply)
    # Helm
    chart = svc_dir/"deploy"/"helm"/name
    ensure(chart/"templates")
    write_if_missing(chart/"Chart.yaml", HELM_CHART.format(name=name), apply)
    write_if_missing(chart/"values.yaml", HELM_VALUES.format(name=name, port=port), apply)
    write_if_missing(chart/"templates"/"deployment.yaml", HELM_DEPLOY.format(name=name), apply)
    write_if_missing(chart/"templates"/"service.yaml", HELM_SVC.format(name=name), apply)
    write_if_missing(chart/"templates"/"hpa.yaml", HELM_HPA.format(name=name), apply)
    write_if_missing(chart/"templates"/"pdb.yaml", HELM_PDB.format(name=name), apply)
    # Observability
    ensure(svc_dir/"observability")
    for f in ["dashboards.json","alerts.yaml","SLO.md","runbook.md"]:
        src = OBS_TPL/f; dst = svc_dir/"observability"/f
        if src.exists() and apply and not dst.exists(): shutil.copyfile(src, dst)

def rename_paths(apply:bool):
    for src_str, dst_str in RENAMES.items():
        src, dst = ROOT/src_str, ROOT/dst_str
        if not src.exists(): continue
        log(f"- rename {src} → {dst}")
        if dst.exists():
            legacy = dst.with_name(dst.name+"-legacy")
            if apply: shutil.move(str(src), str(legacy))
            log(f"  └─ destination existed → moved to {legacy}")
        else:
            if apply: ensure(dst.parent); shutil.move(str(src), str(dst))

def move_eval_docs(apply:bool):
    src, dst = MOVE_EVAL["from"], MOVE_EVAL["to"]
    if src.exists():
        ensure(dst)
        if apply:
            for p in src.iterdir():
                shutil.move(str(p), str(dst/p.name))
            try: src.rmdir()
            except: pass
        log(f"- moved eval/ → {dst} (docs)")

def create_model_gateway(apply:bool):
    svc = APPS/"data-plane"/"model-gateway"
    ensure(svc)
    port = PORTS["model-gateway"]
    scaffold_service(svc, port, apply)
    # settings.py, providers.py, main.py, ci.yml
    write_if_missing(svc/"src"/"settings.py",
"""from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    app_name='model-gateway'
    host='0.0.0.0'; port=%d
    policy_url='http://policy-adapter:80'
    metering_url='http://usage-metering:80'
    default_model='gpt-4o-mini'
    retry_max=2; timeout_s=30
    class Config: env_prefix='MG_'
settings=Settings()
"""%port, apply)
    write_if_missing(svc/"src"/"providers.py",
"""# Provider routing stubs: replace with real provider SDKs later.
from typing import Dict, Any
class Provider:
    name: str
    def __init__(self, name:str): self.name=name
    async def chat(self, payload:Dict[str,Any])->Dict[str,Any]:
        # stub echo; count tokens roughly
        content = payload.get('messages', [])[-1].get('content','') if payload.get('messages') else ''
        return {'output': f'stub[{self.name}]:'+content, 'tokens_in': len(str(payload))//4, 'tokens_out': len(content)//4}
    async def embeddings(self, payload:Dict[str,Any])->Dict[str,Any]:
        return {'vectors': [[0.0]*8 for _ in payload.get('input',[])], 'tokens_in': 0, 'tokens_out':0}
REGISTRY = {
    'openai': Provider('openai'),
    'anthropic': Provider('anthropic'),
    'azure': Provider('azure'),
}
def pick_provider(model:str)->Provider:
    # simple prefix routing: 'gpt-*'→openai, 'claude-*'→anthropic, 'azure:'→azure
    m = model or ''
    if m.startswith('azure:'): return REGISTRY['azure']
    if m.startswith('claude'): return REGISTRY['anthropic']
    return REGISTRY['openai']
""", apply)
    write_if_missing(svc/"src"/"main.py",
"""from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import time, httpx
from .settings import settings
from .providers import pick_provider

app = FastAPI(title=settings.app_name, version='0.1.0')
@app.get('/healthz') def h(): return {'ok': True}

class ChatIn(BaseModel): messages: list[dict]; model: str|None=None; temperature: float|None=None
class ChatOut(BaseModel): model:str; output:str; latency_ms:int; tokens_in:int; tokens_out:int
class EmbedIn(BaseModel): input: list[str]; model: str|None=None
class EmbedOut(BaseModel): model:str; vectors:list[list[float]]; latency_ms:int

def _authz(tenant, actor, action, resource):
    try:
        r = httpx.post(f"{settings.policy_url}/v1/authorize", json={'tenant_id':tenant,'actor':actor,'action':action,'resource':resource}, timeout=5)
        if r.status_code!=200 or not r.json().get('allow'): raise Exception('deny')
    except Exception: raise HTTPException(403, 'forbidden')

def _meter(ev):
    try: httpx.post(f"{settings.metering_url}/v1/usage", json=ev, timeout=3)
    except Exception: pass

async def _retry(call):
    last = None
    for _ in range(settings.retry_max+1):
        try: return await call()
        except Exception as e: last = e
    raise HTTPException(502, f'provider error: {last}')

@app.post('/v1/chat', response_model=ChatOut)
async def chat(body: ChatIn, x_tenant_id: str=Header(...), x_actor: str=Header('system')):
    _authz(x_tenant_id, x_actor, 'chat', 'model')
    model = body.model or settings.default_model
    t0=time.time()
    async def _do():
        p = pick_provider(model)
        return await p.chat(body.model_dump())
    res = await _retry(_do)
    ms=int((time.time()-t0)*1000)
    _meter({'tenant_id':x_tenant_id,'service':'model-gateway','route':'/v1/chat','tokens_in':res['tokens_in'],'tokens_out':res['tokens_out'],'latency_ms':ms,'cost_usd':0.0})
    return ChatOut(model=model, output=res['output'], latency_ms=ms, tokens_in=res['tokens_in'], tokens_out=res['tokens_out'])

@app.post('/v1/embeddings', response_model=EmbedOut)
async def embeddings(body: EmbedIn, x_tenant_id: str=Header(...), x_actor: str=Header('system')):
    _authz(x_tenant_id, x_actor, 'embed', 'model')
    model = body.model or 'text-embedding-3-small'
    t0=time.time()
    async def _do():
        p = pick_provider(model); return await p.embeddings(body.model_dump())
    res = await _retry(_do)
    ms=int((time.time()-t0)*1000)
    _meter({'tenant_id':x_tenant_id,'service':'model-gateway','route':'/v1/embeddings','tokens_in':res['tokens_in'],'tokens_out':res['tokens_out'],'latency_ms':ms,'cost_usd':0.0})
    return EmbedOut(model=model, vectors=res['vectors'], latency_ms=ms)
""", apply)
    # tests
    write_if_missing(svc/"tests"/"test_health.py","""from fastapi.testclient import TestClient\nfrom apps.data-plane.model-gateway.src.main import app\n\ndef test_health():\n    c=TestClient(app)\n    assert c.get('/healthz').status_code==200\n""", apply)

def ensure_chat_adapters_service(apply:bool):
    dst = APPS/"data-plane"/"chat-adapters-service"
    if not dst.exists(): return
    scaffold_service(dst, PORTS["chat-adapters-service"], apply)
    write_if_missing(dst/"contracts"/"openapi.yaml",
"""openapi: 3.0.3
info: { title: chat-adapters-service, version: '0.1.0' }
paths:
  /healthz: { get: { responses: { '200': { description: ok } } } }
  /v1/adapters:
    get: { responses: { '200': { description: list adapters } } }
""", apply)

def create_semantic_cache_service(apply:bool):
    svc = APPS/"data-plane"/"semantic-cache-service"
    ensure(svc); scaffold_service(svc, PORTS["semantic-cache-service"], apply)
    write_if_missing(svc/"src"/"main.py",
"""from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import Dict, Tuple
app=FastAPI(title='semantic-cache-service', version='0.1.0')
@app.get('/healthz') def h(): return {'ok': True}
class PutIn(BaseModel): key:str; value:str; ttl_s:int|None=None
CACHE: Dict[str, Tuple[str,int|None]] = {}
@app.post('/v1/cache/put') def put(b: PutIn): CACHE[b.key]=(b.value,b.ttl_s); return {'ok': True}
@app.get('/v1/cache/get') def get(key:str=Query(...)): return {'hit': key in CACHE, 'value': CACHE.get(key,[None])[0]}
@app.delete('/v1/cache/del') def delete(key:str=Query(...)): CACHE.pop(key, None); return {'ok': True}
""", apply)

def create_notification_service(apply:bool):
    svc = APPS/"control-plane"/"notification-service"
    ensure(svc); scaffold_service(svc, PORTS["notification-service"], apply)
    write_if_missing(svc/"src"/"main.py",
"""from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
app=FastAPI(title='notification-service', version='0.1.0')
@app.get('/healthz') def h(): return {'ok': True}
class Msg(BaseModel): tenant_id:str; channels:List[str]; subject:str; body:str
@app.post('/v1/notify') def send(m: Msg): return {'queued': True, 'channels': m.channels}
""", apply)

def memory_service_boundary_note(apply:bool):
    svc = APPS/"data-plane"/"memory-service"
    if not svc.exists(): return
    write_if_missing(svc/"README.md",
"# Boundary\n- All vector ops go via retrieval-service.\n- This service manages session/episodic state only.\n", apply)

def cleanup_contracts_root(apply:bool):
    root = ROOT/"contracts"
    if not root.exists(): return
    shared_keep = {"shared.yaml","shared.proto"}
    # move service-specific files into service/contracts
    services = {d.name.lower(): d for d in [p.parent.parent for p in (APPS).rglob('deploy/helm/*/Chart.yaml')]}
    for f in list(root.glob("*.yml"))+list(root.glob("*.yaml"))+list(root.glob("*.proto")):
        if f.name in shared_keep: continue
        stem=f.stem.lower()
        target=None
        for name,dir in services.items():
            if name in stem:
                target=dir/"contracts"/("openapi.yaml" if f.suffix in ['.yml','.yaml'] else f.name)
                break
        if target:
            if apply: ensure(target.parent); shutil.move(str(f), str(target))
            log(f"  contract moved {f.name} → {target}")
    # leave only shared.*
    for f in root.iterdir():
        if f.is_file() and f.name not in shared_keep:
            log(f"  NOTE: extra file stays in contracts/: {f.name}")

def update_workflows(apply:bool):
    if not WF_DIR.exists(): return
    globs = [p.parent.parent.relative_to(ROOT).as_posix()+"/**" for p in (APPS).rglob("deploy/helm/*/Chart.yaml")]
    for wf in WF_DIR.glob("*.y*ml"):
        s = wf.read_text(); s2=s.replace("services/**","apps/**")
        if "paths:" in s2:
            for g in globs:
                if g not in s2:
                    s2 = re.sub(r"(paths:\s*\n)", r"\\1      - "+g+"\\n", s2)
        if apply and s2!=s: wf.write_text(s2); log(f"  updated workflow paths: {wf.name}")

def main():
    ap = argparse.ArgumentParser(description="Apply DECISIONS pack: add model-gateway, rename chat-adapters, move eval to docs, add semantic-cache & notification, clean contracts, validate CI/obs.")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(); apply=args.apply

    # ensure obs templates exist
    ensure(OBS_TPL); 
    for n,c in {"dashboards.json":"[]\n","alerts.yaml":"groups: []\n","SLO.md":"# SLO\n","runbook.md":"# Runbook\n"}.items():
        p=OBS_TPL/n
        if apply and not p.exists(): p.write_text(c)

    # rename & moves
    rename_paths(apply)
    move_eval_docs(apply)

    # create services
    create_model_gateway(apply)
    ensure_chat_adapters_service(apply)
    create_semantic_cache_service(apply)
    create_notification_service(apply)
    memory_service_boundary_note(apply)

    # contracts + workflows
    cleanup_contracts_root(apply)
    update_workflows(apply)

    # final scaffold sweep
    for chart in (APPS).rglob("deploy/helm/*/Chart.yaml"):
        svc_dir = chart.parents[2]
        port = PORTS.get(svc_dir.name, 8080)
        scaffold_service(svc_dir, port, apply)

    # summary
    svcs = sorted({p.parent.parent.relative_to(ROOT).as_posix() for p in (APPS).rglob("deploy/helm/*/Chart.yaml")})
    print("\n--- SUMMARY ---")
    print(f"Services detected: {len(svcs)}")
    for s in svcs: print(" -", s)
    print("\nRun: python scripts/decisions_apply.py --apply" if not apply else "\nAPPLIED. Review git diff and commit.")

if __name__ == "__main__":
    main()
