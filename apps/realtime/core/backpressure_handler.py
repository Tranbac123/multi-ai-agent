"""Backpressure handler for WebSocket connections."""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Deque
from collections import deque
from fastapi import WebSocket
import structlog
import redis.asyncio as redis

logger = structlog.get_logger(__name__)


class BackpressureHandler:
    """Handles backpressure for WebSocket connections."""
    
    def __init__(
        self,
        connection_manager,
        max_queue_size: int = 1000,
        drop_policy: str = "intermediate"
    ):
        self.connection_manager = connection_manager
        self.max_queue_size = max_queue_size
        self.drop_policy = drop_policy  # "intermediate", "oldest", "newest"
        
        # Per-connection message queues
        self.message_queues: Dict[str, Deque[Dict[str, Any]]] = {}
        
        # Statistics
        self.stats = {
            "messages_sent": 0,
            "messages_dropped": 0,
            "queue_overflows": 0,
            "backpressure_events": 0
        }
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_queues())
    
    async def send_message(
        self,
        websocket: WebSocket,
        tenant_id: str,
        user_id: Optional[str],
        session_id: str,
        message: Dict[str, Any]
    ) -> bool:
        """Send message with backpressure handling."""
        try:
            # Check if connection is still active
            if not await self._is_connection_active(websocket):
                logger.warning("Connection not active", session_id=session_id)
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
                session_id=session_id
            )
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
                        dropped_count=middle_count
                    )
            
            elif self.drop_policy == "oldest":
                # Drop oldest messages
                while len(queue) >= self.max_queue_size:
                    queue.popleft()
                    self.stats["messages_dropped"] += 1
                
                logger.warning(
                    "Dropped oldest messages due to backpressure",
                    session_id=session_id
                )
            
            elif self.drop_policy == "newest":
                # Drop newest messages (don't add this one)
                self.stats["messages_dropped"] += 1
                logger.warning(
                    "Dropped newest message due to backpressure",
                    session_id=session_id
                )
                return
        
        # Add message to queue
        queue.append(message)
    
    async def _process_queue(self, session_id: str, websocket: WebSocket) -> None:
        """Process message queue for a connection."""
        if session_id not in self.message_queues:
            return
        
        queue = self.message_queues[session_id]
        
        # Process messages in queue
        while queue:
            try:
                # Check if connection is still active
                if not await self._is_connection_active(websocket):
                    logger.warning("Connection not active during queue processing", session_id=session_id)
                    break
                
                # Get next message
                message = queue.popleft()
                
                # Send message
                await websocket.send_text(json.dumps(message))
                self.stats["messages_sent"] += 1
                
                # Small delay to prevent overwhelming the connection
                await asyncio.sleep(0.001)
                
            except Exception as e:
                logger.error(
                    "Failed to process message from queue",
                    error=str(e),
                    session_id=session_id
                )
                break
    
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
            logger.info("Cleared message queue", session_id=session_id, count=cleared_count)
            return cleared_count
        return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get backpressure statistics."""
        total_queued = sum(len(queue) for queue in self.message_queues.values())
        
        return {
            "total_queued_messages": total_queued,
            "active_queues": len(self.message_queues),
            "messages_sent": self.stats["messages_sent"],
            "messages_dropped": self.stats["messages_dropped"],
            "queue_overflows": self.stats["queue_overflows"],
            "backpressure_events": self.stats["backpressure_events"],
            "drop_policy": self.drop_policy,
            "max_queue_size": self.max_queue_size
        }
    
    async def _cleanup_queues(self) -> None:
        """Periodically clean up empty queues."""
        while True:
            try:
                await asyncio.sleep(60)  # Cleanup every minute
                
                # Remove empty queues
                empty_queues = [
                    session_id for session_id, queue in self.message_queues.items()
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
        self,
        tenant_id: str,
        session_id: str,
        event_type: str,
        details: Dict[str, Any]
    ) -> None:
        """Record backpressure event for metrics."""
        event = {
            "tenant_id": tenant_id,
            "session_id": session_id,
            "event_type": event_type,
            "details": details,
            "timestamp": time.time()
        }
        
        # Store in Redis for metrics collection
        await self.redis.lpush(
            "backpressure_events",
            json.dumps(event)
        )
        await self.redis.ltrim("backpressure_events", 0, 9999)  # Keep last 10k events
    
    async def get_backpressure_metrics(
        self,
        tenant_id: Optional[str] = None,
        time_window: int = 3600
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
            "events_per_minute": total_events / (time_window / 60)
        }