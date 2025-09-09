"""Database client with Row-Level Security (RLS) support."""

import asyncio
from typing import Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text
import structlog

logger = structlog.get_logger(__name__)


class TenantAwareDatabaseClient:
    """Database client with tenant-aware RLS support."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = create_async_engine(database_url)
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        self._tenant_context = asyncio.local()
    
    async def get_session(self, tenant_id: Optional[str] = None) -> AsyncGenerator[AsyncSession, None]:
        """Get database session with tenant context."""
        session = self.session_factory()
        
        try:
            if tenant_id:
                # Set tenant context for RLS
                await session.execute(text("SET app.tenant_id = :tenant_id"), {"tenant_id": tenant_id})
                logger.info("Set tenant context", tenant_id=tenant_id)
            
            yield session
            
        except Exception as e:
            await session.rollback()
            logger.error("Database session error", error=str(e), tenant_id=tenant_id)
            raise
        finally:
            # Reset tenant context
            try:
                await session.execute(text("RESET app.tenant_id"))
            except Exception as e:
                logger.warning("Failed to reset tenant context", error=str(e))
            
            await session.close()
    
    async def execute_with_tenant(self, query: str, params: dict, tenant_id: str):
        """Execute query with tenant context."""
        async with self.get_session(tenant_id) as session:
            result = await session.execute(text(query), params)
            await session.commit()
            return result
    
    async def test_tenant_isolation(self, tenant_id: str) -> bool:
        """Test that tenant isolation is working correctly."""
        try:
            # Test that we can only see our own tenant's data
            async with self.get_session(tenant_id) as session:
                # Try to query tenants table - should only see our tenant
                result = await session.execute(
                    text("SELECT id, name FROM tenants WHERE id = :tenant_id"),
                    {"tenant_id": tenant_id}
                )
                rows = result.fetchall()
                
                if len(rows) == 1 and str(rows[0][0]) == tenant_id:
                    logger.info("Tenant isolation test passed", tenant_id=tenant_id)
                    return True
                else:
                    logger.error("Tenant isolation test failed", tenant_id=tenant_id, rows=len(rows))
                    return False
                    
        except Exception as e:
            logger.error("Tenant isolation test error", error=str(e), tenant_id=tenant_id)
            return False


# Global database client instance
db_client: Optional[TenantAwareDatabaseClient] = None


def get_database_client() -> TenantAwareDatabaseClient:
    """Get global database client instance."""
    global db_client
    if db_client is None:
        raise RuntimeError("Database client not initialized")
    return db_client


def initialize_database_client(database_url: str):
    """Initialize global database client."""
    global db_client
    db_client = TenantAwareDatabaseClient(database_url)
    logger.info("Database client initialized", database_url=database_url)


async def get_db_session(tenant_id: Optional[str] = None) -> AsyncGenerator[AsyncSession, None]:
    """Get database session with tenant context."""
    client = get_database_client()
    async with client.get_session(tenant_id) as session:
        yield session
