from typing import Optional
from fastapi import Header, HTTPException

def enforce(tenant: Optional[str] = Header(None, alias="X-Tenant-Id")):
    if not tenant:
        raise HTTPException(400, "missing tenant")
    return tenant
