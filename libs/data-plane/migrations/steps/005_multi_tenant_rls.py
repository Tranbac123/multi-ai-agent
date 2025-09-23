"""Multi-tenant RLS migration with comprehensive tenant isolation."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '005_multi_tenant_rls'
down_revision = '004_events_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Create multi-tenant tables with RLS policies."""
    
    # Create tenants table
    op.create_table(
        'tenants',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('plan', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='active'),
        sa.Column('data_region', sa.String(50), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('tenant_id', 'email', name='uq_tenant_email'),
    )
    
    # Create API keys table
    op.create_table(
        'api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('hash', sa.String(255), nullable=False),
        sa.Column('scopes', postgresql.ARRAY(sa.String(50)), nullable=False),
        sa.Column('rate_limit', sa.Integer, nullable=False, default=1000),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    )
    
    # Create plans table
    op.create_table(
        'plans',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('price_usd', sa.Numeric(10, 2), nullable=False),
        sa.Column('quotas', postgresql.JSONB, nullable=False),
        sa.Column('features', postgresql.JSONB, nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    
    # Create usage_counters table with partitioning
    op.create_table(
        'usage_counters',
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('day', sa.Date, nullable=False),
        sa.Column('tokens_in', sa.BigInteger, nullable=False, default=0),
        sa.Column('tokens_out', sa.BigInteger, nullable=False, default=0),
        sa.Column('tool_calls', sa.BigInteger, nullable=False, default=0),
        sa.Column('ws_minutes', sa.BigInteger, nullable=False, default=0),
        sa.Column('storage_mb', sa.BigInteger, nullable=False, default=0),
        sa.Column('cost_usd', sa.Numeric(10, 4), nullable=False, default=0),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('tenant_id', 'day'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    )
    
    # Create agent_runs table with partitioning
    op.create_table(
        'agent_runs',
        sa.Column('run_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workflow', sa.String(100), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('tokens_in', sa.Integer, nullable=False, default=0),
        sa.Column('tokens_out', sa.Integer, nullable=False, default=0),
        sa.Column('cost_usd', sa.Numeric(10, 4), nullable=False, default=0),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('finished_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    )
    
    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.BigInteger, primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('actor', sa.String(255), nullable=False),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource', sa.String(255), nullable=False),
        sa.Column('hash', sa.String(64), nullable=True),
        sa.Column('at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    )
    
    # Create indexes
    op.create_index('idx_users_tenant_id', 'users', ['tenant_id'])
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_api_keys_tenant_id', 'api_keys', ['tenant_id'])
    op.create_index('idx_api_keys_hash', 'api_keys', ['hash'])
    op.create_index('idx_usage_counters_tenant_day', 'usage_counters', ['tenant_id', 'day'])
    op.create_index('idx_agent_runs_tenant_id', 'agent_runs', ['tenant_id'])
    op.create_index('idx_agent_runs_created_at', 'agent_runs', ['created_at'])
    op.create_index('idx_audit_logs_tenant_id', 'audit_logs', ['tenant_id'])
    op.create_index('idx_audit_logs_at', 'audit_logs', ['at'])
    
    # Enable RLS on all tenant tables
    op.execute('ALTER TABLE tenants ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE users ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE usage_counters ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY')
    
    # Create RLS policies
    # Tenants can only see their own data
    op.execute("""
        CREATE POLICY tenant_isolation ON tenants
        USING (id = current_setting('app.tenant_id')::uuid)
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation ON users
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation ON api_keys
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation ON usage_counters
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation ON agent_runs
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation ON audit_logs
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    """)
    
    # Create partitioning for usage_counters (by day)
    op.execute("""
        CREATE TABLE usage_counters_y2024m01 PARTITION OF usage_counters
        FOR VALUES FROM ('2024-01-01') TO ('2024-02-01')
    """)
    
    op.execute("""
        CREATE TABLE usage_counters_y2024m02 PARTITION OF usage_counters
        FOR VALUES FROM ('2024-02-01') TO ('2024-03-01')
    """)
    
    # Create partitioning for agent_runs (by created_at)
    op.execute("""
        CREATE TABLE agent_runs_y2024m01 PARTITION OF agent_runs
        FOR VALUES FROM ('2024-01-01') TO ('2024-02-01')
    """)
    
    op.execute("""
        CREATE TABLE agent_runs_y2024m02 PARTITION OF agent_runs
        FOR VALUES FROM ('2024-02-01') TO ('2024-03-01')
    """)


def downgrade():
    """Drop multi-tenant tables and RLS policies."""
    
    # Drop RLS policies
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON tenants')
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON users')
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON api_keys')
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON usage_counters')
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON agent_runs')
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON audit_logs')
    
    # Disable RLS
    op.execute('ALTER TABLE tenants DISABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE users DISABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE api_keys DISABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE usage_counters DISABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE agent_runs DISABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE audit_logs DISABLE ROW LEVEL SECURITY')
    
    # Drop tables
    op.drop_table('audit_logs')
    op.drop_table('agent_runs')
    op.drop_table('usage_counters')
    op.drop_table('plans')
    op.drop_table('api_keys')
    op.drop_table('users')
    op.drop_table('tenants')

