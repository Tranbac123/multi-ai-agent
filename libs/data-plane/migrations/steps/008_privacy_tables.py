"""Create privacy and DLP related tables."""

from alembic import op
import sqlalchemy as sa

revision = '008_privacy_tables'
down_revision = '007_budget_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Create privacy and DLP related tables."""
    
    # Create sensitivity_tags table
    op.create_table('sensitivity_tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('sensitivity_level', sa.String(), nullable=False),
        sa.Column('data_categories', sa.ARRAY(sa.String()), nullable=False),
        sa.Column('pii_detected', sa.Boolean(), nullable=False, default=False),
        sa.Column('pii_types', sa.ARRAY(sa.String()), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('tagged_by', sa.String(), nullable=False),
        sa.Column('tagged_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id', name='unique_document_tag'),
        sa.Index('idx_sensitivity_tags_tenant', 'tenant_id'),
        sa.Index('idx_sensitivity_tags_level', 'sensitivity_level'),
        sa.Index('idx_sensitivity_tags_pii', 'pii_detected')
    )
    
    # Create encryption_keys table
    op.create_table('encryption_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key_id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('field_name', sa.String(), nullable=True),
        sa.Column('algorithm', sa.String(), nullable=False),
        sa.Column('key_version', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('rotated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_id', name='unique_key_id'),
        sa.Index('idx_encryption_keys_tenant', 'tenant_id'),
        sa.Index('idx_encryption_keys_status', 'status')
    )
    
    # Create encrypted_fields table
    op.create_table('encrypted_fields',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('field_name', sa.String(), nullable=False),
        sa.Column('encrypted_data', sa.Text(), nullable=False),
        sa.Column('key_id', sa.String(), nullable=False),
        sa.Column('algorithm', sa.String(), nullable=False),
        sa.Column('key_version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_encrypted_fields_tenant', 'tenant_id'),
        sa.Index('idx_encrypted_fields_key', 'key_id')
    )
    
    # Create privacy_policies table
    op.create_table('privacy_policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('policy_id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=True),  # NULL for global policies
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('rules', sa.JSON(), nullable=False),
        sa.Column('sensitivity_level', sa.String(), nullable=False),
        sa.Column('data_categories', sa.ARRAY(sa.String()), nullable=False),
        sa.Column('auto_tag', sa.Boolean(), nullable=False, default=True),
        sa.Column('requires_approval', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('policy_id', name='unique_policy_id'),
        sa.Index('idx_privacy_policies_tenant', 'tenant_id'),
        sa.Index('idx_privacy_policies_active', 'is_active')
    )
    
    # Create pii_detections table
    op.create_table('pii_detections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('detection_id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('document_id', sa.String(), nullable=True),
        sa.Column('request_id', sa.String(), nullable=True),
        sa.Column('pii_type', sa.String(), nullable=False),
        sa.Column('detected_value', sa.String(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('sensitivity_level', sa.String(), nullable=False),
        sa.Column('start_position', sa.Integer(), nullable=False),
        sa.Column('end_position', sa.Integer(), nullable=False),
        sa.Column('context', sa.Text(), nullable=True),
        sa.Column('redaction_mask', sa.String(), nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('redacted', sa.Boolean(), nullable=False, default=False),
        sa.Column('redacted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('detection_id', name='unique_detection_id'),
        sa.Index('idx_pii_detections_tenant', 'tenant_id'),
        sa.Column('idx_pii_detections_type', 'pii_type'),
        sa.Index('idx_pii_detections_detected', 'detected_at')
    )
    
    # Create privacy_violations table
    op.create_table('privacy_violations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('violation_id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('request_id', sa.String(), nullable=True),
        sa.Column('violation_type', sa.String(), nullable=False),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('detected_data', sa.JSON(), nullable=True),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('acknowledged', sa.Boolean(), nullable=False, default=False),
        sa.Column('acknowledged_by', sa.String(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=False, default=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('violation_id', name='unique_violation_id'),
        sa.Index('idx_privacy_violations_tenant', 'tenant_id'),
        sa.Index('idx_privacy_violations_severity', 'severity'),
        sa.Index('idx_privacy_violations_detected', 'detected_at')
    )
    
    # Create data_access_logs table
    op.create_table('data_access_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('access_id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=False),
        sa.Column('resource_id', sa.String(), nullable=False),
        sa.Column('access_type', sa.String(), nullable=False),  # read, write, delete
        sa.Column('sensitivity_level', sa.String(), nullable=True),
        sa.Column('data_categories', sa.ARRAY(sa.String()), nullable=True),
        sa.Column('pii_accessed', sa.Boolean(), nullable=False, default=False),
        sa.Column('pii_types', sa.ARRAY(sa.String()), nullable=True),
        sa.Column('access_granted', sa.Boolean(), nullable=False),
        sa.Column('access_reason', sa.String(), nullable=True),
        sa.Column('accessed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.String(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('access_id', name='unique_access_id'),
        sa.Index('idx_data_access_logs_tenant', 'tenant_id'),
        sa.Index('idx_data_access_logs_user', 'user_id'),
        sa.Index('idx_data_access_logs_accessed', 'accessed_at'),
        sa.Index('idx_data_access_logs_pii', 'pii_accessed')
    )
    
    # Create key_rotation_logs table
    op.create_table('key_rotation_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rotation_id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('key_id', sa.String(), nullable=False),
        sa.Column('field_name', sa.String(), nullable=True),
        sa.Column('old_key_version', sa.Integer(), nullable=True),
        sa.Column('new_key_version', sa.Integer(), nullable=False),
        sa.Column('rotation_type', sa.String(), nullable=False),  # manual, scheduled, emergency
        sa.Column('rotation_reason', sa.String(), nullable=True),
        sa.Column('rotated_by', sa.String(), nullable=False),
        sa.Column('rotated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reencryption_completed', sa.Boolean(), nullable=False, default=False),
        sa.Column('reencryption_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('rotation_id', name='unique_rotation_id'),
        sa.Index('idx_key_rotation_logs_tenant', 'tenant_id'),
        sa.Index('idx_key_rotation_logs_key', 'key_id'),
        sa.Index('idx_key_rotation_logs_rotated', 'rotated_at')
    )


def downgrade():
    """Drop privacy and DLP related tables."""
    op.drop_table('key_rotation_logs')
    op.drop_table('data_access_logs')
    op.drop_table('privacy_violations')
    op.drop_table('pii_detections')
    op.drop_table('privacy_policies')
    op.drop_table('encrypted_fields')
    op.drop_table('encryption_keys')
    op.drop_table('sensitivity_tags')

