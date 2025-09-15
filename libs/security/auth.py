"""Authentication and authorization management."""

import asyncio
import hashlib
import hmac
import jwt
import secrets
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from uuid import UUID
import structlog
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from passlib.hash import bcrypt

from libs.clients.database import get_db_session
from libs.contracts.database import UserProfile, UserRole

logger = structlog.get_logger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
JWT_SECRET_KEY = "your-secret-key-change-in-production"
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30
JWT_REFRESH_TOKEN_EXPIRE_DAYS = 7

# API Key settings
API_KEY_LENGTH = 32
API_KEY_PREFIX = "aiaas_"


class JWTManager:
    """JWT token management."""

    def __init__(
        self, secret_key: str = JWT_SECRET_KEY, algorithm: str = JWT_ALGORITHM
    ):
        self.secret_key = secret_key
        self.algorithm = algorithm

    def create_access_token(
        self,
        user_id: str,
        tenant_id: str,
        roles: List[str],
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """Create JWT access token."""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES
            )

        to_encode = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "roles": roles,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access",
        }

        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(
        self, user_id: str, tenant_id: str, expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT refresh token."""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)

        to_encode = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh",
        }

        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

    def refresh_access_token(self, refresh_token: str) -> str:
        """Refresh access token using refresh token."""
        payload = self.verify_token(refresh_token)

        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")

        # Get user roles from database
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")

        # This would typically fetch from database
        roles = ["user"]  # Default role

        return self.create_access_token(user_id, tenant_id, roles)


class APIKeyManager:
    """API Key management."""

    def __init__(self):
        self.api_keys: Dict[str, Dict[str, Any]] = {}

    def generate_api_key(
        self, user_id: str, tenant_id: str, name: str, permissions: List[str] = None
    ) -> str:
        """Generate new API key."""
        api_key = f"{API_KEY_PREFIX}{secrets.token_urlsafe(API_KEY_LENGTH)}"

        self.api_keys[api_key] = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "name": name,
            "permissions": permissions or ["read"],
            "created_at": time.time(),
            "last_used": None,
            "is_active": True,
        }

        logger.info(
            "API key generated", user_id=user_id, tenant_id=tenant_id, key_name=name
        )

        return api_key

    def validate_api_key(self, api_key: str) -> Dict[str, Any]:
        """Validate API key and return user info."""
        if not api_key.startswith(API_KEY_PREFIX):
            raise HTTPException(status_code=401, detail="Invalid API key format")

        key_info = self.api_keys.get(api_key)
        if not key_info or not key_info.get("is_active"):
            raise HTTPException(status_code=401, detail="Invalid or inactive API key")

        # Update last used timestamp
        key_info["last_used"] = time.time()

        return key_info

    def revoke_api_key(self, api_key: str) -> bool:
        """Revoke API key."""
        if api_key in self.api_keys:
            self.api_keys[api_key]["is_active"] = False
            logger.info("API key revoked", api_key=api_key[:10] + "...")
            return True
        return False

    def list_api_keys(self, user_id: str) -> List[Dict[str, Any]]:
        """List API keys for user."""
        return [
            {**info, "key": key[:10] + "..."}
            for key, info in self.api_keys.items()
            if info["user_id"] == user_id
        ]


class RBACManager:
    """Role-Based Access Control management."""

    def __init__(self):
        self.permissions = {
            UserRole.ADMIN: [
                "users:read",
                "users:write",
                "users:delete",
                "tenants:read",
                "tenants:write",
                "tenants:delete",
                "agents:read",
                "agents:write",
                "agents:delete",
                "tools:read",
                "tools:write",
                "tools:delete",
                "analytics:read",
                "analytics:write",
                "billing:read",
                "billing:write",
                "settings:read",
                "settings:write",
            ],
            UserRole.AGENT: [
                "agents:read",
                "agents:write",
                "tools:read",
                "tools:write",
                "conversations:read",
                "conversations:write",
                "analytics:read",
            ],
            UserRole.VIEWER: ["agents:read", "conversations:read", "analytics:read"],
        }

    def has_permission(self, role: UserRole, permission: str) -> bool:
        """Check if role has permission."""
        return permission in self.permissions.get(role, [])

    def get_permissions(self, role: UserRole) -> List[str]:
        """Get all permissions for role."""
        return self.permissions.get(role, [])

    def require_permission(self, permission: str):
        """Decorator to require specific permission."""

        def decorator(func):
            async def wrapper(*args, **kwargs):
                # This would be implemented with dependency injection
                # in the actual FastAPI route
                return await func(*args, **kwargs)

            return wrapper

        return decorator


class AuthenticationManager:
    """Main authentication manager."""

    def __init__(self):
        self.jwt_manager = JWTManager()
        self.api_key_manager = APIKeyManager()
        self.rbac_manager = RBACManager()
        self.failed_attempts: Dict[str, List[float]] = {}
        self.max_failed_attempts = 5
        self.lockout_duration = 300  # 5 minutes

    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        return pwd_context.verify(plain_password, hashed_password)

    async def authenticate_user(
        self, email: str, password: str, tenant_id: str
    ) -> Optional[Dict[str, Any]]:
        """Authenticate user with email and password."""
        # Check for brute force attempts
        if self._is_locked_out(email):
            raise HTTPException(
                status_code=423,
                detail="Account temporarily locked due to too many failed attempts",
            )

        try:
            # Get user from database
            async with get_db_session() as db:
                user = await db.execute(
                    "SELECT * FROM users WHERE email = :email AND tenant_id = :tenant_id",
                    {"email": email, "tenant_id": tenant_id},
                )
                user_data = user.fetchone()

                if not user_data:
                    self._record_failed_attempt(email)
                    return None

                if not self.verify_password(password, user_data.password_hash):
                    self._record_failed_attempt(email)
                    return None

                # Reset failed attempts on successful login
                self._reset_failed_attempts(email)

                return {
                    "id": user_data.id,
                    "email": user_data.email,
                    "tenant_id": user_data.tenant_id,
                    "role": user_data.role,
                    "is_active": user_data.is_active,
                }

        except Exception as e:
            logger.error("Authentication error", error=str(e), email=email)
            raise HTTPException(status_code=500, detail="Authentication failed")

    async def authenticate_api_key(self, api_key: str) -> Dict[str, Any]:
        """Authenticate using API key."""
        return self.api_key_manager.validate_api_key(api_key)

    def _record_failed_attempt(self, email: str):
        """Record failed login attempt."""
        now = time.time()
        if email not in self.failed_attempts:
            self.failed_attempts[email] = []

        self.failed_attempts[email].append(now)

        # Clean old attempts
        cutoff = now - self.lockout_duration
        self.failed_attempts[email] = [
            attempt for attempt in self.failed_attempts[email] if attempt > cutoff
        ]

        logger.warning(
            "Failed login attempt",
            email=email,
            attempts=len(self.failed_attempts[email]),
        )

    def _reset_failed_attempts(self, email: str):
        """Reset failed attempts for email."""
        if email in self.failed_attempts:
            del self.failed_attempts[email]

    def _is_locked_out(self, email: str) -> bool:
        """Check if email is locked out."""
        if email not in self.failed_attempts:
            return False

        attempts = self.failed_attempts[email]
        if len(attempts) >= self.max_failed_attempts:
            return True

        return False


# Global instances
auth_manager = AuthenticationManager()
jwt_manager = JWTManager()
api_key_manager = APIKeyManager()
rbac_manager = RBACManager()

# Security scheme
security = HTTPBearer()


# Dependency functions
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """Get current user from JWT token."""
    token = credentials.credentials

    # Try JWT first
    try:
        payload = jwt_manager.verify_token(token)
        return {
            "id": payload.get("sub"),
            "tenant_id": payload.get("tenant_id"),
            "roles": payload.get("roles", []),
            "auth_type": "jwt",
        }
    except HTTPException:
        pass

    # Try API key
    try:
        key_info = api_key_manager.validate_api_key(token)
        return {
            "id": key_info["user_id"],
            "tenant_id": key_info["tenant_id"],
            "roles": ["api_user"],
            "permissions": key_info["permissions"],
            "auth_type": "api_key",
        }
    except HTTPException:
        pass

    raise HTTPException(status_code=401, detail="Invalid authentication credentials")


def require_permissions(permissions: List[str]):
    """Dependency to require specific permissions."""

    def permission_checker(current_user: Dict[str, Any] = Depends(get_current_user)):
        user_roles = current_user.get("roles", [])
        user_permissions = current_user.get("permissions", [])

        # Check if user has any of the required permissions
        has_permission = False
        for permission in permissions:
            # Check role-based permissions
            for role in user_roles:
                if rbac_manager.has_permission(UserRole(role), permission):
                    has_permission = True
                    break

            # Check direct permissions (for API keys)
            if permission in user_permissions:
                has_permission = True
                break

        if not has_permission:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required: {permissions}",
            )

        return current_user

    return permission_checker


def require_tenant_access(tenant_id: str):
    """Dependency to require tenant access."""

    def tenant_checker(current_user: Dict[str, Any] = Depends(get_current_user)):
        user_tenant_id = current_user.get("tenant_id")

        if user_tenant_id != tenant_id:
            raise HTTPException(status_code=403, detail="Access denied to this tenant")

        return current_user

    return tenant_checker
