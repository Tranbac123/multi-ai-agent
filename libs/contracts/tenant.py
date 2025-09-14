"""Tenant contracts and specifications."""

from datetime import datetime
from typing import Dict, Any, Optional, List, Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict


class Tenant(BaseModel):
    """Tenant specification."""

    tenant_id: UUID = Field(default_factory=uuid4)
    name: str = Field(description="Tenant name")
    plan_id: UUID = Field(description="Plan identifier")
    status: Literal["active", "suspended", "cancelled"] = Field(default="active")
    data_region: str = Field(default="us-east-1", description="Data region")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Tenant metadata"
    )


class User(BaseModel):
    """User specification."""

    user_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(description="Tenant identifier")
    email: str = Field(description="User email")
    role: Literal["admin", "user", "viewer"] = Field(default="user")
    status: Literal["active", "inactive", "suspended"] = Field(default="active")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = Field(
        default=None, description="Last login time"
    )


class APIKey(BaseModel):
    """API key specification."""

    key_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(description="Tenant identifier")
    key_hash: str = Field(description="Hashed API key")
    scopes: List[str] = Field(description="API key scopes")
    rate_limit: int = Field(ge=1, description="Rate limit per minute")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = Field(default=None, description="Expiration time")
    last_used_at: Optional[datetime] = Field(default=None, description="Last used time")


class Plan(BaseModel):
    """Plan specification."""

    plan_id: UUID = Field(default_factory=uuid4)
    name: str = Field(description="Plan name")
    price_usd: float = Field(ge=0.0, description="Price in USD")
    quotas: Dict[str, int] = Field(description="Plan quotas")
    features: Dict[str, bool] = Field(description="Plan features")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
