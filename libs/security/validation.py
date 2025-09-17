"""Input validation and sanitization."""

import re
# import html
from typing import Any, Dict, List, Optional, Union
import structlog
from pydantic import BaseModel, ValidationError
import bleach

logger = structlog.get_logger(__name__)


class InputValidator:
    """Input validation and sanitization."""

    def __init__(self):
        self.max_string_length = 10000
        self.max_array_length = 1000
        self.allowed_html_tags = ["b", "i", "em", "strong", "p", "br"]
        self.sql_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b)",
            r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
            r"(\b(OR|AND)\s+\w+\s*=\s*\w+)",
            r"(\bUNION\s+SELECT\b)",
            r"(\bDROP\s+TABLE\b)",
            r"(\bDELETE\s+FROM\b)",
            r"(\bINSERT\s+INTO\b)",
            r"(\bUPDATE\s+SET\b)",
        ]
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"vbscript:",
            r"onload\s*=",
            r"onerror\s*=",
            r"onclick\s*=",
            r"onmouseover\s*=",
        ]

    def validate_string(self, value: str, max_length: Optional[int] = None) -> str:
        """Validate and sanitize string input."""
        if not isinstance(value, str):
            raise ValueError("Input must be a string")

        max_len = max_length or self.max_string_length
        if len(value) > max_len:
            raise ValueError(f"String too long. Max length: {max_len}")

        # Check for SQL injection
        if self._detect_sql_injection(value):
            raise ValueError("Potential SQL injection detected")

        # Check for XSS
        if self._detect_xss(value):
            raise ValueError("Potential XSS attack detected")

        # Sanitize HTML
        sanitized = bleach.clean(value, tags=self.allowed_html_tags, strip=True)

        return sanitized

    def validate_email(self, email: str) -> str:
        """Validate email address."""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, email):
            raise ValueError("Invalid email format")

        return email.lower().strip()

    def validate_tenant_id(self, tenant_id: str) -> str:
        """Validate tenant ID format."""
        if not isinstance(tenant_id, str):
            raise ValueError("Tenant ID must be a string")

        # UUID format validation
        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        if not re.match(uuid_pattern, tenant_id, re.IGNORECASE):
            raise ValueError("Invalid tenant ID format")

        return tenant_id.lower()

    def validate_api_key(self, api_key: str) -> str:
        """Validate API key format."""
        if not isinstance(api_key, str):
            raise ValueError("API key must be a string")

        if not api_key.startswith("aiaas_"):
            raise ValueError("Invalid API key format")

        if len(api_key) < 32:
            raise ValueError("API key too short")

        return api_key

    def validate_json(self, data: Any) -> Dict[str, Any]:
        """Validate JSON data."""
        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")

        # Check for circular references
        if self._has_circular_reference(data):
            raise ValueError("Circular reference detected")

        # Validate nested data
        return self._validate_nested_data(data)

    def _detect_sql_injection(self, value: str) -> bool:
        """Detect potential SQL injection."""
        value_lower = value.lower()
        for pattern in self.sql_patterns:
            if re.search(pattern, value_lower, re.IGNORECASE):
                return True
        return False

    def _detect_xss(self, value: str) -> bool:
        """Detect potential XSS attack."""
        for pattern in self.xss_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        return False

    def _has_circular_reference(self, data: Any, seen: Optional[set] = None) -> bool:
        """Check for circular references in data."""
        if seen is None:
            seen = set()

        if id(data) in seen:
            return True

        if isinstance(data, dict):
            seen.add(id(data))
            for value in data.values():
                if self._has_circular_reference(value, seen):
                    return True
            seen.remove(id(data))
        elif isinstance(data, list):
            seen.add(id(data))
            for item in data:
                if self._has_circular_reference(item, seen):
                    return True
            seen.remove(id(data))

        return False

    def _validate_nested_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate nested data structures."""
        validated = {}
        for key, value in data.items():
            if isinstance(value, str):
                validated[key] = self.validate_string(value)
            elif isinstance(value, dict):
                validated[key] = self.validate_json(value)
            elif isinstance(value, list):
                validated[key] = self._validate_list(value)
            else:
                validated[key] = value

        return validated

    def _validate_list(self, data: List[Any]) -> List[Any]:
        """Validate list data."""
        if len(data) > self.max_array_length:
            raise ValueError(f"List too long. Max length: {self.max_array_length}")

        validated = []
        for item in data:
            if isinstance(item, str):
                validated.append(self.validate_string(item))
            elif isinstance(item, dict):
                validated.append(self.validate_json(item))
            elif isinstance(item, list):
                validated.append(self._validate_list(item))
            else:
                validated.append(item)

        return validated


# Global validator instance
validator = InputValidator()


# Convenience functions
def sanitize_input(value: str, max_length: Optional[int] = None) -> str:
    """Sanitize input string."""
    return validator.validate_string(value, max_length)


def validate_tenant_id(tenant_id: str) -> str:
    """Validate tenant ID."""
    return validator.validate_tenant_id(tenant_id)


def validate_user_input(data: Any) -> Any:
    """Validate user input."""
    if isinstance(data, str):
        return validator.validate_string(data)
    elif isinstance(data, dict):
        return validator.validate_json(data)
    else:
        return data


def validate_api_key(api_key: str) -> str:
    """Validate API key."""
    return validator.validate_api_key(api_key)
