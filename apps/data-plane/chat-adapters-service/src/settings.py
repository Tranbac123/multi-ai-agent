from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    app_name: str = "chat-adapters-service"
    host: str = "0.0.0.0"
    port: int = 8084
    
    # Chat platform configurations
    discord_token: Optional[str] = None
    slack_token: Optional[str] = None
    slack_signing_secret: Optional[str] = None
    telegram_token: Optional[str] = None
    teams_webhook_url: Optional[str] = None
    
    # Message processing
    max_message_length: int = 4000
    message_timeout: int = 30
    retry_attempts: int = 3
    
    # Supported platforms
    enabled_platforms: List[str] = ["discord", "slack", "telegram", "teams"]
    
    # Integration settings
    model_gateway_url: str = "http://model-gateway:8083"
    retrieval_service_url: str = "http://retrieval-service:8080"
    
    class Config:
        env_prefix = "CHAT_ADAPTERS_"

settings = Settings()

