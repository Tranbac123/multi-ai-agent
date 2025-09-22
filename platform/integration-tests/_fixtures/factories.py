"""Factory classes for generating test data."""

import random
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional


class TenantFactory:
    """Factory for creating tenant test data."""
    
    @staticmethod
    def create(tenant_id: Optional[str] = None, **overrides) -> Dict[str, Any]:
        """Create a tenant with realistic test data."""
        tenant_id = tenant_id or f"tenant_{uuid.uuid4().hex[:8]}"
        
        return {
            "tenant_id": tenant_id,
            "name": f"Test Tenant {tenant_id[-4:]}",
            "plan": random.choice(["free", "pro", "enterprise"]),
            "tier": random.choice(["basic", "premium", "enterprise"]),
            "created_at": datetime.now(timezone.utc).isoformat(),
            **overrides
        }


class UserFactory:
    """Factory for creating user test data."""
    
    @staticmethod
    def create(tenant_id: str, user_id: Optional[str] = None, **overrides) -> Dict[str, Any]:
        """Create a user with realistic test data."""
        user_id = user_id or f"user_{uuid.uuid4().hex[:8]}"
        
        return {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "email": f"user_{user_id[-4:]}@testtenant.com",
            "name": f"Test User {user_id[-4:]}",
            "role": random.choice(["admin", "user", "viewer"]),
            "created_at": datetime.now(timezone.utc).isoformat(),
            **overrides
        }