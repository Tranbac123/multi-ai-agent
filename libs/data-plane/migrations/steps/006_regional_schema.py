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
    
    # Enable Row Level Security (RLS) patterns
    await _setup_rls_patterns(db)
    
    await db.commit()
    logger.info("Migration 006 completed: Regional schema and providers created with RLS patterns")


async def _setup_rls_patterns(db: AsyncSession) -> None:
    """Setup Row Level Security patterns for multi-tenant data isolation."""
    
    # Enable RLS on tenants table
    await db.execute(text("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY"))
    
    # Create RLS policy for tenants (users can only access their own tenant)
    await db.execute(text("""
        CREATE POLICY tenant_isolation_policy ON tenants
        FOR ALL TO authenticated_users
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
    """))
    
    # Enable RLS on regional_providers table
    await db.execute(text("ALTER TABLE regional_providers ENABLE ROW LEVEL SECURITY"))
    
    # Create RLS policy for regional providers (tenants can only access their region's providers)
    await db.execute(text("""
        CREATE POLICY regional_provider_access_policy ON regional_providers
        FOR SELECT TO authenticated_users
        USING (
            region = (
                SELECT data_region 
                FROM tenants 
                WHERE tenant_id = current_setting('app.current_tenant_id')::uuid
            )
        )
    """))
    
    # Enable RLS on analytics_events table
    await db.execute(text("ALTER TABLE analytics_events ENABLE ROW LEVEL SECURITY"))
    
    # Create RLS policy for analytics events (tenants can only access their own events)
    await db.execute(text("""
        CREATE POLICY analytics_tenant_isolation_policy ON analytics_events
        FOR ALL TO authenticated_users
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
    """))
    
    # Enable RLS on analytics_events_regional table
    await db.execute(text("ALTER TABLE analytics_events_regional ENABLE ROW LEVEL SECURITY"))
    
    # Create RLS policy for regional analytics events
    await db.execute(text("""
        CREATE POLICY regional_analytics_access_policy ON analytics_events_regional
        FOR ALL TO authenticated_users
        USING (
            tenant_id = current_setting('app.current_tenant_id')::uuid
            AND data_region = (
                SELECT data_region 
                FROM tenants 
                WHERE tenant_id = current_setting('app.current_tenant_id')::uuid
            )
        )
    """))
    
    # Enable RLS on any existing user-related tables
    await _enable_rls_on_user_tables(db)
    
    # Create security context functions
    await _create_security_context_functions(db)
    
    logger.info("RLS patterns configured successfully")


async def _enable_rls_on_user_tables(db: AsyncSession) -> None:
    """Enable RLS on user-related tables."""
    
    # List of tables that should have tenant isolation
    user_tables = [
        'users', 'user_sessions', 'user_preferences', 'user_activity',
        'conversations', 'messages', 'agent_runs', 'tool_calls',
        'workflows', 'sagas', 'events'
    ]
    
    for table_name in user_tables:
        try:
            # Check if table exists
            result = await db.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = :table_name
                )
            """), {"table_name": table_name})
            
            table_exists = result.scalar()
            
            if table_exists:
                # Enable RLS
                await db.execute(text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"))
                
                # Create tenant isolation policy
                await db.execute(text(f"""
                    CREATE POLICY tenant_isolation_policy ON {table_name}
                    FOR ALL TO authenticated_users
                    USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
                """))
                
                logger.info(f"RLS enabled on table: {table_name}")
        except Exception as e:
            logger.warning(f"Failed to enable RLS on table {table_name}: {e}")


async def _create_security_context_functions(db: AsyncSession) -> None:
    """Create security context functions for RLS."""
    
    # Function to set current tenant context
    await db.execute(text("""
        CREATE OR REPLACE FUNCTION set_current_tenant(tenant_uuid uuid)
        RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        AS $$
        BEGIN
            PERFORM set_config('app.current_tenant_id', tenant_uuid::text, true);
            PERFORM set_config('app.current_tenant_region', (
                SELECT data_region 
                FROM tenants 
                WHERE tenant_id = tenant_uuid
            ), true);
        END;
        $$;
    """))
    
    # Function to get current tenant
    await db.execute(text("""
        CREATE OR REPLACE FUNCTION get_current_tenant()
        RETURNS uuid
        LANGUAGE plpgsql
        SECURITY DEFINER
        AS $$
        BEGIN
            RETURN current_setting('app.current_tenant_id')::uuid;
        EXCEPTION
            WHEN OTHERS THEN
                RETURN NULL;
        END;
        $$;
    """))
    
    # Function to get current tenant region
    await db.execute(text("""
        CREATE OR REPLACE FUNCTION get_current_tenant_region()
        RETURNS text
        LANGUAGE plpgsql
        SECURITY DEFINER
        AS $$
        BEGIN
            RETURN current_setting('app.current_tenant_region');
        EXCEPTION
            WHEN OTHERS THEN
                RETURN 'us-east-1';
        END;
        $$;
    """))
    
    # Function to check if user belongs to tenant
    await db.execute(text("""
        CREATE OR REPLACE FUNCTION user_belongs_to_tenant(user_uuid uuid, tenant_uuid uuid)
        RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        AS $$
        BEGIN
            RETURN EXISTS (
                SELECT 1 FROM users 
                WHERE user_id = user_uuid 
                AND tenant_id = tenant_uuid
            );
        END;
        $$;
    """))
    
    # Function to validate regional data access
    await db.execute(text("""
        CREATE OR REPLACE FUNCTION validate_regional_access(requested_region text)
        RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        AS $$
        DECLARE
            tenant_region text;
            allowed_regions text[];
        BEGIN
            -- Get tenant's data region and allowed regions
            SELECT data_region, allowed_regions 
            INTO tenant_region, allowed_regions
            FROM tenants 
            WHERE tenant_id = current_setting('app.current_tenant_id')::uuid;
            
            -- Check if requested region matches tenant's data region
            IF requested_region = tenant_region THEN
                RETURN true;
            END IF;
            
            -- Check if requested region is in allowed regions
            IF requested_region = ANY(allowed_regions) THEN
                RETURN true;
            END IF;
            
            RETURN false;
        END;
        $$;
    """))
    
    logger.info("Security context functions created successfully")


async def downgrade(db: AsyncSession) -> None:
    """Remove regional configuration and RLS patterns."""
    
    # Remove RLS patterns first
    await _cleanup_rls_patterns(db)
    
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
    logger.info("Migration 006 downgrade completed: Regional schema and RLS patterns removed")


async def _cleanup_rls_patterns(db: AsyncSession) -> None:
    """Clean up RLS patterns and security functions."""
    
    # Drop security context functions
    security_functions = [
        'set_current_tenant', 'get_current_tenant', 'get_current_tenant_region',
        'user_belongs_to_tenant', 'validate_regional_access'
    ]
    
    for func_name in security_functions:
        try:
            await db.execute(text(f"DROP FUNCTION IF EXISTS {func_name} CASCADE"))
        except Exception as e:
            logger.warning(f"Failed to drop function {func_name}: {e}")
    
    # Disable RLS on tables
    tables_with_rls = [
        'tenants', 'regional_providers', 'analytics_events', 'analytics_events_regional',
        'users', 'user_sessions', 'user_preferences', 'user_activity',
        'conversations', 'messages', 'agent_runs', 'tool_calls',
        'workflows', 'sagas', 'events'
    ]
    
    for table_name in tables_with_rls:
        try:
            await db.execute(text(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY"))
            
            # Drop RLS policies
            await db.execute(text(f"""
                DROP POLICY IF EXISTS tenant_isolation_policy ON {table_name}
            """))
            await db.execute(text(f"""
                DROP POLICY IF EXISTS regional_provider_access_policy ON {table_name}
            """))
            await db.execute(text(f"""
                DROP POLICY IF EXISTS analytics_tenant_isolation_policy ON {table_name}
            """))
            await db.execute(text(f"""
                DROP POLICY IF EXISTS regional_analytics_access_policy ON {table_name}
            """))
            
        except Exception as e:
            logger.warning(f"Failed to clean up RLS on table {table_name}: {e}")
    
    logger.info("RLS patterns cleaned up successfully")

