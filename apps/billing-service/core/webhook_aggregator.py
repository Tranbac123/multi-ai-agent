"""Webhook aggregator for billing service."""

import asyncio
import time
import json
import uuid
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
import redis.asyncio as redis

from apps.billing-service.src.core.usage_tracker import UsageTracker, UsageType, UsageRecord
from apps.billing-service.src.core.billing_engine import BillingEngine, Invoice, InvoiceStatus

logger = structlog.get_logger(__name__)


class WebhookEventType(Enum):
    """Webhook event types."""
    USAGE_RECORDED = "usage_recorded"
    TOOL_CALLED = "tool_called"
    WS_CONNECTION = "ws_connection"
    STORAGE_USED = "storage_used"
    API_CALL = "api_call"
    BILLING_PERIOD_END = "billing_period_end"


class WebhookStatus(Enum):
    """Webhook processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class WebhookEvent:
    """Webhook event."""
    event_id: str
    event_type: WebhookEventType
    tenant_id: str
    timestamp: float
    data: Dict[str, Any]
    metadata: Dict[str, Any] = None


@dataclass
class UsageCounter:
    """Usage counter for aggregation."""
    tenant_id: str
    usage_type: UsageType
    total_usage: float
    count: int
    last_updated: float
    period_start: float
    period_end: float


@dataclass
class AggregatedUsage:
    """Aggregated usage data."""
    tenant_id: str
    period_start: float
    period_end: float
    counters: Dict[str, UsageCounter]
    total_cost: float
    last_aggregated: float


class WebhookAggregator:
    """Webhook aggregator for billing service."""

    def __init__(self, redis_client: redis.Redis, usage_tracker: UsageTracker, billing_engine: BillingEngine):
        self.redis = redis_client
        self.usage_tracker = usage_tracker
        self.billing_engine = billing_engine
        self.aggregation_interval = 300  # 5 minutes
        self.retry_attempts = 3
        self.retry_delay = 60  # 1 minute
        
        # Start background aggregation task
        asyncio.create_task(self._background_aggregation())

    async def process_webhook(self, webhook_data: Dict[str, Any]) -> bool:
        """Process incoming webhook."""
        try:
            # Validate webhook data
            if not self._validate_webhook_data(webhook_data):
                logger.error("Invalid webhook data", webhook_data=webhook_data)
                return False

            # Create webhook event
            event = WebhookEvent(
                event_id=str(uuid.uuid4()),
                event_type=WebhookEventType(webhook_data.get('event_type')),
                tenant_id=webhook_data.get('tenant_id'),
                timestamp=time.time(),
                data=webhook_data.get('data', {}),
                metadata=webhook_data.get('metadata', {})
            )

            # Store webhook event
            await self._store_webhook_event(event)

            # Process event based on type
            success = await self._process_event(event)

            if success:
                logger.info("Webhook processed successfully", event_id=event.event_id, event_type=event.event_type.value)
            else:
                logger.error("Webhook processing failed", event_id=event.event_id, event_type=event.event_type.value)

            return success

        except Exception as e:
            logger.error("Failed to process webhook", error=str(e), webhook_data=webhook_data)
            return False

    async def aggregate_usage_counters(self, tenant_id: str, period_start: float, period_end: float) -> AggregatedUsage:
        """Aggregate usage counters for a tenant and period."""
        try:
            # Get all webhook events for the period
            events = await self._get_webhook_events(tenant_id, period_start, period_end)

            # Initialize counters
            counters = {}
            for usage_type in UsageType:
                counters[usage_type.value] = UsageCounter(
                    tenant_id=tenant_id,
                    usage_type=usage_type,
                    total_usage=0.0,
                    count=0,
                    last_updated=period_start,
                    period_start=period_start,
                    period_end=period_end
                )

            # Process events and update counters
            for event in events:
                await self._update_counters_from_event(counters, event)

            # Calculate total cost
            total_cost = await self._calculate_total_cost(counters)

            # Create aggregated usage
            aggregated_usage = AggregatedUsage(
                tenant_id=tenant_id,
                period_start=period_start,
                period_end=period_end,
                counters=counters,
                total_cost=total_cost,
                last_aggregated=time.time()
            )

            # Store aggregated usage
            await self._store_aggregated_usage(aggregated_usage)

            logger.info(
                "Usage counters aggregated",
                tenant_id=tenant_id,
                period_start=period_start,
                period_end=period_end,
                total_cost=total_cost
            )

            return aggregated_usage

        except Exception as e:
            logger.error("Failed to aggregate usage counters", error=str(e))
            raise

    async def get_usage_counters(self, tenant_id: str, period_start: float, period_end: float) -> Dict[str, Any]:
        """Get usage counters for a tenant and period."""
        try:
            # Try to get cached aggregated usage
            aggregated_usage = await self._get_aggregated_usage(tenant_id, period_start, period_end)
            
            if aggregated_usage:
                return {
                    'tenant_id': tenant_id,
                    'period_start': period_start,
                    'period_end': period_end,
                    'counters': {k: asdict(v) for k, v in aggregated_usage.counters.items()},
                    'total_cost': aggregated_usage.total_cost,
                    'last_aggregated': aggregated_usage.last_aggregated
                }

            # If not cached, aggregate now
            aggregated_usage = await self.aggregate_usage_counters(tenant_id, period_start, period_end)
            
            return {
                'tenant_id': tenant_id,
                'period_start': period_start,
                'period_end': period_end,
                'counters': {k: asdict(v) for k, v in aggregated_usage.counters.items()},
                'total_cost': aggregated_usage.total_cost,
                'last_aggregated': aggregated_usage.last_aggregated
            }

        except Exception as e:
            logger.error("Failed to get usage counters", error=str(e))
            return {'error': str(e)}

    async def generate_invoice_preview(
        self,
        tenant_id: str,
        billing_period_start: float,
        billing_period_end: float
    ) -> Dict[str, Any]:
        """Generate invoice preview for a tenant."""
        try:
            # Get usage counters
            usage_counters = await self.get_usage_counters(tenant_id, billing_period_start, billing_period_end)
            
            if 'error' in usage_counters:
                return usage_counters

            # Create billing items from counters
            items = []
            subtotal = 0.0
            
            for counter_data in usage_counters['counters'].values():
                counter = UsageCounter(**counter_data)
                
                if counter.total_usage > 0:
                    # Calculate cost for this usage type
                    cost = await self._calculate_cost_for_usage_type(counter.usage_type, counter.total_usage)
                    unit_price = cost / counter.total_usage if counter.total_usage > 0 else 0
                    
                    item = {
                        'item_id': f"preview_{counter.usage_type.value}_{int(time.time())}",
                        'description': f"{counter.usage_type.value.replace('_', ' ').title()} Usage",
                        'quantity': counter.total_usage,
                        'unit_price': unit_price,
                        'total_price': cost,
                        'usage_type': counter.usage_type.value,
                        'count': counter.count
                    }
                    
                    items.append(item)
                    subtotal += cost

            # Calculate tax and total
            tax_rate = 0.1  # 10% tax rate
            tax_amount = subtotal * tax_rate
            total_amount = subtotal + tax_amount

            # Create invoice preview
            preview = {
                'tenant_id': tenant_id,
                'billing_period_start': billing_period_start,
                'billing_period_end': billing_period_end,
                'items': items,
                'subtotal': subtotal,
                'tax_rate': tax_rate,
                'tax_amount': tax_amount,
                'total_amount': total_amount,
                'generated_at': time.time(),
                'preview_id': str(uuid.uuid4())
            }

            # Store preview
            await self._store_invoice_preview(preview)

            logger.info(
                "Invoice preview generated",
                tenant_id=tenant_id,
                total_amount=total_amount,
                preview_id=preview['preview_id']
            )

            return preview

        except Exception as e:
            logger.error("Failed to generate invoice preview", error=str(e))
            return {'error': str(e)}

    async def test_plan_enforcement(self, tenant_id: str, usage_type: UsageType, additional_usage: float) -> Dict[str, Any]:
        """Test plan enforcement for usage limits."""
        try:
            # Check current usage
            current_usage = await self.usage_tracker._get_current_usage(tenant_id, usage_type)
            
            # Check usage limit
            limit_check = await self.usage_tracker.check_usage_limit(tenant_id, usage_type, additional_usage)
            
            # Determine if request should be allowed
            within_limit = limit_check.get('within_limit', True)
            
            # If over limit, return 429 status
            if not within_limit:
                return {
                    'allowed': False,
                    'status_code': 429,
                    'message': 'Usage limit exceeded',
                    'current_usage': current_usage,
                    'usage_limit': limit_check.get('usage_limit'),
                    'remaining_usage': limit_check.get('remaining_usage'),
                    'projected_usage': limit_check.get('projected_usage')
                }
            
            return {
                'allowed': True,
                'status_code': 200,
                'message': 'Usage within limits',
                'current_usage': current_usage,
                'usage_limit': limit_check.get('usage_limit'),
                'remaining_usage': limit_check.get('remaining_usage'),
                'projected_usage': limit_check.get('projected_usage')
            }

        except Exception as e:
            logger.error("Failed to test plan enforcement", error=str(e))
            return {'error': str(e)}

    def _validate_webhook_data(self, webhook_data: Dict[str, Any]) -> bool:
        """Validate webhook data."""
        required_fields = ['event_type', 'tenant_id', 'data']
        
        for field in required_fields:
            if field not in webhook_data:
                return False
        
        # Validate event type
        try:
            WebhookEventType(webhook_data['event_type'])
        except ValueError:
            return False
        
        return True

    async def _process_event(self, event: WebhookEvent) -> bool:
        """Process webhook event based on type."""
        try:
            if event.event_type == WebhookEventType.USAGE_RECORDED:
                return await self._process_usage_recorded(event)
            elif event.event_type == WebhookEventType.TOOL_CALLED:
                return await self._process_tool_called(event)
            elif event.event_type == WebhookEventType.WS_CONNECTION:
                return await self._process_ws_connection(event)
            elif event.event_type == WebhookEventType.STORAGE_USED:
                return await self._process_storage_used(event)
            elif event.event_type == WebhookEventType.API_CALL:
                return await self._process_api_call(event)
            elif event.event_type == WebhookEventType.BILLING_PERIOD_END:
                return await self._process_billing_period_end(event)
            else:
                logger.warning("Unknown event type", event_type=event.event_type.value)
                return False

        except Exception as e:
            logger.error("Failed to process event", error=str(e), event_id=event.event_id)
            return False

    async def _process_usage_recorded(self, event: WebhookEvent) -> bool:
        """Process usage recorded event."""
        try:
            data = event.data
            usage_type = UsageType(data.get('usage_type'))
            quantity = float(data.get('quantity', 0))
            
            # Record usage
            success = await self.usage_tracker.record_usage(
                tenant_id=event.tenant_id,
                usage_type=usage_type,
                quantity=quantity,
                metadata=data.get('metadata', {})
            )
            
            return success

        except Exception as e:
            logger.error("Failed to process usage recorded event", error=str(e))
            return False

    async def _process_tool_called(self, event: WebhookEvent) -> bool:
        """Process tool called event."""
        try:
            data = event.data
            tool_name = data.get('tool_name')
            execution_time = float(data.get('execution_time', 0))
            
            # Record tool call usage
            success = await self.usage_tracker.record_usage(
                tenant_id=event.tenant_id,
                usage_type=UsageType.TOOL_CALLS,
                quantity=1.0,
                metadata={
                    'tool_name': tool_name,
                    'execution_time': execution_time
                }
            )
            
            return success

        except Exception as e:
            logger.error("Failed to process tool called event", error=str(e))
            return False

    async def _process_ws_connection(self, event: WebhookEvent) -> bool:
        """Process WebSocket connection event."""
        try:
            data = event.data
            connection_duration = float(data.get('connection_duration', 0))
            minutes = connection_duration / 60.0
            
            # Record WebSocket minutes usage
            success = await self.usage_tracker.record_usage(
                tenant_id=event.tenant_id,
                usage_type=UsageType.WS_MINUTES,
                quantity=minutes,
                metadata={
                    'connection_duration': connection_duration
                }
            )
            
            return success

        except Exception as e:
            logger.error("Failed to process WebSocket connection event", error=str(e))
            return False

    async def _process_storage_used(self, event: WebhookEvent) -> bool:
        """Process storage used event."""
        try:
            data = event.data
            storage_mb = float(data.get('storage_mb', 0))
            
            # Record storage usage
            success = await self.usage_tracker.record_usage(
                tenant_id=event.tenant_id,
                usage_type=UsageType.STORAGE_MB,
                quantity=storage_mb,
                metadata={
                    'storage_type': data.get('storage_type', 'unknown')
                }
            )
            
            return success

        except Exception as e:
            logger.error("Failed to process storage used event", error=str(e))
            return False

    async def _process_api_call(self, event: WebhookEvent) -> bool:
        """Process API call event."""
        try:
            data = event.data
            endpoint = data.get('endpoint')
            response_time = float(data.get('response_time', 0))
            
            # Record API call usage
            success = await self.usage_tracker.record_usage(
                tenant_id=event.tenant_id,
                usage_type=UsageType.API_CALLS,
                quantity=1.0,
                metadata={
                    'endpoint': endpoint,
                    'response_time': response_time
                }
            )
            
            return success

        except Exception as e:
            logger.error("Failed to process API call event", error=str(e))
            return False

    async def _process_billing_period_end(self, event: WebhookEvent) -> bool:
        """Process billing period end event."""
        try:
            data = event.data
            period_start = float(data.get('period_start'))
            period_end = float(data.get('period_end'))
            
            # Generate invoice
            invoice_id = await self.billing_engine.generate_invoice(
                tenant_id=event.tenant_id,
                billing_period_start=period_start,
                billing_period_end=period_end
            )
            
            logger.info(
                "Invoice generated for billing period end",
                tenant_id=event.tenant_id,
                invoice_id=invoice_id,
                period_start=period_start,
                period_end=period_end
            )
            
            return True

        except Exception as e:
            logger.error("Failed to process billing period end event", error=str(e))
            return False

    async def _update_counters_from_event(self, counters: Dict[str, UsageCounter], event: WebhookEvent) -> None:
        """Update counters from webhook event."""
        try:
            if event.event_type == WebhookEventType.USAGE_RECORDED:
                usage_type = UsageType(event.data.get('usage_type'))
                quantity = float(event.data.get('quantity', 0))
                
                if usage_type.value in counters:
                    counters[usage_type.value].total_usage += quantity
                    counters[usage_type.value].count += 1
                    counters[usage_type.value].last_updated = event.timestamp
            
            elif event.event_type == WebhookEventType.TOOL_CALLED:
                if UsageType.TOOL_CALLS.value in counters:
                    counters[UsageType.TOOL_CALLS.value].total_usage += 1.0
                    counters[UsageType.TOOL_CALLS.value].count += 1
                    counters[UsageType.TOOL_CALLS.value].last_updated = event.timestamp
            
            elif event.event_type == WebhookEventType.WS_CONNECTION:
                connection_duration = float(event.data.get('connection_duration', 0))
                minutes = connection_duration / 60.0
                
                if UsageType.WS_MINUTES.value in counters:
                    counters[UsageType.WS_MINUTES.value].total_usage += minutes
                    counters[UsageType.WS_MINUTES.value].count += 1
                    counters[UsageType.WS_MINUTES.value].last_updated = event.timestamp
            
            elif event.event_type == WebhookEventType.STORAGE_USED:
                storage_mb = float(event.data.get('storage_mb', 0))
                
                if UsageType.STORAGE_MB.value in counters:
                    counters[UsageType.STORAGE_MB.value].total_usage += storage_mb
                    counters[UsageType.STORAGE_MB.value].count += 1
                    counters[UsageType.STORAGE_MB.value].last_updated = event.timestamp
            
            elif event.event_type == WebhookEventType.API_CALL:
                if UsageType.API_CALLS.value in counters:
                    counters[UsageType.API_CALLS.value].total_usage += 1.0
                    counters[UsageType.API_CALLS.value].count += 1
                    counters[UsageType.API_CALLS.value].last_updated = event.timestamp

        except Exception as e:
            logger.error("Failed to update counters from event", error=str(e))

    async def _calculate_total_cost(self, counters: Dict[str, UsageCounter]) -> float:
        """Calculate total cost from counters."""
        total_cost = 0.0
        
        for counter in counters.values():
            cost = await self._calculate_cost_for_usage_type(counter.usage_type, counter.total_usage)
            total_cost += cost
        
        return total_cost

    async def _calculate_cost_for_usage_type(self, usage_type: UsageType, quantity: float) -> float:
        """Calculate cost for specific usage type."""
        try:
            # Get pricing rate from usage tracker
            pricing_rate = self.usage_tracker.pricing_rates.get(usage_type.value)
            if not pricing_rate:
                return 0.0
            
            return quantity * pricing_rate['rate']

        except Exception as e:
            logger.error("Failed to calculate cost for usage type", error=str(e))
            return 0.0

    async def _store_webhook_event(self, event: WebhookEvent) -> None:
        """Store webhook event in Redis."""
        try:
            event_key = f"webhook_event:{event.tenant_id}:{event.event_id}"
            
            event_data = {
                'event_id': event.event_id,
                'event_type': event.event_type.value,
                'tenant_id': event.tenant_id,
                'timestamp': event.timestamp,
                'data': json.dumps(event.data),
                'metadata': json.dumps(event.metadata or {})
            }
            
            await self.redis.hset(event_key, mapping=event_data)
            await self.redis.expire(event_key, 86400 * 30)  # 30 days TTL

        except Exception as e:
            logger.error("Failed to store webhook event", error=str(e))

    async def _get_webhook_events(self, tenant_id: str, period_start: float, period_end: float) -> List[WebhookEvent]:
        """Get webhook events for a tenant and period."""
        try:
            pattern = f"webhook_event:{tenant_id}:*"
            keys = await self.redis.keys(pattern)
            
            events = []
            for key in keys:
                try:
                    event_data = await self.redis.hgetall(key)
                    if event_data:
                        timestamp = float(event_data['timestamp'])
                        if period_start <= timestamp <= period_end:
                            event = WebhookEvent(
                                event_id=event_data['event_id'],
                                event_type=WebhookEventType(event_data['event_type']),
                                tenant_id=event_data['tenant_id'],
                                timestamp=timestamp,
                                data=json.loads(event_data['data']),
                                metadata=json.loads(event_data['metadata'])
                            )
                            events.append(event)
                except Exception as e:
                    logger.error("Failed to parse webhook event", error=str(e), key=key)
            
            # Sort by timestamp
            events.sort(key=lambda x: x.timestamp)
            
            return events

        except Exception as e:
            logger.error("Failed to get webhook events", error=str(e))
            return []

    async def _store_aggregated_usage(self, aggregated_usage: AggregatedUsage) -> None:
        """Store aggregated usage in Redis."""
        try:
            usage_key = f"aggregated_usage:{aggregated_usage.tenant_id}:{int(aggregated_usage.period_start)}:{int(aggregated_usage.period_end)}"
            
            usage_data = {
                'tenant_id': aggregated_usage.tenant_id,
                'period_start': aggregated_usage.period_start,
                'period_end': aggregated_usage.period_end,
                'counters': json.dumps({k: asdict(v) for k, v in aggregated_usage.counters.items()}),
                'total_cost': aggregated_usage.total_cost,
                'last_aggregated': aggregated_usage.last_aggregated
            }
            
            await self.redis.hset(usage_key, mapping=usage_data)
            await self.redis.expire(usage_key, 86400 * 365)  # 1 year TTL

        except Exception as e:
            logger.error("Failed to store aggregated usage", error=str(e))

    async def _get_aggregated_usage(self, tenant_id: str, period_start: float, period_end: float) -> Optional[AggregatedUsage]:
        """Get aggregated usage from Redis."""
        try:
            usage_key = f"aggregated_usage:{tenant_id}:{int(period_start)}:{int(period_end)}"
            usage_data = await self.redis.hgetall(usage_key)
            
            if not usage_data:
                return None
            
            # Parse counters
            counters_data = json.loads(usage_data['counters'])
            counters = {}
            for k, v in counters_data.items():
                counters[k] = UsageCounter(**v)
            
            return AggregatedUsage(
                tenant_id=usage_data['tenant_id'],
                period_start=float(usage_data['period_start']),
                period_end=float(usage_data['period_end']),
                counters=counters,
                total_cost=float(usage_data['total_cost']),
                last_aggregated=float(usage_data['last_aggregated'])
            )

        except Exception as e:
            logger.error("Failed to get aggregated usage", error=str(e))
            return None

    async def _store_invoice_preview(self, preview: Dict[str, Any]) -> None:
        """Store invoice preview in Redis."""
        try:
            preview_key = f"invoice_preview:{preview['tenant_id']}:{preview['preview_id']}"
            
            preview_data = {
                'tenant_id': preview['tenant_id'],
                'billing_period_start': preview['billing_period_start'],
                'billing_period_end': preview['billing_period_end'],
                'items': json.dumps(preview['items']),
                'subtotal': preview['subtotal'],
                'tax_rate': preview['tax_rate'],
                'tax_amount': preview['tax_amount'],
                'total_amount': preview['total_amount'],
                'generated_at': preview['generated_at'],
                'preview_id': preview['preview_id']
            }
            
            await self.redis.hset(preview_key, mapping=preview_data)
            await self.redis.expire(preview_key, 86400 * 7)  # 7 days TTL

        except Exception as e:
            logger.error("Failed to store invoice preview", error=str(e))

    async def _background_aggregation(self) -> None:
        """Background task for periodic aggregation."""
        while True:
            try:
                await asyncio.sleep(self.aggregation_interval)
                
                # Get all tenants with recent webhook events
                pattern = "webhook_event:*:*"
                keys = await self.redis.keys(pattern)
                
                # Group by tenant
                tenants = set()
                for key in keys:
                    parts = key.decode().split(':')
                    if len(parts) >= 3:
                        tenants.add(parts[2])
                
                # Aggregate for each tenant
                current_time = time.time()
                period_start = current_time - (86400 * 30)  # Last 30 days
                period_end = current_time
                
                for tenant_id in tenants:
                    try:
                        await self.aggregate_usage_counters(tenant_id, period_start, period_end)
                    except Exception as e:
                        logger.error("Failed to aggregate for tenant", error=str(e), tenant_id=tenant_id)

            except Exception as e:
                logger.error("Background aggregation failed", error=str(e))
                await asyncio.sleep(self.retry_delay)
