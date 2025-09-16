"""
Evaluation Service

FastAPI application for golden task evaluation, LLM judge assessment,
and episode replay functionality.
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
import structlog
from typing import List, Optional, Dict, Any

from .core.golden_tasks import (
    GoldenTaskManager, GoldenTask, TaskCategory, TaskDifficulty, TaskStatus,
    TaskExecution, EvaluationResult
)
from .core.llm_judge import (
    LLMJudge, LLMJudgeConfig, EvaluationCriteria, ScoringScale,
    EvaluationMethod, EvaluationEngine
)
from .core.episode_replay import (
    EpisodeReplayManager, Episode, EpisodeState, StateType,
    ReplayRequest, ReplayExecution, ReplayStatus
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    logger.info("Evaluation service starting up")
    
    # Initialize services
    app.state.task_manager = None
    app.state.replay_manager = None
    app.state.evaluation_engine = None
    
    yield
    
    logger.info("Evaluation service shutting down")


app = FastAPI(
    title="Evaluation Service",
    description="Golden task evaluation, LLM judge assessment, and episode replay",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_db_session() -> AsyncSession:
    """Get database session dependency."""
    # In a real implementation, this would return an actual database session
    # For now, we'll use a mock session
    return AsyncSession()


async def get_task_manager(db_session: AsyncSession = Depends(get_db_session)) -> GoldenTaskManager:
    """Get golden task manager dependency."""
    if not app.state.task_manager:
        app.state.task_manager = GoldenTaskManager(db_session)
    return app.state.task_manager


async def get_replay_manager(db_session: AsyncSession = Depends(get_db_session)) -> EpisodeReplayManager:
    """Get episode replay manager dependency."""
    if not app.state.replay_manager:
        app.state.replay_manager = EpisodeReplayManager(db_session)
    return app.state.replay_manager


async def get_evaluation_engine() -> EvaluationEngine:
    """Get evaluation engine dependency."""
    if not app.state.evaluation_engine:
        # Create LLM judge configuration
        criteria = [
            EvaluationCriteria(
                name="accuracy",
                description="Accuracy of the response",
                weight=0.4,
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
                weight=0.3,
                scoring_scale=ScoringScale.PERCENTAGE,
                min_score=0.0,
                max_score=100.0,
                evaluation_prompt="Rate the relevance of the response"
            )
        ]
        
        judge_config = LLMJudgeConfig(
            model="gpt-4",
            temperature=0.1,
            max_tokens=1000,
            timeout_seconds=60,
            criteria=criteria
        )
        
        llm_judge = LLMJudge(judge_config)
        app.state.evaluation_engine = EvaluationEngine(llm_judge)
    
    return app.state.evaluation_engine


# Golden Task Endpoints

@app.post("/golden-tasks", response_model=Dict[str, str])
async def create_golden_task(
    title: str,
    description: str,
    category: TaskCategory,
    difficulty: TaskDifficulty,
    input_data: Dict[str, Any],
    expected_output: Dict[str, Any],
    evaluation_criteria: Dict[str, Any],
    tags: Optional[List[str]] = None,
    timeout_seconds: int = 300,
    max_retries: int = 3,
    metadata: Optional[Dict[str, Any]] = None,
    task_manager: GoldenTaskManager = Depends(get_task_manager)
):
    """Create a new golden task."""
    
    try:
        task = await task_manager.create_golden_task(
            title=title,
            description=description,
            category=category,
            difficulty=difficulty,
            input_data=input_data,
            expected_output=expected_output,
            evaluation_criteria=evaluation_criteria,
            tags=set(tags) if tags else None,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            metadata=metadata
        )
        
        return {"task_id": task.task_id, "status": "created"}
        
    except Exception as e:
        logger.error("Failed to create golden task", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/golden-tasks/{task_id}", response_model=Dict[str, Any])
async def get_golden_task(
    task_id: str,
    task_manager: GoldenTaskManager = Depends(get_task_manager)
):
    """Get golden task by ID."""
    
    task = await task_manager.get_golden_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "task_id": task.task_id,
        "title": task.title,
        "description": task.description,
        "category": task.category.value,
        "difficulty": task.difficulty.value,
        "input_data": task.input_data,
        "expected_output": task.expected_output,
        "evaluation_criteria": task.evaluation_criteria,
        "tags": list(task.tags),
        "timeout_seconds": task.timeout_seconds,
        "max_retries": task.max_retries,
        "is_active": task.is_active,
        "version": task.version,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat()
    }


@app.get("/golden-tasks", response_model=List[Dict[str, Any]])
async def list_golden_tasks(
    category: Optional[TaskCategory] = None,
    difficulty: Optional[TaskDifficulty] = None,
    tags: Optional[List[str]] = None,
    limit: int = 100,
    offset: int = 0,
    task_manager: GoldenTaskManager = Depends(get_task_manager)
):
    """List golden tasks with filters."""
    
    tasks = await task_manager.get_golden_tasks(
        category=category,
        difficulty=difficulty,
        tags=set(tags) if tags else None,
        limit=limit,
        offset=offset
    )
    
    return [
        {
            "task_id": task.task_id,
            "title": task.title,
            "description": task.description,
            "category": task.category.value,
            "difficulty": task.difficulty.value,
            "tags": list(task.tags),
            "is_active": task.is_active,
            "created_at": task.created_at.isoformat()
        }
        for task in tasks
    ]


@app.post("/golden-tasks/{task_id}/execute", response_model=Dict[str, Any])
async def execute_golden_task(
    task_id: str,
    run_id: str,
    tenant_id: str,
    executor_config: Dict[str, Any],
    task_manager: GoldenTaskManager = Depends(get_task_manager)
):
    """Execute a golden task."""
    
    task = await task_manager.get_golden_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Mock executor function (in real implementation, this would be dynamic)
    async def mock_executor(input_data: Dict[str, Any]) -> Dict[str, Any]:
        # This would be replaced with actual agent execution
        return {"result": "mock_execution", "input_received": input_data}
    
    try:
        execution = await task_manager.execute_task(
            task=task,
            run_id=run_id,
            tenant_id=tenant_id,
            executor_func=mock_executor
        )
        
        return {
            "execution_id": execution.execution_id,
            "task_id": execution.task_id,
            "status": execution.status.value,
            "started_at": execution.started_at.isoformat(),
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
            "actual_output": execution.actual_output,
            "execution_time_ms": execution.execution_time_ms,
            "error_message": execution.error_message
        }
        
    except Exception as e:
        logger.error("Failed to execute golden task", task_id=task_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# Episode Replay Endpoints

@app.post("/episodes", response_model=Dict[str, str])
async def create_episode(
    run_id: str,
    tenant_id: str,
    task_id: str,
    agent_config: Dict[str, Any],
    initial_state: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
    replay_manager: EpisodeReplayManager = Depends(get_replay_manager)
):
    """Record a new episode."""
    
    try:
        episode = await replay_manager.record_episode(
            run_id=run_id,
            tenant_id=tenant_id,
            task_id=task_id,
            agent_config=agent_config,
            initial_state=initial_state
        )
        
        return {"episode_id": episode.episode_id, "status": "recorded"}
        
    except Exception as e:
        logger.error("Failed to create episode", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/episodes/{episode_id}/states", response_model=Dict[str, str])
async def record_state_snapshot(
    episode_id: str,
    step_number: int,
    state_type: StateType,
    agent_state: Dict[str, Any],
    environment_state: Dict[str, Any],
    action_taken: Optional[Dict[str, Any]] = None,
    observation: Optional[Dict[str, Any]] = None,
    reward: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
    replay_manager: EpisodeReplayManager = Depends(get_replay_manager)
):
    """Record a state snapshot."""
    
    try:
        state = await replay_manager.record_state_snapshot(
            episode_id=episode_id,
            step_number=step_number,
            state_type=state_type,
            agent_state=agent_state,
            environment_state=environment_state,
            action_taken=action_taken,
            observation=observation,
            reward=reward,
            metadata=metadata
        )
        
        return {"state_id": state.state_id, "status": "recorded"}
        
    except Exception as e:
        logger.error("Failed to record state snapshot", episode_id=episode_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/episodes/{episode_id}/finalize", response_model=Dict[str, str])
async def finalize_episode(
    episode_id: str,
    final_state: Dict[str, Any],
    success: bool,
    total_reward: float,
    steps_count: int,
    duration_ms: int,
    replay_manager: EpisodeReplayManager = Depends(get_replay_manager)
):
    """Finalize an episode."""
    
    try:
        await replay_manager.finalize_episode(
            episode_id=episode_id,
            final_state=final_state,
            success=success,
            total_reward=total_reward,
            steps_count=steps_count,
            duration_ms=duration_ms
        )
        
        return {"episode_id": episode_id, "status": "finalized"}
        
    except Exception as e:
        logger.error("Failed to finalize episode", episode_id=episode_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/replays", response_model=Dict[str, str])
async def create_replay_request(
    episode_id: str,
    replay_config: Dict[str, Any],
    target_step: Optional[int] = None,
    replay_mode: str = "full",
    breakpoints: Optional[List[int]] = None,
    variable_overrides: Optional[Dict[str, Any]] = None,
    replay_manager: EpisodeReplayManager = Depends(get_replay_manager)
):
    """Create a replay request."""
    
    try:
        replay_request = await replay_manager.create_replay_request(
            episode_id=episode_id,
            replay_config=replay_config,
            target_step=target_step,
            replay_mode=replay_mode,
            breakpoints=breakpoints or [],
            variable_overrides=variable_overrides or {}
        )
        
        return {"replay_id": replay_request.replay_id, "status": "created"}
        
    except Exception as e:
        logger.error("Failed to create replay request", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/replays/{replay_id}/execute", response_model=Dict[str, Any])
async def execute_replay(
    replay_id: str,
    background_tasks: BackgroundTasks,
    replay_manager: EpisodeReplayManager = Depends(get_replay_manager)
):
    """Execute episode replay."""
    
    # Mock replay executor (in real implementation, this would be dynamic)
    async def mock_replay_executor(
        episode, states, replay_config, target_step, replay_mode, breakpoints, variable_overrides
    ):
        return {
            "status": "completed",
            "steps_replayed": len(states),
            "replay_mode": replay_mode,
            "target_step": target_step
        }
    
    try:
        # Get replay request (this would be implemented in the real service)
        # For now, we'll create a mock replay request
        from .core.episode_replay import ReplayRequest
        replay_request = ReplayRequest(
            replay_id=replay_id,
            episode_id="mock-episode-id",
            replay_config={"debug": True}
        )
        
        execution = await replay_manager.execute_replay(replay_request, mock_replay_executor)
        
        return {
            "replay_id": execution.replay_id,
            "episode_id": execution.episode_id,
            "status": execution.status.value,
            "started_at": execution.started_at.isoformat(),
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
            "replay_results": execution.replay_results,
            "execution_time_ms": execution.execution_time_ms,
            "error_message": execution.error_message
        }
        
    except Exception as e:
        logger.error("Failed to execute replay", replay_id=replay_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# Evaluation Endpoints

@app.post("/evaluations", response_model=List[Dict[str, Any]])
async def evaluate_execution(
    execution_id: str,
    task_id: str,
    methods: Optional[List[EvaluationMethod]] = None,
    evaluation_engine: EvaluationEngine = Depends(get_evaluation_engine),
    task_manager: GoldenTaskManager = Depends(get_task_manager)
):
    """Evaluate a task execution."""
    
    # Get task and execution (this would be implemented in the real service)
    task = await task_manager.get_golden_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Mock execution (in real implementation, this would be retrieved from database)
    from .core.golden_tasks import TaskExecution
    execution = TaskExecution(
        execution_id=execution_id,
        task_id=task_id,
        run_id="mock-run-id",
        tenant_id="mock-tenant-id",
        status=TaskStatus.COMPLETED,
        started_at=datetime.now(),
        completed_at=datetime.now(),
        actual_output={"result": "mock_output"}
    )
    
    try:
        results = await evaluation_engine.evaluate_execution(
            task=task,
            execution=execution,
            methods=methods or [EvaluationMethod.LLM_JUDGE]
        )
        
        return [
            {
                "execution_id": result.execution_id,
                "task_id": result.task_id,
                "overall_score": result.overall_score,
                "criteria_scores": result.criteria_scores,
                "passed": result.passed,
                "evaluation_method": result.evaluation_method,
                "evaluated_at": result.evaluated_at.isoformat(),
                "evaluator_metadata": result.evaluator_metadata
            }
            for result in results
        ]
        
    except Exception as e:
        logger.error("Failed to evaluate execution", execution_id=execution_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# Statistics Endpoints

@app.get("/statistics/tasks", response_model=Dict[str, Any])
async def get_task_statistics(
    task_manager: GoldenTaskManager = Depends(get_task_manager)
):
    """Get task statistics."""
    
    try:
        stats = await task_manager.get_task_statistics()
        return stats
        
    except Exception as e:
        logger.error("Failed to get task statistics", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/statistics/episodes", response_model=Dict[str, Any])
async def get_episode_statistics(
    replay_manager: EpisodeReplayManager = Depends(get_replay_manager)
):
    """Get episode statistics."""
    
    try:
        stats = await replay_manager.get_episode_statistics()
        return stats
        
    except Exception as e:
        logger.error("Failed to get episode statistics", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# Health Check

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "evaluation"}
