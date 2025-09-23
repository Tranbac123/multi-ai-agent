from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Literal
from enum import Enum

class Provider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"

class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class CompletionRequest(BaseModel):
    tenant_id: str
    model: str
    messages: List[Message]
    provider: Optional[Provider] = None
    max_tokens: Optional[int] = 1000
    temperature: Optional[float] = 0.7
    stream: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: Optional[float] = None

class CompletionResponse(BaseModel):
    id: str
    model: str
    provider: Provider
    content: str
    usage: Usage
    finish_reason: str
    created_at: str

class ProviderStatus(BaseModel):
    provider: Provider
    status: Literal["healthy", "degraded", "down"]
    error_rate: float
    avg_latency_ms: int
    last_check: str

class HealthResponse(BaseModel):
    status: str
    providers: List[ProviderStatus]
    circuit_breakers: Dict[str, Dict[str, Any]]

class TokenMeteringEvent(BaseModel):
    tenant_id: str
    model: str
    provider: Provider
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    request_id: str
    timestamp: str

