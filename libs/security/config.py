"""Security configuration and settings."""

from typing import Dict, Any, List
from pydantic import BaseSettings


class SecuritySettings(BaseSettings):
    """Security configuration settings."""
    
    # JWT Settings
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    
    # Password Settings
    password_min_length: int = 8
    password_require_uppercase: bool = True
    password_require_lowercase: bool = True
    password_require_numbers: bool = True
    password_require_special: bool = True
    
    # Rate Limiting
    rate_limit_requests_per_minute: int = 60
    rate_limit_burst_size: int = 10
    
    # CORS Settings
    cors_allowed_origins: List[str] = ["*"]
    cors_allowed_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_allowed_headers: List[str] = ["Content-Type", "Authorization", "X-Tenant-ID"]
    
    # Security Headers
    security_headers: Dict[str, str] = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
        "Referrer-Policy": "strict-origin-when-cross-origin"
    }
    
    # Threat Detection
    enable_sql_injection_detection: bool = True
    enable_xss_detection: bool = True
    enable_brute_force_detection: bool = True
    max_failed_attempts: int = 5
    lockout_duration_seconds: int = 300
    
    # Encryption
    encryption_key: str = "your-encryption-key-change-in-production"
    enable_data_encryption: bool = True
    
    # Audit Logging
    enable_audit_logging: bool = True
    audit_log_retention_days: int = 90
    
    class Config:
        env_file = ".env"
        env_prefix = "SECURITY_"


# Global security settings
security_settings = SecuritySettings()
