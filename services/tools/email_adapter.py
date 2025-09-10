"""Email adapter with Saga compensation support."""

import asyncio
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import structlog
import redis.asyncio as redis

from .base_adapter import BaseAdapter, AdapterConfig

logger = structlog.get_logger(__name__)


@dataclass
class EmailMessage:
    """Email message structure."""
    to: str
    subject: str
    body: str
    html_body: Optional[str] = None
    from_email: Optional[str] = None
    reply_to: Optional[str] = None
    attachments: List[Dict[str, Any]] = None


@dataclass
class EmailResult:
    """Email operation result."""
    message_id: str
    status: str
    sent_at: float
    recipient: str
    subject: str


class EmailAdapter(BaseAdapter):
    """Email adapter with reliability patterns and Saga compensation."""
    
    def __init__(self, redis_client: redis.Redis, smtp_config: Dict[str, Any]):
        config = AdapterConfig(
            timeout_ms=30000,
            max_retries=3,
            retry_delay_ms=1000,
            circuit_breaker_threshold=5,
            circuit_breaker_timeout_ms=60000,
            bulkhead_max_concurrent=10,
            idempotency_ttl_seconds=3600,
            saga_compensation_enabled=True,
            saga_compensation_timeout_ms=60000
        )
        
        super().__init__("email_adapter", config, redis_client)
        self.smtp_config = smtp_config
        self.sent_emails: Dict[str, EmailResult] = {}  # For compensation tracking
    
    async def send_email(self, message: EmailMessage) -> EmailResult:
        """Send email with reliability patterns."""
        async def _send_operation():
            # Simulate email sending
            await asyncio.sleep(0.1)  # Simulate network delay
            
            # In production, this would use actual SMTP
            message_id = f"email_{int(time.time() * 1000)}"
            
            result = EmailResult(
                message_id=message_id,
                status="sent",
                sent_at=time.time(),
                recipient=message.to,
                subject=message.subject
            )
            
            # Store for potential compensation
            self.sent_emails[message_id] = result
            
            logger.info("Email sent", message_id=message_id, recipient=message.to, subject=message.subject)
            return result
        
        return await self.call(_send_operation)
    
    async def send_bulk_email(self, messages: List[EmailMessage]) -> List[EmailResult]:
        """Send bulk emails with reliability patterns."""
        async def _bulk_send_operation():
            results = []
            for message in messages:
                result = await self.send_email(message)
                results.append(result)
            return results
        
        return await self.call(_bulk_send_operation)
    
    async def compensate_send_email(self, message_id: str) -> bool:
        """Compensate for sent email (mark as failed/unsent)."""
        async def _compensation_operation():
            if message_id in self.sent_emails:
                # In production, this might involve:
                # - Sending a follow-up email
                # - Updating database records
                # - Notifying administrators
                
                email_result = self.sent_emails[message_id]
                email_result.status = "compensated"
                
                logger.info("Email compensation executed", message_id=message_id, recipient=email_result.recipient)
                
                # Remove from sent emails
                del self.sent_emails[message_id]
                
                return True
            else:
                logger.warning("Email not found for compensation", message_id=message_id)
                return False
        
        return await self.compensate(_compensation_operation)
    
    async def get_sent_emails(self) -> List[EmailResult]:
        """Get list of sent emails for compensation tracking."""
        return list(self.sent_emails.values())
    
    async def get_email_metrics(self) -> Dict[str, Any]:
        """Get email adapter metrics."""
        base_metrics = await self.get_metrics()
        
        return {
            **base_metrics,
            "sent_emails_count": len(self.sent_emails),
            "smtp_config": {
                "host": self.smtp_config.get("host", "unknown"),
                "port": self.smtp_config.get("port", "unknown")
            }
        }