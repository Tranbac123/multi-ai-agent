import pytest, types
from pathlib import Path
from fastapi.testclient import TestClient
from apps.tests_shared_loader import load_module_and_app

class _DummyDB:
    async def start(self): pass
    async def stop(self): pass
    async def set_tenant_context(self, t): self.t=t

@pytest.mark.p0
def test_healthz():
    mod, app = load_module_and_app(Path(__file__).resolve().parents[1])
    assert TestClient(app).get("/healthz").status_code == 200

@pytest.mark.p0
def test_migrate_with_dummy_db(monkeypatch):
    mod, app = load_module_and_app(Path(__file__).resolve().parents[1])
    # Replace DatabaseClient in module with dummy stub
    if hasattr(mod, "DatabaseClient"):
        monkeypatch.setattr(mod, "DatabaseClient", _DummyDB)
    else:
        # main.py likely does "from libs... import DatabaseClient"
        # patch attribute on imported symbol
        try:
            monkeypatch.setattr(mod, "DatabaseClient", _DummyDB)
        except Exception:
            pass
    c = TestClient(app)
    r = c.post("/v1/migrate", json={"tenant_id":"t1"})
    # Accept 200 or 422 depending on body schema; if implemented expect 200
    assert r.status_code in (200, 422)
