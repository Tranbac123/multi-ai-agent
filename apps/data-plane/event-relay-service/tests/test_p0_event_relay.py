import pytest, importlib.util, base64
from pathlib import Path
from fastapi.testclient import TestClient
from apps.tests_shared_loader import load_module_and_app

@pytest.mark.p0
def test_healthz():
    _, app = load_module_and_app(Path(__file__).resolve().parents[1])
    assert TestClient(app).get("/healthz").status_code == 200

@pytest.mark.p0
def test_hmac_signer_or_skip():
    svc = Path(__file__).resolve().parents[1]
    crypto_py = svc / "src" / "crypto.py"
    if not crypto_py.exists():
        pytest.skip("crypto.py signer not present")
    spec = importlib.util.spec_from_file_location("crypto_mod", crypto_py)
    mod = importlib.util.module_from_spec(spec)  # type: ignore
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore
    assert hasattr(mod, "sign"), "sign(k: str, payload: bytes) -> 'sha256=...' expected"
    sig = mod.sign("secret", b"payload")
    assert isinstance(sig, str) and sig.startswith("sha256=")
    base64.b64decode(sig.split("=",1)[1])