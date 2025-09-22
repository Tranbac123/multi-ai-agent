"""Dead Letter Queue (DLQ) handler for failed events."""

import asyncio
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
import structlog

from src.event_types import Event, EventType
from src.event_bus import EventBus

logger = structlog.get_logger(__name__)


@dataclass
class DLQConfig:
    """Configuration for DLQ handler."""

    dlq_subject: str = "dlq.events"
    max_retry_attempts: int = 3
    retry_delay: float = 300.0  # 5 minutes
    max_dlq_size: int = 10000
    retention_period: int = 7 * 24 * 60 * 60  # 7 days in seconds
    enable_auto_retry: bool = True
    retry_backoff_multiplier: float = 2.0


class DLQHandler:
    """Dead Letter Queue handler for failed events."""

    def __init__(self, config: DLQConfig = None):
        self.config = config or DLQConfig()
        self.event_bus: Optional[EventBus] = None
        self.dlq_events: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._retry_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._stats = {
            "events_received": 0,
            "events_retried": 0,
            "events_expired": 0,
            "events_processed": 0,
        }

    async def start(self):
        """Start the DLQ handler."""
        self._retry_task = asyncio.create_task(self._retry_processor())
        self._cleanup_task = asyncio.create_task(self._cleanup_processor())
        logger.info("DLQ handler started")

    async def stop(self):
        """Stop the DLQ handler."""
        if self._retry_task:
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("DLQ handler stopped")

    def set_event_bus(self, event_bus: EventBus):
        """Set the event bus for retrying events."""
        self.event_bus = event_bus

    async def send_to_dlq(self, event: Event, reason: str):
        """Send an event to the dead letter queue."""
        async with self._lock:
            # Check if DLQ is full
            if len(self.dlq_events) >= self.config.max_dlq_size:
                # Remove oldest event
                self.dlq_events.pop(0)

            dlq_entry = {
                "event": event.to_dict(),
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
                "retry_count": 0,
                "next_retry": datetime.utcnow().isoformat(),
            }

            self.dlq_events.append(dlq_entry)
            self._stats["events_received"] += 1

            logger.warning(f"Event {event.metadata.event_id} sent to DLQ: {reason}")

    async def _retry_processor(self):
        """Process DLQ events for retry."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._process_retries()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"DLQ retry processor error: {e}")

    async def _process_retries(self):
        """Process events that are ready for retry."""
        if not self.event_bus or not self.config.enable_auto_retry:
            return

        now = datetime.utcnow()
        events_to_retry = []

        async with self._lock:
            for i, dlq_entry in enumerate(self.dlq_events):
                next_retry = datetime.fromisoformat(dlq_entry["next_retry"])
                if (
                    now >= next_retry
                    and dlq_entry["retry_count"] < self.config.max_retry_attempts
                ):
                    events_to_retry.append((i, dlq_entry))

        # Retry events outside the lock
        for index, dlq_entry in events_to_retry:
            await self._retry_event(index, dlq_entry)

    async def _retry_event(self, index: int, dlq_entry: Dict[str, Any]):
        """Retry a single DLQ event."""
        try:
            event = Event.from_dict(dlq_entry["event"])

            # Try to republish the event
            success = await self.event_bus.publish(event)

            if success:
                # Remove from DLQ on success
                async with self._lock:
                    if index < len(self.dlq_events):
                        self.dlq_events.pop(index)
                self._stats["events_processed"] += 1
                logger.info(f"Event {event.metadata.event_id} retried successfully")
            else:
                # Update retry count and next retry time
                async with self._lock:
                    if index < len(self.dlq_events):
                        dlq_entry["retry_count"] += 1
                        delay = self.config.retry_delay * (
                            self.config.retry_backoff_multiplier
                            ** dlq_entry["retry_count"]
                        )
                        dlq_entry["next_retry"] = (
                            datetime.utcnow() + timedelta(seconds=delay)
                        ).isoformat()

                self._stats["events_retried"] += 1
                logger.warning(
                    f"Event {event.metadata.event_id} retry failed, will retry later"
                )

        except Exception as e:
            logger.error(f"Error retrying event: {e}")

    async def _cleanup_processor(self):
        """Clean up expired DLQ events."""
        while True:
            try:
                await asyncio.sleep(3600)  # Check every hour
                await self._cleanup_expired_events()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"DLQ cleanup processor error: {e}")

    async def _cleanup_expired_events(self):
        """Remove expired events from DLQ."""
        cutoff_time = datetime.utcnow() - timedelta(
            seconds=self.config.retention_period
        )

        async with self._lock:
            original_count = len(self.dlq_events)
            self.dlq_events = [
                entry
                for entry in self.dlq_events
                if datetime.fromisoformat(entry["timestamp"]) > cutoff_time
            ]
            removed_count = original_count - len(self.dlq_events)

            if removed_count > 0:
                self._stats["events_expired"] += removed_count
                logger.info(f"Cleaned up {removed_count} expired DLQ events")

    async def manual_retry(self, event_id: str) -> bool:
        """Manually retry a specific event."""
        if not self.event_bus:
            logger.error("No event bus configured for retry")
            return False

        async with self._lock:
            for i, dlq_entry in enumerate(self.dlq_events):
                event = Event.from_dict(dlq_entry["event"])
                if event.metadata.event_id == event_id:
                    await self._retry_event(i, dlq_entry)
                    return True

        logger.warning(f"Event {event_id} not found in DLQ")
        return False

    async def get_dlq_events(
        self, limit: int = 100, offset: int = 0, event_type: Optional[EventType] = None
    ) -> List[Dict[str, Any]]:
        """Get DLQ events with filtering."""
        async with self._lock:
            events = self.dlq_events[offset : offset + limit]

            if event_type:
                events = [
                    entry
                    for entry in events
                    if Event.from_dict(entry["event"]).metadata.event_type == event_type
                ]

            return events.copy()

    async def clear_dlq(self) -> int:
        """Clear all DLQ events."""
        async with self._lock:
            count = len(self.dlq_events)
            self.dlq_events.clear()
            logger.info(f"Cleared {count} events from DLQ")
            return count

    def get_stats(self) -> Dict[str, Any]:
        """Get DLQ statistics."""
        stats = self._stats.copy()
        stats["dlq_size"] = len(self.dlq_events)
        stats["config"] = {
            "max_dlq_size": self.config.max_dlq_size,
            "max_retry_attempts": self.config.max_retry_attempts,
            "retry_delay": self.config.retry_delay,
            "retention_period": self.config.retention_period,
            "auto_retry_enabled": self.config.enable_auto_retry,
        }
        return stats

    def reset_stats(self):
        """Reset statistics."""
        self._stats = {
            "events_received": 0,
            "events_retried": 0,
            "events_expired": 0,
            "events_processed": 0,
        }
