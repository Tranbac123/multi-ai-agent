from __future__ import annotations
from pathlib import Path
import importlib.util, types
import pytest

def load_module_and_app(service_dir: Path):
    """Dynamically import src/main.py inside a service folder with hyphens.
    Returns (module, app). If main.py or app missing → pytest.skip."""
    main_py = service_dir / "src" / "main.py"
    if not main_py.exists():
        pytest.skip(f"main.py not found in {service_dir}")
    spec = importlib.util.spec_from_file_location("svc_main", main_py)
    mod = importlib.util.module_from_spec(spec)  # type: ignore
    assert spec and spec.loader, "invalid import spec"
    spec.loader.exec_module(mod)  # type: ignore
    if not hasattr(mod, "app"):
        pytest.skip(f"'app' not found in {main_py}")
    return mod, mod.app
