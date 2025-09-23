import anyio
from httpx import AsyncClient
from apps.retrieval-service.src.main import app  # type: ignore


@anyio.run
async def test_health():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get("/healthz")
        assert r.status_code == 200
        assert r.json()["ok"] is True

