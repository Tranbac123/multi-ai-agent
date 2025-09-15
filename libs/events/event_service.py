"""Event service for managing events and DLQ."""

import asyncio
import json
import time
from typing import Dict, Any, List, Optional, Callable
from uuid import UUID
import structlog

from .event_bus import event_bus, publish_event
from .event_types import EventType, EVENT_MODELS
from .event_handlers import create_event_handler
from .dlq_processor import process_dlq_message

logger = structlog.get_logger(__name__)


class EventService:
    """Event service for managing events and DLQ."""

    def __init__(self, tenant_id: UUID):
        self.tenant_id = tenant_id
        self.is_running = False
        self.event_handlers: Dict[EventType, List[Callable]] = {}
        self.dlq_handlers: Dict[EventType, Callable] = {}

    async def start(self) -> None:
        """Start event service."""
        if self.is_running:
            logger.warning("Event service already running")
            return

        try:
            # Connect to event bus
            await event_bus.connect()

            # Register event models
            for event_type, model in EVENT_MODELS.items():
                event_bus.register_event_model(event_type.value, model)

            # Subscribe to all event types
            for event_type in EventType:
                await self._subscribe_to_events(event_type)
                await self._subscribe_to_dlq(event_type)

            self.is_running = True
            logger.info("Event service started", tenant_id=self.tenant_id)

        except Exception as e:
            logger.error(
                "Failed to start event service", error=str(e), tenant_id=self.tenant_id
            )
            raise

    async def stop(self) -> None:
        """Stop event service."""
        if not self.is_running:
            logger.warning("Event service not running")
            return

        try:
            # Disconnect from event bus
            await event_bus.disconnect()

            self.is_running = False
            logger.info("Event service stopped", tenant_id=self.tenant_id)

        except Exception as e:
            logger.error(
                "Failed to stop event service", error=str(e), tenant_id=self.tenant_id
            )
            raise

    async def _subscribe_to_events(self, event_type: EventType) -> None:
        """Subscribe to events for event type."""
        try:
            # Create event handler
            handler = await create_event_handler(event_type, self.tenant_id)

            # Register handler
            event_bus.register_handler(event_type.value, handler.handle)

            # Subscribe to events
            await event_bus.subscribe_to_events(
                event_type=event_type.value,
                consumer_name=f"{event_type.value}_consumer_{self.tenant_id}",
                durable_name=f"{event_type.value}_durable_{self.tenant_id}",
            )

            logger.info(
                "Subscribed to events",
                event_type=event_type.value,
                tenant_id=self.tenant_id,
            )

        except Exception as e:
            logger.error(
                "Failed to subscribe to events",
                event_type=event_type.value,
                error=str(e),
            )

    async def _subscribe_to_dlq(self, event_type: EventType) -> None:
        """Subscribe to DLQ for event type."""
        try:
            # Subscribe to DLQ
            await event_bus.subscribe_to_dlq(
                event_type=event_type.value, handler=process_dlq_message
            )

            logger.info(
                "Subscribed to DLQ",
                event_type=event_type.value,
                tenant_id=self.tenant_id,
            )

        except Exception as e:
            logger.error(
                "Failed to subscribe to DLQ", event_type=event_type.value, error=str(e)
            )

    async def publish_agent_run_event(
        self,
        run_id: str,
        agent_id: str,
        user_id: Optional[UUID] = None,
        session_id: Optional[str] = None,
        input_text: str = "",
        output_text: Optional[str] = None,
        status: str = "started",
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        duration_ms: Optional[int] = None,
        tokens_used: Optional[int] = None,
        cost_usd: Optional[float] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Publish agent run event."""
        from .event_types import create_agent_run_event

        event = create_agent_run_event(
            run_id=run_id,
            tenant_id=self.tenant_id,
            agent_id=agent_id,
            user_id=user_id,
            session_id=session_id,
            input_text=input_text,
            status=status,
            start_time=start_time,
            metadata=metadata,
        )

        # Update event with additional data
        if output_text is not None:
            event.output_text = output_text
        if end_time is not None:
            event.end_time = end_time
        if duration_ms is not None:
            event.duration_ms = duration_ms
        if tokens_used is not None:
            event.tokens_used = tokens_used
        if cost_usd is not None:
            event.cost_usd = cost_usd
        if error_message is not None:
            event.error_message = error_message

        return await publish_event(
            event_type=EventType.AGENT_RUN.value,
            data=event.dict(),
            tenant_id=self.tenant_id,
        )

    async def publish_tool_call_event(
        self,
        call_id: str,
        run_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Optional[Dict[str, Any]] = None,
        status: str = "started",
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        duration_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Publish tool call event."""
        from .event_types import create_tool_call_event

        event = create_tool_call_event(
            call_id=call_id,
            run_id=run_id,
            tenant_id=self.tenant_id,
            tool_name=tool_name,
            tool_input=tool_input,
            status=status,
            start_time=start_time,
            metadata=metadata,
        )

        # Update event with additional data
        if tool_output is not None:
            event.tool_output = tool_output
        if end_time is not None:
            event.end_time = end_time
        if duration_ms is not None:
            event.duration_ms = duration_ms
        if error_message is not None:
            event.error_message = error_message

        return await publish_event(
            event_type=EventType.TOOL_CALL.value,
            data=event.dict(),
            tenant_id=self.tenant_id,
        )

    async def publish_ingest_doc_event(
        self,
        doc_id: str,
        filename: str,
        content_type: str,
        file_size: int,
        user_id: Optional[UUID] = None,
        status: str = "started",
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        duration_ms: Optional[int] = None,
        chunks_created: Optional[int] = None,
        embeddings_generated: Optional[int] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Publish document ingestion event."""
        from .event_types import create_ingest_doc_event

        event = create_ingest_doc_event(
            doc_id=doc_id,
            tenant_id=self.tenant_id,
            filename=filename,
            content_type=content_type,
            file_size=file_size,
            user_id=user_id,
            status=status,
            start_time=start_time,
            metadata=metadata,
        )

        # Update event with additional data
        if end_time is not None:
            event.end_time = end_time
        if duration_ms is not None:
            event.duration_ms = duration_ms
        if chunks_created is not None:
            event.chunks_created = chunks_created
        if embeddings_generated is not None:
            event.embeddings_generated = embeddings_generated
        if error_message is not None:
            event.error_message = error_message

        return await publish_event(
            event_type=EventType.INGEST_DOC.value,
            data=event.dict(),
            tenant_id=self.tenant_id,
        )

    async def publish_usage_metered_event(
        self,
        usage_id: str,
        resource_type: str,
        resource_id: str,
        quantity: int,
        unit: str,
        user_id: Optional[UUID] = None,
        cost_usd: Optional[float] = None,
        timestamp: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Publish usage metering event."""
        from .event_types import create_usage_metered_event

        event = create_usage_metered_event(
            usage_id=usage_id,
            tenant_id=self.tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            quantity=quantity,
            unit=unit,
            user_id=user_id,
            cost_usd=cost_usd,
            timestamp=timestamp,
            metadata=metadata,
        )

        return await publish_event(
            event_type=EventType.USAGE_METERED.value,
            data=event.dict(),
            tenant_id=self.tenant_id,
        )

    async def publish_router_decision_event(
        self,
        decision_id: str,
        input_text: str,
        selected_agent: str,
        confidence: float,
        reasoning: str,
        user_id: Optional[UUID] = None,
        features: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Publish router decision event."""
        from .event_types import create_router_decision_event

        event = create_router_decision_event(
            decision_id=decision_id,
            tenant_id=self.tenant_id,
            input_text=input_text,
            selected_agent=selected_agent,
            confidence=confidence,
            reasoning=reasoning,
            user_id=user_id,
            features=features,
            timestamp=timestamp,
            metadata=metadata,
        )

        return await publish_event(
            event_type=EventType.ROUTER_DECISION.value,
            data=event.dict(),
            tenant_id=self.tenant_id,
        )

    async def publish_websocket_message_event(
        self,
        message_id: str,
        session_id: str,
        message_type: str,
        content: str,
        user_id: Optional[UUID] = None,
        timestamp: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Publish WebSocket message event."""
        from .event_types import create_websocket_message_event

        event = create_websocket_message_event(
            message_id=message_id,
            tenant_id=self.tenant_id,
            session_id=session_id,
            message_type=message_type,
            content=content,
            user_id=user_id,
            timestamp=timestamp,
            metadata=metadata,
        )

        return await publish_event(
            event_type=EventType.WEBSOCKET_MESSAGE.value,
            data=event.dict(),
            tenant_id=self.tenant_id,
        )

    async def publish_billing_event(
        self,
        billing_id: str,
        event_type: str,
        amount_usd: float,
        description: str,
        currency: str = "USD",
        timestamp: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Publish billing event."""
        from .event_types import create_billing_event

        event = create_billing_event(
            billing_id=billing_id,
            tenant_id=self.tenant_id,
            event_type=event_type,
            amount_usd=amount_usd,
            description=description,
            currency=currency,
            timestamp=timestamp,
            metadata=metadata,
        )

        return await publish_event(
            event_type=EventType.BILLING_EVENT.value,
            data=event.dict(),
            tenant_id=self.tenant_id,
        )

    async def publish_audit_log_event(
        self,
        log_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        user_id: Optional[UUID] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        timestamp: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Publish audit log event."""
        from .event_types import create_audit_log_event

        event = create_audit_log_event(
            log_id=log_id,
            tenant_id=self.tenant_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=timestamp,
            metadata=metadata,
        )

        return await publish_event(
            event_type=EventType.AUDIT_LOG.value,
            data=event.dict(),
            tenant_id=self.tenant_id,
        )

    async def get_event_stats(self) -> Dict[str, Any]:
        """Get event statistics."""
        try:
            # Get stream info
            streams_info = await event_bus.get_all_streams_info()

            # Get consumer info
            consumers_info = await event_bus.get_all_consumers_info()

            return {
                "tenant_id": str(self.tenant_id),
                "streams": streams_info,
                "consumers": consumers_info,
                "timestamp": time.time(),
            }

        except Exception as e:
            logger.error(
                "Failed to get event stats", error=str(e), tenant_id=self.tenant_id
            )
            return {
                "tenant_id": str(self.tenant_id),
                "error": str(e),
                "timestamp": time.time(),
            }

    async def health_check(self) -> Dict[str, Any]:
        """Health check for event service."""
        try:
            # Check if event bus is connected
            is_connected = event_bus.is_connected

            # Get basic stats
            stats = await self.get_event_stats()

            return {
                "tenant_id": str(self.tenant_id),
                "is_connected": is_connected,
                "is_running": self.is_running,
                "stats": stats,
                "timestamp": time.time(),
            }

        except Exception as e:
            logger.error("Health check failed", error=str(e), tenant_id=self.tenant_id)
            return {
                "tenant_id": str(self.tenant_id),
                "is_connected": False,
                "is_running": False,
                "error": str(e),
                "timestamp": time.time(),
            }


# Global event service instance
event_service = EventService(tenant_id=UUID("00000000-0000-0000-0000-000000000000"))


async def get_event_service(tenant_id: UUID) -> EventService:
    """Get event service for tenant."""
    if event_service.tenant_id != tenant_id:
        # Create new service for different tenant
        return EventService(tenant_id)
    return event_service
