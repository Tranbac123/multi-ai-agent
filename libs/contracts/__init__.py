"""Contracts for multi-tenant AIaaS platform."""

from .agent import AgentSpec, AgentRun, AgentStep
from .tool import ToolSpec, ToolCall, ToolResult
from .message import MessageSpec, MessageRole
from .error import ErrorSpec, ErrorCode
from .router import RouterDecisionRequest, RouterDecisionResponse, RouterTier
from .billing import UsageCounter, BillingEvent
from .tenant import Tenant, User, APIKey, Plan

__all__ = [
    "AgentSpec",
    "AgentRun", 
    "AgentStep",
    "ToolSpec",
    "ToolCall",
    "ToolResult",
    "MessageSpec",
    "MessageRole",
    "ErrorSpec",
    "ErrorCode",
    "RouterDecisionRequest",
    "RouterDecisionResponse",
    "RouterTier",
    "UsageCounter",
    "BillingEvent",
    "Tenant",
    "User",
    "APIKey",
    "Plan",
]
