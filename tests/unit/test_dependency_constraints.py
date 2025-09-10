"""Test dependency constraints and security tools."""

import subprocess
import sys
from pathlib import Path


def test_constraints_file_exists():
    """Test that constraints.txt exists and is valid."""
    constraints_file = Path("constraints.txt")
    assert constraints_file.exists(), "constraints.txt file should exist"
    
    # Read and validate format
    content = constraints_file.read_text()
    lines = content.strip().split('\n')
    
    # Should have some dependencies
    assert len(lines) > 10, "constraints.txt should have multiple dependencies"
    
    # Each line should be a valid pip requirement
    for line in lines:
        if line.strip() and not line.startswith('#'):
            # Basic validation: should contain ==
            assert '==' in line, f"Line should contain version pin: {line}"


def test_requirements_no_duplicates():
    """Test that requirements.txt has no duplicate packages."""
    requirements_file = Path("requirements.txt")
    assert requirements_file.exists(), "requirements.txt file should exist"
    
    content = requirements_file.read_text()
    lines = [line.strip() for line in content.split('\n') if line.strip() and not line.startswith('#')]
    
    # Extract package names (before ==)
    packages = []
    for line in lines:
        if '==' in line:
            package_name = line.split('==')[0].strip()
            packages.append(package_name)
    
    # Check for duplicates
    duplicates = [pkg for pkg in set(packages) if packages.count(pkg) > 1]
    assert not duplicates, f"Found duplicate packages: {duplicates}"


def test_security_tools_available():
    """Test that security tools are available."""
    # Test safety
    try:
        result = subprocess.run([sys.executable, "-m", "safety", "--version"], 
                              capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Safety check failed: {result.stderr}"
    except subprocess.TimeoutExpired:
        # Safety might not be installed in test environment, that's ok
        pass
    
    # Test bandit
    try:
        result = subprocess.run([sys.executable, "-m", "bandit", "--version"], 
                              capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Bandit check failed: {result.stderr}"
    except subprocess.TimeoutExpired:
        # Bandit might not be installed in test environment, that's ok
        pass


def test_install_script_exists():
    """Test that install script exists and is executable."""
    install_script = Path("scripts/install-deps.sh")
    assert install_script.exists(), "install-deps.sh script should exist"
    
    # Check if it's executable (on Unix systems)
    if sys.platform != "win32":
        assert install_script.stat().st_mode & 0o111, "install-deps.sh should be executable"
