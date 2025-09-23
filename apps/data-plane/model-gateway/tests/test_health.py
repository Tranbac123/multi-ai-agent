import pytest
import anyio
from httpx import AsyncClient
from apps.data-plane.model-gateway.src.main import app

@anyio.run
async def test_health():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["service"] == "model-gateway"

@anyio.run
async def test_detailed_health():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "providers" in data
        assert "circuit_breakers" in data

