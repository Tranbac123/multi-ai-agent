import pytest
from pathlib import Path

@pytest.mark.p0
def test_service_structure():
    """Test that the service has the required structure"""
    service_dir = Path(__file__).parent.parent
    
    # Check required files exist
    required_files = [
        "src/main.py",
        "requirements.txt", 
        "Dockerfile",
        "contracts/openapi.yaml"
    ]
    
    for file_path in required_files:
        full_path = service_dir / file_path
        assert full_path.exists(), f"Required file missing: {file_path}"

@pytest.mark.p0  
def test_main_py_has_app():
    """Test that main.py defines an app variable"""
    service_dir = Path(__file__).parent.parent
    main_py = service_dir / "src" / "main.py"
    
    if not main_py.exists():
        pytest.skip("main.py not found")
        
    content = main_py.read_text()
    assert "app = FastAPI" in content, "main.py should define app = FastAPI"
    assert "FastAPI" in content, "main.py should import FastAPI"
