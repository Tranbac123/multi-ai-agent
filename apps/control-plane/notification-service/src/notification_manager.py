import time
import uuid
from typing import Dict, List, Optional
from .models import (
    NotificationRequest, NotificationResponse, NotificationType, 
    NotificationStatus, ChannelConfig
)
from .channels import EmailChannel, SlackChannel, WebhookChannel

class NotificationManager:
    def __init__(self):
        self.channels = {
            NotificationType.EMAIL: EmailChannel(),
            NotificationType.SLACK: SlackChannel(),
            NotificationType.WEBHOOK: WebhookChannel(),
        }
        self.notification_history: Dict[str, NotificationStatus] = {}
    
    async def send_notification(self, request: NotificationRequest) -> NotificationResponse:
        """Send notification through appropriate channel"""
        start_time = time.time()
        notification_id = str(uuid.uuid4())
        
        try:
            # Validate notification type
            if request.notification_type not in self.channels:
                return NotificationResponse(
                    success=False,
                    notification_id=notification_id,
                    sent_to=[],
                    processing_time_ms=int((time.time() - start_time) * 1000),
                    error=f"Unsupported notification type: {request.notification_type}"
                )
            
            # Get appropriate channel
            channel = self.channels[request.notification_type]
            
            # Send notification
            result = await channel.send(request)
            
            # Record in history
            status = NotificationStatus(
                notification_id=notification_id,
                tenant_id=request.tenant_id,
                notification_type=request.notification_type,
                status="sent" if result["success"] else "failed",
                recipients=request.recipients,
                sent_at=str(int(time.time())) if result["success"] else None,
                error=result.get("error")
            )
            self.notification_history[notification_id] = status
            
            return NotificationResponse(
                success=result["success"],
                notification_id=notification_id,
                sent_to=result.get("sent_to", []),
                failed_recipients=result.get("failed_recipients", []),
                processing_time_ms=int((time.time() - start_time) * 1000),
                error=result.get("error")
            )
            
        except Exception as e:
            # Record failed notification
            status = NotificationStatus(
                notification_id=notification_id,
                tenant_id=request.tenant_id,
                notification_type=request.notification_type,
                status="failed",
                recipients=request.recipients,
                error=str(e)
            )
            self.notification_history[notification_id] = status
            
            return NotificationResponse(
                success=False,
                notification_id=notification_id,
                sent_to=[],
                failed_recipients=request.recipients,
                processing_time_ms=int((time.time() - start_time) * 1000),
                error=str(e)
            )
    
    async def get_channel_health(self) -> Dict[NotificationType, Dict[str, any]]:
        """Get health status for all channels"""
        health_status = {}
        
        for notification_type, channel in self.channels.items():
            if hasattr(channel, 'health_check'):
                health_status[notification_type] = await channel.health_check()
            else:
                health_status[notification_type] = {"status": "unknown"}
        
        return health_status
    
    def get_notification_status(self, notification_id: str) -> Optional[NotificationStatus]:
        """Get status of a specific notification"""
        return self.notification_history.get(notification_id)
    
    def get_tenant_notifications(self, tenant_id: str, limit: int = 100) -> List[NotificationStatus]:
        """Get recent notifications for a tenant"""
        tenant_notifications = [
            status for status in self.notification_history.values()
            if status.tenant_id == tenant_id
        ]
        
        # Sort by timestamp (newest first) and limit
        return sorted(
            tenant_notifications,
            key=lambda x: x.sent_at or "0",
            reverse=True
        )[:limit]
    
    def get_channel_configs(self) -> List[ChannelConfig]:
        """Get configuration for all channels"""
        configs = []
        
        for notification_type, channel in self.channels.items():
            # Determine if channel is enabled based on configuration
            enabled = False
            config = {}
            
            if notification_type == NotificationType.EMAIL:
                enabled = hasattr(channel, 'smtp_host') and channel.smtp_host is not None
                config = {"smtp_host": getattr(channel, 'smtp_host', None)}
            elif notification_type == NotificationType.SLACK:
                enabled = (
                    hasattr(channel, 'bot_token') and channel.bot_token is not None
                ) or (
                    hasattr(channel, 'webhook_url') and channel.webhook_url is not None
                )
                config = {
                    "bot_token_configured": hasattr(channel, 'bot_token') and channel.bot_token is not None,
                    "webhook_url_configured": hasattr(channel, 'webhook_url') and channel.webhook_url is not None
                }
            elif notification_type == NotificationType.WEBHOOK:
                enabled = True  # Webhook channel is always available
                config = {
                    "timeout": getattr(channel, 'timeout', 30),
                    "retry_attempts": getattr(channel, 'retry_attempts', 3)
                }
            
            configs.append(ChannelConfig(
                channel_type=notification_type,
                enabled=enabled,
                config=config
            ))
        
        return configs

