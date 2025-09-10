"""Episode replay system for evaluation and testing."""

import asyncio
import time
import json
import uuid
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
import redis.asyncio as redis

logger = structlog.get_logger(__name__)


class EpisodeStatus(Enum):
    """Episode status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ReplayMode(Enum):
    """Replay mode."""
    EXACT = "exact"
    PARAMETRIC = "parametric"
    STRESS = "stress"


@dataclass
class EpisodeStep:
    """Individual step in an episode."""
    step_id: str
    step_type: str
    timestamp: float
    data: Dict[str, Any]
    metadata: Dict[str, Any] = None


@dataclass
class Episode:
    """Episode representation."""
    episode_id: str
    tenant_id: str
    user_id: str
    session_id: str
    status: EpisodeStatus
    created_at: float
    steps: List[EpisodeStep] = None
    metadata: Dict[str, Any] = None


class EpisodeReplay:
    """Episode replay system for evaluation and testing."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.active_replays = {}
    
    async def record_episode(
        self,
        tenant_id: str,
        user_id: str,
        session_id: str,
        steps: List[EpisodeStep],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Record an episode for later replay."""
        try:
            episode_id = str(uuid.uuid4())
            
            episode = Episode(
                episode_id=episode_id,
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=session_id,
                status=EpisodeStatus.COMPLETED,
                created_at=time.time(),
                steps=steps,
                metadata=metadata or {}
            )
            
            # Store episode
            await self._store_episode(episode)
            
            logger.info("Episode recorded", episode_id=episode_id, tenant_id=tenant_id)
            return episode_id
            
        except Exception as e:
            logger.error("Failed to record episode", error=str(e))
            raise
    
    async def replay_episode(
        self,
        episode_id: str,
        replay_mode: ReplayMode = ReplayMode.EXACT,
        parameters: Optional[Dict[str, Any]] = None
    ) -> str:
        """Replay an episode for evaluation."""
        try:
            # Get episode
            episode = await self._get_episode(episode_id)
            if not episode:
                raise ValueError(f"Episode {episode_id} not found")
            
            # Create replay session
            replay_id = str(uuid.uuid4())
            
            # Start replay
            asyncio.create_task(self._execute_replay(replay_id, episode, replay_mode, parameters))
            
            logger.info("Episode replay started", replay_id=replay_id, episode_id=episode_id)
            return replay_id
            
        except Exception as e:
            logger.error("Failed to start episode replay", error=str(e))
            raise
    
    async def _execute_replay(
        self,
        replay_id: str,
        episode: Episode,
        replay_mode: ReplayMode,
        parameters: Optional[Dict[str, Any]]
    ) -> None:
        """Execute episode replay."""
        try:
            # Replay steps
            for step in episode.steps:
                try:
                    # Apply replay mode modifications
                    modified_step = await self._apply_replay_mode(step, replay_mode, parameters)
                    
                    # Execute step
                    step_result = await self._execute_step(modified_step, episode)
                    
                    # Add delay between steps
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error("Step execution failed", error=str(e), step_id=step.step_id)
            
            logger.info("Episode replay completed", replay_id=replay_id, episode_id=episode.episode_id)
            
        except Exception as e:
            logger.error("Episode replay failed", error=str(e))
    
    async def _apply_replay_mode(
        self,
        step: EpisodeStep,
        replay_mode: ReplayMode,
        parameters: Dict[str, Any]
    ) -> EpisodeStep:
        """Apply replay mode modifications to step."""
        if replay_mode == ReplayMode.EXACT:
            return step
        elif replay_mode == ReplayMode.PARAMETRIC:
            modified_data = step.data.copy()
            for param_name, param_value in parameters.items():
                if param_name in modified_data:
                    modified_data[param_name] = param_value
            return EpisodeStep(
                step_id=step.step_id,
                step_type=step.step_type,
                timestamp=step.timestamp,
                data=modified_data,
                metadata=step.metadata
            )
        else:
            return step
    
    async def _execute_step(self, step: EpisodeStep, episode: Episode) -> Dict[str, Any]:
        """Execute a single step."""
        try:
            start_time = time.time()
            
            # Simulate step execution
            if step.step_type == 'user_message':
                await asyncio.sleep(0.1)
                result = {'status': 'processed'}
            elif step.step_type == 'agent_response':
                await asyncio.sleep(0.2)
                result = {'status': 'generated'}
            elif step.step_type == 'tool_call':
                await asyncio.sleep(0.3)
                result = {'status': 'executed'}
            else:
                result = {'status': 'unknown_step_type'}
            
            execution_time = time.time() - start_time
            
            return {
                'step_id': step.step_id,
                'step_type': step.step_type,
                'execution_time': execution_time,
                'result': result,
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error("Step execution failed", error=str(e))
            return {'step_id': step.step_id, 'error': str(e)}
    
    async def _store_episode(self, episode: Episode) -> None:
        """Store episode in Redis."""
        try:
            episode_key = f"episode:{episode.tenant_id}:{episode.episode_id}"
            
            episode_data = {
                'episode_id': episode.episode_id,
                'tenant_id': episode.tenant_id,
                'user_id': episode.user_id,
                'session_id': episode.session_id,
                'status': episode.status.value,
                'created_at': episode.created_at,
                'steps': json.dumps([asdict(step) for step in episode.steps]),
                'metadata': json.dumps(episode.metadata)
            }
            
            await self.redis.hset(episode_key, mapping=episode_data)
            await self.redis.expire(episode_key, 86400 * 30)  # 30 days TTL
            
        except Exception as e:
            logger.error("Failed to store episode", error=str(e))
    
    async def _get_episode(self, episode_id: str) -> Optional[Episode]:
        """Get episode by ID."""
        try:
            pattern = f"episode:*:{episode_id}"
            keys = await self.redis.keys(pattern)
            
            if not keys:
                return None
            
            episode_key = keys[0].decode()
            episode_data = await self.redis.hgetall(episode_key)
            
            if not episode_data:
                return None
            
            steps_data = json.loads(episode_data['steps'])
            steps = [EpisodeStep(**step_data) for step_data in steps_data]
            metadata = json.loads(episode_data['metadata'])
            
            return Episode(
                episode_id=episode_data['episode_id'],
                tenant_id=episode_data['tenant_id'],
                user_id=episode_data['user_id'],
                session_id=episode_data['session_id'],
                status=EpisodeStatus(episode_data['status']),
                created_at=float(episode_data['created_at']),
                steps=steps,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error("Failed to get episode", error=str(e))
            return None