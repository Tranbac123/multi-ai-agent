"""Event store for persisting events."""

import asyncio
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
import structlog

from src.event_types import Event, EventType, EventMetadata

logger = structlog.get_logger(__name__)


@dataclass
class EventStoreConfig:
    """Configuration for event store."""

    max_events: int = 1000000
    retention_days: int = 30
    batch_size: int = 1000
    flush_interval: float = 5.0  # seconds
    enable_compression: bool = True
    enable_indexing: bool = True


class EventStore:
    """Event store for persisting and querying events."""

    def __init__(self, config: EventStoreConfig = None):
        self.config = config or EventStoreConfig()
        self.events: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._stats = {
            "events_stored": 0,
            "events_retrieved": 0,
            "events_deleted": 0,
            "storage_size_bytes": 0,
        }

    async def start(self):
        """Start the event store."""
        self._flush_task = asyncio.create_task(self._flush_processor())
        self._cleanup_task = asyncio.create_task(self._cleanup_processor())
        logger.info("Event store started")

    async def stop(self):
        """Stop the event store."""
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("Event store stopped")

    async def store_event(self, event: Event) -> bool:
        """Store an event."""
        try:
            event_data = {
                "event": event.to_dict(),
                "stored_at": datetime.utcnow().isoformat(),
                "size_bytes": len(event.to_json().encode()),
            }

            async with self._lock:
                self.events.append(event_data)
                self._stats["events_stored"] += 1
                self._stats["storage_size_bytes"] += event_data["size_bytes"]

                # Check if we need to flush
                if len(self.events) >= self.config.batch_size:
                    await self._flush_events()

            logger.debug(f"Stored event {event.metadata.event_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to store event {event.metadata.event_id}: {e}")
            return False

    async def get_event(self, event_id: str) -> Optional[Event]:
        """Get a specific event by ID."""
        try:
            async with self._lock:
                for event_data in self.events:
                    event = Event.from_dict(event_data["event"])
                    if event.metadata.event_id == event_id:
                        self._stats["events_retrieved"] += 1
                        return event

                return None

        except Exception as e:
            logger.error(f"Failed to get event {event_id}: {e}")
            return None

    async def get_events(
        self,
        event_type: Optional[EventType] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Event]:
        """Get events with filtering."""
        try:
            async with self._lock:
                filtered_events = []

                for event_data in self.events:
                    event = Event.from_dict(event_data["event"])
                    metadata = event.metadata

                    # Apply filters
                    if event_type and metadata.event_type != event_type:
                        continue
                    if tenant_id and metadata.tenant_id != tenant_id:
                        continue
                    if user_id and metadata.user_id != user_id:
                        continue
                    if start_time and metadata.timestamp < start_time:
                        continue
                    if end_time and metadata.timestamp > end_time:
                        continue

                    filtered_events.append(event)

                # Apply pagination
                events = filtered_events[offset : offset + limit]
                self._stats["events_retrieved"] += len(events)

                return events

        except Exception as e:
            logger.error(f"Failed to get events: {e}")
            return []

    async def get_events_by_correlation_id(self, correlation_id: str) -> List[Event]:
        """Get all events with a specific correlation ID."""
        try:
            async with self._lock:
                events = []

                for event_data in self.events:
                    event = Event.from_dict(event_data["event"])
                    if event.metadata.correlation_id == correlation_id:
                        events.append(event)

                self._stats["events_retrieved"] += len(events)
                return events

        except Exception as e:
            logger.error(
                f"Failed to get events by correlation ID {correlation_id}: {e}"
            )
            return []

    async def delete_event(self, event_id: str) -> bool:
        """Delete a specific event."""
        try:
            async with self._lock:
                for i, event_data in enumerate(self.events):
                    event = Event.from_dict(event_data["event"])
                    if event.metadata.event_id == event_id:
                        self.events.pop(i)
                        self._stats["events_deleted"] += 1
                        self._stats["storage_size_bytes"] -= event_data["size_bytes"]
                        logger.debug(f"Deleted event {event_id}")
                        return True

                return False

        except Exception as e:
            logger.error(f"Failed to delete event {event_id}: {e}")
            return False

    async def _flush_processor(self):
        """Process event flushing."""
        while True:
            try:
                await asyncio.sleep(self.config.flush_interval)
                await self._flush_events()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Event store flush processor error: {e}")

    async def _flush_events(self):
        """Flush events to persistent storage."""
        # This is a placeholder - in practice you would flush to a database
        # or other persistent storage
        async with self._lock:
            if self.events:
                logger.debug(f"Flushed {len(self.events)} events to storage")

    async def _cleanup_processor(self):
        """Process event cleanup."""
        while True:
            try:
                await asyncio.sleep(3600)  # Check every hour
                await self._cleanup_old_events()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Event store cleanup processor error: {e}")

    async def _cleanup_old_events(self):
        """Remove old events based on retention policy."""
        cutoff_time = datetime.utcnow() - timedelta(days=self.config.retention_days)

        async with self._lock:
            original_count = len(self.events)
            self.events = [
                event_data
                for event_data in self.events
                if datetime.fromisoformat(event_data["stored_at"]) > cutoff_time
            ]
            removed_count = original_count - len(self.events)

            if removed_count > 0:
                self._stats["events_deleted"] += removed_count
                logger.info(f"Cleaned up {removed_count} old events")

    async def get_event_statistics(
        self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get event statistics for a time period."""
        try:
            async with self._lock:
                events = []

                for event_data in self.events:
                    event = Event.from_dict(event_data["event"])
                    metadata = event.metadata

                    if start_time and metadata.timestamp < start_time:
                        continue
                    if end_time and metadata.timestamp > end_time:
                        continue

                    events.append(event)

                # Calculate statistics
                event_types = {}
                tenants = {}
                sources = {}

                for event in events:
                    # Count by event type
                    event_type = event.metadata.event_type.value
                    event_types[event_type] = event_types.get(event_type, 0) + 1

                    # Count by tenant
                    if event.metadata.tenant_id:
                        tenant_id = event.metadata.tenant_id
                        tenants[tenant_id] = tenants.get(tenant_id, 0) + 1

                    # Count by source
                    if event.metadata.source:
                        source = event.metadata.source
                        sources[source] = sources.get(source, 0) + 1

                return {
                    "total_events": len(events),
                    "event_types": event_types,
                    "tenants": tenants,
                    "sources": sources,
                    "time_range": {
                        "start": start_time.isoformat() if start_time else None,
                        "end": end_time.isoformat() if end_time else None,
                    },
                }

        except Exception as e:
            logger.error(f"Failed to get event statistics: {e}")
            return {}

    def get_stats(self) -> Dict[str, Any]:
        """Get event store statistics."""
        stats = self._stats.copy()
        stats["total_events"] = len(self.events)
        stats["config"] = {
            "max_events": self.config.max_events,
            "retention_days": self.config.retention_days,
            "batch_size": self.config.batch_size,
            "flush_interval": self.config.flush_interval,
        }
        return stats

    def reset_stats(self):
        """Reset statistics."""
        self._stats = {
            "events_stored": 0,
            "events_retrieved": 0,
            "events_deleted": 0,
            "storage_size_bytes": 0,
        }
