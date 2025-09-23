from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    app_name: str = "semantic-cache-service"
    host: str = "0.0.0.0"
    port: int = 8088
    
    # Redis connection
    redis_url: str = "redis://localhost:6379"
    redis_db: int = 0
    redis_password: Optional[str] = None
    
    # Cache settings
    default_ttl_seconds: int = 3600  # 1 hour
    max_ttl_seconds: int = 86400    # 24 hours
    similarity_threshold: float = 0.85  # Similarity threshold for cache hits
    
    # Embedding settings
    embedding_model: str = "text-embedding-ada-002"
    embedding_dimensions: int = 1536
    max_text_length: int = 8192
    
    # Rate limiting
    max_requests_per_minute: int = 1000
    
    class Config:
        env_prefix = "SEMANTIC_CACHE_"

settings = Settings()

