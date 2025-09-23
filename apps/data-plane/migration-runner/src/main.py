from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from libs.data_plane.storages.database import DatabaseClient
from libs.data_plane.migrations.engine import apply_all
from .settings import settings

app = FastAPI(title="migration-runner", version="0.1.0")

@app.get("/healthz") 
def healthz(): 
    return {"ok": True, "name": settings.app_name}

class MigrateIn(BaseModel):
    tenant_id: str
    target_version: str | None = None

@app.post("/v1/migrate")
async def migrate(body: MigrateIn):
    db = DatabaseClient()
    await db.start()
    try:
        await db.set_tenant_context(body.tenant_id)
        await apply_all(db, body.tenant_id, body.target_version)
        return {"ok": True, "tenant_id": body.tenant_id}
    finally:
        await db.stop()

