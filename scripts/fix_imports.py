#!/usr/bin/env python3
"""
Script to fix import paths after microservices migration.
"""

import os
import re
from pathlib import Path

def fix_imports_in_file(file_path: Path, service_name: str) -> bool:
    """Fix import statements in a Python file."""
    if not file_path.exists() or file_path.suffix != ".py":
        return False
        
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        original_content = content
        
        # Fix imports from old structure to new structure
        patterns = [
            # From apps.service_name to apps.service_name.src
            (rf"from apps\.{service_name}\.", f"from apps.{service_name}.src."),
            (rf"import apps\.{service_name}\.", f"import apps.{service_name}.src."),
            
            # From service_name to src (within service)
            (rf"from {service_name}\.", "from src."),
            (rf"import {service_name}\.", "import src."),
            
            # Fix relative imports to use src
            (r"from \.(.*)", r"from src.\1"),
        ]
        
        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement, content)
        
        # Update web/admin-portal references
        content = re.sub(r"web/", "apps/web-frontend/", content)
        content = re.sub(r"admin-portal/", "apps/admin-portal/", content)
        
        # Update docker-compose references
        content = re.sub(r"docker-compose", "platform/compose/docker-compose", content)
        
        # Update observability references
        content = re.sub(r"observability/", "platform/shared-observability/", content)
        
        if content != original_content:
            with open(file_path, 'w') as f:
                f.write(content)
            return True
            
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False
    
    return False

def fix_config_files() -> None:
    """Fix configuration files."""
    config_files = [
        "platform/compose/docker-compose.yml",
        "platform/compose/docker-compose.dev.yml", 
        "platform/compose/docker-compose.prod.yml",
        "platform/compose/docker-compose.test.yml"
    ]
    
    for config_file in config_files:
        path = Path(config_file)
        if not path.exists():
            continue
            
        try:
            with open(path, 'r') as f:
                content = f.read()
            
            original_content = content
            
            # Update service build contexts
            services = [
                "api-gateway", "analytics-service", "orchestrator", "router-service",
                "realtime", "ingestion", "billing-service", "tenant-service",
                "chat-adapters", "tool-service", "eval-service", "capacity-monitor",
                "admin-portal"
            ]
            
            for service in services:
                # Update build context
                content = re.sub(
                    rf"build:\s*\.\s*dockerfile:\s*dockerfiles/Dockerfile\.{service}",
                    f"build:\n      context: .\n      dockerfile: apps/{service}/Dockerfile",
                    content
                )
                
                # Update volume mounts
                content = re.sub(
                    rf"- \./apps/{service}:/app",
                    f"- ./apps/{service}/src:/app/src",
                    content
                )
            
            # Update web references
            content = re.sub(r"./web:", "./apps/web-frontend/src:", content)
            content = re.sub(r"dockerfile: dockerfiles/Dockerfile.web", "dockerfile: apps/web-frontend/Dockerfile", content)
            
            if content != original_content:
                with open(path, 'w') as f:
                    f.write(content)
                print(f"Updated {config_file}")
                
        except Exception as e:
            print(f"Error updating {config_file}: {e}")

def main():
    """Main function."""
    print("Fixing import paths after microservices migration...")
    
    services = [
        "api-gateway", "analytics-service", "orchestrator", "router-service",
        "realtime", "ingestion", "billing-service", "tenant-service",
        "chat-adapters", "tool-service", "eval-service", "capacity-monitor",
        "admin-portal"
    ]
    
    files_updated = 0
    
    # Fix imports in service files
    for service in services:
        service_path = Path(f"apps/{service}")
        if not service_path.exists():
            continue
            
        for py_file in service_path.rglob("*.py"):
            if fix_imports_in_file(py_file, service):
                files_updated += 1
                print(f"Updated imports in {py_file}")
    
    # Fix imports in shared libraries
    libs_path = Path("libs")
    if libs_path.exists():
        for py_file in libs_path.rglob("*.py"):
            if fix_imports_in_file(py_file, ""):
                files_updated += 1
                print(f"Updated imports in {py_file}")
    
    # Fix configuration files
    fix_config_files()
    
    print(f"Import path fixes completed! Updated {files_updated} Python files.")

if __name__ == "__main__":
    main()
