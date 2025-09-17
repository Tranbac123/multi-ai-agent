"""Authentication client for multi-tenant system."""

import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID
import structlog

# from libs.contracts.tenant import Tenant, User, APIKey
from libs.contracts.error import ErrorSpec, ErrorCode
from libs.utils.exceptions import AuthenticationError, AuthorizationError

logger = structlog.get_logger(__name__)


class AuthClient:
    """Authentication client for JWT and API key validation."""

    def __init__(self, secret_key: str = "your-secret-key"):
        self.secret_key = secret_key
        self.algorithm = "HS256"

    def create_jwt_token(
        self, tenant_id: UUID, user_id: UUID, expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT token for user."""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=24)

        payload = {
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access",
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_jwt_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT token and return payload."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise AuthenticationError(
                ErrorSpec(
                    code=ErrorCode.AUTHENTICATION_FAILED,
                    message="Token has expired",
                    retriable=False,
                )
            )
        except jwt.InvalidTokenError:
            raise AuthenticationError(
                ErrorSpec(
                    code=ErrorCode.AUTHENTICATION_FAILED,
                    message="Invalid token",
                    retriable=False,
                )
            )

    def verify_api_key(self, api_key: str) -> Dict[str, Any]:
        """Verify API key and return tenant info."""
        # In production, this would query the database
        # For now, return mock data
        return {
            "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
            "scopes": ["read", "write"],
            "rate_limit": 1000,
        }

    def check_permissions(
        self, tenant_id: UUID, user_id: UUID, resource: str, action: str
    ) -> bool:
        """Check if user has permission for resource action."""
        # In production, this would check against a permissions table
        return True


async def get_current_tenant(request) -> Optional[UUID]:
    """Get current tenant from request context."""
    # Check for JWT token in Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        auth_client = AuthClient()
        try:
            payload = auth_client.verify_jwt_token(token)
            return UUID(payload["tenant_id"])
        except AuthenticationError:
            return None

    # Check for API key in X-API-Key header
    api_key = request.headers.get("X-API-Key")
    if api_key:
        auth_client = AuthClient()
        try:
            payload = auth_client.verify_api_key(api_key)
            return UUID(payload["tenant_id"])
        except AuthenticationError:
            return None

    return None
