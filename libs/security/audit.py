"""Security audit and logging."""

import time
from typing import Dict, Any, Optional, List
from uuid import UUID
import structlog

from src.auth import get_current_user

logger = structlog.get_logger(__name__)


class SecurityAuditor:
    """Security audit system."""
    
    def __init__(self):
        self.audit_logs: List[Dict[str, Any]] = []
    
    def log_security_event(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "info"
    ):
        """Log security event."""
        audit_entry = {
            "timestamp": time.time(),
            "event_type": event_type,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "details": details or {},
            "severity": severity
        }
        
        self.audit_logs.append(audit_entry)
        
        # Log to structured logger
        logger.info("Security event",
                   event_type=event_type,
                   user_id=user_id,
                   tenant_id=tenant_id,
                   severity=severity)
    
    def track_user_action(
        self,
        action: str,
        resource: str,
        user_id: str,
        tenant_id: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Track user action."""
        self.log_security_event(
            event_type="user_action",
            user_id=user_id,
            tenant_id=tenant_id,
            details={
                "action": action,
                "resource": resource,
                **details
            }
        )
    
    def detect_anomalies(self, user_id: str, recent_actions: List[Dict[str, Any]]) -> List[str]:
        """Detect security anomalies."""
        anomalies = []
        
        # Check for unusual activity patterns
        if len(recent_actions) > 100:  # Too many actions
            anomalies.append("high_activity_volume")
        
        # Check for privilege escalation attempts
        admin_actions = [
            action for action in recent_actions
            if action.get("permission", "").startswith("admin:")
        ]
        
        if len(admin_actions) > 5:
            anomalies.append("privilege_escalation_attempt")
        
        return anomalies


# Global security auditor
security_auditor = SecurityAuditor()


# Convenience functions
def log_security_event(
    event_type: str,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    severity: str = "info"
):
    """Log security event."""
    security_auditor.log_security_event(
        event_type, user_id, tenant_id, details, severity
    )


def track_user_action(
    action: str,
    resource: str,
    user_id: str,
    tenant_id: str,
    details: Optional[Dict[str, Any]] = None
):
    """Track user action."""
    security_auditor.track_user_action(
        action, resource, user_id, tenant_id, details
    )


def detect_anomalies(user_id: str, recent_actions: List[Dict[str, Any]]) -> List[str]:
    """Detect anomalies."""
    return security_auditor.detect_anomalies(user_id, recent_actions)
