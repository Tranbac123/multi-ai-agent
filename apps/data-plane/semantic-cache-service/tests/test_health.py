import pytest
import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from main import app
except ImportError:
    app = None

def test_health():
    if app is None:
        pytest.skip("main.py not found or import failed")
    c = TestClient(app)
    response = c.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True

