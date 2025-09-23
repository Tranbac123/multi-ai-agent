import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from apps.tests_shared_loader import load_module_and_app

@pytest.mark.p0
def test_healthz():
    _, app = load_module_and_app(Path(__file__).resolve().parents[1])
    assert TestClient(app).get("/healthz").status_code == 200

@pytest.mark.p0
def test_put_get_del_roundtrip():
    _, app = load_module_and_app(Path(__file__).resolve().parents[1])
    c = TestClient(app)
    k = "k1"
    assert c.post("/v1/cache/put", json={"key":k,"value":"hello","ttl_s":60}).status_code in (200,201)
    r = c.get("/v1/cache/get", params={"key":k})
    assert r.status_code == 200 and r.json().get("hit") is True and r.json().get("value") == "hello"
    assert c.delete("/v1/cache/del", params={"key":k}).status_code in (200,204)
    r2 = c.get("/v1/cache/get", params={"key":k})
    assert r2.status_code == 200 and r2.json().get("hit") is False
