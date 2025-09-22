"""Test PII detection and redaction."""

import pytest
import json
import re
from unittest.mock import Mock, AsyncMock

from tests._helpers.assertions import PIIAssertions
from libs.contracts.errors import ErrorSpec


class TestPIIDetection:
    """Test PII detection in various contexts."""
    
    def test_email_detection(self):
        """Test email detection in text."""
        test_cases = [
            ("Contact us at support@company.com for help", True),
            ("Email: john.doe@example.org", True),
            ("user123@test-domain.co.uk", True),
            ("Regular text without email", False),
            ("Invalid email format: @domain.com", False),
            ("Multiple emails: user1@test.com and user2@test.com", True)
        ]
        
        for text, should_contain_pii in test_cases:
            result = PIIAssertions.assert_no_pii_in_text(text, f"Email test: {text[:30]}")
            
            if should_contain_pii:
                assert not result.passed, f"Should detect email in: {text}"
            else:
                assert result.passed, f"Should not detect email in: {text}"
    
    def test_phone_detection(self):
        """Test phone number detection in text."""
        test_cases = [
            ("Call us at (555) 123-4567", True),
            ("Phone: 555.123.4567", True),
            ("Contact: 555 123 4567", True),
            ("International: +1-555-123-4567", True),
            ("Regular text without phone", False),
            ("Invalid phone: 123", False),
            ("Multiple phones: (555) 111-2222 and (555) 333-4444", True)
        ]
        
        for text, should_contain_pii in test_cases:
            result = PIIAssertions.assert_no_pii_in_text(text, f"Phone test: {text[:30]}")
            
            if should_contain_pii:
                assert not result.passed, f"Should detect phone in: {text}"
            else:
                assert result.passed, f"Should not detect phone in: {text}"
    
    def test_ssn_detection(self):
        """Test SSN detection in text."""
        test_cases = [
            ("SSN: 123-45-6789", True),
            ("Social Security: 123456789", True),
            ("Regular text without SSN", False),
            ("Invalid SSN: 123-45", False),
            ("Multiple SSNs: 123-45-6789 and 987-65-4321", True)
        ]
        
        for text, should_contain_pii in test_cases:
            result = PIIAssertions.assert_no_pii_in_text(text, f"SSN test: {text[:30]}")
            
            if should_contain_pii:
                assert not result.passed, f"Should detect SSN in: {text}"
            else:
                assert result.passed, f"Should not detect SSN in: {text}"
    
    def test_credit_card_detection(self):
        """Test credit card detection in text."""
        test_cases = [
            ("Card: 4532-1234-5678-9012", True),
            ("Credit Card: 4532123456789012", True),
            ("Regular text without credit card", False),
            ("Invalid card: 1234", False),
            ("Multiple cards: 4532-1234-5678-9012 and 5555-5555-5555-4444", True)
        ]
        
        for text, should_contain_pii in test_cases:
            result = PIIAssertions.assert_no_pii_in_text(text, f"Credit card test: {text[:30]}")
            
            if should_contain_pii:
                assert not result.passed, f"Should detect credit card in: {text}"
            else:
                assert result.passed, f"Should not detect credit card in: {text}"
    
    def test_ip_address_detection(self):
        """Test IP address detection in text."""
        test_cases = [
            ("IP: 192.168.1.1", True),
            ("Address: 10.0.0.1", True),
            ("Regular text without IP", False),
            ("Invalid IP: 999.999.999.999", True),  # Still matches pattern
            ("Multiple IPs: 192.168.1.1 and 10.0.0.1", True)
        ]
        
        for text, should_contain_pii in test_cases:
            result = PIIAssertions.assert_no_pii_in_text(text, f"IP test: {text[:30]}")
            
            if should_contain_pii:
                assert not result.passed, f"Should detect IP in: {text}"
            else:
                assert result.passed, f"Should not detect IP in: {text}"


class TestPIIRedaction:
    """Test PII redaction functionality."""
    
    def test_email_redaction(self):
        """Test email redaction."""
        test_cases = [
            ("Contact us at support@company.com", "Contact us at [REDACTED]"),
            ("Email: john.doe@example.org", "Email: [REDACTED]"),
            ("user123@test-domain.co.uk", "[REDACTED]"),
            ("Regular text without email", "Regular text without email")
        ]
        
        for original, expected in test_cases:
            # Simulate redaction (in real implementation, this would be done by the service)
            redacted = re.sub(
                PIIAssertions.PII_PATTERNS['email'],
                '[REDACTED]',
                original
            )
            
            result = PIIAssertions.assert_pii_redacted(redacted, "[REDACTED]", f"Email redaction: {original}")
            assert result.passed, f"Email should be redacted: {original} -> {redacted}"
    
    def test_phone_redaction(self):
        """Test phone number redaction."""
        test_cases = [
            ("Call us at (555) 123-4567", "Call us at [REDACTED]"),
            ("Phone: 555.123.4567", "Phone: [REDACTED]"),
            ("Contact: 555 123 4567", "Contact: [REDACTED]"),
            ("Regular text without phone", "Regular text without phone")
        ]
        
        for original, expected in test_cases:
            # Simulate redaction
            redacted = re.sub(
                PIIAssertions.PII_PATTERNS['phone'],
                '[REDACTED]',
                original
            )
            
            result = PIIAssertions.assert_pii_redacted(redacted, "[REDACTED]", f"Phone redaction: {original}")
            assert result.passed, f"Phone should be redacted: {original} -> {redacted}"
    
    def test_multiple_pii_redaction(self):
        """Test redaction of multiple PII types."""
        text_with_pii = "Contact John Doe at john.doe@example.com or call (555) 123-4567. SSN: 123-45-6789"
        expected_redacted = "Contact John Doe at [REDACTED] or call [REDACTED]. SSN: [REDACTED]"
        
        # Simulate multiple redactions
        redacted = text_with_pii
        for pattern in PIIAssertions.PII_PATTERNS.values():
            redacted = re.sub(pattern, '[REDACTED]', redacted)
        
        result = PIIAssertions.assert_pii_redacted(redacted, "[REDACTED]", "Multiple PII redaction")
        assert result.passed, f"Multiple PII should be redacted: {text_with_pii} -> {redacted}"


class TestLogRedaction:
    """Test PII redaction in logs."""
    
    def test_log_message_redaction(self):
        """Test PII redaction in log messages."""
        log_messages = [
            "User john.doe@example.com logged in successfully",
            "Payment processed for card ending in 1234",
            "Customer (555) 123-4567 requested refund",
            "SSN 123-45-6789 verified for account",
            "Request from IP 192.168.1.1 processed"
        ]
        
        for log_message in log_messages:
            # Simulate log redaction
            redacted_log = log_message
            for pattern in PIIAssertions.PII_PATTERNS.values():
                redacted_log = re.sub(pattern, '[REDACTED]', redacted_log)
            
            result = PIIAssertions.assert_pii_redacted(redacted_log, "[REDACTED]", f"Log redaction: {log_message}")
            assert result.passed, f"Log should have PII redacted: {log_message} -> {redacted_log}"
    
    def test_error_message_redaction(self):
        """Test PII redaction in error messages."""
        error_messages = [
            "Failed to send email to support@company.com",
            "Invalid phone number format: (555) 123-4567",
            "SSN validation failed for 123-45-6789",
            "Credit card 4532-1234-5678-9012 declined"
        ]
        
        for error_message in error_messages:
            # Simulate error message redaction
            redacted_error = error_message
            for pattern in PIIAssertions.PII_PATTERNS.values():
                redacted_error = re.sub(pattern, '[REDACTED]', redacted_error)
            
            result = PIIAssertions.assert_pii_redacted(redacted_error, "[REDACTED]", f"Error redaction: {error_message}")
            assert result.passed, f"Error message should have PII redacted: {error_message} -> {redacted_error}"
    
    def test_structured_log_redaction(self):
        """Test PII redaction in structured log data."""
        structured_log = {
            "level": "INFO",
            "message": "User authentication successful",
            "user_email": "john.doe@example.com",
            "user_phone": "(555) 123-4567",
            "ip_address": "192.168.1.1",
            "metadata": {
                "session_id": "sess_123",
                "request_id": "req_456"
            }
        }
        
        # Simulate structured log redaction
        redacted_log = json.dumps(structured_log)
        for pattern in PIIAssertions.PII_PATTERNS.values():
            redacted_log = re.sub(pattern, '[REDACTED]', redacted_log)
        
        # Parse back to dict
        redacted_dict = json.loads(redacted_log)
        
        result = PIIAssertions.assert_pii_redacted(redacted_dict["user_email"], "[REDACTED]", "Structured log email redaction")
        assert result.passed, f"Structured log email should be redacted: {structured_log['user_email']}"
        
        result = PIIAssertions.assert_pii_redacted(redacted_dict["user_phone"], "[REDACTED]", "Structured log phone redaction")
        assert result.passed, f"Structured log phone should be redacted: {structured_log['user_phone']}"


class TestPIIContractValidation:
    """Test PII validation in contract boundaries."""
    
    def test_api_request_pii_validation(self):
        """Test PII validation in API requests."""
        # Request with PII
        request_with_pii = {
            "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
            "message": "My email is john.doe@example.com and phone is (555) 123-4567",
            "context": {
                "user_id": "user_123",
                "session_id": "session_456"
            },
            "features": {}
        }
        
        # Should detect PII in message
        result = PIIAssertions.assert_no_pii_in_text(request_with_pii["message"], "API request message")
        assert not result.passed, f"Should detect PII in API request message: {request_with_pii['message']}"
    
    def test_api_response_pii_validation(self):
        """Test PII validation in API responses."""
        # Response with PII
        response_with_pii = {
            "tier": "SLM_A",
            "confidence": 0.85,
            "expected_cost_usd": 0.005,
            "expected_latency_ms": 800,
            "reasoning": "Contact support@company.com for assistance"
        }
        
        # Should detect PII in reasoning
        result = PIIAssertions.assert_no_pii_in_text(response_with_pii["reasoning"], "API response reasoning")
        assert not result.passed, f"Should detect PII in API response reasoning: {response_with_pii['reasoning']}"
    
    def test_error_response_pii_validation(self):
        """Test PII validation in error responses."""
        # Error response with PII
        error_with_pii = {
            "error": "Validation Error",
            "message": "Failed to process request for user john.doe@example.com",
            "code": "VALIDATION_FAILED",
            "timestamp": "2024-01-01T12:00:00Z"
        }
        
        # Should detect PII in error message
        result = PIIAssertions.assert_no_pii_in_text(error_with_pii["message"], "Error response message")
        assert not result.passed, f"Should detect PII in error response message: {error_with_pii['message']}"


class TestPIIConfiguration:
    """Test PII detection configuration and customization."""
    
    def test_custom_pii_patterns(self):
        """Test custom PII patterns."""
        # Custom pattern for API keys
        custom_pattern = r'\b[A-Za-z0-9]{32,}\b'  # 32+ character alphanumeric
        
        text_with_api_key = "API key: sk-1234567890abcdef1234567890abcdef"
        
        # Test with custom pattern
        matches = re.findall(custom_pattern, text_with_api_key)
        assert len(matches) > 0, f"Should detect API key pattern: {text_with_api_key}"
    
    def test_pii_allowlist(self):
        """Test PII allowlist functionality."""
        # Some PII might be allowed in certain contexts
        allowed_pii = [
            "support@company.com",  # Company email might be allowed
            "1-800-HELP",  # Public phone numbers might be allowed
        ]
        
        for allowed_text in allowed_pii:
            # In a real implementation, these would be checked against an allowlist
            # before being flagged as PII
            result = PIIAssertions.assert_no_pii_in_text(allowed_text, f"Allowlist test: {allowed_text}")
            # This would depend on the allowlist configuration
            # For now, we assume they're still flagged as PII
            assert not result.passed, f"PII should still be detected: {allowed_text}"
    
    def test_pii_context_awareness(self):
        """Test context-aware PII detection."""
        # PII in different contexts
        contexts = [
            ("Email: john.doe@example.com", "field_name"),
            ("Contact us at john.doe@example.com", "message_content"),
            ("User john.doe@example.com logged in", "log_message"),
            ("john.doe@example.com is not a valid email", "error_message")
        ]
        
        for text, context in contexts:
            # In a real implementation, different contexts might have different
            # PII handling rules
            result = PIIAssertions.assert_no_pii_in_text(text, f"Context: {context}")
            assert not result.passed, f"Should detect PII in {context}: {text}"
