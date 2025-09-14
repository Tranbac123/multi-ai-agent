"""Saga pattern implementation for distributed transactions."""

import asyncio
import time
import uuid
from typing import Dict, Any, Optional, List, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
import structlog

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
    execute_func: Callable[..., Awaitable[Any]]
    compensate_func: Optional[Callable[..., Awaitable[Any]]] = None
    timeout: float = 30.0
    retry_attempts: int = 0
    max_retries: int = 3
    status: StepStatus = StepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


@dataclass
class Saga:
    """Saga definition with steps and configuration."""
    saga_id: str
    name: str
    steps: List[SagaStep] = field(default_factory=list)
    timeout: float = 300.0  # 5 minutes
    parallel_execution: bool = False
    compensation_strategy: str = "reverse_order"
    created_at: float = field(default_factory=time.time)
    status: SagaStatus = SagaStatus.PENDING
    error: Optional[str] = None

    def add_step(
        self,
        step_id: str,
        name: str,
        execute_func: Callable[..., Awaitable[Any]],
        compensate_func: Optional[Callable[..., Awaitable[Any]]] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        """Add a step to the saga."""
        step = SagaStep(
            step_id=step_id,
            name=name,
            execute_func=execute_func,
            compensate_func=compensate_func,
            timeout=timeout,
            max_retries=max_retries,
        )
        self.steps.append(step)


class SagaManager:
    """Saga manager for distributed transactions."""

    def __init__(self):
        self.active_sagas: Dict[str, Saga] = {}
        self.completed_sagas: Dict[str, Saga] = {}
        self.saga_metrics = {
            "total_sagas": 0,
            "completed_sagas": 0,
            "failed_sagas": 0,
            "compensated_sagas": 0,
            "active_sagas": 0,
        }

    def create_saga(self, saga_id: str, name: str) -> Saga:
        """Create a new saga."""
        saga = Saga(saga_id=saga_id, name=name)
        self.active_sagas[saga_id] = saga
        self.saga_metrics["total_sagas"] += 1
        self.saga_metrics["active_sagas"] += 1
        
        logger.info("Saga created", saga_id=saga_id, name=name)
        return saga

    async def execute_saga(self, saga_id: str) -> bool:
        """Execute a saga."""
        saga = self.active_sagas.get(saga_id)
        if not saga:
            raise ValueError(f"Saga {saga_id} not found")

        try:
            saga.status = SagaStatus.RUNNING
            logger.info("Starting saga execution", saga_id=saga_id, name=saga.name)

            if saga.parallel_execution:
                success = await self._execute_saga_parallel(saga)
            else:
                success = await self._execute_saga_sequential(saga)

            if success:
                saga.status = SagaStatus.COMPLETED
                self.completed_sagas[saga_id] = saga
                del self.active_sagas[saga_id]
                self.saga_metrics["completed_sagas"] += 1
                self.saga_metrics["active_sagas"] -= 1
                
                logger.info("Saga completed successfully", saga_id=saga_id, name=saga.name)
                return True
            else:
                # Execute compensation
                await self._execute_compensation(saga)
                
                saga.status = SagaStatus.COMPENSATED
                self.completed_sagas[saga_id] = saga
                del self.active_sagas[saga_id]
                self.saga_metrics["compensated_sagas"] += 1
                self.saga_metrics["active_sagas"] -= 1
                
                logger.info("Saga compensated", saga_id=saga_id, name=saga.name)
                return False

        except Exception as e:
            logger.error("Saga execution failed", saga_id=saga_id, error=str(e))
            
            saga.status = SagaStatus.FAILED
            saga.error = str(e)
            self.completed_sagas[saga_id] = saga
            del self.active_sagas[saga_id]
            self.saga_metrics["failed_sagas"] += 1
            self.saga_metrics["active_sagas"] -= 1
            
            return False

    async def _execute_saga_sequential(self, saga: Saga) -> bool:
        """Execute saga steps sequentially."""
        for step in saga.steps:
            try:
                step.status = StepStatus.RUNNING
                step.started_at = time.time()
                
                # Execute step with timeout and retry
                result = await self._execute_step_with_retry(step)
                
                step.result = result
                step.status = StepStatus.COMPLETED
                step.completed_at = time.time()
                
                logger.info(
                    "Saga step completed",
                    saga_id=saga.saga_id,
                    step_id=step.step_id,
                    name=step.name,
                )
                
            except Exception as e:
                step.status = StepStatus.FAILED
                step.error = str(e)
                step.completed_at = time.time()
                
                logger.error(
                    "Saga step failed",
                    saga_id=saga.saga_id,
                    step_id=step.step_id,
                    name=step.name,
                    error=str(e),
                )
                
                return False
        
        return True

    async def _execute_saga_parallel(self, saga: Saga) -> bool:
        """Execute saga steps in parallel."""
        try:
            # Create tasks for all steps
            tasks = []
            for step in saga.steps:
                step.status = StepStatus.RUNNING
                step.started_at = time.time()
                
                task = asyncio.create_task(self._execute_step_with_retry(step))
                tasks.append((step, task))
            
            # Wait for all tasks to complete
            for step, task in tasks:
                try:
                    result = await task
                    step.result = result
                    step.status = StepStatus.COMPLETED
                    step.completed_at = time.time()
                    
                except Exception as e:
                    step.status = StepStatus.FAILED
                    step.error = str(e)
                    step.completed_at = time.time()
                    
                    logger.error(
                        "Saga step failed in parallel execution",
                        saga_id=saga.saga_id,
                        step_id=step.step_id,
                        error=str(e),
                    )
                    
                    return False
            
            return True
            
        except Exception as e:
            logger.error(
                "Parallel saga execution failed",
                saga_id=saga.saga_id,
                error=str(e),
            )
            return False

    async def _execute_step_with_retry(self, step: SagaStep) -> Any:
        """Execute a step with retry logic."""
        last_exception = None
        
        for attempt in range(step.max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    step.execute_func(), timeout=step.timeout
                )
                return result
                
            except Exception as e:
                last_exception = e
                step.retry_attempts += 1
                
                if attempt < step.max_retries:
                    delay = min(1000 * (2 ** attempt), 10000)  # Exponential backoff
                    logger.warning(
                        "Step failed, retrying",
                        step_id=step.step_id,
                        attempt=attempt,
                        delay=delay,
                        error=str(e),
                    )
                    await asyncio.sleep(delay / 1000.0)
                else:
                    logger.error(
                        "Step failed after all retries",
                        step_id=step.step_id,
                        attempts=attempt,
                        error=str(e),
                    )
        
        raise last_exception

    async def _execute_compensation(self, saga: Saga) -> None:
        """Execute compensation for a saga."""
        try:
            saga.status = SagaStatus.COMPENSATING
            logger.info("Starting saga compensation", saga_id=saga.saga_id, name=saga.name)
            
            # Get completed steps in reverse order
            completed_steps = [
                step for step in saga.steps if step.status == StepStatus.COMPLETED
            ]
            
            if saga.compensation_strategy == "reverse_order":
                completed_steps.reverse()
            
            for step in completed_steps:
                if step.compensate_func:
                    try:
                        await step.compensate_func()
                        step.status = StepStatus.COMPENSATED
                        
                        logger.info(
                            "Step compensation completed",
                            saga_id=saga.saga_id,
                            step_id=step.step_id,
                            name=step.name,
                        )
                        
                    except Exception as e:
                        logger.error(
                            "Step compensation failed",
                            saga_id=saga.saga_id,
                            step_id=step.step_id,
                            name=step.name,
                            error=str(e),
                        )
                        # Continue with other compensations even if one fails
            
            logger.info("Saga compensation completed", saga_id=saga.saga_id, name=saga.name)
            
        except Exception as e:
            logger.error("Saga compensation failed", saga_id=saga.saga_id, error=str(e))
            raise

    def get_saga_status(self, saga_id: str) -> Optional[Dict[str, Any]]:
        """Get saga status and details."""
        saga = self.active_sagas.get(saga_id) or self.completed_sagas.get(saga_id)
        if not saga:
            return None
        
        return {
            "saga_id": saga.saga_id,
            "name": saga.name,
            "status": saga.status.value,
            "created_at": saga.created_at,
            "error": saga.error,
            "steps": [
                {
                    "step_id": step.step_id,
                    "name": step.name,
                    "status": step.status.value,
                    "started_at": step.started_at,
                    "completed_at": step.completed_at,
                    "error": step.error,
                }
                for step in saga.steps
            ],
        }

    def get_saga_metrics(self) -> Dict[str, Any]:
        """Get saga manager metrics."""
        return {
            **self.saga_metrics,
            "success_rate": (
                self.saga_metrics["completed_sagas"] / self.saga_metrics["total_sagas"]
                if self.saga_metrics["total_sagas"] > 0
                else 0
            ),
        }


# Global saga manager
saga_manager = SagaManager()