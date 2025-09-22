"""Chaos tests for orchestrator failure recovery and episode replay."""

import pytest
import asyncio
import time
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from tests.chaos import ChaosEventType, EpisodeStatus, ReplayStatus, Episode, Task
from tests._fixtures.factories import factory, TenantTier


class MockOrchestrator:
    """Mock orchestrator for chaos testing."""
    
    def __init__(self):
        self.episodes: Dict[str, Episode] = {}
        self.tasks: Dict[str, Task] = {}
        self.is_running = True
        self.failure_probability = 0.0
        self.current_episode_id: Optional[str] = None
    
    async def start_episode(self, tenant_id: str, user_id: str, workflow_spec: Dict[str, Any]) -> str:
        """Start a new episode."""
        episode_id = f"episode_{uuid.uuid4().hex[:8]}"
        
        episode = Episode(
            episode_id=episode_id,
            tenant_id=tenant_id,
            user_id=user_id,
            workflow_spec=workflow_spec,
            model_version="gpt-4-turbo-2024-04-09",
            prompt_version="v1.2.3",
            tool_versions={"payment": "v2.1.0", "email": "v1.5.2"},
            status=EpisodeStatus.PENDING,
            started_at=datetime.now(),
            completed_at=None,
            final_state=None,
            failure_point=None,
            replay_status=ReplayStatus.NOT_REPLAYED,
            metadata={"chaos_test": True}
        )
        
        self.episodes[episode_id] = episode
        self.current_episode_id = episode_id
        
        return episode_id
    
    async def execute_episode(self, episode_id: str) -> Dict[str, Any]:
        """Execute episode with potential failure."""
        episode = self.episodes.get(episode_id)
        if not episode:
            raise ValueError(f"Episode {episode_id} not found")
        
        episode.status = EpisodeStatus.RUNNING
        
        try:
            # Simulate episode execution steps
            steps = episode.workflow_spec.get("steps", [])
            final_state = {}
            
            for i, step in enumerate(steps):
                # Simulate step execution
                await asyncio.sleep(0.1)  # Simulate work
                
                # Check for orchestrator failure
                if not self.is_running:
                    episode.status = EpisodeStatus.INTERRUPTED
                    episode.failure_point = f"step_{i}"
                    raise Exception("Orchestrator failure during execution")
                
                # Simulate random failure
                import random
                if random.random() < self.failure_probability:
                    episode.status = EpisodeStatus.INTERRUPTED
                    episode.failure_point = f"step_{i}"
                    raise Exception(f"Random failure at step {i}")
                
                # Create task record
                task_id = f"task_{episode_id}_{i}"
                task = Task(
                    task_id=task_id,
                    episode_id=episode_id,
                    step_name=step.get("name", f"step_{i}"),
                    input_data=step.get("input", {}),
                    output_data={"result": f"output_{i}"},
                    status="completed",
                    started_at=datetime.now(),
                    completed_at=datetime.now(),
                    error_message=None
                )
                
                self.tasks[task_id] = task
                final_state[f"step_{i}"] = task.output_data
            
            # Episode completed successfully
            episode.status = EpisodeStatus.COMPLETED
            episode.completed_at = datetime.now()
            episode.final_state = final_state
            
            return {"status": "completed", "episode_id": episode_id, "final_state": final_state}
            
        except Exception as e:
            episode.status = EpisodeStatus.INTERRUPTED
            episode.failure_point = episode.failure_point or "unknown"
            episode.error_message = str(e)
            raise e
    
    async def stop_orchestrator(self):
        """Stop the orchestrator (simulate failure)."""
        self.is_running = False
    
    async def restart_orchestrator(self):
        """Restart the orchestrator."""
        self.is_running = True
    
    async def get_episode(self, episode_id: str) -> Optional[Episode]:
        """Get episode by ID."""
        return self.episodes.get(episode_id)
    
    async def get_episode_tasks(self, episode_id: str) -> List[Task]:
        """Get all tasks for an episode."""
        return [task for task in self.tasks.values() if task.episode_id == episode_id]


class MockReplayService:
    """Mock replay service for episode replay testing."""
    
    def __init__(self, orchestrator: MockOrchestrator):
        self.orchestrator = orchestrator
        self.replay_log: List[Dict[str, Any]] = []
    
    async def replay_episode(self, episode_id: str) -> Dict[str, Any]:
        """Replay an episode with frozen model/prompt/tool versions."""
        original_episode = await self.orchestrator.get_episode(episode_id)
        if not original_episode:
            raise ValueError(f"Episode {episode_id} not found")
        
        if original_episode.status != EpisodeStatus.INTERRUPTED:
            raise ValueError(f"Episode {episode_id} is not in interrupted state")
        
        # Mark as replaying
        original_episode.replay_status = ReplayStatus.REPLAYING
        
        try:
            # Create replay episode with same versions
            replay_episode_id = f"replay_{episode_id}"
            replay_episode = Episode(
                episode_id=replay_episode_id,
                tenant_id=original_episode.tenant_id,
                user_id=original_episode.user_id,
                workflow_spec=original_episode.workflow_spec,
                model_version=original_episode.model_version,  # Frozen version
                prompt_version=original_episode.prompt_version,  # Frozen version
                tool_versions=original_episode.tool_versions.copy(),  # Frozen versions
                status=EpisodeStatus.REPLAYING,
                started_at=datetime.now(),
                completed_at=None,
                final_state=None,
                failure_point=None,
                replay_status=ReplayStatus.REPLAYING,
                metadata={
                    **original_episode.metadata,
                    "replay_of": episode_id,
                    "replay_started_at": datetime.now().isoformat()
                }
            )
            
            self.orchestrator.episodes[replay_episode_id] = replay_episode
            
            # Execute replay episode
            result = await self.orchestrator.execute_episode(replay_episode_id)
            
            # Mark original episode as successfully replayed
            original_episode.replay_status = ReplayStatus.REPLAYED_SUCCESS
            
            # Log replay
            self.replay_log.append({
                "original_episode_id": episode_id,
                "replay_episode_id": replay_episode_id,
                "replay_status": "success",
                "timestamp": datetime.now()
            })
            
            return result
            
        except Exception as e:
            # Mark original episode as failed replay
            original_episode.replay_status = ReplayStatus.REPLAYED_FAILURE
            
            # Log failed replay
            self.replay_log.append({
                "original_episode_id": episode_id,
                "replay_episode_id": replay_episode_id if 'replay_episode_id' in locals() else None,
                "replay_status": "failure",
                "error": str(e),
                "timestamp": datetime.now()
            })
            
            raise e
    
    async def get_replay_log(self) -> List[Dict[str, Any]]:
        """Get replay execution log."""
        return self.replay_log


class TestOrchestratorFailureRecovery:
    """Test orchestrator failure recovery and episode replay."""
    
    @pytest.fixture
    def mock_orchestrator(self):
        """Create mock orchestrator."""
        return MockOrchestrator()
    
    @pytest.fixture
    def mock_replay_service(self, mock_orchestrator):
        """Create mock replay service."""
        return MockReplayService(mock_orchestrator)
    
    @pytest.fixture
    def sample_workflow_spec(self):
        """Create sample workflow specification."""
        return {
            "name": "test_workflow",
            "steps": [
                {"name": "step_1", "action": "process_input", "input": {"data": "input_1"}},
                {"name": "step_2", "action": "call_llm", "input": {"prompt": "test_prompt"}},
                {"name": "step_3", "action": "process_output", "input": {"result": "llm_result"}},
                {"name": "step_4", "action": "finalize", "input": {"output": "final_result"}}
            ]
        }
    
    @pytest.mark.asyncio
    async def test_episode_execution_success(self, mock_orchestrator, sample_workflow_spec):
        """Test successful episode execution."""
        # Start episode
        episode_id = await mock_orchestrator.start_episode(
            "tenant_1234",
            "user_1234",
            sample_workflow_spec
        )
        
        # Execute episode
        result = await mock_orchestrator.execute_episode(episode_id)
        
        # Validate success
        assert result["status"] == "completed"
        assert result["episode_id"] == episode_id
        
        # Check episode state
        episode = await mock_orchestrator.get_episode(episode_id)
        assert episode.status == EpisodeStatus.COMPLETED
        assert episode.completed_at is not None
        assert episode.final_state is not None
        assert len(episode.final_state) == 4  # 4 steps
        
        # Check tasks
        tasks = await mock_orchestrator.get_episode_tasks(episode_id)
        assert len(tasks) == 4
        for task in tasks:
            assert task.status == "completed"
            assert task.completed_at is not None
    
    @pytest.mark.asyncio
    async def test_orchestrator_failure_during_execution(self, mock_orchestrator, sample_workflow_spec):
        """Test orchestrator failure during episode execution."""
        # Start episode
        episode_id = await mock_orchestrator.start_episode(
            "tenant_1234",
            "user_1234",
            sample_workflow_spec
        )
        
        # Start execution in background
        execution_task = asyncio.create_task(
            mock_orchestrator.execute_episode(episode_id)
        )
        
        # Stop orchestrator during execution
        await asyncio.sleep(0.05)  # Let it start
        await mock_orchestrator.stop_orchestrator()
        
        # Wait for execution to complete (should fail)
        with pytest.raises(Exception, match="Orchestrator failure during execution"):
            await execution_task
        
        # Check episode state
        episode = await mock_orchestrator.get_episode(episode_id)
        assert episode.status == EpisodeStatus.INTERRUPTED
        assert episode.failure_point is not None
        assert episode.completed_at is None
    
    @pytest.mark.asyncio
    async def test_episode_replay_identical_outcome(self, mock_orchestrator, mock_replay_service, sample_workflow_spec):
        """Test episode replay produces identical outcome."""
        # Start and interrupt episode
        episode_id = await mock_orchestrator.start_episode(
            "tenant_1234",
            "user_1234",
            sample_workflow_spec
        )
        
        # Start execution and stop orchestrator
        execution_task = asyncio.create_task(
            mock_orchestrator.execute_episode(episode_id)
        )
        await asyncio.sleep(0.05)
        await mock_orchestrator.stop_orchestrator()
        
        try:
            await execution_task
        except Exception:
            pass  # Expected failure
        
        # Restart orchestrator
        await mock_orchestrator.restart_orchestrator()
        
        # Replay episode
        replay_result = await mock_replay_service.replay_episode(episode_id)
        
        # Validate replay success
        assert replay_result["status"] == "completed"
        
        # Check original episode
        original_episode = await mock_orchestrator.get_episode(episode_id)
        assert original_episode.replay_status == ReplayStatus.REPLAYED_SUCCESS
        
        # Check replay log
        replay_log = await mock_replay_service.get_replay_log()
        assert len(replay_log) == 1
        assert replay_log[0]["replay_status"] == "success"
    
    @pytest.mark.asyncio
    async def test_multiple_replay_attempts(self, mock_orchestrator, mock_replay_service, sample_workflow_spec):
        """Test multiple replay attempts for failed episodes."""
        # Create multiple interrupted episodes
        episode_ids = []
        for i in range(3):
            episode_id = await mock_orchestrator.start_episode(
                f"tenant_123{i}",
                f"user_123{i}",
                sample_workflow_spec
            )
            
            # Interrupt execution
            execution_task = asyncio.create_task(
                mock_orchestrator.execute_episode(episode_id)
            )
            await asyncio.sleep(0.05)
            await mock_orchestrator.stop_orchestrator()
            
            try:
                await execution_task
            except Exception:
                pass
            
            episode_ids.append(episode_id)
            await mock_orchestrator.restart_orchestrator()
        
        # Replay all episodes
        for episode_id in episode_ids:
            replay_result = await mock_replay_service.replay_episode(episode_id)
            assert replay_result["status"] == "completed"
        
        # Check replay log
        replay_log = await mock_replay_service.get_replay_log()
        assert len(replay_log) == 3
        for log_entry in replay_log:
            assert log_entry["replay_status"] == "success"
    
    @pytest.mark.asyncio
    async def test_replay_with_frozen_versions(self, mock_orchestrator, mock_replay_service, sample_workflow_spec):
        """Test replay uses frozen model/prompt/tool versions."""
        # Start and interrupt episode
        episode_id = await mock_orchestrator.start_episode(
            "tenant_1234",
            "user_1234",
            sample_workflow_spec
        )
        
        # Interrupt execution
        execution_task = asyncio.create_task(
            mock_orchestrator.execute_episode(episode_id)
        )
        await asyncio.sleep(0.05)
        await mock_orchestrator.stop_orchestrator()
        
        try:
            await execution_task
        except Exception:
            pass
        
        await mock_orchestrator.restart_orchestrator()
        
        # Replay episode
        await mock_replay_service.replay_episode(episode_id)
        
        # Get original and replay episodes
        original_episode = await mock_orchestrator.get_episode(episode_id)
        replay_episode_id = f"replay_{episode_id}"
        replay_episode = await mock_orchestrator.get_episode(replay_episode_id)
        
        # Validate frozen versions
        assert replay_episode.model_version == original_episode.model_version
        assert replay_episode.prompt_version == original_episode.prompt_version
        assert replay_episode.tool_versions == original_episode.tool_versions
        assert replay_episode.metadata["replay_of"] == episode_id
    
    @pytest.mark.asyncio
    async def test_random_failure_simulation(self, mock_orchestrator, sample_workflow_spec):
        """Test random failure simulation during execution."""
        # Set high failure probability
        mock_orchestrator.failure_probability = 0.5
        
        success_count = 0
        failure_count = 0
        
        # Run multiple episodes
        for i in range(10):
            episode_id = await mock_orchestrator.start_episode(
                f"tenant_123{i}",
                f"user_123{i}",
                sample_workflow_spec
            )
            
            try:
                await mock_orchestrator.execute_episode(episode_id)
                success_count += 1
            except Exception:
                failure_count += 1
        
        # Should have both successes and failures
        assert success_count > 0
        assert failure_count > 0
        assert success_count + failure_count == 10
    
    @pytest.mark.asyncio
    async def test_episode_state_persistence(self, mock_orchestrator, sample_workflow_spec):
        """Test episode state persistence across orchestrator restarts."""
        # Start episode
        episode_id = await mock_orchestrator.start_episode(
            "tenant_1234",
            "user_1234",
            sample_workflow_spec
        )
        
        # Start execution and stop orchestrator
        execution_task = asyncio.create_task(
            mock_orchestrator.execute_episode(episode_id)
        )
        await asyncio.sleep(0.05)
        await mock_orchestrator.stop_orchestrator()
        
        try:
            await execution_task
        except Exception:
            pass
        
        # Check episode state is preserved
        episode = await mock_orchestrator.get_episode(episode_id)
        assert episode.status == EpisodeStatus.INTERRUPTED
        assert episode.failure_point is not None
        
        # Restart orchestrator
        await mock_orchestrator.restart_orchestrator()
        
        # Episode state should still be preserved
        episode_after_restart = await mock_orchestrator.get_episode(episode_id)
        assert episode_after_restart.status == EpisodeStatus.INTERRUPTED
        assert episode_after_restart.failure_point == episode.failure_point
    
    @pytest.mark.asyncio
    async def test_concurrent_episode_execution(self, mock_orchestrator, sample_workflow_spec):
        """Test concurrent episode execution and failure handling."""
        # Start multiple episodes concurrently
        episode_ids = []
        execution_tasks = []
        
        for i in range(5):
            episode_id = await mock_orchestrator.start_episode(
                f"tenant_123{i}",
                f"user_123{i}",
                sample_workflow_spec
            )
            episode_ids.append(episode_id)
            
            # Start execution
            task = asyncio.create_task(
                mock_orchestrator.execute_episode(episode_id)
            )
            execution_tasks.append(task)
        
        # Stop orchestrator during execution
        await asyncio.sleep(0.05)
        await mock_orchestrator.stop_orchestrator()
        
        # Wait for all executions to complete (should fail)
        results = await asyncio.gather(*execution_tasks, return_exceptions=True)
        
        # All should have failed
        for result in results:
            assert isinstance(result, Exception)
        
        # Check all episodes are interrupted
        for episode_id in episode_ids:
            episode = await mock_orchestrator.get_episode(episode_id)
            assert episode.status == EpisodeStatus.INTERRUPTED
    
    @pytest.mark.asyncio
    async def test_replay_metadata_consistency(self, mock_orchestrator, mock_replay_service, sample_workflow_spec):
        """Test replay metadata consistency and tracking."""
        # Start and interrupt episode
        episode_id = await mock_orchestrator.start_episode(
            "tenant_1234",
            "user_1234",
            sample_workflow_spec
        )
        
        # Add custom metadata
        episode = await mock_orchestrator.get_episode(episode_id)
        episode.metadata["custom_field"] = "custom_value"
        episode.metadata["test_run"] = "chaos_test_001"
        
        # Interrupt execution
        execution_task = asyncio.create_task(
            mock_orchestrator.execute_episode(episode_id)
        )
        await asyncio.sleep(0.05)
        await mock_orchestrator.stop_orchestrator()
        
        try:
            await execution_task
        except Exception:
            pass
        
        await mock_orchestrator.restart_orchestrator()
        
        # Replay episode
        await mock_replay_service.replay_episode(episode_id)
        
        # Check replay metadata
        replay_episode_id = f"replay_{episode_id}"
        replay_episode = await mock_orchestrator.get_episode(replay_episode_id)
        
        # Original metadata should be preserved
        assert replay_episode.metadata["custom_field"] == "custom_value"
        assert replay_episode.metadata["test_run"] == "chaos_test_001"
        assert replay_episode.metadata["chaos_test"] is True
        
        # Replay-specific metadata should be added
        assert "replay_of" in replay_episode.metadata
        assert "replay_started_at" in replay_episode.metadata