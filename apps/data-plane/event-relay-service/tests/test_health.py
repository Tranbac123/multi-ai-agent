from fastapi.testclient import TestClient
from apps.data-plane.event-relay-service.src.main import app  # type: ignore

def test_health(): 
    c = TestClient(app)
    assert c.get("/healthz").status_code == 200

