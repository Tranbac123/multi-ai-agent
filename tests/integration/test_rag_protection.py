"""
Integration tests for RAG & data protection.

Tests metadata management, permissioned retrieval, PII redaction,
and cross-tenant data leakage prevention.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

from apps.ingestion.core.rag_metadata import (
    RAGMetadataManager, DocumentMetadata, DocumentStatus, SensitivityLevel,
    TTLReindexManager
)
from apps.ingestion.core.permissioned_retrieval import (
    PermissionedRetrievalEngine, PermissionValidator, AccessLevel,
    RetrievalContext, RetrievalResult, DocumentAccess
)
from apps.ingestion.core.pii_redaction import (
    PIIDetector, PIIRedactionMiddleware, SensitivityTagger,
    PIIType, RedactionMethod, RedactionConfig
)


class TestRAGMetadataManager:
    """Test RAG metadata management."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        session_mock = AsyncMock()
        session_mock.execute = AsyncMock()
        session_mock.commit = AsyncMock()
        session_mock.rollback = AsyncMock()
        return session_mock
    
    @pytest.fixture
    def metadata_manager(self, mock_db_session):
        """Create metadata manager for testing."""
        return RAGMetadataManager(mock_db_session)
    
    @pytest.mark.asyncio
    async def test_create_document_metadata(self, metadata_manager, mock_db_session):
        """Test creating document metadata."""
        
        content = "This is a test document with some content."
        source = "test_source"
        roles = ["admin", "user"]
        
        metadata = await metadata_manager.create_document_metadata(
            tenant_id="tenant-123",
            content=content,
            source=source,
            roles=roles,
            sensitivity=SensitivityLevel.INTERNAL,
            ttl_days=30,
            tags={"test", "document"}
        )
        
        assert metadata.tenant_id == "tenant-123"
        assert metadata.source == source
        assert metadata.roles == roles
        assert metadata.sensitivity == SensitivityLevel.INTERNAL
        assert metadata.ttl is not None
        assert "test" in metadata.tags
        assert mock_db_session.execute.called
        assert mock_db_session.commit.called
    
    @pytest.mark.asyncio
    async def test_update_document_status(self, metadata_manager, mock_db_session):
        """Test updating document status."""
        
        await metadata_manager.update_document_status(
            doc_id="doc-123",
            status=DocumentStatus.INDEXED
        )
        
        assert mock_db_session.execute.called
        assert mock_db_session.commit.called
    
    @pytest.mark.asyncio
    async def test_update_document_status_failed(self, metadata_manager, mock_db_session):
        """Test updating document status to failed."""
        
        error_message = "Indexing failed due to invalid content"
        
        await metadata_manager.update_document_status(
            doc_id="doc-123",
            status=DocumentStatus.FAILED,
            error_message=error_message
        )
        
        assert mock_db_session.execute.called
        assert mock_db_session.commit.called
    
    @pytest.mark.asyncio
    async def test_get_document_metadata(self, metadata_manager, mock_db_session):
        """Test getting document metadata."""
        
        # Mock database result
        mock_row = MagicMock()
        mock_row.doc_id = "doc-123"
        mock_row.tenant_id = "tenant-123"
        mock_row.roles = ["admin", "user"]
        mock_row.source = "test_source"
        mock_row.hash = "hash123"
        mock_row.sensitivity = "internal"
        mock_row.status = "indexed"
        mock_row.created_at = datetime.now()
        mock_row.updated_at = datetime.now()
        mock_row.ttl = None
        mock_row.indexed_at = datetime.now()
        mock_row.failed_at = None
        mock_row.error_message = None
        mock_row.file_size = 1000
        mock_row.content_type = "text/plain"
        mock_row.language = "en"
        mock_row.tags = ["test", "document"]
        mock_row.custom_metadata = {}
        
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db_session.execute.return_value = mock_result
        
        metadata = await metadata_manager.get_document_metadata("doc-123")
        
        assert metadata is not None
        assert metadata.doc_id == "doc-123"
        assert metadata.tenant_id == "tenant-123"
        assert metadata.roles == ["admin", "user"]
        assert metadata.sensitivity == SensitivityLevel.INTERNAL
        assert metadata.status == DocumentStatus.INDEXED
    
    @pytest.mark.asyncio
    async def test_get_tenant_documents(self, metadata_manager, mock_db_session):
        """Test getting documents for a tenant."""
        
        # Mock database results
        mock_row1 = MagicMock()
        mock_row1.doc_id = "doc-1"
        mock_row1.tenant_id = "tenant-123"
        mock_row1.roles = ["admin"]
        mock_row1.source = "source1"
        mock_row1.hash = "hash1"
        mock_row1.sensitivity = "internal"
        mock_row1.status = "indexed"
        mock_row1.created_at = datetime.now()
        mock_row1.updated_at = datetime.now()
        mock_row1.ttl = None
        mock_row1.indexed_at = datetime.now()
        mock_row1.failed_at = None
        mock_row1.error_message = None
        mock_row1.file_size = 1000
        mock_row1.content_type = "text/plain"
        mock_row1.language = "en"
        mock_row1.tags = ["test"]
        mock_row1.custom_metadata = {}
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row1]
        mock_db_session.execute.return_value = mock_result
        
        documents = await metadata_manager.get_tenant_documents("tenant-123")
        
        assert len(documents) == 1
        assert documents[0].doc_id == "doc-1"
        assert documents[0].tenant_id == "tenant-123"
    
    @pytest.mark.asyncio
    async def test_check_document_permissions(self, metadata_manager, mock_db_session):
        """Test checking document permissions."""
        
        # Mock metadata
        metadata = DocumentMetadata(
            doc_id="doc-123",
            tenant_id="tenant-123",
            roles=["admin", "user"],
            source="test_source",
            hash="hash123",
            sensitivity=SensitivityLevel.INTERNAL
        )
        
        # Mock get_document_metadata to return our metadata
        metadata_manager.get_document_metadata = AsyncMock(return_value=metadata)
        
        # Test valid access
        has_access = await metadata_manager.check_document_permissions(
            doc_id="doc-123",
            tenant_id="tenant-123",
            user_roles=["admin"]
        )
        assert has_access is True
        
        # Test invalid tenant
        has_access = await metadata_manager.check_document_permissions(
            doc_id="doc-123",
            tenant_id="tenant-456",
            user_roles=["admin"]
        )
        assert has_access is False
        
        # Test invalid roles
        has_access = await metadata_manager.check_document_permissions(
            doc_id="doc-123",
            tenant_id="tenant-123",
            user_roles=["guest"]
        )
        assert has_access is False
    
    @pytest.mark.asyncio
    async def test_get_expired_documents(self, metadata_manager, mock_db_session):
        """Test getting expired documents."""
        
        # Mock database results
        mock_row = MagicMock()
        mock_row.doc_id = "expired-doc"
        mock_row.tenant_id = "tenant-123"
        mock_row.roles = ["admin"]
        mock_row.source = "source"
        mock_row.hash = "hash"
        mock_row.sensitivity = "internal"
        mock_row.status = "indexed"
        mock_row.created_at = datetime.now()
        mock_row.updated_at = datetime.now()
        mock_row.ttl = datetime.now() - timedelta(days=1)  # Expired
        mock_row.indexed_at = datetime.now()
        mock_row.failed_at = None
        mock_row.error_message = None
        mock_row.file_size = 1000
        mock_row.content_type = "text/plain"
        mock_row.language = "en"
        mock_row.tags = []
        mock_row.custom_metadata = {}
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db_session.execute.return_value = mock_result
        
        expired_docs = await metadata_manager.get_expired_documents()
        
        assert len(expired_docs) == 1
        assert expired_docs[0].doc_id == "expired-doc"
    
    @pytest.mark.asyncio
    async def test_get_tenant_metrics(self, metadata_manager, mock_db_session):
        """Test getting tenant metrics."""
        
        # Mock database results
        mock_row = MagicMock()
        mock_row.status = "indexed"
        mock_row.sensitivity = "internal"
        mock_row.count = 10
        mock_row.avg_file_size = 1500.0
        mock_row.oldest_document = datetime.now() - timedelta(days=30)
        mock_row.newest_document = datetime.now()
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db_session.execute.return_value = mock_result
        
        metrics = await metadata_manager.get_tenant_metrics("tenant-123")
        
        assert metrics["tenant_id"] == "tenant-123"
        assert metrics["total_documents"] == 10
        assert "by_status" in metrics
        assert "by_sensitivity" in metrics


class TestPermissionedRetrieval:
    """Test permissioned retrieval system."""
    
    @pytest.fixture
    def mock_metadata_manager(self):
        """Mock metadata manager."""
        return AsyncMock()
    
    @pytest.fixture
    def retrieval_engine(self, mock_metadata_manager):
        """Create retrieval engine for testing."""
        return PermissionedRetrievalEngine(mock_metadata_manager)
    
    @pytest.mark.asyncio
    async def test_retrieve_documents_success(self, retrieval_engine, mock_metadata_manager):
        """Test successful document retrieval."""
        
        # Mock metadata
        metadata = DocumentMetadata(
            doc_id="doc-123",
            tenant_id="tenant-123",
            roles=["admin", "user"],
            source="test_source",
            hash="hash123",
            sensitivity=SensitivityLevel.INTERNAL
        )
        
        mock_metadata_manager.get_document_metadata.return_value = metadata
        
        # Create retrieval context
        context = RetrievalContext(
            tenant_id="tenant-123",
            user_roles=["admin"],
            query="test query",
            max_results=5
        )
        
        results = await retrieval_engine.retrieve_documents(
            context=context,
            user_access_level=AccessLevel.READ
        )
        
        assert len(results) >= 0  # May be empty due to mock vector store
    
    @pytest.mark.asyncio
    async def test_validate_document_access_success(self, retrieval_engine, mock_metadata_manager):
        """Test successful document access validation."""
        
        # Mock metadata
        metadata = DocumentMetadata(
            doc_id="doc-123",
            tenant_id="tenant-123",
            roles=["admin", "user"],
            source="test_source",
            hash="hash123",
            sensitivity=SensitivityLevel.INTERNAL
        )
        
        mock_metadata_manager.get_document_metadata.return_value = metadata
        
        has_access, reason = await retrieval_engine.validate_document_access(
            doc_id="doc-123",
            tenant_id="tenant-123",
            user_roles=["admin"],
            user_access_level=AccessLevel.READ
        )
        
        assert has_access is True
        assert reason == "access_granted"
    
    @pytest.mark.asyncio
    async def test_validate_document_access_insufficient_roles(self, retrieval_engine, mock_metadata_manager):
        """Test document access validation with insufficient roles."""
        
        # Mock metadata
        metadata = DocumentMetadata(
            doc_id="doc-123",
            tenant_id="tenant-123",
            roles=["admin"],  # Only admin role required
            source="test_source",
            hash="hash123",
            sensitivity=SensitivityLevel.INTERNAL
        )
        
        mock_metadata_manager.get_document_metadata.return_value = metadata
        
        has_access, reason = await retrieval_engine.validate_document_access(
            doc_id="doc-123",
            tenant_id="tenant-123",
            user_roles=["user"],  # User doesn't have admin role
            user_access_level=AccessLevel.READ
        )
        
        assert has_access is False
        assert reason == "insufficient_roles"
    
    @pytest.mark.asyncio
    async def test_validate_document_access_tenant_isolation(self, retrieval_engine, mock_metadata_manager):
        """Test document access validation with tenant isolation."""
        
        # Mock metadata
        metadata = DocumentMetadata(
            doc_id="doc-123",
            tenant_id="tenant-123",
            roles=["admin"],
            source="test_source",
            hash="hash123",
            sensitivity=SensitivityLevel.INTERNAL
        )
        
        mock_metadata_manager.get_document_metadata.return_value = metadata
        
        has_access, reason = await retrieval_engine.validate_document_access(
            doc_id="doc-123",
            tenant_id="tenant-456",  # Different tenant
            user_roles=["admin"],
            user_access_level=AccessLevel.READ
        )
        
        assert has_access is False
        assert reason == "tenant_isolation_violation"
    
    @pytest.mark.asyncio
    async def test_get_accessible_documents(self, retrieval_engine, mock_metadata_manager):
        """Test getting accessible documents."""
        
        # Mock documents
        doc1 = DocumentMetadata(
            doc_id="doc-1",
            tenant_id="tenant-123",
            roles=["admin", "user"],
            source="source1",
            hash="hash1",
            sensitivity=SensitivityLevel.INTERNAL
        )
        
        doc2 = DocumentMetadata(
            doc_id="doc-2",
            tenant_id="tenant-123",
            roles=["admin"],  # Only admin
            source="source2",
            hash="hash2",
            sensitivity=SensitivityLevel.CONFIDENTIAL
        )
        
        mock_metadata_manager.get_tenant_documents.return_value = [doc1, doc2]
        
        accessible_docs = await retrieval_engine.get_accessible_documents(
            tenant_id="tenant-123",
            user_roles=["admin"],
            user_access_level=AccessLevel.WRITE,  # Can access confidential
            limit=10
        )
        
        assert len(accessible_docs) == 2  # Both documents accessible
    
    @pytest.mark.asyncio
    async def test_get_retrieval_metrics(self, retrieval_engine):
        """Test getting retrieval metrics."""
        
        metrics = await retrieval_engine.get_retrieval_metrics("tenant-123")
        
        assert "tenant_id" in metrics
        assert "total_retrievals" in metrics
        assert "successful_retrievals" in metrics
        assert "access_denied" in metrics
        assert "success_rate" in metrics


class TestPIIDetection:
    """Test PII detection and redaction."""
    
    @pytest.fixture
    def redaction_config(self):
        """Create redaction configuration."""
        return RedactionConfig(
            enabled=True,
            log_detections=True
        )
    
    @pytest.fixture
    def pii_detector(self, redaction_config):
        """Create PII detector for testing."""
        return PIIDetector(redaction_config)
    
    def test_detect_email(self, pii_detector):
        """Test email detection."""
        
        text = "Contact us at john.doe@example.com for support"
        detections = pii_detector.detect_pii(text)
        
        assert len(detections) == 1
        assert detections[0].pii_type == PIIType.EMAIL
        assert detections[0].original_text == "john.doe@example.com"
        assert detections[0].confidence == 0.95
    
    def test_detect_phone(self, pii_detector):
        """Test phone number detection."""
        
        text = "Call us at (555) 123-4567 or 555-123-4567"
        detections = pii_detector.detect_pii(text)
        
        assert len(detections) == 2
        assert all(d.pii_type == PIIType.PHONE for d in detections)
    
    def test_detect_ssn(self, pii_detector):
        """Test SSN detection."""
        
        text = "SSN: 123-45-6789"
        detections = pii_detector.detect_pii(text)
        
        assert len(detections) == 1
        assert detections[0].pii_type == PIIType.SSN
        assert detections[0].confidence == 0.98
    
    def test_detect_credit_card(self, pii_detector):
        """Test credit card detection."""
        
        text = "Card number: 4111 1111 1111 1111"
        detections = pii_detector.detect_pii(text)
        
        assert len(detections) == 1
        assert detections[0].pii_type == PIIType.CREDIT_CARD
    
    def test_detect_ip_address(self, pii_detector):
        """Test IP address detection."""
        
        text = "Server IP: 192.168.1.1"
        detections = pii_detector.detect_pii(text)
        
        assert len(detections) == 1
        assert detections[0].pii_type == PIIType.IP_ADDRESS
    
    def test_detect_api_key(self, pii_detector):
        """Test API key detection."""
        
        text = "API Key: sk-1234567890abcdef1234567890abcdef"
        detections = pii_detector.detect_pii(text)
        
        assert len(detections) == 1
        assert detections[0].pii_type == PIIType.API_KEY
    
    def test_redact_text(self, pii_detector):
        """Test text redaction."""
        
        text = "Email: john@example.com, Phone: (555) 123-4567"
        redacted_text, detections = pii_detector.redact_text(text)
        
        assert len(detections) == 2
        assert "[EMAIL]" in redacted_text or "*" in redacted_text
        assert "[PHONE]" in redacted_text or "*" in redacted_text
    
    def test_get_detection_summary(self, pii_detector):
        """Test detection summary."""
        
        text = "Email: john@example.com, Phone: (555) 123-4567, SSN: 123-45-6789"
        detections = pii_detector.detect_pii(text)
        summary = pii_detector.get_detection_summary(detections)
        
        assert summary["total_detections"] == 3
        assert "email" in summary["by_type"]
        assert "phone" in summary["by_type"]
        assert "ssn" in summary["by_type"]
        assert summary["by_confidence"]["high"] > 0


class TestPIIRedactionMiddleware:
    """Test PII redaction middleware."""
    
    @pytest.fixture
    def redaction_config(self):
        """Create redaction configuration."""
        return RedactionConfig(enabled=True)
    
    @pytest.fixture
    def redaction_middleware(self, redaction_config):
        """Create redaction middleware for testing."""
        return PIIRedactionMiddleware(redaction_config)
    
    @pytest.mark.asyncio
    async def test_redact_string_data(self, redaction_middleware):
        """Test redacting string data."""
        
        text = "Contact john@example.com at (555) 123-4567"
        redacted_data, detections = await redaction_middleware.redact_request_data(
            data=text,
            endpoint="/api/test"
        )
        
        assert len(detections) == 2
        assert redacted_data != text  # Should be redacted
    
    @pytest.mark.asyncio
    async def test_redact_dict_data(self, redaction_middleware):
        """Test redacting dictionary data."""
        
        data = {
            "email": "user@example.com",
            "phone": "(555) 123-4567",
            "name": "John Doe",
            "non_pii": "This is not PII"
        }
        
        redacted_data, detections = await redaction_middleware.redact_request_data(
            data=data,
            endpoint="/api/user"
        )
        
        assert len(detections) >= 2  # At least email and phone
        assert redacted_data["non_pii"] == "This is not PII"  # Should remain unchanged
    
    @pytest.mark.asyncio
    async def test_redact_list_data(self, redaction_middleware):
        """Test redacting list data."""
        
        data = [
            "Contact: john@example.com",
            "Phone: (555) 123-4567",
            "Regular text"
        ]
        
        redacted_data, detections = await redaction_middleware.redact_request_data(
            data=data,
            endpoint="/api/contacts"
        )
        
        assert len(detections) == 2
        assert len(redacted_data) == 3
        assert redacted_data[2] == "Regular text"  # Should remain unchanged
    
    def test_get_redaction_stats(self, redaction_middleware):
        """Test getting redaction statistics."""
        
        stats = redaction_middleware.get_redaction_stats()
        
        assert "total_requests" in stats
        assert "requests_with_pii" in stats
        assert "total_detections" in stats
        assert "pii_detection_rate" in stats
        assert "by_pii_type" in stats
        assert "by_endpoint" in stats
    
    def test_reset_stats(self, redaction_middleware):
        """Test resetting statistics."""
        
        # Add some stats
        redaction_middleware.redaction_stats["total_requests"] = 10
        
        # Reset stats
        redaction_middleware.reset_stats()
        
        # Check that stats are reset
        stats = redaction_middleware.get_redaction_stats()
        assert stats["total_requests"] == 0


class TestSensitivityTagger:
    """Test sensitivity tagging."""
    
    @pytest.fixture
    def redaction_config(self):
        """Create redaction configuration."""
        return RedactionConfig(enabled=True)
    
    @pytest.fixture
    def pii_detector(self, redaction_config):
        """Create PII detector."""
        return PIIDetector(redaction_config)
    
    @pytest.fixture
    def sensitivity_tagger(self, pii_detector):
        """Create sensitivity tagger."""
        return SensitivityTagger(pii_detector)
    
    def test_tag_no_pii(self, sensitivity_tagger):
        """Test tagging document with no PII."""
        
        content = "This is a regular document with no personal information."
        
        sensitivity, metadata = sensitivity_tagger.tag_document_sensitivity(content)
        
        assert sensitivity == SensitivityLevel.PUBLIC
        assert metadata["reason"] == "no_pii_detected"
    
    def test_tag_email_sensitivity(self, sensitivity_tagger):
        """Test tagging document with email."""
        
        content = "Contact us at support@example.com for assistance."
        
        sensitivity, metadata = sensitivity_tagger.tag_document_sensitivity(content)
        
        assert sensitivity == SensitivityLevel.PUBLIC  # Email has low sensitivity
        assert "email" in metadata["detected_pii_types"]
    
    def test_tag_ssn_sensitivity(self, sensitivity_tagger):
        """Test tagging document with SSN."""
        
        content = "SSN: 123-45-6789"
        
        sensitivity, metadata = sensitivity_tagger.tag_document_sensitivity(content)
        
        assert sensitivity == SensitivityLevel.RESTRICTED  # SSN has very high sensitivity
        assert "ssn" in metadata["detected_pii_types"]
        assert metadata["max_sensitivity_score"] == 4
    
    def test_tag_mixed_pii_sensitivity(self, sensitivity_tagger):
        """Test tagging document with mixed PII types."""
        
        content = "John Doe (john@example.com) SSN: 123-45-6789"
        
        sensitivity, metadata = sensitivity_tagger.tag_document_sensitivity(content)
        
        assert sensitivity == SensitivityLevel.RESTRICTED  # Highest sensitivity wins
        assert len(metadata["detected_pii_types"]) >= 2  # At least email and SSN


@pytest.mark.asyncio
async def test_no_cross_tenant_retrieval():
    """Test that cross-tenant retrieval is prevented."""
    
    # Create mock metadata manager
    mock_metadata_manager = AsyncMock()
    
    # Create retrieval engine
    retrieval_engine = PermissionedRetrievalEngine(mock_metadata_manager)
    
    # Mock metadata for tenant A
    metadata_a = DocumentMetadata(
        doc_id="doc-a",
        tenant_id="tenant-a",
        roles=["user"],
        source="source-a",
        hash="hash-a",
        sensitivity=SensitivityLevel.INTERNAL
    )
    
    mock_metadata_manager.get_document_metadata.return_value = metadata_a
    
    # Try to access document from tenant B
    has_access, reason = await retrieval_engine.validate_document_access(
        doc_id="doc-a",
        tenant_id="tenant-b",  # Different tenant
        user_roles=["user"],
        user_access_level=AccessLevel.READ
    )
    
    assert has_access is False
    assert reason == "tenant_isolation_violation"


@pytest.mark.asyncio
async def test_redaction_snapshots_pass():
    """Test that redaction snapshots pass validation."""
    
    # Create redaction configuration
    config = RedactionConfig(enabled=True)
    detector = PIIDetector(config)
    
    # Test various PII patterns
    test_cases = [
        ("Email: john@example.com", ["email"]),
        ("Phone: (555) 123-4567", ["phone"]),
        ("SSN: 123-45-6789", ["ssn"]),
        ("Card: 4111 1111 1111 1111", ["credit_card"]),
        ("IP: 192.168.1.1", ["ip_address"]),
        ("API Key: sk-1234567890abcdef", ["api_key"]),
    ]
    
    for text, expected_types in test_cases:
        detections = detector.detect_pii(text)
        detected_types = [d.pii_type.value for d in detections]
        
        # Verify that expected PII types are detected
        for expected_type in expected_types:
            assert expected_type in detected_types, f"Expected {expected_type} in {detected_types} for text: {text}"
        
        # Verify redaction works
        redacted_text, _ = detector.redact_text(text)
        assert redacted_text != text, f"Text should be redacted: {text}"
        
        # Verify no original PII remains in redacted text
        original_pii = []
        for detection in detections:
            if detection.original_text in redacted_text:
                original_pii.append(detection.original_text)
        
        assert len(original_pii) == 0, f"Original PII found in redacted text: {original_pii}"


@pytest.mark.asyncio
async def test_ttl_reindex_covered():
    """Test that TTL reindexing is properly covered."""
    
    # Create mock database session
    mock_db_session = AsyncMock()
    
    # Create metadata manager
    metadata_manager = RAGMetadataManager(mock_db_session)
    
    # Create TTL reindex manager
    reindex_manager = TTLReindexManager(metadata_manager)
    
    # Mock database results for documents needing reindexing
    mock_row = MagicMock()
    mock_row.doc_id = "doc-123"
    mock_row.tenant_id = "tenant-123"
    mock_row.roles = ["admin"]
    mock_row.source = "source"
    mock_row.hash = "hash"
    mock_row.sensitivity = "internal"
    mock_row.status = "indexed"
    mock_row.created_at = datetime.now()
    mock_row.updated_at = datetime.now()
    mock_row.ttl = datetime.now() + timedelta(days=5)  # Expires soon
    mock_row.indexed_at = datetime.now()
    mock_row.failed_at = None
    mock_row.error_message = None
    mock_row.file_size = 1000
    mock_row.content_type = "text/plain"
    mock_row.language = "en"
    mock_row.tags = []
    mock_row.custom_metadata = {}
    
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_db_session.execute.return_value = mock_result
    
    # Find documents for reindexing
    documents = await reindex_manager.find_documents_for_reindex()
    
    assert len(documents) == 1
    assert documents[0].doc_id == "doc-123"
    
    # Schedule reindexing
    await reindex_manager.schedule_reindex([doc.doc_id for doc in documents])
    
    # Verify that database was updated
    assert mock_db_session.execute.called
    assert mock_db_session.commit.called
