"""Bulkhead pattern implementation for resilient tool adapters."""

import asyncio
from typing import Callable, Any, Optional, Dict
from dataclasses import dataclass
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class BulkheadStrategy(Enum):
    """Bulkhead strategies."""
    SEMAPHORE = "semaphore"      # Limit concurrent executions
    THREAD_POOL = "thread_pool"  # Isolate in separate thread pool
    PROCESS_POOL = "process_pool"  # Isolate in separate process pool


@dataclass
class BulkheadConfig:
    """Configuration for bulkhead."""
    max_concurrent: int = 10
    max_queue_size: int = 100
    strategy: BulkheadStrategy = BulkheadStrategy.SEMAPHORE
    timeout: float = 30.0


class Bulkhead:
    """Bulkhead pattern implementation."""
    
    def __init__(self, name: str, config: BulkheadConfig = None):
        self.name = name
        self.config = config or BulkheadConfig()
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent)
        self._queue = asyncio.Queue(maxsize=self.config.max_queue_size)
        self._active_tasks = 0
        self._rejected_count = 0
        self._completed_count = 0
        self._failed_count = 0
        self._lock = asyncio.Lock()
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with bulkhead protection."""
        # Check if we can accept the task
        if not await self._can_accept_task():
            self._rejected_count += 1
            raise BulkheadRejectedError(f"Bulkhead {self.name} is full")
        
        # Acquire semaphore
        try:
            await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self.config.timeout
            )
        except asyncio.TimeoutError:
            self._rejected_count += 1
            raise BulkheadTimeoutError(f"Bulkhead {self.name} timeout waiting for semaphore")
        
        try:
            async with self._lock:
                self._active_tasks += 1
            
            # Execute the function
            result = await func(*args, **kwargs)
            
            async with self._lock:
                self._completed_count += 1
            
            return result
            
        except Exception as e:
            async with self._lock:
                self._failed_count += 1
            raise
            
        finally:
            # Release semaphore
            self._semaphore.release()
            
            async with self._lock:
                self._active_tasks -= 1
    
    async def _can_accept_task(self) -> bool:
        """Check if bulkhead can accept a new task."""
        async with self._lock:
            return self._active_tasks < self.config.max_concurrent
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bulkhead statistics."""
        return {
            "name": self.name,
            "active_tasks": self._active_tasks,
            "max_concurrent": self.config.max_concurrent,
            "rejected_count": self._rejected_count,
            "completed_count": self._completed_count,
            "failed_count": self._failed_count,
            "utilization": self._active_tasks / self.config.max_concurrent if self.config.max_concurrent > 0 else 0
        }
    
    def reset_stats(self):
        """Reset statistics."""
        async with self._lock:
            self._rejected_count = 0
            self._completed_count = 0
            self._failed_count = 0


class BulkheadRejectedError(Exception):
    """Bulkhead rejected the request."""
    pass


class BulkheadTimeoutError(Exception):
    """Bulkhead timeout error."""
    pass
