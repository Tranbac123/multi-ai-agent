import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from apps.tests_shared_loader import load_module_and_app

@pytest.mark.p0
def test_healthz():
    _, app = load_module_and_app(Path(__file__).resolve().parents[1])
    assert TestClient(app).get("/healthz").status_code == 200

@pytest.mark.p0
def test_list_adapters_or_skip():
    _, app = load_module_and_app(Path(__file__).resolve().parents[1])
    c = TestClient(app)
    r = c.get("/v1/adapters")
    if r.status_code == 404:
        pytest.skip("/v1/adapters not implemented yet")
    assert r.status_code == 200
    assert isinstance(r.json(), (list, dict))
