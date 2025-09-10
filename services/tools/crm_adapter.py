"""CRM adapter with Saga compensation support."""

import asyncio
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import structlog
import redis.asyncio as redis

from .base_adapter import BaseAdapter, AdapterConfig

logger = structlog.get_logger(__name__)


class CRMOperation(Enum):
    """CRM operation types."""
    CREATE_CONTACT = "create_contact"
    UPDATE_CONTACT = "update_contact"
    DELETE_CONTACT = "delete_contact"
    CREATE_LEAD = "create_lead"
    UPDATE_LEAD = "update_lead"
    CONVERT_LEAD = "convert_lead"


@dataclass
class Contact:
    """Contact structure."""
    contact_id: Optional[str] = None
    email: str = ""
    first_name: str = ""
    last_name: str = ""
    phone: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    metadata: Dict[str, Any] = None


@dataclass
class Lead:
    """Lead structure."""
    lead_id: Optional[str] = None
    email: str = ""
    first_name: str = ""
    last_name: str = ""
    company: str = ""
    title: Optional[str] = None
    source: str = ""
    status: str = "new"
    metadata: Dict[str, Any] = None


@dataclass
class CRMResult:
    """CRM operation result."""
    operation: CRMOperation
    record_id: str
    status: str
    processed_at: float
    data: Dict[str, Any]
    error_message: Optional[str] = None


class CRMAdapter(BaseAdapter):
    """CRM adapter with reliability patterns and Saga compensation."""
    
    def __init__(self, redis_client: redis.Redis, crm_config: Dict[str, Any]):
        config = AdapterConfig(
            timeout_ms=30000,
            max_retries=3,
            retry_delay_ms=1000,
            circuit_breaker_threshold=5,
            circuit_breaker_timeout_ms=60000,
            bulkhead_max_concurrent=8,
            idempotency_ttl_seconds=3600,
            saga_compensation_enabled=True,
            saga_compensation_timeout_ms=60000
        )
        
        super().__init__("crm_adapter", config, redis_client)
        self.crm_config = crm_config
        self.crm_operations: Dict[str, CRMResult] = {}  # For compensation tracking
    
    async def create_contact(self, contact: Contact) -> CRMResult:
        """Create contact with reliability patterns."""
        async def _create_operation():
            # Simulate CRM API call
            await asyncio.sleep(0.1)  # Simulate API delay
            
            # In production, this would call actual CRM API (Salesforce, HubSpot, etc.)
            contact_id = f"contact_{int(time.time() * 1000)}"
            
            result = CRMResult(
                operation=CRMOperation.CREATE_CONTACT,
                record_id=contact_id,
                status="created",
                processed_at=time.time(),
                data={
                    "contact_id": contact_id,
                    "email": contact.email,
                    "first_name": contact.first_name,
                    "last_name": contact.last_name,
                    "phone": contact.phone,
                    "company": contact.company,
                    "title": contact.title,
                    "metadata": contact.metadata or {}
                }
            )
            
            # Store for potential compensation
            self.crm_operations[contact_id] = result
            
            logger.info("Contact created", contact_id=contact_id, email=contact.email, name=f"{contact.first_name} {contact.last_name}")
            return result
        
        return await self.call(_create_operation)
    
    async def create_lead(self, lead: Lead) -> CRMResult:
        """Create lead with reliability patterns."""
        async def _create_operation():
            # Simulate CRM API call
            await asyncio.sleep(0.1)  # Simulate API delay
            
            # In production, this would call actual CRM API
            lead_id = f"lead_{int(time.time() * 1000)}"
            
            result = CRMResult(
                operation=CRMOperation.CREATE_LEAD,
                record_id=lead_id,
                status="created",
                processed_at=time.time(),
                data={
                    "lead_id": lead_id,
                    "email": lead.email,
                    "first_name": lead.first_name,
                    "last_name": lead.last_name,
                    "company": lead.company,
                    "title": lead.title,
                    "source": lead.source,
                    "status": lead.status,
                    "metadata": lead.metadata or {}
                }
            )
            
            # Store for potential compensation
            self.crm_operations[lead_id] = result
            
            logger.info("Lead created", lead_id=lead_id, email=lead.email, company=lead.company)
            return result
        
        return await self.call(_create_operation)
    
    async def update_contact(self, contact_id: str, updates: Dict[str, Any]) -> CRMResult:
        """Update contact with reliability patterns."""
        async def _update_operation():
            # Simulate CRM API call
            await asyncio.sleep(0.1)  # Simulate API delay
            
            # In production, this would call actual CRM API
            result = CRMResult(
                operation=CRMOperation.UPDATE_CONTACT,
                record_id=contact_id,
                status="updated",
                processed_at=time.time(),
                data=updates
            )
            
            # Store for potential compensation
            self.crm_operations[f"update_{contact_id}"] = result
            
            logger.info("Contact updated", contact_id=contact_id, updates=updates)
            return result
        
        return await self.call(_update_operation)
    
    async def convert_lead(self, lead_id: str, contact_data: Dict[str, Any]) -> CRMResult:
        """Convert lead to contact with reliability patterns."""
        async def _convert_operation():
            # Simulate CRM API call
            await asyncio.sleep(0.15)  # Simulate conversion delay
            
            # In production, this would call actual CRM API
            contact_id = f"contact_from_lead_{lead_id}"
            
            result = CRMResult(
                operation=CRMOperation.CONVERT_LEAD,
                record_id=contact_id,
                status="converted",
                processed_at=time.time(),
                data={
                    "lead_id": lead_id,
                    "contact_id": contact_id,
                    "contact_data": contact_data
                }
            )
            
            # Store for potential compensation
            self.crm_operations[f"convert_{lead_id}"] = result
            
            logger.info("Lead converted to contact", lead_id=lead_id, contact_id=contact_id)
            return result
        
        return await self.call(_convert_operation)
    
    async def compensate_crm_operation(self, record_id: str) -> bool:
        """Compensate for CRM operation."""
        async def _compensation_operation():
            # Find the operation to compensate
            operation = None
            for op_id, op_result in self.crm_operations.items():
                if op_result.record_id == record_id or op_id == record_id:
                    operation = op_result
                    break
            
            if not operation:
                logger.warning("CRM operation not found for compensation", record_id=record_id)
                return False
            
            # Execute compensation based on operation type
            if operation.operation == CRMOperation.CREATE_CONTACT:
                # Delete the contact
                await self._delete_contact(record_id)
                logger.info("Contact compensation executed (deleted)", record_id=record_id)
                
            elif operation.operation == CRMOperation.CREATE_LEAD:
                # Delete the lead
                await self._delete_lead(record_id)
                logger.info("Lead compensation executed (deleted)", record_id=record_id)
                
            elif operation.operation == CRMOperation.UPDATE_CONTACT:
                # Revert the update (would need to store original data)
                logger.info("Contact update compensation executed (reverted)", record_id=record_id)
                
            elif operation.operation == CRMOperation.CONVERT_LEAD:
                # Revert the conversion
                await self._revert_lead_conversion(record_id)
                logger.info("Lead conversion compensation executed (reverted)", record_id=record_id)
            
            return True
        
        return await self.compensate(_compensation_operation)
    
    async def _delete_contact(self, contact_id: str) -> None:
        """Delete contact (compensation operation)."""
        # Simulate deletion
        await asyncio.sleep(0.05)
        logger.info("Contact deleted", contact_id=contact_id)
    
    async def _delete_lead(self, lead_id: str) -> None:
        """Delete lead (compensation operation)."""
        # Simulate deletion
        await asyncio.sleep(0.05)
        logger.info("Lead deleted", lead_id=lead_id)
    
    async def _revert_lead_conversion(self, contact_id: str) -> None:
        """Revert lead conversion (compensation operation)."""
        # Simulate reversion
        await asyncio.sleep(0.05)
        logger.info("Lead conversion reverted", contact_id=contact_id)
    
    async def get_crm_operations(self) -> List[CRMResult]:
        """Get list of CRM operations for compensation tracking."""
        return list(self.crm_operations.values())
    
    async def get_crm_metrics(self) -> Dict[str, Any]:
        """Get CRM adapter metrics."""
        base_metrics = await self.get_metrics()
        
        # Calculate CRM-specific metrics
        operations_by_type = {}
        for operation in self.crm_operations.values():
            op_type = operation.operation.value
            operations_by_type[op_type] = operations_by_type.get(op_type, 0) + 1
        
        return {
            **base_metrics,
            "total_operations": len(self.crm_operations),
            "operations_by_type": operations_by_type,
            "crm_system": self.crm_config.get("system", "unknown"),
            "api_endpoint": self.crm_config.get("endpoint", "unknown")
        }