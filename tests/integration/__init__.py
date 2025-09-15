"""Integration tests for router correctness and drift detection."""

from enum import Enum
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime

class RouterTier(Enum):
    """Router tier levels."""
    SLM_A = "SLM_A"
    SLM_B = "SLM_B" 
    LLM = "LLM"

class RouterDecision(Enum):
    """Router decision types."""
    ACCEPT = "accept"
    ESCALATE = "escalate"
    REJECT = "reject"
    RETRY = "retry"

class DriftType(Enum):
    """Drift detection types."""
    COST_DRIFT = "cost_drift"
    LATENCY_DRIFT = "latency_drift"
    MISROUTE_DRIFT = "misroute_drift"
    QUALITY_DRIFT = "quality_drift"

@dataclass
class RouterMetrics:
    """Router performance metrics."""
    tier: RouterTier
    decision_time_ms: float
    cost_usd: float
    confidence_score: float
    escalation_count: int
    rejection_count: int
    
@dataclass
class DriftMetrics:
    """Drift detection metrics."""
    drift_type: DriftType
    expected_value: float
    actual_value: float
    drift_percentage: float
    threshold_exceeded: bool
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'drift_type': self.drift_type.value,
            'expected_value': self.expected_value,
            'actual_value': self.actual_value,
            'drift_percentage': self.drift_percentage,
            'threshold_exceeded': self.threshold_exceeded,
            'timestamp': self.timestamp.isoformat()
        }