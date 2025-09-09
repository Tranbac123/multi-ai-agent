"""Standardized response utilities."""

from typing import Any, Optional
from datetime import datetime
from libs.contracts.error import ErrorSpec, ErrorResponse


def success_response(data: Any, message: str = "Success") -> dict:
    """Create standardized success response."""
    return {
        "success": True,
        "message": message,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }


def error_response(error_spec: ErrorSpec, trace_id: Optional[str] = None) -> dict:
    """Create standardized error response."""
    return {
        "success": False,
        "error": {
            "code": error_spec.code,
            "message": error_spec.message,
            "retriable": error_spec.retriable,
            "diagnostics": error_spec.diagnostics,
            "context": error_spec.context,
            "created_at": error_spec.created_at.isoformat()
        },
        "trace_id": trace_id,
        "timestamp": datetime.utcnow().isoformat()
    }
