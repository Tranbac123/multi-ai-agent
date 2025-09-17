"""Standardized Redis configuration and client management."""

from typing import Optional
import redis.asyncio as redis

from .logging_config import get_logger

logger = get_logger(__name__)


class RedisConfig:
    """Redis configuration manager."""
    
    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0, **kwargs):
        self.host = host
        self.port = port
        self.db = db
        self.extra_kwargs = kwargs
        self.client: Optional[redis.Redis] = None
    
    async def initialize(self) -> redis.Redis:
        """Initialize Redis client."""
        self.client = redis.Redis(
            host=self.host,
            port=self.port,
            db=self.db,
            **self.extra_kwargs
        )
        
        # Test connection
        await self.client.ping()
        logger.info(f"Redis client initialized: {self.host}:{self.port}/{self.db}")
        
        return self.client
    
    async def close(self) -> None:
        """Close Redis client."""
        if self.client:
            await self.client.close()
            logger.info("Redis client closed")
    
    async def health_check(self) -> bool:
        """Check Redis health."""
        try:
            if not self.client:
                return False
            await self.client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False


# Global Redis config instance
_redis_config: Optional[RedisConfig] = None


def initialize_redis(
    host: str = "localhost", 
    port: int = 6379, 
    db: int = 0, 
    **kwargs
) -> RedisConfig:
    """Initialize global Redis configuration."""
    global _redis_config
    _redis_config = RedisConfig(host, port, db, **kwargs)
    return _redis_config


async def get_redis_client() -> redis.Redis:
    """Get Redis client from the global configuration."""
    if not _redis_config or not _redis_config.client:
        raise RuntimeError("Redis not initialized. Call initialize_redis() first.")
    
    return _redis_config.client


async def get_redis_health() -> bool:
    """Check Redis health."""
    if not _redis_config:
        return False
    
    return await _redis_config.health_check()
