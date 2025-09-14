"""Router contracts and specifications with strict JSON validation."""

from datetime import datetime
from typing import Dict, Any, Optional, List, Literal
from uuid import UUID, uuid4
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, field_validator


class RouterTier(str, Enum):
    """Router tier enumeration."""

    SLM_A = "SLM_A"
    SLM_B = "SLM_B"
    LLM = "LLM"


class TextFeatures(BaseModel):
    """Text features for routing decisions with strict JSON validation."""
    
    model_config = ConfigDict(
        extra="forbid",  # Forbid extra fields
        validate_assignment=True,
        str_strip_whitespace=True
    )

    token_count: int = Field(ge=0, le=100000, description="Token count")
    json_schema_strictness: float = Field(
        ge=0.0, le=1.0, description="JSON schema strictness (0=loose, 1=strict)"
    )
    domain_flags: Dict[str, bool] = Field(
        default_factory=dict, description="Domain flags (customer_support, ecommerce, etc.)"
    )
    novelty_score: float = Field(ge=0.0, le=1.0, description="Novelty score")
    historical_failure_rate: float = Field(
        ge=0.0, le=1.0, description="Historical failure rate"
    )
    reasoning_keywords: List[str] = Field(
        default_factory=list, max_length=50, description="Reasoning keywords"
    )
    entity_count: int = Field(ge=0, le=1000, description="Entity count")
    format_strictness: float = Field(ge=0.0, le=1.0, description="Format strictness")


class HistoryStats(BaseModel):
    """Historical performance statistics with strict JSON validation."""
    
    model_config = ConfigDict(
        extra="forbid",  # Forbid extra fields
        validate_assignment=True,
        str_strip_whitespace=True
    )

    total_runs: int = Field(ge=0, le=1000000, description="Total runs")
    success_rate: float = Field(ge=0.0, le=1.0, description="Success rate")
    avg_latency_ms: float = Field(ge=0.0, le=60000, description="Average latency in ms")
    avg_cost_usd: float = Field(ge=0.0, le=100.0, description="Average cost in USD")
    tier_distribution: Dict[str, int] = Field(
        default_factory=dict, description="Tier distribution counts"
    )


class RouterDecisionRequest(BaseModel):
    """Router decision request with strict JSON validation."""
    
    model_config = ConfigDict(
        extra="forbid",  # Forbid extra fields
        validate_assignment=True,
        str_strip_whitespace=True
    )

    request_id: UUID = Field(default_factory=uuid4, description="Request identifier")
    tenant_id: UUID = Field(..., description="Tenant identifier")
    task_id: UUID = Field(..., description="Task identifier")
    requirement: str = Field(..., min_length=1, max_length=10000, description="Task requirement")
    text_features: TextFeatures = Field(..., description="Text features")
    history_stats: HistoryStats = Field(..., description="Historical statistics")
    budget_usd: Optional[float] = Field(
        default=None, ge=0.0, le=1000.0, description="Budget constraint in USD"
    )
    max_latency_ms: Optional[int] = Field(
        default=None, ge=0, le=60000, description="Latency constraint in ms"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Request timestamp")
    
    @field_validator('requirement')
    @classmethod
    def validate_requirement(cls, v):
        """Validate requirement is not markdown-wrapped JSON."""
        if v.strip().startswith('```json') and v.strip().endswith('```'):
            raise ValueError("Markdown-wrapped JSON is not allowed")
        return v


class RouterDecisionResponse(BaseModel):
    """Router decision response with strict JSON validation."""
    
    model_config = ConfigDict(
        extra="forbid",  # Forbid extra fields
        validate_assignment=True,
        str_strip_whitespace=True
    )

    request_id: UUID = Field(..., description="Request identifier")
    tier: RouterTier = Field(..., description="Selected tier")
    confidence: float = Field(ge=0.0, le=1.0, description="Decision confidence")
    expected_cost_usd: float = Field(ge=0.0, le=1000.0, description="Expected cost in USD")
    expected_latency_ms: int = Field(ge=0, le=60000, description="Expected latency in ms")
    reasons: List[str] = Field(..., min_length=1, max_length=10, description="Decision reasons")
    policy_escalation: bool = Field(default=False, description="Policy escalation flag")
    fallback_tier: Optional[RouterTier] = Field(
        default=None, description="Fallback tier"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    
    @field_validator('reasons')
    @classmethod
    def validate_reasons(cls, v):
        """Validate reasons list is not empty."""
        if not v:
            raise ValueError("At least one reason must be provided")
        return v
