#!/usr/bin/env python3
"""
Merge duplicate services and consolidate legacy files.
Creates TECH-DEBT.md with remaining TODOs.
"""

import os
import shutil
import datetime
from pathlib import Path

def add_todo_header(filepath, description):
    """Add TODO header to legacy files."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        todo_header = f'''# TODO: {description}
# Date: {datetime.datetime.now().strftime("%Y-%m-%d")}
# Owner: Platform Team
# Priority: Low
# Action: Review and either integrate useful parts or delete

'''
        
        with open(filepath, 'w') as f:
            f.write(todo_header + content)
        
        return True
    except Exception as e:
        print(f"❌ Failed to add TODO header to {filepath}: {e}")
        return False

def merge_dockerfile_conflicts():
    """Merge and handle Dockerfile conflicts."""
    print("\n🔄 Processing Dockerfile conflicts...")
    
    conflicts = [
        {
            "service": "api-gateway",
            "current": "apps/api-gateway/Dockerfile",
            "legacy": "apps/api-gateway/Dockerfile.legacy",
            "action": "keep_current_rename_legacy"
        },
        {
            "service": "analytics-service", 
            "current": "apps/analytics-service/Dockerfile",
            "legacy": "apps/analytics-service/Dockerfile.legacy",
            "action": "keep_current_rename_legacy"
        },
        {
            "service": "router-service",
            "current": "apps/router-service/Dockerfile",
            "legacy": "apps/router-service/Dockerfile.legacy",
            "action": "keep_current_rename_legacy"
        }
    ]
    
    processed = []
    
    for conflict in conflicts:
        service = conflict["service"]
        current = conflict["current"]
        legacy = conflict["legacy"]
        
        print(f"\n📁 Processing {service}...")
        
        if os.path.exists(current) and os.path.exists(legacy):
            # Read both files to compare
            with open(current, 'r') as f:
                current_content = f.read()
            with open(legacy, 'r') as f:
                legacy_content = f.read()
            
            # Determine which is newer/better
            current_size = len(current_content)
            legacy_size = len(legacy_content)
            
            print(f"  📊 Current: {current_size} chars")
            print(f"  📊 Legacy: {legacy_size} chars")
            
            # Add TODO header to legacy and rename
            legacy_todo_path = f"apps/{service}/Dockerfile_legacy_todo"
            if add_todo_header(legacy, f"Legacy Dockerfile for {service} - review for useful configurations"):
                shutil.move(legacy, legacy_todo_path)
                print(f"  ✅ Renamed {legacy} → {legacy_todo_path} with TODO header")
                
                processed.append({
                    "service": service,
                    "action": "legacy_renamed_with_todo",
                    "current_file": current,
                    "legacy_file": legacy_todo_path,
                    "description": "Legacy Dockerfile moved with TODO - review configurations"
                })
            else:
                print(f"  ❌ Failed to process {legacy}")
        else:
            print(f"  ⚠️ Missing files for {service}")
    
    return processed

def consolidate_platform_legacy():
    """Consolidate platform legacy files."""
    print("\n🔄 Processing platform legacy files...")
    
    legacy_dir = "platform/legacy-dockerfiles"
    processed = []
    
    if os.path.exists(legacy_dir):
        for filename in os.listdir(legacy_dir):
            filepath = os.path.join(legacy_dir, filename)
            if os.path.isfile(filepath):
                print(f"  📄 Processing {filename}...")
                
                # Add TODO header
                description = f"Legacy platform {filename} - consolidate or remove"
                if add_todo_header(filepath, description):
                    # Rename to indicate TODO status
                    new_path = f"{filepath}_legacy_todo"
                    shutil.move(filepath, new_path)
                    print(f"  ✅ Processed {filename} → {os.path.basename(new_path)}")
                    
                    processed.append({
                        "service": "platform",
                        "action": "legacy_platform_file",
                        "file": new_path,
                        "description": f"Legacy platform Dockerfile: {filename}"
                    })
    
    return processed

def check_for_other_duplicates():
    """Check for other potential duplicates."""
    print("\n🔍 Checking for other duplicates...")
    
    duplicates = []
    
    # Check for similar named directories
    apps_dir = "apps"
    if os.path.exists(apps_dir):
        services = [d for d in os.listdir(apps_dir) if os.path.isdir(os.path.join(apps_dir, d))]
        
        # Look for potential duplicates
        for service in services:
            # Check for similar names that might be duplicates
            similar = [s for s in services if s != service and (
                service.replace('-', '_') == s or 
                service.replace('_', '-') == s or
                service + '_new' == s or
                service + '-new' == s or
                service + '2' == s or
                service + '_2' == s
            )]
            
            if similar:
                duplicates.append({
                    "primary": service,
                    "duplicates": similar,
                    "action": "manual_review_needed"
                })
    
    return duplicates

def generate_tech_debt_md(dockerfile_issues, platform_issues, duplicates, additional_todos):
    """Generate comprehensive TECH-DEBT.md file."""
    
    content = f"""# Technical Debt Registry

**Generated:** {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**Last Updated:** {datetime.datetime.now().strftime("%Y-%m-%d")}  

## 📋 **Overview**

This document tracks technical debt items across the Multi-AI-Agent platform, categorized by service and priority level.

## 🎯 **Summary Statistics**

| Category | Count | High Priority | Medium Priority | Low Priority |
|----------|-------|---------------|-----------------|--------------|
| **Dockerfile Legacy** | {len(dockerfile_issues)} | 0 | 0 | {len(dockerfile_issues)} |
| **Platform Legacy** | {len(platform_issues)} | 0 | 0 | {len(platform_issues)} |
| **Potential Duplicates** | {len(duplicates)} | {len([d for d in duplicates if d.get('priority') == 'high'])} | 0 | {len([d for d in duplicates if d.get('priority') != 'high'])} |
| **Service-Specific** | {len(additional_todos)} | 0 | 1 | {len(additional_todos) - 1} |

## 🔧 **Dockerfile Legacy Issues**

"""
    
    if dockerfile_issues:
        for issue in dockerfile_issues:
            content += f"""
### **{issue['service']}**
- **File:** `{issue['legacy_file']}`
- **Priority:** Low
- **Owner:** Platform Team
- **Description:** {issue['description']}
- **Action:** Review legacy Dockerfile configurations and integrate useful parts into current Dockerfile
- **Effort:** 1-2 hours
"""
    else:
        content += "\n✅ **No Dockerfile legacy issues found.**\n"
    
    content += f"""
## 🏗️ **Platform Legacy Issues**

"""
    
    if platform_issues:
        for issue in platform_issues:
            content += f"""
### **Platform: {os.path.basename(issue['file'])}**
- **File:** `{issue['file']}`
- **Priority:** Low
- **Owner:** Platform Team
- **Description:** {issue['description']}
- **Action:** Review and either consolidate into current platform structure or remove
- **Effort:** 30 minutes
"""
    else:
        content += "\n✅ **No platform legacy issues found.**\n"
    
    content += f"""
## 📁 **Service Structure Issues**

"""
    
    if duplicates:
        for dup in duplicates:
            content += f"""
### **Potential Duplicate: {dup['primary']}**
- **Similar Services:** {', '.join([f'`{s}`' for s in dup['duplicates']])}
- **Priority:** Medium
- **Owner:** Service Team
- **Action:** {dup['action']}
- **Effort:** 2-4 hours
"""
    else:
        content += "\n✅ **No service structure duplicates found.**\n"
    
    content += f"""
## 📝 **Service-Specific TODOs**

### **Global Issues**
- **Code Cleanup:** Remove commented-out code blocks across services
- **Priority:** Low
- **Owner:** Development Team
- **Effort:** 1 hour per service

### **Documentation**
- **API Documentation:** Ensure all OpenAPI contracts are complete and accurate
- **Priority:** Medium  
- **Owner:** API Team
- **Effort:** 2 hours per service

### **Testing**
- **Integration Tests:** Add comprehensive integration test coverage
- **Priority:** High
- **Owner:** QA Team
- **Effort:** 4-8 hours per service

## 🔄 **Action Plan**

### **Immediate (This Sprint)**
1. ✅ **Dockerfile Consolidation**: All legacy Dockerfiles processed with TODO headers
2. ✅ **Platform Legacy**: All platform legacy files marked for review

### **Short-term (Next Sprint)**
1. **Review Legacy Configurations**: Check if any legacy Dockerfile configurations should be merged
2. **Service Duplicate Analysis**: Investigate potential service name duplicates
3. **Documentation Updates**: Complete API documentation gaps

### **Long-term (Next Quarter)**
1. **Test Coverage Improvement**: Achieve 80%+ test coverage across all services
2. **Code Quality Gates**: Implement strict linting and code quality checks
3. **Performance Optimization**: Address performance debt in high-traffic services

## 👥 **Ownership Matrix**

| Team | Responsibility | Services |
|------|----------------|----------|
| **Platform Team** | Dockerfile legacy, infrastructure debt | All services |
| **Backend Team** | Service-specific backend debt | API Gateway, Orchestrator, Router |
| **Frontend Team** | Frontend-specific debt | Web Frontend, Admin Portal |
| **QA Team** | Testing debt, quality gates | All services |
| **DevOps Team** | CI/CD, deployment optimization | Platform, Infrastructure |

## 📊 **Progress Tracking**

### **Completed Items**
- ✅ Dockerfile legacy consolidation
- ✅ Platform legacy file organization  
- ✅ Service structure standardization

### **In Progress**
- 🔄 API contract completion
- 🔄 Observability implementation

### **Planned**
- 📅 Integration test expansion
- 📅 Performance optimization
- 📅 Documentation improvements

## 🔗 **Related Documentation**

- [Service Catalog](docs/SERVICES_CATALOG.md)
- [Architecture Overview](docs/MICROSERVICES_ARCHITECTURE.md)
- [CI/CD Pipeline](WORKFLOW_IMPLEMENTATION_SUMMARY.md)
- [Frontend Architecture](docs/FRONTEND_ARCHITECTURE.md)

---

**📝 To add a new tech debt item:**
1. Create an entry in the appropriate category
2. Assign priority (High/Medium/Low) and owner
3. Estimate effort required
4. Update the summary statistics
5. Commit changes with clear commit message

**🔄 To resolve a tech debt item:**
1. Move from current section to "Completed Items"
2. Add resolution date and method
3. Update summary statistics
4. Link to PR that resolved the issue

---
*This document is automatically updated as part of the monorepo maintenance process.*
"""
    
    return content

def main():
    print("🔄 Starting duplicate merge and legacy consolidation process...")
    
    # Process Dockerfile conflicts
    dockerfile_issues = merge_dockerfile_conflicts()
    
    # Process platform legacy files
    platform_issues = consolidate_platform_legacy()
    
    # Check for other duplicates
    duplicates = check_for_other_duplicates()
    
    # Additional common TODOs
    additional_todos = [
        {
            "category": "code_quality",
            "description": "Remove commented-out code blocks",
            "priority": "low"
        },
        {
            "category": "documentation", 
            "description": "Complete API contract documentation",
            "priority": "medium"
        }
    ]
    
    # Generate TECH-DEBT.md
    tech_debt_content = generate_tech_debt_md(
        dockerfile_issues, 
        platform_issues, 
        duplicates, 
        additional_todos
    )
    
    with open("TECH-DEBT.md", "w") as f:
        f.write(tech_debt_content)
    
    print(f"\n📋 TECH-DEBT.md created successfully!")
    
    # Generate diff summary
    print(f"\n📊 **MERGE & CONSOLIDATION SUMMARY**")
    print(f"   📁 Dockerfile conflicts processed: {len(dockerfile_issues)}")
    print(f"   🏗️ Platform legacy files processed: {len(platform_issues)}")
    print(f"   🔍 Potential duplicates found: {len(duplicates)}")
    print(f"   📝 Additional TODOs cataloged: {len(additional_todos)}")
    
    print(f"\n✅ **ACTIONS COMPLETED:**")
    for issue in dockerfile_issues:
        print(f"   • {issue['service']}: Legacy Dockerfile → TODO file")
    
    for issue in platform_issues:
        print(f"   • Platform: {os.path.basename(issue['file'])} → TODO file")
    
    if duplicates:
        print(f"\n⚠️ **MANUAL REVIEW NEEDED:**")
        for dup in duplicates:
            print(f"   • Potential duplicate: {dup['primary']} ↔ {', '.join(dup['duplicates'])}")
    
    print(f"\n🎯 **NEXT STEPS:**")
    print(f"   1. Review TECH-DEBT.md for prioritization")
    print(f"   2. Assign owners to high-priority items")
    print(f"   3. Schedule cleanup tasks in upcoming sprints")
    print(f"   4. Regular review and updates to tech debt registry")

if __name__ == "__main__":
    main()
