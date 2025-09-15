"""Integration tests for RAG/Memory functionality."""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch
from hypothesis import given, strategies as st

from apps.ingestion_service.core.document_processor import DocumentProcessor
from apps.ingestion_service.core.vector_store import VectorStore
from apps.ingestion_service.core.memory_manager import MemoryManager


class TestRAGPermissionedRetrieval:
    """Test RAG permissioned retrieval functionality."""

    @pytest.mark.asyncio
    async def test_tenant_filtered_retrieval(self):
        """Test retrieval filtered by tenant."""
        vector_store = VectorStore()
        memory_manager = MemoryManager()

        # Store documents for different tenants
        doc1 = {
            "id": "doc_001",
            "content": "Tenant 1 specific information",
            "tenant_id": "tenant_001",
            "metadata": {"category": "internal"},
        }

        doc2 = {
            "id": "doc_002",
            "content": "Tenant 2 specific information",
            "tenant_id": "tenant_002",
            "metadata": {"category": "internal"},
        }

        # Store documents
        await vector_store.store_document(doc1)
        await vector_store.store_document(doc2)

        # Retrieve for tenant_001
        results1 = await memory_manager.retrieve_documents(
            query="specific information", tenant_id="tenant_001", limit=10
        )

        # Retrieve for tenant_002
        results2 = await memory_manager.retrieve_documents(
            query="specific information", tenant_id="tenant_002", limit=10
        )

        # Results should be tenant-isolated
        assert len(results1) == 1
        assert results1[0]["tenant_id"] == "tenant_001"
        assert "Tenant 1" in results1[0]["content"]

        assert len(results2) == 1
        assert results2[0]["tenant_id"] == "tenant_002"
        assert "Tenant 2" in results2[0]["content"]

    @pytest.mark.asyncio
    async def test_role_filtered_retrieval(self):
        """Test retrieval filtered by user role."""
        memory_manager = MemoryManager()

        # Store documents with different access levels
        doc1 = {
            "id": "doc_001",
            "content": "Public information",
            "tenant_id": "tenant_001",
            "access_level": "public",
            "metadata": {"category": "general"},
        }

        doc2 = {
            "id": "doc_002",
            "content": "Admin only information",
            "tenant_id": "tenant_001",
            "access_level": "admin",
            "metadata": {"category": "sensitive"},
        }

        # Store documents
        await memory_manager.store_document(doc1)
        await memory_manager.store_document(doc2)

        # Retrieve as regular user
        user_results = await memory_manager.retrieve_documents(
            query="information", tenant_id="tenant_001", user_role="user", limit=10
        )

        # Retrieve as admin
        admin_results = await memory_manager.retrieve_documents(
            query="information", tenant_id="tenant_001", user_role="admin", limit=10
        )

        # Regular user should only see public docs
        assert len(user_results) == 1
        assert user_results[0]["access_level"] == "public"

        # Admin should see all docs
        assert len(admin_results) == 2
        access_levels = [doc["access_level"] for doc in admin_results]
        assert "public" in access_levels
        assert "admin" in access_levels

    @pytest.mark.asyncio
    async def test_cross_tenant_isolation(self):
        """Test that cross-tenant retrieval returns zero results."""
        memory_manager = MemoryManager()

        # Store document for tenant_001
        doc = {
            "id": "doc_001",
            "content": "Sensitive tenant 1 data",
            "tenant_id": "tenant_001",
            "metadata": {"sensitive": True},
        }

        await memory_manager.store_document(doc)

        # Try to retrieve from different tenant
        results = await memory_manager.retrieve_documents(
            query="sensitive data", tenant_id="tenant_002", limit=10  # Different tenant
        )

        # Should return zero results
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_stale_index_ttl_reindex(self):
        """Test stale index TTL and reindexing."""
        vector_store = VectorStore(ttl_seconds=1)  # 1 second TTL
        memory_manager = MemoryManager()

        # Store document
        doc = {
            "id": "doc_001",
            "content": "Test document",
            "tenant_id": "tenant_001",
            "metadata": {"version": "1.0"},
        }

        await vector_store.store_document(doc)

        # Verify document is retrievable
        results = await memory_manager.retrieve_documents(
            query="test document", tenant_id="tenant_001", limit=10
        )
        assert len(results) == 1

        # Wait for TTL to expire
        await asyncio.sleep(1.1)

        # Document should be stale
        is_stale = await vector_store.is_document_stale("doc_001")
        assert is_stale is True

        # Trigger reindex
        await vector_store.reindex_stale_documents()

        # Document should be fresh again
        is_stale = await vector_store.is_document_stale("doc_001")
        assert is_stale is False

    @pytest.mark.asyncio
    async def test_document_versioning(self):
        """Test document versioning and updates."""
        memory_manager = MemoryManager()

        # Store initial document
        doc_v1 = {
            "id": "doc_001",
            "content": "Original content",
            "tenant_id": "tenant_001",
            "version": "1.0",
            "metadata": {"author": "user1"},
        }

        await memory_manager.store_document(doc_v1)

        # Update document
        doc_v2 = {
            "id": "doc_001",
            "content": "Updated content",
            "tenant_id": "tenant_001",
            "version": "2.0",
            "metadata": {"author": "user1", "updated": True},
        }

        await memory_manager.update_document(doc_v2)

        # Retrieve latest version
        results = await memory_manager.retrieve_documents(
            query="content", tenant_id="tenant_001", limit=10
        )

        assert len(results) == 1
        assert results[0]["version"] == "2.0"
        assert "Updated content" in results[0]["content"]
        assert results[0]["metadata"]["updated"] is True

    @pytest.mark.asyncio
    async def test_semantic_search_accuracy(self):
        """Test semantic search accuracy."""
        memory_manager = MemoryManager()

        # Store documents with different topics
        docs = [
            {
                "id": "doc_001",
                "content": "Python programming tutorial",
                "tenant_id": "tenant_001",
                "metadata": {"topic": "programming"},
            },
            {
                "id": "doc_002",
                "content": "Cooking recipes for beginners",
                "tenant_id": "tenant_001",
                "metadata": {"topic": "cooking"},
            },
            {
                "id": "doc_003",
                "content": "Machine learning algorithms",
                "tenant_id": "tenant_001",
                "metadata": {"topic": "programming"},
            },
        ]

        for doc in docs:
            await memory_manager.store_document(doc)

        # Search for programming-related content
        results = await memory_manager.retrieve_documents(
            query="software development", tenant_id="tenant_001", limit=10
        )

        # Should return programming-related docs
        assert len(results) >= 2
        programming_docs = [
            doc for doc in results if doc["metadata"]["topic"] == "programming"
        ]
        assert len(programming_docs) >= 2

    @pytest.mark.asyncio
    async def test_memory_context_retrieval(self):
        """Test memory context retrieval for conversations."""
        memory_manager = MemoryManager()

        # Store conversation history
        conversation = [
            {
                "id": "msg_001",
                "content": "Hello, I need help with my order",
                "tenant_id": "tenant_001",
                "user_id": "user_001",
                "session_id": "session_001",
                "timestamp": time.time() - 3600,
                "metadata": {"type": "user_message"},
            },
            {
                "id": "msg_002",
                "content": "I can help you with that. What's your order number?",
                "tenant_id": "tenant_001",
                "user_id": "user_001",
                "session_id": "session_001",
                "timestamp": time.time() - 3500,
                "metadata": {"type": "agent_response"},
            },
            {
                "id": "msg_003",
                "content": "My order number is 12345",
                "tenant_id": "tenant_001",
                "user_id": "user_001",
                "session_id": "session_001",
                "timestamp": time.time() - 3400,
                "metadata": {"type": "user_message"},
            },
        ]

        for msg in conversation:
            await memory_manager.store_conversation_message(msg)

        # Retrieve conversation context
        context = await memory_manager.get_conversation_context(
            session_id="session_001", tenant_id="tenant_001", limit=10
        )

        assert len(context) == 3
        assert context[0]["content"] == "Hello, I need help with my order"
        assert (
            context[1]["content"]
            == "I can help you with that. What's your order number?"
        )
        assert context[2]["content"] == "My order number is 12345"

    @pytest.mark.asyncio
    async def test_memory_cleanup_old_data(self):
        """Test memory cleanup for old data."""
        memory_manager = MemoryManager(retention_days=1)

        # Store old conversation
        old_msg = {
            "id": "msg_old",
            "content": "Old message",
            "tenant_id": "tenant_001",
            "user_id": "user_001",
            "session_id": "session_001",
            "timestamp": time.time() - 86400 * 2,  # 2 days ago
            "metadata": {"type": "user_message"},
        }

        await memory_manager.store_conversation_message(old_msg)

        # Store recent conversation
        recent_msg = {
            "id": "msg_recent",
            "content": "Recent message",
            "tenant_id": "tenant_001",
            "user_id": "user_001",
            "session_id": "session_001",
            "timestamp": time.time() - 3600,  # 1 hour ago
            "metadata": {"type": "user_message"},
        }

        await memory_manager.store_conversation_message(recent_msg)

        # Cleanup old data
        await memory_manager.cleanup_old_data()

        # Old message should be removed, recent should remain
        context = await memory_manager.get_conversation_context(
            session_id="session_001", tenant_id="tenant_001", limit=10
        )

        assert len(context) == 1
        assert context[0]["content"] == "Recent message"

    @pytest.mark.asyncio
    async def test_document_embedding_consistency(self):
        """Test document embedding consistency."""
        vector_store = VectorStore()

        # Store same document multiple times
        doc = {
            "id": "doc_001",
            "content": "Consistent content",
            "tenant_id": "tenant_001",
            "metadata": {"test": True},
        }

        # Store document
        await vector_store.store_document(doc)

        # Get embedding
        embedding1 = await vector_store.get_document_embedding("doc_001")

        # Store same document again
        await vector_store.store_document(doc)

        # Get embedding again
        embedding2 = await vector_store.get_document_embedding("doc_001")

        # Embeddings should be consistent
        assert embedding1 is not None
        assert embedding2 is not None
        assert len(embedding1) == len(embedding2)

    @pytest.mark.asyncio
    async def test_memory_performance_under_load(self):
        """Test memory performance under load."""
        memory_manager = MemoryManager()

        # Store many documents
        documents = []
        for i in range(100):
            doc = {
                "id": f"doc_{i:03d}",
                "content": f"Document content {i}",
                "tenant_id": "tenant_001",
                "metadata": {"index": i},
            }
            documents.append(doc)

        # Store documents concurrently
        start_time = time.time()
        await asyncio.gather(*[memory_manager.store_document(doc) for doc in documents])
        store_time = time.time() - start_time

        # Should complete within reasonable time
        assert store_time < 10.0  # 10 seconds

        # Retrieve documents concurrently
        start_time = time.time()
        results = await asyncio.gather(
            *[
                memory_manager.retrieve_documents(
                    query=f"content {i}", tenant_id="tenant_001", limit=1
                )
                for i in range(10)
            ]
        )
        retrieve_time = time.time() - start_time

        # Should complete within reasonable time
        assert retrieve_time < 5.0  # 5 seconds

        # All retrievals should find their documents
        for i, result in enumerate(results):
            assert len(result) >= 1
            assert f"content {i}" in result[0]["content"]
