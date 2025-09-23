from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "policy-adapter"
    host: str = "0.0.0.0"
    port: int = 8091
    cors_origins: str = "*"
    jwt_aud: str | None = None
    jwt_iss: str | None = None
    cache_ttl_s: int = 120
    storage_backend: str = "memory"  # memory|fs|s3 placeholder
    class Config: env_prefix = "POLICY_"

settings = Settings()

