#!/usr/bin/env python3
"""
Final fix for service directory structures.
Ensures each service has ONLY the correct structure and removes all corruption.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def log(msg): 
    print(msg)

def fix_service_structure(service_dir, apply=False):
    """Fix a single service to have only the correct structure."""
    log(f"  Fixing {service_dir.name}")
    
    # Expected final structure
    expected_structure = {
        "src": "directory",
        "tests": "directory", 
        "contracts": "directory",
        "observability": "directory",
        "deploy/helm/{}/Chart.yaml".format(service_dir.name): "file",
        "deploy/helm/{}/values.yaml".format(service_dir.name): "file",
        "deploy/helm/{}/templates".format(service_dir.name): "directory",
        "Dockerfile": "file",
        "requirements.txt": "file",
        "Makefile": "file",
        ".github/workflows/ci.yaml": "file"
    }
    
    # Backup any valid Chart.yaml content
    valid_chart_content = None
    valid_values_content = None
    valid_templates = {}
    
    # Find and backup the best Chart.yaml
    for chart_file in service_dir.rglob("Chart.yaml"):
        try:
            content = chart_file.read_text()
            if f"name: {service_dir.name}" in content and "apiVersion: v2" in content:
                valid_chart_content = content
                values_file = chart_file.parent / "values.yaml"
                if values_file.exists():
                    valid_values_content = values_file.read_text()
                
                templates_dir = chart_file.parent / "templates"
                if templates_dir.exists():
                    for tmpl_file in templates_dir.glob("*.yaml"):
                        valid_templates[tmpl_file.name] = tmpl_file.read_text()
                break
        except Exception:
            continue
    
    if apply:
        # Completely remove deploy directory
        deploy_dir = service_dir / "deploy"
        if deploy_dir.exists():
            # Use system commands for stubborn directories
            subprocess.run(["rm", "-rf", str(deploy_dir)], check=False)
        
        # Recreate clean deploy structure
        clean_helm_dir = service_dir / "deploy" / "helm" / service_dir.name
        clean_helm_dir.mkdir(parents=True, exist_ok=True)
        
        # Restore or create Chart.yaml
        chart_content = valid_chart_content or f"""apiVersion: v2
name: {service_dir.name}
type: application
version: 0.1.0
appVersion: "0.1.0"
"""
        (clean_helm_dir / "Chart.yaml").write_text(chart_content)
        
        # Restore or create values.yaml
        values_content = valid_values_content or f"""image:
  repository: ghcr.io/OWNER/{service_dir.name}
  tag: "latest"
  pullPolicy: IfNotPresent
service:
  port: 8080
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
        (clean_helm_dir / "values.yaml").write_text(values_content)
        
        # Restore or create templates
        templates_dir = clean_helm_dir / "templates"
        templates_dir.mkdir(exist_ok=True)
        
        if valid_templates:
            for filename, content in valid_templates.items():
                (templates_dir / filename).write_text(content)
        else:
            # Create minimal templates
            (templates_dir / "deployment.yaml").write_text(f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {service_dir.name}
spec:
  replicas: 2
  selector:
    matchLabels:
      app: {service_dir.name}
  template:
    metadata:
      labels:
        app: {service_dir.name}
    spec:
      containers:
        - name: app
          image: "{{{{ .Values.image.repository }}}}:{{{{ .Values.image.tag }}}}"
          ports:
            - containerPort: {{{{ .Values.service.port }}}}
          readinessProbe:
            httpGet:
              path: /healthz
              port: {{{{ .Values.service.port }}}}
          resources:
            {{{{- toYaml .Values.resources | nindent 12 }}}}
""")
            
            (templates_dir / "service.yaml").write_text(f"""apiVersion: v1
kind: Service
metadata:
  name: {service_dir.name}
spec:
  selector:
    app: {service_dir.name}
  ports:
    - port: 80
      targetPort: {{{{ .Values.service.port }}}}
      name: http
""")
        
        log(f"    ✅ Clean structure created")
    else:
        log(f"    [DRY-RUN] Would create clean deploy/helm/{service_dir.name} structure")

def main():
    parser = argparse.ArgumentParser(description="Final structure fix for all services")
    parser.add_argument("--apply", action="store_true", help="Actually apply fixes")
    args = parser.parse_args()
    
    log("=== FINAL STRUCTURE FIX ===")
    log("")
    
    # Process all services
    all_services = []
    for apps_dir in ["apps/control-plane", "apps/data-plane"]:
        apps_path = ROOT / apps_dir
        if apps_path.exists():
            for service_dir in apps_path.iterdir():
                if service_dir.is_dir() and not service_dir.name.startswith('.'):
                    all_services.append(service_dir)
    
    log(f"Processing {len(all_services)} services:")
    for service_dir in all_services:
        fix_service_structure(service_dir, apply=args.apply)
    
    log("")
    log("=== VERIFICATION ===")
    if args.apply:
        # Count final Chart.yaml files
        result = subprocess.run(
            ["find", "apps/", "-name", "Chart.yaml"], 
            capture_output=True, text=True, cwd=ROOT
        )
        if result.returncode == 0:
            chart_files = [l for l in result.stdout.strip().split('\n') if l]
            log(f"Final Helm charts count: {len(chart_files)}")
            
            # Check for corruption
            corrupt_count = len([f for f in chart_files if "/deploy/deploy/" in f])
            log(f"Corrupted paths: {corrupt_count} (should be 0)")
            
            if len(chart_files) == 24 and corrupt_count == 0:
                log("✅ Perfect! Clean architecture achieved.")
            else:
                log("⚠️  May need additional cleanup.")
                
        log("")
        log("Sample structure verification:")
        log("apps/data-plane/api-gateway/deploy/:")
        subprocess.run(["ls", "-la", "apps/data-plane/api-gateway/deploy/"], cwd=ROOT)
    else:
        log("ℹ️  Dry run completed. Use --apply to fix all structures.")

if __name__ == "__main__":
    main()
