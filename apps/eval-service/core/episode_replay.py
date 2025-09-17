"""
Episode Replay System

Implements episode replay for debugging, analysis, and regression testing
with comprehensive state tracking and replay capabilities.
"""

import asyncio
import json
import uuid
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import structlog
from datetime import datetime, timedelta
from sqlalchemy import text, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class ReplayStatus(Enum):
    """Episode replay status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class StateType(Enum):
    """Types of state snapshots."""
    INITIAL = "initial"
    INTERMEDIATE = "intermediate"
    FINAL = "final"
    ERROR = "error"
    CHECKPOINT = "checkpoint"


@dataclass
class EpisodeState:
    """Episode state snapshot."""
    
    state_id: str
    episode_id: str
    step_number: int
    state_type: StateType
    timestamp: datetime
    agent_state: Dict[str, Any]
    environment_state: Dict[str, Any]
    action_taken: Optional[Dict[str, Any]] = None
    observation: Optional[Dict[str, Any]] = None
    reward: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Episode:
    """Episode definition for replay."""
    
    episode_id: str
    run_id: str
    tenant_id: str
    task_id: str
    agent_config: Dict[str, Any]
    initial_state: Dict[str, Any]
    final_state: Optional[Dict[str, Any]] = None
    success: Optional[bool] = None
    total_reward: Optional[float] = None
    steps_count: int = 0
    duration_ms: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplayRequest:
    """Episode replay request."""
    
    replay_id: str
    episode_id: str
    replay_config: Dict[str, Any]
    target_step: Optional[int] = None
    replay_mode: str = "full"  # full, partial, step_by_step
    breakpoints: List[int] = field(default_factory=list)
    variable_overrides: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ReplayExecution:
    """Episode replay execution record."""
    
    replay_id: str
    episode_id: str
    status: ReplayStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    current_step: int = 0
    total_steps: int = 0
    replay_results: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class EpisodeReplayManager:
    """Manages episode recording and replay."""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        
        logger.info("Episode replay manager initialized")
    
    async def record_episode(
        self,
        run_id: str,
        tenant_id: str,
        task_id: str,
        agent_config: Dict[str, Any],
        initial_state: Dict[str, Any]
    ) -> Episode:
        """Record a new episode."""
        
        episode_id = str(uuid.uuid4())
        
        episode = Episode(
            episode_id=episode_id,
            run_id=run_id,
            tenant_id=tenant_id,
            task_id=task_id,
            agent_config=agent_config,
            initial_state=initial_state
        )
        
        await self._store_episode(episode)
        
        logger.info("Episode recorded", 
                   episode_id=episode_id,
                   run_id=run_id,
                   tenant_id=tenant_id,
                   task_id=task_id)
        
        return episode
    
    async def _store_episode(self, episode: Episode):
        """Store episode in database."""
        
        query = """
        INSERT INTO episodes (
            episode_id, run_id, tenant_id, task_id, agent_config,
            initial_state, final_state, success, total_reward,
            steps_count, duration_ms, created_at, metadata
        ) VALUES (
            :episode_id, :run_id, :tenant_id, :task_id, :agent_config,
            :initial_state, :final_state, :success, :total_reward,
            :steps_count, :duration_ms, :created_at, :metadata
        )
        """
        
        await self.db_session.execute(text(query), {
            "episode_id": episode.episode_id,
            "run_id": episode.run_id,
            "tenant_id": episode.tenant_id,
            "task_id": episode.task_id,
            "agent_config": json.dumps(episode.agent_config),
            "initial_state": json.dumps(episode.initial_state),
            "final_state": json.dumps(episode.final_state) if episode.final_state else None,
            "success": episode.success,
            "total_reward": episode.total_reward,
            "steps_count": episode.steps_count,
            "duration_ms": episode.duration_ms,
            "created_at": episode.created_at,
            "metadata": json.dumps(episode.metadata)
        })
        
        await self.db_session.commit()
    
    async def record_state_snapshot(
        self,
        episode_id: str,
        step_number: int,
        state_type: StateType,
        agent_state: Dict[str, Any],
        environment_state: Dict[str, Any],
        action_taken: Optional[Dict[str, Any]] = None,
        observation: Optional[Dict[str, Any]] = None,
        reward: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> EpisodeState:
        """Record a state snapshot during episode execution."""
        
        state_id = str(uuid.uuid4())
        
        state = EpisodeState(
            state_id=state_id,
            episode_id=episode_id,
            step_number=step_number,
            state_type=state_type,
            timestamp=datetime.now(),
            agent_state=agent_state,
            environment_state=environment_state,
            action_taken=action_taken,
            observation=observation,
            reward=reward,
            metadata=metadata or {}
        )
        
        await self._store_state_snapshot(state)
        
        return state
    
    async def _store_state_snapshot(self, state: EpisodeState):
        """Store state snapshot in database."""
        
        query = """
        INSERT INTO episode_states (
            state_id, episode_id, step_number, state_type, timestamp,
            agent_state, environment_state, action_taken, observation,
            reward, metadata
        ) VALUES (
            :state_id, :episode_id, :step_number, :state_type, :timestamp,
            :agent_state, :environment_state, :action_taken, :observation,
            :reward, :metadata
        )
        """
        
        await self.db_session.execute(text(query), {
            "state_id": state.state_id,
            "episode_id": state.episode_id,
            "step_number": state.step_number,
            "state_type": state.state_type.value,
            "timestamp": state.timestamp,
            "agent_state": json.dumps(state.agent_state),
            "environment_state": json.dumps(state.environment_state),
            "action_taken": json.dumps(state.action_taken) if state.action_taken else None,
            "observation": json.dumps(state.observation) if state.observation else None,
            "reward": state.reward,
            "metadata": json.dumps(state.metadata)
        })
        
        await self.db_session.commit()
    
    async def finalize_episode(
        self,
        episode_id: str,
        final_state: Dict[str, Any],
        success: bool,
        total_reward: float,
        steps_count: int,
        duration_ms: int
    ):
        """Finalize episode recording."""
        
        query = """
        UPDATE episodes 
        SET final_state = :final_state, success = :success, total_reward = :total_reward,
            steps_count = :steps_count, duration_ms = :duration_ms
        WHERE episode_id = :episode_id
        """
        
        await self.db_session.execute(text(query), {
            "episode_id": episode_id,
            "final_state": json.dumps(final_state),
            "success": success,
            "total_reward": total_reward,
            "steps_count": steps_count,
            "duration_ms": duration_ms
        })
        
        await self.db_session.commit()
        
        logger.info("Episode finalized", 
                   episode_id=episode_id,
                   success=success,
                   total_reward=total_reward,
                   steps_count=steps_count)
    
    async def get_episode(self, episode_id: str) -> Optional[Episode]:
        """Get episode by ID."""
        
        query = """
        SELECT * FROM episodes 
        WHERE episode_id = :episode_id
        """
        
        result = await self.db_session.execute(text(query), {"episode_id": episode_id})
        row = result.fetchone()
        
        if not row:
            return None
        
        return self._row_to_episode(row)
    
    async def get_episode_states(
        self, 
        episode_id: str,
        state_type: Optional[StateType] = None,
        limit: int = 1000
    ) -> List[EpisodeState]:
        """Get episode states."""
        
        query = """
        SELECT * FROM episode_states 
        WHERE episode_id = :episode_id
        """
        
        params = {"episode_id": episode_id}
        
        if state_type:
            query += " AND state_type = :state_type"
            params["state_type"] = state_type.value
        
        query += " ORDER BY step_number, timestamp LIMIT :limit"
        params["limit"] = limit
        
        result = await self.db_session.execute(text(query), params)
        rows = result.fetchall()
        
        return [self._row_to_episode_state(row) for row in rows]
    
    async def create_replay_request(
        self,
        episode_id: str,
        replay_config: Dict[str, Any],
        target_step: Optional[int] = None,
        replay_mode: str = "full",
        breakpoints: Optional[List[int]] = None,
        variable_overrides: Optional[Dict[str, Any]] = None
    ) -> ReplayRequest:
        """Create a replay request."""
        
        replay_id = str(uuid.uuid4())
        
        replay_request = ReplayRequest(
            replay_id=replay_id,
            episode_id=episode_id,
            replay_config=replay_config,
            target_step=target_step,
            replay_mode=replay_mode,
            breakpoints=breakpoints or [],
            variable_overrides=variable_overrides or {}
        )
        
        await self._store_replay_request(replay_request)
        
        logger.info("Replay request created", 
                   replay_id=replay_id,
                   episode_id=episode_id,
                   replay_mode=replay_mode)
        
        return replay_request
    
    async def _store_replay_request(self, replay_request: ReplayRequest):
        """Store replay request in database."""
        
        query = """
        INSERT INTO replay_requests (
            replay_id, episode_id, replay_config, target_step,
            replay_mode, breakpoints, variable_overrides, created_at
        ) VALUES (
            :replay_id, :episode_id, :replay_config, :target_step,
            :replay_mode, :breakpoints, :variable_overrides, :created_at
        )
        """
        
        await self.db_session.execute(text(query), {
            "replay_id": replay_request.replay_id,
            "episode_id": replay_request.episode_id,
            "replay_config": json.dumps(replay_request.replay_config),
            "target_step": replay_request.target_step,
            "replay_mode": replay_request.replay_mode,
            "breakpoints": json.dumps(replay_request.breakpoints),
            "variable_overrides": json.dumps(replay_request.variable_overrides),
            "created_at": replay_request.created_at
        })
        
        await self.db_session.commit()
    
    async def execute_replay(
        self,
        replay_request: ReplayRequest,
        executor_func: callable
    ) -> ReplayExecution:
        """Execute episode replay."""
        
        execution = ReplayExecution(
            replay_id=replay_request.replay_id,
            episode_id=replay_request.episode_id,
            status=ReplayStatus.PENDING,
            started_at=datetime.now()
        )
        
        await self._store_replay_execution(execution)
        
        try:
            # Update status to running
            execution.status = ReplayStatus.RUNNING
            await self._update_replay_execution(execution)
            
            # Get original episode
            episode = await self.get_episode(replay_request.episode_id)
            if not episode:
                raise ValueError(f"Episode not found: {replay_request.episode_id}")
            
            # Get episode states
            episode_states = await self.get_episode_states(replay_request.episode_id)
            
            # Execute replay
            start_time = datetime.now()
            replay_results = await executor_func(
                episode=episode,
                states=episode_states,
                replay_config=replay_request.replay_config,
                target_step=replay_request.target_step,
                replay_mode=replay_request.replay_mode,
                breakpoints=replay_request.breakpoints,
                variable_overrides=replay_request.variable_overrides
            )
            
            end_time = datetime.now()
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Update execution with results
            execution.status = ReplayStatus.COMPLETED
            execution.completed_at = end_time
            execution.replay_results = replay_results
            execution.execution_time_ms = execution_time_ms
            
            await self._update_replay_execution(execution)
            
            logger.info("Episode replay completed", 
                       replay_id=replay_request.replay_id,
                       episode_id=replay_request.episode_id,
                       execution_time_ms=execution_time_ms)
            
        except Exception as e:
            execution.status = ReplayStatus.FAILED
            execution.completed_at = datetime.now()
            execution.error_message = str(e)
            
            await self._update_replay_execution(execution)
            
            logger.error("Episode replay failed", 
                        replay_id=replay_request.replay_id,
                        episode_id=replay_request.episode_id,
                        error=str(e))
        
        return execution
    
    async def _store_replay_execution(self, execution: ReplayExecution):
        """Store replay execution in database."""
        
        query = """
        INSERT INTO replay_executions (
            replay_id, episode_id, status, started_at, completed_at,
            current_step, total_steps, replay_results, error_message,
            execution_time_ms, metadata
        ) VALUES (
            :replay_id, :episode_id, :status, :started_at, :completed_at,
            :current_step, :total_steps, :replay_results, :error_message,
            :execution_time_ms, :metadata
        )
        """
        
        await self.db_session.execute(text(query), {
            "replay_id": execution.replay_id,
            "episode_id": execution.episode_id,
            "status": execution.status.value,
            "started_at": execution.started_at,
            "completed_at": execution.completed_at,
            "current_step": execution.current_step,
            "total_steps": execution.total_steps,
            "replay_results": json.dumps(execution.replay_results) if execution.replay_results else None,
            "error_message": execution.error_message,
            "execution_time_ms": execution.execution_time_ms,
            "metadata": json.dumps(execution.metadata)
        })
        
        await self.db_session.commit()
    
    async def _update_replay_execution(self, execution: ReplayExecution):
        """Update replay execution in database."""
        
        query = """
        UPDATE replay_executions 
        SET status = :status, completed_at = :completed_at,
            current_step = :current_step, total_steps = :total_steps,
            replay_results = :replay_results, error_message = :error_message,
            execution_time_ms = :execution_time_ms, metadata = :metadata
        WHERE replay_id = :replay_id
        """
        
        await self.db_session.execute(text(query), {
            "replay_id": execution.replay_id,
            "status": execution.status.value,
            "completed_at": execution.completed_at,
            "current_step": execution.current_step,
            "total_steps": execution.total_steps,
            "replay_results": json.dumps(execution.replay_results) if execution.replay_results else None,
            "error_message": execution.error_message,
            "execution_time_ms": execution.execution_time_ms,
            "metadata": json.dumps(execution.metadata)
        })
        
        await self.db_session.commit()
    
    async def get_episodes(
        self,
        run_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        task_id: Optional[str] = None,
        success: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Episode]:
        """Get episodes with filters."""
        
        query = """
        SELECT * FROM episodes 
        WHERE 1=1
        """
        
        params = {}
        
        if run_id:
            query += " AND run_id = :run_id"
            params["run_id"] = run_id
        
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = tenant_id
        
        if task_id:
            query += " AND task_id = :task_id"
            params["task_id"] = task_id
        
        if success is not None:
            query += " AND success = :success"
            params["success"] = success
        
        query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset
        
        result = await self.db_session.execute(text(query), params)
        rows = result.fetchall()
        
        return [self._row_to_episode(row) for row in rows]
    
    def _row_to_episode(self, row) -> Episode:
        """Convert database row to Episode object."""
        
        return Episode(
            episode_id=row.episode_id,
            run_id=row.run_id,
            tenant_id=row.tenant_id,
            task_id=row.task_id,
            agent_config=json.loads(row.agent_config),
            initial_state=json.loads(row.initial_state),
            final_state=json.loads(row.final_state) if row.final_state else None,
            success=row.success,
            total_reward=row.total_reward,
            steps_count=row.steps_count,
            duration_ms=row.duration_ms,
            created_at=row.created_at,
            metadata=json.loads(row.metadata) if row.metadata else {}
        )
    
    def _row_to_episode_state(self, row) -> EpisodeState:
        """Convert database row to EpisodeState object."""
        
        return EpisodeState(
            state_id=row.state_id,
            episode_id=row.episode_id,
            step_number=row.step_number,
            state_type=StateType(row.state_type),
            timestamp=row.timestamp,
            agent_state=json.loads(row.agent_state),
            environment_state=json.loads(row.environment_state),
            action_taken=json.loads(row.action_taken) if row.action_taken else None,
            observation=json.loads(row.observation) if row.observation else None,
            reward=row.reward,
            metadata=json.loads(row.metadata) if row.metadata else {}
        )
    
    async def get_episode_statistics(self) -> Dict[str, Any]:
        """Get episode statistics."""
        
        # Episode statistics
        episode_query = """
        SELECT 
            COUNT(*) as total_episodes,
            COUNT(CASE WHEN success = true THEN 1 END) as successful_episodes,
            COUNT(CASE WHEN success = false THEN 1 END) as failed_episodes,
            AVG(steps_count) as avg_steps,
            AVG(duration_ms) as avg_duration_ms,
            AVG(total_reward) as avg_reward
        FROM episodes
        """
        
        episode_result = await self.db_session.execute(text(episode_query))
        episode_stats = episode_result.fetchone()
        
        # State statistics
        state_query = """
        SELECT 
            COUNT(*) as total_states,
            COUNT(DISTINCT episode_id) as episodes_with_states
        FROM episode_states
        """
        
        state_result = await self.db_session.execute(text(state_query))
        state_stats = state_result.fetchone()
        
        return {
            "episode_statistics": {
                "total_episodes": episode_stats.total_episodes,
                "successful_episodes": episode_stats.successful_episodes,
                "failed_episodes": episode_stats.failed_episodes,
                "success_rate": (
                    episode_stats.successful_episodes / max(1, episode_stats.total_episodes)
                ),
                "avg_steps": episode_stats.avg_steps,
                "avg_duration_ms": episode_stats.avg_duration_ms,
                "avg_reward": episode_stats.avg_reward
            },
            "state_statistics": {
                "total_states": state_stats.total_states,
                "episodes_with_states": state_stats.episodes_with_states
            },
            "timestamp": datetime.now().isoformat()
        }
