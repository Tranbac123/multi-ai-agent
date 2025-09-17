"""
Golden Tasks for Evaluation

Manages golden task datasets for evaluation, validation, and regression testing
with comprehensive task management and result tracking.
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


class TaskCategory(Enum):
    """Task categories for evaluation."""
    BASIC_REASONING = "basic_reasoning"
    COMPLEX_REASONING = "complex_reasoning"
    CODE_GENERATION = "code_generation"
    DATA_ANALYSIS = "data_analysis"
    CREATIVE_WRITING = "creative_writing"
    MULTIMODAL = "multimodal"
    EDGE_CASES = "edge_cases"
    STRESS_TEST = "stress_test"


class TaskDifficulty(Enum):
    """Task difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass
class GoldenTask:
    """Golden task definition."""
    
    task_id: str
    title: str
    description: str
    category: TaskCategory
    difficulty: TaskDifficulty
    input_data: Dict[str, Any]
    expected_output: Dict[str, Any]
    evaluation_criteria: Dict[str, Any]
    tags: Set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: int = 1
    is_active: bool = True
    timeout_seconds: int = 300
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskExecution:
    """Task execution record."""
    
    execution_id: str
    task_id: str
    run_id: str
    tenant_id: str
    status: TaskStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    actual_output: Optional[Dict[str, Any]] = None
    evaluation_score: Optional[float] = None
    evaluation_details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationResult:
    """Evaluation result for a task execution."""
    
    execution_id: str
    task_id: str
    overall_score: float
    criteria_scores: Dict[str, float]
    passed: bool
    evaluation_method: str
    evaluated_at: datetime
    evaluator_metadata: Dict[str, Any] = field(default_factory=dict)


class GoldenTaskManager:
    """Manages golden tasks for evaluation."""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        
        logger.info("Golden task manager initialized")
    
    async def create_golden_task(
        self,
        title: str,
        description: str,
        category: TaskCategory,
        difficulty: TaskDifficulty,
        input_data: Dict[str, Any],
        expected_output: Dict[str, Any],
        evaluation_criteria: Dict[str, Any],
        tags: Optional[Set[str]] = None,
        timeout_seconds: int = 300,
        max_retries: int = 3,
        metadata: Optional[Dict[str, Any]] = None
    ) -> GoldenTask:
        """Create a new golden task."""
        
        task_id = str(uuid.uuid4())
        
        task = GoldenTask(
            task_id=task_id,
            title=title,
            description=description,
            category=category,
            difficulty=difficulty,
            input_data=input_data,
            expected_output=expected_output,
            evaluation_criteria=evaluation_criteria,
            tags=tags or set(),
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            metadata=metadata or {}
        )
        
        await self._store_golden_task(task)
        
        logger.info("Golden task created", 
                   task_id=task_id,
                   title=title,
                   category=category.value,
                   difficulty=difficulty.value)
        
        return task
    
    async def _store_golden_task(self, task: GoldenTask):
        """Store golden task in database."""
        
        query = """
        INSERT INTO golden_tasks (
            task_id, title, description, category, difficulty,
            input_data, expected_output, evaluation_criteria,
            tags, created_at, updated_at, version, is_active,
            timeout_seconds, max_retries, metadata
        ) VALUES (
            :task_id, :title, :description, :category, :difficulty,
            :input_data, :expected_output, :evaluation_criteria,
            :tags, :created_at, :updated_at, :version, :is_active,
            :timeout_seconds, :max_retries, :metadata
        )
        """
        
        await self.db_session.execute(text(query), {
            "task_id": task.task_id,
            "title": task.title,
            "description": task.description,
            "category": task.category.value,
            "difficulty": task.difficulty.value,
            "input_data": json.dumps(task.input_data),
            "expected_output": json.dumps(task.expected_output),
            "evaluation_criteria": json.dumps(task.evaluation_criteria),
            "tags": list(task.tags),
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "version": task.version,
            "is_active": task.is_active,
            "timeout_seconds": task.timeout_seconds,
            "max_retries": task.max_retries,
            "metadata": json.dumps(task.metadata)
        })
        
        await self.db_session.commit()
    
    async def get_golden_task(self, task_id: str) -> Optional[GoldenTask]:
        """Get golden task by ID."""
        
        query = """
        SELECT * FROM golden_tasks 
        WHERE task_id = :task_id AND is_active = true
        """
        
        result = await self.db_session.execute(text(query), {"task_id": task_id})
        row = result.fetchone()
        
        if not row:
            return None
        
        return self._row_to_golden_task(row)
    
    async def get_golden_tasks(
        self,
        category: Optional[TaskCategory] = None,
        difficulty: Optional[TaskDifficulty] = None,
        tags: Optional[Set[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[GoldenTask]:
        """Get golden tasks with filters."""
        
        query = """
        SELECT * FROM golden_tasks 
        WHERE is_active = true
        """
        
        params = {}
        
        if category:
            query += " AND category = :category"
            params["category"] = category.value
        
        if difficulty:
            query += " AND difficulty = :difficulty"
            params["difficulty"] = difficulty.value
        
        if tags:
            # Filter by tags (simplified - in production, use proper array operations)
            tag_conditions = []
            for i, tag in enumerate(tags):
                param_name = f"tag_{i}"
                tag_conditions.append(f":{param_name} = ANY(tags)")
                params[param_name] = tag
            
            if tag_conditions:
                query += f" AND ({' OR '.join(tag_conditions)})"
        
        query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset
        
        result = await self.db_session.execute(text(query), params)
        rows = result.fetchall()
        
        return [self._row_to_golden_task(row) for row in rows]
    
    async def update_golden_task(self, task: GoldenTask):
        """Update an existing golden task."""
        
        task.updated_at = datetime.now()
        task.version += 1
        
        query = """
        UPDATE golden_tasks 
        SET title = :title, description = :description, category = :category,
            difficulty = :difficulty, input_data = :input_data,
            expected_output = :expected_output, evaluation_criteria = :evaluation_criteria,
            tags = :tags, updated_at = :updated_at, version = :version,
            timeout_seconds = :timeout_seconds, max_retries = :max_retries,
            metadata = :metadata
        WHERE task_id = :task_id
        """
        
        await self.db_session.execute(text(query), {
            "task_id": task.task_id,
            "title": task.title,
            "description": task.description,
            "category": task.category.value,
            "difficulty": task.difficulty.value,
            "input_data": json.dumps(task.input_data),
            "expected_output": json.dumps(task.expected_output),
            "evaluation_criteria": json.dumps(task.evaluation_criteria),
            "tags": list(task.tags),
            "updated_at": task.updated_at,
            "version": task.version,
            "timeout_seconds": task.timeout_seconds,
            "max_retries": task.max_retries,
            "metadata": json.dumps(task.metadata)
        })
        
        await self.db_session.commit()
        
        logger.info("Golden task updated", 
                   task_id=task.task_id,
                   version=task.version)
    
    async def deactivate_golden_task(self, task_id: str):
        """Deactivate a golden task."""
        
        query = """
        UPDATE golden_tasks 
        SET is_active = false, updated_at = :updated_at
        WHERE task_id = :task_id
        """
        
        await self.db_session.execute(text(query), {
            "task_id": task_id,
            "updated_at": datetime.now()
        })
        
        await self.db_session.commit()
        
        logger.info("Golden task deactivated", task_id=task_id)
    
    async def execute_task(
        self,
        task: GoldenTask,
        run_id: str,
        tenant_id: str,
        executor_func: callable
    ) -> TaskExecution:
        """Execute a golden task."""
        
        execution_id = str(uuid.uuid4())
        
        execution = TaskExecution(
            execution_id=execution_id,
            task_id=task.task_id,
            run_id=run_id,
            tenant_id=tenant_id,
            status=TaskStatus.PENDING,
            started_at=datetime.now()
        )
        
        await self._store_task_execution(execution)
        
        try:
            # Update status to running
            execution.status = TaskStatus.RUNNING
            await self._update_task_execution(execution)
            
            # Execute the task with timeout
            start_time = datetime.now()
            
            actual_output = await asyncio.wait_for(
                executor_func(task.input_data),
                timeout=task.timeout_seconds
            )
            
            end_time = datetime.now()
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Update execution with results
            execution.status = TaskStatus.COMPLETED
            execution.completed_at = end_time
            execution.actual_output = actual_output
            execution.execution_time_ms = execution_time_ms
            
            await self._update_task_execution(execution)
            
            logger.info("Golden task executed successfully", 
                       execution_id=execution_id,
                       task_id=task.task_id,
                       execution_time_ms=execution_time_ms)
            
        except asyncio.TimeoutError:
            execution.status = TaskStatus.TIMEOUT
            execution.completed_at = datetime.now()
            execution.error_message = f"Task timed out after {task.timeout_seconds} seconds"
            
            await self._update_task_execution(execution)
            
            logger.warning("Golden task timed out", 
                          execution_id=execution_id,
                          task_id=task.task_id,
                          timeout_seconds=task.timeout_seconds)
            
        except Exception as e:
            execution.status = TaskStatus.FAILED
            execution.completed_at = datetime.now()
            execution.error_message = str(e)
            
            await self._update_task_execution(execution)
            
            logger.error("Golden task execution failed", 
                        execution_id=execution_id,
                        task_id=task.task_id,
                        error=str(e))
        
        return execution
    
    async def _store_task_execution(self, execution: TaskExecution):
        """Store task execution in database."""
        
        query = """
        INSERT INTO task_executions (
            execution_id, task_id, run_id, tenant_id, status,
            started_at, completed_at, actual_output, evaluation_score,
            evaluation_details, error_message, execution_time_ms,
            retry_count, metadata
        ) VALUES (
            :execution_id, :task_id, :run_id, :tenant_id, :status,
            :started_at, :completed_at, :actual_output, :evaluation_score,
            :evaluation_details, :error_message, :execution_time_ms,
            :retry_count, :metadata
        )
        """
        
        await self.db_session.execute(text(query), {
            "execution_id": execution.execution_id,
            "task_id": execution.task_id,
            "run_id": execution.run_id,
            "tenant_id": execution.tenant_id,
            "status": execution.status.value,
            "started_at": execution.started_at,
            "completed_at": execution.completed_at,
            "actual_output": json.dumps(execution.actual_output) if execution.actual_output else None,
            "evaluation_score": execution.evaluation_score,
            "evaluation_details": json.dumps(execution.evaluation_details) if execution.evaluation_details else None,
            "error_message": execution.error_message,
            "execution_time_ms": execution.execution_time_ms,
            "retry_count": execution.retry_count,
            "metadata": json.dumps(execution.metadata)
        })
        
        await self.db_session.commit()
    
    async def _update_task_execution(self, execution: TaskExecution):
        """Update task execution in database."""
        
        query = """
        UPDATE task_executions 
        SET status = :status, completed_at = :completed_at,
            actual_output = :actual_output, evaluation_score = :evaluation_score,
            evaluation_details = :evaluation_details, error_message = :error_message,
            execution_time_ms = :execution_time_ms, retry_count = :retry_count,
            metadata = :metadata
        WHERE execution_id = :execution_id
        """
        
        await self.db_session.execute(text(query), {
            "execution_id": execution.execution_id,
            "status": execution.status.value,
            "completed_at": execution.completed_at,
            "actual_output": json.dumps(execution.actual_output) if execution.actual_output else None,
            "evaluation_score": execution.evaluation_score,
            "evaluation_details": json.dumps(execution.evaluation_details) if execution.evaluation_details else None,
            "error_message": execution.error_message,
            "execution_time_ms": execution.execution_time_ms,
            "retry_count": execution.retry_count,
            "metadata": json.dumps(execution.metadata)
        })
        
        await self.db_session.commit()
    
    async def get_task_executions(
        self,
        task_id: Optional[str] = None,
        run_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[TaskExecution]:
        """Get task executions with filters."""
        
        query = """
        SELECT * FROM task_executions 
        WHERE 1=1
        """
        
        params = {}
        
        if task_id:
            query += " AND task_id = :task_id"
            params["task_id"] = task_id
        
        if run_id:
            query += " AND run_id = :run_id"
            params["run_id"] = run_id
        
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = tenant_id
        
        if status:
            query += " AND status = :status"
            params["status"] = status.value
        
        query += " ORDER BY started_at DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset
        
        result = await self.db_session.execute(text(query), params)
        rows = result.fetchall()
        
        return [self._row_to_task_execution(row) for row in rows]
    
    def _row_to_golden_task(self, row) -> GoldenTask:
        """Convert database row to GoldenTask object."""
        
        return GoldenTask(
            task_id=row.task_id,
            title=row.title,
            description=row.description,
            category=TaskCategory(row.category),
            difficulty=TaskDifficulty(row.difficulty),
            input_data=json.loads(row.input_data),
            expected_output=json.loads(row.expected_output),
            evaluation_criteria=json.loads(row.evaluation_criteria),
            tags=set(row.tags) if row.tags else set(),
            created_at=row.created_at,
            updated_at=row.updated_at,
            version=row.version,
            is_active=row.is_active,
            timeout_seconds=row.timeout_seconds,
            max_retries=row.max_retries,
            metadata=json.loads(row.metadata) if row.metadata else {}
        )
    
    def _row_to_task_execution(self, row) -> TaskExecution:
        """Convert database row to TaskExecution object."""
        
        return TaskExecution(
            execution_id=row.execution_id,
            task_id=row.task_id,
            run_id=row.run_id,
            tenant_id=row.tenant_id,
            status=TaskStatus(row.status),
            started_at=row.started_at,
            completed_at=row.completed_at,
            actual_output=json.loads(row.actual_output) if row.actual_output else None,
            evaluation_score=row.evaluation_score,
            evaluation_details=json.loads(row.evaluation_details) if row.evaluation_details else None,
            error_message=row.error_message,
            execution_time_ms=row.execution_time_ms,
            retry_count=row.retry_count,
            metadata=json.loads(row.metadata) if row.metadata else {}
        )
    
    async def get_task_statistics(self) -> Dict[str, Any]:
        """Get statistics about golden tasks and executions."""
        
        # Task statistics
        task_query = """
        SELECT 
            category,
            difficulty,
            COUNT(*) as task_count
        FROM golden_tasks 
        WHERE is_active = true
        GROUP BY category, difficulty
        """
        
        task_result = await self.db_session.execute(text(task_query))
        task_stats = task_result.fetchall()
        
        # Execution statistics
        exec_query = """
        SELECT 
            status,
            COUNT(*) as execution_count,
            AVG(execution_time_ms) as avg_execution_time_ms
        FROM task_executions 
        GROUP BY status
        """
        
        exec_result = await self.db_session.execute(text(exec_query))
        exec_stats = exec_result.fetchall()
        
        return {
            "task_statistics": {
                "by_category": {row.category: row.task_count for row in task_stats},
                "by_difficulty": {row.difficulty: row.task_count for row in task_stats}
            },
            "execution_statistics": {
                "by_status": {
                    row.status: {
                        "count": row.execution_count,
                        "avg_execution_time_ms": row.avg_execution_time_ms
                    }
                    for row in exec_stats
                }
            },
            "timestamp": datetime.now().isoformat()
        }
