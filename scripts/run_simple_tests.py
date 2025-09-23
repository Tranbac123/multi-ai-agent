#!/usr/bin/env python3
"""
Simple test runner that validates service structure and runs basic tests
"""
import os
import sys
import subprocess
from pathlib import Path

def find_services_with_source():
    """Find services that have src/main.py files"""
    services = []
    apps_dir = Path("apps")
    
    for plane_dir in apps_dir.iterdir():
        if not plane_dir.is_dir():
            continue
            
        for service_dir in plane_dir.iterdir():
            if not service_dir.is_dir():
                continue
                
            main_py = service_dir / "src" / "main.py"
            if main_py.exists():
                services.append(service_dir)
                
    return services

def test_service_structure(service_dir):
    """Test that a service has the required structure"""
    required_files = [
        "src/main.py",
        "requirements.txt", 
        "Dockerfile"
    ]
    
    missing_files = []
    for file_path in required_files:
        full_path = service_dir / file_path
        if not full_path.exists():
            missing_files.append(file_path)
    
    # Debug: print what files actually exist
    print(f"  📁 Checking {service_dir}:")
    for file_path in required_files:
        full_path = service_dir / file_path
        status = "✅" if full_path.exists() else "❌"
        print(f"    {status} {file_path}")
    
    return missing_files

def run_tests_for_service(service_dir):
    """Run tests for a specific service"""
    print(f"\n🧪 Testing {service_dir.name}...")
    
    # Check structure
    missing_files = test_service_structure(service_dir)
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    
    # Try to run tests
    try:
        os.chdir(service_dir)
        result = subprocess.run(
            ["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print(f"✅ {service_dir.name} tests passed")
            return True
        else:
            print(f"⚠️  {service_dir.name} tests had issues:")
            print(result.stdout)
            if result.stderr:
                print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {service_dir.name} tests timed out")
        return False
    except Exception as e:
        print(f"❌ {service_dir.name} test error: {e}")
        return False
    finally:
        os.chdir(Path.cwd().parent.parent)  # Back to repo root

def main():
    """Main test runner"""
    print("🚀 Running Simple Test Suite")
    print("=" * 50)
    
    # Find services with source code
    services = find_services_with_source()
    print(f"Found {len(services)} services with source code:")
    for service in services:
        print(f"  - {service}")
    
    # Test each service
    passed = 0
    failed = 0
    
    for service in services:
        if run_tests_for_service(service):
            passed += 1
        else:
            failed += 1
    
    # Summary
    print("\n" + "=" * 50)
    print(f"📊 Test Summary:")
    print(f"  ✅ Passed: {passed}")
    print(f"  ❌ Failed: {failed}")
    print(f"  📈 Total:  {len(services)}")
    
    if failed == 0:
        print("\n🎉 All services passed!")
        return 0
    else:
        print(f"\n⚠️  {failed} services had issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())
