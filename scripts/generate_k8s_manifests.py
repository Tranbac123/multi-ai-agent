#!/usr/bin/env python3
"""
Generate complete Kubernetes manifests for all services.
"""

from pathlib import Path
from typing import Dict

# Service configurations (reusing from previous script)
SERVICES_CONFIG = {
    "api-gateway": {"port": 8000, "replicas": 3, "cpu": "250m", "memory": "512Mi"},
    "analytics-service": {"port": 8005, "replicas": 2, "cpu": "200m", "memory": "512Mi"},
    "orchestrator": {"port": 8002, "replicas": 2, "cpu": "300m", "memory": "1Gi"},
    "router-service": {"port": 8003, "replicas": 2, "cpu": "200m", "memory": "512Mi"},
    "realtime": {"port": 8004, "replicas": 3, "cpu": "250m", "memory": "512Mi"},
    "ingestion": {"port": 8006, "replicas": 2, "cpu": "300m", "memory": "1Gi"},
    "billing-service": {"port": 8007, "replicas": 2, "cpu": "200m", "memory": "512Mi"},
    "tenant-service": {"port": 8008, "replicas": 2, "cpu": "200m", "memory": "512Mi"},
    "chat-adapters": {"port": 8009, "replicas": 2, "cpu": "200m", "memory": "512Mi"},
    "tool-service": {"port": 8010, "replicas": 2, "cpu": "200m", "memory": "512Mi"},
    "eval-service": {"port": 8011, "replicas": 1, "cpu": "500m", "memory": "1Gi"},
    "capacity-monitor": {"port": 8012, "replicas": 1, "cpu": "100m", "memory": "256Mi"},
    "admin-portal": {"port": 8100, "replicas": 2, "cpu": "200m", "memory": "512Mi"},
    "web-frontend": {"port": 3000, "replicas": 2, "cpu": "100m", "memory": "128Mi"}
}

def create_base_manifests(service_name: str, config: Dict) -> None:
    """Create base Kubernetes manifests for a service."""
    base_path = Path(f"apps/{service_name}/deploy/base")
    
    # Create deployment.yaml
    deployment_file = base_path / "deployment.yaml"
    if not deployment_file.exists():
        deployment_content = f'''apiVersion: apps/v1
kind: Deployment
metadata:
  name: {service_name}
  labels:
    app: {service_name}
    component: microservice
spec:
  replicas: {config["replicas"]}
  selector:
    matchLabels:
      app: {service_name}
  template:
    metadata:
      labels:
        app: {service_name}
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "{config["port"]}"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: {service_name}
        image: {service_name}:IMAGE_TAG
        ports:
        - containerPort: {config["port"]}
          name: http
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: database-secret
              key: url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: redis-secret
              key: url
        - name: PORT
          value: "{config["port"]}"
        - name: ENVIRONMENT
          value: "production"
        envFrom:
        - configMapRef:
            name: {service_name}-config
        livenessProbe:
          httpGet:
            path: /health
            port: {config["port"]}
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health
            port: {config["port"]}
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
        resources:
          requests:
            memory: "{config["memory"]}"
            cpu: "{config["cpu"]}"
          limits:
            memory: "{config["memory"]}"
            cpu: "{config["cpu"]}"
        securityContext:
          allowPrivilegeEscalation: false
          runAsNonRoot: true
          runAsUser: 1000
          capabilities:
            drop:
            - ALL
      securityContext:
        fsGroup: 1000
        runAsGroup: 1000
        runAsUser: 1000
      serviceAccountName: {service_name}'''
        deployment_file.write_text(deployment_content)
    
    # Create service.yaml
    service_file = base_path / "service.yaml"
    if not service_file.exists():
        service_content = f'''apiVersion: v1
kind: Service
metadata:
  name: {service_name}
  labels:
    app: {service_name}
spec:
  selector:
    app: {service_name}
  ports:
  - name: http
    port: {config["port"]}
    targetPort: {config["port"]}
    protocol: TCP
  type: ClusterIP'''
        service_file.write_text(service_content)
    
    # Create configmap.yaml
    configmap_file = base_path / "configmap.yaml"
    if not configmap_file.exists():
        configmap_content = f'''apiVersion: v1
kind: ConfigMap
metadata:
  name: {service_name}-config
data:
  LOG_LEVEL: "INFO"
  METRICS_ENABLED: "true"
  TRACING_ENABLED: "true"
  SERVICE_NAME: "{service_name}"'''
        configmap_file.write_text(configmap_content)
    
    # Create serviceaccount.yaml
    sa_file = base_path / "serviceaccount.yaml"
    if not sa_file.exists():
        sa_content = f'''apiVersion: v1
kind: ServiceAccount
metadata:
  name: {service_name}
  labels:
    app: {service_name}
automountServiceAccountToken: false'''
        sa_file.write_text(sa_content)
    
    # Create hpa.yaml
    hpa_file = base_path / "hpa.yaml"
    if not hpa_file.exists():
        hpa_content = f'''apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {service_name}-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {service_name}
  minReplicas: {config["replicas"]}
  maxReplicas: {config["replicas"] * 3}
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
      - type: Pods
        value: 2
        periodSeconds: 60
      selectPolicy: Max'''
        hpa_file.write_text(hpa_content)
    
    # Update or create kustomization.yaml
    kustomization_file = base_path / "kustomization.yaml"
    kustomization_content = f'''apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

metadata:
  name: {service_name}-base

resources:
  - deployment.yaml
  - service.yaml
  - configmap.yaml
  - serviceaccount.yaml
  - hpa.yaml

commonLabels:
  app: {service_name}
  component: microservice
  version: v1'''
    kustomization_file.write_text(kustomization_content)

def create_environment_overlays(service_name: str, config: Dict) -> None:
    """Create environment-specific overlays."""
    environments = ["dev", "staging", "prod"]
    
    for env in environments:
        overlay_path = Path(f"apps/{service_name}/deploy/overlays/{env}")
        overlay_path.mkdir(parents=True, exist_ok=True)
        
        # Create kustomization.yaml for environment
        kustomization_file = overlay_path / "kustomization.yaml"
        
        patches = []
        if env == "dev":
            patches = [
                "deployment-patch.yaml",
                "configmap-patch.yaml"
            ]
            replicas = 1
        elif env == "staging":
            patches = [
                "deployment-patch.yaml", 
                "configmap-patch.yaml"
            ]
            replicas = 2
        else:  # prod
            patches = [
                "configmap-patch.yaml"
            ]
            replicas = config["replicas"]
        
        kustomization_content = f'''apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

metadata:
  name: {service_name}-{env}

namespace: multi-ai-agent-{env}

resources:
  - ../../base

patchesStrategicMerge:'''
        
        for patch in patches:
            kustomization_content += f"\n  - {patch}"
        
        kustomization_content += f'''

configMapGenerator:
  - name: {service_name}-config
    behavior: merge
    literals:
      - ENVIRONMENT={env}
      - LOG_LEVEL={"DEBUG" if env == "dev" else "INFO"}'''
        
        kustomization_file.write_text(kustomization_content)
        
        # Create deployment patch for dev/staging
        if env in ["dev", "staging"]:
            deployment_patch = overlay_path / "deployment-patch.yaml"
            patch_content = f'''apiVersion: apps/v1
kind: Deployment
metadata:
  name: {service_name}
spec:
  replicas: {replicas}'''
            deployment_patch.write_text(patch_content)
        
        # Create configmap patch for each environment
        configmap_patch = overlay_path / "configmap-patch.yaml"
        patch_content = f'''apiVersion: v1
kind: ConfigMap
metadata:
  name: {service_name}-config
data:
  ENVIRONMENT: "{env}"
  DEBUG: "{"true" if env == "dev" else "false"}"'''
        configmap_patch.write_text(patch_content)

def create_deploy_makefile(service_name: str) -> None:
    """Create deployment Makefile for a service."""
    deploy_path = Path(f"apps/{service_name}/deploy")
    makefile = deploy_path / "Makefile"
    
    if not makefile.exists():
        makefile_content = f'''.PHONY: help deploy clean validate

ENV ?= dev
IMAGE_TAG ?= latest
NAMESPACE ?= multi-ai-agent-$(ENV)

help:
	@echo "{service_name.title()} Deployment - Available Commands:"
	@echo ""
	@echo "  deploy       Deploy to environment (ENV=dev|staging|prod)"
	@echo "  clean        Clean deployment"
	@echo "  validate     Validate manifests"
	@echo ""
	@echo "Usage: make deploy ENV=dev IMAGE_TAG=v1.0.0"

deploy:
	@echo "Deploying {service_name} to $(ENV) environment..."
	@kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	@kustomize build overlays/$(ENV) | \\
		sed 's|IMAGE_TAG|$(IMAGE_TAG)|g' | \\
		kubectl apply -f -
	@kubectl rollout status deployment/{service_name} -n $(NAMESPACE) --timeout=300s

clean:
	@echo "Cleaning {service_name} from $(ENV) environment..."
	@kustomize build overlays/$(ENV) | kubectl delete -f - || true

validate:
	@echo "Validating {service_name} manifests..."
	@kustomize build overlays/dev | kubectl apply --dry-run=client -f -
	@kustomize build overlays/staging | kubectl apply --dry-run=client -f -
	@kustomize build overlays/prod | kubectl apply --dry-run=client -f -
	@echo "✓ All manifests are valid"'''
        makefile.write_text(makefile_content)

def main():
    """Main function to generate K8s manifests."""
    print("Generating Kubernetes manifests for all services...")
    
    for service_name, config in SERVICES_CONFIG.items():
        print(f"\\nGenerating manifests for {service_name}...")
        
        # Create base manifests
        create_base_manifests(service_name, config)
        print(f"  ✓ Base manifests created")
        
        # Create environment overlays
        create_environment_overlays(service_name, config)
        print(f"  ✓ Environment overlays created")
        
        # Create deployment Makefile
        create_deploy_makefile(service_name)
        print(f"  ✓ Deployment Makefile created")
    
    print("\\n🎉 All Kubernetes manifests generated!")
    print("\\nYou can now deploy services using:")
    print("  cd apps/<service>/deploy")
    print("  make deploy ENV=dev")

if __name__ == "__main__":
    main()
