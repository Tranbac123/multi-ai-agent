"""
Integration tests for evaluation and replay system.

Tests golden task management, LLM judge evaluation, and episode replay
capabilities with comprehensive test coverage.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json

from apps.eval_service.core.golden_tasks import (
    GoldenTaskManager, GoldenTask, TaskCategory, TaskDifficulty, TaskStatus,
    TaskExecution, EvaluationResult
)
from apps.eval_service.core.llm_judge import (
    LLMJudge, LLMJudgeConfig, EvaluationCriteria, ScoringScale,
    EvaluationMethod, JudgeResponse, EvaluationEngine
)
from apps.eval_service.core.episode_replay import (
    EpisodeReplayManager, Episode, EpisodeState, StateType,
    ReplayRequest, ReplayExecution, ReplayStatus
)


class TestGoldenTaskManager:
    """Test golden task management."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        return AsyncMock()
    
    @pytest.fixture
    def task_manager(self, mock_db_session):
        """Create golden task manager for testing."""
        return GoldenTaskManager(mock_db_session)
    
    @pytest.fixture
    def sample_task(self):
        """Create sample golden task."""
        return GoldenTask(
            task_id="task-123",
            title="Test Task",
            description="A test task for evaluation",
            category=TaskCategory.BASIC_REASONING,
            difficulty=TaskDifficulty.EASY,
            input_data={"question": "What is 2+2?"},
            expected_output={"answer": 4},
            evaluation_criteria={"accuracy": 0.8, "completeness": 0.2},
            tags={"math", "basic"},
            timeout_seconds=60,
            max_retries=3
        )
    
    @pytest.mark.asyncio
    async def test_create_golden_task(self, task_manager, mock_db_session):
        """Test creating a golden task."""
        
        task = await task_manager.create_golden_task(
            title="Test Task",
            description="A test task",
            category=TaskCategory.BASIC_REASONING,
            difficulty=TaskDifficulty.EASY,
            input_data={"input": "test"},
            expected_output={"output": "result"},
            evaluation_criteria={"accuracy": 1.0},
            tags={"test"}
        )
        
        assert task.task_id is not None
        assert task.title == "Test Task"
        assert task.category == TaskCategory.BASIC_REASONING
        assert task.difficulty == TaskDifficulty.EASY
        assert task.is_active is True
        
        # Verify database call
        mock_db_session.execute.assert_called()
        mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_get_golden_task(self, task_manager, mock_db_session, sample_task):
        """Test getting a golden task."""
        
        # Mock database response
        mock_row = MagicMock()
        mock_row.task_id = sample_task.task_id
        mock_row.title = sample_task.title
        mock_row.description = sample_task.description
        mock_row.category = sample_task.category.value
        mock_row.difficulty = sample_task.difficulty.value
        mock_row.input_data = json.dumps(sample_task.input_data)
        mock_row.expected_output = json.dumps(sample_task.expected_output)
        mock_row.evaluation_criteria = json.dumps(sample_task.evaluation_criteria)
        mock_row.tags = list(sample_task.tags)
        mock_row.created_at = sample_task.created_at
        mock_row.updated_at = sample_task.updated_at
        mock_row.version = sample_task.version
        mock_row.is_active = sample_task.is_active
        mock_row.timeout_seconds = sample_task.timeout_seconds
        mock_row.max_retries = sample_task.max_retries
        mock_row.metadata = json.dumps(sample_task.metadata)
        
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db_session.execute.return_value = mock_result
        
        task = await task_manager.get_golden_task(sample_task.task_id)
        
        assert task is not None
        assert task.task_id == sample_task.task_id
        assert task.title == sample_task.title
    
    @pytest.mark.asyncio
    async def test_execute_task_success(self, task_manager, mock_db_session, sample_task):
        """Test successful task execution."""
        
        # Mock executor function
        async def mock_executor(input_data):
            return {"result": "success", "computed": True}
        
        execution = await task_manager.execute_task(
            task=sample_task,
            run_id="run-123",
            tenant_id="tenant-456",
            executor_func=mock_executor
        )
        
        assert execution.status == TaskStatus.COMPLETED
        assert execution.actual_output is not None
        assert execution.execution_time_ms is not None
        assert execution.error_message is None
    
    @pytest.mark.asyncio
    async def test_execute_task_timeout(self, task_manager, mock_db_session, sample_task):
        """Test task execution timeout."""
        
        # Mock slow executor function
        async def slow_executor(input_data):
            await asyncio.sleep(1.0)  # Longer than timeout
            return {"result": "success"}
        
        # Set short timeout
        sample_task.timeout_seconds = 0.1
        
        execution = await task_manager.execute_task(
            task=sample_task,
            run_id="run-123",
            tenant_id="tenant-456",
            executor_func=slow_executor
        )
        
        assert execution.status == TaskStatus.TIMEOUT
        assert execution.error_message is not None
        assert "timed out" in execution.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_execute_task_failure(self, task_manager, mock_db_session, sample_task):
        """Test task execution failure."""
        
        # Mock failing executor function
        async def failing_executor(input_data):
            raise ValueError("Test error")
        
        execution = await task_manager.execute_task(
            task=sample_task,
            run_id="run-123",
            tenant_id="tenant-456",
            executor_func=failing_executor
        )
        
        assert execution.status == TaskStatus.FAILED
        assert execution.error_message == "Test error"
        assert execution.actual_output is None


class TestLLMJudge:
    """Test LLM judge functionality."""
    
    @pytest.fixture
    def evaluation_criteria(self):
        """Create evaluation criteria."""
        return [
            EvaluationCriteria(
                name="accuracy",
                description="Accuracy of the response",
                weight=0.5,
                scoring_scale=ScoringScale.PERCENTAGE,
                min_score=0.0,
                max_score=100.0,
                evaluation_prompt="Rate the accuracy of the response"
            ),
            EvaluationCriteria(
                name="completeness",
                description="Completeness of the response",
                weight=0.3,
                scoring_scale=ScoringScale.PERCENTAGE,
                min_score=0.0,
                max_score=100.0,
                evaluation_prompt="Rate the completeness of the response"
            ),
            EvaluationCriteria(
                name="relevance",
                description="Relevance to the question",
                weight=0.2,
                scoring_scale=ScoringScale.PERCENTAGE,
                min_score=0.0,
                max_score=100.0,
                evaluation_prompt="Rate the relevance of the response"
            )
        ]
    
    @pytest.fixture
    def judge_config(self, evaluation_criteria):
        """Create LLM judge configuration."""
        return LLMJudgeConfig(
            model="gpt-4",
            temperature=0.1,
            max_tokens=1000,
            timeout_seconds=60,
            retry_attempts=3,
            criteria=evaluation_criteria
        )
    
    @pytest.fixture
    def mock_openai_client(self):
        """Create mock OpenAI client."""
        return AsyncMock()
    
    @pytest.fixture
    def llm_judge(self, judge_config, mock_openai_client):
        """Create LLM judge for testing."""
        return LLMJudge(judge_config, mock_openai_client)
    
    @pytest.fixture
    def sample_task(self):
        """Create sample task."""
        return GoldenTask(
            task_id="task-123",
            title="Math Problem",
            description="Solve a simple math problem",
            category=TaskCategory.BASIC_REASONING,
            difficulty=TaskDifficulty.EASY,
            input_data={"question": "What is 5 + 3?"},
            expected_output={"answer": 8},
            evaluation_criteria={"accuracy": 1.0}
        )
    
    @pytest.fixture
    def sample_execution(self):
        """Create sample execution."""
        return TaskExecution(
            execution_id="exec-123",
            task_id="task-123",
            run_id="run-456",
            tenant_id="tenant-789",
            status=TaskStatus.COMPLETED,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            actual_output={"answer": 8, "explanation": "5 + 3 = 8"},
            execution_time_ms=1500
        )
    
    @pytest.mark.asyncio
    async def test_evaluate_task_execution_success(
        self, 
        llm_judge, 
        mock_openai_client, 
        sample_task, 
        sample_execution
    ):
        """Test successful task evaluation."""
        
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "overall_score": 95.0,
            "criteria_scores": {
                "accuracy": 100.0,
                "completeness": 90.0,
                "relevance": 95.0
            },
            "reasoning": "The response is accurate, complete, and relevant.",
            "passed": True,
            "confidence": 0.9
        })
        
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        judge_response = await llm_judge.evaluate_task_execution(sample_task, sample_execution)
        
        assert judge_response.overall_score == 95.0
        assert judge_response.criteria_scores["accuracy"] == 100.0
        assert judge_response.criteria_scores["completeness"] == 90.0
        assert judge_response.criteria_scores["relevance"] == 95.0
        assert judge_response.passed is True
        assert judge_response.confidence == 0.9
        assert judge_response.model_used == "gpt-4"
    
    @pytest.mark.asyncio
    async def test_evaluate_task_execution_parse_error(
        self, 
        llm_judge, 
        mock_openai_client, 
        sample_task, 
        sample_execution
    ):
        """Test evaluation with parsing error."""
        
        # Mock OpenAI response with invalid JSON
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Invalid JSON response"
        
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        judge_response = await llm_judge.evaluate_task_execution(sample_task, sample_execution)
        
        assert judge_response.overall_score == 0.0
        assert judge_response.passed is False
        assert judge_response.confidence == 0.0
        assert "Failed to parse" in judge_response.reasoning
    
    @pytest.mark.asyncio
    async def test_create_evaluation_result(self, llm_judge, sample_execution):
        """Test creating evaluation result from judge response."""
        
        judge_response = JudgeResponse(
            overall_score=85.0,
            criteria_scores={"accuracy": 90.0, "completeness": 80.0},
            reasoning="Good response",
            passed=True,
            confidence=0.8,
            raw_response="{}",
            evaluation_time_ms=2000,
            model_used="gpt-4"
        )
        
        result = llm_judge.create_evaluation_result(sample_execution, judge_response)
        
        assert result.execution_id == sample_execution.execution_id
        assert result.task_id == sample_execution.task_id
        assert result.overall_score == 85.0
        assert result.criteria_scores["accuracy"] == 90.0
        assert result.passed is True
        assert result.evaluation_method == EvaluationMethod.LLM_JUDGE.value


class TestEvaluationEngine:
    """Test evaluation engine functionality."""
    
    @pytest.fixture
    def mock_llm_judge(self):
        """Create mock LLM judge."""
        return AsyncMock()
    
    @pytest.fixture
    def evaluation_engine(self, mock_llm_judge):
        """Create evaluation engine for testing."""
        return EvaluationEngine(mock_llm_judge)
    
    @pytest.fixture
    def sample_task(self):
        """Create sample task."""
        return GoldenTask(
            task_id="task-123",
            title="Test Task",
            description="A test task",
            category=TaskCategory.BASIC_REASONING,
            difficulty=TaskDifficulty.EASY,
            input_data={"input": "test"},
            expected_output={"output": "expected"},
            evaluation_criteria={"accuracy": 1.0}
        )
    
    @pytest.fixture
    def sample_execution(self):
        """Create sample execution."""
        return TaskExecution(
            execution_id="exec-123",
            task_id="task-123",
            run_id="run-456",
            tenant_id="tenant-789",
            status=TaskStatus.COMPLETED,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            actual_output={"output": "actual"},
            execution_time_ms=1000
        )
    
    @pytest.mark.asyncio
    async def test_evaluate_exact_match_success(self, evaluation_engine, sample_task, sample_execution):
        """Test exact match evaluation with success."""
        
        # Set actual output to match expected
        sample_execution.actual_output = sample_task.expected_output
        
        result = await evaluation_engine._evaluate_exact_match(sample_task, sample_execution)
        
        assert result.overall_score == 100.0
        assert result.criteria_scores["exact_match"] == 100.0
        assert result.passed is True
        assert result.evaluation_method == EvaluationMethod.EXACT_MATCH.value
    
    @pytest.mark.asyncio
    async def test_evaluate_exact_match_failure(self, evaluation_engine, sample_task, sample_execution):
        """Test exact match evaluation with failure."""
        
        # Set actual output to differ from expected
        sample_execution.actual_output = {"output": "different"}
        
        result = await evaluation_engine._evaluate_exact_match(sample_task, sample_execution)
        
        assert result.overall_score == 0.0
        assert result.criteria_scores["exact_match"] == 0.0
        assert result.passed is False
    
    @pytest.mark.asyncio
    async def test_evaluate_criteria_based(self, evaluation_engine, sample_task, sample_execution):
        """Test criteria-based evaluation."""
        
        result = await evaluation_engine._evaluate_criteria_based(sample_task, sample_execution)
        
        assert result.overall_score > 0.0
        assert "completeness" in result.criteria_scores
        assert "accuracy" in result.criteria_scores
        assert "relevance" in result.criteria_scores
        assert result.evaluation_method == EvaluationMethod.CRITERIA_BASED.value
    
    @pytest.mark.asyncio
    async def test_evaluate_execution_multiple_methods(
        self, 
        evaluation_engine, 
        mock_llm_judge, 
        sample_task, 
        sample_execution
    ):
        """Test evaluation with multiple methods."""
        
        # Mock LLM judge response
        mock_judge_response = MagicMock()
        mock_judge_response.overall_score = 85.0
        mock_judge_response.criteria_scores = {"accuracy": 90.0}
        mock_judge_response.passed = True
        mock_judge_response.confidence = 0.8
        mock_judge_response.reasoning = "Good response"
        mock_judge_response.model_used = "gpt-4"
        mock_judge_response.evaluation_time_ms = 2000
        
        mock_llm_judge.evaluate_task_execution.return_value = mock_judge_response
        mock_llm_judge.create_evaluation_result.return_value = EvaluationResult(
            execution_id=sample_execution.execution_id,
            task_id=sample_execution.task_id,
            overall_score=85.0,
            criteria_scores={"accuracy": 90.0},
            passed=True,
            evaluation_method=EvaluationMethod.LLM_JUDGE.value,
            evaluated_at=datetime.now()
        )
        
        results = await evaluation_engine.evaluate_execution(
            sample_task, 
            sample_execution,
            methods=[EvaluationMethod.EXACT_MATCH, EvaluationMethod.LLM_JUDGE]
        )
        
        assert len(results) == 2
        assert any(r.evaluation_method == EvaluationMethod.EXACT_MATCH.value for r in results)
        assert any(r.evaluation_method == EvaluationMethod.LLM_JUDGE.value for r in results)
    
    def test_calculate_composite_score(self, evaluation_engine):
        """Test composite score calculation."""
        
        results = [
            EvaluationResult(
                execution_id="exec-1",
                task_id="task-1",
                overall_score=80.0,
                criteria_scores={},
                passed=True,
                evaluation_method="method1",
                evaluated_at=datetime.now()
            ),
            EvaluationResult(
                execution_id="exec-1",
                task_id="task-1",
                overall_score=90.0,
                criteria_scores={},
                passed=True,
                evaluation_method="method2",
                evaluated_at=datetime.now()
            )
        ]
        
        composite_score = evaluation_engine.calculate_composite_score(results)
        
        assert composite_score == 85.0  # Average of 80.0 and 90.0
    
    def test_determine_overall_pass(self, evaluation_engine):
        """Test overall pass determination."""
        
        results = [
            EvaluationResult(
                execution_id="exec-1",
                task_id="task-1",
                overall_score=80.0,
                criteria_scores={},
                passed=True,
                evaluation_method="method1",
                evaluated_at=datetime.now()
            ),
            EvaluationResult(
                execution_id="exec-1",
                task_id="task-1",
                overall_score=90.0,
                criteria_scores={},
                passed=False,
                evaluation_method="method2",
                evaluated_at=datetime.now()
            ),
            EvaluationResult(
                execution_id="exec-1",
                task_id="task-1",
                overall_score=70.0,
                criteria_scores={},
                passed=True,
                evaluation_method="method3",
                evaluated_at=datetime.now()
            )
        ]
        
        overall_pass = evaluation_engine.determine_overall_pass(results)
        
        assert overall_pass is True  # 2 out of 3 passed


class TestEpisodeReplayManager:
    """Test episode replay functionality."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        return AsyncMock()
    
    @pytest.fixture
    def replay_manager(self, mock_db_session):
        """Create episode replay manager for testing."""
        return EpisodeReplayManager(mock_db_session)
    
    @pytest.fixture
    def sample_episode(self):
        """Create sample episode."""
        return Episode(
            episode_id="episode-123",
            run_id="run-456",
            tenant_id="tenant-789",
            task_id="task-101",
            agent_config={"model": "gpt-4", "temperature": 0.1},
            initial_state={"step": 0, "context": "initial"},
            steps_count=5,
            duration_ms=2500,
            success=True,
            total_reward=100.0
        )
    
    @pytest.mark.asyncio
    async def test_record_episode(self, replay_manager, mock_db_session):
        """Test recording an episode."""
        
        episode = await replay_manager.record_episode(
            run_id="run-123",
            tenant_id="tenant-456",
            task_id="task-789",
            agent_config={"model": "gpt-4"},
            initial_state={"step": 0}
        )
        
        assert episode.episode_id is not None
        assert episode.run_id == "run-123"
        assert episode.tenant_id == "tenant-456"
        assert episode.task_id == "task-789"
        
        # Verify database call
        mock_db_session.execute.assert_called()
        mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_record_state_snapshot(self, replay_manager, mock_db_session):
        """Test recording state snapshot."""
        
        state = await replay_manager.record_state_snapshot(
            episode_id="episode-123",
            step_number=1,
            state_type=StateType.INTERMEDIATE,
            agent_state={"thoughts": "thinking"},
            environment_state={"observation": "seeing"},
            action_taken={"action": "move"},
            reward=10.0
        )
        
        assert state.state_id is not None
        assert state.episode_id == "episode-123"
        assert state.step_number == 1
        assert state.state_type == StateType.INTERMEDIATE
        assert state.reward == 10.0
        
        # Verify database call
        mock_db_session.execute.assert_called()
        mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_finalize_episode(self, replay_manager, mock_db_session):
        """Test finalizing an episode."""
        
        await replay_manager.finalize_episode(
            episode_id="episode-123",
            final_state={"step": 5, "completed": True},
            success=True,
            total_reward=100.0,
            steps_count=5,
            duration_ms=2500
        )
        
        # Verify database call
        mock_db_session.execute.assert_called()
        mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_create_replay_request(self, replay_manager, mock_db_session):
        """Test creating replay request."""
        
        replay_request = await replay_manager.create_replay_request(
            episode_id="episode-123",
            replay_config={"debug": True},
            target_step=3,
            replay_mode="partial",
            breakpoints=[1, 2, 3]
        )
        
        assert replay_request.replay_id is not None
        assert replay_request.episode_id == "episode-123"
        assert replay_request.replay_mode == "partial"
        assert replay_request.target_step == 3
        assert 1 in replay_request.breakpoints
        
        # Verify database call
        mock_db_session.execute.assert_called()
        mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_execute_replay_success(
        self, 
        replay_manager, 
        mock_db_session, 
        sample_episode
    ):
        """Test successful replay execution."""
        
        # Mock executor function
        async def mock_executor(episode, states, replay_config, target_step, replay_mode, breakpoints, variable_overrides):
            return {"status": "completed", "steps_replayed": 5}
        
        # Mock get_episode
        replay_manager.get_episode = AsyncMock(return_value=sample_episode)
        replay_manager.get_episode_states = AsyncMock(return_value=[])
        
        replay_request = ReplayRequest(
            replay_id="replay-123",
            episode_id="episode-123",
            replay_config={"debug": True}
        )
        
        execution = await replay_manager.execute_replay(replay_request, mock_executor)
        
        assert execution.status == ReplayStatus.COMPLETED
        assert execution.replay_results is not None
        assert execution.execution_time_ms is not None
        assert execution.error_message is None
    
    @pytest.mark.asyncio
    async def test_execute_replay_failure(
        self, 
        replay_manager, 
        mock_db_session, 
        sample_episode
    ):
        """Test failed replay execution."""
        
        # Mock failing executor function
        async def failing_executor(episode, states, replay_config, target_step, replay_mode, breakpoints, variable_overrides):
            raise RuntimeError("Replay failed")
        
        # Mock get_episode
        replay_manager.get_episode = AsyncMock(return_value=sample_episode)
        replay_manager.get_episode_states = AsyncMock(return_value=[])
        
        replay_request = ReplayRequest(
            replay_id="replay-123",
            episode_id="episode-123",
            replay_config={"debug": True}
        )
        
        execution = await replay_manager.execute_replay(replay_request, failing_executor)
        
        assert execution.status == ReplayStatus.FAILED
        assert execution.error_message == "Replay failed"
        assert execution.replay_results is None


@pytest.mark.asyncio
async def test_golden_task_evaluation_workflow():
    """Test complete golden task evaluation workflow."""
    
    # Create mock components
    mock_db_session = AsyncMock()
    task_manager = GoldenTaskManager(mock_db_session)
    
    # Create task
    task = GoldenTask(
        task_id="task-123",
        title="Math Problem",
        description="Solve 2+2",
        category=TaskCategory.BASIC_REASONING,
        difficulty=TaskDifficulty.EASY,
        input_data={"question": "What is 2+2?"},
        expected_output={"answer": 4},
        evaluation_criteria={"accuracy": 1.0}
    )
    
    # Mock executor
    async def executor(input_data):
        return {"answer": 4, "method": "addition"}
    
    # Execute task
    execution = await task_manager.execute_task(
        task=task,
        run_id="run-123",
        tenant_id="tenant-456",
        executor_func=executor
    )
    
    assert execution.status == TaskStatus.COMPLETED
    assert execution.actual_output["answer"] == 4


@pytest.mark.asyncio
async def test_episode_replay_workflow():
    """Test complete episode replay workflow."""
    
    # Create mock components
    mock_db_session = AsyncMock()
    replay_manager = EpisodeReplayManager(mock_db_session)
    
    # Record episode
    episode = await replay_manager.record_episode(
        run_id="run-123",
        tenant_id="tenant-456",
        task_id="task-789",
        agent_config={"model": "gpt-4"},
        initial_state={"step": 0, "position": "start"}
    )
    
    # Record state snapshots
    await replay_manager.record_state_snapshot(
        episode_id=episode.episode_id,
        step_number=1,
        state_type=StateType.INTERMEDIATE,
        agent_state={"thoughts": "moving"},
        environment_state={"observation": "path clear"},
        action_taken={"action": "move_forward"},
        reward=10.0
    )
    
    # Finalize episode
    await replay_manager.finalize_episode(
        episode_id=episode.episode_id,
        final_state={"step": 5, "position": "goal"},
        success=True,
        total_reward=50.0,
        steps_count=5,
        duration_ms=3000
    )
    
    # Create and execute replay
    replay_request = await replay_manager.create_replay_request(
        episode_id=episode.episode_id,
        replay_config={"debug": True}
    )
    
    async def mock_replay_executor(episode, states, replay_config, target_step, replay_mode, breakpoints, variable_overrides):
        return {"replayed_steps": len(states), "success": True}
    
    # Mock database responses
    replay_manager.get_episode = AsyncMock(return_value=episode)
    replay_manager.get_episode_states = AsyncMock(return_value=[])
    
    execution = await replay_manager.execute_replay(replay_request, mock_replay_executor)
    
    assert execution.status == ReplayStatus.COMPLETED
    assert execution.replay_results["success"] is True


@pytest.mark.asyncio
async def test_llm_judge_evaluation_accuracy():
    """Test LLM judge evaluation accuracy."""
    
    # Create evaluation criteria
    criteria = [
        EvaluationCriteria(
            name="accuracy",
            description="Mathematical accuracy",
            weight=1.0,
            scoring_scale=ScoringScale.PERCENTAGE,
            min_score=0.0,
            max_score=100.0,
            evaluation_prompt="Rate mathematical accuracy"
        )
    ]
    
    config = LLMJudgeConfig(
        model="gpt-4",
        criteria=criteria
    )
    
    mock_client = AsyncMock()
    llm_judge = LLMJudge(config, mock_client)
    
    # Mock correct response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "overall_score": 100.0,
        "criteria_scores": {"accuracy": 100.0},
        "reasoning": "Correct mathematical answer",
        "passed": True,
        "confidence": 1.0
    })
    mock_client.chat.completions.create.return_value = mock_response
    
    # Create task and execution
    task = GoldenTask(
        task_id="task-123",
        title="Math Test",
        description="Test math accuracy",
        category=TaskCategory.BASIC_REASONING,
        difficulty=TaskDifficulty.EASY,
        input_data={"question": "What is 3+3?"},
        expected_output={"answer": 6},
        evaluation_criteria={"accuracy": 1.0}
    )
    
    execution = TaskExecution(
        execution_id="exec-123",
        task_id="task-123",
        run_id="run-456",
        tenant_id="tenant-789",
        status=TaskStatus.COMPLETED,
        started_at=datetime.now(),
        completed_at=datetime.now(),
        actual_output={"answer": 6},
        execution_time_ms=1000
    )
    
    # Evaluate
    judge_response = await llm_judge.evaluate_task_execution(task, execution)
    
    assert judge_response.overall_score == 100.0
    assert judge_response.criteria_scores["accuracy"] == 100.0
    assert judge_response.passed is True
    assert judge_response.confidence == 1.0
