#!/usr/bin/env python3
"""
Final validation script for microservices monorepo refactor.
Validates service isolation, structure, and CI/CD functionality.
"""

import os
import subprocess
import json
import yaml
from pathlib import Path
from typing import List, Dict, Tuple, Any
import sys

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_status(status: str, message: str):
    """Print colored status message."""
    color = Colors.GREEN if status == "PASS" else Colors.RED if status == "FAIL" else Colors.YELLOW
    print(f"  {color}[{status}]{Colors.RESET} {message}")

def print_section(title: str):
    """Print section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")

def run_command(cmd: str, cwd: str = None, capture_output: bool = True) -> Tuple[int, str, str]:
    """Run shell command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            cwd=cwd,
            capture_output=capture_output,
            text=True,
            timeout=60
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)

def get_all_services() -> List[str]:
    """Get list of all services from apps/ directory."""
    apps_dir = "apps"
    if not os.path.exists(apps_dir):
        return []
    
    services = []
    for item in os.listdir(apps_dir):
        item_path = os.path.join(apps_dir, item)
        if os.path.isdir(item_path) and not item.startswith('.') and not item.startswith('__'):
            services.append(item)
    
    return sorted(services)

def validate_service_structure(service: str) -> Dict[str, bool]:
    """Validate that a service has the required structure."""
    service_dir = f"apps/{service}"
    required_items = {
        "src/": False,
        "db/": False,
        "contracts/": False,
        "deploy/": False,
        "observability/": False,
        "tests/": False,
        "Dockerfile": False,
        "README.md": False,
        "Makefile": False,
        ".github/workflows/ci.yaml": False
    }
    
    for item, _ in required_items.items():
        item_path = os.path.join(service_dir, item)
        if item.endswith('/'):
            # Directory
            required_items[item] = os.path.isdir(item_path)
        else:
            # File
            required_items[item] = os.path.isfile(item_path)
    
    return required_items

def validate_makefile_targets(service: str) -> Dict[str, bool]:
    """Validate that service Makefile has required targets."""
    makefile_path = f"apps/{service}/Makefile"
    if not os.path.exists(makefile_path):
        return {}
    
    required_targets = ["dev", "lint", "test", "build", "migrate", "run", "docker-build", "docker-push"]
    found_targets = {}
    
    try:
        with open(makefile_path, 'r') as f:
            content = f.read()
            
        for target in required_targets:
            # Look for target definition (e.g., "dev:" or "dev::") 
            found_targets[target] = f"{target}:" in content or f"{target}::" in content
            
    except Exception:
        return {target: False for target in required_targets}
    
    return found_targets

def test_service_isolation(service: str) -> Dict[str, Any]:
    """Test that service can build in isolation."""
    service_dir = f"apps/{service}"
    results = {
        "makefile_exists": False,
        "make_dev_works": False,
        "make_lint_works": False,
        "make_test_works": False,
        "make_build_works": False,
        "dockerfile_builds": False
    }
    
    # Check Makefile exists
    makefile_path = os.path.join(service_dir, "Makefile")
    results["makefile_exists"] = os.path.exists(makefile_path)
    
    if not results["makefile_exists"]:
        return results
    
    # Test make targets (with timeout and error handling)
    targets_to_test = [
        ("make_dev_works", "dev"),
        ("make_lint_works", "lint"), 
        ("make_test_works", "test"),
        ("make_build_works", "build")
    ]
    
    for result_key, target in targets_to_test:
        print(f"    Testing make {target} for {service}...")
        exit_code, stdout, stderr = run_command(f"make {target}", cwd=service_dir)
        results[result_key] = exit_code == 0
        if exit_code != 0:
            print(f"      ❌ make {target} failed: {stderr[:100]}...")
    
    # Test Docker build
    print(f"    Testing docker build for {service}...")
    exit_code, stdout, stderr = run_command(f"docker build -t {service}-test .", cwd=service_dir)
    results["dockerfile_builds"] = exit_code == 0
    if exit_code != 0:
        print(f"      ❌ Docker build failed: {stderr[:100]}...")
    
    return results

def validate_ci_workflows() -> Dict[str, Any]:
    """Validate CI workflow files."""
    results = {
        "platform_template_exists": False,
        "frontend_template_exists": False,
        "service_workflows": {},
        "path_filtering": True
    }
    
    # Check platform templates
    platform_ci = "platform/ci-templates/service-ci.yaml"
    frontend_ci = "platform/ci-templates/frontend-ci.yaml"
    
    results["platform_template_exists"] = os.path.exists(platform_ci)
    results["frontend_template_exists"] = os.path.exists(frontend_ci)
    
    # Check each service has CI workflow
    services = get_all_services()
    for service in services:
        ci_file = f"apps/{service}/.github/workflows/ci.yaml"
        has_ci = os.path.exists(ci_file)
        
        # If CI exists, check for path filtering
        has_path_filter = False
        if has_ci:
            try:
                with open(ci_file, 'r') as f:
                    content = f.read()
                    # Look for path filter in the CI file
                    has_path_filter = f"apps/{service}/**" in content
            except:
                pass
        
        results["service_workflows"][service] = {
            "has_ci": has_ci,
            "has_path_filter": has_path_filter
        }
    
    return results

def simulate_path_filtered_ci() -> Dict[str, Any]:
    """Simulate path-filtered CI by checking workflow triggers."""
    results = {
        "changed_services_workflow": False,
        "sample_service_trigger": False,
        "path_filter_effectiveness": {}
    }
    
    # Check if changed-services workflow exists
    changed_services_file = ".github/workflows/changed-services.yaml"
    results["changed_services_workflow"] = os.path.exists(changed_services_file)
    
    # Test a sample service trigger simulation
    sample_service = "api-gateway"  # Use a known service
    sample_ci = f"apps/{sample_service}/.github/workflows/ci.yaml"
    
    if os.path.exists(sample_ci):
        try:
            with open(sample_ci, 'r') as f:
                content = f.read()
                # Check if it has proper path filtering
                results["sample_service_trigger"] = (
                    "paths:" in content and 
                    f"apps/{sample_service}/**" in content
                )
        except:
            pass
    
    # Check path filter effectiveness for all services
    services = get_all_services()
    for service in services:
        ci_file = f"apps/{service}/.github/workflows/ci.yaml"
        if os.path.exists(ci_file):
            try:
                with open(ci_file, 'r') as f:
                    content = f.read()
                    # Service should only trigger on its own path changes
                    has_own_path = f"apps/{service}/**" in content
                    # Should not trigger on other service paths
                    other_service_paths = [f"apps/{s}/**" for s in services if s != service]
                    has_other_paths = any(path in content for path in other_service_paths)
                    
                    results["path_filter_effectiveness"][service] = {
                        "has_own_path": has_own_path,
                        "has_other_paths": has_other_paths,  # This should be False
                        "is_effective": has_own_path and not has_other_paths
                    }
            except:
                results["path_filter_effectiveness"][service] = {
                    "has_own_path": False,
                    "has_other_paths": False,
                    "is_effective": False
                }
    
    return results

def check_global_cleanup() -> Dict[str, bool]:
    """Check that global directories have been properly migrated."""
    global_dirs_to_check = {
        "db/": "Should be moved to service-specific db/ directories",
        "k8s/": "Should be moved to service-specific deploy/ directories", 
        "dockerfiles/": "Should be moved to service-specific Dockerfiles",
        "tests/": "Should be moved to service-specific tests/ directories"
    }
    
    results = {}
    for dir_name, description in global_dirs_to_check.items():
        # Check if directory exists and has content
        exists = os.path.exists(dir_name)
        has_content = False
        
        if exists:
            try:
                content = os.listdir(dir_name)
                # Filter out hidden files and common empty directory indicators
                real_content = [f for f in content if not f.startswith('.') and f != '__pycache__']
                has_content = len(real_content) > 0
            except:
                has_content = False
        
        # For validation, we want these directories to NOT exist or be empty
        results[dir_name] = not (exists and has_content)
    
    return results

def generate_checklist_report(services: List[str]) -> Dict[str, Any]:
    """Generate comprehensive checklist report."""
    print_section("🔍 COMPREHENSIVE VALIDATION CHECKLIST")
    
    report = {
        "services_count": len(services),
        "structure_validation": {},
        "isolation_testing": {},
        "ci_validation": {},
        "path_filtering": {},
        "global_cleanup": {},
        "overall_score": 0,
        "failed_items": [],
        "next_steps": []
    }
    
    print(f"\n📊 **Validating {len(services)} services:** {', '.join(services)}")
    
    # 1. Structure Validation
    print(f"\n🏗️ **Service Structure Validation**")
    structure_passed = 0
    for service in services:
        print(f"\n  📁 {service}:")
        structure = validate_service_structure(service)
        makefile_targets = validate_makefile_targets(service)
        
        # Combine structure and makefile validation
        all_checks = {**structure, **{f"makefile_{k}": v for k, v in makefile_targets.items()}}
        service_passed = sum(all_checks.values())
        service_total = len(all_checks)
        
        report["structure_validation"][service] = {
            "passed": service_passed,
            "total": service_total,
            "percentage": (service_passed / service_total * 100) if service_total > 0 else 0,
            "details": all_checks
        }
        
        # Print individual results
        for item, passed in structure.items():
            print_status("PASS" if passed else "FAIL", f"{item}")
            if not passed:
                report["failed_items"].append(f"{service}: Missing {item}")
        
        for target, passed in makefile_targets.items():
            print_status("PASS" if passed else "FAIL", f"Makefile target: {target}")
            if not passed:
                report["failed_items"].append(f"{service}: Missing Makefile target {target}")
        
        if service_passed == service_total:
            structure_passed += 1
    
    # 2. Isolation Testing (sample a few services to avoid long runtime)
    print(f"\n🧪 **Service Isolation Testing** (Sample)")
    sample_services = services[:3]  # Test first 3 services as sample
    isolation_passed = 0
    
    for service in sample_services:
        print(f"\n  🔬 Testing {service} isolation:")
        isolation_results = test_service_isolation(service)
        
        service_isolation_passed = sum(isolation_results.values())
        service_isolation_total = len(isolation_results)
        
        report["isolation_testing"][service] = {
            "passed": service_isolation_passed,
            "total": service_isolation_total,
            "percentage": (service_isolation_passed / service_isolation_total * 100) if service_isolation_total > 0 else 0,
            "details": isolation_results
        }
        
        for test, passed in isolation_results.items():
            print_status("PASS" if passed else "FAIL", f"{test.replace('_', ' ').title()}")
            if not passed:
                report["failed_items"].append(f"{service}: Failed {test}")
        
        if service_isolation_passed == service_isolation_total:
            isolation_passed += 1
    
    # 3. CI/CD Validation
    print(f"\n🔄 **CI/CD Pipeline Validation**")
    ci_results = validate_ci_workflows()
    
    print_status("PASS" if ci_results["platform_template_exists"] else "FAIL", 
                "Platform CI template exists")
    print_status("PASS" if ci_results["frontend_template_exists"] else "FAIL", 
                "Frontend CI template exists")
    
    services_with_ci = sum(1 for s in ci_results["service_workflows"].values() if s["has_ci"])
    services_with_path_filter = sum(1 for s in ci_results["service_workflows"].values() if s["has_path_filter"])
    
    print_status("PASS" if services_with_ci == len(services) else "FAIL",
                f"All services have CI workflows ({services_with_ci}/{len(services)})")
    print_status("PASS" if services_with_path_filter == len(services) else "FAIL",
                f"All services have path filtering ({services_with_path_filter}/{len(services)})")
    
    report["ci_validation"] = {
        "platform_template": ci_results["platform_template_exists"],
        "frontend_template": ci_results["frontend_template_exists"],
        "services_with_ci": services_with_ci,
        "services_with_path_filter": services_with_path_filter,
        "total_services": len(services)
    }
    
    # 4. Path Filtering Simulation
    print(f"\n🎯 **Path Filtering Effectiveness**")
    path_filter_results = simulate_path_filtered_ci()
    
    print_status("PASS" if path_filter_results["changed_services_workflow"] else "FAIL",
                "Changed services detection workflow exists")
    print_status("PASS" if path_filter_results["sample_service_trigger"] else "FAIL",
                "Sample service has proper path filtering")
    
    effective_filters = sum(1 for s in path_filter_results["path_filter_effectiveness"].values() 
                           if s["is_effective"])
    total_filters = len(path_filter_results["path_filter_effectiveness"])
    
    print_status("PASS" if effective_filters == total_filters else "FAIL",
                f"Path filtering is effective ({effective_filters}/{total_filters})")
    
    report["path_filtering"] = path_filter_results
    
    # 5. Global Cleanup Validation
    print(f"\n🧹 **Global Directory Cleanup**")
    cleanup_results = check_global_cleanup()
    
    for directory, is_clean in cleanup_results.items():
        print_status("PASS" if is_clean else "FAIL", 
                    f"Global {directory} directory {'cleaned' if is_clean else 'still has content'}")
        if not is_clean:
            report["failed_items"].append(f"Global {directory} directory not properly migrated")
    
    report["global_cleanup"] = cleanup_results
    
    # Calculate overall score
    total_checks = (
        structure_passed +
        isolation_passed + 
        (1 if ci_results["platform_template_exists"] else 0) +
        (1 if ci_results["frontend_template_exists"] else 0) +
        (1 if services_with_ci == len(services) else 0) +
        (1 if services_with_path_filter == len(services) else 0) +
        (1 if path_filter_results["changed_services_workflow"] else 0) +
        (1 if effective_filters == total_filters else 0) +
        sum(cleanup_results.values())
    )
    
    max_checks = (
        len(services) +  # structure validation
        len(sample_services) +  # isolation testing
        6 +  # CI validation checks
        len(cleanup_results)  # cleanup checks
    )
    
    report["overall_score"] = (total_checks / max_checks * 100) if max_checks > 0 else 0
    
    return report

def generate_next_steps(report: Dict[str, Any]) -> List[str]:
    """Generate next steps based on validation results."""
    next_steps = []
    
    if report["failed_items"]:
        next_steps.append("🔧 Fix failed validation items:")
        for item in report["failed_items"][:5]:  # Show first 5
            next_steps.append(f"   • {item}")
        if len(report["failed_items"]) > 5:
            next_steps.append(f"   • ... and {len(report['failed_items']) - 5} more items")
    
    # Check specific issues
    structure_issues = [s for s, data in report["structure_validation"].items() 
                       if data["percentage"] < 100]
    if structure_issues:
        next_steps.append(f"📁 Complete service structure for: {', '.join(structure_issues)}")
    
    ci_issues = [s for s, data in report["ci_validation"]["services_with_ci"] 
                if not data] if isinstance(report["ci_validation"].get("services_with_ci"), dict) else []
    
    global_cleanup_issues = [d for d, clean in report["global_cleanup"].items() if not clean]
    if global_cleanup_issues:
        next_steps.append(f"🧹 Complete migration of global directories: {', '.join(global_cleanup_issues)}")
    
    if report["overall_score"] < 90:
        next_steps.append("📈 Focus on bringing overall validation score above 90%")
    
    if not next_steps:
        next_steps.append("🎉 All validation checks passed! Ready for production.")
    
    return next_steps

def main():
    """Main validation function."""
    print(f"{Colors.BOLD}{Colors.BLUE}🔍 MICROSERVICES MONOREPO FINAL VALIDATION{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}")
    
    # Get all services
    services = get_all_services()
    
    if not services:
        print_status("FAIL", "No services found in apps/ directory")
        sys.exit(1)
    
    # Run comprehensive validation
    report = generate_checklist_report(services)
    
    # Generate next steps
    next_steps = generate_next_steps(report)
    report["next_steps"] = next_steps
    
    # Print final summary
    print_section("📊 FINAL VALIDATION SUMMARY")
    
    print(f"\n🎯 **Overall Score:** {report['overall_score']:.1f}%")
    
    score_color = Colors.GREEN if report['overall_score'] >= 90 else Colors.YELLOW if report['overall_score'] >= 70 else Colors.RED
    score_status = "EXCELLENT" if report['overall_score'] >= 90 else "GOOD" if report['overall_score'] >= 70 else "NEEDS_WORK"
    
    print(f"🏆 **Status:** {score_color}{score_status}{Colors.RESET}")
    
    print(f"\n📈 **Validation Breakdown:**")
    print(f"   • Services Validated: {report['services_count']}")
    print(f"   • Structure Issues: {len([s for s, d in report['structure_validation'].items() if d['percentage'] < 100])}")
    print(f"   • CI/CD Issues: {len(report['failed_items']) - len([i for i in report['failed_items'] if 'Missing' in i])}")
    print(f"   • Global Cleanup Issues: {len([d for d, clean in report['global_cleanup'].items() if not clean])}")
    
    if report["failed_items"]:
        print(f"\n❌ **Failed Items ({len(report['failed_items'])}):**")
        for item in report["failed_items"][:10]:  # Show first 10
            print(f"   • {item}")
        if len(report["failed_items"]) > 10:
            print(f"   • ... and {len(report['failed_items']) - 10} more")
    
    print(f"\n🎯 **Next Steps:**")
    for step in next_steps:
        print(f"   {step}")
    
    # Save detailed report
    with open("VALIDATION_REPORT.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 **Detailed report saved to:** VALIDATION_REPORT.json")
    
    # Exit with appropriate code
    exit_code = 0 if report['overall_score'] >= 70 else 1
    
    if exit_code == 0:
        print(f"\n{Colors.GREEN}✅ VALIDATION PASSED{Colors.RESET}")
    else:
        print(f"\n{Colors.RED}❌ VALIDATION FAILED - See next steps above{Colors.RESET}")
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
