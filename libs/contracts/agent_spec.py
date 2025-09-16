"""
Agent Specification Contract

Strict Pydantic models for agent-related data structures.
No markdown-JSON tolerated, strict validation enforced.
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator, root_validator
from enum import Enum
import uuid
from datetime import datetime, timezone


class AgentCapability(Enum):
    """Agent capability types."""
    TEXT_PROCESSING = "text_processing"
    IMAGE_ANALYSIS = "image_analysis"
    DATA_ANALYSIS = "data_analysis"
    CODE_GENERATION = "code_generation"
    REASONING = "reasoning"
    CREATIVE_WRITING = "creative_writing"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    QUESTION_ANSWERING = "question_answering"
    CLASSIFICATION = "classification"


class AgentStatus(Enum):
    """Agent status types."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    TRAINING = "training"
    ERROR = "error"
    DEPRECATED = "deprecated"


class AgentCapabilities(BaseModel):
    """Agent capabilities specification."""
    
    capabilities: List[AgentCapability] = Field(
        ..., 
        description="List of agent capabilities",
        min_items=1
    )
    max_context_length: int = Field(
        ..., 
        description="Maximum context length in tokens",
        ge=1,
        le=1000000
    )
    max_output_length: int = Field(
        ..., 
        description="Maximum output length in tokens",
        ge=1,
        le=100000
    )
    supported_languages: List[str] = Field(
        default_factory=list,
        description="Supported languages (ISO 639-1 codes)"
    )
    requires_tools: bool = Field(
        default=False,
        description="Whether agent requires external tools"
    )
    
    class Config:
        strict = True
        forbid_extra = True
        use_enum_values = True


class AgentMetadata(BaseModel):
    """Agent metadata specification."""
    
    name: str = Field(
        ..., 
        description="Agent name",
        min_length=1,
        max_length=100,
        regex=r'^[a-zA-Z0-9_-]+$'
    )
    version: str = Field(
        ..., 
        description="Agent version",
        regex=r'^\d+\.\d+\.\d+$'
    )
    description: str = Field(
        ..., 
        description="Agent description",
        min_length=1,
        max_length=1000
    )
    author: str = Field(
        ..., 
        description="Agent author",
        min_length=1,
        max_length=100
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp"
    )
    
    class Config:
        strict = True
        forbid_extra = True


class AgentSpec(BaseModel):
    """Complete agent specification."""
    
    agent_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique agent identifier"
    )
    tenant_id: str = Field(
        ..., 
        description="Tenant identifier",
        min_length=1
    )
    metadata: AgentMetadata = Field(
        ..., 
        description="Agent metadata"
    )
    capabilities: AgentCapabilities = Field(
        ..., 
        description="Agent capabilities"
    )
    status: AgentStatus = Field(
        default=AgentStatus.ACTIVE,
        description="Agent status"
    )
    configuration: Dict[str, Any] = Field(
        default_factory=dict,
        description="Agent-specific configuration"
    )
    performance_metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="Performance metrics"
    )
    
    @validator('agent_id')
    def validate_agent_id(cls, v):
        """Validate agent ID format."""
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError('agent_id must be a valid UUID')
    
    @validator('tenant_id')
    def validate_tenant_id(cls, v):
        """Validate tenant ID format."""
        if not v or not v.strip():
            raise ValueError('tenant_id cannot be empty')
        return v.strip()
    
    @validator('configuration')
    def validate_configuration(cls, v):
        """Validate configuration is JSON-serializable."""
        if not isinstance(v, dict):
            raise ValueError('configuration must be a dictionary')
        
        # Check for non-serializable values
        try:
            import json
            json.dumps(v)
        except (TypeError, ValueError):
            raise ValueError('configuration must be JSON-serializable')
        
        return v
    
    @validator('performance_metrics')
    def validate_performance_metrics(cls, v):
        """Validate performance metrics."""
        if not isinstance(v, dict):
            raise ValueError('performance_metrics must be a dictionary')
        
        for key, value in v.items():
            if not isinstance(key, str):
                raise ValueError('performance_metrics keys must be strings')
            if not isinstance(value, (int, float)):
                raise ValueError('performance_metrics values must be numbers')
        
        return v
    
    @root_validator
    def validate_agent_consistency(cls, values):
        """Validate agent specification consistency."""
        capabilities = values.get('capabilities')
        metadata = values.get('metadata')
        configuration = values.get('configuration', {})
        
        if capabilities and metadata:
            # Check if agent name matches capability requirements
            if 'max_context_length' in configuration:
                config_max = configuration['max_context_length']
                capability_max = capabilities.max_context_length
                if config_max > capability_max:
                    raise ValueError('configuration max_context_length cannot exceed capability limit')
        
        return values
    
    class Config:
        strict = True
        forbid_extra = True
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
