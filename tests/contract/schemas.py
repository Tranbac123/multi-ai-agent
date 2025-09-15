"""Pydantic schemas for contract validation at service boundaries."""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Dict, Any, List, Optional, Union, Literal
from datetime import datetime
from enum import Enum
import re
import json

# Import ContentPolicyViolation from contract module
from . import ContentPolicyViolation

# Enums for type safety
class RequestType(Enum):
    """Request types for routing."""
    FAQ = "faq"
    ORDER = "order"
    TRACKING = "tracking"
    LEAD = "lead"
    PAYMENT = "payment"
    SUPPORT = "support"

class LLMTier(Enum):
    """LLM tiers for routing decisions."""
    SLM_A = "SLM_A"
    SLM_B = "SLM_B"
    LLM = "LLM"

class ToolStatus(Enum):
    """Tool execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class WorkflowStatus(Enum):
    """Workflow execution status."""
    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"

# API Gateway ↔ Orchestrator Contracts
class APIRequest(BaseModel):
    """API Gateway request schema."""
    request_id: str = Field(..., min_length=1, max_length=64)
    tenant_id: str = Field(..., pattern=r"^tenant_\d{4}$")
    user_id: str = Field(..., pattern=r"^user_\d{4}$")
    request_type: RequestType
    message: str = Field(..., min_length=1, max_length=10000)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @field_validator('message')
    @classmethod
    def validate_message_content(cls, v):
        """Validate message content policy."""
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        
        # Check for content policy violations
        profanity_patterns = [
            r'\b(bad|hate|stupid)\b',  # Simplified for demo
        ]
        
        for pattern in profanity_patterns:
            if re.search(pattern, v.lower()):
                raise ValueError("Content policy violation: inappropriate language")
        
        return v.strip()
    
    @field_validator('context')
    @classmethod
    def validate_context(cls, v):
        """Validate context is valid JSON structure."""
        if v is None:
            return {}
        
        # Ensure context is serializable
        try:
            json.dumps(v)
        except (TypeError, ValueError):
            raise ValueError("Context must be JSON serializable")
        
        return v

class APIResponse(BaseModel):
    """API Gateway response schema."""
    request_id: str
    success: bool
    response: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    execution_time_ms: Optional[float] = None
    cost_usd: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @model_validator(mode='after')
    def validate_response_consistency(self):
        """Validate response consistency."""
        if self.success and (self.error_code or not self.response):
            raise ValueError("Successful response must have response text and no error")
        
        if not self.success and (not self.error_code or self.response):
            raise ValueError("Failed response must have error code and no response text")
        
        return self

# Orchestrator ↔ Router Contracts
class RouterRequest(BaseModel):
    """Router service request schema."""
    request_id: str
    tenant_id: str
    user_id: str
    message: str
    request_type: RequestType
    context: Dict[str, Any] = Field(default_factory=dict)
    user_history: Optional[List[Dict[str, Any]]] = Field(default=None, max_length=50)
    tenant_config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @field_validator('user_history')
    @classmethod
    def validate_user_history(cls, v):
        """Validate user history structure."""
        if v is None:
            return None
        
        for item in v:
            if not isinstance(item, dict):
                raise ValueError("User history items must be dictionaries")
            
            required_fields = ['timestamp', 'request_type', 'message']
            for field in required_fields:
                if field not in item:
                    raise ValueError(f"User history item missing required field: {field}")
        
        return v

class RouterResponse(BaseModel):
    """Router service response schema."""
    request_id: str
    tier: LLMTier
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = Field(..., min_length=10, max_length=500)
    estimated_cost_usd: float = Field(..., ge=0.0, le=1.0)
    estimated_latency_ms: float = Field(..., ge=0.0, le=10000.0)
    features: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('reasoning')
    @classmethod
    def validate_reasoning(cls, v):
        """Validate reasoning is meaningful."""
        if len(v.split()) < 3:
            raise ValueError("Reasoning must be at least 3 words")
        return v

# Router ↔ Tool Contracts
class ToolRequest(BaseModel):
    """Tool execution request schema."""
    tool_id: str = Field(..., pattern=r"^tool_[a-z_]+$")
    tenant_id: str
    user_id: str
    request_id: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int = Field(default=30000, ge=1000, le=300000)
    retry_count: int = Field(default=0, ge=0, le=3)
    idempotency_key: Optional[str] = Field(default=None, max_length=128)
    
    @field_validator('parameters')
    @classmethod
    def validate_parameters(cls, v):
        """Validate parameters are JSON serializable."""
        try:
            json.dumps(v)
        except (TypeError, ValueError):
            raise ValueError("Parameters must be JSON serializable")
        return v

class ToolResponse(BaseModel):
    """Tool execution response schema."""
    tool_id: str
    request_id: str
    status: ToolStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: float = Field(..., ge=0.0)
    cost_usd: float = Field(..., ge=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @model_validator(mode='after')
    def validate_response_consistency(self):
        """Validate tool response consistency."""
        if self.status == ToolStatus.COMPLETED and (not self.result or self.error):
            raise ValueError("Completed tool must have result and no error")
        
        if self.status == ToolStatus.FAILED and (self.result or not self.error):
            raise ValueError("Failed tool must have error and no result")
        
        return self

# Workflow Contracts
class WorkflowStep(BaseModel):
    """Individual workflow step schema."""
    step_id: str = Field(..., pattern=r"^step_\d+$")
    step_type: str = Field(..., min_length=1, max_length=50)
    tool_id: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    condition: Optional[str] = None
    timeout_ms: int = Field(default=30000, ge=1000, le=300000)
    
    @field_validator('step_type')
    @classmethod
    def validate_step_type(cls, v):
        """Validate step type."""
        valid_types = ['tool_call', 'condition', 'loop', 'parallel', 'wait']
        if v not in valid_types:
            raise ValueError(f"Invalid step type. Must be one of: {valid_types}")
        return v

class WorkflowRequest(BaseModel):
    """Workflow execution request schema."""
    workflow_id: str = Field(..., pattern=r"^workflow_[a-z_]+$")
    tenant_id: str
    user_id: str
    request_id: str
    steps: List[WorkflowStep] = Field(..., min_length=1, max_length=50)
    context: Dict[str, Any] = Field(default_factory=dict)
    max_duration_ms: int = Field(default=300000, ge=10000, le=1800000)  # Max 30 minutes
    
    @field_validator('steps')
    @classmethod
    def validate_step_sequence(cls, v):
        """Validate step sequence."""
        step_ids = [step.step_id for step in v]
        
        # Check for duplicate step IDs
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Duplicate step IDs found")
        
        # Check sequential numbering
        expected_ids = [f"step_{i+1}" for i in range(len(v))]
        if step_ids != expected_ids:
            raise ValueError("Steps must be sequentially numbered starting from step_1")
        
        return v

class WorkflowResponse(BaseModel):
    """Workflow execution response schema."""
    workflow_id: str
    request_id: str
    status: WorkflowStatus
    current_step: Optional[str] = None
    results: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: float = Field(..., ge=0.0)
    total_cost_usd: float = Field(..., ge=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @model_validator(mode='after')
    def validate_response_consistency(self):
        """Validate workflow response consistency."""
        if self.status == WorkflowStatus.COMPLETED and (not self.results or self.error):
            raise ValueError("Completed workflow must have results and no error")
        
        if self.status == WorkflowStatus.FAILED and (self.results or not self.error):
            raise ValueError("Failed workflow must have error and no results")
        
        if self.status == WorkflowStatus.ACTIVE and not self.current_step:
            raise ValueError("Active workflow must have current step")
        
        return self

# Event Contracts
class EventPayload(BaseModel):
    """Standard event payload schema."""
    event_id: str = Field(..., pattern=r"^evt_[a-f0-9]{16}$")
    event_type: str = Field(..., pattern=r"^[a-z_]+\.[a-z_]+$")
    tenant_id: str
    user_id: str
    timestamp: datetime
    data: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('data')
    @classmethod
    def validate_event_data(cls, v):
        """Validate event data is JSON serializable."""
        try:
            json.dumps(v)
        except (TypeError, ValueError):
            raise ValueError("Event data must be JSON serializable")
        return v

# Error Response Contract
class ErrorResponse(BaseModel):
    """Standard error response schema."""
    error_code: str = Field(..., min_length=1, max_length=50)
    message: str = Field(..., min_length=1, max_length=500)
    field: Optional[str] = Field(default=None, max_length=100)
    details: Optional[Dict[str, Any]] = Field(default=None)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    request_id: Optional[str] = Field(default=None, max_length=64)
    
    @field_validator('error_code')
    @classmethod
    def validate_error_code(cls, v):
        """Validate error code format."""
        if not re.match(r'^[A-Z_]+$', v):
            raise ValueError("Error code must be uppercase with underscores")
        return v

# Validation helper functions
def validate_strict_json(data: Union[str, Dict, List]) -> Union[Dict, List]:
    """Validate that data is strict JSON (reject loose/markdown JSON)."""
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
        
        # Check for markdown-like content
        if isinstance(parsed, str):
            if any(marker in parsed for marker in ['```', '**', '*', '#', '##']):
                raise ValueError("Markdown content not allowed in strict JSON mode")
        
        return parsed
    
    return data

def validate_no_pii(data: Dict[str, Any]) -> None:
    """Validate that data contains no PII."""
    import re
    
    pii_patterns = [
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
        r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
        r'\b\d{3}-\d{3}-\d{4}\b',  # Phone
        r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',  # Credit card
    ]
    
    data_str = json.dumps(data)
    for pattern in pii_patterns:
        matches = re.findall(pattern, data_str)
        if matches:
            raise ValueError(f"PII detected: {matches}")

def validate_content_policy(text: str) -> List[ContentPolicyViolation]:
    """Validate content policy and return violations."""
    violations = []
    
    # Check for profanity (simplified for demo)
    profanity_words = ['bad', 'hate', 'stupid']  # Simplified list
    if any(word in text.lower() for word in profanity_words):
        violations.append(ContentPolicyViolation.PROFANITY)
    
    # Check for spam patterns
    if text.count('!') > 5 or text.upper() == text:
        violations.append(ContentPolicyViolation.SPAM)
    
    # Check for malicious links
    if re.search(r'https?://(?!trusted-domain\.com)', text):
        violations.append(ContentPolicyViolation.MALICIOUS_LINK)
    
    return violations
