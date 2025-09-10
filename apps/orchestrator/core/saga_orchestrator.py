"""Saga orchestrator for managing distributed transactions."""

import asyncio
import time
import uuid
from typing import Dict, List, Any, Optional, Callable, Tuple
from enum import Enum
import structlog
import redis.asyncio as redis

from libs.adapters.resilient_adapter import ResilientAdapter

logger = structlog.get_logger(__name__)


class SagaStatus(Enum):
    """Saga execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"


class SagaStep:
    """Individual step in a saga."""
    
    def __init__(
        self,
        step_id: str,
        operation: Callable[..., Any],
        compensation: Callable[..., Any],
        adapter: Optional[ResilientAdapter] = None,
        timeout: float = 30.0,
        retry_count: int = 0
    ):
        self.step_id = step_id
        self.operation = operation
        self.compensation = compensation
        self.adapter = adapter
        self.timeout = timeout
        self.retry_count = retry_count
        self.status = SagaStatus.PENDING
        self.result = None
        self.error = None
        self.started_at = None
        self.completed_at = None


class SagaOrchestrator:
    """Orchestrates saga execution with compensation."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.active_sagas = {}
        self.saga_ttl = 3600  # 1 hour
    
    async def create_saga(
        self,
        saga_id: Optional[str] = None,
        tenant_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new saga."""
        if not saga_id:
            saga_id = str(uuid.uuid4())
        
        saga_data = {
            'saga_id': saga_id,
            'tenant_id': tenant_id,
            'status': SagaStatus.PENDING.value,
            'steps': [],
            'metadata': metadata or {},
            'created_at': time.time(),
            'updated_at': time.time()
        }
        
        # Store saga in Redis
        saga_key = f"saga:{tenant_id}:{saga_id}"
        await self.redis.hset(saga_key, mapping=saga_data)
        await self.redis.expire(saga_key, self.saga_ttl)
        
        # Store in memory
        self.active_sagas[saga_id] = {
            'steps': [],
            'status': SagaStatus.PENDING,
            'tenant_id': tenant_id,
            'metadata': metadata or {}
        }
        
        logger.info("Saga created", saga_id=saga_id, tenant_id=tenant_id)
        return saga_id
    
    async def add_step(
        self,
        saga_id: str,
        step_id: str,
        operation: Callable[..., Any],
        compensation: Callable[..., Any],
        adapter: Optional[ResilientAdapter] = None,
        timeout: float = 30.0
    ) -> bool:
        """Add a step to the saga."""
        try:
            step = SagaStep(
                step_id=step_id,
                operation=operation,
                compensation=compensation,
                adapter=adapter,
                timeout=timeout
            )
            
            # Add to memory
            if saga_id in self.active_sagas:
                self.active_sagas[saga_id]['steps'].append(step)
            
            # Add to Redis
            saga_key = f"saga:{self.active_sagas[saga_id]['tenant_id']}:{saga_id}"
            step_data = {
                'step_id': step_id,
                'status': SagaStatus.PENDING.value,
                'timeout': timeout,
                'retry_count': 0
            }
            await self.redis.hset(f"{saga_key}:steps", step_id, str(step_data))
            
            logger.info("Step added to saga", saga_id=saga_id, step_id=step_id)
            return True
            
        except Exception as e:
            logger.error("Failed to add step to saga", error=str(e), saga_id=saga_id)
            return False
    
    async def execute_saga(self, saga_id: str) -> Tuple[bool, List[Any]]:
        """Execute the saga with compensation on failure."""
        try:
            if saga_id not in self.active_sagas:
                raise ValueError(f"Saga {saga_id} not found")
            
            saga = self.active_sagas[saga_id]
            saga['status'] = SagaStatus.RUNNING
            
            # Update status in Redis
            await self._update_saga_status(saga_id, SagaStatus.RUNNING)
            
            results = []
            executed_steps = []
            
            try:
                # Execute steps in order
                for step in saga['steps']:
                    logger.info(
                        "Executing saga step",
                        saga_id=saga_id,
                        step_id=step.step_id
                    )
                    
                    step.started_at = time.time()
                    step.status = SagaStatus.RUNNING
                    
                    try:
                        # Execute step
                        if step.adapter:
                            result = await step.adapter.execute(
                                step.operation,
                                idempotency_key=f"{saga_id}:{step.step_id}"
                            )
                        else:
                            result = await asyncio.wait_for(
                                step.operation(),
                                timeout=step.timeout
                            )
                        
                        step.result = result
                        step.status = SagaStatus.COMPLETED
                        step.completed_at = time.time()
                        
                        results.append(result)
                        executed_steps.append(step)
                        
                        logger.info(
                            "Saga step completed",
                            saga_id=saga_id,
                            step_id=step.step_id
                        )
                        
                    except Exception as e:
                        step.error = str(e)
                        step.status = SagaStatus.FAILED
                        step.completed_at = time.time()
                        
                        logger.error(
                            "Saga step failed",
                            saga_id=saga_id,
                            step_id=step.step_id,
                            error=str(e)
                        )
                        
                        # Start compensation
                        await self._execute_compensation(saga_id, executed_steps)
                        return False, results
                
                # All steps completed successfully
                saga['status'] = SagaStatus.COMPLETED
                await self._update_saga_status(saga_id, SagaStatus.COMPLETED)
                
                logger.info(
                    "Saga completed successfully",
                    saga_id=saga_id,
                    steps_count=len(results)
                )
                
                return True, results
                
            except Exception as e:
                logger.error(
                    "Saga execution failed",
                    saga_id=saga_id,
                    error=str(e)
                )
                
                # Execute compensation
                await self._execute_compensation(saga_id, executed_steps)
                return False, results
                
        except Exception as e:
            logger.error("Saga execution error", error=str(e), saga_id=saga_id)
            return False, []
    
    async def _execute_compensation(
        self,
        saga_id: str,
        executed_steps: List[SagaStep]
    ) -> None:
        """Execute compensation for failed saga."""
        try:
            saga = self.active_sagas[saga_id]
            saga['status'] = SagaStatus.COMPENSATING
            
            await self._update_saga_status(saga_id, SagaStatus.COMPENSATING)
            
            # Execute compensation in reverse order
            for step in reversed(executed_steps):
                try:
                    logger.info(
                        "Executing compensation",
                        saga_id=saga_id,
                        step_id=step.step_id
                    )
                    
                    if step.adapter:
                        await step.adapter.execute(step.compensation)
                    else:
                        await step.compensation()
                    
                    logger.info(
                        "Compensation completed",
                        saga_id=saga_id,
                        step_id=step.step_id
                    )
                    
                except Exception as e:
                    logger.error(
                        "Compensation failed",
                        saga_id=saga_id,
                        step_id=step.step_id,
                        error=str(e)
                    )
            
            saga['status'] = SagaStatus.COMPENSATED
            await self._update_saga_status(saga_id, SagaStatus.COMPENSATED)
            
            logger.info("Saga compensation completed", saga_id=saga_id)
            
        except Exception as e:
            logger.error("Compensation execution error", error=str(e), saga_id=saga_id)
    
    async def _update_saga_status(self, saga_id: str, status: SagaStatus) -> None:
        """Update saga status in Redis."""
        try:
            saga = self.active_sagas[saga_id]
            saga_key = f"saga:{saga['tenant_id']}:{saga_id}"
            
            await self.redis.hset(saga_key, mapping={
                'status': status.value,
                'updated_at': time.time()
            })
            
        except Exception as e:
            logger.error("Failed to update saga status", error=str(e))
    
    async def get_saga_status(self, saga_id: str) -> Optional[Dict[str, Any]]:
        """Get saga status and details."""
        try:
            if saga_id not in self.active_sagas:
                return None
            
            saga = self.active_sagas[saga_id]
            
            return {
                'saga_id': saga_id,
                'status': saga['status'].value,
                'tenant_id': saga['tenant_id'],
                'steps_count': len(saga['steps']),
                'completed_steps': len([s for s in saga['steps'] if s.status == SagaStatus.COMPLETED]),
                'failed_steps': len([s for s in saga['steps'] if s.status == SagaStatus.FAILED]),
                'metadata': saga['metadata']
            }
            
        except Exception as e:
            logger.error("Failed to get saga status", error=str(e))
            return None
    
    async def get_saga_results(self, saga_id: str) -> List[Any]:
        """Get saga execution results."""
        try:
            if saga_id not in self.active_sagas:
                return []
            
            saga = self.active_sagas[saga_id]
            return [step.result for step in saga['steps'] if step.result is not None]
            
        except Exception as e:
            logger.error("Failed to get saga results", error=str(e))
            return []
    
    async def cleanup_saga(self, saga_id: str) -> bool:
        """Clean up completed saga."""
        try:
            if saga_id in self.active_sagas:
                saga = self.active_sagas[saga_id]
                saga_key = f"saga:{saga['tenant_id']}:{saga_id}"
                
                # Remove from Redis
                await self.redis.delete(saga_key)
                await self.redis.delete(f"{saga_key}:steps")
                
                # Remove from memory
                del self.active_sagas[saga_id]
                
                logger.info("Saga cleaned up", saga_id=saga_id)
                return True
            
            return False
            
        except Exception as e:
            logger.error("Failed to cleanup saga", error=str(e))
            return False
    
    async def get_active_sagas(self) -> List[str]:
        """Get list of active saga IDs."""
        return list(self.active_sagas.keys())
    
    async def get_saga_statistics(self) -> Dict[str, Any]:
        """Get saga execution statistics."""
        try:
            total_sagas = len(self.active_sagas)
            completed_sagas = len([
                saga for saga in self.active_sagas.values()
                if saga['status'] == SagaStatus.COMPLETED
            ])
            failed_sagas = len([
                saga for saga in self.active_sagas.values()
                if saga['status'] == SagaStatus.FAILED
            ])
            compensating_sagas = len([
                saga for saga in self.active_sagas.values()
                if saga['status'] == SagaStatus.COMPENSATING
            ])
            
            return {
                'total_sagas': total_sagas,
                'completed_sagas': completed_sagas,
                'failed_sagas': failed_sagas,
                'compensating_sagas': compensating_sagas,
                'success_rate': completed_sagas / max(total_sagas, 1)
            }
            
        except Exception as e:
            logger.error("Failed to get saga statistics", error=str(e))
            return {}
