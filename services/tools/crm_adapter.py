"""CRM adapter with saga compensation."""

import asyncio
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import structlog
import redis.asyncio as redis

from services.tools.base_adapter import BaseAdapter, AdapterConfig
from services.tools.saga_adapter import SagaAdapter, SagaStep

logger = structlog.get_logger(__name__)


class CRMStatus(Enum):
    """CRM status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class CRMRecord:
    """CRM record."""
    record_id: str
    record_type: str  # "lead", "contact", "opportunity", "account"
    data: Dict[str, Any]
    tenant_id: str
    user_id: str


@dataclass
class CRMResult:
    """CRM result."""
    record_id: str
    status: CRMStatus
    crm_id: str
    processed_at: float
    error: Optional[str] = None


class CRMAdapter:
    """CRM adapter with saga compensation."""
    
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
        self.saga_adapter = SagaAdapter(name, config, redis_client)
    
    async def create_record(
        self,
        record: CRMRecord,
        tenant_id: str,
        user_id: str
    ) -> CRMResult:
        """Create CRM record using base adapter."""
        try:
            # Generate CRM ID
            crm_id = f"crm_{int(time.time())}_{hash(record.record_id)}"
            
            # Mock CRM record creation
            result = await self.base_adapter.call(
                self._create_record_operation,
                record,
                crm_id
            )
            
            return result
            
        except Exception as e:
            logger.error("Failed to create CRM record", error=str(e), record_id=record.record_id, record_type=record.record_type)
            raise
    
    async def create_record_with_saga(
        self,
        record: CRMRecord,
        tenant_id: str,
        user_id: str
    ) -> CRMResult:
        """Create CRM record using saga pattern."""
        try:
            # Generate saga ID
            saga_id = f"crm_saga_{int(time.time())}_{hash(record.record_id)}"
            
            # Create saga steps
            steps = [
                SagaStep(
                    step_id="create_crm_record",
                    operation=self._create_record_operation,
                    compensate=self._compensate_record_operation,
                    args=(record,),
                    kwargs={}
                )
            ]
            
            # Execute saga
            context = await self.saga_adapter.execute_saga(
                saga_id=saga_id,
                steps=steps,
                tenant_id=tenant_id,
                user_id=user_id
            )
            
            # Get result from first step
            if context.steps and context.steps[0].result:
                return context.steps[0].result
            
            # If saga failed, raise exception
            if context.status.value in ['failed', 'compensated']:
                error_msg = context.steps[0].error if context.steps else "Unknown error"
                raise Exception(f"CRM saga failed: {error_msg}")
            
            raise Exception("CRM saga completed but no result found")
            
        except Exception as e:
            logger.error("Failed to create CRM record with saga", error=str(e), record_id=record.record_id, record_type=record.record_type)
            raise
    
    async def _create_record_operation(
        self,
        record: CRMRecord,
        crm_id: Optional[str] = None
    ) -> CRMResult:
        """Create CRM record operation (mock implementation)."""
        try:
            if not crm_id:
                crm_id = f"crm_{int(time.time())}_{hash(record.record_id)}"
            
            # Mock CRM record creation delay
            await asyncio.sleep(0.15)
            
            # Mock CRM service response
            result = CRMResult(
                record_id=record.record_id,
                status=CRMStatus.COMPLETED,
                crm_id=crm_id,
                processed_at=time.time()
            )
            
            logger.info("CRM record created successfully", record_id=record.record_id, crm_id=crm_id, record_type=record.record_type)
            return result
            
        except Exception as e:
            logger.error("CRM record creation failed", error=str(e), record_id=record.record_id, record_type=record.record_type)
            raise
    
    async def _compensate_record_operation(
        self,
        result: CRMResult,
        record: CRMRecord
    ) -> None:
        """Compensate CRM record operation (mock implementation)."""
        try:
            # Mock CRM record compensation (e.g., delete record, update status)
            logger.info("Compensating CRM record operation", record_id=result.record_id, crm_id=result.crm_id)
            
            # Mock compensation delay
            await asyncio.sleep(0.08)
            
            # In a real implementation, this might:
            # - Delete the CRM record
            # - Update record status to "cancelled"
            # - Move record to trash
            # - Send notification to CRM administrators
            # - Log for manual review
            
            logger.info("CRM record operation compensated", record_id=result.record_id, crm_id=result.crm_id)
            
        except Exception as e:
            logger.error("CRM record compensation failed", error=str(e), record_id=result.record_id, crm_id=result.crm_id)
            raise
    
    async def get_crm_metrics(self) -> Dict[str, Any]:
        """Get CRM adapter metrics."""
        try:
            # Get base adapter metrics
            base_metrics = await self.base_adapter.get_metrics()
            
            # Get saga metrics
            saga_metrics = await self.saga_adapter.get_saga_metrics()
            
            return {
                'adapter_name': self.name,
                'base_metrics': base_metrics,
                'saga_metrics': saga_metrics
            }
            
        except Exception as e:
            logger.error("Failed to get CRM metrics", error=str(e))
            return {'error': str(e)}
