"""Security utilities and middleware for the AIaaS platform."""

from .auth import (
    AuthenticationManager,
    JWTManager,
    APIKeyManager,
    RBACManager,
    get_current_user,
    require_permissions,
    require_tenant_access
)

from .encryption import (
    EncryptionManager,
    encrypt_sensitive_data,
    decrypt_sensitive_data,
    hash_password,
    verify_password
)

from .validation import (
    InputValidator,
    sanitize_input,
    validate_tenant_id,
    validate_user_input,
    validate_api_key
)

from .middleware import (
    SecurityMiddleware,
    RateLimitMiddleware,
    CORSMiddleware,
    SecurityHeadersMiddleware,
    TenantIsolationMiddleware
)

from .audit import (
    SecurityAuditor,
    log_security_event,
    track_user_action,
    detect_anomalies
)

from .threat_detection import (
    ThreatDetector,
    detect_sql_injection,
    detect_xss_attack,
    detect_brute_force,
    detect_privilege_escalation
)

__all__ = [
    # Authentication
    "AuthenticationManager",
    "JWTManager", 
    "APIKeyManager",
    "RBACManager",
    "get_current_user",
    "require_permissions",
    "require_tenant_access",
    
    # Encryption
    "EncryptionManager",
    "encrypt_sensitive_data",
    "decrypt_sensitive_data",
    "hash_password",
    "verify_password",
    
    # Validation
    "InputValidator",
    "sanitize_input",
    "validate_tenant_id",
    "validate_user_input",
    "validate_api_key",
    
    # Middleware
    "SecurityMiddleware",
    "RateLimitMiddleware",
    "CORSMiddleware",
    "SecurityHeadersMiddleware",
    "TenantIsolationMiddleware",
    
    # Audit
    "SecurityAuditor",
    "log_security_event",
    "track_user_action",
    "detect_anomalies",
    
    # Threat Detection
    "ThreatDetector",
    "detect_sql_injection",
    "detect_xss_attack",
    "detect_brute_force",
    "detect_privilege_escalation"
]
