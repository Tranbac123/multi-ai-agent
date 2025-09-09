"""NATS client with JetStream and DLQ support."""

import asyncio
import json
import time
from typing import Dict, Any, List, Optional, Callable
from uuid import UUID, uuid4
import structlog
import nats
from nats.js import api
from nats.js.errors import NotFoundError

logger = structlog.get_logger(__name__)


class NATSClient:
    """NATS client with JetStream and DLQ support."""
    
    def __init__(self, url: str = "nats://localhost:4222"):
        self.url = url
        self.nc: Optional[nats.NATS] = None
        self.js: Optional[api.JetStreamContext] = None
        self.subscriptions: Dict[str, nats.Subscription] = {}
        self.dlq_handlers: Dict[str, Callable] = {}
        
        # Standard event subjects
        self.subjects = {
            "agent_run": "agent.run",
            "tool_call": "tool.call",
            "ingest_doc": "ingest.doc",
            "usage_metered": "usage.metered",
            "router_decision": "router.decision",
            "websocket_message": "websocket.message",
            "billing_event": "billing.event",
            "audit_log": "audit.log"
        }
        
        # DLQ subjects
        self.dlq_subjects = {
            "agent_run": "agent.run.dlq",
            "tool_call": "tool.call.dlq",
            "ingest_doc": "ingest.doc.dlq",
            "usage_metered": "usage.metered.dlq",
            "router_decision": "router.decision.dlq",
            "websocket_message": "websocket.message.dlq",
            "billing_event": "billing.event.dlq",
            "audit_log": "audit.log.dlq"
        }
    
    async def connect(self):
        """Connect to NATS server."""
        try:
            self.nc = await nats.connect(self.url)
            self.js = self.nc.jetstream()
            
            # Create streams for each event type
            await self._create_streams()
            
            logger.info("Connected to NATS", url=self.url)
            
        except Exception as e:
            logger.error("Failed to connect to NATS", error=str(e))
            raise
    
    async def disconnect(self):
        """Disconnect from NATS server."""
        if self.nc:
            await self.nc.close()
            logger.info("Disconnected from NATS")
    
    async def _create_streams(self):
        """Create JetStream streams for event processing."""
        streams = [
            {
                "name": "agent_events",
                "subjects": ["agent.run.*"],
                "retention": api.RetentionPolicy.WORK_QUEUE,
                "max_age": 24 * 60 * 60,  # 24 hours
                "max_msgs": 1000000,
                "storage": api.StorageType.FILE
            },
            {
                "name": "tool_events",
                "subjects": ["tool.call.*"],
                "retention": api.RetentionPolicy.WORK_QUEUE,
                "max_age": 12 * 60 * 60,  # 12 hours
                "max_msgs": 500000,
                "storage": api.StorageType.FILE
            },
            {
                "name": "ingestion_events",
                "subjects": ["ingest.doc.*"],
                "retention": api.RetentionPolicy.WORK_QUEUE,
                "max_age": 7 * 24 * 60 * 60,  # 7 days
                "max_msgs": 100000,
                "storage": api.StorageType.FILE
            },
            {
                "name": "usage_events",
                "subjects": ["usage.metered.*"],
                "retention": api.RetentionPolicy.WORK_QUEUE,
                "max_age": 30 * 24 * 60 * 60,  # 30 days
                "max_msgs": 10000000,
                "storage": api.StorageType.FILE
            },
            {
                "name": "router_events",
                "subjects": ["router.decision.*"],
                "retention": api.RetentionPolicy.WORK_QUEUE,
                "max_age": 7 * 24 * 60 * 60,  # 7 days
                "max_msgs": 1000000,
                "storage": api.StorageType.FILE
            },
            {
                "name": "websocket_events",
                "subjects": ["websocket.message.*"],
                "retention": api.RetentionPolicy.WORK_QUEUE,
                "max_age": 1 * 60 * 60,  # 1 hour
                "max_msgs": 100000,
                "storage": api.StorageType.MEMORY
            },
            {
                "name": "billing_events",
                "subjects": ["billing.event.*"],
                "retention": api.RetentionPolicy.WORK_QUEUE,
                "max_age": 365 * 24 * 60 * 60,  # 1 year
                "max_msgs": 1000000,
                "storage": api.StorageType.FILE
            },
            {
                "name": "audit_events",
                "subjects": ["audit.log.*"],
                "retention": api.RetentionPolicy.WORK_QUEUE,
                "max_age": 365 * 24 * 60 * 60,  # 1 year
                "max_msgs": 10000000,
                "storage": api.StorageType.FILE
            }
        ]
        
        for stream_config in streams:
            try:
                await self.js.add_stream(stream_config)
                logger.info("Stream created", name=stream_config["name"])
            except Exception as e:
                logger.warning("Stream creation failed", 
                             name=stream_config["name"], 
                             error=str(e))
    
    async def publish_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        tenant_id: UUID,
        headers: Optional[Dict[str, str]] = None
    ) -> str:
        """Publish event to NATS."""
        if not self.js:
            raise RuntimeError("NATS client not connected")
        
        try:
            # Prepare event payload
            event_payload = {
                "event_id": str(uuid4()),
                "event_type": event_type,
                "tenant_id": str(tenant_id),
                "timestamp": time.time(),
                "data": data
            }
            
            # Determine subject
            base_subject = self.subjects.get(event_type, "unknown")
            subject = f"{base_subject}.{event_type}"
            
            # Prepare headers
            event_headers = {
                "tenant_id": str(tenant_id),
                "event_type": event_type,
                "timestamp": str(int(time.time())),
                "event_id": event_payload["event_id"]
            }
            
            if headers:
                event_headers.update(headers)
            
            # Publish event
            ack = await self.js.publish(
                subject,
                json.dumps(event_payload).encode(),
                headers=event_headers
            )
            
            logger.debug("Event published", 
                        event_type=event_type, 
                        tenant_id=tenant_id,
                        subject=subject)
            
            return ack.seq
            
        except Exception as e:
            logger.error("Failed to publish event", 
                        event_type=event_type, 
                        tenant_id=tenant_id, 
                        error=str(e))
            raise
    
    async def subscribe_to_events(
        self,
        event_type: str,
        handler: Callable,
        consumer_name: str = None,
        durable_name: str = None
    ):
        """Subscribe to events with DLQ handling."""
        if not self.js:
            raise RuntimeError("NATS client not connected")
        
        try:
            # Determine subject pattern
            base_subject = self.subjects.get(event_type, "unknown")
            subject_pattern = f"{base_subject}.*"
            
            # Create consumer configuration
            consumer_config = {
                "durable_name": durable_name or f"{event_type}_consumer",
                "deliver_policy": api.DeliverPolicy.ALL,
                "ack_policy": api.AckPolicy.EXPLICIT,
                "max_deliver": 3,  # Max retry attempts
                "ack_wait": 30,  # 30 seconds
                "replay_policy": api.ReplayPolicy.INSTANT
            }
            
            # Create consumer
            consumer = await self.js.add_consumer(
                stream_name=f"{event_type}_events",
                config=consumer_config
            )
            
            # Subscribe to events
            subscription = await self.js.pull_subscribe(
                subject_pattern,
                consumer_name or f"{event_type}_subscriber",
                consumer=consumer
            )
            
            self.subscriptions[event_type] = subscription
            
            # Start message processing
            asyncio.create_task(self._process_messages(subscription, handler, event_type))
            
            logger.info("Subscribed to events", 
                       event_type=event_type, 
                       subject_pattern=subject_pattern)
            
        except Exception as e:
            logger.error("Failed to subscribe to events", 
                        event_type=event_type, 
                        error=str(e))
            raise
    
    async def _process_messages(
        self,
        subscription: nats.Subscription,
        handler: Callable,
        event_type: str
    ):
        """Process messages from subscription."""
        while True:
            try:
                # Fetch messages
                messages = await subscription.fetch(batch=10, timeout=5.0)
                
                for msg in messages:
                    try:
                        # Parse message
                        event_data = json.loads(msg.data.decode())
                        
                        # Process event
                        await handler(event_data)
                        
                        # Acknowledge message
                        await msg.ack()
                        
                        logger.debug("Event processed", 
                                   event_type=event_type, 
                                   event_id=event_data.get("event_id"))
                        
                    except Exception as e:
                        logger.error("Failed to process event", 
                                   event_type=event_type, 
                                   error=str(e))
                        
                        # Check if we should send to DLQ
                        if msg.info.num_delivered >= 3:  # Max retry attempts
                            await self._send_to_dlq(event_type, msg, str(e))
                            await msg.ack()  # Acknowledge to remove from queue
                        else:
                            # NAK to retry
                            await msg.nak()
                
            except asyncio.TimeoutError:
                # No messages, continue
                continue
            except Exception as e:
                logger.error("Message processing error", 
                           event_type=event_type, 
                           error=str(e))
                await asyncio.sleep(1)  # Wait before retrying
    
    async def _send_to_dlq(
        self,
        event_type: str,
        message: nats.Msg,
        error: str
    ):
        """Send message to Dead Letter Queue."""
        try:
            # Get DLQ subject
            dlq_subject = self.dlq_subjects.get(event_type, f"{event_type}.dlq")
            
            # Prepare DLQ message
            dlq_data = {
                "original_subject": message.subject,
                "original_data": message.data.decode(),
                "original_headers": dict(message.headers) if message.headers else {},
                "error": error,
                "failed_at": time.time(),
                "retry_count": message.info.num_delivered
            }
            
            # Publish to DLQ
            await self.js.publish(
                dlq_subject,
                json.dumps(dlq_data).encode(),
                headers={
                    "original_subject": message.subject,
                    "error": error,
                    "failed_at": str(int(time.time()))
                }
            )
            
            logger.warning("Message sent to DLQ", 
                          event_type=event_type, 
                          dlq_subject=dlq_subject,
                          error=error)
            
        except Exception as e:
            logger.error("Failed to send message to DLQ", 
                        event_type=event_type, 
                        error=str(e))
    
    async def subscribe_to_dlq(
        self,
        event_type: str,
        handler: Callable
    ):
        """Subscribe to Dead Letter Queue."""
        if not self.js:
            raise RuntimeError("NATS client not connected")
        
        try:
            # Get DLQ subject
            dlq_subject = self.dlq_subjects.get(event_type, f"{event_type}.dlq")
            
            # Subscribe to DLQ
            subscription = await self.js.subscribe(
                dlq_subject,
                handler=self._handle_dlq_message,
                queue="dlq_processor"
            )
            
            self.dlq_handlers[event_type] = handler
            
            logger.info("Subscribed to DLQ", 
                       event_type=event_type, 
                       dlq_subject=dlq_subject)
            
        except Exception as e:
            logger.error("Failed to subscribe to DLQ", 
                        event_type=event_type, 
                        error=str(e))
            raise
    
    async def _handle_dlq_message(self, msg: nats.Msg):
        """Handle DLQ message."""
        try:
            # Parse DLQ message
            dlq_data = json.loads(msg.data.decode())
            event_type = dlq_data.get("original_subject", "").split(".")[0]
            
            # Get handler for event type
            handler = self.dlq_handlers.get(event_type)
            if handler:
                await handler(dlq_data)
            else:
                logger.warning("No DLQ handler found", event_type=event_type)
            
            # Acknowledge message
            await msg.ack()
            
        except Exception as e:
            logger.error("Failed to handle DLQ message", error=str(e))
    
    async def get_stream_info(self, stream_name: str) -> Optional[Dict[str, Any]]:
        """Get stream information."""
        if not self.js:
            return None
        
        try:
            stream_info = await self.js.stream_info(stream_name)
            return {
                "name": stream_info.config.name,
                "subjects": stream_info.config.subjects,
                "state": {
                    "messages": stream_info.state.messages,
                    "bytes": stream_info.state.bytes,
                    "first_seq": stream_info.state.first_seq,
                    "last_seq": stream_info.state.last_seq
                }
            }
        except NotFoundError:
            return None
        except Exception as e:
            logger.error("Failed to get stream info", 
                        stream_name=stream_name, 
                        error=str(e))
            return None
    
    async def get_consumer_info(self, stream_name: str, consumer_name: str) -> Optional[Dict[str, Any]]:
        """Get consumer information."""
        if not self.js:
            return None
        
        try:
            consumer_info = await self.js.consumer_info(stream_name, consumer_name)
            return {
                "name": consumer_info.name,
                "stream_name": consumer_info.stream_name,
                "config": {
                    "durable_name": consumer_info.config.durable_name,
                    "deliver_policy": consumer_info.config.deliver_policy,
                    "ack_policy": consumer_info.config.ack_policy,
                    "max_deliver": consumer_info.config.max_deliver,
                    "ack_wait": consumer_info.config.ack_wait
                },
                "state": {
                    "delivered": consumer_info.delivered,
                    "ack_floor": consumer_info.ack_floor,
                    "num_ack_pending": consumer_info.num_ack_pending,
                    "num_redelivered": consumer_info.num_redelivered
                }
            }
        except NotFoundError:
            return None
        except Exception as e:
            logger.error("Failed to get consumer info", 
                        stream_name=stream_name, 
                        consumer_name=consumer_name, 
                        error=str(e))
            return None
