"""Security middleware for FastAPI."""

import time
from typing import Dict, Any, Optional
from fastapi import Request, Response, HTTPException
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
import structlog

from .auth import get_current_user
from .validation import validate_tenant_id
from .threat_detection import ThreatDetector

logger = structlog.get_logger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Base security middleware."""

    def __init__(self, app):
        super().__init__(app)
        self.threat_detector = ThreatDetector()

    async def dispatch(self, request: Request, call_next):
        """Process request through security middleware."""
        start_time = time.time()

        try:
            # Extract tenant ID from request
            tenant_id = self._extract_tenant_id(request)
            if tenant_id:
                request.state.tenant_id = tenant_id

            # Process request
            response = await call_next(request)

            # Add security headers
            self._add_security_headers(response)

            # Log request
            duration = time.time() - start_time
            logger.info(
                "Request processed",
                method=request.method,
                url=str(request.url),
                status_code=response.status_code,
                duration=duration,
            )

            return response

        except Exception as e:
            logger.error("Security middleware error", error=str(e))
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )

    def _extract_tenant_id(self, request: Request) -> Optional[str]:
        """Extract tenant ID from request."""
        # Try header first
        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id:
            try:
                return validate_tenant_id(tenant_id)
            except ValueError:
                pass

        # Try query parameter
        tenant_id = request.query_params.get("tenant_id")
        if tenant_id:
            try:
                return validate_tenant_id(tenant_id)
            except ValueError:
                pass

        return None

    def _add_security_headers(self, response: Response):
        """Add security headers to response."""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers[
            "Permissions-Policy"
        ] = "geolocation=(), microphone=(), camera=()"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, list] = {}

    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting."""
        client_ip = request.client.host
        now = time.time()

        # Clean old requests
        if client_ip in self.requests:
            self.requests[client_ip] = [
                req_time for req_time in self.requests[client_ip] if now - req_time < 60
            ]
        else:
            self.requests[client_ip] = []

        # Check rate limit
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            logger.warning("Rate limit exceeded", client_ip=client_ip)
            return JSONResponse(
                status_code=429, content={"detail": "Rate limit exceeded"}
            )

        # Record request
        self.requests[client_ip].append(now)

        return await call_next(request)


class CORSMiddleware(BaseHTTPMiddleware):
    """CORS middleware with security controls."""

    def __init__(self, app, allowed_origins: list = None):
        super().__init__(app)
        self.allowed_origins = allowed_origins or ["*"]

    async def dispatch(self, request: Request, call_next):
        """Handle CORS."""
        origin = request.headers.get("origin")

        if (
            origin
            and origin not in self.allowed_origins
            and "*" not in self.allowed_origins
        ):
            return JSONResponse(
                status_code=403, content={"detail": "Origin not allowed"}
            )

        response = await call_next(request)

        # Add CORS headers
        if origin in self.allowed_origins or "*" in self.allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin or "*"
            response.headers[
                "Access-Control-Allow-Methods"
            ] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers[
                "Access-Control-Allow-Headers"
            ] = "Content-Type, Authorization, X-Tenant-ID"
            response.headers["Access-Control-Max-Age"] = "86400"

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Security headers middleware."""

    async def dispatch(self, request: Request, call_next):
        """Add security headers."""
        response = await call_next(request)

        # Security headers
        response.headers[
            "Strict-Transport-Security"
        ] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        return response


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """Tenant isolation middleware."""

    async def dispatch(self, request: Request, call_next):
        """Enforce tenant isolation."""
        # Extract tenant ID
        tenant_id = getattr(request.state, "tenant_id", None)

        if not tenant_id:
            # Try to get from authenticated user
            try:
                user = await get_current_user(request)
                tenant_id = user.get("tenant_id")
            except HTTPException:
                pass

        if tenant_id:
            # Set tenant context for database queries
            request.state.tenant_id = tenant_id

        return await call_next(request)
