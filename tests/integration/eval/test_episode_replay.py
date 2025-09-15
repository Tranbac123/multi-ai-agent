"""Test episode replay functionality."""

import pytest
import asyncio
import json
import time
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone
from pathlib import Path

from eval.episode_replay import (
    EpisodeReplayEngine,
    EpisodeConfig,
    EpisodeStep,
    Episode,
    ReplayStatus,
    ReplayMode,
)


class TestEpisodeReplayEngine:
    """Test EpisodeReplayEngine functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis_client = Mock()
        redis_client.setex = AsyncMock()
        redis_client.get = AsyncMock()
        redis_client.keys = AsyncMock()
        redis_client.delete = AsyncMock()
        return redis_client

    @pytest.fixture
    def replay_engine(self, mock_redis):
        """Create EpisodeReplayEngine instance."""
        with patch('pathlib.Path.mkdir'):
            return EpisodeReplayEngine(mock_redis, "test_episodes")

    @pytest.fixture
    def sample_config(self):
        """Create sample episode configuration."""
        return EpisodeConfig(
            episode_id="test_episode_1",
            model_version="gpt-4-1106-preview",
            prompt_version="v1.2",
            tool_versions={"knowledge_base": "v2.1", "crm": "v1.5"},
            router_config={"threshold": 0.8},
            tenant_config={"tier": "premium"},
            timestamp=datetime.now(timezone.utc),
            metadata={"test": True}
        )

    @pytest.fixture
    def sample_steps(self):
        """Create sample episode steps."""
        return [
            EpisodeStep(
                step_id="step_1",
                step_type="input",
                timestamp=datetime.now(timezone.utc),
                input_data={"input_text": "What are your business hours?"},
                output_data={"intent": "business_hours", "confidence": 0.9},
                duration_ms=100,
                success=True,
                metadata={"processed": True}
            ),
            EpisodeStep(
                step_id="step_2",
                step_type="router_decision",
                timestamp=datetime.now(timezone.utc),
                input_data={"text_features": {"token_count": 6}},
                output_data={"selected_tier": "SLM_A", "confidence": 0.85},
                duration_ms=50,
                success=True
            ),
            EpisodeStep(
                step_id="step_3",
                step_type="tool_call",
                timestamp=datetime.now(timezone.utc),
                input_data={"tool_name": "knowledge_base", "query": "business hours"},
                output_data={"result": {"hours": "9 AM - 5 PM"}, "success": True},
                duration_ms=200,
                success=True
            ),
            EpisodeStep(
                step_id="step_4",
                step_type="response",
                timestamp=datetime.now(timezone.utc),
                input_data={"context": "business hours query"},
                output_data={"response_text": "Our business hours are 9 AM - 5 PM"},
                duration_ms=150,
                success=True
            )
        ]

    @pytest.mark.asyncio
    async def test_record_episode_success(self, replay_engine, sample_config, sample_steps):
        """Test successful episode recording."""
        tenant_id = "tenant_123"
        session_id = "session_456"
        
        episode_id = await replay_engine.record_episode(
            tenant_id, session_id, sample_config, sample_steps
        )
        
        # Verify episode ID was generated
        assert episode_id is not None
        assert len(episode_id) > 0
        
        # Verify Redis storage was called
        replay_engine.redis.setex.assert_called_once()
        call_args = replay_engine.redis.setex.call_args
        
        # Check Redis key format
        assert call_args[0][0].startswith("episode:")
        assert episode_id in call_args[0][0]
        
        # Check TTL
        assert call_args[0][1] == 86400  # 24 hours
        
        # Verify episode data structure
        episode_data = json.loads(call_args[0][2])
        assert episode_data["tenant_id"] == tenant_id
        assert episode_data["session_id"] == session_id
        assert episode_data["status"] == "completed"
        assert episode_data["total_duration_ms"] == 500  # Sum of all step durations
        assert episode_data["success_count"] == 4
        assert episode_data["failure_count"] == 0

    @pytest.mark.asyncio
    async def test_record_episode_with_failures(self, replay_engine, sample_config):
        """Test episode recording with some failed steps."""
        steps_with_failures = [
            EpisodeStep(
                step_id="step_1",
                step_type="input",
                timestamp=datetime.now(timezone.utc),
                input_data={"input_text": "Hello"},
                output_data={"intent": "greeting"},
                duration_ms=100,
                success=True
            ),
            EpisodeStep(
                step_id="step_2",
                step_type="tool_call",
                timestamp=datetime.now(timezone.utc),
                input_data={"tool_name": "broken_tool"},
                output_data={},
                duration_ms=50,
                success=False,
                error_message="Tool not available"
            )
        ]
        
        episode_id = await replay_engine.record_episode(
            "tenant_123", "session_456", sample_config, steps_with_failures
        )
        
        # Verify Redis storage
        call_args = replay_engine.redis.setex.call_args
        episode_data = json.loads(call_args[0][2])
        
        assert episode_data["success_count"] == 1
        assert episode_data["failure_count"] == 1
        assert episode_data["total_duration_ms"] == 150

    @pytest.mark.asyncio
    async def test_replay_episode_exact_mode(self, replay_engine, sample_config, sample_steps):
        """Test episode replay in exact mode."""
        tenant_id = "tenant_123"
        session_id = "session_456"
        
        # First record an episode
        episode_id = await replay_engine.record_episode(
            tenant_id, session_id, sample_config, sample_steps
        )
        
        # Mock loading the episode
        with patch.object(replay_engine, '_load_episode') as mock_load:
            # Create a mock episode
            mock_episode = Episode(
                episode_id=episode_id,
                tenant_id=tenant_id,
                session_id=session_id,
                config=sample_config,
                steps=sample_steps,
                status=ReplayStatus.COMPLETED
            )
            mock_load.return_value = mock_episode
            
            # Replay the episode
            replay_episode = await replay_engine.replay_episode(
                episode_id, ReplayMode.EXACT
            )
        
        # Verify replay results
        assert replay_episode.episode_id.startswith(f"replay_{episode_id}_")
        assert replay_episode.tenant_id == tenant_id
        assert replay_episode.session_id.startswith("replay_")
        assert replay_episode.status == ReplayStatus.COMPLETED
        
        # Verify all steps were replayed
        assert len(replay_episode.steps) == 4
        assert replay_episode.success_count == 4
        assert replay_episode.failure_count == 0
        
        # Verify step IDs are prefixed with "replay_"
        for step in replay_episode.steps:
            assert step.step_id.startswith("replay_")

    @pytest.mark.asyncio
    async def test_replay_episode_similar_mode(self, replay_engine, sample_config, sample_steps):
        """Test episode replay in similar mode."""
        tenant_id = "tenant_123"
        session_id = "session_456"
        
        # Record an episode
        episode_id = await replay_engine.record_episode(
            tenant_id, session_id, sample_config, sample_steps
        )
        
        # Mock loading the episode
        with patch.object(replay_engine, '_load_episode') as mock_load:
            mock_episode = Episode(
                episode_id=episode_id,
                tenant_id=tenant_id,
                session_id=session_id,
                config=sample_config,
                steps=sample_steps,
                status=ReplayStatus.COMPLETED
            )
            mock_load.return_value = mock_episode
            
            # Replay in similar mode
            replay_episode = await replay_engine.replay_episode(
                episode_id, ReplayMode.SIMILAR
            )
        
        # Verify similar mode behavior (should use current versions)
        assert replay_episode.status == ReplayStatus.COMPLETED
        assert len(replay_episode.steps) == 4
        
        # Check that output data was processed (not exact copy)
        for step in replay_episode.steps:
            assert step.output_data is not None
            assert step.success is True

    @pytest.mark.asyncio
    async def test_replay_episode_adaptive_mode(self, replay_engine, sample_config, sample_steps):
        """Test episode replay in adaptive mode."""
        tenant_id = "tenant_123"
        session_id = "session_456"
        
        # Record an episode
        episode_id = await replay_engine.record_episode(
            tenant_id, session_id, sample_config, sample_steps
        )
        
        # Mock loading the episode
        with patch.object(replay_engine, '_load_episode') as mock_load:
            mock_episode = Episode(
                episode_id=episode_id,
                tenant_id=tenant_id,
                session_id=session_id,
                config=sample_config,
                steps=sample_steps,
                status=ReplayStatus.COMPLETED
            )
            mock_load.return_value = mock_episode
            
            # Replay in adaptive mode
            replay_episode = await replay_engine.replay_episode(
                episode_id, ReplayMode.ADAPTIVE
            )
        
        # Verify adaptive mode behavior
        assert replay_episode.status == ReplayStatus.COMPLETED
        assert len(replay_episode.steps) == 4
        
        # Check adaptive output data
        for step in replay_episode.steps:
            assert step.output_data is not None
            assert step.success is True

    @pytest.mark.asyncio
    async def test_replay_episode_not_found(self, replay_engine):
        """Test replaying non-existent episode."""
        with patch.object(replay_engine, '_load_episode') as mock_load:
            mock_load.return_value = None
            
            with pytest.raises(ValueError, match="Episode .* not found"):
                await replay_engine.replay_episode("non_existent_episode")

    @pytest.mark.asyncio
    async def test_replay_episode_with_step_failure(self, replay_engine, sample_config):
        """Test episode replay with step failures."""
        steps_with_error = [
            EpisodeStep(
                step_id="step_1",
                step_type="input",
                timestamp=datetime.now(timezone.utc),
                input_data={"input_text": "Hello"},
                output_data={"intent": "greeting"},
                duration_ms=100,
                success=True
            ),
            EpisodeStep(
                step_id="step_2",
                step_type="tool_call",
                timestamp=datetime.now(timezone.utc),
                input_data={"tool_name": "failing_tool"},
                output_data={},
                duration_ms=50,
                success=False,
                error_message="Tool error"
            )
        ]
        
        episode_id = await replay_engine.record_episode(
            "tenant_123", "session_456", sample_config, steps_with_error
        )
        
        # Mock loading the episode
        with patch.object(replay_engine, '_load_episode') as mock_load:
            mock_episode = Episode(
                episode_id=episode_id,
                tenant_id="tenant_123",
                session_id="session_456",
                config=sample_config,
                steps=steps_with_error,
                status=ReplayStatus.COMPLETED
            )
            mock_load.return_value = mock_episode
            
            # Replay the episode
            replay_episode = await replay_engine.replay_episode(episode_id)
        
        # Verify replay handled failures
        assert replay_episode.status == ReplayStatus.COMPLETED
        assert len(replay_episode.steps) == 2
        assert replay_episode.success_count == 1
        assert replay_episode.failure_count == 1

    @pytest.mark.asyncio
    async def test_replay_step_input_type(self, replay_engine, sample_config):
        """Test replaying input step type."""
        original_step = EpisodeStep(
            step_id="step_1",
            step_type="input",
            timestamp=datetime.now(timezone.utc),
            input_data={"input_text": "Hello"},
            output_data={"intent": "greeting", "confidence": 0.9},
            duration_ms=100,
            success=True
        )
        
        replay_episode = Episode(
            episode_id="replay_test",
            tenant_id="tenant_123",
            session_id="session_456",
            config=sample_config,
            status=ReplayStatus.RUNNING
        )
        
        # Test exact mode
        replayed_step = await replay_engine._replay_step(
            original_step, ReplayMode.EXACT, replay_episode
        )
        
        assert replayed_step.step_id == "replay_step_1"
        assert replayed_step.step_type == "input"
        assert replayed_step.success is True
        assert replayed_step.output_data == original_step.output_data

    @pytest.mark.asyncio
    async def test_replay_step_router_type(self, replay_engine, sample_config):
        """Test replaying router decision step type."""
        original_step = EpisodeStep(
            step_id="step_2",
            step_type="router_decision",
            timestamp=datetime.now(timezone.utc),
            input_data={"text_features": {"token_count": 5}},
            output_data={"selected_tier": "SLM_A", "confidence": 0.85},
            duration_ms=50,
            success=True
        )
        
        replay_episode = Episode(
            episode_id="replay_test",
            tenant_id="tenant_123",
            session_id="session_456",
            config=sample_config,
            status=ReplayStatus.RUNNING
        )
        
        # Test similar mode
        replayed_step = await replay_engine._replay_step(
            original_step, ReplayMode.SIMILAR, replay_episode
        )
        
        assert replayed_step.step_id == "replay_step_2"
        assert replayed_step.step_type == "router_decision"
        assert replayed_step.success is True
        assert "selected_tier" in replayed_step.output_data
        assert "confidence" in replayed_step.output_data

    @pytest.mark.asyncio
    async def test_replay_step_tool_type(self, replay_engine, sample_config):
        """Test replaying tool call step type."""
        original_step = EpisodeStep(
            step_id="step_3",
            step_type="tool_call",
            timestamp=datetime.now(timezone.utc),
            input_data={"tool_name": "knowledge_base", "query": "business hours"},
            output_data={"result": {"hours": "9 AM - 5 PM"}, "success": True},
            duration_ms=200,
            success=True
        )
        
        replay_episode = Episode(
            episode_id="replay_test",
            tenant_id="tenant_123",
            session_id="session_456",
            config=sample_config,
            status=ReplayStatus.RUNNING
        )
        
        # Test adaptive mode
        replayed_step = await replay_engine._replay_step(
            original_step, ReplayMode.ADAPTIVE, replay_episode
        )
        
        assert replayed_step.step_id == "replay_step_3"
        assert replayed_step.step_type == "tool_call"
        assert replayed_step.success is True
        assert "tool_name" in replayed_step.output_data
        assert "result" in replayed_step.output_data

    @pytest.mark.asyncio
    async def test_replay_step_response_type(self, replay_engine, sample_config):
        """Test replaying response step type."""
        original_step = EpisodeStep(
            step_id="step_4",
            step_type="response",
            timestamp=datetime.now(timezone.utc),
            input_data={"context": "business hours query"},
            output_data={"response_text": "Our hours are 9 AM - 5 PM"},
            duration_ms=150,
            success=True
        )
        
        replay_episode = Episode(
            episode_id="replay_test",
            tenant_id="tenant_123",
            session_id="session_456",
            config=sample_config,
            status=ReplayStatus.RUNNING
        )
        
        # Test exact mode
        replayed_step = await replay_engine._replay_step(
            original_step, ReplayMode.EXACT, replay_episode
        )
        
        assert replayed_step.step_id == "replay_step_4"
        assert replayed_step.step_type == "response"
        assert replayed_step.success is True
        assert replayed_step.output_data == original_step.output_data

    @pytest.mark.asyncio
    async def test_replay_step_unknown_type(self, replay_engine, sample_config):
        """Test replaying unknown step type."""
        original_step = EpisodeStep(
            step_id="step_5",
            step_type="unknown_type",
            timestamp=datetime.now(timezone.utc),
            input_data={"data": "test"},
            output_data={"result": "test"},
            duration_ms=100,
            success=True
        )
        
        replay_episode = Episode(
            episode_id="replay_test",
            tenant_id="tenant_123",
            session_id="session_456",
            config=sample_config,
            status=ReplayStatus.RUNNING
        )
        
        # Should handle unknown step type gracefully
        replayed_step = await replay_engine._replay_step(
            original_step, ReplayMode.EXACT, replay_episode
        )
        
        assert replayed_step.step_id == "replay_step_5"
        assert replayed_step.success is False
        assert "Unknown step type" in replayed_step.error_message

    @pytest.mark.asyncio
    async def test_store_episode(self, replay_engine, sample_config, sample_steps):
        """Test episode storage."""
        episode = Episode(
            episode_id="test_episode",
            tenant_id="tenant_123",
            session_id="session_456",
            config=sample_config,
            steps=sample_steps,
            status=ReplayStatus.COMPLETED,
            total_duration_ms=500,
            success_count=4,
            failure_count=0
        )
        
        with patch('builtins.open', mock_open()) as mock_file:
            await replay_engine._store_episode(episode)
        
        # Verify Redis storage
        replay_engine.redis.setex.assert_called_once()
        call_args = replay_engine.redis.setex.call_args
        
        # Verify file storage
        mock_file.assert_called_once()
        
        # Verify episode data
        episode_data = json.loads(call_args[0][2])
        assert episode_data["episode_id"] == "test_episode"
        assert episode_data["status"] == "completed"
        assert len(episode_data["steps"]) == 4

    @pytest.mark.asyncio
    async def test_load_episode_from_redis(self, replay_engine, sample_config, sample_steps):
        """Test loading episode from Redis."""
        # Mock Redis response
        episode_data = {
            "episode_id": "test_episode",
            "tenant_id": "tenant_123",
            "session_id": "session_456",
            "config": {
                "episode_id": sample_config.episode_id,
                "model_version": sample_config.model_version,
                "prompt_version": sample_config.prompt_version,
                "tool_versions": sample_config.tool_versions,
                "router_config": sample_config.router_config,
                "tenant_config": sample_config.tenant_config,
                "timestamp": sample_config.timestamp.isoformat(),
                "metadata": sample_config.metadata
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
                    "metadata": step.metadata
                }
                for step in sample_steps
            ],
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
            "total_duration_ms": 500,
            "success_count": 4,
            "failure_count": 0,
            "metadata": {}
        }
        
        replay_engine.redis.get.return_value = json.dumps(episode_data)
        
        episode = await replay_engine._load_episode("test_episode")
        
        assert episode is not None
        assert episode.episode_id == "test_episode"
        assert episode.tenant_id == "tenant_123"
        assert episode.status == ReplayStatus.COMPLETED
        assert len(episode.steps) == 4

    @pytest.mark.asyncio
    async def test_load_episode_from_filesystem(self, replay_engine, sample_config, sample_steps):
        """Test loading episode from file system when Redis fails."""
        # Mock Redis returning None
        replay_engine.redis.get.return_value = None
        
        # Mock file system
        episode_data = {
            "episode_id": "test_episode",
            "tenant_id": "tenant_123",
            "session_id": "session_456",
            "config": {
                "episode_id": sample_config.episode_id,
                "model_version": sample_config.model_version,
                "prompt_version": sample_config.prompt_version,
                "tool_versions": sample_config.tool_versions,
                "router_config": sample_config.router_config,
                "tenant_config": sample_config.tenant_config,
                "timestamp": sample_config.timestamp.isoformat(),
                "metadata": sample_config.metadata
            },
            "steps": [],
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
            "total_duration_ms": 500,
            "success_count": 4,
            "failure_count": 0,
            "metadata": {}
        }
        
        mock_file_path = Path("test_episodes/test_episode.json")
        
        with patch.object(Path, 'exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(episode_data))):
            
            episode = await replay_engine._load_episode("test_episode")
        
        assert episode is not None
        assert episode.episode_id == "test_episode"

    @pytest.mark.asyncio
    async def test_load_episode_not_found(self, replay_engine):
        """Test loading non-existent episode."""
        # Mock Redis and file system both returning None/not found
        replay_engine.redis.get.return_value = None
        
        with patch.object(Path, 'exists', return_value=False):
            episode = await replay_engine._load_episode("non_existent")
        
        assert episode is None

    @pytest.mark.asyncio
    async def test_get_episode_stats(self, replay_engine):
        """Test getting episode statistics."""
        # Mock Redis keys and data
        mock_keys = [b"episode:ep1", b"episode:ep2"]
        replay_engine.redis.keys.return_value = mock_keys
        
        episode_data_1 = {
            "tenant_id": "tenant_123",
            "status": "completed",
            "total_duration_ms": 500,
            "success_count": 4,
            "failure_count": 0
        }
        episode_data_2 = {
            "tenant_id": "tenant_123",
            "status": "failed",
            "total_duration_ms": 200,
            "success_count": 1,
            "failure_count": 1
        }
        
        replay_engine.redis.get.side_effect = [
            json.dumps(episode_data_1),
            json.dumps(episode_data_2)
        ]
        
        stats = await replay_engine.get_episode_stats("tenant_123")
        
        assert stats["total_episodes"] == 2
        assert stats["success_rate"] == 0.5  # 1 successful out of 2
        assert stats["average_duration_ms"] == 350  # (500 + 200) / 2
        assert stats["episodes_by_status"]["completed"] == 1
        assert stats["episodes_by_status"]["failed"] == 1

    @pytest.mark.asyncio
    async def test_get_episode_stats_no_episodes(self, replay_engine):
        """Test getting episode statistics when no episodes exist."""
        replay_engine.redis.keys.return_value = []
        
        stats = await replay_engine.get_episode_stats("tenant_123")
        
        assert stats["total_episodes"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["average_duration_ms"] == 0
        assert stats["episodes_by_status"] == {}
        assert stats["episodes_by_category"] == {}

    @pytest.mark.asyncio
    async def test_cleanup_old_episodes(self, replay_engine):
        """Test cleaning up old episodes."""
        # Mock Redis keys
        mock_keys = [b"episode:old_episode", b"episode:new_episode"]
        replay_engine.redis.keys.return_value = mock_keys
        
        # Mock episode data - one old, one new
        old_time = datetime.now(timezone.utc).timestamp() - (35 * 24 * 60 * 60)  # 35 days ago
        new_time = datetime.now(timezone.utc).timestamp() - (5 * 24 * 60 * 60)   # 5 days ago
        
        old_episode = {
            "start_time": datetime.fromtimestamp(old_time).isoformat()
        }
        new_episode = {
            "start_time": datetime.fromtimestamp(new_time).isoformat()
        }
        
        replay_engine.redis.get.side_effect = [
            json.dumps(old_episode),
            json.dumps(new_episode)
        ]
        
        # Mock file system cleanup
        mock_old_file = Mock()
        mock_old_file.stat.return_value.st_mtime = old_time
        mock_new_file = Mock()
        mock_new_file.stat.return_value.st_mtime = new_time
        
        with patch.object(Path, 'glob', return_value=[mock_old_file, mock_new_file]):
            cleaned_count = await replay_engine.cleanup_old_episodes(days=30)
        
        # Should clean 1 old episode from Redis and 1 old file
        assert cleaned_count == 2
        replay_engine.redis.delete.assert_called_once_with(b"episode:old_episode")

    @pytest.mark.asyncio
    async def test_cleanup_old_episodes_error_handling(self, replay_engine):
        """Test cleanup error handling."""
        replay_engine.redis.keys.side_effect = Exception("Redis error")
        
        cleaned_count = await replay_engine.cleanup_old_episodes(days=30)
        
        assert cleaned_count == 0

    def test_episode_config_creation(self):
        """Test EpisodeConfig creation."""
        config = EpisodeConfig(
            episode_id="test_episode",
            model_version="gpt-4",
            prompt_version="v1.0",
            tool_versions={"tool1": "v1.0"},
            router_config={"threshold": 0.8},
            tenant_config={"tier": "premium"},
            timestamp=datetime.now(timezone.utc),
            metadata={"test": True}
        )
        
        assert config.episode_id == "test_episode"
        assert config.model_version == "gpt-4"
        assert config.tool_versions == {"tool1": "v1.0"}
        assert config.metadata == {"test": True}

    def test_episode_step_creation(self):
        """Test EpisodeStep creation."""
        step = EpisodeStep(
            step_id="step_1",
            step_type="input",
            timestamp=datetime.now(timezone.utc),
            input_data={"text": "Hello"},
            output_data={"intent": "greeting"},
            duration_ms=100,
            success=True,
            error_message=None,
            metadata={"processed": True}
        )
        
        assert step.step_id == "step_1"
        assert step.step_type == "input"
        assert step.success is True
        assert step.duration_ms == 100
        assert step.metadata == {"processed": True}

    def test_episode_creation(self):
        """Test Episode creation."""
        config = EpisodeConfig(
            episode_id="test_episode",
            model_version="gpt-4",
            prompt_version="v1.0",
            tool_versions={},
            router_config={},
            tenant_config={},
            timestamp=datetime.now(timezone.utc)
        )
        
        episode = Episode(
            episode_id="test_episode",
            tenant_id="tenant_123",
            session_id="session_456",
            config=config,
            status=ReplayStatus.PENDING
        )
        
        assert episode.episode_id == "test_episode"
        assert episode.tenant_id == "tenant_123"
        assert episode.status == ReplayStatus.PENDING
        assert episode.success_count == 0
        assert episode.failure_count == 0


def mock_open(read_data=""):
    """Mock open function for file operations."""
    from unittest.mock import mock_open as _mock_open
    return _mock_open(read_data=read_data)
