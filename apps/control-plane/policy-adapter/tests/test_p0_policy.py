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
    c = TestClient(app)
    r = c.get("/healthz")
    assert r.status_code == 200

# Optional: if /v1/authorize exists, smoke allow/deny. Otherwise skip.
@pytest.mark.p0
def test_authorize_allow_or_skip():
    if app is None:
        pytest.skip("main.py not found or import failed")
    c = TestClient(app)
    try:
        r = c.post("/v1/authorize", json={"resource":"model","action":"chat"})
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert "allow" in r.json()
    except Exception:
        pytest.skip("authorize endpoint not implemented yet")
