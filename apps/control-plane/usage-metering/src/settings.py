from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "usage-metering"
    host: str = "0.0.0.0"
    port: int = 8095
    cors_origins: str = "*"
    jwt_aud: str | None = None
    jwt_iss: str | None = None
    cache_ttl_s: int = 120
    storage_backend: str = "memory"  # memory|fs|s3 placeholder
    class Config: env_prefix = "USAGE_"

settings = Settings()

