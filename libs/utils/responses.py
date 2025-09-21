"""Standardized response utilities."""

from typing import Any, Optional
from datetime import datetime
from libs.contracts.error_spec import ErrorSpec


def success_response(data: Any, message: str = "Success") -> dict:
    """Create standardized success response."""
    return {
        "success": True,
        "message": message,
        "data": data,
        "timestamp": datetime.utcnow().isoformat(),
    }


def error_response(error_spec: ErrorSpec, trace_id: Optional[str] = None) -> dict:
    """Create standardized error response."""
    return {
        "success": False,
        "error": {
            "error_id": error_spec.error_id,
            "code": error_spec.error_code.value,
            "severity": error_spec.severity.value,
            "category": error_spec.category.value,
            "message": error_spec.details.message,
            "retriable": error_spec.details.retry_after_seconds is not None,
            "diagnostics": error_spec.details.technical_message or "",
            "context": error_spec.context.dict(),
            "created_at": error_spec.timestamp.isoformat(),
        },
        "trace_id": trace_id,
        "timestamp": datetime.utcnow().isoformat(),
    }
