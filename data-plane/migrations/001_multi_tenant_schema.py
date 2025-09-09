"""Multi-tenant database schema with RLS policies."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create multi-tenant schema with RLS policies."""
    
    # Create tenants table
    op.create_table('tenants',
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.Enum('active', 'suspended', 'cancelled', name='tenant_status'), nullable=False),
        sa.Column('data_region', sa.String(50), nullable=False, default='us-east-1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, default={}),
        sa.PrimaryKeyConstraint('tenant_id')
    )
    op.create_index('ix_tenants_plan_id', 'tenants', ['plan_id'])
    op.create_index('ix_tenants_status', 'tenants', ['status'])
    
    # Create plans table
    op.create_table('plans',
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('price_usd', sa.Numeric(10, 2), nullable=False),
        sa.Column('quotas', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('features', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('plan_id')
    )
    op.create_index('ix_plans_name', 'plans', ['name'], unique=True)
    
    # Create users table
    op.create_table('users',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('role', sa.Enum('admin', 'user', 'viewer', name='user_role'), nullable=False),
        sa.Column('status', sa.Enum('active', 'inactive', 'suspended', name='user_status'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('user_id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE')
    )
    op.create_index('ix_users_tenant_id', 'users', ['tenant_id'])
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    
    # Create API keys table
    op.create_table('api_keys',
        sa.Column('key_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key_hash', sa.String(255), nullable=False),
        sa.Column('scopes', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('rate_limit', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('key_id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE')
    )
    op.create_index('ix_api_keys_tenant_id', 'api_keys', ['tenant_id'])
    op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'], unique=True)
    
    # Create usage counters table (partitioned by day)
    op.create_table('usage_counters',
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('tokens_in', sa.BigInteger(), nullable=False, default=0),
        sa.Column('tokens_out', sa.BigInteger(), nullable=False, default=0),
        sa.Column('tool_calls', sa.BigInteger(), nullable=False, default=0),
        sa.Column('ws_minutes', sa.BigInteger(), nullable=False, default=0),
        sa.Column('storage_mb', sa.BigInteger(), nullable=False, default=0),
        sa.Column('cost_usd', sa.Numeric(10, 4), nullable=False, default=0.0),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('tenant_id', 'day'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE')
    )
    op.create_index('ix_usage_counters_day', 'usage_counters', ['day'])
    
    # Create agent runs table (partitioned by created_at)
    op.create_table('agent_runs',
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workflow', sa.String(255), nullable=False),
        sa.Column('status', sa.Enum('pending', 'running', 'completed', 'failed', 'cancelled', name='run_status'), nullable=False),
        sa.Column('tokens_in', sa.BigInteger(), nullable=False, default=0),
        sa.Column('tokens_out', sa.BigInteger(), nullable=False, default=0),
        sa.Column('cost_usd', sa.Numeric(10, 4), nullable=False, default=0.0),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=False, default={}),
        sa.Column('plan', postgresql.JSONB(astext_type=sa.Text()), nullable=False, default=[]),
        sa.Column('artifacts', postgresql.JSONB(astext_type=sa.Text()), nullable=False, default={}),
        sa.PrimaryKeyConstraint('run_id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE')
    )
    op.create_index('ix_agent_runs_tenant_id', 'agent_runs', ['tenant_id'])
    op.create_index('ix_agent_runs_status', 'agent_runs', ['status'])
    op.create_index('ix_agent_runs_created_at', 'agent_runs', ['created_at'])
    
    # Create audit logs table
    op.create_table('audit_logs',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('actor', sa.String(255), nullable=False),
        sa.Column('action', sa.String(255), nullable=False),
        sa.Column('resource', sa.String(255), nullable=False),
        sa.Column('hash', sa.String(64), nullable=False),
        sa.Column('at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, default={}),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE')
    )
    op.create_index('ix_audit_logs_tenant_id', 'audit_logs', ['tenant_id'])
    op.create_index('ix_audit_logs_at', 'audit_logs', ['at'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    
    # Enable RLS on all tenant tables
    op.execute('ALTER TABLE tenants ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE users ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE usage_counters ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY')
    
    # Create RLS policies
    op.execute("""
        CREATE POLICY tenant_isolation ON tenants
        FOR ALL TO PUBLIC
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation ON users
        FOR ALL TO PUBLIC
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation ON api_keys
        FOR ALL TO PUBLIC
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation ON usage_counters
        FOR ALL TO PUBLIC
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation ON agent_runs
        FOR ALL TO PUBLIC
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation ON audit_logs
        FOR ALL TO PUBLIC
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)
    
    # Create function to set tenant context
    op.execute("""
        CREATE OR REPLACE FUNCTION set_tenant_context(tenant_uuid uuid)
        RETURNS void AS $$
        BEGIN
            PERFORM set_config('app.tenant_id', tenant_uuid::text, true);
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    """Drop multi-tenant schema."""
    op.execute('DROP FUNCTION IF EXISTS set_tenant_context(uuid)')
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON audit_logs')
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON agent_runs')
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON usage_counters')
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON api_keys')
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON users')
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON tenants')
    op.drop_table('audit_logs')
    op.drop_table('agent_runs')
    op.drop_table('usage_counters')
    op.drop_table('api_keys')
    op.drop_table('users')
    op.drop_table('plans')
    op.drop_table('tenants')
