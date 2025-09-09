"""Router input/output contracts for service boundaries."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RouterDecisionRequest(BaseModel):
    """Router decision request."""
    message: str
    tenant_id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    features: Dict[str, Any] = Field(default_factory=dict)
    constraints: Dict[str, Any] = Field(default_factory=dict)


class RouterDecisionResponse(BaseModel):
    """Router decision response."""
    agent_id: str
    tier: str  # A, B, C
    confidence: float
    reasoning: str
    cost_estimate: float
    latency_estimate_ms: int
    features_used: List[str]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FeatureExtraction(BaseModel):
    """Feature extraction result."""
    token_count: int
    json_strictness: float
    domain_flags: Dict[str, bool]
    novelty_score: float
    historical_failure_rate: float
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    context_features: Dict[str, Any] = Field(default_factory=dict)


class RouterMetrics(BaseModel):
    """Router performance metrics."""
    decision_latency_ms: float
    misroute_rate: float
    tier_distribution: Dict[str, int]
    cost_efficiency: float
    confidence_distribution: Dict[str, int]
    feature_importance: Dict[str, float]
