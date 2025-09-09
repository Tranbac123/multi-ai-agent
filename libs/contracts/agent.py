"""Agent contracts and specifications."""

from datetime import datetime
from typing import Dict, List, Optional, Any, Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict


class AgentBudgets(BaseModel):
    """Agent execution budgets."""
    max_tokens: int = Field(ge=0, description="Maximum tokens allowed")
    max_cost_usd: float = Field(ge=0.0, description="Maximum cost in USD")
    wall_ms: int = Field(ge=0, description="Maximum wall time in milliseconds")


class AgentSpec(BaseModel):
    """Agent specification with capabilities and constraints."""
    model_config = ConfigDict(frozen=True)
    
    name: str = Field(description="Agent name")
    version: str = Field(description="Agent version")
    inputs_schema: Dict[str, Any] = Field(description="JSONSchema for inputs")
    outputs_schema: Dict[str, Any] = Field(description="JSONSchema for outputs")
    tools_allowed: List[str] = Field(description="List of allowed tool IDs")
    budgets: AgentBudgets = Field(description="Execution budgets")
    role: str = Field(description="Agent role description")
    system_prompt: str = Field(description="System prompt template")


class AgentRun(BaseModel):
    """Agent run state and metadata."""
    run_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(description="Tenant identifier")
    workflow: str = Field(description="Workflow name")
    status: Literal["pending", "running", "completed", "failed", "cancelled"] = Field(
        default="pending"
    )
    agent_spec: AgentSpec = Field(description="Agent specification")
    context: Dict[str, Any] = Field(default_factory=dict)
    plan: List[Dict[str, Any]] = Field(default_factory=list)
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    tokens_in: int = Field(default=0, ge=0)
    tokens_out: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = Field(default=None)
    error: Optional[str] = Field(default=None)


class AgentStep(BaseModel):
    """Individual agent execution step."""
    step_id: UUID = Field(default_factory=uuid4)
    run_id: UUID = Field(description="Parent run ID")
    step_type: Literal["plan", "execute", "critic", "verifier", "finalize"] = Field(
        description="Step type"
    )
    status: Literal["pending", "running", "completed", "failed"] = Field(
        default="pending"
    )
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Dict[str, Any] = Field(default_factory=dict)
    tool_calls: List[str] = Field(default_factory=list)
    tokens_used: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    error: Optional[str] = Field(default=None)
    retry_count: int = Field(default=0, ge=0)
