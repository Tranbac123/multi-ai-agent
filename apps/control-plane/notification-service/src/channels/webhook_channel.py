import asyncio
import httpx
from typing import Dict, Any, List
from ..models import NotificationRequest, NotificationType
from ..settings import settings

class WebhookChannel:
    def __init__(self):
        self.timeout = settings.webhook_timeout
        self.retry_attempts = settings.webhook_retry_attempts
        self.retry_delay = settings.webhook_retry_delay
    
    async def send(self, request: NotificationRequest) -> Dict[str, Any]:
        """Send webhook notification"""
        # Extract webhook URLs from recipients (assuming recipients are URLs)
        webhook_urls = [url for url in request.recipients if url.startswith('http')]
        
        if not webhook_urls:
            return {
                "success": False,
                "error": "No valid webhook URLs provided",
                "sent_to": [],
                "failed_recipients": request.recipients
            }
        
        sent_to = []
        failed_recipients = []
        
        # Send to each webhook URL
        for url in webhook_urls:
            success = await self._send_to_webhook(url, request)
            if success:
                sent_to.append(url)
            else:
                failed_recipients.append(url)
        
        return {
            "success": len(failed_recipients) == 0,
            "sent_to": sent_to,
            "failed_recipients": failed_recipients
        }
    
    async def _send_to_webhook(self, url: str, request: NotificationRequest) -> bool:
        """Send notification to specific webhook URL with retry logic"""
        payload = {
            "tenant_id": request.tenant_id,
            "notification_type": request.notification_type.value,
            "subject": request.subject,
            "message": request.message,
            "priority": request.priority.value,
            "metadata": request.metadata,
            "timestamp": str(asyncio.get_event_loop().time())
        }
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "notification-service/1.0"
        }
        
        for attempt in range(self.retry_attempts):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        url,
                        json=payload,
                        headers=headers
                    )
                    response.raise_for_status()
                    return True
                    
            except Exception as e:
                if attempt == self.retry_attempts - 1:
                    print(f"Webhook failed after {self.retry_attempts} attempts: {e}")
                    return False
                else:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
        
        return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Check webhook channel health"""
        return {
            "status": "healthy",
            "timeout": self.timeout,
            "retry_attempts": self.retry_attempts,
            "retry_delay": self.retry_delay
        }

