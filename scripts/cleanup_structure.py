#!/usr/bin/env python3
"""
Clean up corrupted nested directory structures in migrated services.
"""

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def fix_service_structure(service_path: Path):
    """Fix corrupted nested helm structure in a service."""
    service_name = service_path.name
    helm_dir = service_path / "deploy" / "helm"
    
    if not helm_dir.exists():
        return False
        
    # Find the correct Chart.yaml
    chart_files = list(helm_dir.rglob("Chart.yaml"))
    if not chart_files:
        return False
    
    # Find the one that's in the correct service subdirectory
    correct_chart = None
    for chart in chart_files:
        if chart.parent.name == service_name:
            correct_chart = chart
            break
    
    if not correct_chart:
        # Take the first one found
        correct_chart = chart_files[0]
    
    correct_helm_service_dir = correct_chart.parent
    
    # Check if we have nested structure
    nested_dirs = [d for d in helm_dir.rglob("*") if d.is_dir() and d.name == "helm"]
    
    if nested_dirs:
        print(f"Fixing {service_name}: nested helm directories found")
        
        # Backup the correct helm service directory
        backup_dir = Path(f"/tmp/{service_name}-helm-backup")
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        shutil.copytree(correct_helm_service_dir, backup_dir)
        
        # Remove the entire corrupted structure
        shutil.rmtree(helm_dir)
        
        # Recreate clean structure
        helm_dir.mkdir(parents=True)
        shutil.move(str(backup_dir), str(helm_dir / service_name))
        
        print(f"  ✅ Fixed {service_name} helm structure")
        return True
    
    return False

def main():
    print("=== CLEANING UP CORRUPTED SERVICE STRUCTURES ===")
    
    fixed_count = 0
    
    # Find all services
    for service_dir in (ROOT / "apps").rglob("deploy/helm"):
        service_path = service_dir.parents[1]  # Go up from deploy/helm to service root
        
        if fix_service_structure(service_path):
            fixed_count += 1
    
    print(f"\n✅ Fixed {fixed_count} services with corrupted structures")
    
    # Verify cleanup
    nested_dirs = list((ROOT / "apps").rglob("helm/*/helm"))
    if nested_dirs:
        print(f"⚠️  Still found {len(nested_dirs)} nested helm directories:")
        for d in nested_dirs[:5]:
            print(f"   {d}")
    else:
        print("✅ No more nested helm directories found")

if __name__ == "__main__":
    main()
