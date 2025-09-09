"""Saga pattern implementation for distributed transactions."""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, List, Optional, Callable
from uuid import UUID, uuid4
import structlog

logger = structlog.get_logger(__name__)


class SagaStepStatus(Enum):
    """Saga step status."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"


@dataclass
class SagaStep:
    """Saga step definition."""
    step_id: str
    name: str
    execute_func: Callable
    compensate_func: Callable
    timeout: float = 30.0
    retry_attempts: int = 3
    status: SagaStepStatus = SagaStepStatus.PENDING
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


class SagaOrchestrator:
    """Saga orchestrator for managing distributed transactions."""
    
    def __init__(self, saga_id: str):
        self.saga_id = saga_id
        self.steps: List[SagaStep] = []
        self.current_step_index = 0
        self.status = SagaStepStatus.PENDING
        self.created_at = time.time()
        self.completed_at = None
        self.error = None
    
    def add_step(
        self,
        step_id: str,
        name: str,
        execute_func: Callable,
        compensate_func: Callable,
        timeout: float = 30.0,
        retry_attempts: int = 3
    ):
        """Add step to saga."""
        step = SagaStep(
            step_id=step_id,
            name=name,
            execute_func=execute_func,
            compensate_func=compensate_func,
            timeout=timeout,
            retry_attempts=retry_attempts
        )
        self.steps.append(step)
    
    async def execute(self) -> bool:
        """Execute saga steps in order."""
        try:
            self.status = SagaStepStatus.EXECUTING
            logger.info("Starting saga execution", saga_id=self.saga_id)
            
            for i, step in enumerate(self.steps):
                self.current_step_index = i
                step.started_at = time.time()
                step.status = SagaStepStatus.EXECUTING
                
                # Execute step with retry
                success = await self._execute_step(step)
                
                if not success:
                    # Step failed, start compensation
                    logger.error("Step failed, starting compensation", 
                               saga_id=self.saga_id, 
                               step_id=step.step_id)
                    await self._compensate()
                    return False
                
                step.status = SagaStepStatus.COMPLETED
                step.completed_at = time.time()
                
                logger.info("Step completed", 
                           saga_id=self.saga_id, 
                           step_id=step.step_id)
            
            # All steps completed successfully
            self.status = SagaStepStatus.COMPLETED
            self.completed_at = time.time()
            
            logger.info("Saga completed successfully", saga_id=self.saga_id)
            return True
            
        except Exception as e:
            logger.error("Saga execution failed", 
                        saga_id=self.saga_id, 
                        error=str(e))
            self.error = str(e)
            self.status = SagaStepStatus.FAILED
            
            # Start compensation
            await self._compensate()
            return False
    
    async def _execute_step(self, step: SagaStep) -> bool:
        """Execute single step with retry logic."""
        for attempt in range(step.retry_attempts):
            try:
                # Execute step with timeout
                result = await asyncio.wait_for(
                    step.execute_func(),
                    timeout=step.timeout
                )
                
                logger.debug("Step executed successfully", 
                           saga_id=self.saga_id, 
                           step_id=step.step_id, 
                           attempt=attempt + 1)
                return True
                
            except asyncio.TimeoutError:
                logger.warning("Step execution timeout", 
                             saga_id=self.saga_id, 
                             step_id=step.step_id, 
                             attempt=attempt + 1,
                             timeout=step.timeout)
                
                if attempt == step.retry_attempts - 1:
                    step.error = f"Timeout after {step.retry_attempts} attempts"
                    return False
                
                # Wait before retry
                await asyncio.sleep(1.0 * (attempt + 1))
                
            except Exception as e:
                logger.warning("Step execution failed", 
                             saga_id=self.saga_id, 
                             step_id=step.step_id, 
                             attempt=attempt + 1,
                             error=str(e))
                
                if attempt == step.retry_attempts - 1:
                    step.error = str(e)
                    return False
                
                # Wait before retry
                await asyncio.sleep(1.0 * (attempt + 1))
        
        return False
    
    async def _compensate(self):
        """Compensate for failed saga by running compensation functions in reverse order."""
        logger.info("Starting saga compensation", saga_id=self.saga_id)
        self.status = SagaStepStatus.COMPENSATING
        
        # Compensate steps in reverse order
        for i in range(self.current_step_index, -1, -1):
            step = self.steps[i]
            
            if step.status == SagaStepStatus.COMPLETED:
                try:
                    step.status = SagaStepStatus.COMPENSATING
                    await step.compensate_func()
                    step.status = SagaStepStatus.COMPENSATED
                    
                    logger.info("Step compensated", 
                               saga_id=self.saga_id, 
                               step_id=step.step_id)
                    
                except Exception as e:
                    logger.error("Step compensation failed", 
                               saga_id=self.saga_id, 
                               step_id=step.step_id, 
                               error=str(e))
                    # Continue with other compensations
        
        self.status = SagaStepStatus.COMPENSATED
        logger.info("Saga compensation completed", saga_id=self.saga_id)
    
    def get_status(self) -> Dict[str, Any]:
        """Get saga status and statistics."""
        completed_steps = sum(1 for step in self.steps if step.status == SagaStepStatus.COMPLETED)
        failed_steps = sum(1 for step in self.steps if step.status == SagaStepStatus.FAILED)
        compensated_steps = sum(1 for step in self.steps if step.status == SagaStepStatus.COMPENSATED)
        
        return {
            "saga_id": self.saga_id,
            "status": self.status.value,
            "total_steps": len(self.steps),
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "compensated_steps": compensated_steps,
            "current_step_index": self.current_step_index,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "steps": [
                {
                    "step_id": step.step_id,
                    "name": step.name,
                    "status": step.status.value,
                    "error": step.error,
                    "started_at": step.started_at,
                    "completed_at": step.completed_at
                }
                for step in self.steps
            ]
        }


class SagaManager:
    """Manager for multiple sagas."""
    
    def __init__(self):
        self.active_sagas: Dict[str, SagaOrchestrator] = {}
        self.completed_sagas: Dict[str, SagaOrchestrator] = {}
    
    def create_saga(self, saga_id: Optional[str] = None) -> SagaOrchestrator:
        """Create new saga."""
        if saga_id is None:
            saga_id = str(uuid4())
        
        saga = SagaOrchestrator(saga_id)
        self.active_sagas[saga_id] = saga
        
        logger.info("Saga created", saga_id=saga_id)
        return saga
    
    async def execute_saga(self, saga_id: str) -> bool:
        """Execute saga."""
        if saga_id not in self.active_sagas:
            raise ValueError(f"Saga {saga_id} not found")
        
        saga = self.active_sagas[saga_id]
        success = await saga.execute()
        
        # Move to completed sagas
        self.completed_sagas[saga_id] = saga
        del self.active_sagas[saga_id]
        
        return success
    
    def get_saga(self, saga_id: str) -> Optional[SagaOrchestrator]:
        """Get saga by ID."""
        if saga_id in self.active_sagas:
            return self.active_sagas[saga_id]
        elif saga_id in self.completed_sagas:
            return self.completed_sagas[saga_id]
        return None
    
    def get_all_sagas(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all sagas."""
        all_sagas = {}
        
        for saga_id, saga in self.active_sagas.items():
            all_sagas[saga_id] = saga.get_status()
        
        for saga_id, saga in self.completed_sagas.items():
            all_sagas[saga_id] = saga.get_status()
        
        return all_sagas
    
    def cleanup_old_sagas(self, max_age_hours: int = 24):
        """Clean up old completed sagas."""
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        to_remove = []
        for saga_id, saga in self.completed_sagas.items():
            if saga.completed_at and (current_time - saga.completed_at) > max_age_seconds:
                to_remove.append(saga_id)
        
        for saga_id in to_remove:
            del self.completed_sagas[saga_id]
            logger.info("Old saga cleaned up", saga_id=saga_id)


# Global saga manager
saga_manager = SagaManager()


def saga_step(step_id: str, timeout: float = 30.0, retry_attempts: int = 3):
    """Decorator for saga step functions."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # This would be used in the context of a saga
            return await func(*args, **kwargs)
        return wrapper
    return decorator
