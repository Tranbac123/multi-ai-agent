"""Router contracts and specifications."""

from datetime import datetime
from typing import Dict, Any, Optional, List, Literal
from uuid import UUID, uuid4
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class RouterTier(str, Enum):
    """Router tier enumeration."""
    SLM_A = "SLM_A"
    SLM_B = "SLM_B"
    LLM = "LLM"


class TextFeatures(BaseModel):
    """Text features for routing decisions."""
    token_count: int = Field(ge=0, description="Token count")
    json_schema_complexity: float = Field(ge=0.0, le=1.0, description="JSON schema complexity")
    domain_flags: Dict[str, bool] = Field(default_factory=dict, description="Domain flags")
    novelty_score: float = Field(ge=0.0, le=1.0, description="Novelty score")
    historical_failure_rate: float = Field(ge=0.0, le=1.0, description="Historical failure rate")
    reasoning_keywords: List[str] = Field(default_factory=list, description="Reasoning keywords")
    entity_count: int = Field(ge=0, description="Entity count")
    format_strictness: float = Field(ge=0.0, le=1.0, description="Format strictness")


class HistoryStats(BaseModel):
    """Historical performance statistics."""
    total_runs: int = Field(ge=0, description="Total runs")
    success_rate: float = Field(ge=0.0, le=1.0, description="Success rate")
    avg_latency_ms: float = Field(ge=0.0, description="Average latency")
    avg_cost_usd: float = Field(ge=0.0, description="Average cost")
    tier_distribution: Dict[str, int] = Field(default_factory=dict, description="Tier distribution")


class RouterDecisionRequest(BaseModel):
    """Router decision request."""
    request_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(description="Tenant identifier")
    task_id: UUID = Field(description="Task identifier")
    requirement: str = Field(description="Task requirement")
    text_features: TextFeatures = Field(description="Text features")
    history_stats: HistoryStats = Field(description="Historical statistics")
    budget_usd: Optional[float] = Field(default=None, ge=0.0, description="Budget constraint")
    max_latency_ms: Optional[int] = Field(default=None, ge=0, description="Latency constraint")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RouterDecisionResponse(BaseModel):
    """Router decision response."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    request_id: UUID = Field(description="Request identifier")
    tier: RouterTier = Field(description="Selected tier")
    confidence: float = Field(ge=0.0, le=1.0, description="Decision confidence")
    expected_cost_usd: float = Field(ge=0.0, description="Expected cost")
    expected_latency_ms: int = Field(ge=0, description="Expected latency")
    reasons: List[str] = Field(description="Decision reasons")
    policy_escalation: bool = Field(default=False, description="Policy escalation flag")
    fallback_tier: Optional[RouterTier] = Field(default=None, description="Fallback tier")
    created_at: datetime = Field(default_factory=datetime.utcnow)
