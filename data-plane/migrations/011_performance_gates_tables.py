"""
Migration: Performance Gates Tables

Creates tables for performance baselines, metrics, alerts, cost ceilings,
cost records, and optimization recommendations.
"""

from sqlalchemy import text

# Migration version
VERSION = "011"


async def upgrade(db_session):
    """Upgrade database schema."""
    
    # Performance baselines table
    await db_session.execute(text("""
        CREATE TABLE performance_baselines (
            id SERIAL PRIMARY KEY,
            baseline_id VARCHAR(255) UNIQUE NOT NULL,
            name VARCHAR(500) NOT NULL,
            description TEXT NOT NULL,
            baseline_type VARCHAR(100) NOT NULL,
            service VARCHAR(100) NOT NULL,
            endpoint VARCHAR(500),
            tenant_id VARCHAR(255),
            aggregation_method VARCHAR(50) NOT NULL,
            window_size_hours INTEGER DEFAULT 24,
            sample_size INTEGER DEFAULT 1000,
            threshold_percentage FLOAT DEFAULT 10.0,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            metadata JSONB DEFAULT '{}'
        )
    """))
    
    # Performance metrics table
    await db_session.execute(text("""
        CREATE TABLE performance_metrics (
            id SERIAL PRIMARY KEY,
            metric_id VARCHAR(255) UNIQUE NOT NULL,
            baseline_id VARCHAR(255) NOT NULL REFERENCES performance_baselines(baseline_id),
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
            value FLOAT NOT NULL,
            unit VARCHAR(50) NOT NULL,
            tags JSONB DEFAULT '{}',
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """))
    
    # Baseline calculations table
    await db_session.execute(text("""
        CREATE TABLE baseline_calculations (
            id SERIAL PRIMARY KEY,
            baseline_id VARCHAR(255) NOT NULL REFERENCES performance_baselines(baseline_id),
            calculated_value FLOAT NOT NULL,
            baseline_value FLOAT NOT NULL,
            calculated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """))
    
    # Performance alerts table
    await db_session.execute(text("""
        CREATE TABLE performance_alerts (
            id SERIAL PRIMARY KEY,
            alert_id VARCHAR(255) UNIQUE NOT NULL,
            baseline_id VARCHAR(255) NOT NULL REFERENCES performance_baselines(baseline_id),
            alert_type VARCHAR(100) NOT NULL,
            severity VARCHAR(50) NOT NULL,
            regression_percentage FLOAT NOT NULL,
            current_value FLOAT NOT NULL,
            baseline_value FLOAT NOT NULL,
            threshold_percentage FLOAT NOT NULL,
            triggered_at TIMESTAMP WITH TIME ZONE NOT NULL,
            resolved_at TIMESTAMP WITH TIME ZONE,
            is_resolved BOOLEAN DEFAULT false,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """))
    
    # Cost ceilings table
    await db_session.execute(text("""
        CREATE TABLE cost_ceilings (
            id SERIAL PRIMARY KEY,
            ceiling_id VARCHAR(255) UNIQUE NOT NULL,
            name VARCHAR(500) NOT NULL,
            description TEXT NOT NULL,
            ceiling_type VARCHAR(100) NOT NULL,
            cost_type VARCHAR(100) NOT NULL,
            limit_amount DECIMAL(15,4) NOT NULL,
            currency VARCHAR(10) DEFAULT 'USD',
            tenant_id VARCHAR(255),
            service VARCHAR(100),
            is_active BOOLEAN DEFAULT true,
            alert_thresholds JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            metadata JSONB DEFAULT '{}'
        )
    """))
    
    # Cost records table
    await db_session.execute(text("""
        CREATE TABLE cost_records (
            id SERIAL PRIMARY KEY,
            record_id VARCHAR(255) UNIQUE NOT NULL,
            ceiling_id VARCHAR(255) NOT NULL REFERENCES cost_ceilings(ceiling_id),
            tenant_id VARCHAR(255) NOT NULL,
            service VARCHAR(100) NOT NULL,
            cost_type VARCHAR(100) NOT NULL,
            amount DECIMAL(15,4) NOT NULL,
            currency VARCHAR(10) DEFAULT 'USD',
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
            request_id VARCHAR(255),
            operation VARCHAR(100),
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """))
    
    # Cost alerts table
    await db_session.execute(text("""
        CREATE TABLE cost_alerts (
            id SERIAL PRIMARY KEY,
            alert_id VARCHAR(255) UNIQUE NOT NULL,
            ceiling_id VARCHAR(255) NOT NULL REFERENCES cost_ceilings(ceiling_id),
            alert_level VARCHAR(50) NOT NULL,
            current_spending DECIMAL(15,4) NOT NULL,
            limit_amount DECIMAL(15,4) NOT NULL,
            usage_percentage FLOAT NOT NULL,
            triggered_at TIMESTAMP WITH TIME ZONE NOT NULL,
            resolved_at TIMESTAMP WITH TIME ZONE,
            is_resolved BOOLEAN DEFAULT false,
            message TEXT,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """))
    
    # Cost optimization recommendations table
    await db_session.execute(text("""
        CREATE TABLE cost_optimization_recommendations (
            id SERIAL PRIMARY KEY,
            recommendation_id VARCHAR(255) UNIQUE NOT NULL,
            ceiling_id VARCHAR(255) NOT NULL REFERENCES cost_ceilings(ceiling_id),
            recommendation_type VARCHAR(100) NOT NULL,
            description TEXT NOT NULL,
            potential_savings DECIMAL(15,4) NOT NULL,
            implementation_effort VARCHAR(50) NOT NULL,
            priority INTEGER NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            metadata JSONB DEFAULT '{}'
        )
    """))
    
    # Create indexes for performance
    await db_session.execute(text("""
        CREATE INDEX idx_performance_baselines_service ON performance_baselines(service);
        CREATE INDEX idx_performance_baselines_type ON performance_baselines(baseline_type);
        CREATE INDEX idx_performance_baselines_active ON performance_baselines(is_active);
        CREATE INDEX idx_performance_baselines_tenant ON performance_baselines(tenant_id);
        CREATE INDEX idx_performance_metrics_baseline_id ON performance_metrics(baseline_id);
        CREATE INDEX idx_performance_metrics_timestamp ON performance_metrics(timestamp);
        CREATE INDEX idx_baseline_calculations_baseline_id ON baseline_calculations(baseline_id);
        CREATE INDEX idx_baseline_calculations_calculated_at ON baseline_calculations(calculated_at);
        CREATE INDEX idx_performance_alerts_baseline_id ON performance_alerts(baseline_id);
        CREATE INDEX idx_performance_alerts_severity ON performance_alerts(severity);
        CREATE INDEX idx_performance_alerts_triggered_at ON performance_alerts(triggered_at);
        CREATE INDEX idx_performance_alerts_resolved ON performance_alerts(is_resolved);
        CREATE INDEX idx_cost_ceilings_tenant_id ON cost_ceilings(tenant_id);
        CREATE INDEX idx_cost_ceilings_service ON cost_ceilings(service);
        CREATE INDEX idx_cost_ceilings_type ON cost_ceilings(ceiling_type);
        CREATE INDEX idx_cost_ceilings_active ON cost_ceilings(is_active);
        CREATE INDEX idx_cost_records_ceiling_id ON cost_records(ceiling_id);
        CREATE INDEX idx_cost_records_tenant_id ON cost_records(tenant_id);
        CREATE INDEX idx_cost_records_timestamp ON cost_records(timestamp);
        CREATE INDEX idx_cost_records_service ON cost_records(service);
        CREATE INDEX idx_cost_alerts_ceiling_id ON cost_alerts(ceiling_id);
        CREATE INDEX idx_cost_alerts_level ON cost_alerts(alert_level);
        CREATE INDEX idx_cost_alerts_triggered_at ON cost_alerts(triggered_at);
        CREATE INDEX idx_cost_alerts_resolved ON cost_alerts(is_resolved);
        CREATE INDEX idx_cost_recommendations_ceiling_id ON cost_optimization_recommendations(ceiling_id);
        CREATE INDEX idx_cost_recommendations_priority ON cost_optimization_recommendations(priority);
        CREATE INDEX idx_cost_recommendations_created_at ON cost_optimization_recommendations(created_at);
    """))
    
    # Create composite indexes for common queries
    await db_session.execute(text("""
        CREATE INDEX idx_performance_baselines_service_type ON performance_baselines(service, baseline_type);
        CREATE INDEX idx_performance_metrics_baseline_timestamp ON performance_metrics(baseline_id, timestamp);
        CREATE INDEX idx_cost_records_ceiling_timestamp ON cost_records(ceiling_id, timestamp);
        CREATE INDEX idx_cost_records_tenant_timestamp ON cost_records(tenant_id, timestamp);
        CREATE INDEX idx_performance_alerts_baseline_triggered ON performance_alerts(baseline_id, triggered_at);
        CREATE INDEX idx_cost_alerts_ceiling_triggered ON cost_alerts(ceiling_id, triggered_at);
    """))
    
    await db_session.commit()
    print(f"Migration {VERSION} completed successfully")


async def downgrade(db_session):
    """Downgrade database schema."""
    
    # Drop tables in reverse order (respecting foreign key constraints)
    await db_session.execute(text("DROP TABLE IF EXISTS cost_optimization_recommendations CASCADE"))
    await db_session.execute(text("DROP TABLE IF EXISTS cost_alerts CASCADE"))
    await db_session.execute(text("DROP TABLE IF EXISTS cost_records CASCADE"))
    await db_session.execute(text("DROP TABLE IF EXISTS cost_ceilings CASCADE"))
    await db_session.execute(text("DROP TABLE IF EXISTS performance_alerts CASCADE"))
    await db_session.execute(text("DROP TABLE IF EXISTS baseline_calculations CASCADE"))
    await db_session.execute(text("DROP TABLE IF EXISTS performance_metrics CASCADE"))
    await db_session.execute(text("DROP TABLE IF EXISTS performance_baselines CASCADE"))
    
    await db_session.commit()
    print(f"Migration {VERSION} downgraded successfully")
