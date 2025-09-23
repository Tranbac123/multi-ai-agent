import asyncio
import httpx
from typing import Dict, Any
from ..models import NotificationRequest, NotificationType
from ..settings import settings

class SlackChannel:
    def __init__(self):
        self.bot_token = settings.slack_bot_token
        self.webhook_url = settings.slack_webhook_url
    
    async def send(self, request: NotificationRequest) -> Dict[str, Any]:
        """Send Slack notification"""
        if not self.bot_token and not self.webhook_url:
            return {
                "success": False,
                "error": "Slack not configured",
                "sent_to": [],
                "failed_recipients": request.recipients
            }
        
        try:
            # Use webhook if available, otherwise use bot API
            if self.webhook_url:
                return await self._send_via_webhook(request)
            else:
                return await self._send_via_bot(request)
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "sent_to": [],
                "failed_recipients": request.recipients
            }
    
    async def _send_via_webhook(self, request: NotificationRequest) -> Dict[str, Any]:
        """Send via Slack webhook"""
        payload = {
            "text": request.subject or "Notification",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": request.message
                    }
                }
            ]
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(self.webhook_url, json=payload)
            response.raise_for_status()
            
            return {
                "success": True,
                "sent_to": request.recipients,
                "failed_recipients": []
            }
    
    async def _send_via_bot(self, request: NotificationRequest) -> Dict[str, Any]:
        """Send via Slack Bot API"""
        headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json"
        }
        
        sent_to = []
        failed_recipients = []
        
        async with httpx.AsyncClient(timeout=30) as client:
            for recipient in request.recipients:
                try:
                    payload = {
                        "channel": recipient,
                        "text": request.message,
                        "username": "Notification Bot"
                    }
                    
                    if request.subject:
                        payload["text"] = f"*{request.subject}*\n\n{request.message}"
                    
                    response = await client.post(
                        "https://slack.com/api/chat.postMessage",
                        headers=headers,
                        json=payload
                    )
                    response.raise_for_status()
                    
                    data = response.json()
                    if data.get("ok"):
                        sent_to.append(recipient)
                    else:
                        failed_recipients.append(recipient)
                        
                except Exception:
                    failed_recipients.append(recipient)
        
        return {
            "success": len(failed_recipients) == 0,
            "sent_to": sent_to,
            "failed_recipients": failed_recipients
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Slack channel health"""
        if not self.bot_token and not self.webhook_url:
            return {
                "status": "not_configured",
                "error": "Neither bot token nor webhook URL configured"
            }
        
        try:
            if self.webhook_url:
                # Test webhook
                async with httpx.AsyncClient(timeout=5) as client:
                    response = await client.post(
                        self.webhook_url,
                        json={"text": "Health check"}
                    )
                    return {"status": "healthy"}
            else:
                # Test bot token
                headers = {"Authorization": f"Bearer {self.bot_token}"}
                async with httpx.AsyncClient(timeout=5) as client:
                    response = await client.get(
                        "https://slack.com/api/auth.test",
                        headers=headers
                    )
                    data = response.json()
                    return {
                        "status": "healthy" if data.get("ok") else "unhealthy",
                        "user": data.get("user")
                    }
                    
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

