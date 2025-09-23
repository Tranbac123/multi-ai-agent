"""Enhanced episode replay system for reproducing runs with frozen configurations."""

import asyncio
import json
import time
import uuid
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import structlog
import redis.asyncio as redis
from datetime import datetime, timezone

logger = structlog.get_logger(__name__)


class ReplayStatus(Enum):
    """Episode replay status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReplayMode(Enum):
    """Replay mode."""

    EXACT = "exact"  # Exact reproduction with same model/prompt/tools
    SIMILAR = "similar"  # Similar reproduction with updated versions
    ADAPTIVE = "adaptive"  # Adaptive reproduction with current best config


@dataclass
class EpisodeConfig:
    """Episode configuration for replay."""

    episode_id: str
    model_version: str
    prompt_version: str
    tool_versions: Dict[str, str]
    router_config: Dict[str, Any]
    tenant_config: Dict[str, Any]
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EpisodeStep:
    """Episode step for replay."""

    step_id: str
    step_type: str  # "input", "router_decision", "tool_call", "response"
    timestamp: datetime
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    duration_ms: int
    success: bool
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Episode:
    """Complete episode for replay."""

    episode_id: str
    tenant_id: str
    session_id: str
    config: EpisodeConfig
    steps: List[EpisodeStep] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    status: ReplayStatus = ReplayStatus.PENDING
    total_duration_ms: int = 0
    success_count: int = 0
    failure_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class EpisodeReplayEngine:
    """Enhanced episode replay engine."""

    def __init__(self, redis_client: redis.Redis, storage_path: str = "eval/episodes"):
        self.redis = redis_client
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.active_replays: Dict[str, Episode] = {}

    async def record_episode(
        self,
        tenant_id: str,
        session_id: str,
        config: EpisodeConfig,
        steps: List[EpisodeStep],
    ) -> str:
        """Record an episode for later replay."""
        episode_id = str(uuid.uuid4())

        episode = Episode(
            episode_id=episode_id,
            tenant_id=tenant_id,
            session_id=session_id,
            config=config,
            steps=steps,
        )

        # Calculate episode metrics
        episode.total_duration_ms = sum(step.duration_ms for step in steps)
        episode.success_count = sum(1 for step in steps if step.success)
        episode.failure_count = len(steps) - episode.success_count
        episode.status = ReplayStatus.COMPLETED
        episode.end_time = datetime.now(timezone.utc)

        # Store episode
        await self._store_episode(episode)

        logger.info(
            "Episode recorded",
            episode_id=episode_id,
            tenant_id=tenant_id,
            step_count=len(steps),
            duration_ms=episode.total_duration_ms,
        )

        return episode_id

    async def replay_episode(
        self,
        episode_id: str,
        mode: ReplayMode = ReplayMode.EXACT,
        target_tenant_id: Optional[str] = None,
    ) -> Episode:
        """Replay an episode with specified mode."""
        # Load episode
        episode = await self._load_episode(episode_id)
        if not episode:
            raise ValueError(f"Episode {episode_id} not found")

        # Create replay episode
        replay_episode = Episode(
            episode_id=f"replay_{episode_id}_{int(time.time())}",
            tenant_id=target_tenant_id or episode.tenant_id,
            session_id=f"replay_{episode.session_id}",
            config=episode.config,
            status=ReplayStatus.RUNNING,
        )

        self.active_replays[replay_episode.episode_id] = replay_episode

        try:
            logger.info(
                "Starting episode replay",
                episode_id=episode_id,
                replay_id=replay_episode.episode_id,
                mode=mode.value,
            )

            # Replay steps
            for step in episode.steps:
                try:
                    replayed_step = await self._replay_step(step, mode, replay_episode)
                    replay_episode.steps.append(replayed_step)

                    if replayed_step.success:
                        replay_episode.success_count += 1
                    else:
                        replay_episode.failure_count += 1

                except Exception as e:
                    logger.error(
                        "Step replay failed", step_id=step.step_id, error=str(e)
                    )

                    # Create failed step
                    failed_step = EpisodeStep(
                        step_id=f"replay_{step.step_id}",
                        step_type=step.step_type,
                        timestamp=datetime.now(timezone.utc),
                        input_data=step.input_data,
                        output_data={},
                        duration_ms=0,
                        success=False,
                        error_message=str(e),
                    )
                    replay_episode.steps.append(failed_step)
                    replay_episode.failure_count += 1

            # Complete replay
            replay_episode.status = ReplayStatus.COMPLETED
            replay_episode.end_time = datetime.now(timezone.utc)
            replay_episode.total_duration_ms = sum(
                step.duration_ms for step in replay_episode.steps
            )

            # Store replay episode
            await self._store_episode(replay_episode)

            logger.info(
                "Episode replay completed",
                episode_id=episode_id,
                replay_id=replay_episode.episode_id,
                success_count=replay_episode.success_count,
                failure_count=replay_episode.failure_count,
            )

            return replay_episode

        except Exception as e:
            logger.error("Episode replay failed", episode_id=episode_id, error=str(e))

            replay_episode.status = ReplayStatus.FAILED
            replay_episode.end_time = datetime.now(timezone.utc)
            await self._store_episode(replay_episode)

            raise
        finally:
            # Clean up active replay
            if replay_episode.episode_id in self.active_replays:
                del self.active_replays[replay_episode.episode_id]

    async def _replay_step(
        self, original_step: EpisodeStep, mode: ReplayMode, replay_episode: Episode
    ) -> EpisodeStep:
        """Replay a single step."""
        start_time = time.time()

        try:
            # Create replay step
            replay_step = EpisodeStep(
                step_id=f"replay_{original_step.step_id}",
                step_type=original_step.step_type,
                timestamp=datetime.now(timezone.utc),
                input_data=original_step.input_data.copy(),
                output_data={},
                duration_ms=0,
                success=False,
            )

            # Replay based on step type and mode
            if original_step.step_type == "input":
                replay_step.output_data = await self._replay_input_step(
                    original_step, mode
                )

            elif original_step.step_type == "router_decision":
                replay_step.output_data = await self._replay_router_step(
                    original_step, mode
                )

            elif original_step.step_type == "tool_call":
                replay_step.output_data = await self._replay_tool_step(
                    original_step, mode
                )

            elif original_step.step_type == "response":
                replay_step.output_data = await self._replay_response_step(
                    original_step, mode
                )

            else:
                raise ValueError(f"Unknown step type: {original_step.step_type}")

            # Calculate duration
            replay_step.duration_ms = int((time.time() - start_time) * 1000)
            replay_step.success = True

            return replay_step

        except Exception as e:
            logger.error(
                "Step replay failed",
                step_id=original_step.step_id,
                step_type=original_step.step_type,
                error=str(e),
            )

            replay_step.duration_ms = int((time.time() - start_time) * 1000)
            replay_step.error_message = str(e)
            replay_step.success = False

            return replay_step

    async def _replay_input_step(
        self, original_step: EpisodeStep, mode: ReplayMode
    ) -> Dict[str, Any]:
        """Replay input processing step."""
        if mode == ReplayMode.EXACT:
            # Exact reproduction - return original output
            return original_step.output_data.copy()

        elif mode == ReplayMode.SIMILAR:
            # Similar reproduction - process with current input processor
            # This would call the actual input processing service
            return {
                "processed_input": original_step.input_data.get("input_text", ""),
                "intent": original_step.output_data.get("intent", "unknown"),
                "confidence": original_step.output_data.get("confidence", 0.0),
                "metadata": original_step.output_data.get("metadata", {}),
            }

        else:  # ADAPTIVE
            # Adaptive reproduction - use current best configuration
            return await self._adaptive_input_processing(original_step)

    async def _replay_router_step(
        self, original_step: EpisodeStep, mode: ReplayMode
    ) -> Dict[str, Any]:
        """Replay router decision step."""
        if mode == ReplayMode.EXACT:
            return original_step.output_data.copy()

        elif mode == ReplayMode.SIMILAR:
            # Use current router with similar configuration
            return {
                "selected_tier": original_step.output_data.get(
                    "selected_tier", "SLM_A"
                ),
                "confidence": original_step.output_data.get("confidence", 0.0),
                "reasoning": original_step.output_data.get("reasoning", ""),
                "features": original_step.output_data.get("features", {}),
            }

        else:  # ADAPTIVE
            return await self._adaptive_router_decision(original_step)

    async def _replay_tool_step(
        self, original_step: EpisodeStep, mode: ReplayMode
    ) -> Dict[str, Any]:
        """Replay tool call step."""
        if mode == ReplayMode.EXACT:
            return original_step.output_data.copy()

        elif mode == ReplayMode.SIMILAR:
            # Use current tool versions
            return {
                "tool_name": original_step.output_data.get("tool_name", ""),
                "result": original_step.output_data.get("result", {}),
                "success": original_step.output_data.get("success", False),
                "duration_ms": original_step.output_data.get("duration_ms", 0),
            }

        else:  # ADAPTIVE
            return await self._adaptive_tool_call(original_step)

    async def _replay_response_step(
        self, original_step: EpisodeStep, mode: ReplayMode
    ) -> Dict[str, Any]:
        """Replay response generation step."""
        if mode == ReplayMode.EXACT:
            return original_step.output_data.copy()

        elif mode == ReplayMode.SIMILAR:
            # Use current response generator
            return {
                "response_text": original_step.output_data.get("response_text", ""),
                "metadata": original_step.output_data.get("metadata", {}),
                "tokens_used": original_step.output_data.get("tokens_used", 0),
            }

        else:  # ADAPTIVE
            return await self._adaptive_response_generation(original_step)

    async def _adaptive_input_processing(
        self, original_step: EpisodeStep
    ) -> Dict[str, Any]:
        """Adaptive input processing with current best configuration."""
        # This would use the current best input processing configuration
        return {
            "processed_input": original_step.input_data.get("input_text", ""),
            "intent": "adaptive_intent",
            "confidence": 0.9,
            "metadata": {"adaptive": True},
        }

    async def _adaptive_router_decision(
        self, original_step: EpisodeStep
    ) -> Dict[str, Any]:
        """Adaptive router decision with current best configuration."""
        # This would use the current best router configuration
        return {
            "selected_tier": "SLM_B",
            "confidence": 0.85,
            "reasoning": "Adaptive routing based on current best practices",
            "features": {"adaptive": True},
        }

    async def _adaptive_tool_call(self, original_step: EpisodeStep) -> Dict[str, Any]:
        """Adaptive tool call with current best configuration."""
        # This would use the current best tool configuration
        return {
            "tool_name": original_step.output_data.get("tool_name", ""),
            "result": {"adaptive": True},
            "success": True,
            "duration_ms": 100,
        }

    async def _adaptive_response_generation(
        self, original_step: EpisodeStep
    ) -> Dict[str, Any]:
        """Adaptive response generation with current best configuration."""
        # This would use the current best response generation configuration
        return {
            "response_text": "Adaptive response based on current best practices",
            "metadata": {"adaptive": True},
            "tokens_used": 50,
        }

    async def _store_episode(self, episode: Episode) -> None:
        """Store episode to Redis and file system."""
        try:
            # Store in Redis
            episode_key = f"episode:{episode.episode_id}"
            episode_data = {
                "episode_id": episode.episode_id,
                "tenant_id": episode.tenant_id,
                "session_id": episode.session_id,
                "config": {
                    "episode_id": episode.config.episode_id,
                    "model_version": episode.config.model_version,
                    "prompt_version": episode.config.prompt_version,
                    "tool_versions": episode.config.tool_versions,
                    "router_config": episode.config.router_config,
                    "tenant_config": episode.config.tenant_config,
                    "timestamp": episode.config.timestamp.isoformat(),
                    "metadata": episode.config.metadata,
                },
                "steps": [
                    {
                        "step_id": step.step_id,
                        "step_type": step.step_type,
                        "timestamp": step.timestamp.isoformat(),
                        "input_data": step.input_data,
                        "output_data": step.output_data,
                        "duration_ms": step.duration_ms,
                        "success": step.success,
                        "error_message": step.error_message,
                        "metadata": step.metadata,
                    }
                    for step in episode.steps
                ],
                "start_time": episode.start_time.isoformat(),
                "end_time": episode.end_time.isoformat() if episode.end_time else None,
                "status": episode.status.value,
                "total_duration_ms": episode.total_duration_ms,
                "success_count": episode.success_count,
                "failure_count": episode.failure_count,
                "metadata": episode.metadata,
            }

            await self.redis.setex(
                episode_key, 86400, json.dumps(episode_data)
            )  # 24 hours TTL

            # Store in file system
            episode_file = self.storage_path / f"{episode.episode_id}.json"
            with open(episode_file, "w") as f:
                json.dump(episode_data, f, indent=2)

            logger.info(
                "Episode stored",
                episode_id=episode.episode_id,
                redis_key=episode_key,
                file_path=str(episode_file),
            )

        except Exception as e:
            logger.error(
                "Failed to store episode", episode_id=episode.episode_id, error=str(e)
            )
            raise

    async def _load_episode(self, episode_id: str) -> Optional[Episode]:
        """Load episode from Redis or file system."""
        try:
            # Try Redis first
            episode_key = f"episode:{episode_id}"
            episode_data = await self.redis.get(episode_key)

            if not episode_data:
                # Try file system
                episode_file = self.storage_path / f"{episode_id}.json"
                if episode_file.exists():
                    with open(episode_file, "r") as f:
                        episode_data = f.read()
                else:
                    return None

            data = json.loads(episode_data)

            # Reconstruct episode
            config = EpisodeConfig(
                episode_id=data["config"]["episode_id"],
                model_version=data["config"]["model_version"],
                prompt_version=data["config"]["prompt_version"],
                tool_versions=data["config"]["tool_versions"],
                router_config=data["config"]["router_config"],
                tenant_config=data["config"]["tenant_config"],
                timestamp=datetime.fromisoformat(data["config"]["timestamp"]),
                metadata=data["config"]["metadata"],
            )

            episode = Episode(
                episode_id=data["episode_id"],
                tenant_id=data["tenant_id"],
                session_id=data["session_id"],
                config=config,
                start_time=datetime.fromisoformat(data["start_time"]),
                end_time=datetime.fromisoformat(data["end_time"])
                if data["end_time"]
                else None,
                status=ReplayStatus(data["status"]),
                total_duration_ms=data["total_duration_ms"],
                success_count=data["success_count"],
                failure_count=data["failure_count"],
                metadata=data["metadata"],
            )

            # Reconstruct steps
            for step_data in data["steps"]:
                step = EpisodeStep(
                    step_id=step_data["step_id"],
                    step_type=step_data["step_type"],
                    timestamp=datetime.fromisoformat(step_data["timestamp"]),
                    input_data=step_data["input_data"],
                    output_data=step_data["output_data"],
                    duration_ms=step_data["duration_ms"],
                    success=step_data["success"],
                    error_message=step_data["error_message"],
                    metadata=step_data["metadata"],
                )
                episode.steps.append(step)

            return episode

        except Exception as e:
            logger.error("Failed to load episode", episode_id=episode_id, error=str(e))
            return None

    async def get_episode_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get episode statistics for tenant."""
        try:
            # Get all episodes for tenant
            pattern = f"episode:*"
            keys = await self.redis.keys(pattern)

            episodes = []
            for key in keys:
                episode_data = await self.redis.get(key)
                if episode_data:
                    data = json.loads(episode_data)
                    if data.get("tenant_id") == tenant_id:
                        episodes.append(data)

            if not episodes:
                return {
                    "total_episodes": 0,
                    "success_rate": 0.0,
                    "average_duration_ms": 0,
                    "episodes_by_status": {},
                    "episodes_by_category": {},
                }

            # Calculate statistics
            total_episodes = len(episodes)
            successful_episodes = len(
                [e for e in episodes if e["status"] == "completed"]
            )
            success_rate = (
                successful_episodes / total_episodes if total_episodes > 0 else 0.0
            )

            durations = [
                e["total_duration_ms"] for e in episodes if e["total_duration_ms"]
            ]
            average_duration = sum(durations) / len(durations) if durations else 0

            status_counts = {}
            for episode in episodes:
                status = episode["status"]
                status_counts[status] = status_counts.get(status, 0) + 1

            return {
                "total_episodes": total_episodes,
                "success_rate": success_rate,
                "average_duration_ms": average_duration,
                "episodes_by_status": status_counts,
                "episodes_by_category": {},  # Would need category tracking
            }

        except Exception as e:
            logger.error(
                "Failed to get episode stats", tenant_id=tenant_id, error=str(e)
            )
            return {}

    async def cleanup_old_episodes(self, days: int = 30) -> int:
        """Clean up episodes older than specified days."""
        try:
            cutoff_time = datetime.now(timezone.utc).timestamp() - (days * 24 * 60 * 60)
            cleaned_count = 0

            # Clean Redis
            pattern = f"episode:*"
            keys = await self.redis.keys(pattern)

            for key in keys:
                episode_data = await self.redis.get(key)
                if episode_data:
                    data = json.loads(episode_data)
                    episode_time = datetime.fromisoformat(
                        data["start_time"]
                    ).timestamp()

                    if episode_time < cutoff_time:
                        await self.redis.delete(key)
                        cleaned_count += 1

            # Clean file system
            for episode_file in self.storage_path.glob("*.json"):
                if episode_file.stat().st_mtime < cutoff_time:
                    episode_file.unlink()
                    cleaned_count += 1

            logger.info(
                "Episode cleanup completed", days=days, cleaned_count=cleaned_count
            )

            return cleaned_count

        except Exception as e:
            logger.error("Episode cleanup failed", days=days, error=str(e))
            return 0


if __name__ == "__main__":
    # Example usage
    async def main():
        redis_client = redis.from_url("redis://localhost:6379")
        engine = EpisodeReplayEngine(redis_client)

        # Example episode recording
        config = EpisodeConfig(
            episode_id="test_episode",
            model_version="gpt-4-1106-preview",
            prompt_version="v1.2",
            tool_versions={"knowledge_base": "v2.1", "crm": "v1.5"},
            router_config={"threshold": 0.8},
            tenant_config={"tier": "premium"},
            timestamp=datetime.now(timezone.utc),
        )

        steps = [
            EpisodeStep(
                step_id="step_1",
                step_type="input",
                timestamp=datetime.now(timezone.utc),
                input_data={"input_text": "What are your business hours?"},
                output_data={"intent": "business_hours", "confidence": 0.9},
                duration_ms=100,
                success=True,
            )
        ]

        episode_id = await engine.record_episode(
            "tenant_123", "session_456", config, steps
        )
        print(f"Recorded episode: {episode_id}")

        # Example episode replay
        replay_episode = await engine.replay_episode(episode_id, ReplayMode.SIMILAR)
        print(f"Replayed episode: {replay_episode.episode_id}")

        await redis_client.close()

    asyncio.run(main())
