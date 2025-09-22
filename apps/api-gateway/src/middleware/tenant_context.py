"""Tenant context middleware for API Gateway."""

import uuid
from typing import Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import jwt
import time

from libs.contracts.error import ErrorResponse, ServiceError


class TenantContextMiddleware:
    """Middleware for setting tenant context in database connections."""

    def __init__(self, jwt_secret: str):
        self.jwt_secret = jwt_secret

    async def set_tenant_context(self, request: Request, call_next):
        """Set tenant context for the request."""
        try:
            # Extract tenant_id from JWT token
            tenant_id = await self._extract_tenant_id(request)

            if tenant_id:
                # Set tenant_id in request state
                request.state.tenant_id = tenant_id
                request.state.request_id = str(uuid.uuid4())

                # Set tenant context in database connection
                await self._set_db_tenant_context(tenant_id)

            response = await call_next(request)

            # Reset tenant context after request
            await self._reset_db_tenant_context()

            return response

        except Exception as e:
            error_id = str(uuid.uuid4())
            error = ServiceError(
                error_id=error_id,
                error_type="authentication_error",
                error_code="TENANT_CONTEXT_ERROR",
                message=f"Failed to set tenant context: {str(e)}",
                timestamp=time.time(),
                service="api-gateway",
            )

            return JSONResponse(
                status_code=401,
                content=ErrorResponse(success=False, error=error).dict(),
            )

    async def _extract_tenant_id(self, request: Request) -> Optional[str]:
        """Extract tenant_id from JWT token or API key."""
        # Try JWT token first
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
                return payload.get("tenant_id")
            except jwt.InvalidTokenError:
                pass

        # Try API key
        api_key = request.headers.get("X-API-Key")
        if api_key:
            # Look up tenant_id from API key hash
            tenant_id = await self._lookup_tenant_from_api_key(api_key)
            if tenant_id:
                return tenant_id

        return None

    async def _lookup_tenant_from_api_key(self, api_key: str) -> Optional[str]:
        """Look up tenant_id from API key hash."""
        # This would typically query the database
        # For now, return None to indicate no tenant found
        return None

    async def _set_db_tenant_context(self, tenant_id: str):
        """Set tenant context in database connection."""
        # This would typically set the tenant_id in the database session
        # For PostgreSQL RLS, this would be:
        # await db.execute("SET app.tenant_id = :tenant_id", {"tenant_id": tenant_id})
        pass

    async def _reset_db_tenant_context(self):
        """Reset tenant context in database connection."""
        # This would typically reset the tenant_id in the database session
        # For PostgreSQL RLS, this would be:
        # await db.execute("RESET app.tenant_id")
        pass


def create_tenant_context_middleware(jwt_secret: str) -> TenantContextMiddleware:
    """Create tenant context middleware instance."""
    return TenantContextMiddleware(jwt_secret)
