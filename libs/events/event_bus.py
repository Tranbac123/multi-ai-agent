"""Event bus for inter-service communication."""

import asyncio
import json
import time
from typing import Dict, Any, List, Optional, Callable, Type
from uuid import UUID
import structlog
from pydantic import BaseModel

from src.nats_client import NATSClient

logger = structlog.get_logger(__name__)


class Event(BaseModel):
    """Base event model."""

    event_id: str
    event_type: str
    tenant_id: UUID
    timestamp: float
    data: Dict[str, Any]
    headers: Optional[Dict[str, str]] = None


class EventBus:
    """Event bus for inter-service communication."""

    def __init__(self, nats_url: str = "nats://localhost:4222"):
        self.nats_client = NATSClient(nats_url)
        self.event_handlers: Dict[str, List[Callable]] = {}
        self.event_models: Dict[str, Type[BaseModel]] = {}
        self.is_connected = False

    async def connect(self):
        """Connect to event bus."""
        await self.nats_client.connect()
        self.is_connected = True
        logger.info("Event bus connected")

    async def disconnect(self):
        """Disconnect from event bus."""
        await self.nats_client.disconnect()
        self.is_connected = False
        logger.info("Event bus disconnected")

    def register_event_model(self, event_type: str, model: Type[BaseModel]):
        """Register event model for validation."""
        self.event_models[event_type] = model
        logger.info("Event model registered", event_type=event_type)

    def register_handler(self, event_type: str, handler: Callable):
        """Register event handler."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []

        self.event_handlers[event_type].append(handler)
        logger.info("Event handler registered", event_type=event_type)

    async def publish_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        tenant_id: UUID,
        headers: Optional[Dict[str, str]] = None,
    ) -> str:
        """Publish event to event bus."""
        if not self.is_connected:
            raise RuntimeError("Event bus not connected")

        try:
            # Validate event data if model is registered
            if event_type in self.event_models:
                model = self.event_models[event_type]
                model(**data)

            # Publish event
            seq = await self.nats_client.publish_event(
                event_type=event_type, data=data, tenant_id=tenant_id, headers=headers
            )

            logger.debug(
                "Event published", event_type=event_type, tenant_id=tenant_id, seq=seq
            )

            return seq

        except Exception as e:
            logger.error(
                "Failed to publish event",
                event_type=event_type,
                tenant_id=tenant_id,
                error=str(e),
            )
            raise

    async def subscribe_to_events(
        self, event_type: str, consumer_name: str = None, durable_name: str = None
    ):
        """Subscribe to events."""
        if not self.is_connected:
            raise RuntimeError("Event bus not connected")

        try:
            # Get handlers for event type
            handlers = self.event_handlers.get(event_type, [])
            if not handlers:
                logger.warning(
                    "No handlers registered for event type", event_type=event_type
                )
                return

            # Create combined handler
            async def combined_handler(event_data: Dict[str, Any]):
                for handler in handlers:
                    try:
                        await handler(event_data)
                    except Exception as e:
                        logger.error(
                            "Handler failed",
                            event_type=event_type,
                            handler=handler.__name__,
                            error=str(e),
                        )

            # Subscribe to events
            await self.nats_client.subscribe_to_events(
                event_type=event_type,
                handler=combined_handler,
                consumer_name=consumer_name,
                durable_name=durable_name,
            )

            logger.info("Subscribed to events", event_type=event_type)

        except Exception as e:
            logger.error(
                "Failed to subscribe to events", event_type=event_type, error=str(e)
            )
            raise

    async def subscribe_to_dlq(self, event_type: str, handler: Callable):
        """Subscribe to Dead Letter Queue."""
        if not self.is_connected:
            raise RuntimeError("Event bus not connected")

        try:
            await self.nats_client.subscribe_to_dlq(event_type, handler)
            logger.info("Subscribed to DLQ", event_type=event_type)

        except Exception as e:
            logger.error(
                "Failed to subscribe to DLQ", event_type=event_type, error=str(e)
            )
            raise

    async def get_stream_info(self, stream_name: str) -> Optional[Dict[str, Any]]:
        """Get stream information."""
        return await self.nats_client.get_stream_info(stream_name)

    async def get_consumer_info(
        self, stream_name: str, consumer_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get consumer information."""
        return await self.nats_client.get_consumer_info(stream_name, consumer_name)

    async def get_all_streams_info(self) -> Dict[str, Any]:
        """Get information for all streams."""
        streams = [
            "agent_events",
            "tool_events",
            "ingestion_events",
            "usage_events",
            "router_events",
            "websocket_events",
            "billing_events",
            "audit_events",
        ]

        info = {}
        for stream_name in streams:
            stream_info = await self.get_stream_info(stream_name)
            if stream_info:
                info[stream_name] = stream_info

        return info

    async def get_all_consumers_info(self) -> Dict[str, Any]:
        """Get information for all consumers."""
        consumers = [
            ("agent_events", "agent_run_consumer"),
            ("tool_events", "tool_call_consumer"),
            ("ingestion_events", "ingest_doc_consumer"),
            ("usage_events", "usage_metered_consumer"),
            ("router_events", "router_decision_consumer"),
            ("websocket_events", "websocket_message_consumer"),
            ("billing_events", "billing_event_consumer"),
            ("audit_events", "audit_log_consumer"),
        ]

        info = {}
        for stream_name, consumer_name in consumers:
            consumer_info = await self.get_consumer_info(stream_name, consumer_name)
            if consumer_info:
                info[f"{stream_name}.{consumer_name}"] = consumer_info

        return info


# Global event bus instance
event_bus = EventBus()


# Event decorators
def event_handler(event_type: str):
    """Decorator to register event handler."""

    def decorator(func: Callable):
        event_bus.register_handler(event_type, func)
        return func

    return decorator


def event_model(event_type: str):
    """Decorator to register event model."""

    def decorator(model: Type[BaseModel]):
        event_bus.register_event_model(event_type, model)
        return model

    return decorator


# Event publishing helper
async def publish_event(
    event_type: str,
    data: Dict[str, Any],
    tenant_id: UUID,
    headers: Optional[Dict[str, str]] = None,
) -> str:
    """Publish event using global event bus."""
    return await event_bus.publish_event(event_type, data, tenant_id, headers)
