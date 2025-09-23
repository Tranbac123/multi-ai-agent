from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    app_name: str = "notification-service"
    host: str = "0.0.0.0"
    port: int = 8097
    
    # Email configuration
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = True
    from_email: str = "noreply@company.com"
    
    # Slack configuration
    slack_bot_token: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    
    # Teams configuration
    teams_webhook_url: Optional[str] = None
    
    # Webhook configuration
    webhook_timeout: int = 30
    webhook_retry_attempts: int = 3
    webhook_retry_delay: float = 1.0
    
    # Rate limiting
    max_notifications_per_minute: int = 1000
    
    # Template settings
    template_base_path: str = "templates"
    
    class Config:
        env_prefix = "NOTIFICATION_"

settings = Settings()

