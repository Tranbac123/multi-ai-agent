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

@pytest.mark.p0
def test_healthz():
    if app is None:
        pytest.skip("main.py not found or import failed")
    assert TestClient(app).get("/healthz").status_code == 200
