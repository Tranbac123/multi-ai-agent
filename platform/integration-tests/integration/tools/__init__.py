"""Tool reliability integration tests for saga patterns and idempotency."""

from enum import Enum
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

class ReliabilityPattern(Enum):
    """Reliability pattern types."""
    TIMEOUT = "timeout"
    RETRY = "retry"
    CIRCUIT_BREAKER = "circuit_breaker"
    BULKHEAD = "bulkhead"
    IDEMPOTENCY = "idempotency"
    SAGA = "saga"

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class RetryStrategy(Enum):
    """Retry strategy types."""
    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    LINEAR = "linear"

@dataclass
class SagaStep:
    """Individual step in a saga transaction."""
    step_id: str
    action: str
    compensate: str
    timeout_seconds: int
    retry_count: int
    max_retries: int
    completed: bool = False
    failed: bool = False
    compensated: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'step_id': self.step_id,
            'action': self.action,
            'compensate': self.compensate,
            'timeout_seconds': self.timeout_seconds,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'completed': self.completed,
            'failed': self.failed,
            'compensated': self.compensated
        }

@dataclass
class IdempotencyKey:
    """Idempotency key for request deduplication."""
    key: str
    tenant_id: str
    user_id: str
    operation: str
    timestamp: datetime
    ttl_seconds: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'key': self.key,
            'tenant_id': self.tenant_id,
            'user_id': self.user_id,
            'operation': self.operation,
            'timestamp': self.timestamp.isoformat(),
            'ttl_seconds': self.ttl_seconds
        }
