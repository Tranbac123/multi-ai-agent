"""Saga orchestrator for managing distributed transactions with compensation."""

import asyncio
import time
import uuid
from typing import Dict, List, Any, Optional, Callable, Awaitable, Union
from dataclasses import dataclass, field
from enum import Enum
import structlog
import redis.asyncio as redis

logger = structlog.get_logger(__name__)


class SagaStatus(Enum):
    """Saga execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    FAILED = "failed"


class StepStatus(Enum):
    """Saga step status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATED = "compensated"


@dataclass
class SagaStep:
    """Saga step definition."""
    step_id: str
    name: str
    operation: Callable[..., Awaitable[Any]]
    compensation: Optional[Callable[..., Awaitable[Any]]] = None
    timeout_ms: int = 30000
    retry_count: int = 0
    max_retries: int = 3
    status: StepStatus = StepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    compensation_started_at: Optional[float] = None
    compensation_completed_at: Optional[float] = None


@dataclass
class SagaDefinition:
    """Saga definition with steps and configuration."""
    saga_id: str
    name: str
    steps: List[SagaStep] = field(default_factory=list)
    timeout_ms: int = 300000  # 5 minutes
    parallel_execution: bool = False
    compensation_strategy: str = "reverse_order"  # "reverse_order" or "custom"
    created_at: float = field(default_factory=time.time)
    status: SagaStatus = SagaStatus.PENDING


class SagaOrchestrator:
    """Saga orchestrator for managing distributed transactions."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.active_sagas: Dict[str, SagaDefinition] = {}
        self.saga_metrics = {
            "total_sagas": 0,
            "completed_sagas": 0,
            "failed_sagas": 0,
            "compensated_sagas": 0,
            "active_sagas": 0
        }
    
    async def create_saga(
        self,
        name: str,
        steps: List[SagaStep],
        timeout_ms: int = 300000,
        parallel_execution: bool = False,
        compensation_strategy: str = "reverse_order"
    ) -> str:
        """Create a new saga."""
        saga_id = str(uuid.uuid4())
        
        saga = SagaDefinition(
            saga_id=saga_id,
            name=name,
            steps=steps,
            timeout_ms=timeout_ms,
            parallel_execution=parallel_execution,
            compensation_strategy=compensation_strategy
        )
        
        # Store saga definition
        await self._store_saga_definition(saga)
        self.active_sagas[saga_id] = saga
        
        # Update metrics
        self.saga_metrics["total_sagas"] += 1
        self.saga_metrics["active_sagas"] += 1
        
        logger.info("Saga created", saga_id=saga_id, name=name, steps_count=len(steps))
        
        return saga_id
    
    async def execute_saga(self, saga_id: str) -> Dict[str, Any]:
        """Execute a saga."""
        try:
            # Try to get from active sagas first, then from Redis
            saga = self.active_sagas.get(saga_id)
            if not saga:
                saga = await self._get_saga_definition(saga_id)
            if not saga:
                raise ValueError(f"Saga {saga_id} not found")
            
            saga.status = SagaStatus.RUNNING
            await self._update_saga_status(saga_id, SagaStatus.RUNNING)
            
            logger.info("Starting saga execution", saga_id=saga_id, name=saga.name)
            
            if saga.parallel_execution:
                result = await self._execute_saga_parallel(saga)
            else:
                result = await self._execute_saga_sequential(saga)
            
            if result["success"]:
                saga.status = SagaStatus.COMPLETED
                await self._update_saga_status(saga_id, SagaStatus.COMPLETED)
                self.saga_metrics["completed_sagas"] += 1
                self.saga_metrics["active_sagas"] -= 1
                
                logger.info("Saga completed successfully", saga_id=saga_id, name=saga.name)
            else:
                # Execute compensation
                await self._execute_compensation(saga)
                
                saga.status = SagaStatus.COMPENSATED
                await self._update_saga_status(saga_id, SagaStatus.COMPENSATED)
                self.saga_metrics["compensated_sagas"] += 1
                self.saga_metrics["active_sagas"] -= 1
                
                logger.info("Saga compensated", saga_id=saga_id, name=saga.name)
            
            return result
            
        except Exception as e:
            logger.error("Saga execution failed", saga_id=saga_id, error=str(e))
            
            # Try to compensate if possible
            try:
                saga = self.active_sagas.get(saga_id) or await self._get_saga_definition(saga_id)
                if saga:
                    await self._execute_compensation(saga)
                    saga.status = SagaStatus.COMPENSATED
                    await self._update_saga_status(saga_id, SagaStatus.COMPENSATED)
            except Exception as comp_error:
                logger.error("Compensation failed", saga_id=saga_id, error=str(comp_error))
            
            # Update saga status if we have it
            saga = self.active_sagas.get(saga_id)
            if saga:
                saga.status = SagaStatus.FAILED
            await self._update_saga_status(saga_id, SagaStatus.FAILED)
            self.saga_metrics["failed_sagas"] += 1
            self.saga_metrics["active_sagas"] -= 1
            
            return {
                "success": False,
                "error": str(e),
                "saga_id": saga_id,
                "status": "failed"
            }
    
    async def _execute_saga_sequential(self, saga: SagaDefinition) -> Dict[str, Any]:
        """Execute saga steps sequentially."""
        results = []
        
        for step in saga.steps:
            try:
                step.status = StepStatus.RUNNING
                step.started_at = time.time()
                await self._update_step_status(saga.saga_id, step.step_id, StepStatus.RUNNING)
                
                # Execute step with timeout
                result = await asyncio.wait_for(
                    step.operation(),
                    timeout=step.timeout_ms / 1000.0
                )
                
                step.result = result
                step.status = StepStatus.COMPLETED
                step.completed_at = time.time()
                await self._update_step_status(saga.saga_id, step.step_id, StepStatus.COMPLETED)
                
                results.append({
                    "step_id": step.step_id,
                    "name": step.name,
                    "status": "completed",
                    "result": result
                })
                
                logger.info("Saga step completed", saga_id=saga.saga_id, step_id=step.step_id, name=step.name)
                
            except asyncio.TimeoutError:
                step.status = StepStatus.FAILED
                step.error = f"Step timed out after {step.timeout_ms}ms"
                step.completed_at = time.time()
                await self._update_step_status(saga.saga_id, step.step_id, StepStatus.FAILED)
                
                logger.error("Saga step timed out", saga_id=saga.saga_id, step_id=step.step_id, name=step.name)
                
                return {
                    "success": False,
                    "error": f"Step {step.step_id} timed out",
                    "completed_steps": results,
                    "failed_step": step.step_id
                }
                
            except Exception as e:
                step.status = StepStatus.FAILED
                step.error = str(e)
                step.completed_at = time.time()
                await self._update_step_status(saga.saga_id, step.step_id, StepStatus.FAILED)
                
                logger.error("Saga step failed", saga_id=saga.saga_id, step_id=step.step_id, name=step.name, error=str(e))
                
                return {
                    "success": False,
                    "error": f"Step {step.step_id} failed: {str(e)}",
                    "completed_steps": results,
                    "failed_step": step.step_id
                }
        
        return {
            "success": True,
            "results": results,
            "saga_id": saga.saga_id
        }
    
    async def _execute_saga_parallel(self, saga: SagaDefinition) -> Dict[str, Any]:
        """Execute saga steps in parallel."""
        try:
            # Create tasks for all steps
            tasks = []
            for step in saga.steps:
                step.status = StepStatus.RUNNING
                step.started_at = time.time()
                await self._update_step_status(saga.saga_id, step.step_id, StepStatus.RUNNING)
                
                task = asyncio.create_task(self._execute_step_with_retry(step))
                tasks.append((step, task))
            
            # Wait for all tasks to complete
            results = []
            for step, task in tasks:
                try:
                    result = await task
                    step.result = result
                    step.status = StepStatus.COMPLETED
                    step.completed_at = time.time()
                    await self._update_step_status(saga.saga_id, step.step_id, StepStatus.COMPLETED)
                    
                    results.append({
                        "step_id": step.step_id,
                        "name": step.name,
                        "status": "completed",
                        "result": result
                    })
                    
                except Exception as e:
                    step.status = StepStatus.FAILED
                    step.error = str(e)
                    step.completed_at = time.time()
                    await self._update_step_status(saga.saga_id, step.step_id, StepStatus.FAILED)
                    
                    logger.error("Saga step failed in parallel execution", saga_id=saga.saga_id, step_id=step.step_id, error=str(e))
                    
                    return {
                        "success": False,
                        "error": f"Step {step.step_id} failed: {str(e)}",
                        "completed_steps": results,
                        "failed_step": step.step_id
                    }
            
            return {
                "success": True,
                "results": results,
                "saga_id": saga.saga_id
            }
            
        except Exception as e:
            logger.error("Parallel saga execution failed", saga_id=saga.saga_id, error=str(e))
            return {
                "success": False,
                "error": str(e),
                "saga_id": saga.saga_id
            }
    
    async def _execute_step_with_retry(self, step: SagaStep) -> Any:
        """Execute a step with retry logic."""
        last_exception = None
        
        for attempt in range(step.max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    step.operation(),
                    timeout=step.timeout_ms / 1000.0
                )
                return result
                
            except Exception as e:
                last_exception = e
                step.retry_count += 1
                
                if attempt < step.max_retries:
                    delay = min(1000 * (2 ** attempt), 10000)  # Exponential backoff, max 10s
                    logger.warning("Step failed, retrying", step_id=step.step_id, attempt=attempt, delay=delay, error=str(e))
                    await asyncio.sleep(delay / 1000.0)
                else:
                    logger.error("Step failed after all retries", step_id=step.step_id, attempts=attempt, error=str(e))
        
        raise last_exception
    
    async def _execute_compensation(self, saga: SagaDefinition) -> None:
        """Execute compensation for a saga."""
        try:
            saga.status = SagaStatus.COMPENSATING
            await self._update_saga_status(saga.saga_id, SagaStatus.COMPENSATING)
            
            logger.info("Starting saga compensation", saga_id=saga.saga_id, name=saga.name)
            
            # Get completed steps in reverse order
            completed_steps = [step for step in saga.steps if step.status == StepStatus.COMPLETED]
            
            if saga.compensation_strategy == "reverse_order":
                completed_steps.reverse()
            
            for step in completed_steps:
                if step.compensation:
                    try:
                        step.compensation_started_at = time.time()
                        await step.compensation()
                        step.status = StepStatus.COMPENSATED
                        step.compensation_completed_at = time.time()
                        await self._update_step_status(saga.saga_id, step.step_id, StepStatus.COMPENSATED)
                        
                        logger.info("Step compensation completed", saga_id=saga.saga_id, step_id=step.step_id, name=step.name)
                        
                    except Exception as e:
                        logger.error("Step compensation failed", saga_id=saga.saga_id, step_id=step.step_id, name=step.name, error=str(e))
                        # Continue with other compensations even if one fails
            
            logger.info("Saga compensation completed", saga_id=saga.saga_id, name=saga.name)
            
        except Exception as e:
            logger.error("Saga compensation failed", saga_id=saga.saga_id, error=str(e))
            raise
    
    async def get_saga_status(self, saga_id: str) -> Optional[Dict[str, Any]]:
        """Get saga status and details."""
        # Try to get from active sagas first, then from Redis
        saga = self.active_sagas.get(saga_id)
        if not saga:
            saga = await self._get_saga_definition(saga_id)
        if not saga:
            return None
        
        return {
            "saga_id": saga.saga_id,
            "name": saga.name,
            "status": saga.status.value,
            "created_at": saga.created_at,
            "steps": [
                {
                    "step_id": step.step_id,
                    "name": step.name,
                    "status": step.status.value,
                    "started_at": step.started_at,
                    "completed_at": step.completed_at,
                    "error": step.error
                }
                for step in saga.steps
            ]
        }
    
    async def get_saga_metrics(self) -> Dict[str, Any]:
        """Get saga orchestrator metrics."""
        return {
            "total_sagas": self.saga_metrics["total_sagas"],
            "completed_sagas": self.saga_metrics["completed_sagas"],
            "failed_sagas": self.saga_metrics["failed_sagas"],
            "compensated_sagas": self.saga_metrics["compensated_sagas"],
            "active_sagas": self.saga_metrics["active_sagas"],
            "success_rate": (
                self.saga_metrics["completed_sagas"] / self.saga_metrics["total_sagas"]
                if self.saga_metrics["total_sagas"] > 0 else 0
            )
        }
    
    async def _store_saga_definition(self, saga: SagaDefinition) -> None:
        """Store saga definition in Redis."""
        try:
            import json
            saga_data = {
                "saga_id": saga.saga_id,
                "name": saga.name,
                "timeout_ms": saga.timeout_ms,
                "parallel_execution": saga.parallel_execution,
                "compensation_strategy": saga.compensation_strategy,
                "created_at": saga.created_at,
                "status": saga.status.value,
                "steps": [
                    {
                        "step_id": step.step_id,
                        "name": step.name,
                        "timeout_ms": step.timeout_ms,
                        "max_retries": step.max_retries,
                        "status": step.status.value
                    }
                    for step in saga.steps
                ]
            }
            
            key = f"saga_definition:{saga.saga_id}"
            await self.redis.setex(key, 86400, json.dumps(saga_data))  # 24 hours TTL
            
        except Exception as e:
            logger.error("Failed to store saga definition", saga_id=saga.saga_id, error=str(e))
    
    async def _get_saga_definition(self, saga_id: str) -> Optional[SagaDefinition]:
        """Get saga definition from Redis."""
        try:
            key = f"saga_definition:{saga_id}"
            saga_data = await self.redis.get(key)
            
            if not saga_data:
                return None
            
            import json
            data = json.loads(saga_data)
            
            # Reconstruct saga definition
            saga = SagaDefinition(
                saga_id=data["saga_id"],
                name=data["name"],
                timeout_ms=data["timeout_ms"],
                parallel_execution=data["parallel_execution"],
                compensation_strategy=data["compensation_strategy"],
                created_at=data["created_at"],
                status=SagaStatus(data["status"])
            )
            
            # Reconstruct steps
            for step_data in data["steps"]:
                step = SagaStep(
                    step_id=step_data["step_id"],
                    name=step_data["name"],
                    timeout_ms=step_data["timeout_ms"],
                    max_retries=step_data["max_retries"],
                    status=StepStatus(step_data["status"])
                )
                saga.steps.append(step)
            
            return saga
            
        except Exception as e:
            logger.error("Failed to get saga definition", saga_id=saga_id, error=str(e))
            return None
    
    async def _update_saga_status(self, saga_id: str, status: SagaStatus) -> None:
        """Update saga status in Redis."""
        try:
            key = f"saga_status:{saga_id}"
            await self.redis.setex(key, 86400, status.value)  # 24 hours TTL
        except Exception as e:
            logger.error("Failed to update saga status", saga_id=saga_id, status=status.value, error=str(e))
    
    async def _update_step_status(self, saga_id: str, step_id: str, status: StepStatus) -> None:
        """Update step status in Redis."""
        try:
            key = f"saga_step_status:{saga_id}:{step_id}"
            await self.redis.setex(key, 86400, status.value)  # 24 hours TTL
        except Exception as e:
            logger.error("Failed to update step status", saga_id=saga_id, step_id=step_id, status=status.value, error=str(e))