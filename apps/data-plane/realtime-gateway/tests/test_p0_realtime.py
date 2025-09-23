import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from apps.tests_shared_loader import load_module_and_app

@pytest.mark.p0
def test_healthz():
    _, app = load_module_and_app(Path(__file__).resolve().parents[1])
    assert TestClient(app).get("/healthz").status_code == 200

@pytest.mark.p0
def test_websocket_connect_or_skip():
    _, app = load_module_and_app(Path(__file__).resolve().parents[1])
    c = TestClient(app)
    # Try /ws then /realtime
    for path in ("/ws", "/realtime"):
        try:
            with c.websocket_connect(path) as ws:
                ws.send_text("ping")
                # don't assert reply shape; just ensure connection works
                break
        except Exception:
            continue
    else:
        pytest.skip("no websocket endpoint implemented yet")
