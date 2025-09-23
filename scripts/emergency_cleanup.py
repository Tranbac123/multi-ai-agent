#!/usr/bin/env python3
"""
Emergency cleanup for extremely corrupted directory structures.
Handles cases where paths are too long for filesystem operations.
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def log(msg): 
    print(msg)

def emergency_remove_corrupted_service(service_dir, apply=False):
    """Use system tools to remove extremely corrupted directories."""
    deploy_dir = service_dir / "deploy"
    if not deploy_dir.exists():
        return
    
    # Use find with -delete to handle long paths
    try:
        # First, try to find any valid Chart.yaml content
        valid_content = None
        try:
            result = subprocess.run(
                ["find", str(service_dir), "-name", "Chart.yaml", "-exec", "head", "-10", "{}", ";"], 
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and result.stdout:
                lines = result.stdout.strip().split('\n')
                # Look for actual Chart.yaml content
                for i, line in enumerate(lines):
                    if 'apiVersion: v2' in line or 'name:' in line:
                        valid_content = '\n'.join(lines[max(0, i-2):i+8])
                        break
        except Exception:
            pass
        
        log(f"  Processing {service_dir.name}")
        
        if apply:
            # Emergency removal using system find
            subprocess.run(
                ["find", str(deploy_dir), "-type", "f", "-delete"], 
                check=False, capture_output=True
            )
            subprocess.run(
                ["find", str(deploy_dir), "-depth", "-type", "d", "-delete"], 
                check=False, capture_output=True
            )
            
            # Recreate clean structure
            clean_helm_dir = service_dir / "deploy" / "helm" / service_dir.name
            clean_helm_dir.mkdir(parents=True, exist_ok=True)
            
            # Create minimal Chart.yaml
            chart_content = f"""apiVersion: v2
name: {service_dir.name}
type: application
version: 0.1.0
appVersion: "0.1.0"
"""
            (clean_helm_dir / "Chart.yaml").write_text(chart_content)
            
            # Create minimal values.yaml  
            values_content = f"""image:
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
            
            # Create templates directory with basic files
            templates_dir = clean_helm_dir / "templates"
            templates_dir.mkdir(exist_ok=True)
            
            # Basic deployment
            deployment_content = f"""apiVersion: apps/v1
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
            {{{{- toYaml .Values.resources | nindent 12 }}}}
"""
            (templates_dir / "deployment.yaml").write_text(deployment_content)
            
            # Basic service
            service_content = f"""apiVersion: v1
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
"""
            (templates_dir / "service.yaml").write_text(service_content)
            
            log(f"    ✅ Rebuilt clean structure")
        else:
            log(f"    [DRY-RUN] Would emergency clean and rebuild")
            
    except Exception as e:
        log(f"    ❌ Error processing {service_dir.name}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Emergency cleanup for corrupted directories")
    parser.add_argument("--apply", action="store_true", help="Actually apply fixes (default: dry run)")
    args = parser.parse_args()
    
    log("=== EMERGENCY DIRECTORY CLEANUP ===")
    log("")
    
    # Find services with any sign of corruption
    corrupted_services = []
    
    for apps_dir in ["apps/control-plane", "apps/data-plane"]:
        apps_path = ROOT / apps_dir
        if not apps_path.exists():
            continue
            
        for service_dir in apps_path.iterdir():
            if service_dir.is_dir() and not service_dir.name.startswith('.'):
                deploy_deploy = service_dir / "deploy" / "deploy"
                if deploy_deploy.exists():
                    corrupted_services.append(service_dir)
    
    log(f"Found {len(corrupted_services)} corrupted services:")
    for service_dir in corrupted_services:
        log(f"  - {service_dir.name}")
    
    log("")
    
    if not corrupted_services:
        log("✅ No corrupted services found!")
        return
    
    # Process each corrupted service
    log("Emergency processing:")
    for service_dir in corrupted_services:
        emergency_remove_corrupted_service(service_dir, apply=args.apply)
    
    log("")
    log("=== SUMMARY ===")
    if args.apply:
        log("✅ Emergency cleanup completed!")
        log("Verifying clean structure:")
        # Count Chart.yaml files
        result = subprocess.run(
            ["find", "apps/", "-name", "Chart.yaml"], 
            capture_output=True, text=True, cwd=ROOT
        )
        if result.returncode == 0:
            chart_count = len([l for l in result.stdout.strip().split('\n') if l])
            log(f"  Found {chart_count} Helm charts (expected: 24)")
            if chart_count == 24:
                log("  ✅ Perfect! Architecture is clean.")
            else:
                log("  ⚠️  Count mismatch - may need additional cleanup.")
    else:
        log("ℹ️  Dry run completed. Use --apply to execute emergency cleanup.")

if __name__ == "__main__":
    main()
