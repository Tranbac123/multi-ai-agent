"""Migration 006: Add regional configuration and data residency controls."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

logger = structlog.get_logger(__name__)


async def upgrade(db: AsyncSession) -> None:
    """Add regional configuration to tenants and create regional providers table."""
    
    # Add regional configuration to tenants table
    await db.execute(text("""
        ALTER TABLE tenants 
        ADD COLUMN IF NOT EXISTS data_region VARCHAR(50) NOT NULL DEFAULT 'us-east-1'
    """))
    
    await db.execute(text("""
        ALTER TABLE tenants 
        ADD COLUMN IF NOT EXISTS allowed_regions TEXT[] DEFAULT ARRAY['us-east-1']
    """))
    
    await db.execute(text("""
        ALTER TABLE tenants 
        ADD COLUMN IF NOT EXISTS regional_config JSONB DEFAULT '{}'
    """))
    
    # Create regional providers table
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS regional_providers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            region VARCHAR(50) NOT NULL,
            provider_type VARCHAR(50) NOT NULL,
            provider_name VARCHAR(100) NOT NULL,
            endpoint_url TEXT NOT NULL,
            credentials JSONB NOT NULL,
            is_active BOOLEAN DEFAULT true,
            priority INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(region, provider_type, provider_name)
        )
    """))
    
    # Create regional analytics partitioning
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS analytics_events_regional (
            LIKE analytics_events INCLUDING ALL
        ) PARTITION BY LIST (data_region)
    """))
    
    # Create partitions for common regions
    regions = ['us-east-1', 'us-west-2', 'eu-west-1', 'ap-southeast-1', 'ap-northeast-1']
    for region in regions:
        await db.execute(text(f"""
            CREATE TABLE IF NOT EXISTS analytics_events_{region.replace('-', '_')}
            PARTITION OF analytics_events_regional
            FOR VALUES IN ('{region}')
        """))
    
    # Add data_region column to analytics_events if not exists
    await db.execute(text("""
        ALTER TABLE analytics_events 
        ADD COLUMN IF NOT EXISTS data_region VARCHAR(50) DEFAULT 'us-east-1'
    """))
    
    # Create index on regional providers
    await db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_regional_providers_region_type 
        ON regional_providers(region, provider_type, is_active)
    """))
    
    # Create index on tenant data_region
    await db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_tenants_data_region 
        ON tenants(data_region)
    """))
    
    # Insert default regional providers
    default_providers = [
        # US East 1
        ('us-east-1', 'llm', 'openai', 'https://api.openai.com/v1', '{"api_key": "env:OPENAI_API_KEY"}'),
        ('us-east-1', 'llm', 'anthropic', 'https://api.anthropic.com/v1', '{"api_key": "env:ANTHROPIC_API_KEY"}'),
        ('us-east-1', 'vector', 'pinecone', 'https://api.pinecone.io', '{"api_key": "env:PINECONE_API_KEY"}'),
        ('us-east-1', 'storage', 's3', 'https://s3.amazonaws.com', '{"access_key": "env:AWS_ACCESS_KEY_ID"}'),
        
        # EU West 1
        ('eu-west-1', 'llm', 'openai', 'https://api.openai.com/v1', '{"api_key": "env:OPENAI_API_KEY"}'),
        ('eu-west-1', 'llm', 'anthropic', 'https://api.anthropic.com/v1', '{"api_key": "env:ANTHROPIC_API_KEY"}'),
        ('eu-west-1', 'vector', 'pinecone', 'https://api.pinecone.io', '{"api_key": "env:PINECONE_API_KEY"}'),
        ('eu-west-1', 'storage', 's3', 'https://s3.eu-west-1.amazonaws.com', '{"access_key": "env:AWS_ACCESS_KEY_ID"}'),
        
        # AP Southeast 1
        ('ap-southeast-1', 'llm', 'openai', 'https://api.openai.com/v1', '{"api_key": "env:OPENAI_API_KEY"}'),
        ('ap-southeast-1', 'llm', 'anthropic', 'https://api.anthropic.com/v1', '{"api_key": "env:ANTHROPIC_API_KEY"}'),
        ('ap-southeast-1', 'vector', 'pinecone', 'https://api.pinecone.io', '{"api_key": "env:PINECONE_API_KEY"}'),
        ('ap-southeast-1', 'storage', 's3', 'https://s3.ap-southeast-1.amazonaws.com', '{"access_key": "env:AWS_ACCESS_KEY_ID"}'),
    ]
    
    for region, provider_type, provider_name, endpoint_url, credentials in default_providers:
        await db.execute(text("""
            INSERT INTO regional_providers (region, provider_type, provider_name, endpoint_url, credentials)
            VALUES (:region, :provider_type, :provider_name, :endpoint_url, :credentials::jsonb)
            ON CONFLICT (region, provider_type, provider_name) DO NOTHING
        """), {
            "region": region,
            "provider_type": provider_type,
            "provider_name": provider_name,
            "endpoint_url": endpoint_url,
            "credentials": credentials
        })
    
    await db.commit()
    logger.info("Migration 006 completed: Regional schema and providers created")


async def downgrade(db: AsyncSession) -> None:
    """Remove regional configuration."""
    
    # Drop regional analytics partitions
    regions = ['us-east-1', 'us-west-2', 'eu-west-1', 'ap-southeast-1', 'ap-northeast-1']
    for region in regions:
        await db.execute(text(f"""
            DROP TABLE IF EXISTS analytics_events_{region.replace('-', '_')}
        """))
    
    # Drop regional analytics table
    await db.execute(text("DROP TABLE IF EXISTS analytics_events_regional"))
    
    # Drop regional providers table
    await db.execute(text("DROP TABLE IF EXISTS regional_providers"))
    
    # Remove regional columns from tenants
    await db.execute(text("ALTER TABLE tenants DROP COLUMN IF EXISTS data_region"))
    await db.execute(text("ALTER TABLE tenants DROP COLUMN IF EXISTS allowed_regions"))
    await db.execute(text("ALTER TABLE tenants DROP COLUMN IF EXISTS regional_config"))
    
    # Remove data_region column from analytics_events
    await db.execute(text("ALTER TABLE analytics_events DROP COLUMN IF EXISTS data_region"))
    
    await db.commit()
    logger.info("Migration 006 downgrade completed: Regional schema removed")
