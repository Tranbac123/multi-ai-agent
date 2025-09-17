"""Standardized database configuration and session management."""

from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text

from .logging_config import get_logger

logger = get_logger(__name__)


class DatabaseConfig:
    """Database configuration manager."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = None
        self.session_factory = None
    
    async def initialize(self) -> None:
        """Initialize database engine and session factory."""
        self.engine = create_async_engine(
            self.database_url,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=300,
        )
        self.session_factory = async_sessionmaker(
            self.engine, 
            expire_on_commit=False
        )
        logger.info("Database engine and session factory initialized")
    
    async def close(self) -> None:
        """Close database engine."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database engine closed")
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session."""
        if not self.session_factory:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def health_check(self) -> bool:
        """Check database health."""
        try:
            async with self.get_session() as session:
                await session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Global database config instance
_db_config: Optional[DatabaseConfig] = None


def initialize_database(database_url: str) -> DatabaseConfig:
    """Initialize global database configuration."""
    global _db_config
    _db_config = DatabaseConfig(database_url)
    return _db_config


async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session from the global configuration."""
    if not _db_config:
        raise RuntimeError("Database not initialized. Call initialize_database() first.")
    
    async for session in _db_config.get_session():
        yield session


async def get_database_health() -> bool:
    """Check database health."""
    if not _db_config:
        return False
    
    return await _db_config.health_check()
