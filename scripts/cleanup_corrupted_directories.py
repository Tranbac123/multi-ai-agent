#!/usr/bin/env python3
"""
Emergency cleanup script to fix massively corrupted directory structures.
This fixes the deploy/deploy/deploy/... nesting issue affecting all services.
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def log(msg): 
    print(msg)

def find_deepest_valid_helm_chart(service_dir):
    """Find the deepest valid Helm chart with actual content."""
    candidates = []
    
    # Find all Chart.yaml files
    for chart_yaml in service_dir.rglob("Chart.yaml"):
        helm_dir = chart_yaml.parent
        # Check if this looks like a valid helm chart
        if (helm_dir / "values.yaml").exists() and (helm_dir / "templates").exists():
            candidates.append(helm_dir)
    
    if not candidates:
        return None
    
    # Return the one with the most files (likely the most complete)
    best_candidate = max(candidates, key=lambda p: len(list(p.rglob("*"))))
    return best_candidate

def cleanup_service_structure(service_dir, apply=False):
    """Clean up a single service's corrupted directory structure."""
    log(f"  Processing {service_dir.name}")
    
    deploy_dir = service_dir / "deploy"
    if not deploy_dir.exists():
        log(f"    No deploy directory found")
        return
    
    # Find the valid helm chart
    valid_helm = find_deepest_valid_helm_chart(service_dir)
    if not valid_helm:
        log(f"    No valid Helm chart found")
        return
    
    log(f"    Found valid chart at: {valid_helm.relative_to(service_dir)}")
    
    # Expected location
    expected_helm = service_dir / "deploy" / "helm" / service_dir.name
    
    if valid_helm == expected_helm:
        log(f"    ✅ Already in correct location")
        return
    
    if apply:
        # Backup the valid chart
        backup_dir = Path("/tmp") / f"helm-backup-{service_dir.name}"
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        shutil.copytree(valid_helm, backup_dir)
        log(f"    📦 Backed up to {backup_dir}")
        
        # Remove the entire corrupted deploy directory
        shutil.rmtree(deploy_dir)
        log(f"    🗑️  Removed corrupted structure")
        
        # Recreate clean structure
        expected_helm.mkdir(parents=True, exist_ok=True)
        
        # Restore from backup
        for item in backup_dir.iterdir():
            if item.is_dir():
                shutil.copytree(item, expected_helm / item.name)
            else:
                shutil.copy2(item, expected_helm / item.name)
        
        log(f"    ✅ Restored to {expected_helm.relative_to(service_dir)}")
        
        # Cleanup backup
        shutil.rmtree(backup_dir)
    else:
        log(f"    [DRY-RUN] Would restore {valid_helm.relative_to(service_dir)} → deploy/helm/{service_dir.name}")

def main():
    parser = argparse.ArgumentParser(description="Fix corrupted directory structures")
    parser.add_argument("--apply", action="store_true", help="Actually apply fixes (default: dry run)")
    args = parser.parse_args()
    
    log("=== DIRECTORY CORRUPTION CLEANUP ===")
    log("")
    
    # Find all services with corrupted structures
    services_to_fix = []
    
    for apps_dir in ["apps/control-plane", "apps/data-plane"]:
        apps_path = ROOT / apps_dir
        if not apps_path.exists():
            continue
            
        for service_dir in apps_path.iterdir():
            if service_dir.is_dir() and not service_dir.name.startswith('.'):
                # Check for corruption signs
                deploy_deploy = service_dir / "deploy" / "deploy"
                if deploy_deploy.exists():
                    services_to_fix.append(service_dir)
    
    log(f"Found {len(services_to_fix)} services with corrupted structures:")
    for service_dir in services_to_fix:
        log(f"  - {service_dir.relative_to(ROOT)}")
    
    log("")
    
    if not services_to_fix:
        log("✅ No corrupted services found!")
        return
    
    # Process each service
    log("Processing services:")
    for service_dir in services_to_fix:
        cleanup_service_structure(service_dir, apply=args.apply)
    
    log("")
    log("=== SUMMARY ===")
    if args.apply:
        log("✅ Cleanup applied successfully!")
        log("Run the following to verify:")
        log("  find apps/ -name 'Chart.yaml' | wc -l")
        log("  # Should show exactly 24 services")
    else:
        log("ℹ️  Dry run completed. Use --apply to execute changes.")
        log("  python scripts/cleanup_corrupted_directories.py --apply")

if __name__ == "__main__":
    main()
