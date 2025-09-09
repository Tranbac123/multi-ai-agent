"""Configuration profiles using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseSettings, Field, validator
from pydantic_settings import BaseSettings as PydanticBaseSettings


class DatabaseSettings(BaseSettings):
    """Database configuration."""
    url: str = Field(..., env="DATABASE_URL")
    pool_size: int = Field(10, env="DATABASE_POOL_SIZE")
    max_overflow: int = Field(20, env="DATABASE_MAX_OVERFLOW")
    pool_timeout: int = Field(30, env="DATABASE_POOL_TIMEOUT")
    pool_recycle: int = Field(3600, env="DATABASE_POOL_RECYCLE")
    echo: bool = Field(False, env="DATABASE_ECHO")


class RedisSettings(BaseSettings):
    """Redis configuration."""
    url: str = Field(..., env="REDIS_URL")
    max_connections: int = Field(20, env="REDIS_MAX_CONNECTIONS")
    socket_timeout: int = Field(5, env="REDIS_SOCKET_TIMEOUT")
    socket_connect_timeout: int = Field(5, env="REDIS_SOCKET_CONNECT_TIMEOUT")
    retry_on_timeout: bool = Field(True, env="REDIS_RETRY_ON_TIMEOUT")


class NATSSettings(BaseSettings):
    """NATS configuration."""
    url: str = Field(..., env="NATS_URL")
    max_reconnect_attempts: int = Field(10, env="NATS_MAX_RECONNECT_ATTEMPTS")
    reconnect_time_wait: int = Field(2, env="NATS_RECONNECT_TIME_WAIT")
    max_payload: int = Field(1048576, env="NATS_MAX_PAYLOAD")
    jetstream_enabled: bool = Field(True, env="NATS_JETSTREAM_ENABLED")


class OpenAISettings(BaseSettings):
    """OpenAI configuration."""
    api_key: str = Field(..., env="OPENAI_API_KEY")
    base_url: Optional[str] = Field(None, env="OPENAI_BASE_URL")
    max_tokens: int = Field(4000, env="OPENAI_MAX_TOKENS")
    temperature: float = Field(0.7, env="OPENAI_TEMPERATURE")
    timeout: int = Field(30, env="OPENAI_TIMEOUT")


class AnthropicSettings(BaseSettings):
    """Anthropic configuration."""
    api_key: str = Field(..., env="ANTHROPIC_API_KEY")
    max_tokens: int = Field(4000, env="ANTHROPIC_MAX_TOKENS")
    temperature: float = Field(0.7, env="ANTHROPIC_TEMPERATURE")
    timeout: int = Field(30, env="ANTHROPIC_TIMEOUT")


class SecuritySettings(BaseSettings):
    """Security configuration."""
    secret_key: str = Field(..., env="SECRET_KEY")
    jwt_algorithm: str = Field("HS256", env="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(60, env="JWT_EXPIRE_MINUTES")
    cors_origins: List[str] = Field(["*"], env="CORS_ORIGINS")
    rate_limit_per_minute: int = Field(100, env="RATE_LIMIT_PER_MINUTE")
    max_file_size_mb: int = Field(10, env="MAX_FILE_SIZE_MB")


class ObservabilitySettings(BaseSettings):
    """Observability configuration."""
    otel_endpoint: Optional[str] = Field(None, env="OTEL_ENDPOINT")
    prometheus_port: int = Field(9090, env="PROMETHEUS_PORT")
    grafana_url: Optional[str] = Field(None, env="GRAFANA_URL")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_format: str = Field("json", env="LOG_FORMAT")


class BillingSettings(BaseSettings):
    """Billing configuration."""
    stripe_secret_key: Optional[str] = Field(None, env="STRIPE_SECRET_KEY")
    stripe_webhook_secret: Optional[str] = Field(None, env="STRIPE_WEBHOOK_SECRET")
    braintree_merchant_id: Optional[str] = Field(None, env="BRAINTREE_MERCHANT_ID")
    braintree_public_key: Optional[str] = Field(None, env="BRAINTREE_PUBLIC_KEY")
    braintree_private_key: Optional[str] = Field(None, env="BRAINTREE_PRIVATE_KEY")


class VectorDBSettings(BaseSettings):
    """Vector database configuration."""
    provider: str = Field("chroma", env="VECTOR_DB_PROVIDER")
    host: str = Field("localhost", env="VECTOR_DB_HOST")
    port: int = Field(8000, env="VECTOR_DB_PORT")
    collection_name: str = Field("documents", env="VECTOR_DB_COLLECTION")
    embedding_model: str = Field("text-embedding-ada-002", env="VECTOR_DB_EMBEDDING_MODEL")


class BaseSettings(PydanticBaseSettings):
    """Base application settings."""
    
    # Environment
    environment: str = Field("development", env="ENVIRONMENT")
    debug: bool = Field(False, env="DEBUG")
    app_name: str = Field("Multi-AI-Agent", env="APP_NAME")
    app_version: str = Field("2.0.0", env="APP_VERSION")
    
    # Service configuration
    api_gateway_host: str = Field("0.0.0.0", env="API_GATEWAY_HOST")
    api_gateway_port: int = Field(8000, env="API_GATEWAY_PORT")
    orchestrator_host: str = Field("0.0.0.0", env="ORCHESTRATOR_HOST")
    orchestrator_port: int = Field(8001, env="ORCHESTRATOR_PORT")
    router_host: str = Field("0.0.0.0", env="ROUTER_HOST")
    router_port: int = Field(8002, env="ROUTER_PORT")
    realtime_host: str = Field("0.0.0.0", env="REALTIME_HOST")
    realtime_port: int = Field(8003, env="REALTIME_PORT")
    ingestion_host: str = Field("0.0.0.0", env="INGESTION_HOST")
    ingestion_port: int = Field(8004, env="INGESTION_PORT")
    analytics_host: str = Field("0.0.0.0", env="ANALYTICS_HOST")
    analytics_port: int = Field(8005, env="ANALYTICS_PORT")
    billing_host: str = Field("0.0.0.0", env="BILLING_HOST")
    billing_port: int = Field(8006, env="BILLING_PORT")
    
    # Component settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    nats: NATSSettings = Field(default_factory=NATSSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    anthropic: AnthropicSettings = Field(default_factory=AnthropicSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    billing: BillingSettings = Field(default_factory=BillingSettings)
    vector_db: VectorDBSettings = Field(default_factory=VectorDBSettings)
    
    # Feature flags
    feature_flags_enabled: bool = Field(True, env="FEATURE_FLAGS_ENABLED")
    registry_enabled: bool = Field(True, env="REGISTRY_ENABLED")
    
    # Multi-tenancy
    default_tenant_id: str = Field("00000000-0000-0000-0000-000000000000", env="DEFAULT_TENANT_ID")
    tenant_isolation_enabled: bool = Field(True, env="TENANT_ISOLATION_ENABLED")
    
    # Performance
    max_concurrent_requests: int = Field(100, env="MAX_CONCURRENT_REQUESTS")
    request_timeout: int = Field(30, env="REQUEST_TIMEOUT")
    worker_processes: int = Field(1, env="WORKER_PROCESSES")
    
    @validator("environment")
    def validate_environment(cls, v):
        """Validate environment value."""
        if v not in ["development", "staging", "production"]:
            raise ValueError("Environment must be development, staging, or production")
        return v
    
    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> BaseSettings:
    """Get cached settings instance."""
    return BaseSettings()


def get_environment_config(environment: str) -> Dict[str, Any]:
    """Get environment-specific configuration."""
    configs = {
        "development": {
            "debug": True,
            "log_level": "DEBUG",
            "database": {"echo": True},
            "observability": {"log_format": "pretty"}
        },
        "staging": {
            "debug": False,
            "log_level": "INFO",
            "database": {"echo": False},
            "observability": {"log_format": "json"}
        },
        "production": {
            "debug": False,
            "log_level": "WARNING",
            "database": {"echo": False},
            "observability": {"log_format": "json"},
            "security": {"cors_origins": ["https://yourdomain.com"]}
        }
    }
    
    return configs.get(environment, configs["development"])


def get_region_config(region: str) -> Dict[str, Any]:
    """Get region-specific configuration."""
    configs = {
        "us-east-1": {
            "database": {"url": "postgresql://..."},
            "redis": {"url": "redis://..."},
            "nats": {"url": "nats://..."}
        },
        "eu-west-1": {
            "database": {"url": "postgresql://..."},
            "redis": {"url": "redis://..."},
            "nats": {"url": "nats://..."}
        },
        "ap-southeast-1": {
            "database": {"url": "postgresql://..."},
            "redis": {"url": "redis://..."},
            "nats": {"url": "nats://..."}
        }
    }
    
    return configs.get(region, configs["us-east-1"])
