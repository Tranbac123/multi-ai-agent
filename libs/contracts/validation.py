"""
Contract Validation Utilities

Utilities for validating contracts at service boundaries.
"""

import json
import re
from typing import Any, Dict, List, Optional, Type, Union
from pydantic import BaseModel, ValidationError
import structlog

logger = structlog.get_logger(__name__)


class ContractValidationError(Exception):
    """Contract validation error."""
    
    def __init__(self, message: str, errors: Optional[List[Dict]] = None):
        super().__init__(message)
        self.errors = errors or []


def validate_contract(
    data: Union[Dict, str, bytes],
    contract_class: Type[BaseModel],
    strict: bool = True,
    forbid_extra: bool = True  # noqa: F841
) -> BaseModel:
    """
    Validate data against a contract class.
    
    Args:
        data: Data to validate (dict, JSON string, or bytes)
        contract_class: Pydantic model class to validate against
        strict: Whether to use strict validation
        forbid_extra: Whether to forbid extra fields
        
    Returns:
        Validated contract instance
        
    Raises:
        ContractValidationError: If validation fails
    """
    try:
        # Parse data if it's a string or bytes
        if isinstance(data, (str, bytes)):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as e:
                raise ContractValidationError(f"Invalid JSON: {e}")
        
        # Validate against contract
        if isinstance(data, dict):
            instance = contract_class(**data)
        else:
            # For non-dict data, pass as a single argument
            instance = contract_class.model_validate(data)
        
        # Additional strict validation
        if strict:
            _validate_strict_mode(instance, contract_class)
        
        return instance
        
    except ValidationError as e:
        error_details = []
        for error in e.errors():
            error_details.append({
                'field': '.'.join(str(x) for x in error['loc']),
                'message': error['msg'],
                'type': error['type'],
                'input': error.get('input')
            })
        
        raise ContractValidationError(
            f"Contract validation failed for {contract_class.__name__}",
            errors=error_details
        )
    
    except Exception as e:
        raise ContractValidationError(f"Unexpected validation error: {e}")


def _validate_strict_mode(instance: BaseModel, contract_class: Type[BaseModel]):
    """Perform additional strict validation checks."""
    
    # Check for markdown-JSON patterns (not allowed)
    for field_name, field_value in instance.__dict__.items():
        if isinstance(field_value, str):
            if _contains_markdown_json(field_value):
                raise ContractValidationError(
                    f"Field '{field_name}' contains markdown-JSON, which is not allowed"
                )
        elif isinstance(field_value, dict):
            _check_dict_for_markdown_json(field_value, field_name)
        elif isinstance(field_value, list):
            _check_list_for_markdown_json(field_value, field_name)


def _contains_markdown_json(text: str) -> bool:
    """Check if text contains markdown-JSON patterns."""
    # Patterns that indicate markdown-wrapped JSON
    markdown_json_patterns = [
        r'```json\s*\{.*?\}\s*```',  # JSON in code blocks
        r'```\s*\{.*?\}\s*```',      # JSON in generic code blocks
        r'`\{.*?\}`',                # JSON in inline code
        r'```\w*\s*\{.*?\}\s*```',   # JSON with language specifier
    ]
    
    for pattern in markdown_json_patterns:
        if re.search(pattern, text, re.DOTALL | re.IGNORECASE):
            return True
    
    return False


def _check_dict_for_markdown_json(data: Dict[str, Any], path: str):
    """Recursively check dictionary for markdown-JSON."""
    for key, value in data.items():
        current_path = f"{path}.{key}"
        
        if isinstance(value, str):
            if _contains_markdown_json(value):
                raise ContractValidationError(
                    f"Field '{current_path}' contains markdown-JSON, which is not allowed"
                )
        elif isinstance(value, dict):
            _check_dict_for_markdown_json(value, current_path)
        elif isinstance(value, list):
            _check_list_for_markdown_json(value, current_path)


def _check_list_for_markdown_json(data: List[Any], path: str):
    """Recursively check list for markdown-JSON."""
    for i, value in enumerate(data):
        current_path = f"{path}[{i}]"
        
        if isinstance(value, str):
            if _contains_markdown_json(value):
                raise ContractValidationError(
                    f"Field '{current_path}' contains markdown-JSON, which is not allowed"
                )
        elif isinstance(value, dict):
            _check_dict_for_markdown_json(value, current_path)
        elif isinstance(value, list):
            _check_list_for_markdown_json(value, current_path)


def sanitize_for_logging(data: Any, sensitive_fields: Optional[List[str]] = None) -> Any:
    """
    Sanitize data for logging by redacting sensitive information.
    
    Args:
        data: Data to sanitize
        sensitive_fields: List of field names to redact
        
    Returns:
        Sanitized data
    """
    if sensitive_fields is None:
        sensitive_fields = [
            'password', 'token', 'secret', 'key', 'auth', 'credential',
            'ssn', 'credit_card', 'phone', 'email', 'address'
        ]
    
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            if _is_sensitive_field(key, sensitive_fields):
                sanitized[key] = '[REDACTED]'
            else:
                sanitized[key] = sanitize_for_logging(value, sensitive_fields)
        return sanitized
    
    elif isinstance(data, list):
        return [sanitize_for_logging(item, sensitive_fields) for item in data]
    
    elif isinstance(data, str):
        # Check for PII patterns in strings
        if _contains_pii(data):
            return '[REDACTED]'
        return data
    
    else:
        return data


def _is_sensitive_field(field_name: str, sensitive_fields: List[str]) -> bool:
    """Check if field name indicates sensitive data."""
    field_lower = field_name.lower()
    return any(sensitive in field_lower for sensitive in sensitive_fields)


def _contains_pii(text: str) -> bool:
    """Check if text contains PII patterns."""
    pii_patterns = [
        r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
        r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',  # Credit card
        r'\b\d{3}[\s-]?\d{3}[\s-]?\d{4}\b',  # Phone number
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
    ]
    
    for pattern in pii_patterns:
        if re.search(pattern, text):
            return True
    
    return False


def validate_api_request(
    request_data: Dict[str, Any],
    contract_class: Type[BaseModel],
    endpoint: str
) -> BaseModel:
    """
    Validate API request data against contract.
    
    Args:
        request_data: Request data to validate
        contract_class: Contract class to validate against
        endpoint: API endpoint name for logging
        
    Returns:
        Validated contract instance
        
    Raises:
        ContractValidationError: If validation fails
    """
    try:
        # Sanitize data for logging
        sanitized_data = sanitize_for_logging(request_data)
        
        logger.info(
            "Validating API request",
            endpoint=endpoint,
            contract_class=contract_class.__name__,
            data_keys=list(request_data.keys()) if isinstance(request_data, dict) else None
        )
        
        # Validate contract
        contract = validate_contract(request_data, contract_class, strict=True, forbid_extra=True)
        
        logger.info(
            "API request validation successful",
            endpoint=endpoint,
            contract_class=contract_class.__name__
        )
        
        return contract
        
    except ContractValidationError as e:
        logger.error(
            "API request validation failed",
            endpoint=endpoint,
            contract_class=contract_class.__name__,
            errors=e.errors,
            sanitized_data=sanitize_for_logging(request_data)
        )
        raise
    
    except Exception as e:
        logger.error(
            "Unexpected validation error",
            endpoint=endpoint,
            contract_class=contract_class.__name__,
            error=str(e),
            sanitized_data=sanitize_for_logging(request_data)
        )
        raise ContractValidationError(f"Validation error: {e}")


def validate_api_response(
    response_data: Any,
    contract_class: Type[BaseModel],
    endpoint: str
) -> BaseModel:
    """
    Validate API response data against contract.
    
    Args:
        response_data: Response data to validate
        contract_class: Contract class to validate against
        endpoint: API endpoint name for logging
        
    Returns:
        Validated contract instance
        
    Raises:
        ContractValidationError: If validation fails
    """
    try:
        logger.info(
            "Validating API response",
            endpoint=endpoint,
            contract_class=contract_class.__name__
        )
        
        # Validate contract
        contract = validate_contract(response_data, contract_class, strict=True, forbid_extra=True)
        
        logger.info(
            "API response validation successful",
            endpoint=endpoint,
            contract_class=contract_class.__name__
        )
        
        return contract
        
    except ContractValidationError as e:
        logger.error(
            "API response validation failed",
            endpoint=endpoint,
            contract_class=contract_class.__name__,
            errors=e.errors
        )
        raise
    
    except Exception as e:
        logger.error(
            "Unexpected response validation error",
            endpoint=endpoint,
            contract_class=contract_class.__name__,
            error=str(e)
        )
        raise ContractValidationError(f"Response validation error: {e}")


def create_error_response(
    error: ContractValidationError,
    status_code: int = 400
) -> Dict[str, Any]:
    """
    Create standardized error response from contract validation error.
    
    Args:
        error: Contract validation error
        status_code: HTTP status code
        
    Returns:
        Error response dictionary
    """
    return {
        "error": {
            "type": "contract_validation_error",
            "message": str(error),
            "status_code": status_code,
            "details": error.errors
        },
        "timestamp": None,  # Will be set by API framework
        "request_id": None  # Will be set by API framework
    }


def validate_inter_service_payload(
    payload: Dict[str, Any],
    contract_class: Type[BaseModel],
    service_name: str,
    operation: str
) -> BaseModel:
    """
    Validate inter-service communication payload.
    
    Args:
        payload: Payload to validate
        contract_class: Contract class to validate against
        service_name: Name of the service
        operation: Operation name
        
    Returns:
        Validated contract instance
        
    Raises:
        ContractValidationError: If validation fails
    """
    try:
        logger.debug(
            "Validating inter-service payload",
            service=service_name,
            operation=operation,
            contract_class=contract_class.__name__
        )
        
        # Validate contract
        contract = validate_contract(payload, contract_class, strict=True, forbid_extra=True)
        
        logger.debug(
            "Inter-service payload validation successful",
            service=service_name,
            operation=operation,
            contract_class=contract_class.__name__
        )
        
        return contract
        
    except ContractValidationError as e:
        logger.error(
            "Inter-service payload validation failed",
            service=service_name,
            operation=operation,
            contract_class=contract_class.__name__,
            errors=e.errors
        )
        raise
    
    except Exception as e:
        logger.error(
            "Unexpected inter-service validation error",
            service=service_name,
            operation=operation,
            contract_class=contract_class.__name__,
            error=str(e)
        )
        raise ContractValidationError(f"Inter-service validation error: {e}")
