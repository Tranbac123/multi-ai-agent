"""Backpressure handler for WebSocket message queuing."""

import asyncio
import json
import time
from typing import Dict, Any, Optional, List
from uuid import UUID
import structlog
import redis.asyncio as redis

logger = structlog.get_logger(__name__)


class BackpressureHandler:
    """Handles backpressure for WebSocket connections."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.max_queue_size = 100  # Maximum messages in queue
        self.slow_client_threshold = 50  # Consider client slow if queue > this
        self.drop_intermediate_threshold = 80  # Drop intermediate messages if queue > this
        self.queue_ttl = 300  # 5 minutes
    
    async def should_drop_message(
        self, 
        connection_id: str, 
        message_type: str
    ) -> bool:
        """Check if message should be dropped due to backpressure."""
        try:
            # Get current queue size
            queue_size = await self.get_queue_size(connection_id)
            
            # Always deliver final messages
            if message_type in ["final", "error", "complete"]:
                return False
            
            # Drop intermediate messages if queue is too large
            if queue_size > self.drop_intermediate_threshold:
                logger.warning("Dropping intermediate message due to backpressure",
                             connection_id=connection_id,
                             queue_size=queue_size,
                             message_type=message_type)
                return True
            
            return False
            
        except Exception as e:
            logger.error("Backpressure check failed", 
                        connection_id=connection_id, 
                        error=str(e))
            return False
    
    async def queue_message(
        self, 
        connection_id: str, 
        message: Dict[str, Any]
    ) -> bool:
        """Queue message for delivery with backpressure handling."""
        try:
            message_type = message.get("type", "unknown")
            
            # Check if message should be dropped
            if await self.should_drop_message(connection_id, message_type):
                await self.record_drop(connection_id, message_type)
                return False
            
            # Add message to queue
            message_data = {
                "message": message,
                "timestamp": time.time(),
                "retry_count": 0
            }
            
            await self.redis.lpush(
                f"ws_queue:{connection_id}",
                json.dumps(message_data)
            )
            await self.redis.expire(f"ws_queue:{connection_id}", self.queue_ttl)
            
            # Record queue metrics
            await self.record_queue_metrics(connection_id)
            
            return True
            
        except Exception as e:
            logger.error("Failed to queue message", 
                        connection_id=connection_id, 
                        error=str(e))
            return False
    
    async def get_queue_size(self, connection_id: str) -> int:
        """Get current queue size for connection."""
        try:
            return await self.redis.llen(f"ws_queue:{connection_id}")
        except Exception as e:
            logger.error("Failed to get queue size", 
                        connection_id=connection_id, 
                        error=str(e))
            return 0
    
    async def process_queue(self, connection_id: str) -> List[Dict[str, Any]]:
        """Process queued messages for connection."""
        try:
            messages = []
            queue_size = await self.get_queue_size(connection_id)
            
            if queue_size == 0:
                return messages
            
            # Process up to 10 messages at a time
            batch_size = min(10, queue_size)
            
            for _ in range(batch_size):
                message_data = await self.redis.rpop(f"ws_queue:{connection_id}")
                if not message_data:
                    break
                
                try:
                    message = json.loads(message_data)
                    messages.append(message["message"])
                except json.JSONDecodeError:
                    logger.warning("Invalid message in queue", 
                                 connection_id=connection_id)
                    continue
            
            return messages
            
        except Exception as e:
            logger.error("Failed to process queue", 
                        connection_id=connection_id, 
                        error=str(e))
            return []
    
    async def clear_queue(self, connection_id: str):
        """Clear message queue for connection."""
        try:
            await self.redis.delete(f"ws_queue:{connection_id}")
            logger.info("Queue cleared", connection_id=connection_id)
        except Exception as e:
            logger.error("Failed to clear queue", 
                        connection_id=connection_id, 
                        error=str(e))
    
    async def record_drop(self, connection_id: str, message_type: str):
        """Record dropped message for metrics."""
        try:
            await self.redis.incr(f"ws_drops:{connection_id}")
            await self.redis.expire(f"ws_drops:{connection_id}", 3600)  # 1 hour
            
            # Record global drops
            await self.redis.incr("ws_drops_total")
            await self.redis.incr(f"ws_drops_by_type:{message_type}")
            
        except Exception as e:
            logger.error("Failed to record drop", 
                        connection_id=connection_id, 
                        error=str(e))
    
    async def record_queue_metrics(self, connection_id: str):
        """Record queue metrics."""
        try:
            queue_size = await self.get_queue_size(connection_id)
            
            # Record queue size
            await self.redis.hset(
                f"ws_metrics:{connection_id}",
                mapping={
                    "queue_size": queue_size,
                    "last_updated": time.time()
                }
            )
            await self.redis.expire(f"ws_metrics:{connection_id}", 3600)
            
            # Record global metrics
            await self.redis.hset(
                "ws_metrics_global",
                mapping={
                    "total_queues": await self.redis.scard("ws_active_queues"),
                    "max_queue_size": max(
                        await self.redis.hget("ws_metrics_global", "max_queue_size") or 0,
                        queue_size
                    ),
                    "last_updated": time.time()
                }
            )
            
        except Exception as e:
            logger.error("Failed to record queue metrics", 
                        connection_id=connection_id, 
                        error=str(e))
    
    async def get_backpressure_metrics(self) -> Dict[str, Any]:
        """Get backpressure metrics."""
        try:
            # Get total drops
            total_drops = await self.redis.get("ws_drops_total") or 0
            total_drops = int(total_drops)
            
            # Get drops by type
            drop_types = {}
            for message_type in ["typing", "intermediate", "chunk", "progress"]:
                count = await self.redis.get(f"ws_drops_by_type:{message_type}") or 0
                drop_types[message_type] = int(count)
            
            # Get queue statistics
            active_queues = await self.redis.scard("ws_active_queues")
            max_queue_size = await self.redis.hget("ws_metrics_global", "max_queue_size") or 0
            max_queue_size = int(max_queue_size)
            
            return {
                "total_drops": total_drops,
                "drops_by_type": drop_types,
                "active_queues": active_queues,
                "max_queue_size": max_queue_size,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error("Failed to get backpressure metrics", error=str(e))
            return {}
    
    async def is_client_slow(self, connection_id: str) -> bool:
        """Check if client is considered slow."""
        try:
            queue_size = await self.get_queue_size(connection_id)
            return queue_size > self.slow_client_threshold
        except Exception as e:
            logger.error("Failed to check if client is slow", 
                        connection_id=connection_id, 
                        error=str(e))
            return False
