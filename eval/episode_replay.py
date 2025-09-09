"""Episode replay system for testing and debugging."""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import UUID
import structlog
from dataclasses import dataclass

logger = structlog.get_logger(__name__)


@dataclass
class EpisodeStep:
    """Episode step definition."""
    step_id: str
    timestamp: float
    action: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    duration: float
    success: bool
    error: Optional[str] = None


@dataclass
class Episode:
    """Episode definition."""
    episode_id: str
    tenant_id: UUID
    workflow: str
    start_time: float
    end_time: Optional[float]
    status: str
    steps: List[EpisodeStep]
    metadata: Dict[str, Any]


class EpisodeRecorder:
    """Records episodes for later replay."""
    
    def __init__(self):
        self.episodes: Dict[str, Episode] = {}
        self.current_episodes: Dict[str, Episode] = {}
    
    def start_episode(
        self,
        episode_id: str,
        tenant_id: UUID,
        workflow: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Episode:
        """Start recording an episode."""
        episode = Episode(
            episode_id=episode_id,
            tenant_id=tenant_id,
            workflow=workflow,
            start_time=time.time(),
            end_time=None,
            status="running",
            steps=[],
            metadata=metadata or {}
        )
        
        self.current_episodes[episode_id] = episode
        
        logger.info("Episode started", 
                   episode_id=episode_id, 
                   tenant_id=tenant_id, 
                   workflow=workflow)
        
        return episode
    
    def record_step(
        self,
        episode_id: str,
        step_id: str,
        action: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        duration: float,
        success: bool,
        error: Optional[str] = None
    ):
        """Record a step in the episode."""
        if episode_id not in self.current_episodes:
            logger.warning("Episode not found", episode_id=episode_id)
            return
        
        episode = self.current_episodes[episode_id]
        
        step = EpisodeStep(
            step_id=step_id,
            timestamp=time.time(),
            action=action,
            input_data=input_data,
            output_data=output_data,
            duration=duration,
            success=success,
            error=error
        )
        
        episode.steps.append(step)
        
        logger.debug("Step recorded", 
                    episode_id=episode_id, 
                    step_id=step_id, 
                    action=action)
    
    def end_episode(
        self,
        episode_id: str,
        status: str = "completed"
    ):
        """End an episode."""
        if episode_id not in self.current_episodes:
            logger.warning("Episode not found", episode_id=episode_id)
            return
        
        episode = self.current_episodes[episode_id]
        episode.end_time = time.time()
        episode.status = status
        
        # Move to completed episodes
        self.episodes[episode_id] = episode
        del self.current_episodes[episode_id]
        
        logger.info("Episode ended", 
                   episode_id=episode_id, 
                   status=status,
                   duration=episode.end_time - episode.start_time)
    
    def get_episode(self, episode_id: str) -> Optional[Episode]:
        """Get episode by ID."""
        return self.episodes.get(episode_id)
    
    def get_episodes_by_tenant(self, tenant_id: UUID) -> List[Episode]:
        """Get episodes for tenant."""
        return [ep for ep in self.episodes.values() if ep.tenant_id == tenant_id]
    
    def get_episodes_by_workflow(self, workflow: str) -> List[Episode]:
        """Get episodes for workflow."""
        return [ep for ep in self.episodes.values() if ep.workflow == workflow]
    
    def save_episode(self, episode_id: str, file_path: str):
        """Save episode to file."""
        episode = self.get_episode(episode_id)
        if not episode:
            raise ValueError(f"Episode {episode_id} not found")
        
        # Convert to serializable format
        episode_data = {
            "episode_id": episode.episode_id,
            "tenant_id": str(episode.tenant_id),
            "workflow": episode.workflow,
            "start_time": episode.start_time,
            "end_time": episode.end_time,
            "status": episode.status,
            "steps": [
                {
                    "step_id": step.step_id,
                    "timestamp": step.timestamp,
                    "action": step.action,
                    "input_data": step.input_data,
                    "output_data": step.output_data,
                    "duration": step.duration,
                    "success": step.success,
                    "error": step.error
                }
                for step in episode.steps
            ],
            "metadata": episode.metadata
        }
        
        with open(file_path, 'w') as f:
            json.dump(episode_data, f, indent=2)
        
        logger.info("Episode saved", episode_id=episode_id, file_path=file_path)
    
    def load_episode(self, file_path: str) -> Episode:
        """Load episode from file."""
        with open(file_path, 'r') as f:
            episode_data = json.load(f)
        
        # Convert back to Episode object
        episode = Episode(
            episode_id=episode_data["episode_id"],
            tenant_id=UUID(episode_data["tenant_id"]),
            workflow=episode_data["workflow"],
            start_time=episode_data["start_time"],
            end_time=episode_data["end_time"],
            status=episode_data["status"],
            steps=[
                EpisodeStep(
                    step_id=step["step_id"],
                    timestamp=step["timestamp"],
                    action=step["action"],
                    input_data=step["input_data"],
                    output_data=step["output_data"],
                    duration=step["duration"],
                    success=step["success"],
                    error=step.get("error")
                )
                for step in episode_data["steps"]
            ],
            metadata=episode_data["metadata"]
        )
        
        self.episodes[episode.episode_id] = episode
        
        logger.info("Episode loaded", episode_id=episode.episode_id, file_path=file_path)
        
        return episode


class EpisodeReplayer:
    """Replays episodes for testing and debugging."""
    
    def __init__(self, recorder: EpisodeRecorder):
        self.recorder = recorder
        self.replay_results: Dict[str, Dict[str, Any]] = {}
    
    async def replay_episode(
        self,
        episode_id: str,
        tenant_id: UUID,
        workflow_executor: callable,
        step_executor: callable
    ) -> Dict[str, Any]:
        """Replay an episode."""
        episode = self.recorder.get_episode(episode_id)
        if not episode:
            raise ValueError(f"Episode {episode_id} not found")
        
        logger.info("Starting episode replay", 
                   episode_id=episode_id, 
                   tenant_id=tenant_id)
        
        replay_start = time.time()
        replay_steps = []
        success_count = 0
        error_count = 0
        
        try:
            # Replay each step
            for step in episode.steps:
                step_start = time.time()
                
                try:
                    # Execute step
                    result = await step_executor(
                        step.action,
                        step.input_data,
                        tenant_id
                    )
                    
                    step_duration = time.time() - step_start
                    success = True
                    error = None
                    success_count += 1
                    
                except Exception as e:
                    step_duration = time.time() - step_start
                    result = None
                    success = False
                    error = str(e)
                    error_count += 1
                
                # Record replay step
                replay_step = {
                    "step_id": step.step_id,
                    "action": step.action,
                    "input_data": step.input_data,
                    "output_data": result,
                    "duration": step_duration,
                    "success": success,
                    "error": error,
                    "original_duration": step.duration,
                    "original_success": step.success
                }
                
                replay_steps.append(replay_step)
                
                # Check if step matches original
                if success != step.success:
                    logger.warning("Step result mismatch", 
                                 step_id=step.step_id, 
                                 original_success=step.success, 
                                 replay_success=success)
        
        except Exception as e:
            logger.error("Episode replay failed", 
                        episode_id=episode_id, 
                        error=str(e))
            raise
        
        replay_duration = time.time() - replay_start
        total_steps = len(episode.steps)
        
        # Calculate replay statistics
        replay_stats = {
            "episode_id": episode_id,
            "tenant_id": str(tenant_id),
            "workflow": episode.workflow,
            "replay_duration": replay_duration,
            "original_duration": episode.end_time - episode.start_time if episode.end_time else 0,
            "total_steps": total_steps,
            "success_count": success_count,
            "error_count": error_count,
            "success_rate": success_count / total_steps if total_steps > 0 else 0,
            "steps": replay_steps,
            "timestamp": time.time()
        }
        
        self.replay_results[episode_id] = replay_stats
        
        logger.info("Episode replay completed", 
                   episode_id=episode_id, 
                   success_rate=replay_stats["success_rate"])
        
        return replay_stats
    
    def get_replay_result(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """Get replay result by episode ID."""
        return self.replay_results.get(episode_id)
    
    def get_all_replay_results(self) -> Dict[str, Dict[str, Any]]:
        """Get all replay results."""
        return self.replay_results
    
    def compare_episodes(
        self,
        episode_id: str,
        tolerance: float = 0.1
    ) -> Dict[str, Any]:
        """Compare original episode with replay."""
        episode = self.recorder.get_episode(episode_id)
        replay_result = self.get_replay_result(episode_id)
        
        if not episode or not replay_result:
            raise ValueError("Episode or replay result not found")
        
        comparison = {
            "episode_id": episode_id,
            "duration_match": abs(
                replay_result["replay_duration"] - replay_result["original_duration"]
            ) <= tolerance,
            "step_count_match": len(episode.steps) == len(replay_result["steps"]),
            "success_rate_match": abs(
                replay_result["success_rate"] - 
                sum(1 for step in episode.steps if step.success) / len(episode.steps)
            ) <= tolerance,
            "step_comparisons": []
        }
        
        # Compare individual steps
        for i, (original_step, replay_step) in enumerate(
            zip(episode.steps, replay_result["steps"])
        ):
            step_comparison = {
                "step_index": i,
                "step_id": original_step.step_id,
                "action_match": original_step.action == replay_step["action"],
                "success_match": original_step.success == replay_step["success"],
                "duration_match": abs(
                    original_step.duration - replay_step["duration"]
                ) <= tolerance,
                "input_match": original_step.input_data == replay_step["input_data"]
            }
            
            comparison["step_comparisons"].append(step_comparison)
        
        return comparison


# Global instances
episode_recorder = EpisodeRecorder()
episode_replayer = EpisodeReplayer(episode_recorder)
