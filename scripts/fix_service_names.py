#!/usr/bin/env python3
"""
Fix service names in Kubernetes manifests after renaming services.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Service renames
RENAMES = {
    "agents": "agents-service",
    "tools": "tools-service", 
    "memory": "memory-service"
}

def update_k8s_manifests():
    """Update Kubernetes manifests with new service names."""
    
    for old_name, new_name in RENAMES.items():
        service_path = ROOT / "apps" / "data-plane" / new_name
        if not service_path.exists():
            continue
            
        templates_dir = service_path / "deploy" / "helm" / new_name / "templates"
        if not templates_dir.exists():
            continue
            
        print(f"Updating {new_name} manifests...")
        
        for template_file in templates_dir.glob("*.yaml"):
            content = template_file.read_text()
            
            # Update metadata names
            content = content.replace(f"name: {old_name}", f"name: {new_name}")
            content = content.replace(f"app: {old_name}", f"app: {new_name}")
            
            template_file.write_text(content)
            print(f"  ✅ Updated {template_file.name}")

def main():
    print("=== FIXING SERVICE NAMES IN KUBERNETES MANIFESTS ===")
    update_k8s_manifests()
    print("✅ All service names updated")

if __name__ == "__main__":
    main()
