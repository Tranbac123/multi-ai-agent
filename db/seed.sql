-- Seed data for local development
-- This script creates sample data for testing and development

-- Insert sample tenant
INSERT INTO tenants (id, name, slug, status, settings) VALUES
('550e8400-e29b-41d4-a716-446655440000', 'Acme Corp', 'acme-corp', 'active', '{"plan": "enterprise", "features": ["ai_chat", "document_ingestion", "analytics"]}'),
('660e8400-e29b-41d4-a716-446655440001', 'TechStart Inc', 'techstart', 'trial', '{"plan": "trial", "features": ["ai_chat"]}');

-- Insert sample users
INSERT INTO users (id, tenant_id, email, first_name, last_name, status, metadata) VALUES
('770e8400-e29b-41d4-a716-446655440002', '550e8400-e29b-41d4-a716-446655440000', 'admin@acme.com', 'John', 'Doe', 'active', '{"role": "admin", "department": "IT"}'),
('880e8400-e29b-41d4-a716-446655440003', '550e8400-e29b-41d4-a716-446655440000', 'user@acme.com', 'Jane', 'Smith', 'active', '{"role": "user", "department": "Sales"}'),
('990e8400-e29b-41d4-a716-446655440004', '660e8400-e29b-41d4-a716-446655440001', 'founder@techstart.com', 'Bob', 'Johnson', 'active', '{"role": "admin", "department": "Founder"}');

-- Insert sample API keys
INSERT INTO api_keys (id, tenant_id, user_id, name, key_hash, key_prefix, permissions) VALUES
('aa0e8400-e29b-41d4-a716-446655440005', '550e8400-e29b-41d4-a716-446655440000', '770e8400-e29b-41d4-a716-446655440002', 'Admin API Key', 'hashed_key_1', 'ak_acme_', '{"permissions": ["read", "write", "admin"]}'),
('bb0e8400-e29b-41d4-a716-446655440006', '550e8400-e29b-41d4-a716-446655440000', '880e8400-e29b-41d4-a716-446655440003', 'User API Key', 'hashed_key_2', 'ak_user_', '{"permissions": ["read", "write"]}'),
('cc0e8400-e29b-41d4-a716-446655440007', '660e8400-e29b-41d4-a716-446655440001', '990e8400-e29b-41d4-a716-446655440004', 'Founder API Key', 'hashed_key_3', 'ak_tech_', '{"permissions": ["read", "write", "admin"]}');

-- Insert sample documents
INSERT INTO documents (id, tenant_id, user_id, title, content, status, metadata) VALUES
('dd0e8400-e29b-41d4-a716-446655440008', '550e8400-e29b-41d4-a716-446655440000', '770e8400-e29b-41d4-a716-446655440002', 'Company Handbook', 'This is the company handbook content...', 'processed', '{"category": "hr", "version": "1.0"}'),
('ee0e8400-e29b-41d4-a716-446655440009', '550e8400-e29b-41d4-a716-446655440000', '880e8400-e29b-41d4-a716-446655440003', 'Sales Guide', 'This is the sales guide content...', 'processed', '{"category": "sales", "version": "2.1"}'),
('ff0e8400-e29b-41d4-a716-446655440010', '660e8400-e29b-41d4-a716-446655440001', '990e8400-e29b-41d4-a716-446655440004', 'Product Spec', 'This is the product specification...', 'pending', '{"category": "product", "version": "1.0"}');

-- Insert sample workflows
INSERT INTO workflows (id, tenant_id, user_id, name, description, definition, status) VALUES
('110e8400-e29b-41d4-a716-446655440011', '550e8400-e29b-41d4-a716-446655440000', '770e8400-e29b-41d4-a716-446655440002', 'Document Processing', 'Process uploaded documents', '{"steps": [{"name": "validate", "service": "ingestion-service"}, {"name": "extract", "service": "ingestion-service"}, {"name": "index", "service": "retrieval-service"}]}', 'active'),
('220e8400-e29b-41d4-a716-446655440012', '660e8400-e29b-41d4-a716-446655440001', '990e8400-e29b-41d4-a716-446655440004', 'AI Chat Workflow', 'Handle AI chat requests', '{"steps": [{"name": "route", "service": "router-service"}, {"name": "infer", "service": "model-gateway"}, {"name": "respond", "service": "realtime-gateway"}]}', 'active');

-- Insert sample configurations
INSERT INTO configurations (id, tenant_id, key, value, description) VALUES
('330e8400-e29b-41d4-a716-446655440013', '550e8400-e29b-41d4-a716-446655440000', 'max_documents_per_user', '{"value": 1000}', 'Maximum documents per user'),
('440e8400-e29b-41d4-a716-446655440014', '550e8400-e29b-41d4-a716-446655440000', 'ai_model_preference', '{"value": "gpt-4"}', 'Preferred AI model'),
('550e8400-e29b-41d4-a716-446655440015', '660e8400-e29b-41d4-a716-446655440001', 'max_documents_per_user', '{"value": 100}', 'Maximum documents per user (trial)'),
('660e8400-e29b-41d4-a716-446655440016', '660e8400-e29b-41d4-a716-446655440001', 'ai_model_preference', '{"value": "gpt-3.5-turbo"}', 'Preferred AI model (trial)');

-- Insert sample feature flags
INSERT INTO feature_flags (id, tenant_id, name, is_enabled, rollout_percentage, conditions) VALUES
('770e8400-e29b-41d4-a716-446655440017', '550e8400-e29b-41d4-a716-446655440000', 'advanced_analytics', true, 100, '{}'),
('880e8400-e29b-41d4-a716-446655440018', '550e8400-e29b-41d4-a716-446655440000', 'beta_features', false, 0, '{}'),
('990e8400-e29b-41d4-a716-446655440019', '660e8400-e29b-41d4-a716-446655440001', 'advanced_analytics', false, 0, '{}'),
('aa0e8400-e29b-41d4-a716-446655440020', '660e8400-e29b-41d4-a716-446655440001', 'beta_features', false, 0, '{}');

-- Insert sample usage events
INSERT INTO usage_events (id, event_id, tenant_id, user_id, service_name, event_type, resource_type, quantity, unit, cost_amount, cost_currency, cost_rate, timestamp, metadata) VALUES
('bb0e8400-e29b-41d4-a716-446655440021', 'cc0e8400-e29b-41d4-a716-446655440022', '550e8400-e29b-41d4-a716-446655440000', '770e8400-e29b-41d4-a716-446655440002', 'model-gateway', 'model_inference', 'tokens', 150, 'tokens', 0.0003, 'USD', 0.000002, NOW() - INTERVAL '1 hour', '{"model": "gpt-4", "response_time_ms": 1250}'),
('dd0e8400-e29b-41d4-a716-446655440023', 'ee0e8400-e29b-41d4-a716-446655440024', '550e8400-e29b-41d4-a716-446655440000', '880e8400-e29b-41d4-a716-446655440003', 'ingestion-service', 'document_ingestion', 'documents', 1, 'documents', 0.01, 'USD', 0.01, NOW() - INTERVAL '2 hours', '{"file_size": 1024000, "processing_time_ms": 5000}'),
('ff0e8400-e29b-41d4-a716-446655440025', '110e8400-e29b-41d4-a716-446655440026', '660e8400-e29b-41d4-a716-446655440001', '990e8400-e29b-41d4-a716-446655440004', 'model-gateway', 'model_inference', 'tokens', 75, 'tokens', 0.00015, 'USD', 0.000002, NOW() - INTERVAL '30 minutes', '{"model": "gpt-3.5-turbo", "response_time_ms": 800}');

-- Insert sample audit logs
INSERT INTO audit_logs (id, tenant_id, user_id, service_name, action, resource_type, resource_id, old_values, new_values, metadata) VALUES
('220e8400-e29b-41d4-a716-446655440027', '550e8400-e29b-41d4-a716-446655440000', '770e8400-e29b-41d4-a716-446655440002', 'api-gateway', 'user_login', 'user', '770e8400-e29b-41d4-a716-446655440002', NULL, '{"login_method": "api_key"}', '{"ip_address": "192.168.1.100"}'),
('330e8400-e29b-41d4-a716-446655440028', '550e8400-e29b-41d4-a716-446655440000', '880e8400-e29b-41d4-a716-446655440003', 'ingestion-service', 'document_upload', 'document', 'ee0e8400-e29b-41d4-a716-446655440009', NULL, '{"title": "Sales Guide", "size": 2048000}', '{"ip_address": "192.168.1.101"}'),
('440e8400-e29b-41d4-a716-446655440029', '660e8400-e29b-41d4-a716-446655440001', '990e8400-e29b-41d4-a716-446655440004', 'config-service', 'configuration_update', 'configuration', '660e8400-e29b-41d4-a716-446655440016', '{"value": "gpt-3.5-turbo"}', '{"value": "gpt-4"}', '{"ip_address": "192.168.1.102"}');

-- Create a function to set tenant context for RLS
CREATE OR REPLACE FUNCTION set_tenant_context(tenant_uuid UUID)
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', tenant_uuid::text, true);
END;
$$ LANGUAGE plpgsql;

-- Grant necessary permissions
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;

-- Create a view for tenant usage summary
CREATE VIEW tenant_usage_summary AS
SELECT 
    t.id as tenant_id,
    t.name as tenant_name,
    COUNT(DISTINCT ue.user_id) as active_users,
    COUNT(ue.id) as total_events,
    SUM(ue.cost_amount) as total_cost,
    DATE_TRUNC('day', ue.timestamp) as usage_date
FROM tenants t
LEFT JOIN usage_events ue ON t.id = ue.tenant_id
GROUP BY t.id, t.name, DATE_TRUNC('day', ue.timestamp)
ORDER BY usage_date DESC;

-- Grant access to the view
GRANT SELECT ON tenant_usage_summary TO authenticated;
