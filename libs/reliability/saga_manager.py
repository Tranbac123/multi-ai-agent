"""
Saga Manager for Multi-Step Tool Operations

Implements Saga pattern for managing distributed transactions
and compensating for side effects in multi-step tool operations.
"""

import asyncio
import uuid
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
import structlog
from datetime import datetime, timedelta

logger = structlog.get_logger(__name__)


class SagaStepStatus(Enum):
    """Saga step status."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    FAILED = "failed"


class SagaStatus(Enum):
    """Saga execution status."""
    RUNNING = "running"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    FAILED = "failed"


@dataclass
class SagaStep:
    """Individual step in a saga."""
    
    step_id: str
    tool_adapter: Any  # BaseToolAdapter instance
    parameters: Dict[str, Any]
    compensation: Optional[Callable[[Dict[str, Any], Any], Awaitable[bool]]] = None
    status: SagaStepStatus = SagaStepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    compensation_start_time: Optional[datetime] = None
    compensation_end_time: Optional[datetime] = None


@dataclass
class SagaExecution:
    """Saga execution context."""
    
    saga_id: str
    tenant_id: str
    workflow_id: str
    status: SagaStatus = SagaStatus.RUNNING
    steps: List[SagaStep] = field(default_factory=list)
    current_step_index: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    error: Optional[str] = None
    compensation_reason: Optional[str] = None


class SagaManager:
    """Manages saga execution and compensation."""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.active_sagas: Dict[str, SagaExecution] = {}
        
        # Metrics
        self.total_sagas = 0
        self.completed_sagas = 0
        self.compensated_sagas = 0
        self.failed_sagas = 0
        
        logger.info("Saga manager initialized")
    
    async def start_saga(
        self,
        tenant_id: str,
        workflow_id: str,
        steps: List[Dict[str, Any]]
    ) -> str:
        """Start a new saga execution."""
        
        saga_id = str(uuid.uuid4())
        
        # Create saga steps
        saga_steps = []
        for i, step_config in enumerate(steps):
            step = SagaStep(
                step_id=f"{saga_id}_step_{i}",
                tool_adapter=step_config["tool_adapter"],
                parameters=step_config["parameters"],
                compensation=step_config.get("compensation")
            )
            saga_steps.append(step)
        
        # Create saga execution
        saga_execution = SagaExecution(
            saga_id=saga_id,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            steps=saga_steps
        )
        
        self.active_sagas[saga_id] = saga_execution
        self.total_sagas += 1
        
        logger.info("Saga started", 
                   saga_id=saga_id,
                   tenant_id=tenant_id,
                   workflow_id=workflow_id,
                   step_count=len(steps))
        
        # Start execution asynchronously
        asyncio.create_task(self._execute_saga(saga_execution))
        
        return saga_id
    
    async def _execute_saga(self, saga_execution: SagaExecution):
        """Execute saga steps sequentially."""
        
        try:
            for i, step in enumerate(saga_execution.steps):
                saga_execution.current_step_index = i
                
                logger.info("Executing saga step", 
                           saga_id=saga_execution.saga_id,
                           step_id=step.step_id,
                           step_index=i)
                
                await self._execute_step(step)
                
                if step.status == SagaStepStatus.FAILED:
                    logger.error("Saga step failed, initiating compensation", 
                               saga_id=saga_execution.saga_id,
                               step_id=step.step_id,
                               error=step.error)
                    await self._compensate_saga(saga_execution, step.error)
                    return
            
            # All steps completed successfully
            saga_execution.status = SagaStatus.COMPLETED
            saga_execution.end_time = datetime.now()
            self.completed_sagas += 1
            
            logger.info("Saga completed successfully", 
                       saga_id=saga_execution.saga_id,
                       duration_seconds=(saga_execution.end_time - saga_execution.start_time).total_seconds())
            
        except Exception as e:
            logger.error("Saga execution failed", 
                        saga_id=saga_execution.saga_id,
                        error=str(e))
            
            saga_execution.status = SagaStatus.FAILED
            saga_execution.error = str(e)
            saga_execution.end_time = datetime.now()
            self.failed_sagas += 1
            
            # Attempt compensation
            await self._compensate_saga(saga_execution, str(e))
    
    async def _execute_step(self, step: SagaStep):
        """Execute a single saga step."""
        
        step.status = SagaStepStatus.EXECUTING
        step.start_time = datetime.now()
        
        try:
            # Execute the tool
            result = await step.tool_adapter.execute(step.parameters)
            
            step.status = SagaStepStatus.COMPLETED
            step.result = result
            step.end_time = datetime.now()
            
            execution_time = (step.end_time - step.start_time).total_seconds()
            logger.info("Saga step completed", 
                       step_id=step.step_id,
                       execution_time_seconds=execution_time)
            
        except Exception as e:
            step.status = SagaStepStatus.FAILED
            step.error = str(e)
            step.end_time = datetime.now()
            
            execution_time = (step.end_time - step.start_time).total_seconds()
            logger.error("Saga step failed", 
                        step_id=step.step_id,
                        execution_time_seconds=execution_time,
                        error=str(e))
            raise
    
    async def _compensate_saga(self, saga_execution: SagaExecution, reason: str):
        """Compensate saga by executing compensation functions in reverse order."""
        
        saga_execution.status = SagaStatus.COMPENSATING
        saga_execution.compensation_reason = reason
        
        logger.info("Starting saga compensation", 
                   saga_id=saga_execution.saga_id,
                   reason=reason)
        
        # Compensate steps in reverse order
        compensation_start_time = datetime.now()
        
        for i in range(saga_execution.current_step_index, -1, -1):
            step = saga_execution.steps[i]
            
            if step.status == SagaStepStatus.COMPLETED and step.compensation:
                logger.info("Compensating saga step", 
                           saga_id=saga_execution.saga_id,
                           step_id=step.step_id)
                
                await self._compensate_step(step)
        
        # Mark saga as compensated
        saga_execution.status = SagaStatus.COMPENSATED
        saga_execution.end_time = datetime.now()
        self.compensated_sagas += 1
        
        compensation_duration = (saga_execution.end_time - compensation_start_time).total_seconds()
        logger.info("Saga compensation completed", 
                   saga_id=saga_execution.saga_id,
                   duration_seconds=compensation_duration)
    
    async def _compensate_step(self, step: SagaStep):
        """Compensate a single saga step."""
        
        step.status = SagaStepStatus.COMPENSATING
        step.compensation_start_time = datetime.now()
        
        try:
            if step.compensation:
                # Use provided compensation function
                compensation_success = await step.compensation(step.parameters, step.result)
            else:
                # Use tool adapter's compensate method
                compensation_success = await step.tool_adapter.compensate(step.parameters, step.result)
            
            if compensation_success:
                step.status = SagaStepStatus.COMPENSATED
                logger.info("Step compensation successful", step_id=step.step_id)
            else:
                step.status = SagaStepStatus.FAILED
                logger.error("Step compensation failed", step_id=step.step_id)
            
        except Exception as e:
            step.status = SagaStepStatus.FAILED
            logger.error("Step compensation error", 
                        step_id=step.step_id,
                        error=str(e))
        
        step.compensation_end_time = datetime.now()
    
    async def get_saga_status(self, saga_id: str) -> Optional[Dict[str, Any]]:
        """Get saga execution status."""
        
        saga_execution = self.active_sagas.get(saga_id)
        if not saga_execution:
            return None
        
        # Calculate step statuses
        step_statuses = []
        for step in saga_execution.steps:
            step_status = {
                "step_id": step.step_id,
                "status": step.status.value,
                "start_time": step.start_time.isoformat() if step.start_time else None,
                "end_time": step.end_time.isoformat() if step.end_time else None,
                "execution_time_seconds": None,
                "compensation_start_time": step.compensation_start_time.isoformat() if step.compensation_start_time else None,
                "compensation_end_time": step.compensation_end_time.isoformat() if step.compensation_end_time else None,
                "compensation_time_seconds": None,
                "error": step.error
            }
            
            # Calculate execution time
            if step.start_time and step.end_time:
                step_status["execution_time_seconds"] = (step.end_time - step.start_time).total_seconds()
            
            # Calculate compensation time
            if step.compensation_start_time and step.compensation_end_time:
                step_status["compensation_time_seconds"] = (step.compensation_end_time - step.compensation_start_time).total_seconds()
            
            step_statuses.append(step_status)
        
        return {
            "saga_id": saga_id,
            "tenant_id": saga_execution.tenant_id,
            "workflow_id": saga_execution.workflow_id,
            "status": saga_execution.status.value,
            "current_step_index": saga_execution.current_step_index,
            "start_time": saga_execution.start_time.isoformat(),
            "end_time": saga_execution.end_time.isoformat() if saga_execution.end_time else None,
            "total_duration_seconds": (saga_execution.end_time - saga_execution.start_time).total_seconds() if saga_execution.end_time else None,
            "error": saga_execution.error,
            "compensation_reason": saga_execution.compensation_reason,
            "steps": step_statuses
        }
    
    async def cancel_saga(self, saga_id: str) -> bool:
        """Cancel a running saga and initiate compensation."""
        
        saga_execution = self.active_sagas.get(saga_id)
        if not saga_execution or saga_execution.status != SagaStatus.RUNNING:
            return False
        
        logger.info("Cancelling saga", saga_id=saga_id)
        
        # Initiate compensation
        await self._compensate_saga(saga_execution, "Manually cancelled")
        
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get saga manager statistics."""
        
        active_sagas = len([s for s in self.active_sagas.values() if s.status == SagaStatus.RUNNING])
        compensating_sagas = len([s for s in self.active_sagas.values() if s.status == SagaStatus.COMPENSATING])
        
        return {
            "total_sagas": self.total_sagas,
            "completed_sagas": self.completed_sagas,
            "compensated_sagas": self.compensated_sagas,
            "failed_sagas": self.failed_sagas,
            "active_sagas": active_sagas,
            "compensating_sagas": compensating_sagas,
            "success_rate": self.completed_sagas / max(1, self.total_sagas),
            "compensation_rate": self.compensated_sagas / max(1, self.total_sagas)
        }
    
    def cleanup_completed_sagas(self, max_age_hours: int = 24):
        """Clean up completed sagas older than specified age."""
        
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        sagas_to_remove = []
        for saga_id, saga_execution in self.active_sagas.items():
            if (saga_execution.end_time and 
                saga_execution.end_time < cutoff_time and
                saga_execution.status in [SagaStatus.COMPLETED, SagaStatus.COMPENSATED, SagaStatus.FAILED]):
                sagas_to_remove.append(saga_id)
        
        for saga_id in sagas_to_remove:
            del self.active_sagas[saga_id]
        
        if sagas_to_remove:
            logger.info("Cleaned up completed sagas", 
                       removed_count=len(sagas_to_remove),
                       remaining_count=len(self.active_sagas))


# Saga step builders for common patterns
class SagaStepBuilder:
    """Builder for saga steps."""
    
    def __init__(self, tool_adapter: Any):
        self.tool_adapter = tool_adapter
        self.parameters: Dict[str, Any] = {}
        self.compensation: Optional[Callable] = None
    
    def with_parameters(self, parameters: Dict[str, Any]) -> 'SagaStepBuilder':
        """Set step parameters."""
        self.parameters = parameters
        return self
    
    def with_compensation(self, compensation: Callable) -> 'SagaStepBuilder':
        """Set compensation function."""
        self.compensation = compensation
        return self
    
    def build(self) -> Dict[str, Any]:
        """Build saga step configuration."""
        return {
            "tool_adapter": self.tool_adapter,
            "parameters": self.parameters,
            "compensation": self.compensation
        }


def create_saga_step(tool_adapter: Any) -> SagaStepBuilder:
    """Create a new saga step builder."""
    return SagaStepBuilder(tool_adapter)
