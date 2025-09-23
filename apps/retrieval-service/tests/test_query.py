import anyio
from httpx import AsyncClient
from apps.retrieval-service.src.main import app  # type: ignore


@anyio.run
async def test_query_minimal():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        payload = {"tenant_id": "t1", "query": "hello"}
        r = await ac.post("/v1/query", json=payload)
        assert r.status_code == 200
        j = r.json()
        assert "results" in j

