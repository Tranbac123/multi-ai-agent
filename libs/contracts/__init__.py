"""Strict contracts for all service boundaries."""

from .agent_spec import AgentSpec, AgentCapabilities, AgentMetadata
from .message_spec import MessageSpec, MessageType, MessagePriority
from .tool_spec import ToolSpec, ToolInput, ToolOutput, ToolError
from .error_spec import ErrorSpec, ErrorCode, ErrorSeverity
from .router_spec import RouterDecisionRequest, RouterDecisionResponse, RouterTier, RouterConfidence
from .validation import validate_contract, ContractValidationError

__all__ = [
    "AgentSpec",
    "AgentCapabilities", 
    "AgentMetadata",
    "MessageSpec",
    "MessageType",
    "MessagePriority",
    "ToolSpec",
    "ToolInput",
    "ToolOutput",
    "ToolError",
    "ErrorSpec",
    "ErrorCode",
    "ErrorSeverity",
    "RouterDecisionRequest",
    "RouterDecisionResponse",
    "RouterTier",
    "RouterConfidence",
    "validate_contract",
    "ContractValidationError"
]