"""Webhook Manager for tenant lifecycle events and notifications."""

import asyncio
import json
import uuid
import hmac
import hashlib
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = structlog.get_logger(__name__)


class WebhookEvent(Enum):
    """Webhook event types."""
    TENANT_CREATED = "tenant.created"
    TENANT_UPDATED = "tenant.updated"
    TENANT_DELETED = "tenant.deleted"
    PLAN_UPGRADED = "plan.upgraded"
    PLAN_DOWNGRADED = "plan.downgraded"
    PAYMENT_SUCCESS = "payment.success"
    PAYMENT_FAILED = "payment.failed"
    TRIAL_STARTED = "trial.started"
    TRIAL_ENDING = "trial.ending"
    TRIAL_ENDED = "trial.ended"
    QUOTA_EXCEEDED = "quota.exceeded"
    BILLING_CYCLE_CHANGED = "billing.cycle_changed"
    SUBSCRIPTION_CANCELLED = "subscription.cancelled"
    SUBSCRIPTION_REACTIVATED = "subscription.reactivated"


class WebhookStatus(Enum):
    """Webhook delivery status."""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    DISABLED = "disabled"


class WebhookSecret:
    """Webhook secret for signature verification."""
    def __init__(self, secret: str):
        self.secret = secret
    
    def generate_signature(self, payload: str) -> str:
        """Generate HMAC signature for payload."""
        return hmac.new(
            self.secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def verify_signature(self, payload: str, signature: str) -> bool:
        """Verify HMAC signature."""
        expected_signature = self.generate_signature(payload)
        return hmac.compare_digest(signature, expected_signature)


@dataclass
class WebhookEndpoint:
    """Webhook endpoint configuration."""
    endpoint_id: str
    tenant_id: str
    url: str
    events: List[WebhookEvent]
    secret: str
    enabled: bool = True
    created_at: datetime = None
    updated_at: datetime = None
    metadata: Dict[str, Any] = None


@dataclass
class WebhookDelivery:
    """Webhook delivery record."""
    delivery_id: str
    endpoint_id: str
    event: WebhookEvent
    payload: Dict[str, Any]
    status: WebhookStatus
    attempts: int = 0
    max_attempts: int = 3
    next_retry_at: Optional[datetime] = None
    last_attempt_at: Optional[datetime] = None
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = None
    updated_at: datetime = None


@dataclass
class WebhookEventData:
    """Webhook event data."""
    event: WebhookEvent
    tenant_id: str
    data: Dict[str, Any]
    timestamp: datetime
    event_id: str


class WebhookManager:
    """Manages webhook endpoints and event delivery."""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.webhook_endpoints: Dict[str, WebhookEndpoint] = {}
        self.webhook_deliveries: Dict[str, WebhookDelivery] = {}
        self.event_handlers: Dict[WebhookEvent, List[Callable]] = {}
        self.retry_delays = [60, 300, 900, 3600]  # 1min, 5min, 15min, 1hour
    
    async def create_webhook_endpoint(self, tenant_id: str, url: str, 
                                    events: List[WebhookEvent],
                                    secret: str,
                                    metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create webhook endpoint."""
        try:
            logger.info("Creating webhook endpoint",
                       tenant_id=tenant_id,
                       url=url,
                       events=[e.value for e in events])
            
            # Validate URL
            if not self._validate_url(url):
                raise ValueError("Invalid webhook URL")
            
            # Generate endpoint ID
            endpoint_id = str(uuid.uuid4())
            
            # Create webhook endpoint
            webhook_endpoint = WebhookEndpoint(
                endpoint_id=endpoint_id,
                tenant_id=tenant_id,
                url=url,
                events=events,
                secret=secret,
                enabled=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                metadata=metadata or {}
            )
            
            # Store endpoint
            self.webhook_endpoints[endpoint_id] = webhook_endpoint
            
            # Store in database
            await self._store_webhook_endpoint(webhook_endpoint)
            
            logger.info("Webhook endpoint created successfully",
                       endpoint_id=endpoint_id,
                       tenant_id=tenant_id)
            
            return endpoint_id
            
        except Exception as e:
            logger.error("Failed to create webhook endpoint",
                        tenant_id=tenant_id,
                        error=str(e))
            raise
    
    def _validate_url(self, url: str) -> bool:
        """Validate webhook URL."""
        try:
            # Basic URL validation
            return url.startswith(('http://', 'https://')) and '.' in url
        except Exception:
            return False
    
    async def _store_webhook_endpoint(self, webhook_endpoint: WebhookEndpoint):
        """Store webhook endpoint in database."""
        try:
            query = text("""
                INSERT INTO webhook_endpoints (
                    endpoint_id, tenant_id, url, events, secret, enabled,
                    created_at, updated_at, metadata
                ) VALUES (
                    :endpoint_id, :tenant_id, :url, :events, :secret, :enabled,
                    :created_at, :updated_at, :metadata
                )
            """)
            
            await self.db_session.execute(query, {
                "endpoint_id": webhook_endpoint.endpoint_id,
                "tenant_id": webhook_endpoint.tenant_id,
                "url": webhook_endpoint.url,
                "events": json.dumps([e.value for e in webhook_endpoint.events]),
                "secret": webhook_endpoint.secret,
                "enabled": webhook_endpoint.enabled,
                "created_at": webhook_endpoint.created_at,
                "updated_at": webhook_endpoint.updated_at,
                "metadata": json.dumps(webhook_endpoint.metadata or {})
            })
            
            await self.db_session.commit()
            
        except Exception as e:
            logger.error("Failed to store webhook endpoint", error=str(e))
            await self.db_session.rollback()
            raise
    
    async def update_webhook_endpoint(self, endpoint_id: str, url: Optional[str] = None,
                                    events: Optional[List[WebhookEvent]] = None,
                                    enabled: Optional[bool] = None,
                                    metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Update webhook endpoint."""
        try:
            logger.info("Updating webhook endpoint", endpoint_id=endpoint_id)
            
            if endpoint_id not in self.webhook_endpoints:
                raise ValueError("Webhook endpoint not found")
            
            webhook_endpoint = self.webhook_endpoints[endpoint_id]
            
            # Update fields
            if url is not None:
                if not self._validate_url(url):
                    raise ValueError("Invalid webhook URL")
                webhook_endpoint.url = url
            
            if events is not None:
                webhook_endpoint.events = events
            
            if enabled is not None:
                webhook_endpoint.enabled = enabled
            
            if metadata is not None:
                webhook_endpoint.metadata = metadata
            
            webhook_endpoint.updated_at = datetime.now(timezone.utc)
            
            # Update in database
            await self._update_webhook_endpoint_db(webhook_endpoint)
            
            logger.info("Webhook endpoint updated successfully", endpoint_id=endpoint_id)
            return True
            
        except Exception as e:
            logger.error("Failed to update webhook endpoint",
                        endpoint_id=endpoint_id,
                        error=str(e))
            return False
    
    async def _update_webhook_endpoint_db(self, webhook_endpoint: WebhookEndpoint):
        """Update webhook endpoint in database."""
        try:
            query = text("""
                UPDATE webhook_endpoints 
                SET url = :url,
                    events = :events,
                    enabled = :enabled,
                    updated_at = :updated_at,
                    metadata = :metadata
                WHERE endpoint_id = :endpoint_id
            """)
            
            await self.db_session.execute(query, {
                "endpoint_id": webhook_endpoint.endpoint_id,
                "url": webhook_endpoint.url,
                "events": json.dumps([e.value for e in webhook_endpoint.events]),
                "enabled": webhook_endpoint.enabled,
                "updated_at": webhook_endpoint.updated_at,
                "metadata": json.dumps(webhook_endpoint.metadata or {})
            })
            
            await self.db_session.commit()
            
        except Exception as e:
            logger.error("Failed to update webhook endpoint in database", error=str(e))
            await self.db_session.rollback()
            raise
    
    async def delete_webhook_endpoint(self, endpoint_id: str) -> bool:
        """Delete webhook endpoint."""
        try:
            logger.info("Deleting webhook endpoint", endpoint_id=endpoint_id)
            
            if endpoint_id not in self.webhook_endpoints:
                return False
            
            # Delete from database
            await self._delete_webhook_endpoint_db(endpoint_id)
            
            # Remove from memory
            del self.webhook_endpoints[endpoint_id]
            
            logger.info("Webhook endpoint deleted successfully", endpoint_id=endpoint_id)
            return True
            
        except Exception as e:
            logger.error("Failed to delete webhook endpoint",
                        endpoint_id=endpoint_id,
                        error=str(e))
            return False
    
    async def _delete_webhook_endpoint_db(self, endpoint_id: str):
        """Delete webhook endpoint from database."""
        try:
            query = text("DELETE FROM webhook_endpoints WHERE endpoint_id = :endpoint_id")
            await self.db_session.execute(query, {"endpoint_id": endpoint_id})
            await self.db_session.commit()
            
        except Exception as e:
            logger.error("Failed to delete webhook endpoint from database", error=str(e))
            await self.db_session.rollback()
            raise
    
    async def trigger_webhook_event(self, event: WebhookEvent, tenant_id: str, 
                                  data: Dict[str, Any]) -> List[str]:
        """Trigger webhook event for tenant."""
        try:
            logger.info("Triggering webhook event",
                       event=event.value,
                       tenant_id=tenant_id)
            
            # Create event data
            event_data = WebhookEventData(
                event=event,
                tenant_id=tenant_id,
                data=data,
                timestamp=datetime.now(timezone.utc),
                event_id=str(uuid.uuid4())
            )
            
            # Find matching endpoints
            matching_endpoints = []
            for endpoint in self.webhook_endpoints.values():
                if (endpoint.tenant_id == tenant_id and
                    endpoint.enabled and
                    event in endpoint.events):
                    matching_endpoints.append(endpoint)
            
            # Create deliveries
            delivery_ids = []
            for endpoint in matching_endpoints:
                delivery_id = await self._create_webhook_delivery(endpoint, event_data)
                delivery_ids.append(delivery_id)
            
            # Process deliveries
            if delivery_ids:
                asyncio.create_task(self._process_webhook_deliveries(delivery_ids))
            
            logger.info("Webhook event triggered",
                       event=event.value,
                       tenant_id=tenant_id,
                       delivery_count=len(delivery_ids))
            
            return delivery_ids
            
        except Exception as e:
            logger.error("Failed to trigger webhook event",
                        event=event.value,
                        tenant_id=tenant_id,
                        error=str(e))
            return []
    
    async def _create_webhook_delivery(self, endpoint: WebhookEndpoint, 
                                     event_data: WebhookEventData) -> str:
        """Create webhook delivery."""
        try:
            delivery_id = str(uuid.uuid4())
            
            # Prepare payload
            payload = {
                "id": event_data.event_id,
                "event": event_data.event.value,
                "tenant_id": event_data.tenant_id,
                "data": event_data.data,
                "timestamp": event_data.timestamp.isoformat(),
                "api_version": "1.0"
            }
            
            # Create delivery
            delivery = WebhookDelivery(
                delivery_id=delivery_id,
                endpoint_id=endpoint.endpoint_id,
                event=event_data.event,
                payload=payload,
                status=WebhookStatus.PENDING,
                attempts=0,
                max_attempts=3,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            
            # Store delivery
            self.webhook_deliveries[delivery_id] = delivery
            
            return delivery_id
            
        except Exception as e:
            logger.error("Failed to create webhook delivery", error=str(e))
            raise
    
    async def _process_webhook_deliveries(self, delivery_ids: List[str]):
        """Process webhook deliveries."""
        try:
            for delivery_id in delivery_ids:
                if delivery_id in self.webhook_deliveries:
                    await self._deliver_webhook(delivery_id)
            
        except Exception as e:
            logger.error("Failed to process webhook deliveries", error=str(e))
    
    async def _deliver_webhook(self, delivery_id: str):
        """Deliver webhook."""
        try:
            delivery = self.webhook_deliveries[delivery_id]
            endpoint = self.webhook_endpoints[delivery.endpoint_id]
            
            # Check if delivery should be retried
            if delivery.attempts >= delivery.max_attempts:
                delivery.status = WebhookStatus.FAILED
                delivery.updated_at = datetime.now(timezone.utc)
                logger.warning("Webhook delivery failed permanently",
                             delivery_id=delivery_id,
                             attempts=delivery.attempts)
                return
            
            # Check retry timing
            if delivery.next_retry_at and delivery.next_retry_at > datetime.now(timezone.utc):
                return
            
            delivery.status = WebhookStatus.RETRYING
            delivery.attempts += 1
            delivery.last_attempt_at = datetime.now(timezone.utc)
            delivery.updated_at = datetime.now(timezone.utc)
            
            # Prepare payload
            payload_json = json.dumps(delivery.payload)
            
            # Generate signature
            webhook_secret = WebhookSecret(endpoint.secret)
            signature = webhook_secret.generate_signature(payload_json)
            
            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Multi-Tenant-AIaaS-Platform/1.0",
                "X-Webhook-Signature": f"sha256={signature}",
                "X-Webhook-Event": delivery.event.value,
                "X-Webhook-Delivery": delivery_id
            }
            
            # Send webhook
            success = await self._send_webhook_request(endpoint.url, headers, payload_json)
            
            if success:
                delivery.status = WebhookStatus.DELIVERED
                delivery.updated_at = datetime.now(timezone.utc)
                logger.info("Webhook delivered successfully",
                           delivery_id=delivery_id,
                           endpoint_id=endpoint.endpoint_id)
            else:
                # Schedule retry
                retry_delay = self.retry_delays[min(delivery.attempts - 1, len(self.retry_delays) - 1)]
                delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)
                delivery.updated_at = datetime.now(timezone.utc)
                
                logger.warning("Webhook delivery failed, scheduling retry",
                             delivery_id=delivery_id,
                             attempt=delivery.attempts,
                             next_retry=delivery.next_retry_at)
                
                # Schedule retry
                asyncio.create_task(self._schedule_retry(delivery_id, retry_delay))
            
        except Exception as e:
            logger.error("Failed to deliver webhook",
                        delivery_id=delivery_id,
                        error=str(e))
            
            delivery = self.webhook_deliveries[delivery_id]
            delivery.status = WebhookStatus.FAILED
            delivery.error_message = str(e)
            delivery.updated_at = datetime.now(timezone.utc)
    
    async def _send_webhook_request(self, url: str, headers: Dict[str, str], 
                                  payload: str) -> bool:
        """Send webhook HTTP request."""
        try:
            # In production, this would use aiohttp or httpx
            # For this implementation, we'll simulate the request
            
            import random
            
            # Simulate network request
            await asyncio.sleep(0.1)
            
            # Simulate success/failure (90% success rate)
            success = random.random() > 0.1
            
            if success:
                logger.info("Webhook request sent successfully", url=url)
            else:
                logger.warning("Webhook request failed", url=url)
            
            return success
            
        except Exception as e:
            logger.error("Failed to send webhook request", url=url, error=str(e))
            return False
    
    async def _schedule_retry(self, delivery_id: str, delay_seconds: int):
        """Schedule webhook retry."""
        try:
            await asyncio.sleep(delay_seconds)
            await self._deliver_webhook(delivery_id)
            
        except Exception as e:
            logger.error("Failed to schedule webhook retry",
                        delivery_id=delivery_id,
                        error=str(e))
    
    async def get_webhook_endpoints(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get webhook endpoints for tenant."""
        try:
            endpoints = []
            
            for endpoint in self.webhook_endpoints.values():
                if endpoint.tenant_id == tenant_id:
                    endpoints.append({
                        "endpoint_id": endpoint.endpoint_id,
                        "url": endpoint.url,
                        "events": [e.value for e in endpoint.events],
                        "enabled": endpoint.enabled,
                        "created_at": endpoint.created_at.isoformat(),
                        "updated_at": endpoint.updated_at.isoformat(),
                        "metadata": endpoint.metadata
                    })
            
            return endpoints
            
        except Exception as e:
            logger.error("Failed to get webhook endpoints", error=str(e))
            return []
    
    async def get_webhook_deliveries(self, endpoint_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get webhook deliveries for endpoint."""
        try:
            deliveries = []
            
            for delivery in self.webhook_deliveries.values():
                if delivery.endpoint_id == endpoint_id:
                    deliveries.append({
                        "delivery_id": delivery.delivery_id,
                        "event": delivery.event.value,
                        "status": delivery.status.value,
                        "attempts": delivery.attempts,
                        "response_status": delivery.response_status,
                        "error_message": delivery.error_message,
                        "created_at": delivery.created_at.isoformat(),
                        "last_attempt_at": delivery.last_attempt_at.isoformat() if delivery.last_attempt_at else None
                    })
            
            # Sort by creation date (newest first)
            deliveries.sort(key=lambda x: x["created_at"], reverse=True)
            
            return deliveries[:limit]
            
        except Exception as e:
            logger.error("Failed to get webhook deliveries", error=str(e))
            return []
    
    async def verify_webhook_signature(self, payload: str, signature: str, 
                                     endpoint_id: str) -> bool:
        """Verify webhook signature."""
        try:
            if endpoint_id not in self.webhook_endpoints:
                return False
            
            endpoint = self.webhook_endpoints[endpoint_id]
            webhook_secret = WebhookSecret(endpoint.secret)
            
            # Extract signature from header
            if signature.startswith("sha256="):
                signature = signature[7:]
            
            return webhook_secret.verify_signature(payload, signature)
            
        except Exception as e:
            logger.error("Failed to verify webhook signature", error=str(e))
            return False
    
    async def retry_failed_deliveries(self):
        """Retry failed webhook deliveries."""
        try:
            current_time = datetime.now(timezone.utc)
            retry_deliveries = []
            
            for delivery in self.webhook_deliveries.values():
                if (delivery.status == WebhookStatus.RETRYING and
                    delivery.next_retry_at and
                    delivery.next_retry_at <= current_time):
                    retry_deliveries.append(delivery.delivery_id)
            
            # Retry deliveries
            for delivery_id in retry_deliveries:
                await self._deliver_webhook(delivery_id)
            
            if retry_deliveries:
                logger.info("Retried failed deliveries", count=len(retry_deliveries))
            
        except Exception as e:
            logger.error("Failed to retry failed deliveries", error=str(e))
    
    async def cleanup_old_deliveries(self, days_old: int = 30):
        """Cleanup old webhook deliveries."""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
            old_deliveries = []
            
            for delivery_id, delivery in self.webhook_deliveries.items():
                if delivery.created_at < cutoff_date:
                    old_deliveries.append(delivery_id)
            
            # Remove old deliveries
            for delivery_id in old_deliveries:
                del self.webhook_deliveries[delivery_id]
            
            if old_deliveries:
                logger.info("Cleaned up old deliveries", count=len(old_deliveries))
            
        except Exception as e:
            logger.error("Failed to cleanup old deliveries", error=str(e))
