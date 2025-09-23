from pydantic_settings import BaseSettings
from typing import Dict, List, Optional

class Settings(BaseSettings):
    app_name: str = "model-gateway"
    host: str = "0.0.0.0"
    port: int = 8083
    
    # Provider configurations
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    azure_openai_key: Optional[str] = None
    
    # Circuit breaker settings
    failure_threshold: int = 5
    recovery_timeout: int = 60
    
    # Rate limiting
    requests_per_minute: int = 1000
    tokens_per_minute: int = 100000
    
    # Timeout settings
    request_timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Allowed models per provider
    openai_models: List[str] = ["gpt-4", "gpt-3.5-turbo", "gpt-4-turbo"]
    anthropic_models: List[str] = ["claude-3-sonnet", "claude-3-haiku"]
    azure_models: List[str] = ["gpt-4", "gpt-35-turbo"]
    
    class Config:
        env_prefix = "MODEL_GATEWAY_"

settings = Settings()
