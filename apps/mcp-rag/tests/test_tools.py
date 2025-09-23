from apps.mcp-rag.src.server import rag_query  # type: ignore


def test_schema_load_and_stub_call(monkeypatch):
    class R:
        def json(self): return {"results": []}
    def fake_post(*a, **k): return R()
    import apps.mcp-rag.src.server as s  # type: ignore
    monkeypatch.setattr(s.httpx, "post", fake_post)
    out = rag_query({"tenant_id": "t1", "query": "hello"})
    assert "results" in out

