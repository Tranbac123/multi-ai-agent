from __future__ import annotations
import asyncpg, os, contextvars
from typing import Any, Optional, Sequence

_tenant = contextvars.ContextVar("tenant_id", default=None)

class DatabaseClient:
    def __init__(self):
        self.write_dsn = os.getenv("DP_WRITE_DSN","postgresql://postgres:postgres@db-write/postgres")
        self.read_dsn  = os.getenv("DP_READ_DSN", self.write_dsn)
        self.min_size  = int(os.getenv("DP_POOL_MIN","2"))
        self.max_size  = int(os.getenv("DP_POOL_MAX","10"))
        self._write_pool = None
        self._read_pool  = None

    async def start(self):
        self._write_pool = await asyncpg.create_pool(self.write_dsn, min_size=self.min_size, max_size=self.max_size)
        self._read_pool  = await asyncpg.create_pool(self.read_dsn,  min_size=self.min_size, max_size=self.max_size)

    async def stop(self):
        if self._write_pool: await self._write_pool.close()
        if self._read_pool:  await self._read_pool.close()

    async def set_tenant_context(self, tenant_id: str):
        _tenant.set(tenant_id)

    async def _apply_rls(self, conn):
        t = _tenant.get()
        if t:
            # set GUC for RLS policies like: current_setting('app.tenant_id')
            await conn.execute("select set_config('app.tenant_id',$1,true)", t)

    async def query(self, sql: str, *args, read_only: bool=True):
        pool = self._read_pool if read_only else self._write_pool
        async with pool.acquire() as conn:
            await self._apply_rls(conn)
            rows = await conn.fetch(sql, *args)
            return [dict(r) for r in rows]

    async def execute(self, sql: str, *args):
        async with self._write_pool.acquire() as conn:
            await self._apply_rls(conn)
            return await conn.execute(sql, *args)

