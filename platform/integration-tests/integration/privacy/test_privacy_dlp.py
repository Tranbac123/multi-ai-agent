"""Integration tests for Privacy & DLP features."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from libs.utils.security.pii_detector import PIIDetector, PIIType, SensitivityLevel
from libs.utils.security.field_encryption import FieldEncryptionManager, EncryptionAlgorithm, KeyRotationStatus
from apps.ingestion.core.sensitivity_tagger import SensitivityTagger, DocumentSensitivity, DataCategory
from libs.middleware.privacy_middleware import PrivacyMiddleware, PrivacyValidator


class TestPIIDetector:
    """Test PII detection functionality."""
    
    @pytest.fixture
    def pii_detector(self):
        """Create PIIDetector instance for testing."""
        return PIIDetector()
    
    def test_detect_email(self, pii_detector):
        """Test email detection."""
        text = "Contact us at john.doe@example.com for more information."
        
        result = pii_detector.detect_pii(text)
        
        assert result.has_pii is True
        assert len(result.detections) == 1
        assert result.detections[0].pii_type == PIIType.EMAIL
        assert result.detections[0].value == "john.doe@example.com"
        assert result.detections[0].confidence > 0.8
    
    def test_detect_phone(self, pii_detector):
        """Test phone number detection."""
        text = "Call us at (555) 123-4567 or +1-555-123-4567."
        
        result = pii_detector.detect_pii(text)
        
        assert result.has_pii is True
        assert len(result.detections) >= 1
        phone_detections = [d for d in result.detections if d.pii_type == PIIType.PHONE]
        assert len(phone_detections) >= 1
    
    def test_detect_credit_card(self, pii_detector):
        """Test credit card detection."""
        # Valid credit card number (Visa test number)
        text = "Payment with card 4111111111111111"
        
        result = pii_detector.detect_pii(text)
        
        assert result.has_pii is True
        cc_detections = [d for d in result.detections if d.pii_type == PIIType.CREDIT_CARD]
        assert len(cc_detections) >= 1
        assert cc_detections[0].confidence > 0.9
    
    def test_detect_ssn(self, pii_detector):
        """Test SSN detection."""
        text = "Social Security Number: 123-45-6789"
        
        result = pii_detector.detect_pii(text)
        
        assert result.has_pii is True
        ssn_detections = [d for d in result.detections if d.pii_type == PIIType.SSN]
        assert len(ssn_detections) >= 1
        assert ssn_detections[0].value == "123-45-6789"
    
    def test_no_pii_detection(self, pii_detector):
        """Test text with no PII."""
        text = "This is a regular text with no sensitive information."
        
        result = pii_detector.detect_pii(text)
        
        assert result.has_pii is False
        assert len(result.detections) == 0
        assert result.redacted_text == text
    
    def test_redaction(self, pii_detector):
        """Test PII redaction."""
        text = "Email: john@example.com, Phone: (555) 123-4567"
        
        result = pii_detector.detect_pii(text)
        
        assert result.has_pii is True
        assert "***@***.***" in result.redacted_text
        assert "***-***-****" in result.redacted_text
    
    def test_sensitivity_score_calculation(self, pii_detector):
        """Test sensitivity score calculation."""
        text = "SSN: 123-45-6789, Credit Card: 4111111111111111"
        
        result = pii_detector.detect_pii(text)
        
        assert result.has_pii is True
        assert result.sensitivity_score > 0.8  # Should be high due to critical PII
    
    def test_pii_summary(self, pii_detector):
        """Test PII summary generation."""
        text = "Email: john@example.com, SSN: 123-45-6789"
        
        result = pii_detector.detect_pii(text)
        summary = pii_detector.get_pii_summary(result.detections)
        
        assert summary["total_detections"] == 2
        assert PIIType.EMAIL.value in summary["pii_types_found"]
        assert PIIType.SSN.value in summary["pii_types_found"]
        assert "critical" in summary["sensitivity_levels"]
        assert "medium" in summary["sensitivity_levels"]


class TestFieldEncryptionManager:
    """Test field-level encryption functionality."""
    
    @pytest.fixture
    async def encryption_manager(self):
        """Create FieldEncryptionManager instance for testing."""
        return FieldEncryptionManager()
    
    @pytest.mark.asyncio
    async def test_encrypt_field(self, encryption_manager):
        """Test field encryption."""
        value = "sensitive data"
        tenant_id = "test-tenant"
        field_name = "password"
        
        encrypted_field = await encryption_manager.encrypt_field(value, tenant_id, field_name)
        
        assert encrypted_field.encrypted_data != value
        assert encrypted_field.key_id is not None
        assert encrypted_field.algorithm == EncryptionAlgorithm.FERNET
        assert encrypted_field.key_version == 1
    
    @pytest.mark.asyncio
    async def test_decrypt_field(self, encryption_manager):
        """Test field decryption."""
        value = "sensitive data"
        tenant_id = "test-tenant"
        field_name = "password"
        
        # Encrypt field
        encrypted_field = await encryption_manager.encrypt_field(value, tenant_id, field_name)
        
        # Decrypt field
        decrypted_value = await encryption_manager.decrypt_field(encrypted_field)
        
        assert decrypted_value == value
    
    @pytest.mark.asyncio
    async def test_encrypt_dict_field(self, encryption_manager):
        """Test encryption of dictionary field."""
        value = {"username": "john", "role": "admin"}
        tenant_id = "test-tenant"
        field_name = "user_data"
        
        encrypted_field = await encryption_manager.encrypt_field(value, tenant_id, field_name)
        decrypted_value = await encryption_manager.decrypt_field(encrypted_field)
        
        assert decrypted_value == value
        assert isinstance(decrypted_value, dict)
    
    @pytest.mark.asyncio
    async def test_key_rotation(self, encryption_manager):
        """Test key rotation."""
        tenant_id = "test-tenant"
        field_name = "password"
        
        # Create initial key
        old_key_id = await encryption_manager._get_or_create_key(tenant_id, field_name)
        
        # Rotate key
        new_key_id = await encryption_manager.rotate_key(tenant_id, field_name)
        
        assert new_key_id != old_key_id
        assert new_key_id in encryption_manager.key_cache
    
    @pytest.mark.asyncio
    async def test_reencrypt_with_new_key(self, encryption_manager):
        """Test re-encryption with new key."""
        value = "sensitive data"
        tenant_id = "test-tenant"
        field_name = "password"
        
        # Encrypt with old key
        encrypted_field = await encryption_manager.encrypt_field(value, tenant_id, field_name)
        old_key_id = encrypted_field.key_id
        
        # Rotate key
        new_key_id = await encryption_manager.rotate_key(tenant_id, field_name)
        
        # Re-encrypt with new key
        new_encrypted_field = await encryption_manager.reencrypt_with_new_key(
            encrypted_field, new_key_id
        )
        
        assert new_encrypted_field.key_id == new_key_id
        assert new_encrypted_field.key_id != old_key_id
        
        # Verify decryption works with new key
        decrypted_value = await encryption_manager.decrypt_field(new_encrypted_field)
        assert decrypted_value == value
    
    @pytest.mark.asyncio
    async def test_encryption_summary(self, encryption_manager):
        """Test encryption summary generation."""
        tenant_id = "test-tenant"
        
        # Create some encrypted fields
        await encryption_manager.encrypt_field("data1", tenant_id, "field1")
        await encryption_manager.encrypt_field("data2", tenant_id, "field2")
        
        summary = await encryption_manager.get_encryption_summary(tenant_id)
        
        assert summary["tenant_id"] == tenant_id
        assert summary["total_fields_encrypted"] >= 2
        assert "keys_by_status" in summary
        assert "keys_needing_rotation" in summary


class TestSensitivityTagger:
    """Test sensitivity tagging functionality."""
    
    @pytest.fixture
    async def sensitivity_tagger(self):
        """Create SensitivityTagger instance for testing."""
        return SensitivityTagger()
    
    @pytest.mark.asyncio
    async def test_tag_document_with_pii(self, sensitivity_tagger):
        """Test tagging document with PII."""
        document_id = "doc-1"
        content = "User John Doe with email john.doe@example.com and SSN 123-45-6789"
        tenant_id = "tenant-1"
        
        tag = await sensitivity_tagger.tag_document(document_id, content, tenant_id)
        
        assert tag.document_id == document_id
        assert tag.pii_detected is True
        assert PIIType.EMAIL in tag.pii_types
        assert PIIType.SSN in tag.pii_types
        assert tag.sensitivity_level in [DocumentSensitivity.CONFIDENTIAL, DocumentSensitivity.RESTRICTED]
        assert DataCategory.PERSONAL_IDENTIFIABLE_INFO in tag.data_categories
    
    @pytest.mark.asyncio
    async def test_tag_document_with_financial_data(self, sensitivity_tagger):
        """Test tagging document with financial data."""
        document_id = "doc-2"
        content = "Bank account number 1234567890 and credit card payment of $1000"
        tenant_id = "tenant-1"
        
        tag = await sensitivity_tagger.tag_document(document_id, content, tenant_id)
        
        assert tag.document_id == document_id
        assert DataCategory.FINANCIAL_DATA in tag.data_categories
        assert tag.sensitivity_level in [DocumentSensitivity.CONFIDENTIAL, DocumentSensitivity.RESTRICTED]
    
    @pytest.mark.asyncio
    async def test_tag_document_with_healthcare_data(self, sensitivity_tagger):
        """Test tagging document with healthcare data."""
        document_id = "doc-3"
        content = "Patient medical record shows diagnosis of diabetes and prescription for insulin"
        tenant_id = "tenant-1"
        
        tag = await sensitivity_tagger.tag_document(document_id, content, tenant_id)
        
        assert tag.document_id == document_id
        assert DataCategory.HEALTHCARE_DATA in tag.data_categories
        assert tag.sensitivity_level in [DocumentSensitivity.CONFIDENTIAL, DocumentSensitivity.RESTRICTED]
    
    @pytest.mark.asyncio
    async def test_tag_document_no_sensitive_data(self, sensitivity_tagger):
        """Test tagging document with no sensitive data."""
        document_id = "doc-4"
        content = "This is a regular document with no sensitive information."
        tenant_id = "tenant-1"
        
        tag = await sensitivity_tagger.tag_document(document_id, content, tenant_id)
        
        assert tag.document_id == document_id
        assert tag.pii_detected is False
        assert len(tag.pii_types) == 0
        assert tag.sensitivity_level == DocumentSensitivity.PUBLIC
        assert len(tag.data_categories) == 0
    
    @pytest.mark.asyncio
    async def test_bulk_tag_documents(self, sensitivity_tagger):
        """Test bulk tagging of multiple documents."""
        documents = [
            {"document_id": "doc-1", "content": "Email: john@example.com"},
            {"document_id": "doc-2", "content": "SSN: 123-45-6789"},
            {"document_id": "doc-3", "content": "Regular content"}
        ]
        tenant_id = "tenant-1"
        
        tags = await sensitivity_tagger.bulk_tag_documents(documents, tenant_id)
        
        assert len(tags) == 3
        assert tags[0].pii_detected is True
        assert tags[1].pii_detected is True
        assert tags[2].pii_detected is False
    
    @pytest.mark.asyncio
    async def test_get_sensitivity_summary(self, sensitivity_tagger):
        """Test sensitivity summary generation."""
        tenant_id = "tenant-1"
        
        # Tag some documents
        await sensitivity_tagger.tag_document("doc-1", "Email: john@example.com", tenant_id)
        await sensitivity_tagger.tag_document("doc-2", "SSN: 123-45-6789", tenant_id)
        await sensitivity_tagger.tag_document("doc-3", "Regular content", tenant_id)
        
        summary = await sensitivity_tagger.get_sensitivity_summary(tenant_id)
        
        assert summary["tenant_id"] == tenant_id
        assert summary["total_documents"] == 3
        assert "sensitivity_distribution" in summary
        assert "data_categories" in summary
        assert "pii_detection_stats" in summary
        assert summary["pii_detection_stats"]["documents_with_pii"] == 2


class TestPrivacyMiddleware:
    """Test privacy middleware functionality."""
    
    @pytest.fixture
    async def privacy_middleware(self):
        """Create PrivacyMiddleware instance for testing."""
        pii_detector = PIIDetector()
        field_encryption = FieldEncryptionManager()
        sensitivity_tagger = SensitivityTagger()
        
        return PrivacyMiddleware(pii_detector, field_encryption, sensitivity_tagger)
    
    @pytest.mark.asyncio
    async def test_extract_tenant_id_from_headers(self, privacy_middleware):
        """Test tenant ID extraction from headers."""
        request = MagicMock()
        request.headers = {"X-Tenant-ID": "test-tenant"}
        
        tenant_id = await privacy_middleware._extract_tenant_id(request)
        
        assert tenant_id == "test-tenant"
    
    @pytest.mark.asyncio
    async def test_protect_string_with_pii(self, privacy_middleware):
        """Test string protection with PII."""
        content = "Email: john@example.com, Phone: (555) 123-4567"
        tenant_id = "test-tenant"
        user_id = "user-1"
        request = MagicMock()
        
        protected_content = await privacy_middleware._protect_string(
            content, tenant_id, user_id, request
        )
        
        # Should contain redacted content
        assert "***@***.***" in protected_content or "***-***-****" in protected_content
    
    @pytest.mark.asyncio
    async def test_protect_string_no_pii(self, privacy_middleware):
        """Test string protection without PII."""
        content = "Regular content with no sensitive information"
        tenant_id = "test-tenant"
        user_id = "user-1"
        request = MagicMock()
        
        protected_content = await privacy_middleware._protect_string(
            content, tenant_id, user_id, request
        )
        
        assert protected_content == content
    
    def test_should_encrypt_field(self, privacy_middleware):
        """Test field encryption requirement check."""
        # Should encrypt password field
        assert privacy_middleware._should_encrypt_field("password", "secret123") is True
        
        # Should encrypt secret field
        assert privacy_middleware._should_encrypt_field("api_secret", "abc123") is True
        
        # Should not encrypt regular field
        assert privacy_middleware._should_encrypt_field("username", "john") is False
    
    @pytest.mark.asyncio
    async def test_encrypt_field_value(self, privacy_middleware):
        """Test field value encryption."""
        value = "secret123"
        tenant_id = "test-tenant"
        field_name = "password"
        
        encrypted = await privacy_middleware._encrypt_field_value(value, tenant_id, field_name)
        
        assert encrypted["encrypted"] is True
        assert "value" in encrypted
    
    def test_get_privacy_stats(self, privacy_middleware):
        """Test privacy statistics."""
        # Update some stats
        privacy_middleware.redaction_stats["total_requests"] = 100
        privacy_middleware.redaction_stats["pii_redacted"] = 20
        privacy_middleware.redaction_stats["encryption_applied"] = 10
        
        stats = privacy_middleware.get_privacy_stats()
        
        assert stats["total_requests"] == 100
        assert stats["pii_redacted"] == 20
        assert stats["encryption_applied"] == 10
        assert stats["pii_redaction_rate"] == 20.0
        assert stats["encryption_rate"] == 10.0


class TestPrivacyValidator:
    """Test privacy validator functionality."""
    
    @pytest.fixture
    async def privacy_validator(self):
        """Create PrivacyValidator instance for testing."""
        pii_detector = PIIDetector()
        sensitivity_tagger = SensitivityTagger()
        
        return PrivacyValidator(pii_detector, sensitivity_tagger)
    
    @pytest.mark.asyncio
    async def test_validate_request_with_allowed_pii(self, privacy_validator):
        """Test validation of request with allowed PII."""
        request = MagicMock()
        request.body.return_value = b'{"email": "john@example.com", "phone": "(555) 123-4567"}'
        tenant_id = "test-tenant"
        
        result = await privacy_validator.validate_request_privacy(request, tenant_id)
        
        assert result["compliant"] is True
        assert result["pii_detected"] is True
        assert len(result["violations"]) == 0
    
    @pytest.mark.asyncio
    async def test_validate_request_with_disallowed_pii(self, privacy_validator):
        """Test validation of request with disallowed PII."""
        request = MagicMock()
        request.body.return_value = b'{"ssn": "123-45-6789", "credit_card": "4111111111111111"}'
        tenant_id = "test-tenant"
        
        result = await privacy_validator.validate_request_privacy(request, tenant_id)
        
        assert result["compliant"] is False
        assert result["pii_detected"] is True
        assert len(result["violations"]) > 0
        assert any(v["type"] == "pii_not_allowed" for v in result["violations"])
    
    @pytest.mark.asyncio
    async def test_validate_request_no_pii(self, privacy_validator):
        """Test validation of request with no PII."""
        request = MagicMock()
        request.body.return_value = b'{"username": "john", "role": "user"}'
        tenant_id = "test-tenant"
        
        result = await privacy_validator.validate_request_privacy(request, tenant_id)
        
        assert result["compliant"] is True
        assert result["pii_detected"] is False
        assert len(result["violations"]) == 0


class TestPrivacyDLPIntegration:
    """Integration tests for Privacy & DLP features."""
    
    @pytest.mark.asyncio
    async def test_pii_detection_and_redaction_workflow(self):
        """Test complete PII detection and redaction workflow."""
        # This would test the full integration scenario
        # where PII is detected, redacted, and logged
        
        # Setup PII detector
        # Process document with PII
        # Verify detection and redaction
        # Verify logging and metrics
        
        pass  # Implementation would require full integration setup
    
    @pytest.mark.asyncio
    async def test_field_encryption_workflow(self):
        """Test complete field encryption workflow."""
        # This would test the full integration scenario
        # where sensitive fields are encrypted and decrypted
        
        # Setup encryption manager
        # Encrypt sensitive fields
        # Verify encryption and key management
        # Test key rotation
        
        pass  # Implementation would require full integration setup
    
    @pytest.mark.asyncio
    async def test_sensitivity_tagging_workflow(self):
        """Test complete sensitivity tagging workflow."""
        # This would test the full integration scenario
        # where documents are automatically tagged for sensitivity
        
        # Setup sensitivity tagger
        # Process various document types
        # Verify automatic tagging
        # Test policy-based tagging
        
        pass  # Implementation would require full integration setup
    
    @pytest.mark.asyncio
    async def test_privacy_middleware_workflow(self):
        """Test complete privacy middleware workflow."""
        # This would test the full integration scenario
        # where API responses are automatically protected
        
        # Setup privacy middleware
        # Process API requests with sensitive data
        # Verify automatic protection
        # Test compliance validation
        
        pass  # Implementation would require full integration setup
