"""Strict contracts for all service boundaries."""

from src.agent_spec import AgentSpec, AgentCapabilities, AgentMetadata
from src.message_spec import MessageSpec, MessageType, MessagePriority
from src.tool_spec import ToolSpec, ToolInput, ToolOutput, ToolError
from src.error_spec import ErrorSpec, ErrorCode, ErrorSeverity
from src.router_spec import RouterDecisionRequest, RouterDecisionResponse, RouterTier, RouterConfidence
from src.validation import validate_contract, ContractValidationError

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