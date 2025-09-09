"""Database client with tenant isolation middleware."""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional, AsyncGenerator
from uuid import UUID
import structlog
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

logger = structlog.get_logger(__name__)


class DatabaseClient:
    """Database client with tenant isolation support."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=300,
        )
        self.session_factory = async_sessionmaker(
            self.engine, 
            expire_on_commit=False,
            class_=AsyncSession
        )
    
    @asynccontextmanager
    async def get_session(self, tenant_id: Optional[UUID] = None) -> AsyncGenerator[AsyncSession, None]:
        """Get database session with optional tenant isolation."""
        async with self.session_factory() as session:
            try:
                if tenant_id:
                    # Set tenant context for RLS
                    await session.execute(
                        text("SELECT set_tenant_context(:tenant_id)"),
                        {"tenant_id": str(tenant_id)}
                    )
                    logger.debug("Tenant context set", tenant_id=tenant_id)
                
                yield session
                await session.commit()
                
            except Exception as e:
                await session.rollback()
                logger.error("Database session error", tenant_id=tenant_id, error=str(e))
                raise
            finally:
                await session.close()
    
    async def close(self):
        """Close database engine."""
        await self.engine.dispose()


# Global database client instance
_db_client: Optional[DatabaseClient] = None


def initialize_database(database_url: str):
    """Initialize global database client."""
    global _db_client
    _db_client = DatabaseClient(database_url)
    logger.info("Database client initialized")


@asynccontextmanager
async def get_db_session(tenant_id: Optional[UUID] = None) -> AsyncGenerator[AsyncSession, None]:
    """Get database session with tenant isolation."""
    if _db_client is None:
        raise RuntimeError("Database client not initialized. Call initialize_database() first.")
    
    async with _db_client.get_session(tenant_id) as session:
        yield session


async def get_db_session_dependency() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI to get database session."""
    # This would typically get tenant_id from request context
    # For now, return session without tenant isolation
    async with get_db_session() as session:
        yield session


class TenantContextMiddleware:
    """Middleware to set tenant context in database sessions."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Extract tenant_id from request headers or JWT
            tenant_id = self._extract_tenant_id(scope)
            
            # Add tenant_id to request state
            scope["state"] = scope.get("state", {})
            scope["state"]["tenant_id"] = tenant_id
        
        await self.app(scope, receive, send)
    
    def _extract_tenant_id(self, scope) -> Optional[UUID]:
        """Extract tenant_id from request headers or JWT."""
        # This would typically extract from JWT token or header
        # For now, return None as placeholder
        return None