"""Saga adapter for side-effect operations with compensation."""

import asyncio
import time
from typing import Dict, List, Any, Optional, Callable, TypeVar, Generic
from dataclasses import dataclass
from enum import Enum
import structlog
import redis.asyncio as redis

from services.tools.base_adapter import BaseAdapter, AdapterConfig

logger = structlog.get_logger(__name__)

T = TypeVar('T')


class SagaStatus(Enum):
    """Saga status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    FAILED = "failed"


@dataclass
class SagaStep:
    """Saga step definition."""
    step_id: str
    operation: Callable[..., Any]
    compensate: Callable[..., Any]
    args: tuple = ()
    kwargs: dict = None
    status: SagaStatus = SagaStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


@dataclass
class SagaContext:
    """Saga execution context."""
    saga_id: str
    steps: List[SagaStep]
    status: SagaStatus
    created_at: float
    updated_at: float
    tenant_id: str
    user_id: str


class SagaAdapter:
    """Saga adapter for side-effect operations with compensation."""
    
    def __init__(
        self,
        name: str,
        config: AdapterConfig,
        redis_client: redis.Redis
    ):
        self.name = name
        self.config = config
        self.redis = redis_client
        self.base_adapter = BaseAdapter(name, config, redis_client)
    
    async def execute_saga(
        self,
        saga_id: str,
        steps: List[SagaStep],
        tenant_id: str,
        user_id: str
    ) -> SagaContext:
        """Execute saga with compensation on failure."""
        try:
            # Create saga context
            context = SagaContext(
                saga_id=saga_id,
                steps=steps,
                status=SagaStatus.IN_PROGRESS,
                created_at=time.time(),
                updated_at=time.time(),
                tenant_id=tenant_id,
                user_id=user_id
            )
            
            # Store saga context
            await self._store_saga_context(context)
            
            # Execute steps
            for step in steps:
                try:
                    # Execute step
                    result = await self._execute_step(step, context)
                    step.result = result
                    step.status = SagaStatus.COMPLETED
                    step.completed_at = time.time()
                    
                    # Update context
                    context.updated_at = time.time()
                    await self._store_saga_context(context)
                    
                    logger.info("Saga step completed", saga_id=saga_id, step_id=step.step_id)
                    
                except Exception as e:
                    # Step failed, start compensation
                    step.error = str(e)
                    step.status = SagaStatus.FAILED
                    step.completed_at = time.time()
                    
                    logger.error("Saga step failed, starting compensation", saga_id=saga_id, step_id=step.step_id, error=str(e))
                    
                    # Compensate completed steps
                    await self._compensate_saga(context)
                    
                    context.status = SagaStatus.FAILED
                    context.updated_at = time.time()
                    await self._store_saga_context(context)
                    
                    return context
            
            # All steps completed successfully
            context.status = SagaStatus.COMPLETED
            context.updated_at = time.time()
            await self._store_saga_context(context)
            
            logger.info("Saga completed successfully", saga_id=saga_id)
            return context
            
        except Exception as e:
            logger.error("Saga execution failed", saga_id=saga_id, error=str(e))
            
            # Update context with error
            context.status = SagaStatus.FAILED
            context.updated_at = time.time()
            await self._store_saga_context(context)
            
            return context
    
    async def _execute_step(self, step: SagaStep, context: SagaContext) -> Any:
        """Execute a single saga step."""
        try:
            step.status = SagaStatus.IN_PROGRESS
            step.started_at = time.time()
            
            # Log step execution
            logger.info("Executing saga step", saga_id=context.saga_id, step_id=step.step_id)
            
            # Execute step using base adapter
            result = await self.base_adapter.call(
                step.operation,
                *step.args,
                **step.kwargs or {}
            )
            
            return result
            
        except Exception as e:
            logger.error("Saga step execution failed", saga_id=context.saga_id, step_id=step.step_id, error=str(e))
            raise
    
    async def _compensate_saga(self, context: SagaContext) -> None:
        """Compensate completed steps in reverse order."""
        try:
            context.status = SagaStatus.COMPENSATING
            context.updated_at = time.time()
            await self._store_saga_context(context)
            
            # Find completed steps and compensate in reverse order
            completed_steps = [step for step in context.steps if step.status == SagaStatus.COMPLETED]
            completed_steps.reverse()
            
            for step in completed_steps:
                try:
                    logger.info("Compensating saga step", saga_id=context.saga_id, step_id=step.step_id)
                    
                    # Execute compensation
                    await self.base_adapter.call(
                        step.compensate,
                        step.result,
                        *step.args,
                        **step.kwargs or {}
                    )
                    
                    step.status = SagaStatus.COMPENSATED
                    logger.info("Saga step compensated", saga_id=context.saga_id, step_id=step.step_id)
                    
                except Exception as e:
                    logger.error("Saga step compensation failed", saga_id=context.saga_id, step_id=step.step_id, error=str(e))
                    # Continue with other compensations
            
            context.status = SagaStatus.COMPENSATED
            context.updated_at = time.time()
            await self._store_saga_context(context)
            
            logger.info("Saga compensation completed", saga_id=context.saga_id)
            
        except Exception as e:
            logger.error("Saga compensation failed", saga_id=context.saga_id, error=str(e))
            context.status = SagaStatus.FAILED
            context.updated_at = time.time()
            await self._store_saga_context(context)
    
    async def _store_saga_context(self, context: SagaContext) -> None:
        """Store saga context in Redis."""
        try:
            import json
            
            # Convert context to dict
            context_dict = {
                'saga_id': context.saga_id,
                'steps': [
                    {
                        'step_id': step.step_id,
                        'status': step.status.value,
                        'result': step.result,
                        'error': step.error,
                        'started_at': step.started_at,
                        'completed_at': step.completed_at
                    }
                    for step in context.steps
                ],
                'status': context.status.value,
                'created_at': context.created_at,
                'updated_at': context.updated_at,
                'tenant_id': context.tenant_id,
                'user_id': context.user_id
            }
            
            # Store in Redis
            key = f"saga_context:{context.saga_id}"
            await self.redis.setex(key, 86400 * 7, json.dumps(context_dict, default=str))  # 7 days TTL
            
        except Exception as e:
            logger.error("Failed to store saga context", saga_id=context.saga_id, error=str(e))
    
    async def get_saga_context(self, saga_id: str) -> Optional[SagaContext]:
        """Get saga context from Redis."""
        try:
            key = f"saga_context:{saga_id}"
            cached_data = await self.redis.get(key)
            
            if not cached_data:
                return None
            
            import json
            context_dict = json.loads(cached_data)
            
            # Reconstruct context
            steps = []
            for step_dict in context_dict['steps']:
                step = SagaStep(
                    step_id=step_dict['step_id'],
                    operation=None,  # Not stored in Redis
                    compensate=None,  # Not stored in Redis
                    status=SagaStatus(step_dict['status']),
                    result=step_dict['result'],
                    error=step_dict['error'],
                    started_at=step_dict['started_at'],
                    completed_at=step_dict['completed_at']
                )
                steps.append(step)
            
            context = SagaContext(
                saga_id=context_dict['saga_id'],
                steps=steps,
                status=SagaStatus(context_dict['status']),
                created_at=context_dict['created_at'],
                updated_at=context_dict['updated_at'],
                tenant_id=context_dict['tenant_id'],
                user_id=context_dict['user_id']
            )
            
            return context
            
        except Exception as e:
            logger.error("Failed to get saga context", saga_id=saga_id, error=str(e))
            return None
    
    async def get_saga_metrics(self) -> Dict[str, Any]:
        """Get saga metrics."""
        try:
            # Get base adapter metrics
            base_metrics = await self.base_adapter.get_metrics()
            
            # Get saga-specific metrics
            saga_keys = await self.redis.keys("saga_context:*")
            total_sagas = len(saga_keys)
            
            # Count sagas by status
            status_counts = {}
            for key in saga_keys:
                try:
                    context_data = await self.redis.get(key)
                    if context_data:
                        import json
                        context_dict = json.loads(context_data)
                        status = context_dict['status']
                        status_counts[status] = status_counts.get(status, 0) + 1
                except Exception:
                    continue
            
            return {
                'adapter_name': self.name,
                'base_metrics': base_metrics,
                'total_sagas': total_sagas,
                'status_counts': status_counts
            }
            
        except Exception as e:
            logger.error("Failed to get saga metrics", error=str(e))
            return {'error': str(e)}
