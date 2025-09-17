"""Event producer for publishing events."""

import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import structlog

from .event_bus import EventBus
from .event_types import Event, EventType, EventMetadata

logger = structlog.get_logger(__name__)


@dataclass
class ProducerConfig:
    """Configuration for event producer."""

    batch_size: int = 100
    batch_timeout: float = 1.0  # seconds
    retry_attempts: int = 3
    retry_delay: float = 1.0
    enable_batching: bool = True


class EventProducer:
    """Event producer with batching and retry support."""

    def __init__(self, event_bus: EventBus, config: ProducerConfig = None):
        self.event_bus = event_bus
        self.config = config or ProducerConfig()
        self._batch: List[Event] = []
        self._batch_lock = asyncio.Lock()
        self._batch_task: Optional[asyncio.Task] = None
        self._stats = {
            "events_published": 0,
            "events_failed": 0,
            "batches_sent": 0,
            "retries": 0,
        }

    async def start(self):
        """Start the producer."""
        if self.config.enable_batching:
            self._batch_task = asyncio.create_task(self._batch_processor())
        logger.info("Event producer started")

    async def stop(self):
        """Stop the producer."""
        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass

        # Flush remaining events
        await self._flush_batch()
        logger.info("Event producer stopped")

    async def publish(
        self,
        event_type: EventType,
        payload: Dict[str, Any],
        metadata: Optional[EventMetadata] = None,
        subject: Optional[str] = None,
    ) -> bool:
        """Publish an event."""
        try:
            if not metadata:
                metadata = EventMetadata(event_type=event_type)

            event = Event(payload=payload, metadata=metadata)

            if self.config.enable_batching:
                return await self._add_to_batch(event, subject)
            else:
                return await self._publish_single(event, subject)

        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            self._stats["events_failed"] += 1
            return False

    async def _add_to_batch(self, event: Event, subject: Optional[str] = None) -> bool:
        """Add event to batch."""
        async with self._batch_lock:
            self._batch.append((event, subject))

            # Check if batch is full
            if len(self._batch) >= self.config.batch_size:
                await self._flush_batch()
                return True

            return True

    async def _flush_batch(self):
        """Flush the current batch."""
        async with self._batch_lock:
            if not self._batch:
                return

            batch = self._batch.copy()
            self._batch.clear()

        # Publish batch
        success_count = 0
        for event, subject in batch:
            if await self._publish_single(event, subject):
                success_count += 1

        self._stats["batches_sent"] += 1
        logger.debug(
            f"Flushed batch of {len(batch)} events, {success_count} successful"
        )

    async def _publish_single(
        self, event: Event, subject: Optional[str] = None
    ) -> bool:
        """Publish a single event with retry."""
        for attempt in range(self.config.retry_attempts):
            try:
                success = await self.event_bus.publish(event, subject)
                if success:
                    self._stats["events_published"] += 1
                    return True
                else:
                    if attempt < self.config.retry_attempts - 1:
                        await asyncio.sleep(self.config.retry_delay * (2**attempt))
                        self._stats["retries"] += 1

            except Exception as e:
                logger.warning(f"Publish attempt {attempt + 1} failed: {e}")
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay * (2**attempt))
                    self._stats["retries"] += 1

        self._stats["events_failed"] += 1
        return False

    async def _batch_processor(self):
        """Process batches on timeout."""
        while True:
            try:
                await asyncio.sleep(self.config.batch_timeout)
                await self._flush_batch()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Batch processor error: {e}")

    # Convenience methods for common event types

    async def publish_agent_run_started(
        self, run_id: str, tenant_id: str, agent_name: str, **kwargs
    ):
        """Publish agent run started event."""
        payload = {
            "run_id": run_id,
            "tenant_id": tenant_id,
            "agent_name": agent_name,
            **kwargs,
        }
        metadata = EventMetadata(
            event_type=EventType.AGENT_RUN_STARTED,
            tenant_id=tenant_id,
            correlation_id=run_id,
        )
        return await self.publish(EventType.AGENT_RUN_STARTED, payload, metadata)

    async def publish_agent_run_completed(
        self, run_id: str, tenant_id: str, result: Dict[str, Any], **kwargs
    ):
        """Publish agent run completed event."""
        payload = {"run_id": run_id, "tenant_id": tenant_id, "result": result, **kwargs}
        metadata = EventMetadata(
            event_type=EventType.AGENT_RUN_COMPLETED,
            tenant_id=tenant_id,
            correlation_id=run_id,
        )
        return await self.publish(EventType.AGENT_RUN_COMPLETED, payload, metadata)

    async def publish_router_decision(
        self, request_id: str, tenant_id: str, decision: Dict[str, Any], **kwargs
    ):
        """Publish router decision event."""
        payload = {
            "request_id": request_id,
            "tenant_id": tenant_id,
            "decision": decision,
            **kwargs,
        }
        metadata = EventMetadata(
            event_type=EventType.ROUTER_DECISION_MADE,
            tenant_id=tenant_id,
            correlation_id=request_id,
        )
        return await self.publish(EventType.ROUTER_DECISION_MADE, payload, metadata)

    async def publish_workflow_event(
        self,
        event_type: EventType,
        workflow_id: str,
        tenant_id: str,
        payload: Dict[str, Any],
    ):
        """Publish workflow event."""
        metadata = EventMetadata(
            event_type=event_type, tenant_id=tenant_id, correlation_id=workflow_id
        )
        return await self.publish(event_type, payload, metadata)

    async def publish_system_alert(
        self, alert_type: str, message: str, severity: str = "warning", **kwargs
    ):
        """Publish system alert event."""
        payload = {
            "alert_type": alert_type,
            "message": message,
            "severity": severity,
            **kwargs,
        }
        metadata = EventMetadata(event_type=EventType.SYSTEM_ALERT, source="system")
        return await self.publish(EventType.SYSTEM_ALERT, payload, metadata)

    def get_stats(self) -> Dict[str, Any]:
        """Get producer statistics."""
        return self._stats.copy()

    def reset_stats(self):
        """Reset statistics."""
        self._stats = {
            "events_published": 0,
            "events_failed": 0,
            "batches_sent": 0,
            "retries": 0,
        }
