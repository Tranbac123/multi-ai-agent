"""
Migration: Eval & Replay Tables

Creates tables for golden tasks, task executions, episodes, episode states,
replay requests, and replay executions.
"""

from sqlalchemy import text

# Migration version
VERSION = "010"


async def upgrade(db_session):
    """Upgrade database schema."""
    
    # Golden tasks table
    await db_session.execute(text("""
        CREATE TABLE golden_tasks (
            id SERIAL PRIMARY KEY,
            task_id VARCHAR(255) UNIQUE NOT NULL,
            title VARCHAR(500) NOT NULL,
            description TEXT NOT NULL,
            category VARCHAR(100) NOT NULL,
            difficulty VARCHAR(50) NOT NULL,
            input_data JSONB NOT NULL,
            expected_output JSONB NOT NULL,
            evaluation_criteria JSONB NOT NULL,
            tags TEXT[] DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            version INTEGER DEFAULT 1,
            is_active BOOLEAN DEFAULT true,
            timeout_seconds INTEGER DEFAULT 300,
            max_retries INTEGER DEFAULT 3,
            metadata JSONB DEFAULT '{}'
        )
    """))
    
    # Task executions table
    await db_session.execute(text("""
        CREATE TABLE task_executions (
            id SERIAL PRIMARY KEY,
            execution_id VARCHAR(255) UNIQUE NOT NULL,
            task_id VARCHAR(255) NOT NULL REFERENCES golden_tasks(task_id),
            run_id VARCHAR(255) NOT NULL,
            tenant_id VARCHAR(255) NOT NULL,
            status VARCHAR(50) NOT NULL,
            started_at TIMESTAMP WITH TIME ZONE NOT NULL,
            completed_at TIMESTAMP WITH TIME ZONE,
            actual_output JSONB,
            evaluation_score FLOAT,
            evaluation_details JSONB,
            error_message TEXT,
            execution_time_ms INTEGER,
            retry_count INTEGER DEFAULT 0,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """))
    
    # Episodes table
    await db_session.execute(text("""
        CREATE TABLE episodes (
            id SERIAL PRIMARY KEY,
            episode_id VARCHAR(255) UNIQUE NOT NULL,
            run_id VARCHAR(255) NOT NULL,
            tenant_id VARCHAR(255) NOT NULL,
            task_id VARCHAR(255) NOT NULL,
            agent_config JSONB NOT NULL,
            initial_state JSONB NOT NULL,
            final_state JSONB,
            success BOOLEAN,
            total_reward FLOAT,
            steps_count INTEGER DEFAULT 0,
            duration_ms INTEGER,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            metadata JSONB DEFAULT '{}'
        )
    """))
    
    # Episode states table
    await db_session.execute(text("""
        CREATE TABLE episode_states (
            id SERIAL PRIMARY KEY,
            state_id VARCHAR(255) UNIQUE NOT NULL,
            episode_id VARCHAR(255) NOT NULL REFERENCES episodes(episode_id),
            step_number INTEGER NOT NULL,
            state_type VARCHAR(50) NOT NULL,
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
            agent_state JSONB NOT NULL,
            environment_state JSONB NOT NULL,
            action_taken JSONB,
            observation JSONB,
            reward FLOAT,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """))
    
    # Replay requests table
    await db_session.execute(text("""
        CREATE TABLE replay_requests (
            id SERIAL PRIMARY KEY,
            replay_id VARCHAR(255) UNIQUE NOT NULL,
            episode_id VARCHAR(255) NOT NULL REFERENCES episodes(episode_id),
            replay_config JSONB NOT NULL,
            target_step INTEGER,
            replay_mode VARCHAR(50) DEFAULT 'full',
            breakpoints INTEGER[] DEFAULT '{}',
            variable_overrides JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """))
    
    # Replay executions table
    await db_session.execute(text("""
        CREATE TABLE replay_executions (
            id SERIAL PRIMARY KEY,
            replay_id VARCHAR(255) UNIQUE NOT NULL REFERENCES replay_requests(replay_id),
            episode_id VARCHAR(255) NOT NULL REFERENCES episodes(episode_id),
            status VARCHAR(50) NOT NULL,
            started_at TIMESTAMP WITH TIME ZONE NOT NULL,
            completed_at TIMESTAMP WITH TIME ZONE,
            current_step INTEGER DEFAULT 0,
            total_steps INTEGER DEFAULT 0,
            replay_results JSONB,
            error_message TEXT,
            execution_time_ms INTEGER,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """))
    
    # Evaluation results table
    await db_session.execute(text("""
        CREATE TABLE evaluation_results (
            id SERIAL PRIMARY KEY,
            evaluation_id VARCHAR(255) UNIQUE NOT NULL,
            execution_id VARCHAR(255) NOT NULL REFERENCES task_executions(execution_id),
            task_id VARCHAR(255) NOT NULL REFERENCES golden_tasks(task_id),
            overall_score FLOAT NOT NULL,
            criteria_scores JSONB NOT NULL,
            passed BOOLEAN NOT NULL,
            evaluation_method VARCHAR(100) NOT NULL,
            evaluated_at TIMESTAMP WITH TIME ZONE NOT NULL,
            evaluator_metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """))
    
    # Create indexes for performance
    await db_session.execute(text("""
        CREATE INDEX idx_golden_tasks_category ON golden_tasks(category);
        CREATE INDEX idx_golden_tasks_difficulty ON golden_tasks(difficulty);
        CREATE INDEX idx_golden_tasks_active ON golden_tasks(is_active);
        CREATE INDEX idx_task_executions_task_id ON task_executions(task_id);
        CREATE INDEX idx_task_executions_run_id ON task_executions(run_id);
        CREATE INDEX idx_task_executions_tenant_id ON task_executions(tenant_id);
        CREATE INDEX idx_task_executions_status ON task_executions(status);
        CREATE INDEX idx_episodes_run_id ON episodes(run_id);
        CREATE INDEX idx_episodes_tenant_id ON episodes(tenant_id);
        CREATE INDEX idx_episodes_task_id ON episodes(task_id);
        CREATE INDEX idx_episodes_success ON episodes(success);
        CREATE INDEX idx_episode_states_episode_id ON episode_states(episode_id);
        CREATE INDEX idx_episode_states_step_number ON episode_states(step_number);
        CREATE INDEX idx_episode_states_state_type ON episode_states(state_type);
        CREATE INDEX idx_replay_requests_episode_id ON replay_requests(episode_id);
        CREATE INDEX idx_replay_executions_episode_id ON replay_executions(episode_id);
        CREATE INDEX idx_replay_executions_status ON replay_executions(status);
        CREATE INDEX idx_evaluation_results_execution_id ON evaluation_results(execution_id);
        CREATE INDEX idx_evaluation_results_task_id ON evaluation_results(task_id);
        CREATE INDEX idx_evaluation_results_evaluation_method ON evaluation_results(evaluation_method);
    """))
    
    # Create composite indexes for common queries
    await db_session.execute(text("""
        CREATE INDEX idx_golden_tasks_category_difficulty ON golden_tasks(category, difficulty);
        CREATE INDEX idx_task_executions_tenant_status ON task_executions(tenant_id, status);
        CREATE INDEX idx_episodes_tenant_success ON episodes(tenant_id, success);
        CREATE INDEX idx_episode_states_episode_step ON episode_states(episode_id, step_number);
    """))
    
    await db_session.commit()
    print(f"Migration {VERSION} completed successfully")


async def downgrade(db_session):
    """Downgrade database schema."""
    
    # Drop tables in reverse order (respecting foreign key constraints)
    await db_session.execute(text("DROP TABLE IF EXISTS evaluation_results CASCADE"))
    await db_session.execute(text("DROP TABLE IF EXISTS replay_executions CASCADE"))
    await db_session.execute(text("DROP TABLE IF EXISTS replay_requests CASCADE"))
    await db_session.execute(text("DROP TABLE IF EXISTS episode_states CASCADE"))
    await db_session.execute(text("DROP TABLE IF EXISTS episodes CASCADE"))
    await db_session.execute(text("DROP TABLE IF EXISTS task_executions CASCADE"))
    await db_session.execute(text("DROP TABLE IF EXISTS golden_tasks CASCADE"))
    
    await db_session.commit()
    print(f"Migration {VERSION} downgraded successfully")
