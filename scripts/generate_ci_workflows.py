#!/usr/bin/env python3
"""
Generate CI workflows for all services.
"""

from pathlib import Path

SERVICES = [
    "api-gateway", "analytics-service", "orchestrator", "router-service",
    "realtime", "ingestion", "billing-service", "tenant-service", 
    "chat-adapters", "tool-service", "eval-service", "capacity-monitor",
    "admin-portal", "web-frontend"
]

def create_ci_workflow(service_name: str) -> None:
    """Create CI workflow for a service."""
    workflow_path = Path(f"apps/{service_name}/.github/workflows")
    workflow_path.mkdir(parents=True, exist_ok=True)
    
    ci_file = workflow_path / "ci.yaml"
    
    if service_name == "web-frontend":
        # Frontend CI workflow
        ci_content = f'''name: "{service_name.title()} CI/CD"

on:
  push:
    paths:
      - "apps/{service_name}/**"
      - ".github/workflows/{service_name}-ci.yaml"
  pull_request:
    paths:
      - "apps/{service_name}/**"

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '18'
          cache: 'npm'
          cache-dependency-path: 'apps/{service_name}/package-lock.json'
          
      - name: Install dependencies
        run: |
          cd apps/{service_name}
          npm ci
          
      - name: Lint
        run: |
          cd apps/{service_name}
          npm run lint
          
      - name: Type check
        run: |
          cd apps/{service_name}
          npm run type-check || true
          
      - name: Test
        run: |
          cd apps/{service_name}
          npm run test || true
          
      - name: Build
        run: |
          cd apps/{service_name}
          npm run build

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
        
      - name: Build Docker image
        run: |
          cd apps/{service_name}
          docker build -t {service_name}:latest .
'''
    else:
        # Backend CI workflow
        ci_content = f'''name: "{service_name.title()} CI/CD"

on:
  push:
    paths:
      - "apps/{service_name}/**"
      - "libs/**"
      - "contracts/**"
      - ".github/workflows/{service_name}-ci.yaml"
  pull_request:
    paths:
      - "apps/{service_name}/**"
      - "libs/**"
      - "contracts/**"

jobs:
  service-ci:
    uses: ./.github/workflows/service-ci.yaml
    with:
      service-name: {service_name}
      service-path: apps/{service_name}
      python-version: "3.11"
      enable-docker: true
      enable-helm: true
    secrets:
      DOCKER_REGISTRY_URL: ${{{{ secrets.DOCKER_REGISTRY_URL }}}}
      DOCKER_USERNAME: ${{{{ secrets.DOCKER_USERNAME }}}}
      DOCKER_PASSWORD: ${{{{ secrets.DOCKER_PASSWORD }}}}
'''
    
    ci_file.write_text(ci_content)

def main():
    """Generate CI workflows for all services."""
    print("Generating CI workflows for all services...")
    
    for service_name in SERVICES:
        create_ci_workflow(service_name)
        print(f"  ✓ CI workflow created for {service_name}")
    
    print("\\n🎉 All CI workflows generated!")

if __name__ == "__main__":
    main()
