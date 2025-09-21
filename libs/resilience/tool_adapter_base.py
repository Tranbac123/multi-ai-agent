"""
Tool Adapter Resilience Base Class

Provides comprehensive resilience patterns for all tool adapters:
- Retry with exponential backoff and jitter
- Circuit breaker with configurable thresholds
- Bulkhead isolation for resource protection
- Idempotency with write-ahead logging
- Compensation for side-effect rollback
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Awaitable, Union
from datetime import datetime, timedelta
import redis.asyncio as redis
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential, 
    retry_if_exception_type,
    before_sleep_log
)

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class BulkheadPool:
    """Bulkhead isolation pool."""
    
    def __init__(self, max_concurrent: int = 10, name: str = "default"):
        self.max_concurrent = max_concurrent
        self.name = name
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._current_usage = 0
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire a slot in the bulkhead."""
        await self._semaphore.acquire()
        async with self._lock:
            self._current_usage += 1
        return self
    
    async def release(self):
        """Release a slot in the bulkhead."""
        async with self._lock:
            self._current_usage -= 1
        self._semaphore.release()
    
    @property
    def current_usage(self) -> int:
        """Get current usage count."""
        return self._current_usage
    
    @property
    def available_slots(self) -> int:
        """Get available slots."""
        return self.max_concurrent - self._current_usage


@dataclass
class RetryConfig:
    """Retry configuration."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_multiplier: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple = (Exception,)


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    expected_exception: type = Exception
    failure_ratio: float = 0.5
    minimum_requests: int = 10


@dataclass
class BulkheadConfig:
    """Bulkhead configuration."""
    max_concurrent: int = 10
    max_queue_size: int = 100
    timeout: float = 30.0


@dataclass
class IdempotencyConfig:
    """Idempotency configuration."""
    key_ttl: int = 3600  # 1 hour
    redis_prefix: str = "idempotency"
    include_headers: bool = False
    include_body: bool = True


@dataclass
class WriteAheadLogEntry:
    """Write-ahead log entry."""
    id: str
    timestamp: datetime
    operation: str
    payload: Dict[str, Any]
    state: str = "pending"
    retry_count: int = 0
    last_attempt: Optional[datetime] = None
    error: Optional[str] = None


class CircuitBreaker:
    """Circuit breaker implementation."""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                else:
                    raise Exception("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise e
    
    async def _on_success(self):
        """Handle successful execution."""
        async with self._lock:
            self.success_count += 1
            if self.state == CircuitState.HALF_OPEN:
                if self.success_count >= self.config.minimum_requests:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    logger.info("Circuit breaker reset to CLOSED")
    
    async def _on_failure(self):
        """Handle failed execution."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.utcnow()
            
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                logger.warning("Circuit breaker opened from HALF_OPEN")
            elif self._should_open_circuit():
                self.state = CircuitState.OPEN
                logger.warning("Circuit breaker opened")
    
    def _should_open_circuit(self) -> bool:
        """Check if circuit should be opened."""
        total_requests = self.failure_count + self.success_count
        if total_requests < self.config.minimum_requests:
            return False
        
        failure_ratio = self.failure_count / total_requests
        return (self.failure_count >= self.config.failure_threshold or 
                failure_ratio >= self.config.failure_ratio)
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt reset."""
        if self.last_failure_time is None:
            return True
        
        time_since_failure = datetime.utcnow() - self.last_failure_time
        return time_since_failure.total_seconds() >= self.config.recovery_timeout


class IdempotencyManager:
    """Idempotency management with Redis backend."""
    
    def __init__(self, redis_client: redis.Redis, config: IdempotencyConfig):
        self.redis = redis_client
        self.config = config
    
    def generate_key(self, operation: str, payload: Dict[str, Any], 
                    headers: Optional[Dict[str, str]] = None) -> str:
        """Generate idempotency key."""
        key_data = {
            "operation": operation,
            "payload": payload
        }
        
        if self.config.include_headers and headers:
            key_data["headers"] = headers
        
        key_string = json.dumps(key_data, sort_keys=True)
        return f"{self.config.redis_prefix}:{hashlib.sha256(key_string.encode()).hexdigest()}"
    
    async def get_result(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached result for idempotency key."""
        try:
            result = await self.redis.get(key)
            if result:
                return json.loads(result)
        except Exception as e:
            logger.warning(f"Failed to get idempotency result: {e}")
        return None
    
    async def set_result(self, key: str, result: Dict[str, Any]):
        """Cache result for idempotency key."""
        try:
            await self.redis.setex(
                key, 
                self.config.key_ttl, 
                json.dumps(result)
            )
        except Exception as e:
            logger.warning(f"Failed to set idempotency result: {e}")
    
    async def is_duplicate(self, key: str) -> bool:
        """Check if request is duplicate."""
        return await self.redis.exists(key) > 0


class WriteAheadLogger:
    """Write-ahead logging for side effects."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def log_operation(self, entry: WriteAheadLogEntry):
        """Log operation to write-ahead log."""
        key = f"wal:{entry.id}"
        try:
            await self.redis.setex(
                key,
                86400,  # 24 hours
                json.dumps({
                    "id": entry.id,
                    "timestamp": entry.timestamp.isoformat(),
                    "operation": entry.operation,
                    "payload": entry.payload,
                    "state": entry.state,
                    "retry_count": entry.retry_count,
                    "last_attempt": entry.last_attempt.isoformat() if entry.last_attempt else None,
                    "error": entry.error
                })
            )
        except Exception as e:
            logger.error(f"Failed to log WAL entry: {e}")
    
    async def get_pending_operations(self) -> List[WriteAheadLogEntry]:
        """Get all pending operations from WAL."""
        try:
            keys = await self.redis.keys("wal:*")
            entries = []
            
            for key in keys:
                data = await self.redis.get(key)
                if data:
                    entry_data = json.loads(data)
                    if entry_data["state"] == "pending":
                        entries.append(WriteAheadLogEntry(
                            id=entry_data["id"],
                            timestamp=datetime.fromisoformat(entry_data["timestamp"]),
                            operation=entry_data["operation"],
                            payload=entry_data["payload"],
                            state=entry_data["state"],
                            retry_count=entry_data["retry_count"],
                            last_attempt=datetime.fromisoformat(entry_data["last_attempt"]) if entry_data["last_attempt"] else None,
                            error=entry_data["error"]
                        ))
            
            return entries
        except Exception as e:
            logger.error(f"Failed to get pending operations: {e}")
            return []
    
    async def mark_completed(self, entry_id: str):
        """Mark operation as completed."""
        key = f"wal:{entry_id}"
        try:
            data = await self.redis.get(key)
            if data:
                entry_data = json.loads(data)
                entry_data["state"] = "completed"
                await self.redis.setex(key, 86400, json.dumps(entry_data))
        except Exception as e:
            logger.error(f"Failed to mark operation completed: {e}")


class ResilientToolAdapter(ABC):
    """Base class for resilient tool adapters."""
    
    def __init__(
        self,
        name: str,
        redis_client: Optional[redis.Redis] = None,
        retry_config: Optional[RetryConfig] = None,
        circuit_config: Optional[CircuitBreakerConfig] = None,
        bulkhead_config: Optional[BulkheadConfig] = None,
        idempotency_config: Optional[IdempotencyConfig] = None
    ):
        self.name = name
        self.redis = redis_client
        self.retry_config = retry_config or RetryConfig()
        self.circuit_config = circuit_config or CircuitBreakerConfig()
        self.bulkhead_config = bulkhead_config or BulkheadConfig()
        self.idempotency_config = idempotency_config or IdempotencyConfig()
        
        # Initialize resilience components
        self.circuit_breaker = CircuitBreaker(self.circuit_config)
        self.bulkhead = BulkheadPool(
            max_concurrent=self.bulkhead_config.max_concurrent,
            name=f"{name}_bulkhead"
        )
        
        if self.redis:
            self.idempotency_manager = IdempotencyManager(self.redis, self.idempotency_config)
            self.wal = WriteAheadLogger(self.redis)
        else:
            self.idempotency_manager = None
            self.wal = None
        
        # Metrics
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "circuit_breaker_opens": 0,
            "bulkhead_rejections": 0,
            "idempotency_hits": 0,
            "retry_attempts": 0
        }
    
    @abstractmethod
    async def execute_operation(self, operation: str, payload: Dict[str, Any], 
                              headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Execute the actual tool operation."""
        pass
    
    @abstractmethod
    async def compensate(self, operation: str, payload: Dict[str, Any], 
                        result: Dict[str, Any]) -> bool:
        """Compensate for a completed operation (rollback side effects)."""
        pass
    
    async def execute(
        self,
        operation: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute operation with full resilience patterns."""
        self.metrics["total_requests"] += 1
        
        # Generate idempotency key if not provided
        if idempotency_key is None and self.idempotency_manager:
            idempotency_key = self.idempotency_manager.generate_key(operation, payload, headers)
        
        # Check idempotency
        if self.idempotency_manager and idempotency_key:
            cached_result = await self.idempotency_manager.get_result(idempotency_key)
            if cached_result:
                self.metrics["idempotency_hits"] += 1
                logger.info(f"Idempotency hit for operation {operation}")
                return cached_result
        
        # Acquire bulkhead slot
        try:
            bulkhead_slot = await asyncio.wait_for(
                self.bulkhead.acquire(),
                timeout=self.bulkhead_config.timeout
            )
        except asyncio.TimeoutError:
            self.metrics["bulkhead_rejections"] += 1
            raise Exception("Bulkhead timeout - too many concurrent requests")
        
        try:
            # Execute with circuit breaker and retry
            result = await self.circuit_breaker.call(
                self._execute_with_retry,
                operation,
                payload,
                headers
            )
            
            # Cache result for idempotency
            if self.idempotency_manager and idempotency_key:
                await self.idempotency_manager.set_result(idempotency_key, result)
            
            self.metrics["successful_requests"] += 1
            return result
            
        except Exception as e:
            self.metrics["failed_requests"] += 1
            if self.circuit_breaker.state == CircuitState.OPEN:
                self.metrics["circuit_breaker_opens"] += 1
            raise e
        finally:
            await bulkhead_slot.release()
    
    async def _execute_with_retry(
        self,
        operation: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Execute operation with retry logic."""
        
        @retry(
            stop=stop_after_attempt(self.retry_config.max_attempts),
            wait=wait_exponential(
                multiplier=self.retry_config.exponential_multiplier,
                min=self.retry_config.base_delay,
                max=self.retry_config.max_delay
            ),
            retry=retry_if_exception_type(self.retry_config.retryable_exceptions),
            before_sleep=before_sleep_log(logger, logging.WARNING)
        )
        async def _retry_execute():
            self.metrics["retry_attempts"] += 1
            
            # Create WAL entry
            wal_entry = None
            if self.wal:
                wal_entry = WriteAheadLogEntry(
                    id=str(uuid.uuid4()),
                    timestamp=datetime.utcnow(),
                    operation=operation,
                    payload=payload
                )
                await self.wal.log_operation(wal_entry)
            
            try:
                result = await self.execute_operation(operation, payload, headers)
                
                # Mark WAL entry as completed
                if wal_entry:
                    wal_entry.state = "completed"
                    await self.wal.mark_completed(wal_entry.id)
                
                return result
                
            except Exception as e:
                # Update WAL entry with error
                if wal_entry:
                    wal_entry.state = "failed"
                    wal_entry.error = str(e)
                    wal_entry.retry_count += 1
                    wal_entry.last_attempt = datetime.utcnow()
                    await self.wal.log_operation(wal_entry)
                
                raise e
        
        return await _retry_execute()
    
    async def recover_pending_operations(self) -> int:
        """Recover pending operations from write-ahead log."""
        if not self.wal:
            return 0
        
        pending_ops = await self.wal.get_pending_operations()
        recovered_count = 0
        
        for entry in pending_ops:
            try:
                # Skip if too many retries
                if entry.retry_count >= self.retry_config.max_attempts:
                    logger.error(f"Skipping operation {entry.id} - too many retries")
                    continue
                
                # Retry the operation
                result = await self.execute_operation(
                    entry.operation,
                    entry.payload
                )
                
                await self.wal.mark_completed(entry.id)
                recovered_count += 1
                logger.info(f"Recovered operation {entry.id}")
                
            except Exception as e:
                logger.error(f"Failed to recover operation {entry.id}: {e}")
        
        return recovered_count
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get adapter metrics."""
        return {
            **self.metrics,
            "circuit_breaker_state": self.circuit_breaker.state.value,
            "bulkhead_usage": {
                "current": self.bulkhead.current_usage,
                "max": self.bulkhead.max_concurrent,
                "available": self.bulkhead.available_slots
            }
        }

