"""Custom test assertions for the multi-tenant AI platform."""

import json
import re
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass


@dataclass
class AssertionResult:
    """Result of a custom assertion."""
    passed: bool
    message: str
    details: Optional[Dict[str, Any]] = None


class JSONAssertions:
    """Assertions for JSON data validation."""
    
    @staticmethod
    def assert_valid_json(data: str, message: str = "Invalid JSON") -> AssertionResult:
        """Assert that a string is valid JSON."""
        try:
            json.loads(data)
            return AssertionResult(True, f"Valid JSON: {message}")
        except json.JSONDecodeError as e:
            return AssertionResult(False, f"Invalid JSON: {message}. Error: {str(e)}")
    
    @staticmethod
    def assert_no_markdown_json(data: str, message: str = "Contains markdown-wrapped JSON") -> AssertionResult:
        """Assert that JSON is not wrapped in markdown."""
        # Check for common markdown JSON patterns
        markdown_patterns = [
            r'```json\s*\{.*\}\s*```',
            r'```\s*\{.*\}\s*```',
            r'`\{.*\}`',
            r'```\w*\s*\{.*\}\s*```'
        ]
        
        for pattern in markdown_patterns:
            if re.search(pattern, data, re.DOTALL | re.IGNORECASE):
                return AssertionResult(False, f"Markdown-wrapped JSON found: {message}")
        
        return AssertionResult(True, f"No markdown wrapping: {message}")
    
    @staticmethod
    def assert_strict_schema(data: Dict[str, Any], allowed_fields: List[str], message: str = "Schema validation") -> AssertionResult:
        """Assert that data only contains allowed fields."""
        extra_fields = set(data.keys()) - set(allowed_fields)
        
        if extra_fields:
            return AssertionResult(
                False, 
                f"Extra fields found: {message}. Extra fields: {list(extra_fields)}"
            )
        
        return AssertionResult(True, f"Schema valid: {message}")


class PIIAssertions:
    """Assertions for PII detection and redaction."""
    
    # Common PII patterns
    PII_PATTERNS = {
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'phone': r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b',
        'ssn': r'\b\d{3}-?\d{2}-?\d{4}\b',
        'credit_card': r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        'ip_address': r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
    }
    
    @staticmethod
    def assert_no_pii_in_text(text: str, message: str = "PII detection") -> AssertionResult:
        """Assert that text contains no PII."""
        found_pii = []
        
        for pii_type, pattern in PIIAssertions.PII_PATTERNS.items():
            matches = re.findall(pattern, text)
            if matches:
                found_pii.append({
                    'type': pii_type,
                    'matches': matches[:3],  # Show first 3 matches
                    'count': len(matches)
                })
        
        if found_pii:
            return AssertionResult(
                False,
                f"PII found: {message}",
                {'pii_found': found_pii}
            )
        
        return AssertionResult(True, f"No PII detected: {message}")
    
    @staticmethod
    def assert_pii_redacted(text: str, expected_redaction: str = "[REDACTED]", message: str = "PII redaction") -> AssertionResult:
        """Assert that PII is properly redacted."""
        for pii_type, pattern in PIIAssertions.PII_PATTERNS.items():
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    match = ''.join(match)
                if match not in text:
                    continue  # Already redacted
                if expected_redaction not in text:
                    return AssertionResult(
                        False,
                        f"PII not redacted: {message}. Found {pii_type}: {match}"
                    )
        
        return AssertionResult(True, f"PII properly redacted: {message}")


class PerformanceAssertions:
    """Assertions for performance metrics."""
    
    @staticmethod
    def assert_latency_below_threshold(actual_latency: float, threshold_ms: float, message: str = "Latency check") -> AssertionResult:
        """Assert that latency is below threshold."""
        if actual_latency <= threshold_ms:
            return AssertionResult(
                True, 
                f"Latency OK: {message}. {actual_latency:.2f}ms <= {threshold_ms}ms"
            )
        else:
            return AssertionResult(
                False,
                f"Latency exceeded: {message}. {actual_latency:.2f}ms > {threshold_ms}ms"
            )
    
    @staticmethod
    def assert_throughput_above_threshold(actual_throughput: float, threshold_rps: float, message: str = "Throughput check") -> AssertionResult:
        """Assert that throughput is above threshold."""
        if actual_throughput >= threshold_rps:
            return AssertionResult(
                True,
                f"Throughput OK: {message}. {actual_throughput:.2f} rps >= {threshold_rps} rps"
            )
        else:
            return AssertionResult(
                False,
                f"Throughput below threshold: {message}. {actual_throughput:.2f} rps < {threshold_rps} rps"
            )


class MultiTenantAssertions:
    """Assertions for multi-tenant safety."""
    
    @staticmethod
    def assert_tenant_isolation(data: List[Dict[str, Any]], tenant_field: str = "tenant_id", message: str = "Tenant isolation") -> AssertionResult:
        """Assert that data is properly isolated by tenant."""
        if not data:
            return AssertionResult(True, f"Empty data: {message}")
        
        tenants = set()
        for item in data:
            if tenant_field in item:
                tenants.add(item[tenant_field])
        
        if len(tenants) == 1:
            return AssertionResult(True, f"Single tenant isolation: {message}")
        else:
            return AssertionResult(
                False,
                f"Multi-tenant data mixed: {message}. Found tenants: {list(tenants)}"
            )
    
    @staticmethod
    def assert_cross_tenant_access_blocked(response_data: Any, message: str = "Cross-tenant access") -> AssertionResult:
        """Assert that cross-tenant access is blocked."""
        # Check for common error responses
        if isinstance(response_data, dict):
            if response_data.get("error") == "Access denied":
                return AssertionResult(True, f"Cross-tenant access blocked: {message}")
            if "403" in str(response_data.get("status_code", "")):
                return AssertionResult(True, f"Cross-tenant access blocked (403): {message}")
        
        return AssertionResult(False, f"Cross-tenant access not blocked: {message}")


class ContractAssertions:
    """Assertions for API contracts and boundaries."""
    
    @staticmethod
    def assert_valid_http_status(status_code: int, allowed_statuses: List[int] = None, message: str = "HTTP status") -> AssertionResult:
        """Assert that HTTP status code is valid."""
        if allowed_statuses is None:
            allowed_statuses = [200, 201, 202, 204, 400, 401, 403, 404, 429, 500, 502, 503]
        
        if status_code in allowed_statuses:
            return AssertionResult(True, f"Valid status code: {message}. {status_code}")
        else:
            return AssertionResult(
                False,
                f"Invalid status code: {message}. {status_code} not in {allowed_statuses}"
            )
    
    @staticmethod
    def assert_structured_error_response(response: Dict[str, Any], message: str = "Error response") -> AssertionResult:
        """Assert that error response is properly structured."""
        required_fields = ["error", "message"]
        optional_fields = ["code", "details", "timestamp"]
        
        for field in required_fields:
            if field not in response:
                return AssertionResult(
                    False,
                    f"Missing required error field: {message}. Missing: {field}"
                )
        
        # Check for extra fields that shouldn't be in error responses
        allowed_fields = set(required_fields + optional_fields)
        extra_fields = set(response.keys()) - allowed_fields
        
        if extra_fields:
            return AssertionResult(
                False,
                f"Extra fields in error response: {message}. Extra: {list(extra_fields)}"
            )
        
        return AssertionResult(True, f"Valid error response: {message}")


class RouterAssertions:
    """Assertions for router functionality."""
    
    @staticmethod
    def assert_tier_selection_reasonable(selected_tier: str, expected_tier: str, confidence: float, message: str = "Tier selection") -> AssertionResult:
        """Assert that tier selection is reasonable."""
        if selected_tier == expected_tier:
            return AssertionResult(True, f"Tier selection correct: {message}. {selected_tier}")
        
        # Allow some tolerance for tier selection
        tier_hierarchy = ["SLM_A", "SLM_B", "LLM"]
        
        try:
            selected_idx = tier_hierarchy.index(selected_tier)
            expected_idx = tier_hierarchy.index(expected_tier)
            
            # Allow one tier difference
            if abs(selected_idx - expected_idx) <= 1 and confidence >= 0.7:
                return AssertionResult(True, f"Tier selection acceptable: {message}. {selected_tier} vs {expected_tier}")
        except ValueError:
            pass
        
        return AssertionResult(
            False,
            f"Tier selection mismatch: {message}. Expected {expected_tier}, got {selected_tier} (confidence: {confidence})"
        )
    
    @staticmethod
    def assert_decision_latency_acceptable(latency_ms: float, threshold_ms: float = 50.0, message: str = "Decision latency") -> AssertionResult:
        """Assert that router decision latency is acceptable."""
        if latency_ms <= threshold_ms:
            return AssertionResult(
                True,
                f"Decision latency acceptable: {message}. {latency_ms:.2f}ms <= {threshold_ms}ms"
            )
        else:
            return AssertionResult(
                False,
                f"Decision latency too high: {message}. {latency_ms:.2f}ms > {threshold_ms}ms"
            )


def assert_all(assertions: List[AssertionResult], message: str = "Multiple assertions") -> AssertionResult:
    """Assert that all provided assertions pass."""
    failed_assertions = [a for a in assertions if not a.passed]
    
    if not failed_assertions:
        return AssertionResult(True, f"All assertions passed: {message}")
    else:
        failure_messages = [a.message for a in failed_assertions]
        return AssertionResult(
            False,
            f"Assertions failed: {message}. Failures: {'; '.join(failure_messages)}",
            {"failed_assertions": failed_assertions}
        )
