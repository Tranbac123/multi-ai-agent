#!/usr/bin/env python3
"""
Fix missing Makefile targets across all services.
"""

import os
import glob

def add_missing_docker_targets(service_name: str) -> bool:
    """Add missing docker-build and docker-push targets to service Makefile."""
    makefile_path = f"apps/{service_name}/Makefile"
    
    if not os.path.exists(makefile_path):
        print(f"❌ {service_name}: Makefile not found")
        return False
    
    try:
        with open(makefile_path, 'r') as f:
            content = f.read()
        
        # Check if targets already exist
        has_docker_build = "docker-build:" in content
        has_docker_push = "docker-push:" in content
        
        if has_docker_build and has_docker_push:
            print(f"✅ {service_name}: Docker targets already exist")
            return True
        
        # Add missing targets
        additional_targets = ""
        
        if not has_docker_build:
            additional_targets += f"""
docker-build: ## Build Docker image
\t@echo "🐳 Building Docker image for {service_name}..."
\tdocker build -t {service_name}:latest .
\tdocker build -t {service_name}:$$(git rev-parse --short HEAD) .
\t@echo "✅ Docker image built: {service_name}:latest"
"""
        
        if not has_docker_push:
            additional_targets += f"""
docker-push: docker-build ## Push Docker image to registry
\t@echo "🚀 Pushing Docker image for {service_name}..."
\t@if [ -z "$${{DOCKER_REGISTRY}}" ]; then \\
\t\techo "❌ DOCKER_REGISTRY environment variable not set"; \\
\t\texit 1; \\
\tfi
\tdocker tag {service_name}:latest $${{DOCKER_REGISTRY}}/{service_name}:latest
\tdocker tag {service_name}:$$(git rev-parse --short HEAD) $${{DOCKER_REGISTRY}}/{service_name}:$$(git rev-parse --short HEAD)
\tdocker push $${{DOCKER_REGISTRY}}/{service_name}:latest
\tdocker push $${{DOCKER_REGISTRY}}/{service_name}:$$(git rev-parse --short HEAD)
\t@echo "✅ Docker image pushed: $${{DOCKER_REGISTRY}}/{service_name}:latest"
"""
        
        # Append the new targets
        updated_content = content + additional_targets
        
        with open(makefile_path, 'w') as f:
            f.write(updated_content)
        
        added_targets = []
        if not has_docker_build:
            added_targets.append("docker-build")
        if not has_docker_push:
            added_targets.append("docker-push")
        
        print(f"✅ {service_name}: Added targets: {', '.join(added_targets)}")
        return True
        
    except Exception as e:
        print(f"❌ {service_name}: Failed to update Makefile: {e}")
        return False

def fix_frontend_makefile_targets():
    """Fix frontend-specific Makefile issues."""
    # web-frontend doesn't need a migrate target
    makefile_path = "apps/web-frontend/Makefile"
    
    if not os.path.exists(makefile_path):
        return False
    
    try:
        with open(makefile_path, 'r') as f:
            content = f.read()
        
        if "migrate:" not in content:
            # Add a no-op migrate target for consistency
            migrate_target = """
migrate: ## No-op migrate for frontend service
\t@echo "⚠️ No database migrations needed for frontend service"
"""
            content += migrate_target
            
            with open(makefile_path, 'w') as f:
                f.write(content)
            
            print("✅ web-frontend: Added no-op migrate target")
            return True
            
    except Exception as e:
        print(f"❌ web-frontend: Failed to fix migrate target: {e}")
        return False
    
    return True

def get_all_services():
    """Get all service directories."""
    services = []
    apps_dir = "apps"
    
    if os.path.exists(apps_dir):
        for item in os.listdir(apps_dir):
            item_path = os.path.join(apps_dir, item)
            if os.path.isdir(item_path) and not item.startswith('.'):
                services.append(item)
    
    return sorted(services)

def main():
    print("🔧 Fixing missing Makefile targets across all services...")
    
    services = get_all_services()
    success_count = 0
    
    for service in services:
        if add_missing_docker_targets(service):
            success_count += 1
    
    # Fix frontend-specific issues
    fix_frontend_makefile_targets()
    
    print(f"\n📊 Summary:")
    print(f"   ✅ Updated: {success_count}/{len(services)} services")
    print(f"   🐳 Added docker-build and docker-push targets")
    print(f"   📱 Fixed frontend-specific issues")
    
    if success_count == len(services):
        print(f"\n🎉 All Makefile targets fixed successfully!")
    else:
        print(f"\n⚠️ Some services need manual attention")

if __name__ == "__main__":
    main()
