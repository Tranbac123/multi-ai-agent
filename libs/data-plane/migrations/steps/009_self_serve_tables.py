"""Migration: Add self-serve tables for tenant onboarding, plan upgrades, and webhooks."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '009_self_serve_tables'
down_revision = '008_privacy_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Add self-serve tables."""
    
    # Plan configurations table
    op.create_table(
        'plan_configurations',
        sa.Column('plan_name', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price_monthly', sa.Numeric(10, 2), nullable=False),
        sa.Column('price_yearly', sa.Numeric(10, 2), nullable=False),
        sa.Column('features', postgresql.JSONB(), nullable=False),
        sa.Column('limits', postgresql.JSONB(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('plan_name')
    )
    
    # Webhook endpoints table
    op.create_table(
        'webhook_endpoints',
        sa.Column('endpoint_id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('url', sa.String(), nullable=False),
        sa.Column('events', postgresql.JSONB(), nullable=False),
        sa.Column('secret', sa.String(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint('endpoint_id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE')
    )
    
    # Webhook deliveries table
    op.create_table(
        'webhook_deliveries',
        sa.Column('delivery_id', sa.String(), nullable=False),
        sa.Column('endpoint_id', sa.String(), nullable=False),
        sa.Column('event', sa.String(), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, default=0),
        sa.Column('max_attempts', sa.Integer(), nullable=False, default=3),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('response_status', sa.Integer(), nullable=True),
        sa.Column('response_body', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('delivery_id'),
        sa.ForeignKeyConstraint(['endpoint_id'], ['webhook_endpoints.endpoint_id'], ondelete='CASCADE')
    )
    
    # Tenant onboarding tracking table
    op.create_table(
        'tenant_onboarding_tracking',
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('step', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint('tenant_id', 'step'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE')
    )
    
    # Plan upgrade history table
    op.create_table(
        'plan_upgrade_history',
        sa.Column('upgrade_id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('old_plan', sa.String(), nullable=False),
        sa.Column('new_plan', sa.String(), nullable=False),
        sa.Column('billing_cycle', sa.String(), nullable=False),
        sa.Column('upgrade_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('next_billing_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('cost', postgresql.JSONB(), nullable=False),
        sa.Column('payment_method_id', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('upgrade_id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE')
    )
    
    # Admin users table
    op.create_table(
        'admin_users',
        sa.Column('admin_id', sa.String(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('permissions', postgresql.JSONB(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('admin_id'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('email')
    )
    
    # Create indexes
    op.create_index('idx_webhook_endpoints_tenant_id', 'webhook_endpoints', ['tenant_id'])
    op.create_index('idx_webhook_deliveries_endpoint_id', 'webhook_deliveries', ['endpoint_id'])
    op.create_index('idx_webhook_deliveries_status', 'webhook_deliveries', ['status'])
    op.create_index('idx_webhook_deliveries_next_retry_at', 'webhook_deliveries', ['next_retry_at'])
    op.create_index('idx_tenant_onboarding_tenant_id', 'tenant_onboarding_tracking', ['tenant_id'])
    op.create_index('idx_tenant_onboarding_step', 'tenant_onboarding_tracking', ['step'])
    op.create_index('idx_plan_upgrade_tenant_id', 'plan_upgrade_history', ['tenant_id'])
    op.create_index('idx_plan_upgrade_date', 'plan_upgrade_history', ['upgrade_date'])
    op.create_index('idx_admin_users_username', 'admin_users', ['username'])
    op.create_index('idx_admin_users_email', 'admin_users', ['email'])
    
    # Insert default plan configurations
    op.execute("""
        INSERT INTO plan_configurations (
            plan_name, display_name, description, price_monthly, price_yearly,
            features, limits, enabled, created_at, updated_at
        ) VALUES 
        (
            'trial',
            'Trial',
            'Free trial with limited features',
            0.00,
            0.00,
            '["Basic AI features", "1 user", "1GB storage", "100 API calls/day"]',
            '{"users": 1, "storage_gb": 1, "api_calls_per_day": 100, "concurrent_requests": 5}',
            true,
            NOW(),
            NOW()
        ),
        (
            'basic',
            'Basic',
            'Essential features for small teams',
            29.00,
            290.00,
            '["All AI features", "5 users", "10GB storage", "1000 API calls/day", "Email support"]',
            '{"users": 5, "storage_gb": 10, "api_calls_per_day": 1000, "concurrent_requests": 10}',
            true,
            NOW(),
            NOW()
        ),
        (
            'pro',
            'Professional',
            'Advanced features for growing teams',
            99.00,
            990.00,
            '["All AI features", "25 users", "100GB storage", "10000 API calls/day", "Priority support", "Custom integrations"]',
            '{"users": 25, "storage_gb": 100, "api_calls_per_day": 10000, "concurrent_requests": 50}',
            true,
            NOW(),
            NOW()
        ),
        (
            'enterprise',
            'Enterprise',
            'Full-featured solution for large organizations',
            299.00,
            2990.00,
            '["All AI features", "Unlimited users", "1TB storage", "Unlimited API calls", "24/7 support", "Custom integrations", "SLA", "Dedicated support"]',
            '{"users": -1, "storage_gb": 1000, "api_calls_per_day": -1, "concurrent_requests": -1}',
            true,
            NOW(),
            NOW()
        );
    """)


def downgrade():
    """Remove self-serve tables."""
    
    # Drop indexes
    op.drop_index('idx_admin_users_email', 'admin_users')
    op.drop_index('idx_admin_users_username', 'admin_users')
    op.drop_index('idx_plan_upgrade_date', 'plan_upgrade_history')
    op.drop_index('idx_plan_upgrade_tenant_id', 'plan_upgrade_history')
    op.drop_index('idx_tenant_onboarding_step', 'tenant_onboarding_tracking')
    op.drop_index('idx_tenant_onboarding_tenant_id', 'tenant_onboarding_tracking')
    op.drop_index('idx_webhook_deliveries_next_retry_at', 'webhook_deliveries')
    op.drop_index('idx_webhook_deliveries_status', 'webhook_deliveries')
    op.drop_index('idx_webhook_deliveries_endpoint_id', 'webhook_deliveries')
    op.drop_index('idx_webhook_endpoints_tenant_id', 'webhook_endpoints')
    
    # Drop tables
    op.drop_table('admin_users')
    op.drop_table('plan_upgrade_history')
    op.drop_table('tenant_onboarding_tracking')
    op.drop_table('webhook_deliveries')
    op.drop_table('webhook_endpoints')
    op.drop_table('plan_configurations')

