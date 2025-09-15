"""Event consumer for processing events."""

import asyncio
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
import structlog

from .event_bus import EventBus, EventBusConfig
from .event_types import Event, EventType
from .dlq_handler import DLQHandler, DLQConfig

logger = structlog.get_logger(__name__)


@dataclass
class ConsumerConfig:
    """Configuration for event consumer."""

    max_concurrent_events: int = 10
    event_timeout: float = 30.0
    retry_attempts: int = 3
    retry_delay: float = 1.0
    enable_dlq: bool = True
    dlq_config: DLQConfig = None

    def __post_init__(self):
        if self.dlq_config is None:
            self.dlq_config = DLQConfig()


class EventConsumer:
    """Event consumer with concurrency control and DLQ support."""

    def __init__(self, event_bus: EventBus, config: ConsumerConfig = None):
        self.event_bus = event_bus
        self.config = config or ConsumerConfig()
        self.handlers: Dict[str, Callable[[Event], None]] = {}
        self.subscriptions: Dict[str, str] = {}  # subject -> subscription_id
        self.semaphore = asyncio.Semaphore(self.config.max_concurrent_events)
        self.dlq_handler = (
            DLQHandler(self.config.dlq_config) if self.config.enable_dlq else None
        )
        self._stats = {
            "events_processed": 0,
            "events_failed": 0,
            "events_retried": 0,
            "events_dlq": 0,
            "concurrent_events": 0,
        }

    async def start(self):
        """Start the consumer."""
        if self.dlq_handler:
            await self.dlq_handler.start()
        logger.info("Event consumer started")

    async def stop(self):
        """Stop the consumer."""
        # Unsubscribe from all topics
        for subscription_id in self.subscriptions.values():
            await self.event_bus.unsubscribe(subscription_id)

        if self.dlq_handler:
            await self.dlq_handler.stop()

        logger.info("Event consumer stopped")

    def register_handler(self, event_type: EventType, handler: Callable[[Event], None]):
        """Register an event handler."""
        subject = self._get_subject_for_event_type(event_type)
        self.handlers[subject] = handler
        logger.info(f"Registered handler for {event_type.value}")

    async def subscribe_to_event_type(
        self, event_type: EventType, queue_group: Optional[str] = None
    ):
        """Subscribe to a specific event type."""
        subject = self._get_subject_for_event_type(event_type)

        if subject in self.subscriptions:
            logger.warning(f"Already subscribed to {subject}")
            return

        subscription_id = await self.event_bus.subscribe(
            subject, self._handle_event, queue_group=queue_group
        )

        if subscription_id:
            self.subscriptions[subject] = subscription_id
            logger.info(f"Subscribed to {subject}")

    async def subscribe_to_subject(
        self, subject: str, queue_group: Optional[str] = None
    ):
        """Subscribe to a specific subject."""
        if subject in self.subscriptions:
            logger.warning(f"Already subscribed to {subject}")
            return

        subscription_id = await self.event_bus.subscribe(
            subject, self._handle_event, queue_group=queue_group
        )

        if subscription_id:
            self.subscriptions[subject] = subscription_id
            logger.info(f"Subscribed to {subject}")

    async def _handle_event(self, event: Event):
        """Handle incoming event."""
        async with self.semaphore:
            self._stats["concurrent_events"] = self.semaphore._value
            await self._process_event(event)

    async def _process_event(self, event: Event):
        """Process a single event with retry and DLQ support."""
        subject = self._get_subject_for_event_type(event.metadata.event_type)
        handler = self.handlers.get(subject)

        if not handler:
            logger.warning(
                f"No handler for event type {event.metadata.event_type.value}"
            )
            return

        for attempt in range(self.config.retry_attempts):
            try:
                # Execute handler with timeout
                await asyncio.wait_for(
                    handler(event), timeout=self.config.event_timeout
                )

                self._stats["events_processed"] += 1
                logger.debug(f"Processed event {event.metadata.event_id}")
                return

            except asyncio.TimeoutError:
                logger.warning(f"Event {event.metadata.event_id} processing timed out")
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay * (2**attempt))
                    self._stats["events_retried"] += 1
                else:
                    await self._send_to_dlq(event, "timeout")

            except Exception as e:
                logger.error(f"Event {event.metadata.event_id} processing failed: {e}")
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay * (2**attempt))
                    self._stats["events_retried"] += 1
                else:
                    await self._send_to_dlq(event, str(e))

    async def _send_to_dlq(self, event: Event, reason: str):
        """Send event to dead letter queue."""
        if self.dlq_handler:
            await self.dlq_handler.send_to_dlq(event, reason)
            self._stats["events_dlq"] += 1
            logger.warning(f"Event {event.metadata.event_id} sent to DLQ: {reason}")
        else:
            self._stats["events_failed"] += 1
            logger.error(
                f"Event {event.metadata.event_id} failed and no DLQ configured: {reason}"
            )

    def _get_subject_for_event_type(self, event_type: EventType) -> str:
        """Get subject for event type."""
        type_mapping = {
            EventType.AGENT_RUN_STARTED: "agent_events.run.started",
            EventType.AGENT_RUN_COMPLETED: "agent_events.run.completed",
            EventType.AGENT_RUN_FAILED: "agent_events.run.failed",
            EventType.AGENT_RUN_CANCELLED: "agent_events.run.cancelled",
            EventType.ROUTER_DECISION_MADE: "router_events.decision.made",
            EventType.ROUTER_DECISION_FAILED: "router_events.decision.failed",
            EventType.WORKFLOW_STARTED: "workflow_events.started",
            EventType.WORKFLOW_STEP_COMPLETED: "workflow_events.step.completed",
            EventType.WORKFLOW_COMPLETED: "workflow_events.completed",
            EventType.WORKFLOW_FAILED: "workflow_events.failed",
            EventType.TOOL_CALL_STARTED: "tool_events.call.started",
            EventType.TOOL_CALL_COMPLETED: "tool_events.call.completed",
            EventType.TOOL_CALL_FAILED: "tool_events.call.failed",
            EventType.SYSTEM_HEALTH_CHECK: "system_events.health.check",
            EventType.SYSTEM_METRICS_UPDATED: "system_events.metrics.updated",
            EventType.SYSTEM_ALERT: "system_events.alert",
            EventType.USER_REGISTERED: "user_events.registered",
            EventType.USER_SUBSCRIPTION_CHANGED: "user_events.subscription.changed",
            EventType.USER_ACTION: "user_events.action",
            EventType.CUSTOM: "custom_events.custom",
        }

        return type_mapping.get(event_type, "custom_events.unknown")

    def get_stats(self) -> Dict[str, Any]:
        """Get consumer statistics."""
        stats = self._stats.copy()
        stats["active_subscriptions"] = len(self.subscriptions)
        stats["registered_handlers"] = len(self.handlers)
        return stats

    def reset_stats(self):
        """Reset statistics."""
        self._stats = {
            "events_processed": 0,
            "events_failed": 0,
            "events_retried": 0,
            "events_dlq": 0,
            "concurrent_events": 0,
        }
