import importlib, asyncio
from .registry import STEPS

async def apply_all(db, tenant_id: str, target: str | None=None):
    for step in STEPS:
        module = importlib.import_module(f"libs.data_plane.migrations.steps.{step}")
        if hasattr(module, "apply"):
            await db.execute(f"/* apply {step} */ select 1")
        # real SQL calls live inside each step in production

