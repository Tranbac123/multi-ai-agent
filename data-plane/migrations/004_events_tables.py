"""Create event-related tables for Events & DLQ system."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade():
    """Create event-related tables."""
    
    # Agent runs table
    op.create_table(
        'agent_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('agent_id', sa.String(100), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=True),
        sa.Column('session_id', sa.String(100), nullable=True),
        sa.Column('input_text', sa.Text, nullable=False),
        sa.Column('output_text', sa.Text, nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('start_time', sa.Float, nullable=False),
        sa.Column('end_time', sa.Float, nullable=True),
        sa.Column('duration_ms', sa.Integer, nullable=True),
        sa.Column('tokens_used', sa.Integer, nullable=True),
        sa.Column('cost_usd', sa.Float, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=False, default={}),
        sa.Column('created_at', sa.Timestamp, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.Timestamp, nullable=True, onupdate=sa.func.now()),
        sa.Index('idx_agent_runs_tenant_id', 'tenant_id'),
        sa.Index('idx_agent_runs_agent_id', 'agent_id'),
        sa.Index('idx_agent_runs_user_id', 'user_id'),
        sa.Index('idx_agent_runs_session_id', 'session_id'),
        sa.Index('idx_agent_runs_status', 'status'),
        sa.Index('idx_agent_runs_start_time', 'start_time'),
    )
    
    # Tool calls table
    op.create_table(
        'tool_calls',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('run_id', sa.String(36), nullable=False),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('tool_name', sa.String(100), nullable=False),
        sa.Column('tool_input', postgresql.JSONB, nullable=False),
        sa.Column('tool_output', postgresql.JSONB, nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('start_time', sa.Float, nullable=False),
        sa.Column('end_time', sa.Float, nullable=True),
        sa.Column('duration_ms', sa.Integer, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=False, default={}),
        sa.Column('created_at', sa.Timestamp, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.Timestamp, nullable=True, onupdate=sa.func.now()),
        sa.Index('idx_tool_calls_run_id', 'run_id'),
        sa.Index('idx_tool_calls_tenant_id', 'tenant_id'),
        sa.Index('idx_tool_calls_tool_name', 'tool_name'),
        sa.Index('idx_tool_calls_status', 'status'),
        sa.Index('idx_tool_calls_start_time', 'start_time'),
    )
    
    # Document ingestions table
    op.create_table(
        'document_ingestions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('content_type', sa.String(100), nullable=False),
        sa.Column('file_size', sa.Integer, nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('start_time', sa.Float, nullable=False),
        sa.Column('end_time', sa.Float, nullable=True),
        sa.Column('duration_ms', sa.Integer, nullable=True),
        sa.Column('chunks_created', sa.Integer, nullable=True),
        sa.Column('embeddings_generated', sa.Integer, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=False, default={}),
        sa.Column('created_at', sa.Timestamp, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.Timestamp, nullable=True, onupdate=sa.func.now()),
        sa.Index('idx_document_ingestions_tenant_id', 'tenant_id'),
        sa.Index('idx_document_ingestions_user_id', 'user_id'),
        sa.Index('idx_document_ingestions_content_type', 'content_type'),
        sa.Index('idx_document_ingestions_status', 'status'),
        sa.Index('idx_document_ingestions_start_time', 'start_time'),
    )
    
    # Usage metered table
    op.create_table(
        'usage_metered',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=True),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', sa.String(100), nullable=False),
        sa.Column('quantity', sa.Integer, nullable=False),
        sa.Column('unit', sa.String(20), nullable=False),
        sa.Column('timestamp', sa.Float, nullable=False),
        sa.Column('cost_usd', sa.Float, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=False, default={}),
        sa.Column('created_at', sa.Timestamp, nullable=False, server_default=sa.func.now()),
        sa.Index('idx_usage_metered_tenant_id', 'tenant_id'),
        sa.Index('idx_usage_metered_user_id', 'user_id'),
        sa.Index('idx_usage_metered_resource_type', 'resource_type'),
        sa.Index('idx_usage_metered_timestamp', 'timestamp'),
    )
    
    # Router decisions table
    op.create_table(
        'router_decisions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=True),
        sa.Column('input_text', sa.Text, nullable=False),
        sa.Column('selected_agent', sa.String(100), nullable=False),
        sa.Column('confidence', sa.Float, nullable=False),
        sa.Column('reasoning', sa.Text, nullable=False),
        sa.Column('features', postgresql.JSONB, nullable=False, default={}),
        sa.Column('timestamp', sa.Float, nullable=False),
        sa.Column('metadata', postgresql.JSONB, nullable=False, default={}),
        sa.Column('created_at', sa.Timestamp, nullable=False, server_default=sa.func.now()),
        sa.Index('idx_router_decisions_tenant_id', 'tenant_id'),
        sa.Index('idx_router_decisions_user_id', 'user_id'),
        sa.Index('idx_router_decisions_selected_agent', 'selected_agent'),
        sa.Index('idx_router_decisions_timestamp', 'timestamp'),
    )
    
    # WebSocket messages table
    op.create_table(
        'websocket_messages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=True),
        sa.Column('session_id', sa.String(100), nullable=False),
        sa.Column('message_type', sa.String(20), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('timestamp', sa.Float, nullable=False),
        sa.Column('metadata', postgresql.JSONB, nullable=False, default={}),
        sa.Column('created_at', sa.Timestamp, nullable=False, server_default=sa.func.now()),
        sa.Index('idx_websocket_messages_tenant_id', 'tenant_id'),
        sa.Index('idx_websocket_messages_user_id', 'user_id'),
        sa.Index('idx_websocket_messages_session_id', 'session_id'),
        sa.Index('idx_websocket_messages_message_type', 'message_type'),
        sa.Index('idx_websocket_messages_timestamp', 'timestamp'),
    )
    
    # Billing events table
    op.create_table(
        'billing_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('amount_usd', sa.Float, nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, default='USD'),
        sa.Column('timestamp', sa.Float, nullable=False),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('metadata', postgresql.JSONB, nullable=False, default={}),
        sa.Column('created_at', sa.Timestamp, nullable=False, server_default=sa.func.now()),
        sa.Index('idx_billing_events_tenant_id', 'tenant_id'),
        sa.Index('idx_billing_events_event_type', 'event_type'),
        sa.Index('idx_billing_events_timestamp', 'timestamp'),
    )
    
    # Permanent failures table
    op.create_table(
        'permanent_failures',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('original_subject', sa.String(255), nullable=False),
        sa.Column('original_data', sa.Text, nullable=False),
        sa.Column('original_headers', postgresql.JSONB, nullable=False, default={}),
        sa.Column('error', sa.Text, nullable=False),
        sa.Column('failed_at', sa.Float, nullable=False),
        sa.Column('retry_count', sa.Integer, nullable=False),
        sa.Column('created_at', sa.Float, nullable=False),
        sa.Index('idx_permanent_failures_tenant_id', 'tenant_id'),
        sa.Index('idx_permanent_failures_event_type', 'event_type'),
        sa.Index('idx_permanent_failures_failed_at', 'failed_at'),
        sa.Index('idx_permanent_failures_created_at', 'created_at'),
    )
    
    # DLQ processing errors table
    op.create_table(
        'dlq_processing_errors',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('dlq_data', postgresql.JSONB, nullable=False, default={}),
        sa.Column('error', sa.Text, nullable=False),
        sa.Column('created_at', sa.Float, nullable=False),
        sa.Index('idx_dlq_processing_errors_tenant_id', 'tenant_id'),
        sa.Index('idx_dlq_processing_errors_created_at', 'created_at'),
    )
    
    # Enable RLS on all tables
    op.execute("ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tool_calls ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE document_ingestions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE usage_metered ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE router_decisions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE websocket_messages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE billing_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE permanent_failures ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE dlq_processing_errors ENABLE ROW LEVEL SECURITY")
    
    # Create RLS policies for tenant isolation
    op.execute("""
        CREATE POLICY tenant_isolation_agent_runs ON agent_runs
        FOR ALL TO authenticated
        USING (tenant_id = current_setting('app.tenant_id'))
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_tool_calls ON tool_calls
        FOR ALL TO authenticated
        USING (tenant_id = current_setting('app.tenant_id'))
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_document_ingestions ON document_ingestions
        FOR ALL TO authenticated
        USING (tenant_id = current_setting('app.tenant_id'))
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_usage_metered ON usage_metered
        FOR ALL TO authenticated
        USING (tenant_id = current_setting('app.tenant_id'))
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_router_decisions ON router_decisions
        FOR ALL TO authenticated
        USING (tenant_id = current_setting('app.tenant_id'))
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_websocket_messages ON websocket_messages
        FOR ALL TO authenticated
        USING (tenant_id = current_setting('app.tenant_id'))
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_billing_events ON billing_events
        FOR ALL TO authenticated
        USING (tenant_id = current_setting('app.tenant_id'))
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_permanent_failures ON permanent_failures
        FOR ALL TO authenticated
        USING (tenant_id = current_setting('app.tenant_id'))
    """)
    
    op.execute("""
        CREATE POLICY tenant_isolation_dlq_processing_errors ON dlq_processing_errors
        FOR ALL TO authenticated
        USING (tenant_id = current_setting('app.tenant_id'))
    """)


def downgrade():
    """Drop event-related tables."""
    
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS tenant_isolation_agent_runs ON agent_runs")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_tool_calls ON tool_calls")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_document_ingestions ON document_ingestions")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_usage_metered ON usage_metered")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_router_decisions ON router_decisions")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_websocket_messages ON websocket_messages")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_billing_events ON billing_events")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_permanent_failures ON permanent_failures")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_dlq_processing_errors ON dlq_processing_errors")
    
    # Drop tables
    op.drop_table('dlq_processing_errors')
    op.drop_table('permanent_failures')
    op.drop_table('billing_events')
    op.drop_table('websocket_messages')
    op.drop_table('router_decisions')
    op.drop_table('usage_metered')
    op.drop_table('document_ingestions')
    op.drop_table('tool_calls')
    op.drop_table('agent_runs')
