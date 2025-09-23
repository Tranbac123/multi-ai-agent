"""Create budget and drift detection tables."""

from alembic import op
import sqlalchemy as sa

revision = '007_budget_tables'
down_revision = '006_regional_schema'
branch_labels = None
depends_on = None


def upgrade():
    """Create budget and drift detection tables."""
    
    # Create tenant_budgets table
    op.create_table('tenant_budgets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('period', sa.String(), nullable=False),  # daily, weekly, monthly, yearly
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, default='USD'),
        sa.Column('warning_threshold', sa.Float(), nullable=False, default=75.0),
        sa.Column('critical_threshold', sa.Float(), nullable=False, default=90.0),
        sa.Column('auto_renew', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'period', name='unique_tenant_period')
    )
    
    # Create billing_events table for usage tracking
    op.create_table('billing_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('request_id', sa.String(), nullable=False),
        sa.Column('service_type', sa.String(), nullable=False),
        sa.Column('cost_usd', sa.Numeric(10, 6), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_billing_events_tenant_created', 'tenant_id', 'created_at'),
        sa.Index('idx_billing_events_service_type', 'service_type')
    )
    
    # Create request_metrics table for drift analysis
    op.create_table('request_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('request_id', sa.String(), nullable=False),
        sa.Column('service_type', sa.String(), nullable=False),
        sa.Column('tier', sa.String(), nullable=False),
        sa.Column('cost_usd', sa.Numeric(10, 6), nullable=False),
        sa.Column('latency_ms', sa.Float(), nullable=False),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_request_metrics_tenant_service', 'tenant_id', 'service_type'),
        sa.Index('idx_request_metrics_created', 'created_at')
    )
    
    # Create drift_analysis_summaries table
    op.create_table('drift_analysis_summaries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('analysis_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('total_tenants', sa.Integer(), nullable=False),
        sa.Column('tenants_with_drift', sa.Integer(), nullable=False),
        sa.Column('budget_alerts', sa.Integer(), nullable=False),
        sa.Column('safe_mode_recommendations', sa.Integer(), nullable=False),
        sa.Column('total_potential_savings', sa.Numeric(10, 2), nullable=False),
        sa.Column('errors', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_drift_analysis_date', 'analysis_date')
    )
    
    # Create budget_alerts table
    op.create_table('budget_alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('period', sa.String(), nullable=False),
        sa.Column('usage_percent', sa.Float(), nullable=False),
        sa.Column('alert_type', sa.String(), nullable=False),  # warning, critical, exceeded
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('acknowledged', sa.Boolean(), nullable=False, default=False),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_budget_alerts_tenant', 'tenant_id'),
        sa.Index('idx_budget_alerts_created', 'created_at')
    )
    
    # Create cost_optimization_events table
    op.create_table('cost_optimization_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('request_id', sa.String(), nullable=False),
        sa.Column('original_tier', sa.String(), nullable=True),
        sa.Column('optimized_tier', sa.String(), nullable=False),
        sa.Column('original_cost', sa.Numeric(10, 6), nullable=True),
        sa.Column('optimized_cost', sa.Numeric(10, 6), nullable=False),
        sa.Column('cost_savings', sa.Numeric(10, 6), nullable=False),
        sa.Column('safe_mode_level', sa.String(), nullable=False),
        sa.Column('reasoning', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_cost_optimization_tenant', 'tenant_id'),
        sa.Index('idx_cost_optimization_created', 'created_at')
    )


def downgrade():
    """Drop budget and drift detection tables."""
    op.drop_table('cost_optimization_events')
    op.drop_table('budget_alerts')
    op.drop_table('drift_analysis_summaries')
    op.drop_table('request_metrics')
    op.drop_table('billing_events')
    op.drop_table('tenant_budgets')

