"""Security integration tests for multi-tenant isolation and data safety."""

from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

class SecurityViolation(Enum):
    """Security violation types."""
    CROSS_TENANT_ACCESS = "cross_tenant_access"
    QUOTA_EXCEEDED = "quota_exceeded"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    PII_EXPOSURE = "pii_exposure"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DATA_LEAKAGE = "data_leakage"

class IsolationLevel(Enum):
    """Data isolation levels."""
    TENANT_LEVEL = "tenant_level"
    USER_LEVEL = "user_level"
    ROLE_LEVEL = "role_level"
    DOCUMENT_LEVEL = "document_level"

@dataclass
class SecurityAudit:
    """Security audit record."""
    violation_type: SecurityViolation
    tenant_id: str
    user_id: str
    resource_accessed: str
    isolation_level: IsolationLevel
    timestamp: datetime
    severity: str
    blocked: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'violation_type': self.violation_type.value,
            'tenant_id': self.tenant_id,
            'user_id': self.user_id,
            'resource_accessed': self.resource_accessed,
            'isolation_level': self.isolation_level.value,
            'timestamp': self.timestamp.isoformat(),
            'severity': self.severity,
            'blocked': self.blocked
        }