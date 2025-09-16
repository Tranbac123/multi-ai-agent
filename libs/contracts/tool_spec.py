"""
Tool Specification Contract

Strict Pydantic models for tool-related data structures.
No markdown-JSON tolerated, strict validation enforced.
"""

from typing import Dict, List, Optional, Any, Union, Callable
from pydantic import BaseModel, Field, validator, root_validator
from enum import Enum
import uuid
from datetime import datetime, timezone


class ToolType(Enum):
    """Tool type enumeration."""
    API_CALL = "api_call"
    DATABASE_QUERY = "database_query"
    FILE_OPERATION = "file_operation"
    CALCULATION = "calculation"
    VALIDATION = "validation"
    TRANSFORMATION = "transformation"
    NOTIFICATION = "notification"
    INTEGRATION = "integration"


class ToolStatus(Enum):
    """Tool execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class ToolParameter(BaseModel):
    """Tool parameter specification."""
    
    name: str = Field(
        ..., 
        description="Parameter name",
        min_length=1,
        max_length=50,
        regex=r'^[a-zA-Z_][a-zA-Z0-9_]*$'
    )
    type: str = Field(
        ..., 
        description="Parameter type",
        regex=r'^(string|integer|float|boolean|object|array)$'
    )
    description: str = Field(
        ..., 
        description="Parameter description",
        min_length=1,
        max_length=200
    )
    required: bool = Field(
        default=False,
        description="Whether parameter is required"
    )
    default_value: Optional[Any] = Field(
        None,
        description="Default parameter value"
    )
    constraints: Optional[Dict[str, Any]] = Field(
        None,
        description="Parameter constraints"
    )
    
    @validator('default_value')
    def validate_default_value(cls, v, values):
        """Validate default value against type."""
        if v is None:
            return v
        
        param_type = values.get('type')
        if param_type == 'string' and not isinstance(v, str):
            raise ValueError('default_value must be string for string type')
        elif param_type == 'integer' and not isinstance(v, int):
            raise ValueError('default_value must be integer for integer type')
        elif param_type == 'float' and not isinstance(v, (int, float)):
            raise ValueError('default_value must be number for float type')
        elif param_type == 'boolean' and not isinstance(v, bool):
            raise ValueError('default_value must be boolean for boolean type')
        elif param_type == 'object' and not isinstance(v, dict):
            raise ValueError('default_value must be object for object type')
        elif param_type == 'array' and not isinstance(v, list):
            raise ValueError('default_value must be array for array type')
        
        return v
    
    class Config:
        strict = True
        forbid_extra = True


class ToolInput(BaseModel):
    """Tool input specification."""
    
    tool_id: str = Field(
        ..., 
        description="Tool identifier"
    )
    parameters: Dict[str, Any] = Field(
        ..., 
        description="Tool parameters"
    )
    context: Optional[Dict[str, Any]] = Field(
        None,
        description="Execution context"
    )
    timeout_seconds: Optional[int] = Field(
        None,
        description="Execution timeout in seconds",
        ge=1,
        le=3600
    )
    retry_count: int = Field(
        default=0,
        description="Number of retries",
        ge=0,
        le=5
    )
    idempotency_key: Optional[str] = Field(
        None,
        description="Idempotency key for safe retries"
    )
    
    @validator('tool_id')
    def validate_tool_id(cls, v):
        """Validate tool ID format."""
        if not v or not v.strip():
            raise ValueError('tool_id cannot be empty')
        return v.strip()
    
    @validator('parameters')
    def validate_parameters(cls, v):
        """Validate parameters."""
        if not isinstance(v, dict):
            raise ValueError('parameters must be a dictionary')
        return v
    
    @validator('context')
    def validate_context(cls, v):
        """Validate context."""
        if v is not None and not isinstance(v, dict):
            raise ValueError('context must be a dictionary or None')
        return v
    
    class Config:
        strict = True
        forbid_extra = True


class ToolOutput(BaseModel):
    """Tool output specification."""
    
    tool_id: str = Field(
        ..., 
        description="Tool identifier"
    )
    status: ToolStatus = Field(
        ..., 
        description="Execution status"
    )
    result: Optional[Dict[str, Any]] = Field(
        None,
        description="Tool execution result"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if failed"
    )
    execution_time_ms: float = Field(
        ..., 
        description="Execution time in milliseconds",
        ge=0
    )
    cost_usd: float = Field(
        default=0.0,
        description="Execution cost in USD",
        ge=0
    )
    tokens_used: int = Field(
        default=0,
        description="Tokens consumed",
        ge=0
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata"
    )
    
    @validator('tool_id')
    def validate_tool_id(cls, v):
        """Validate tool ID format."""
        if not v or not v.strip():
            raise ValueError('tool_id cannot be empty')
        return v.strip()
    
    @validator('error_message')
    def validate_error_message(cls, v, values):
        """Validate error message presence for failed status."""
        status = values.get('status')
        if status == ToolStatus.FAILED and not v:
            raise ValueError('error_message is required for failed status')
        return v
    
    @validator('result')
    def validate_result(cls, v, values):
        """Validate result presence for completed status."""
        status = values.get('status')
        if status == ToolStatus.COMPLETED and v is None:
            raise ValueError('result is required for completed status')
        return v
    
    class Config:
        strict = True
        forbid_extra = True
        use_enum_values = True


class ToolError(BaseModel):
    """Tool error specification."""
    
    error_code: str = Field(
        ..., 
        description="Error code",
        min_length=1,
        max_length=50
    )
    error_message: str = Field(
        ..., 
        description="Error message",
        min_length=1,
        max_length=500
    )
    error_type: str = Field(
        ..., 
        description="Error type",
        regex=r'^(validation|execution|timeout|network|permission|resource)$'
    )
    stack_trace: Optional[str] = Field(
        None,
        description="Stack trace for debugging"
    )
    context: Optional[Dict[str, Any]] = Field(
        None,
        description="Error context"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Error timestamp"
    )
    
    class Config:
        strict = True
        forbid_extra = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ToolSpec(BaseModel):
    """Complete tool specification."""
    
    tool_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique tool identifier"
    )
    tenant_id: str = Field(
        ..., 
        description="Tenant identifier",
        min_length=1
    )
    name: str = Field(
        ..., 
        description="Tool name",
        min_length=1,
        max_length=100,
        regex=r'^[a-zA-Z_][a-zA-Z0-9_-]*$'
    )
    description: str = Field(
        ..., 
        description="Tool description",
        min_length=1,
        max_length=500
    )
    tool_type: ToolType = Field(
        ..., 
        description="Tool type"
    )
    parameters: List[ToolParameter] = Field(
        default_factory=list,
        description="Tool parameters"
    )
    version: str = Field(
        ..., 
        description="Tool version",
        regex=r'^\d+\.\d+\.\d+$'
    )
    timeout_seconds: int = Field(
        default=30,
        description="Default timeout in seconds",
        ge=1,
        le=3600
    )
    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts",
        ge=0,
        le=10
    )
    cost_per_call_usd: float = Field(
        default=0.0,
        description="Cost per tool call in USD",
        ge=0
    )
    requires_approval: bool = Field(
        default=False,
        description="Whether tool requires approval"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tool tags"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp"
    )
    
    @validator('tool_id')
    def validate_tool_id(cls, v):
        """Validate tool ID format."""
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError('tool_id must be a valid UUID')
    
    @validator('tenant_id')
    def validate_tenant_id(cls, v):
        """Validate tenant ID format."""
        if not v or not v.strip():
            raise ValueError('tenant_id cannot be empty')
        return v.strip()
    
    @validator('parameters')
    def validate_parameters(cls, v):
        """Validate parameters."""
        if not isinstance(v, list):
            raise ValueError('parameters must be a list')
        
        # Check for duplicate parameter names
        names = [p.name for p in v]
        if len(names) != len(set(names)):
            raise ValueError('parameter names must be unique')
        
        return v
    
    @validator('tags')
    def validate_tags(cls, v):
        """Validate tool tags."""
        if not isinstance(v, list):
            raise ValueError('tags must be a list')
        
        for i, tag in enumerate(v):
            if not isinstance(tag, str):
                raise ValueError(f'tag {i} must be a string')
            if not tag.strip():
                raise ValueError(f'tag {i} cannot be empty')
            if len(tag) > 30:
                raise ValueError(f'tag {i} cannot exceed 30 characters')
        
        return [tag.strip() for tag in v]
    
    @root_validator
    def validate_tool_consistency(cls, values):
        """Validate tool specification consistency."""
        tool_type = values.get('tool_type')
        parameters = values.get('parameters', [])
        requires_approval = values.get('requires_approval', False)
        
        # Validate parameters based on tool type
        if tool_type == ToolType.API_CALL:
            # API calls should have URL parameter
            url_params = [p for p in parameters if p.name == 'url']
            if not url_params:
                raise ValueError('API_CALL tools must have a url parameter')
        
        elif tool_type == ToolType.DATABASE_QUERY:
            # Database queries should have query parameter
            query_params = [p for p in parameters if p.name == 'query']
            if not query_params:
                raise ValueError('DATABASE_QUERY tools must have a query parameter')
        
        # Check approval requirements
        if requires_approval and tool_type in [ToolType.VALIDATION, ToolType.CALCULATION]:
            # These tool types typically don't need approval
            pass  # Could add warning here
        
        return values
    
    class Config:
        strict = True
        forbid_extra = True
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
