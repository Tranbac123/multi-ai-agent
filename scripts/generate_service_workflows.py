#!/usr/bin/env python3
"""
Generate service-specific CI workflows that use the reusable template.
"""

from pathlib import Path
from typing import Dict

# Service configurations with their languages
SERVICES_CONFIG = {
    "api-gateway": {"language": "python", "port": 8000},
    "analytics-service": {"language": "python", "port": 8005},
    "orchestrator": {"language": "python", "port": 8002},
    "router-service": {"language": "python", "port": 8003},
    "realtime": {"language": "python", "port": 8004},
    "ingestion": {"language": "python", "port": 8006},
    "billing-service": {"language": "python", "port": 8007},
    "tenant-service": {"language": "python", "port": 8008},
    "chat-adapters": {"language": "python", "port": 8009},
    "tool-service": {"language": "python", "port": 8010},
    "eval-service": {"language": "python", "port": 8011},
    "capacity-monitor": {"language": "python", "port": 8012},
    "admin-portal": {"language": "python", "port": 8100},
    "web-frontend": {"language": "node", "port": 3000},
}

def create_service_workflow(service_name: str, config: Dict) -> None:
    """Create CI workflow for a service."""
    workflow_path = Path(f"apps/{service_name}/.github/workflows")
    workflow_path.mkdir(parents=True, exist_ok=True)
    
    ci_file = workflow_path / "ci.yaml"
    
    # Create service-specific workflow
    ci_content = f'''name: "{service_name.title().replace('-', ' ')} CI/CD"

on:
  push:
    paths:
      - "apps/{service_name}/**"
      - "libs/**"
      - "contracts/**"
      - "platform/ci-templates/**"
      - ".github/workflows/{service_name}-*.yaml"
  pull_request:
    paths:
      - "apps/{service_name}/**"
      - "libs/**"
      - "contracts/**"

concurrency:
  group: ${{{{ github.workflow }}}}-${{{{ github.ref }}}}
  cancel-in-progress: true

jobs:
  ci:
    name: "Build and Test {service_name.title().replace('-', ' ')}"
    uses: ./platform/ci-templates/service-ci.yaml
    with:
      language: "{config["language"]}"
      service_path: "apps/{service_name}"
      service_name: "{service_name}"
      enable_docker: true
      enable_sbom: true
    secrets:
      DOCKER_REGISTRY_URL: ${{{{ secrets.DOCKER_REGISTRY_URL }}}}
      DOCKER_USERNAME: ${{{{ secrets.DOCKER_USERNAME }}}}
      DOCKER_PASSWORD: ${{{{ secrets.DOCKER_PASSWORD }}}}

  # Optional: Service-specific deployment to dev environment
  deploy-dev:
    name: "Deploy to Development"
    needs: ci
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    environment: development
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Deploy to development
        run: |
          echo "Deploying {service_name} to development environment"
          # Add your deployment logic here
          # cd apps/{service_name}/deploy
          # make deploy ENV=dev IMAGE_TAG=${{{{ github.sha }}}}
'''
    
    ci_file.write_text(ci_content)

def main():
    """Generate CI workflows for all services."""
    print("Generating service-specific CI workflows...")
    
    for service_name, config in SERVICES_CONFIG.items():
        create_service_workflow(service_name, config)
        print(f"  ✓ Created CI workflow for {service_name} ({config['language']})")
    
    print(f"\\n🎉 Generated CI workflows for {len(SERVICES_CONFIG)} services!")

if __name__ == "__main__":
    main()
