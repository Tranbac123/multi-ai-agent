#!/usr/bin/env python3
"""
Simple test script to verify quality analysis tools work correctly.
"""

import json
import subprocess
import sys
from pathlib import Path


def test_jscpd_config():
    """Test that jscpd configuration is valid."""
    print("Testing jscpd configuration...")
    
    config_file = Path(".jscpd.json")
    if not config_file.exists():
        print("❌ .jscpd.json not found")
        return False
    
    with open(config_file) as f:
        config = json.load(f)
    
    required_fields = ["threshold", "reporters", "output"]
    for field in required_fields:
        if field not in config:
            print(f"❌ Missing field: {field}")
            return False
    
    print(f"✅ jscpd config valid - threshold: {config['threshold']}")
    return True


def test_ruff_config():
    """Test that ruff configuration includes required rules."""
    print("Testing ruff configuration...")
    
    config_file = Path(".ruff.toml")
    if not config_file.exists():
        print("❌ .ruff.toml not found")
        return False
    
    with open(config_file) as f:
        config_content = f.read()
    
    required_rules = ["F401", "F841", "ERA", "SIM", "PLR", "TRY", "UP", "PERF"]
    missing_rules = []
    
    for rule in required_rules:
        if rule not in config_content:
            missing_rules.append(rule)
    
    if missing_rules:
        print(f"❌ Missing rules: {missing_rules}")
        return False
    
    print("✅ ruff config includes all required rules")
    return True


def test_mypy_config():
    """Test that mypy configuration is in strict mode."""
    print("Testing mypy configuration...")
    
    config_file = Path("mypy.ini")
    if not config_file.exists():
        print("❌ mypy.ini not found")
        return False
    
    with open(config_file) as f:
        config_content = f.read()
    
    if "strict = True" not in config_content:
        print("❌ mypy not in strict mode")
        return False
    
    print("✅ mypy config is in strict mode")
    return True


def test_eslint_config():
    """Test that ESLint configuration includes required rules."""
    print("Testing ESLint configuration...")
    
    config_file = Path("web/.eslintrc.cjs")
    if not config_file.exists():
        print("❌ web/.eslintrc.cjs not found")
        return False
    
    with open(config_file) as f:
        config_content = f.read()
    
    required_rules = ["no-duplicate-imports", "import/no-duplicates", "import/order", "no-unused-vars"]
    missing_rules = []
    
    for rule in required_rules:
        if rule not in config_content:
            missing_rules.append(rule)
    
    if missing_rules:
        print(f"❌ Missing ESLint rules: {missing_rules}")
        return False
    
    print("✅ ESLint config includes all required rules")
    return True


def test_package_json():
    """Test that package.json includes dead code detection scripts."""
    print("Testing package.json scripts...")
    
    package_file = Path("web/package.json")
    if not package_file.exists():
        print("❌ web/package.json not found")
        return False
    
    with open(package_file) as f:
        package_data = json.load(f)
    
    scripts = package_data.get("scripts", {})
    required_scripts = ["ts-unused-exports", "ts-unused-exports-report", "dead-code"]
    missing_scripts = []
    
    for script in required_scripts:
        if script not in scripts:
            missing_scripts.append(script)
    
    if missing_scripts:
        print(f"❌ Missing scripts: {missing_scripts}")
        return False
    
    # Check ts-prune dependency
    dev_deps = package_data.get("devDependencies", {})
    if "ts-prune" not in dev_deps:
        print("❌ ts-prune not in devDependencies")
        return False
    
    print("✅ package.json includes all required scripts and dependencies")
    return True


def test_makefile_targets():
    """Test that Makefile includes quality analysis targets."""
    print("Testing Makefile targets...")
    
    makefile = Path("Makefile")
    if not makefile.exists():
        print("❌ Makefile not found")
        return False
    
    with open(makefile) as f:
        makefile_content = f.read()
    
    required_targets = ["dup:", "dead:", "comp:", "qa:", "qa-comprehensive:"]
    missing_targets = []
    
    for target in required_targets:
        if target not in makefile_content:
            missing_targets.append(target)
    
    if missing_targets:
        print(f"❌ Missing Makefile targets: {missing_targets}")
        return False
    
    print("✅ Makefile includes all required targets")
    return True


def test_tools_installation():
    """Test that required tools are installed."""
    print("Testing tool installation...")
    
    tools = [
        ("jscpd", ["jscpd", "--version"]),
        ("vulture", ["vulture", "--version"]),
        ("radon", ["radon", "--version"]),
        ("ruff", ["ruff", "--version"]),
        ("mypy", ["mypy", "--version"]),
    ]
    
    for tool_name, cmd in tools:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"✅ {tool_name} installed")
            else:
                print(f"❌ {tool_name} not working: {result.stderr}")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print(f"❌ {tool_name} not found")
            return False
    
    return True


def test_reports_directory():
    """Test that reports directory structure exists."""
    print("Testing reports directory...")
    
    reports_dir = Path("reports")
    if not reports_dir.exists():
        print("❌ reports directory not found")
        return False
    
    required_subdirs = ["duplication", "dead-code", "complexity"]
    missing_subdirs = []
    
    for subdir in required_subdirs:
        subdir_path = reports_dir / subdir
        if not subdir_path.exists():
            missing_subdirs.append(subdir)
    
    if missing_subdirs:
        print(f"❌ Missing report subdirectories: {missing_subdirs}")
        return False
    
    print("✅ reports directory structure exists")
    return True


def test_quality_analysis_script():
    """Test that quality analysis script runs."""
    print("Testing quality analysis script...")
    
    script_file = Path("scripts/quality_analysis_report.py")
    if not script_file.exists():
        print("❌ quality_analysis_report.py not found")
        return False
    
    try:
        result = subprocess.run(
            ["python3", str(script_file), "--help"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            print("✅ quality_analysis_report.py script runs")
            return True
        else:
            print(f"❌ quality_analysis_report.py failed: {result.stderr}")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("❌ quality_analysis_report.py not executable")
        return False


def main():
    """Run all tests."""
    print("🔍 Testing Quality Analysis Tools (COMMIT 1 - Baseline & Detectors)")
    print("=" * 70)
    
    tests = [
        test_jscpd_config,
        test_ruff_config,
        test_mypy_config,
        test_eslint_config,
        test_package_json,
        test_makefile_targets,
        test_tools_installation,
        test_reports_directory,
        test_quality_analysis_script,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            print()
    
    print("=" * 70)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All quality analysis tools are properly configured!")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
