#!/usr/bin/env python3
"""
Validate all GitHub workflow files for syntax and completeness.
"""

import yaml
import os
from pathlib import Path
from typing import List, Dict

def validate_yaml_syntax(file_path: Path) -> tuple[bool, str]:
    """Validate YAML syntax of a file."""
    try:
        with open(file_path, 'r') as f:
            yaml.safe_load(f)
        return True, "Valid YAML syntax"
    except yaml.YAMLError as e:
        return False, f"YAML syntax error: {e}"
    except Exception as e:
        return False, f"Error reading file: {e}"

def validate_workflow_structure(file_path: Path) -> tuple[bool, List[str]]:
    """Validate GitHub workflow structure."""
    issues = []
    
    try:
        with open(file_path, 'r') as f:
            workflow = yaml.safe_load(f)
        
        # Check required top-level keys
        if 'name' not in workflow:
            issues.append("Missing 'name' field")
        
        if 'on' not in workflow:
            issues.append("Missing 'on' field")
        
        if 'jobs' not in workflow:
            issues.append("Missing 'jobs' field")
        
        # Check jobs structure
        if 'jobs' in workflow:
            for job_name, job_config in workflow['jobs'].items():
                if not isinstance(job_config, dict):
                    issues.append(f"Job '{job_name}' is not a dictionary")
                    continue
                
                # Check for uses or runs-on
                if 'uses' not in job_config and 'runs-on' not in job_config:
                    issues.append(f"Job '{job_name}' missing 'runs-on' or 'uses'")
        
        return len(issues) == 0, issues
        
    except Exception as e:
        return False, [f"Error validating structure: {e}"]

def check_service_workflow_completeness(service_name: str) -> tuple[bool, List[str]]:
    """Check if service has complete workflow setup."""
    issues = []
    service_path = Path(f"apps/{service_name}")
    
    # Check if service workflow exists
    workflow_file = service_path / ".github/workflows/ci.yaml"
    if not workflow_file.exists():
        issues.append(f"Missing CI workflow at {workflow_file}")
        return False, issues
    
    # Validate workflow content
    try:
        with open(workflow_file, 'r') as f:
            workflow = yaml.safe_load(f)
        
        # Check if it uses the reusable template
        jobs = workflow.get('jobs', {})
        found_reusable_job = False
        
        for job_name, job_config in jobs.items():
            if isinstance(job_config, dict) and 'uses' in job_config:
                if 'service-ci.yaml' in job_config['uses']:
                    found_reusable_job = True
                    break
        
        if not found_reusable_job:
            issues.append("Workflow doesn't use reusable service-ci.yaml template")
        
        # Check path filters
        on_config = workflow.get('on', {})
        if isinstance(on_config, dict):
            push_config = on_config.get('push', {})
            if isinstance(push_config, dict):
                paths = push_config.get('paths', [])
                expected_path = f"apps/{service_name}/**"
                if expected_path not in paths:
                    issues.append(f"Missing path filter for {expected_path}")
        
    except Exception as e:
        issues.append(f"Error validating workflow content: {e}")
    
    return len(issues) == 0, issues

def main():
    """Main validation function."""
    print("🔍 Validating GitHub Workflows...")
    print("=" * 50)
    
    # Define all workflow files to check
    workflow_files = []
    
    # Platform workflows
    platform_workflows = [
        ".github/workflows/changed-services.yaml",
        ".github/workflows/platform-ci.yaml", 
        ".github/workflows/platform-health.yaml",
        ".github/workflows/security-scan.yaml",
        ".github/workflows/service-ci.yaml",
    ]
    
    # Reusable templates
    template_files = [
        "platform/ci-templates/service-ci.yaml"
    ]
    
    # Service workflows
    services = [
        "api-gateway", "analytics-service", "orchestrator", "router-service",
        "realtime", "ingestion", "billing-service", "tenant-service",
        "chat-adapters", "tool-service", "eval-service", "capacity-monitor", 
        "admin-portal", "web-frontend"
    ]
    
    service_workflows = [f"apps/{service}/.github/workflows/ci.yaml" for service in services]
    
    workflow_files = platform_workflows + template_files + service_workflows
    
    # Validation results
    total_files = 0
    valid_files = 0
    syntax_errors = 0
    structure_errors = 0
    
    print("\\n📋 YAML Syntax Validation")
    print("-" * 30)
    
    for file_path in workflow_files:
        path = Path(file_path)
        total_files += 1
        
        if not path.exists():
            print(f"❌ {file_path} - File not found")
            continue
        
        # Validate YAML syntax
        syntax_valid, syntax_message = validate_yaml_syntax(path)
        
        if syntax_valid:
            print(f"✅ {file_path} - {syntax_message}")
            valid_files += 1
        else:
            print(f"❌ {file_path} - {syntax_message}")
            syntax_errors += 1
            continue
        
        # Validate workflow structure
        structure_valid, structure_issues = validate_workflow_structure(path)
        
        if not structure_valid:
            print(f"⚠️  {file_path} - Structure issues:")
            for issue in structure_issues:
                print(f"   • {issue}")
            structure_errors += 1
    
    print("\\n🔧 Service Workflow Completeness")
    print("-" * 35)
    
    service_issues = 0
    
    for service in services:
        complete, issues = check_service_workflow_completeness(service)
        
        if complete:
            print(f"✅ {service} - Complete workflow setup")
        else:
            print(f"❌ {service} - Issues found:")
            for issue in issues:
                print(f"   • {issue}")
            service_issues += 1
    
    # Summary
    print("\\n📊 Validation Summary")
    print("=" * 25)
    print(f"Total workflow files: {total_files}")
    print(f"Valid syntax: {valid_files}")
    print(f"Syntax errors: {syntax_errors}")
    print(f"Structure issues: {structure_errors}")
    print(f"Service workflow issues: {service_issues}")
    
    # Overall status
    print("\\n🎯 Overall Status")
    print("-" * 20)
    
    if syntax_errors == 0 and structure_errors == 0 and service_issues == 0:
        print("🎉 All workflows are valid and complete!")
        return 0
    else:
        print("⚠️  Some issues found that need attention:")
        if syntax_errors > 0:
            print(f"   • {syntax_errors} files with YAML syntax errors")
        if structure_errors > 0:
            print(f"   • {structure_errors} files with structure issues") 
        if service_issues > 0:
            print(f"   • {service_issues} services with incomplete workflows")
        return 1

if __name__ == "__main__":
    exit(main())
