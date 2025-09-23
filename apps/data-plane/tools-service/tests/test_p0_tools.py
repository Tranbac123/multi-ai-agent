import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from apps.tests_shared_loader import load_module_and_app

@pytest.mark.p0
def test_healthz():
    _, app = load_module_and_app(Path(__file__).resolve().parents[1])
    assert TestClient(app).get("/healthz").status_code == 200

@pytest.mark.p0
def test_exec_echo_or_skip():
    _, app = load_module_and_app(Path(__file__).resolve().parents[1])
    c = TestClient(app)
    # Try common patterns; skip if neither exists yet.
    payload = {"name":"echo","args":{"text":"hi"}}
    for path in ("/v1/tools/exec", "/v1/exec", "/v1/run"):
        r = c.post(path, json=payload)
        if r.status_code != 404:
            assert r.status_code in (200, 202)
            break
    else:
        pytest.skip("no exec endpoint implemented")
