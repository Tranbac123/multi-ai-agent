# Minimal in-memory config store with env scoping.
from typing import Dict, Any

_store: Dict[str, Dict[str, Any]] = {"production": {}, "staging": {}, "dev": {}}

def get(env: str, key: str) -> Any | None:
    return _store.get(env, {}).get(key)

def set(env: str, key: str, value: Any):
    _store.setdefault(env, {})[key] = value
    return True

def list_env(env: str) -> Dict[str, Any]:
    return _store.get(env, {})

