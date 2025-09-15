"""Custom exceptions for the AIaaS platform."""

from typing import Optional
from libs.contracts.error import ErrorSpec


class APIException(Exception):
    """Base API exception."""

    def __init__(self, error_spec: ErrorSpec, status_code: int = 500):
        self.error_spec = error_spec
        self.status_code = status_code
        super().__init__(error_spec.message)


class ValidationError(APIException):
    """Validation error exception."""

    def __init__(self, message: str, field: Optional[str] = None):
        error_spec = ErrorSpec(
            code="VALIDATION_FAIL",
            message=message,
            retriable=False,
            diagnostics={"field": field} if field else {},
        )
        super().__init__(error_spec, status_code=422)


class AuthenticationError(APIException):
    """Authentication error exception."""

    def __init__(self, message: str = "Authentication failed"):
        error_spec = ErrorSpec(
            code="AUTHENTICATION_FAILED", message=message, retriable=False
        )
        super().__init__(error_spec, status_code=401)


class AuthorizationError(APIException):
    """Authorization error exception."""

    def __init__(self, message: str = "Authorization failed"):
        error_spec = ErrorSpec(
            code="AUTHORIZATION_FAILED", message=message, retriable=False
        )
        super().__init__(error_spec, status_code=403)
