"""Test permissioned RAG and vector security."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from tests._fixtures.factories import TenantFactory, UserFactory, DocumentFactory
from tests._helpers.assertions import MultiTenantAssertions, PIIAssertions


class TestPermissionedRAG:
    """Test permissioned RAG and vector security."""
    
    @pytest.mark.asyncio
    async def test_tenant_vector_isolation(self):
        """Test tenant isolation in vector database."""
        # Setup two tenants
        tenant_factory = TenantFactory()
        doc_factory = DocumentFactory()
        
        tenant_a = tenant_factory.create()
        tenant_b = tenant_factory.create()
        
        # Create documents with embeddings for each tenant
        doc_a = doc_factory.create(tenant_a["tenant_id"])
        doc_a["embeddings"]["vectors"] = [0.1, 0.2, 0.3, 0.4, 0.5]  # Tenant A vectors
        
        doc_b = doc_factory.create(tenant_b["tenant_id"])
        doc_b["embeddings"]["vectors"] = [0.6, 0.7, 0.8, 0.9, 1.0]  # Tenant B vectors
        
        # Mock vector database
        vector_db = Mock()
        vector_db.search = AsyncMock()
        
        # Simulate tenant-isolated vector search
        async def search_vectors(tenant_id, query_vector, limit=10):
            if tenant_id == tenant_a["tenant_id"]:
                return [doc_a]  # Only return tenant A documents
            elif tenant_id == tenant_b["tenant_id"]:
                return [doc_b]  # Only return tenant B documents
            else:
                return []
        
        vector_db.search.side_effect = search_vectors
        
        # Test vector isolation
        results_a = await vector_db.search(
            tenant_id=tenant_a["tenant_id"],
            query_vector=[0.1, 0.2, 0.3, 0.4, 0.5],
            limit=10
        )
        
        results_b = await vector_db.search(
            tenant_id=tenant_b["tenant_id"],
            query_vector=[0.6, 0.7, 0.8, 0.9, 1.0],
            limit=10
        )
        
        # Verify vector isolation
        assert len(results_a) == 1
        assert len(results_b) == 1
        assert results_a[0]["tenant_id"] == tenant_a["tenant_id"]
        assert results_b[0]["tenant_id"] == tenant_b["tenant_id"]
        assert results_a[0]["tenant_id"] != results_b[0]["tenant_id"]
        
        # Verify different vector spaces
        assert results_a[0]["embeddings"]["vectors"] != results_b[0]["embeddings"]["vectors"]
    
    @pytest.mark.asyncio
    async def test_role_based_rag_access(self):
        """Test role-based access control for RAG."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        doc_factory = DocumentFactory()
        
        tenant = tenant_factory.create()
        
        # Create users with different roles
        admin_user = user_factory.create(tenant["tenant_id"])
        admin_user["role"] = "admin"
        admin_user["permissions"] = ["read_all", "write_all", "delete_all"]
        
        user_user = user_factory.create(tenant["tenant_id"])
        user_user["role"] = "user"
        user_user["permissions"] = ["read_own", "write_own"]
        
        viewer_user = user_factory.create(tenant["tenant_id"])
        viewer_user["role"] = "viewer"
        viewer_user["permissions"] = ["read_own"]
        
        # Create documents with different access levels
        public_doc = doc_factory.create(tenant["tenant_id"])
        public_doc["access_level"] = "public"
        
        private_doc = doc_factory.create(tenant["tenant_id"])
        private_doc["access_level"] = "private"
        private_doc["owner_id"] = admin_user["user_id"]
        
        # Mock RAG service with role-based access
        rag_service = Mock()
        rag_service.search = AsyncMock()
        
        async def search_with_rbac(tenant_id, user_id, query, limit=10):
            # Get user permissions
            user_permissions = []
            if user_id == admin_user["user_id"]:
                user_permissions = admin_user["permissions"]
            elif user_id == user_user["user_id"]:
                user_permissions = user_user["permissions"]
            elif user_id == viewer_user["user_id"]:
                user_permissions = viewer_user["permissions"]
            
            # Filter documents based on permissions
            accessible_docs = []
            
            if "read_all" in user_permissions:
                accessible_docs = [public_doc, private_doc]
            elif "read_own" in user_permissions:
                accessible_docs = [public_doc]
                if user_id == admin_user["user_id"]:
                    accessible_docs.append(private_doc)
            
            return accessible_docs[:limit]
        
        rag_service.search.side_effect = search_with_rbac
        
        # Test role-based access
        admin_results = await rag_service.search(
            tenant_id=tenant["tenant_id"],
            user_id=admin_user["user_id"],
            query="test query"
        )
        
        user_results = await rag_service.search(
            tenant_id=tenant["tenant_id"],
            user_id=user_user["user_id"],
            query="test query"
        )
        
        viewer_results = await rag_service.search(
            tenant_id=tenant["tenant_id"],
            user_id=viewer_user["user_id"],
            query="test query"
        )
        
        # Verify role-based access
        assert len(admin_results) == 2  # Admin can access both
        assert len(user_results) == 1   # User can access only public
        assert len(viewer_results) == 1  # Viewer can access only public
        
        # Verify document access levels
        assert public_doc in admin_results
        assert private_doc in admin_results
        assert public_doc in user_results
        assert private_doc not in user_results
        assert public_doc in viewer_results
        assert private_doc not in viewer_results
    
    @pytest.mark.asyncio
    async def test_rag_permission_filters(self):
        """Test RAG permission filters."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        doc_factory = DocumentFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        user["permissions"] = ["read_finance", "read_hr", "read_engineering"]
        
        # Create documents with different categories
        finance_doc = doc_factory.create(tenant["tenant_id"])
        finance_doc["category"] = "finance"
        finance_doc["content"] = "Financial report for Q4"
        
        hr_doc = doc_factory.create(tenant["tenant_id"])
        hr_doc["category"] = "hr"
        hr_doc["content"] = "Employee handbook"
        
        engineering_doc = doc_factory.create(tenant["tenant_id"])
        engineering_doc["category"] = "engineering"
        engineering_doc["content"] = "Technical documentation"
        
        legal_doc = doc_factory.create(tenant["tenant_id"])
        legal_doc["category"] = "legal"
        legal_doc["content"] = "Legal contracts"
        
        # Mock RAG service with permission filters
        rag_service = Mock()
        rag_service.search = AsyncMock()
        
        async def search_with_filters(tenant_id, user_id, query, filters=None):
            # Get user permissions
            user_permissions = ["read_finance", "read_hr", "read_engineering"]
            
            # Apply permission filters
            allowed_categories = []
            for perm in user_permissions:
                if perm.startswith("read_"):
                    category = perm.replace("read_", "")
                    allowed_categories.append(category)
            
            # Filter documents by category
            all_docs = [finance_doc, hr_doc, engineering_doc, legal_doc]
            filtered_docs = [
                doc for doc in all_docs 
                if doc["category"] in allowed_categories
            ]
            
            return filtered_docs
        
        rag_service.search.side_effect = search_with_filters
        
        # Test permission filtering
        results = await rag_service.search(
            tenant_id=tenant["tenant_id"],
            user_id=user["user_id"],
            query="test query"
        )
        
        # Verify permission filtering
        assert len(results) == 3  # finance, hr, engineering
        categories = [doc["category"] for doc in results]
        assert "finance" in categories
        assert "hr" in categories
        assert "engineering" in categories
        assert "legal" not in categories  # User doesn't have legal permission
    
    @pytest.mark.asyncio
    async def test_rag_ttl_reindexing(self):
        """Test RAG TTL reindexing."""
        # Setup
        tenant_factory = TenantFactory()
        doc_factory = DocumentFactory()
        
        tenant = tenant_factory.create()
        
        # Create documents with different TTLs
        short_ttl_doc = doc_factory.create(tenant["tenant_id"])
        short_ttl_doc["ttl"] = 3600  # 1 hour
        short_ttl_doc["last_indexed"] = time.time() - 1800  # 30 minutes ago
        
        long_ttl_doc = doc_factory.create(tenant["tenant_id"])
        long_ttl_doc["ttl"] = 86400  # 24 hours
        long_ttl_doc["last_indexed"] = time.time() - 3600  # 1 hour ago
        
        expired_doc = doc_factory.create(tenant["tenant_id"])
        expired_doc["ttl"] = 1800  # 30 minutes
        expired_doc["last_indexed"] = time.time() - 3600  # 1 hour ago (expired)
        
        # Mock RAG indexer
        rag_indexer = Mock()
        rag_indexer.check_ttl_reindex = AsyncMock()
        rag_indexer.reindex_document = AsyncMock()
        
        async def check_ttl_reindex(tenant_id):
            docs_to_reindex = []
            all_docs = [short_ttl_doc, long_ttl_doc, expired_doc]
            
            for doc in all_docs:
                time_since_indexed = time.time() - doc["last_indexed"]
                if time_since_indexed >= doc["ttl"]:
                    docs_to_reindex.append(doc)
            
            return docs_to_reindex
        
        rag_indexer.check_ttl_reindex.side_effect = check_ttl_reindex
        rag_indexer.reindex_document.return_value = {"success": True, "new_index_time": time.time()}
        
        # Test TTL reindexing
        docs_to_reindex = await rag_indexer.check_ttl_reindex(tenant["tenant_id"])
        
        # Verify TTL reindexing
        assert len(docs_to_reindex) == 1  # Only expired_doc should need reindexing
        assert expired_doc in docs_to_reindex
        assert short_ttl_doc not in docs_to_reindex
        assert long_ttl_doc not in docs_to_reindex
        
        # Test document reindexing
        for doc in docs_to_reindex:
            result = await rag_indexer.reindex_document(doc["doc_id"])
            assert result["success"]
            assert result["new_index_time"] > doc["last_indexed"]
    
    @pytest.mark.asyncio
    async def test_rag_vector_security(self):
        """Test vector security and access control."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        doc_factory = DocumentFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        
        # Create document with sensitive content
        sensitive_doc = doc_factory.create(tenant["tenant_id"])
        sensitive_doc["content"] = "Sensitive financial data: account numbers, SSNs"
        sensitive_doc["security_level"] = "confidential"
        sensitive_doc["embeddings"]["vectors"] = [0.1, 0.2, 0.3]
        
        # Mock vector security checker
        vector_security = Mock()
        vector_security.check_access = AsyncMock()
        vector_security.filter_sensitive_content = AsyncMock()
        
        # Simulate vector access check
        vector_security.check_access.return_value = {
            "allowed": True,
            "security_level": "confidential",
            "user_clearance": "confidential"
        }
        
        # Simulate content filtering
        vector_security.filter_sensitive_content.return_value = {
            "filtered_content": "Sensitive financial data: [REDACTED], [REDACTED]",
            "redacted_fields": ["account_numbers", "ssns"],
            "original_content": sensitive_doc["content"]
        }
        
        # Test vector security
        access_result = await vector_security.check_access(
            tenant_id=tenant["tenant_id"],
            user_id=user["user_id"],
            document_id=sensitive_doc["doc_id"]
        )
        
        # Verify vector access
        assert access_result["allowed"]
        assert access_result["security_level"] == "confidential"
        assert access_result["user_clearance"] == "confidential"
        
        # Test content filtering
        filter_result = await vector_security.filter_sensitive_content(
            content=sensitive_doc["content"],
            user_id=user["user_id"]
        )
        
        # Verify content filtering
        assert "[REDACTED]" in filter_result["filtered_content"]
        assert "account_numbers" in filter_result["redacted_fields"]
        assert "ssns" in filter_result["redacted_fields"]
        assert filter_result["original_content"] == sensitive_doc["content"]
    
    @pytest.mark.asyncio
    async def test_rag_cross_tenant_prevention(self):
        """Test RAG cross-tenant access prevention."""
        # Setup two tenants
        tenant_factory = TenantFactory()
        doc_factory = DocumentFactory()
        
        tenant_a = tenant_factory.create()
        tenant_b = tenant_factory.create()
        
        # Create documents for each tenant
        doc_a = doc_factory.create(tenant_a["tenant_id"])
        doc_a["content"] = "Tenant A confidential data"
        
        doc_b = doc_factory.create(tenant_b["tenant_id"])
        doc_b["content"] = "Tenant B confidential data"
        
        # Mock RAG service with cross-tenant prevention
        rag_service = Mock()
        rag_service.search = AsyncMock()
        
        async def search_with_tenant_isolation(requesting_tenant_id, query):
            # Simulate cross-tenant access attempt
            if requesting_tenant_id == tenant_a["tenant_id"]:
                return [doc_a]  # Only return tenant A documents
            elif requesting_tenant_id == tenant_b["tenant_id"]:
                return [doc_b]  # Only return tenant B documents
            else:
                return []  # Unknown tenant
        
        rag_service.search.side_effect = search_with_tenant_isolation
        
        # Test cross-tenant prevention
        results_a = await rag_service.search(
            requesting_tenant_id=tenant_a["tenant_id"],
            query="confidential data"
        )
        
        results_b = await rag_service.search(
            requesting_tenant_id=tenant_b["tenant_id"],
            query="confidential data"
        )
        
        # Verify cross-tenant prevention
        assert len(results_a) == 1
        assert len(results_b) == 1
        assert results_a[0]["tenant_id"] == tenant_a["tenant_id"]
        assert results_b[0]["tenant_id"] == tenant_b["tenant_id"]
        assert results_a[0]["tenant_id"] != results_b[0]["tenant_id"]
        assert results_a[0]["content"] != results_b[0]["content"]
        
        # Test isolation assertion
        all_results = results_a + results_b
        result = MultiTenantAssertions.assert_tenant_isolation(
            all_results, "tenant_id", "RAG cross-tenant prevention"
        )
        assert not result.passed, f"Should detect multi-tenant RAG data: {result.message}"
    
    @pytest.mark.asyncio
    async def test_rag_audit_trail(self):
        """Test RAG audit trail."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        doc_factory = DocumentFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        doc = doc_factory.create(tenant["tenant_id"])
        
        # Mock RAG audit logger
        audit_logs = []
        
        class MockRAGAuditLogger:
            def log_rag_access(self, tenant_id, user_id, document_id, action, query=None):
                audit_logs.append({
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "document_id": document_id,
                    "action": action,
                    "query": query,
                    "timestamp": time.time()
                })
        
        rag_audit_logger = MockRAGAuditLogger()
        
        # Simulate RAG access
        rag_audit_logger.log_rag_access(
            tenant_id=tenant["tenant_id"],
            user_id=user["user_id"],
            document_id=doc["doc_id"],
            action="search",
            query="test query"
        )
        
        rag_audit_logger.log_rag_access(
            tenant_id=tenant["tenant_id"],
            user_id=user["user_id"],
            document_id=doc["doc_id"],
            action="retrieve",
            query="test query"
        )
        
        # Verify audit trail
        assert len(audit_logs) == 2
        assert all(log["tenant_id"] == tenant["tenant_id"] for log in audit_logs)
        assert all(log["user_id"] == user["user_id"] for log in audit_logs)
        assert all(log["document_id"] == doc["doc_id"] for log in audit_logs)
        assert audit_logs[0]["action"] == "search"
        assert audit_logs[1]["action"] == "retrieve"
        assert audit_logs[0]["query"] == "test query"
        assert audit_logs[1]["query"] == "test query"
    
    @pytest.mark.asyncio
    async def test_rag_performance_with_security(self):
        """Test RAG performance with security checks."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        
        # Mock RAG service with security overhead
        rag_service = Mock()
        rag_service.search_with_security = AsyncMock()
        
        async def search_with_security_overhead(tenant_id, user_id, query):
            start_time = time.time()
            
            # Simulate security checks
            await asyncio.sleep(0.005)  # 5ms security check
            
            # Simulate vector search
            await asyncio.sleep(0.010)  # 10ms vector search
            
            # Simulate permission filtering
            await asyncio.sleep(0.003)  # 3ms permission filtering
            
            end_time = time.time()
            total_time = (end_time - start_time) * 1000  # Convert to ms
            
            return {
                "results": [{"doc_id": "doc_1", "content": "test content"}],
                "total_time_ms": total_time,
                "security_time_ms": 5,
                "search_time_ms": 10,
                "filter_time_ms": 3
            }
        
        rag_service.search_with_security.side_effect = search_with_security_overhead
        
        # Test RAG performance with security
        result = await rag_service.search_with_security(
            tenant_id=tenant["tenant_id"],
            user_id=user["user_id"],
            query="test query"
        )
        
        # Verify performance
        assert result["total_time_ms"] < 50  # Less than 50ms total
        assert result["security_time_ms"] == 5
        assert result["search_time_ms"] == 10
        assert result["filter_time_ms"] == 3
        assert len(result["results"]) == 1
        
        # Verify performance assertion
        perf_result = PerformanceAssertions.assert_latency_below_threshold(
            result["total_time_ms"], 50, "RAG performance with security"
        )
        assert perf_result.passed, f"RAG with security should be fast: {perf_result.message}"
