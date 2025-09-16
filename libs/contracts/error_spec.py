"""
Error Specification Contract

Strict Pydantic models for error-related data structures.
No markdown-JSON tolerated, strict validation enforced.
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator, root_validator
from enum import Enum
import uuid
from datetime import datetime, timezone


class ErrorCode(Enum):
    """Standard error codes."""
    # Validation errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_FORMAT = "INVALID_FORMAT"
    
    # Authentication/Authorization errors
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    
    # Resource errors
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    
    # System errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    
    # Business logic errors
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"
    WORKFLOW_ERROR = "WORKFLOW_ERROR"
    AGENT_ERROR = "AGENT_ERROR"
    TOOL_ERROR = "TOOL_ERROR"


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories."""
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    RESOURCE = "resource"
    SYSTEM = "system"
    BUSINESS = "business"
    NETWORK = "network"
    TIMEOUT = "timeout"


class ErrorContext(BaseModel):
    """Error context information."""
    
    tenant_id: Optional[str] = Field(
        None,
        description="Tenant identifier"
    )
    user_id: Optional[str] = Field(
        None,
        description="User identifier"
    )
    session_id: Optional[str] = Field(
        None,
        description="Session identifier"
    )
    request_id: Optional[str] = Field(
        None,
        description="Request identifier"
    )
    workflow_id: Optional[str] = Field(
        None,
        description="Workflow identifier"
    )
    agent_id: Optional[str] = Field(
        None,
        description="Agent identifier"
    )
    tool_id: Optional[str] = Field(
        None,
        description="Tool identifier"
    )
    component: Optional[str] = Field(
        None,
        description="Component that generated the error",
        max_length=100
    )
    operation: Optional[str] = Field(
        None,
        description="Operation that failed",
        max_length=100
    )
    
    class Config:
        strict = True
        forbid_extra = True


class ErrorDetails(BaseModel):
    """Detailed error information."""
    
    message: str = Field(
        ..., 
        description="Human-readable error message",
        min_length=1,
        max_length=1000
    )
    technical_message: Optional[str] = Field(
        None,
        description="Technical error details",
        max_length=2000
    )
    stack_trace: Optional[str] = Field(
        None,
        description="Stack trace for debugging"
    )
    suggestions: List[str] = Field(
        default_factory=list,
        description="Suggested actions to resolve the error"
    )
    documentation_url: Optional[str] = Field(
        None,
        description="URL to relevant documentation"
    )
    retry_after_seconds: Optional[int] = Field(
        None,
        description="Suggested retry delay in seconds",
        ge=1
    )
    
    @validator('suggestions')
    def validate_suggestions(cls, v):
        """Validate suggestions."""
        if not isinstance(v, list):
            raise ValueError('suggestions must be a list')
        
        for i, suggestion in enumerate(v):
            if not isinstance(suggestion, str):
                raise ValueError(f'suggestion {i} must be a string')
            if not suggestion.strip():
                raise ValueError(f'suggestion {i} cannot be empty')
            if len(suggestion) > 200:
                raise ValueError(f'suggestion {i} cannot exceed 200 characters')
        
        return [suggestion.strip() for suggestion in v]
    
    @validator('documentation_url')
    def validate_documentation_url(cls, v):
        """Validate documentation URL."""
        if v is not None:
            if not v.startswith(('http://', 'https://')):
                raise ValueError('documentation_url must be a valid HTTP URL')
        return v
    
    class Config:
        strict = True
        forbid_extra = True


class ErrorSpec(BaseModel):
    """Complete error specification."""
    
    error_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique error identifier"
    )
    error_code: ErrorCode = Field(
        ..., 
        description="Error code"
    )
    severity: ErrorSeverity = Field(
        ..., 
        description="Error severity"
    )
    category: ErrorCategory = Field(
        ..., 
        description="Error category"
    )
    details: ErrorDetails = Field(
        ..., 
        description="Error details"
    )
    context: ErrorContext = Field(
        ..., 
        description="Error context"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Error timestamp"
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID for error tracking"
    )
    parent_error_id: Optional[str] = Field(
        None,
        description="Parent error ID for error chains"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional error metadata"
    )
    
    @validator('error_id')
    def validate_error_id(cls, v):
        """Validate error ID format."""
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError('error_id must be a valid UUID')
    
    @validator('parent_error_id')
    def validate_parent_error_id(cls, v):
        """Validate parent error ID format."""
        if v is not None:
            try:
                uuid.UUID(v)
                return v
            except ValueError:
                raise ValueError('parent_error_id must be a valid UUID')
        return v
    
    @validator('correlation_id')
    def validate_correlation_id(cls, v):
        """Validate correlation ID format."""
        if v is not None and not v.strip():
            raise ValueError('correlation_id cannot be empty')
        return v.strip() if v else None
    
    @validator('metadata')
    def validate_metadata(cls, v):
        """Validate metadata."""
        if not isinstance(v, dict):
            raise ValueError('metadata must be a dictionary')
        
        # Ensure metadata is JSON-serializable
        try:
            import json
            json.dumps(v)
        except (TypeError, ValueError):
            raise ValueError('metadata must be JSON-serializable')
        
        return v
    
    @root_validator
    def validate_error_consistency(cls, values):
        """Validate error specification consistency."""
        error_code = values.get('error_code')
        category = values.get('category')
        severity = values.get('severity')
        details = values.get('details')
        
        # Validate category matches error code
        if error_code and category:
            code_category_map = {
                ErrorCode.VALIDATION_ERROR: ErrorCategory.VALIDATION,
                ErrorCode.INVALID_INPUT: ErrorCategory.VALIDATION,
                ErrorCode.MISSING_REQUIRED_FIELD: ErrorCategory.VALIDATION,
                ErrorCode.INVALID_FORMAT: ErrorCategory.VALIDATION,
                
                ErrorCode.UNAUTHORIZED: ErrorCategory.AUTHENTICATION,
                ErrorCode.INVALID_TOKEN: ErrorCategory.AUTHENTICATION,
                ErrorCode.TOKEN_EXPIRED: ErrorCategory.AUTHENTICATION,
                ErrorCode.FORBIDDEN: ErrorCategory.AUTHORIZATION,
                
                ErrorCode.RESOURCE_NOT_FOUND: ErrorCategory.RESOURCE,
                ErrorCode.RESOURCE_CONFLICT: ErrorCategory.RESOURCE,
                ErrorCode.QUOTA_EXCEEDED: ErrorCategory.RESOURCE,
                ErrorCode.RATE_LIMIT_EXCEEDED: ErrorCategory.RESOURCE,
                
                ErrorCode.INTERNAL_ERROR: ErrorCategory.SYSTEM,
                ErrorCode.SERVICE_UNAVAILABLE: ErrorCategory.SYSTEM,
                ErrorCode.TIMEOUT: ErrorCategory.TIMEOUT,
                ErrorCode.NETWORK_ERROR: ErrorCategory.NETWORK,
                
                ErrorCode.BUSINESS_RULE_VIOLATION: ErrorCategory.BUSINESS,
                ErrorCode.WORKFLOW_ERROR: ErrorCategory.BUSINESS,
                ErrorCode.AGENT_ERROR: ErrorCategory.BUSINESS,
                ErrorCode.TOOL_ERROR: ErrorCategory.BUSINESS,
            }
            
            expected_category = code_category_map.get(error_code)
            if expected_category and category != expected_category:
                raise ValueError(f'error_code {error_code} should have category {expected_category}')
        
        # Validate severity and retry suggestions
        if severity == ErrorSeverity.CRITICAL and details and details.retry_after_seconds:
            # Critical errors typically shouldn't suggest retries
            pass  # Could add warning here
        
        return values
    
    class Config:
        strict = True
        forbid_extra = True
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
