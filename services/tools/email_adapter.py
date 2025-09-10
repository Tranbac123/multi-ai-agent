"""Email adapter with saga compensation."""

import asyncio
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import structlog
import redis.asyncio as redis

from services.tools.base_adapter import BaseAdapter, AdapterConfig
from services.tools.saga_adapter import SagaAdapter, SagaStep

logger = structlog.get_logger(__name__)


@dataclass
class EmailMessage:
    """Email message."""
    to: str
    subject: str
    body: str
    from_email: str = "noreply@example.com"
    cc: List[str] = None
    bcc: List[str] = None
    attachments: List[Dict[str, Any]] = None


@dataclass
class EmailResult:
    """Email result."""
    message_id: str
    status: str
    sent_at: float
    error: Optional[str] = None


class EmailAdapter:
    """Email adapter with saga compensation."""
    
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
    
    async def send_email(
        self,
        message: EmailMessage,
        tenant_id: str,
        user_id: str
    ) -> EmailResult:
        """Send email using base adapter."""
        try:
            # Generate message ID
            message_id = f"email_{int(time.time())}_{hash(message.to)}"
            
            # Mock email sending
            result = await self.base_adapter.call(
                self._send_email_operation,
                message,
                message_id
            )
            
            return result
            
        except Exception as e:
            logger.error("Failed to send email", error=str(e), to=message.to, subject=message.subject)
            raise
    
    async def send_email_with_saga(
        self,
        message: EmailMessage,
        tenant_id: str,
        user_id: str
    ) -> EmailResult:
        """Send email using saga pattern."""
        try:
            # Generate saga ID
            saga_id = f"email_saga_{int(time.time())}_{hash(message.to)}"
            
            # Create saga steps
            steps = [
                SagaStep(
                    step_id="send_email",
                    operation=self._send_email_operation,
                    compensate=self._compensate_email_operation,
                    args=(message,),
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
                raise Exception(f"Email saga failed: {error_msg}")
            
            raise Exception("Email saga completed but no result found")
            
        except Exception as e:
            logger.error("Failed to send email with saga", error=str(e), to=message.to, subject=message.subject)
            raise
    
    async def _send_email_operation(
        self,
        message: EmailMessage,
        message_id: Optional[str] = None
    ) -> EmailResult:
        """Send email operation (mock implementation)."""
        try:
            if not message_id:
                message_id = f"email_{int(time.time())}_{hash(message.to)}"
            
            # Mock email sending delay
            await asyncio.sleep(0.1)
            
            # Mock email service response
            result = EmailResult(
                message_id=message_id,
                status="sent",
                sent_at=time.time()
            )
            
            logger.info("Email sent successfully", message_id=message_id, to=message.to, subject=message.subject)
            return result
            
        except Exception as e:
            logger.error("Email sending failed", error=str(e), to=message.to, subject=message.subject)
            raise
    
    async def _compensate_email_operation(
        self,
        result: EmailResult,
        message: EmailMessage
    ) -> None:
        """Compensate email operation (mock implementation)."""
        try:
            # Mock email compensation (e.g., send follow-up email, log for manual review)
            logger.info("Compensating email operation", message_id=result.message_id, to=message.to)
            
            # Mock compensation delay
            await asyncio.sleep(0.05)
            
            # In a real implementation, this might:
            # - Send a follow-up email
            # - Log the email for manual review
            # - Update a database record
            # - Send a notification to administrators
            
            logger.info("Email operation compensated", message_id=result.message_id)
            
        except Exception as e:
            logger.error("Email compensation failed", error=str(e), message_id=result.message_id)
            raise
    
    async def get_email_metrics(self) -> Dict[str, Any]:
        """Get email adapter metrics."""
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
            logger.error("Failed to get email metrics", error=str(e))
            return {'error': str(e)}
