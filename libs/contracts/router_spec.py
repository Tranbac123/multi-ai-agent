"""
Router Specification Contract

Strict Pydantic models for router-related data structures.
No markdown-JSON tolerated, strict validation enforced.
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum
import uuid
from datetime import datetime, timezone


class RouterTier(Enum):
    """Router tier enumeration."""
    SLM_A = "slm_a"  # Small Language Model A
    SLM_B = "slm_b"  # Small Language Model B
    LLM_A = "llm_a"  # Large Language Model A
    LLM_B = "llm_b"  # Large Language Model B
    HUMAN = "human"   # Human escalation


class RouterConfidence(Enum):
    """Router confidence levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class FeatureVector(BaseModel):
    """Feature vector for routing decisions."""
    
    token_count: int = Field(
        ..., 
        description="Input token count",
        ge=0,
        le=1000000
    )
    json_schema_strictness: float = Field(
        ..., 
        description="JSON schema strictness score",
        ge=0.0,
        le=1.0
    )
    domain_flags: List[str] = Field(
        ..., 
        description="Domain classification flags",
        min_length=1
    )
    novelty: float = Field(
        ..., 
        description="Novelty score (0-1)",
        ge=0.0,
        le=1.0
    )
    historical_failure_rate: float = Field(
        ..., 
        description="Historical failure rate for similar requests",
        ge=0.0,
        le=1.0
    )
    complexity_score: float = Field(
        ..., 
        description="Request complexity score",
        ge=0.0,
        le=1.0
    )
    urgency_score: float = Field(
        ..., 
        description="Request urgency score",
        ge=0.0,
        le=1.0
    )
    cost_sensitivity: float = Field(
        ..., 
        description="Cost sensitivity score",
        ge=0.0,
        le=1.0
    )
    
    @field_validator('domain_flags')
    @classmethod
    def validate_domain_flags(cls, v):
        """Validate domain flags."""
        if not isinstance(v, list):
            raise ValueError('domain_flags must be a list')
        
        for i, flag in enumerate(v):
            if not isinstance(flag, str):
                raise ValueError(f'domain_flag {i} must be a string')
            if not flag.strip():
                raise ValueError(f'domain_flag {i} cannot be empty')
            if len(flag) > 50:
                raise ValueError(f'domain_flag {i} cannot exceed 50 characters')
        
        return [flag.strip() for flag in v]
    
    class Config:
        strict = True
        forbid_extra = True


class RoutingContext(BaseModel):
    """Routing context information."""
    
    tenant_id: str = Field(
        ..., 
        description="Tenant identifier",
        min_length=1
    )
    user_id: Optional[str] = Field(
        None,
        description="User identifier"
    )
    session_id: Optional[str] = Field(
        None,
        description="Session identifier"
    )
    request_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Request identifier"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Request timestamp"
    )
    tenant_tier: str = Field(
        default="standard",
        description="Tenant subscription tier"
    )
    cost_budget_remaining: float = Field(
        default=1.0,
        description="Remaining cost budget",
        ge=0.0
    )
    latency_budget_ms: int = Field(
        default=5000,
        description="Latency budget in milliseconds",
        ge=100,
        le=60000
    )
    
    @field_validator('tenant_id')
    @classmethod
    def validate_tenant_id(cls, v):
        """Validate tenant ID format."""
        if not v or not v.strip():
            raise ValueError('tenant_id cannot be empty')
        return v.strip()
    
    @field_validator('request_id')
    @classmethod
    def validate_request_id(cls, v):
        """Validate request ID format."""
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError('request_id must be a valid UUID')
    
    class Config:
        strict = True
        forbid_extra = True


class RouterDecisionRequest(BaseModel):
    """Router decision request specification."""
    
    input_text: str = Field(
        ..., 
        description="Input text to route",
        min_length=1,
        max_length=100000
    )
    features: FeatureVector = Field(
        ..., 
        description="Extracted feature vector"
    )
    context: RoutingContext = Field(
        ..., 
        description="Routing context"
    )
    available_tiers: List[RouterTier] = Field(
        ..., 
        description="Available routing tiers",
        min_length=1
    )
    early_exit_threshold: Optional[float] = Field(
        None,
        description="Early exit confidence threshold",
        ge=0.0,
        le=1.0
    )
    max_cost_usd: Optional[float] = Field(
        None,
        description="Maximum cost budget",
        ge=0.0
    )
    max_latency_ms: Optional[int] = Field(
        None,
        description="Maximum latency budget",
        ge=100
    )
    
    @field_validator('input_text')
    @classmethod
    def validate_input_text(cls, v):
        """Validate input text."""
        if not v or not v.strip():
            raise ValueError('input_text cannot be empty')
        return v.strip()
    
    @field_validator('available_tiers')
    @classmethod
    def validate_available_tiers(cls, v):
        """Validate available tiers."""
        if not isinstance(v, list):
            raise ValueError('available_tiers must be a list')
        
        if len(set(v)) != len(v):
            raise ValueError('available_tiers must contain unique values')
        
        return v
    
    @model_validator(mode='after')
    def validate_request_consistency(self):
        """Validate request consistency."""
        # Validate cost constraints
        if self.max_cost_usd and self.context and self.context.cost_budget_remaining > self.max_cost_usd:
            raise ValueError('cost_budget_remaining cannot exceed max_cost_usd')
        
        # Validate latency constraints
        if self.max_latency_ms and self.context and self.context.latency_budget_ms > self.max_latency_ms:
            raise ValueError('latency_budget_ms cannot exceed max_latency_ms')
        
        # Validate feature consistency
        if self.features and self.context:
            if self.features.cost_sensitivity > 0.8 and self.context.cost_budget_remaining < 0.2:
                # High cost sensitivity with low budget - might want to warn
                pass
        
        return self
    
    model_config = {
        "str_strip_whitespace": True,
        "validate_assignment": True,
        "extra": "forbid",
        "use_enum_values": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }


class RouterDecisionResponse(BaseModel):
    """Router decision response specification."""
    
    selected_tier: RouterTier = Field(
        ..., 
        description="Selected routing tier"
    )
    confidence: float = Field(
        ..., 
        description="Decision confidence score",
        ge=0.0,
        le=1.0
    )
    confidence_level: RouterConfidence = Field(
        ..., 
        description="Confidence level"
    )
    reasoning: str = Field(
        ..., 
        description="Decision reasoning",
        min_length=1,
        max_length=1000
    )
    expected_cost_usd: float = Field(
        ..., 
        description="Expected cost in USD",
        ge=0.0
    )
    expected_latency_ms: int = Field(
        ..., 
        description="Expected latency in milliseconds",
        ge=1
    )
    early_exit: bool = Field(
        default=False,
        description="Whether early exit was triggered"
    )
    alternative_tiers: List[RouterTier] = Field(
        default_factory=list,
        description="Alternative tier options"
    )
    decision_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Decision metadata"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Decision timestamp"
    )
    
    @field_validator('reasoning')
    @classmethod
    def validate_reasoning(cls, v):
        """Validate reasoning."""
        if not v or not v.strip():
            raise ValueError('reasoning cannot be empty')
        return v.strip()
    
    @field_validator('alternative_tiers')
    @classmethod
    def validate_alternative_tiers(cls, v):
        """Validate alternative tiers."""
        if not isinstance(v, list):
            raise ValueError('alternative_tiers must be a list')
        
        if len(set(v)) != len(v):
            raise ValueError('alternative_tiers must contain unique values')
        
        return v
    
    @field_validator('decision_metadata')
    @classmethod
    def validate_decision_metadata(cls, v):
        """Validate decision metadata."""
        if not isinstance(v, dict):
            raise ValueError('decision_metadata must be a dictionary')
        
        # Ensure metadata is JSON-serializable
        try:
            import json
            json.dumps(v)
        except (TypeError, ValueError):
            raise ValueError('decision_metadata must be JSON-serializable')
        
        return v
    
    @model_validator(mode='after')
    def validate_response_consistency(self):
        """Validate response consistency."""
        # Validate confidence level mapping
        if self.confidence is not None and self.confidence_level is not None:
            if self.confidence < 0.3 and self.confidence_level != RouterConfidence.LOW:
                pass  # Could add warning here
            elif 0.3 <= self.confidence < 0.6 and self.confidence_level != RouterConfidence.MEDIUM:
                pass  # Could add warning here
            elif 0.6 <= self.confidence < 0.8 and self.confidence_level != RouterConfidence.HIGH:
                pass  # Could add warning here
            elif self.confidence >= 0.8 and self.confidence_level != RouterConfidence.VERY_HIGH:
                pass  # Could add warning here
        
        # Validate early exit consistency
        if self.early_exit and self.confidence < 0.8:
            pass  # Early exit with low confidence might be suspicious
        
        # Validate alternative tiers don't include selected tier
        if self.selected_tier in self.alternative_tiers:
            raise ValueError('selected_tier cannot be in alternative_tiers')
        
        return self
    
    model_config = {
        "str_strip_whitespace": True,
        "validate_assignment": True,
        "extra": "forbid",
        "use_enum_values": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }
