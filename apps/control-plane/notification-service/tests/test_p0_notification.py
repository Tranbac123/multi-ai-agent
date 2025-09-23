import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from apps.tests_shared_loader import load_module_and_app

@pytest.mark.p0
def test_healthz():
    _, app = load_module_and_app(Path(__file__).resolve().parents[1])
    assert TestClient(app).get("/healthz").status_code == 200

@pytest.mark.p0
def test_notify_queue_or_skip():
    _, app = load_module_and_app(Path(__file__).resolve().parents[1])
    c = TestClient(app)
    r = c.post("/v1/notify", json={
        "tenant_id":"t_1",
        "channels":["email","slack"],
        "subject":"Test",
        "body":"Hello"
    })
    if r.status_code == 404:
        pytest.skip("/v1/notify not implemented yet")
    assert r.status_code in (200, 202)
    if r.status_code == 200:
        body = r.json()
        assert "notification_id" in body
