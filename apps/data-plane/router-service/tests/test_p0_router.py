import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from apps.tests_shared_loader import load_module_and_app

@pytest.mark.p0
def test_healthz():
    _, app = load_module_and_app(Path(__file__).resolve().parents[1])
    assert TestClient(app).get("/healthz").status_code == 200

@pytest.mark.p0
def test_route_default_or_skip():
    _, app = load_module_and_app(Path(__file__).resolve().parents[1])
    c = TestClient(app)
    r = c.post("/v1/route", json={"task":"chat","tenant_id":"t1"})
    if r.status_code == 404:
        pytest.skip("/v1/route not implemented yet")
    assert r.status_code == 200
    jr = r.json()
    assert isinstance(jr, dict)
    # If model/rule present, expect a model key
    if "model" in jr:
        assert isinstance(jr["model"], str) and jr["model"]
