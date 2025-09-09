"""Complete multi-tenant schema with RLS, quotas, and billing.

Revision ID: 003
Revises: 002
Create Date: 2024-01-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade to complete multi-tenant schema."""
    
    # Create tenants table
    op.create_table('tenants',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('plan', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, default='active'),
        sa.Column('data_region', sa.String(length=50), nullable=False, default='us-east-1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tenants_id'), 'tenants', ['id'], unique=True)
    op.create_index(op.f('ix_tenants_plan'), 'tenants', ['plan'], unique=False)
    
    # Update users table for multi-tenancy
    op.add_column('users', sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False))
    op.add_column('users', sa.Column('role', sa.String(length=20), nullable=False, default='user'))
    op.create_foreign_key('fk_users_tenant_id', 'users', 'tenants', ['tenant_id'], ['id'])
    op.create_index(op.f('ix_users_tenant_id'), 'users', ['tenant_id'], unique=False)
    
    # Create api_keys table
    op.create_table('api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('hash', sa.String(length=255), nullable=False),
        sa.Column('scopes', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('rate_limit', sa.Integer(), nullable=False, default=1000),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_api_keys_tenant_id'), 'api_keys', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_api_keys_hash'), 'api_keys', ['hash'], unique=True)
    
    # Create plans table
    op.create_table('plans',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('price_usd', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('quotas', postgresql.JSONB(), nullable=False),
        sa.Column('features', postgresql.JSONB(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create usage_counters table (partitioned by day)
    op.execute("""
        CREATE TABLE usage_counters (
            tenant_id UUID NOT NULL,
            day DATE NOT NULL,
            tokens_in BIGINT DEFAULT 0,
            tokens_out BIGINT DEFAULT 0,
            tool_calls BIGINT DEFAULT 0,
            ws_minutes BIGINT DEFAULT 0,
            storage_mb BIGINT DEFAULT 0,
            cost_usd NUMERIC(10,4) DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (tenant_id, day)
        ) PARTITION BY RANGE (day)
    """)
    
    # Create partitions for usage_counters (current month and next 2 months)
    op.execute("""
        CREATE TABLE usage_counters_2024_01 PARTITION OF usage_counters
        FOR VALUES FROM ('2024-01-01') TO ('2024-02-01')
    """)
    op.execute("""
        CREATE TABLE usage_counters_2024_02 PARTITION OF usage_counters
        FOR VALUES FROM ('2024-02-01') TO ('2024-03-01')
    """)
    op.execute("""
        CREATE TABLE usage_counters_2024_03 PARTITION OF usage_counters
        FOR VALUES FROM ('2024-03-01') TO ('2024-04-01')
    """)
    
    # Create agent_runs table (partitioned by created_at)
    op.execute("""
        CREATE TABLE agent_runs (
            run_id UUID NOT NULL,
            tenant_id UUID NOT NULL,
            workflow TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            tokens_in INTEGER DEFAULT 0,
            tokens_out INTEGER DEFAULT 0,
            cost_usd NUMERIC(10,4) DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            finished_at TIMESTAMPTZ,
            metadata JSONB,
            PRIMARY KEY (run_id, created_at)
        ) PARTITION BY RANGE (created_at)
    """)
    
    # Create partitions for agent_runs (current month and next 2 months)
    op.execute("""
        CREATE TABLE agent_runs_2024_01 PARTITION OF agent_runs
        FOR VALUES FROM ('2024-01-01') TO ('2024-02-01')
    """)
    op.execute("""
        CREATE TABLE agent_runs_2024_02 PARTITION OF agent_runs
        FOR VALUES FROM ('2024-02-01') TO ('2024-03-01')
    """)
    op.execute("""
        CREATE TABLE agent_runs_2024_03 PARTITION OF agent_runs
        FOR VALUES FROM ('2024-03-01') TO ('2024-04-01')
    """)
    
    # Update existing tables for multi-tenancy
    op.add_column('customers', sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False))
    op.add_column('orders', sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False))
    op.add_column('messages', sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False))
    op.add_column('leads', sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False))
    op.add_column('audit_logs', sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False))
    
    # Add foreign key constraints
    op.create_foreign_key('fk_customers_tenant_id', 'customers', 'tenants', ['tenant_id'], ['id'])
    op.create_foreign_key('fk_orders_tenant_id', 'orders', 'tenants', ['tenant_id'], ['id'])
    op.create_foreign_key('fk_messages_tenant_id', 'messages', 'tenants', ['tenant_id'], ['id'])
    op.create_foreign_key('fk_leads_tenant_id', 'leads', 'tenants', ['tenant_id'], ['id'])
    op.create_foreign_key('fk_audit_logs_tenant_id', 'audit_logs', 'tenants', ['tenant_id'], ['id'])
    
    # Create indexes for tenant_id columns
    op.create_index(op.f('ix_customers_tenant_id'), 'customers', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_orders_tenant_id'), 'orders', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_messages_tenant_id'), 'messages', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_leads_tenant_id'), 'leads', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_tenant_id'), 'audit_logs', ['tenant_id'], unique=False)
    
    # Enable Row Level Security on all tenant tables
    tenant_tables = [
        'tenants', 'users', 'api_keys', 'customers', 'orders', 'order_items',
        'messages', 'leads', 'audit_logs', 'usage_counters', 'agent_runs'
    ]
    
    for table in tenant_tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    
    # Create RLS policies
    op.execute("""
        CREATE POLICY tenant_isolation_tenants ON tenants
        FOR ALL TO authenticated
        USING (id = current_setting('app.tenant_id')::uuid)
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_users ON users
        FOR ALL TO authenticated
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_api_keys ON api_keys
        FOR ALL TO authenticated
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_customers ON customers
        FOR ALL TO authenticated
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_orders ON orders
        FOR ALL TO authenticated
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_order_items ON order_items
        FOR ALL TO authenticated
        USING (EXISTS (
            SELECT 1 FROM orders 
            WHERE orders.id = order_items.order_id 
            AND orders.tenant_id = current_setting('app.tenant_id')::uuid
        ))
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_messages ON messages
        FOR ALL TO authenticated
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_leads ON leads
        FOR ALL TO authenticated
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_audit_logs ON audit_logs
        FOR ALL TO authenticated
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_usage_counters ON usage_counters
        FOR ALL TO authenticated
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_agent_runs ON agent_runs
        FOR ALL TO authenticated
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)
    
    # Create function to set tenant context
    op.execute("""
        CREATE OR REPLACE FUNCTION set_tenant_context(tenant_uuid UUID)
        RETURNS VOID AS $$
        BEGIN
            PERFORM set_config('app.tenant_id', tenant_uuid::text, true);
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Insert default plans
    op.execute("""
        INSERT INTO plans (id, name, price_usd, quotas, features) VALUES
        ('free', 'Free', 0.00, 
         '{"max_messages_per_month": 1000, "max_customers": 100, "max_agents": 1, "max_storage_mb": 100}',
         '{"analytics": false, "file_upload": true, "webhook_support": false, "api_access": false, "priority_support": false, "custom_branding": false, "advanced_ai": false}'),
        ('plus', 'Plus', 29.99, 
         '{"max_messages_per_month": 10000, "max_customers": 1000, "max_agents": 5, "max_storage_mb": 1000}',
         '{"analytics": true, "file_upload": true, "webhook_support": true, "api_access": true, "priority_support": false, "custom_branding": false, "advanced_ai": true}'),
        ('pro', 'Pro', 99.99, 
         '{"max_messages_per_month": 100000, "max_customers": 10000, "max_agents": 20, "max_storage_mb": 10000}',
         '{"analytics": true, "file_upload": true, "webhook_support": true, "api_access": true, "priority_support": true, "custom_branding": true, "advanced_ai": true}')
    """)


def downgrade() -> None:
    """Downgrade multi-tenant schema."""
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS tenant_isolation_agent_runs ON agent_runs")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_usage_counters ON usage_counters")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_audit_logs ON audit_logs")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_leads ON leads")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_messages ON messages")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_order_items ON order_items")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_orders ON orders")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_customers ON customers")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_api_keys ON api_keys")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_users ON users")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_tenants ON tenants")
    
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS set_tenant_context(UUID)")
    
    # Drop tables
    op.drop_table('agent_runs')
    op.drop_table('usage_counters')
    op.drop_table('plans')
    op.drop_table('api_keys')
    op.drop_table('tenants')
    
    # Remove tenant_id columns
    op.drop_column('audit_logs', 'tenant_id')
    op.drop_column('leads', 'tenant_id')
    op.drop_column('messages', 'tenant_id')
    op.drop_column('orders', 'tenant_id')
    op.drop_column('customers', 'tenant_id')
    op.drop_column('users', 'tenant_id')
    op.drop_column('users', 'role')
