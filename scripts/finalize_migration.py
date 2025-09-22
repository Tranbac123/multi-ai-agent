#!/usr/bin/env python3
"""
Script to finalize the migration by moving source code and cleaning up old structures.
"""

import os
import shutil
import subprocess
from pathlib import Path

def backup_and_move_source(service_name: str) -> None:
    """Move existing source code to the new structure."""
    old_path = Path(f"apps/{service_name}")
    
    # Skip if already migrated
    if (old_path / "src").exists():
        print(f"✓ {service_name} already has src/ directory")
        return
    
    # Create backup
    backup_path = Path(f"apps/{service_name}_legacy")
    if old_path.exists():
        print(f"Creating backup: {backup_path}")
        shutil.copytree(old_path, backup_path, dirs_exist_ok=True)
        
        # Move Python files to src/
        src_path = old_path / "src"
        src_path.mkdir(exist_ok=True)
        
        for item in old_path.iterdir():
            if item.is_file() and item.suffix == ".py":
                print(f"Moving {item.name} to src/")
                shutil.move(str(item), str(src_path / item.name))
            elif item.is_dir() and item.name not in ["src", "db", "contracts", "deploy", "observability", "tests", ".github"]:
                print(f"Moving directory {item.name} to src/")
                shutil.move(str(item), str(src_path / item.name))

def update_imports_in_file(file_path: Path, service_name: str) -> None:
    """Update import statements to reflect new structure."""
    if not file_path.exists() or file_path.suffix != ".py":
        return
        
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Update imports
        old_imports = [
            f"from apps.{service_name}.",
            f"import apps.{service_name}.",
            f"from {service_name}.",
            f"import {service_name}."
        ]
        
        new_imports = [
            f"from apps.{service_name}.src.",
            f"import apps.{service_name}.src.",
            f"from src.",
            f"import src."
        ]
        
        modified = False
        for old, new in zip(old_imports, new_imports):
            if old in content:
                content = content.replace(old, new)
                modified = True
        
        if modified:
            with open(file_path, 'w') as f:
                f.write(content)
            print(f"Updated imports in {file_path}")
    
    except Exception as e:
        print(f"Error updating {file_path}: {e}")

def update_docker_compose() -> None:
    """Update docker-compose files to use new structure."""
    compose_files = [
        "docker-compose.yml",
        "docker-compose.dev.yml",
        "docker-compose.prod.yml"
    ]
    
    for compose_file in compose_files:
        path = Path(compose_file)
        if not path.exists():
            continue
            
        print(f"Updating {compose_file}")
        try:
            with open(path, 'r') as f:
                content = f.read()
            
            # Update build contexts to use service-specific Dockerfiles
            services = [
                "api-gateway", "analytics-service", "orchestrator", "router-service",
                "realtime", "ingestion", "billing-service", "tenant-service",
                "chat-adapters", "tool-service", "eval-service", "capacity-monitor"
            ]
            
            for service in services:
                old_dockerfile = f"dockerfiles/Dockerfile.{service}"
                new_dockerfile = f"apps/{service}/Dockerfile"
                content = content.replace(old_dockerfile, new_dockerfile)
            
            with open(path, 'w') as f:
                f.write(content)
                
        except Exception as e:
            print(f"Error updating {compose_file}: {e}")

def create_root_makefile() -> None:
    """Create root-level Makefile for platform operations."""
    makefile_content = '''# Multi-AI-Agent Platform Makefile
.PHONY: help dev test lint build clean services

# Default target
help:
	@echo "Multi-AI-Agent Platform - Available Commands:"
	@echo ""
	@echo "Development:"
	@echo "  dev          Set up development environment for all services"
	@echo "  test         Run tests for all services"
	@echo "  lint         Run linting for all services"
	@echo "  build        Build all service Docker images"
	@echo "  clean        Clean build artifacts"
	@echo ""
	@echo "Platform:"
	@echo "  services     List all available services"
	@echo "  deploy-dev   Deploy all services to development"
	@echo "  deploy-prod  Deploy all services to production"

# List of all services
SERVICES := api-gateway analytics-service orchestrator router-service realtime \\
            ingestion billing-service tenant-service chat-adapters tool-service \\
            eval-service capacity-monitor

# Development setup
dev:
	@for service in $(SERVICES); do \\
		echo "Setting up $$service..."; \\
		cd apps/$$service && make dev && cd ../..; \\
	done

# Run tests for all services
test:
	@for service in $(SERVICES); do \\
		echo "Testing $$service..."; \\
		cd apps/$$service && make test && cd ../..; \\
	done

# Lint all services
lint:
	@for service in $(SERVICES); do \\
		echo "Linting $$service..."; \\
		cd apps/$$service && make lint && cd ../..; \\
	done

# Build all Docker images
build:
	@for service in $(SERVICES); do \\
		echo "Building $$service..."; \\
		cd apps/$$service && make build && cd ../..; \\
	done

# Clean all artifacts
clean:
	@for service in $(SERVICES); do \\
		echo "Cleaning $$service..."; \\
		cd apps/$$service && make clean && cd ../..; \\
	done
	docker system prune -f

# List all services
services:
	@echo "Available services:"
	@for service in $(SERVICES); do \\
		echo "  - $$service"; \\
	done

# Deploy to development
deploy-dev:
	@echo "Deploying all services to development..."
	kubectl apply -k infra/k8s/overlays/dev

# Deploy to production
deploy-prod:
	@echo "Deploying all services to production..."
	kubectl apply -k infra/k8s/overlays/prod'''
    
    with open("Makefile", "w") as f:
        f.write(makefile_content)
    print("Created root-level Makefile")

def main():
    """Main finalization function."""
    print("Finalizing microservices migration...")
    
    services = [
        "api-gateway", "analytics-service", "orchestrator", "router-service",
        "realtime", "ingestion", "billing-service", "tenant-service", 
        "chat-adapters", "tool-service", "eval-service", "capacity-monitor"
    ]
    
    # Backup and move source code
    for service in services:
        print(f"\\nProcessing {service}...")
        backup_and_move_source(service)
    
    # Update configuration files
    print("\\nUpdating configuration files...")
    update_docker_compose()
    create_root_makefile()
    
    print("\\nMigration finalized!")
    print("\\nRecommended next steps:")
    print("1. Test each service: make test")
    print("2. Update any remaining import paths")
    print("3. Update CI/CD pipelines")
    print("4. Remove _legacy directories after verification")

if __name__ == "__main__":
    main()
