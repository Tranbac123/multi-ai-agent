"""NATS event bus with JetStream and DLQ handling."""

import asyncio
import json
import time
import uuid
from typing import Dict, List, Any, Optional, Callable, TypeVar
from enum import Enum
import structlog
import nats
from nats.js import JetStreamContext
from nats.js.api import StreamConfig, ConsumerConfig, DeliverPolicy

logger = structlog.get_logger(__name__)

T = TypeVar('T')


class EventType(Enum):
    """Event types for the system."""
    # Agent events
    AGENT_RUN_STARTED = "agent.run.started"
    AGENT_RUN_COMPLETED = "agent.run.completed"
    AGENT_RUN_FAILED = "agent.run.failed"
    
    # Router events
    ROUTER_DECISION = "router.decision"
    ROUTER_MISROUTE = "router.misroute"
    
    # Tool events
    TOOL_CALL_STARTED = "tool.call.started"
    TOOL_CALL_COMPLETED = "tool.call.completed"
    TOOL_CALL_FAILED = "tool.call.failed"
    
    # User events
    USER_MESSAGE = "user.message"
    USER_SESSION_STARTED = "user.session.started"
    USER_SESSION_ENDED = "user.session.ended"
    
    # System events
    SYSTEM_HEALTH_CHECK = "system.health.check"
    SYSTEM_ALERT = "system.alert"


class EventPriority(Enum):
    """Event priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class NATSEventBus:
    """NATS event bus with JetStream and DLQ support."""
    
    def __init__(
        self,
        nats_url: str = "nats://localhost:4222",
        stream_name: str = "aiaas_events",
        dlq_stream_name: str = "aiaas_dlq"
    ):
        self.nats_url = nats_url
        self.stream_name = stream_name
        self.dlq_stream_name = dlq_stream_name
        self.nc = None
        self.js = None
        self.subscribers = {}
        self.dlq_handlers = {}
    
    async def connect(self) -> None:
        """Connect to NATS server."""
        try:
            self.nc = await nats.connect(self.nats_url)
            self.js = self.nc.jetstream()
            
            # Create streams
            await self._create_streams()
            
            logger.info("Connected to NATS server", url=self.nats_url)
            
        except Exception as e:
            logger.error("Failed to connect to NATS", error=str(e))
            raise
    
    async def _create_streams(self) -> None:
        """Create JetStream streams."""
        try:
            # Create main event stream
            await self.js.add_stream(StreamConfig(
                name=self.stream_name,
                subjects=["events.*"],
                retention="workqueue",
                max_age=86400 * 7,  # 7 days
                max_msgs=1000000,
                max_bytes=1024 * 1024 * 1024,  # 1GB
                storage="file"
            ))
            
            # Create DLQ stream
            await self.js.add_stream(StreamConfig(
                name=self.dlq_stream_name,
                subjects=["dlq.*"],
                retention="limits",
                max_age=86400 * 30,  # 30 days
                max_msgs=100000,
                max_bytes=1024 * 1024 * 100,  # 100MB
                storage="file"
            ))
            
            logger.info("Created NATS streams", 
                       main_stream=self.stream_name,
                       dlq_stream=self.dlq_stream_name)
            
        except Exception as e:
            logger.error("Failed to create streams", error=str(e))
            raise
    
    async def publish_event(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        tenant_id: str,
        priority: EventPriority = EventPriority.NORMAL,
        correlation_id: Optional[str] = None
    ) -> str:
        """Publish an event to the bus."""
        try:
            event_id = str(uuid.uuid4())
            correlation_id = correlation_id or str(uuid.uuid4())
            
            event = {
                'event_id': event_id,
                'event_type': event_type.value,
                'tenant_id': tenant_id,
                'priority': priority.value,
                'correlation_id': correlation_id,
                'data': data,
                'timestamp': time.time(),
                'version': '1.0'
            }
            
            # Determine subject based on priority
            subject = f"events.{event_type.value}"
            if priority == EventPriority.CRITICAL:
                subject = f"events.critical.{event_type.value}"
            elif priority == EventPriority.HIGH:
                subject = f"events.high.{event_type.value}"
            
            # Publish to JetStream
            await self.js.publish(
                subject,
                json.dumps(event).encode(),
                headers={
                    'event_id': event_id,
                    'tenant_id': tenant_id,
                    'priority': str(priority.value),
                    'correlation_id': correlation_id
                }
            )
            
            logger.info(
                "Event published",
                event_id=event_id,
                event_type=event_type.value,
                tenant_id=tenant_id,
                priority=priority.value
            )
            
            return event_id
            
        except Exception as e:
            logger.error(
                "Failed to publish event",
                error=str(e),
                event_type=event_type.value,
                tenant_id=tenant_id
            )
            raise
    
    async def subscribe_to_events(
        self,
        event_types: List[EventType],
        handler: Callable[[Dict[str, Any]], None],
        tenant_id: Optional[str] = None,
        consumer_name: Optional[str] = None,
        durable: bool = True
    ) -> str:
        """Subscribe to specific event types."""
        try:
            if not consumer_name:
                consumer_name = f"consumer_{uuid.uuid4().hex[:8]}"
            
            # Create consumer configuration
            consumer_config = ConsumerConfig(
                durable_name=consumer_name if durable else None,
                deliver_policy=DeliverPolicy.ALL,
                ack_policy="explicit",
                max_deliver=3,  # Max retries before DLQ
                ack_wait=30,  # 30 seconds ack wait
                filter_subjects=[f"events.{et.value}" for et in event_types]
            )
            
            # Create consumer
            consumer = await self.js.add_consumer(
                self.stream_name,
                consumer_config
            )
            
            # Store subscriber info
            self.subscribers[consumer_name] = {
                'consumer': consumer,
                'handler': handler,
                'event_types': event_types,
                'tenant_id': tenant_id,
                'durable': durable
            }
            
            # Start message processing
            asyncio.create_task(self._process_messages(consumer_name))
            
            logger.info(
                "Subscribed to events",
                consumer_name=consumer_name,
                event_types=[et.value for et in event_types],
                tenant_id=tenant_id
            )
            
            return consumer_name
            
        except Exception as e:
            logger.error("Failed to subscribe to events", error=str(e))
            raise
    
    async def _process_messages(self, consumer_name: str) -> None:
        """Process messages for a consumer."""
        try:
            subscriber = self.subscribers[consumer_name]
            consumer = subscriber['consumer']
            handler = subscriber['handler']
            tenant_id = subscriber['tenant_id']
            
            async for msg in consumer.messages():
                try:
                    # Parse event
                    event = json.loads(msg.data.decode())
                    
                    # Check tenant filter
                    if tenant_id and event.get('tenant_id') != tenant_id:
                        await msg.ack()
                        continue
                    
                    # Process event
                    await handler(event)
                    
                    # Acknowledge message
                    await msg.ack()
                    
                except Exception as e:
                    logger.error(
                        "Failed to process message",
                        error=str(e),
                        consumer_name=consumer_name,
                        event_id=event.get('event_id')
                    )
                    
                    # Message will be retried or sent to DLQ
                    await msg.nak()
                    
        except Exception as e:
            logger.error(
                "Message processing error",
                error=str(e),
                consumer_name=consumer_name
            )
    
    async def setup_dlq_handler(
        self,
        event_type: EventType,
        handler: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Setup DLQ handler for specific event type."""
        try:
            dlq_consumer_name = f"dlq_{event_type.value}"
            
            # Create DLQ consumer
            dlq_consumer = await self.js.add_consumer(
                self.dlq_stream_name,
                ConsumerConfig(
                    durable_name=dlq_consumer_name,
                    deliver_policy=DeliverPolicy.ALL,
                    ack_policy="explicit",
                    filter_subjects=[f"dlq.{event_type.value}"]
                )
            )
            
            # Store DLQ handler
            self.dlq_handlers[event_type] = {
                'consumer': dlq_consumer,
                'handler': handler
            }
            
            # Start DLQ processing
            asyncio.create_task(self._process_dlq_messages(event_type))
            
            logger.info("DLQ handler setup", event_type=event_type.value)
            
        except Exception as e:
            logger.error("Failed to setup DLQ handler", error=str(e))
    
    async def _process_dlq_messages(self, event_type: EventType) -> None:
        """Process DLQ messages."""
        try:
            dlq_handler = self.dlq_handlers[event_type]
            consumer = dlq_handler['consumer']
            handler = dlq_handler['handler']
            
            async for msg in consumer.messages():
                try:
                    # Parse DLQ event
                    event = json.loads(msg.data.decode())
                    
                    # Process DLQ event
                    await handler(event)
                    
                    # Acknowledge message
                    await msg.ack()
                    
                except Exception as e:
                    logger.error(
                        "Failed to process DLQ message",
                        error=str(e),
                        event_type=event_type.value
                    )
                    
                    # DLQ messages are not retried
                    await msg.ack()
                    
        except Exception as e:
            logger.error(
                "DLQ processing error",
                error=str(e),
                event_type=event_type.value
            )
    
    async def get_stream_info(self) -> Dict[str, Any]:
        """Get stream information."""
        try:
            stream_info = await self.js.stream_info(self.stream_name)
            dlq_info = await self.js.stream_info(self.dlq_stream_name)
            
            return {
                'main_stream': {
                    'name': stream_info.config.name,
                    'subjects': stream_info.config.subjects,
                    'messages': stream_info.state.messages,
                    'bytes': stream_info.state.bytes,
                    'consumers': stream_info.state.consumers
                },
                'dlq_stream': {
                    'name': dlq_info.config.name,
                    'subjects': dlq_info.config.subjects,
                    'messages': dlq_info.state.messages,
                    'bytes': dlq_info.state.bytes,
                    'consumers': dlq_info.state.consumers
                }
            }
            
        except Exception as e:
            logger.error("Failed to get stream info", error=str(e))
            return {}
    
    async def get_consumer_info(self, consumer_name: str) -> Dict[str, Any]:
        """Get consumer information."""
        try:
            consumer_info = await self.js.consumer_info(
                self.stream_name,
                consumer_name
            )
            
            return {
                'name': consumer_info.name,
                'durable_name': consumer_info.config.durable_name,
                'deliver_policy': consumer_info.config.deliver_policy,
                'ack_policy': consumer_info.config.ack_policy,
                'max_deliver': consumer_info.config.max_deliver,
                'ack_wait': consumer_info.config.ack_wait,
                'num_pending': consumer_info.num_pending,
                'num_ack_pending': consumer_info.num_ack_pending,
                'num_redelivered': consumer_info.num_redelivered
            }
            
        except Exception as e:
            logger.error("Failed to get consumer info", error=str(e))
            return {}
    
    async def close(self) -> None:
        """Close NATS connection."""
        try:
            if self.nc:
                await self.nc.close()
                logger.info("NATS connection closed")
        except Exception as e:
            logger.error("Failed to close NATS connection", error=str(e))
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        try:
            if not self.nc or self.nc.is_closed:
                return {'status': 'unhealthy', 'error': 'Not connected'}
            
            # Check stream health
            stream_info = await self.get_stream_info()
            
            return {
                'status': 'healthy',
                'connected': True,
                'streams': stream_info,
                'subscribers_count': len(self.subscribers),
                'dlq_handlers_count': len(self.dlq_handlers)
            }
            
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return {'status': 'unhealthy', 'error': str(e)}
