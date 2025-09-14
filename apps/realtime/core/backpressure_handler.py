"""Backpressure handler for WebSocket connections with Redis session storage."""

import asyncio
import json
import time
import uuid
from typing import Dict, List, Optional, Any, Deque
from collections import deque
from fastapi import WebSocket
import structlog
import redis.asyncio as redis

logger = structlog.get_logger(__name__)


class BackpressureHandler:
    """Handles backpressure for WebSocket connections with Redis session storage."""

    def __init__(
        self,
        connection_manager,
        redis_client: redis.Redis,
        max_queue_size: int = 1000,
        drop_policy: str = "intermediate",
        session_ttl: int = 3600,
    ):
        self.connection_manager = connection_manager
        self.redis = redis_client
        self.max_queue_size = max_queue_size
        self.drop_policy = drop_policy  # "intermediate", "oldest", "newest"
        self.session_ttl = session_ttl  # Session TTL in seconds

        # Per-connection message queues (in-memory for active connections)
        self.message_queues: Dict[str, Deque[Dict[str, Any]]] = {}

        # Statistics
        self.stats = {
            "messages_sent": 0,
            "messages_dropped": 0,
            "queue_overflows": 0,
            "backpressure_events": 0,
            "active_connections": 0,
            "ws_send_errors": 0,
        }

        # Cleanup task will be started when needed
        self._cleanup_task = None

    async def start_cleanup_task(self) -> None:
        """Start the cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_queues())

    async def send_message(
        self,
        websocket: WebSocket,
        tenant_id: str,
        user_id: Optional[str],
        session_id: str,
        message: Dict[str, Any],
    ) -> bool:
        """Send message with backpressure handling and Redis session storage."""
        try:
            # Check if connection is still active
            if not await self._is_connection_active(websocket):
                logger.warning("Connection not active", session_id=session_id)
                # Store message in Redis for later delivery
                await self._store_message_in_redis(session_id, message, tenant_id)
                return False

            # Add message to queue
            await self._add_to_queue(session_id, message)

            # Process queue
            await self._process_queue(session_id, websocket)

            return True

        except Exception as e:
            logger.error(
                "Failed to send message with backpressure",
                error=str(e),
                session_id=session_id,
            )
            # Store message in Redis for later delivery
            await self._store_message_in_redis(session_id, message, tenant_id)
            return False

    async def _add_to_queue(self, session_id: str, message: Dict[str, Any]) -> None:
        """Add message to connection queue."""
        if session_id not in self.message_queues:
            self.message_queues[session_id] = deque()

        queue = self.message_queues[session_id]

        # Check queue size
        if len(queue) >= self.max_queue_size:
            self.stats["queue_overflows"] += 1
            self.stats["backpressure_events"] += 1

            # Apply drop policy
            if self.drop_policy == "intermediate":
                # Drop intermediate messages, keep first and last
                if len(queue) > 1:
                    # Remove middle messages
                    middle_count = len(queue) // 2
                    for _ in range(middle_count):
                        queue.popleft()
                        self.stats["messages_dropped"] += 1

                    logger.warning(
                        "Dropped intermediate messages due to backpressure",
                        session_id=session_id,
                        dropped_count=middle_count,
                    )

            elif self.drop_policy == "oldest":
                # Drop oldest messages
                while len(queue) >= self.max_queue_size:
                    queue.popleft()
                    self.stats["messages_dropped"] += 1

                logger.warning(
                    "Dropped oldest messages due to backpressure", session_id=session_id
                )

            elif self.drop_policy == "newest":
                # Drop newest messages (don't add this one)
                self.stats["messages_dropped"] += 1
                logger.warning(
                    "Dropped newest message due to backpressure", session_id=session_id
                )
                return

        # Add message to queue
        queue.append(message)

    async def _store_message_in_redis(
        self, session_id: str, message: Dict[str, Any], tenant_id: str
    ) -> None:
        """Store message in Redis for later delivery."""
        try:
            message_data = {
                "message": message,
                "timestamp": time.time(),
                "tenant_id": tenant_id,
                "session_id": session_id,
            }

            # Store in Redis list
            redis_key = f"ws_queue:{session_id}"
            await self.redis.lpush(redis_key, json.dumps(message_data))
            await self.redis.expire(redis_key, self.session_ttl)

            # Update statistics
            self.stats["backpressure_events"] += 1

        except Exception as e:
            logger.error(
                "Failed to store message in Redis", error=str(e), session_id=session_id
            )

    async def _retrieve_messages_from_redis(
        self, session_id: str
    ) -> List[Dict[str, Any]]:
        """Retrieve messages from Redis for a session."""
        try:
            redis_key = f"ws_queue:{session_id}"
            messages = await self.redis.lrange(redis_key, 0, -1)

            retrieved_messages = []
            for message_json in messages:
                try:
                    message_data = json.loads(message_json)
                    retrieved_messages.append(message_data["message"])
                except (json.JSONDecodeError, KeyError):
                    continue

            # Clear Redis queue after retrieval
            await self.redis.delete(redis_key)

            return retrieved_messages

        except Exception as e:
            logger.error(
                "Failed to retrieve messages from Redis",
                error=str(e),
                session_id=session_id,
            )
            return []

    async def _process_queue(self, session_id: str, websocket: WebSocket) -> None:
        """Process message queue for a connection with Redis fallback."""
        # First, retrieve any messages from Redis
        redis_messages = await self._retrieve_messages_from_redis(session_id)
        if redis_messages:
            # Add Redis messages to the front of the queue
            if session_id not in self.message_queues:
                self.message_queues[session_id] = deque()

            # Add Redis messages in reverse order (they were stored with lpush)
            for message in reversed(redis_messages):
                self.message_queues[session_id].appendleft(message)

        if session_id not in self.message_queues:
            return

        queue = self.message_queues[session_id]

        # Process messages in queue with improved backpressure handling
        messages_processed = 0
        max_batch_size = 10  # Process up to 10 messages at once

        while queue and messages_processed < max_batch_size:
            try:
                # Check if connection is still active
                if not await self._is_connection_active(websocket):
                    logger.warning(
                        "Connection not active during queue processing",
                        session_id=session_id,
                    )
                    # Store remaining messages in Redis
                    await self._store_remaining_messages_in_redis(session_id, queue)
                    break

                # Get next message
                message = queue.popleft()

                # Check if this is a final message (should always be delivered)
                is_final = message.get("type") == "final" or message.get("final", False)

                # Send message
                try:
                    await websocket.send_text(json.dumps(message))
                    self.stats["messages_sent"] += 1
                    messages_processed += 1

                    # Small delay to prevent overwhelming the connection
                    await asyncio.sleep(0.001)

                except Exception as send_error:
                    self.stats["ws_send_errors"] += 1
                    logger.warning(
                        "Failed to send message to WebSocket",
                        error=str(send_error),
                        session_id=session_id,
                        message_type=message.get("type", "unknown"),
                    )

                    # If it's a final message, store it in Redis for later delivery
                    if is_final:
                        await self._store_message_in_redis(
                            session_id, message, message.get("tenant_id", "unknown")
                        )

                    break

            except Exception as e:
                logger.error(
                    "Failed to process message from queue",
                    error=str(e),
                    session_id=session_id,
                )
                break

    async def _store_remaining_messages_in_redis(
        self, session_id: str, queue: Deque[Dict[str, Any]]
    ) -> None:
        """Store remaining messages in Redis when connection is lost."""
        try:
            while queue:
                message = queue.popleft()
                await self._store_message_in_redis(
                    session_id, message, message.get("tenant_id", "unknown")
                )
        except Exception as e:
            logger.error(
                "Failed to store remaining messages in Redis",
                error=str(e),
                session_id=session_id,
            )

    async def _is_connection_active(self, websocket: WebSocket) -> bool:
        """Check if WebSocket connection is still active."""
        try:
            # Try to send a ping to check connection
            await websocket.send_text(json.dumps({"type": "ping"}))
            return True
        except Exception:
            return False

    async def get_queue_size(self, session_id: str) -> int:
        """Get queue size for a session."""
        if session_id in self.message_queues:
            return len(self.message_queues[session_id])
        return 0

    async def clear_queue(self, session_id: str) -> int:
        """Clear message queue for a session."""
        if session_id in self.message_queues:
            queue = self.message_queues[session_id]
            cleared_count = len(queue)
            queue.clear()
            logger.info(
                "Cleared message queue", session_id=session_id, count=cleared_count
            )
            return cleared_count
        return 0

    async def get_stats(self) -> Dict[str, Any]:
        """Get backpressure statistics."""
        total_queued = sum(len(queue) for queue in self.message_queues.values())

        # Get Redis queue statistics
        redis_queues = await self._get_redis_queue_stats()

        return {
            "ws_active_connections": len(self.message_queues),
            "ws_backpressure_drops": self.stats["messages_dropped"],
            "ws_send_errors": self.stats["ws_send_errors"],
            "total_queued_messages": total_queued,
            "active_queues": len(self.message_queues),
            "messages_sent": self.stats["messages_sent"],
            "messages_dropped": self.stats["messages_dropped"],
            "queue_overflows": self.stats["queue_overflows"],
            "backpressure_events": self.stats["backpressure_events"],
            "redis_queues": redis_queues,
            "drop_policy": self.drop_policy,
            "max_queue_size": self.max_queue_size,
        }

    async def _get_redis_queue_stats(self) -> Dict[str, Any]:
        """Get Redis queue statistics."""
        try:
            # Get all Redis queue keys
            pattern = "ws_queue:*"
            keys = await self.redis.keys(pattern)

            total_redis_messages = 0
            for key in keys:
                length = await self.redis.llen(key)
                total_redis_messages += length

            return {
                "total_redis_queues": len(keys),
                "total_redis_messages": total_redis_messages,
            }
        except Exception as e:
            logger.error("Failed to get Redis queue stats", error=str(e))
            return {"total_redis_queues": 0, "total_redis_messages": 0}

    async def _cleanup_queues(self) -> None:
        """Periodically clean up empty queues."""
        while True:
            try:
                await asyncio.sleep(60)  # Cleanup every minute

                # Remove empty queues
                empty_queues = [
                    session_id
                    for session_id, queue in self.message_queues.items()
                    if not queue
                ]

                for session_id in empty_queues:
                    del self.message_queues[session_id]

                if empty_queues:
                    logger.info("Cleaned up empty queues", count=len(empty_queues))

            except Exception as e:
                logger.error("Error during queue cleanup", error=str(e))

    async def shutdown(self) -> None:
        """Shutdown backpressure handler."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("Backpressure handler shutdown")


class BackpressureMetrics:
    """Metrics collector for backpressure events."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def record_backpressure_event(
        self, tenant_id: str, session_id: str, event_type: str, details: Dict[str, Any]
    ) -> None:
        """Record backpressure event for metrics."""
        event = {
            "tenant_id": tenant_id,
            "session_id": session_id,
            "event_type": event_type,
            "details": details,
            "timestamp": time.time(),
        }

        # Store in Redis for metrics collection
        await self.redis.lpush("backpressure_events", json.dumps(event))
        await self.redis.ltrim("backpressure_events", 0, 9999)  # Keep last 10k events

    async def get_backpressure_metrics(
        self, tenant_id: Optional[str] = None, time_window: int = 3600
    ) -> Dict[str, Any]:
        """Get backpressure metrics for a time window."""
        cutoff_time = time.time() - time_window

        # Get events from Redis
        events = await self.redis.lrange("backpressure_events", 0, -1)

        filtered_events = []
        for event_json in events:
            try:
                event = json.loads(event_json)
                if event["timestamp"] >= cutoff_time:
                    if tenant_id is None or event["tenant_id"] == tenant_id:
                        filtered_events.append(event)
            except (json.JSONDecodeError, KeyError):
                continue

        # Calculate metrics
        total_events = len(filtered_events)
        event_types = {}
        tenant_events = {}

        for event in filtered_events:
            event_type = event["event_type"]
            event_tenant = event["tenant_id"]

            event_types[event_type] = event_types.get(event_type, 0) + 1
            tenant_events[event_tenant] = tenant_events.get(event_tenant, 0) + 1

        return {
            "total_events": total_events,
            "time_window_seconds": time_window,
            "event_types": event_types,
            "tenant_events": tenant_events,
            "events_per_minute": total_events / (time_window / 60),
        }
