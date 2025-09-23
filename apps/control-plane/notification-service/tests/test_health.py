import pytest
import anyio
from httpx import AsyncClient
from apps.control-plane.notification_service.src.main import app

@anyio.run
async def test_health():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["service"] == "notification-service"

