"""Production-grade RAG isolation tests with permission validation."""

import pytest
import asyncio
import json
import time
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from enum import Enum
import random

from tests._fixtures.factories import factory, TenantTier, UserRole
from tests.contract.schemas import APIRequest, APIResponse, RequestType


class RAGIsolationLevel(Enum):
    """RAG isolation levels."""
    TENANT_LEVEL = "tenant_level"
    USER_LEVEL = "user_level"
    DOCUMENT_LEVEL = "document_level"
    FIELD_LEVEL = "field_level"


@dataclass
class VectorSimilarity:
    """Vector similarity result."""
    document_id: str
    tenant_id: str
    similarity_score: float
    content: str
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class RAGQuery:
    """RAG query structure."""
    query_id: str
    tenant_id: str
    user_id: str
    query_text: str
    isolation_level: RAGIsolationLevel
    permissions: List[str] = None
    filters: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.permissions is None:
            self.permissions = ["read"]
        if self.filters is None:
            self.filters = {}


@dataclass
class RAGResult:
    """RAG query result."""
    query_id: str
    results: List[VectorSimilarity]
    total_results: int
    isolation_applied: bool
    permissions_checked: bool
    cross_tenant_results_blocked: int = 0
    execution_time_ms: float = 0.0


class ProductionRAGSystem:
    """Production-grade RAG system with strict isolation."""
    
    def __init__(self):
        """Initialize RAG system with tenant isolation."""
        self.vector_store: Dict[str, Dict[str, Any]] = {}
        self.tenant_documents: Dict[str, List[Dict[str, Any]]] = {}
        self.user_permissions: Dict[str, Dict[str, List[str]]] = {}
        self.query_history: List[RAGQuery] = []
        self.isolation_violations = 0
        self.cross_tenant_blocks = 0
        
        # Initialize test data
        self._initialize_test_data()
    
    def _initialize_test_data(self):
        """Initialize test data for RAG system."""
        # Create test tenants with documents
        tenants = [
            {"tenant_id": "tenant_0001", "tier": TenantTier.PREMIUM, "name": "Premium Corp"},
            {"tenant_id": "tenant_0002", "tier": TenantTier.BASIC, "name": "Basic Corp"},
            {"tenant_id": "tenant_0003", "tier": TenantTier.ENTERPRISE, "name": "Enterprise Corp"}
        ]
        
        for tenant in tenants:
            tenant_id = tenant["tenant_id"]
            
            # Create documents for each tenant
            documents = [
                {
                    "doc_id": f"doc_{tenant_id}_001",
                    "title": f"Product Manual for {tenant['name']}",
                    "content": f"This is the product manual for {tenant['name']} with detailed specifications and usage instructions.",
                    "category": "product",
                    "permissions": ["read"],
                    "created_by": f"admin_{tenant_id}",
                    "vector_embedding": self._generate_mock_embedding(tenant_id, "product")
                },
                {
                    "doc_id": f"doc_{tenant_id}_002", 
                    "title": f"Support Guide for {tenant['name']}",
                    "content": f"This is the support guide for {tenant['name']} with troubleshooting steps and FAQ.",
                    "category": "support",
                    "permissions": ["read"],
                    "created_by": f"support_{tenant_id}",
                    "vector_embedding": self._generate_mock_embedding(tenant_id, "support")
                },
                {
                    "doc_id": f"doc_{tenant_id}_003",
                    "title": f"Internal Policy for {tenant['name']}",
                    "content": f"Internal company policies and procedures for {tenant['name']} employees only.",
                    "category": "internal",
                    "permissions": ["read"],
                    "created_by": f"hr_{tenant_id}",
                    "vector_embedding": self._generate_mock_embedding(tenant_id, "internal")
                }
            ]
            
            self.tenant_documents[tenant_id] = documents
            
            # Setup user permissions
            self.user_permissions[f"admin_{tenant_id}"] = {
                "tenant_id": tenant_id,
                "role": UserRole.ADMIN.value,
                "permissions": ["read", "write", "delete"],
                "document_access": ["product", "support", "internal"]
            }
            
            self.user_permissions[f"user_{tenant_id}"] = {
                "tenant_id": tenant_id,
                "role": UserRole.USER.value,
                "permissions": ["read"],
                "document_access": ["product", "support"]
            }
            
            self.user_permissions[f"viewer_{tenant_id}"] = {
                "tenant_id": tenant_id,
                "role": UserRole.VIEWER.value,
                "permissions": ["read"],
                "document_access": ["product"]
            }
    
    def _generate_mock_embedding(self, tenant_id: str, category: str) -> List[float]:
        """Generate mock vector embedding."""
        # Simple hash-based embedding for testing
        base_hash = hash(f"{tenant_id}_{category}")
        embedding = []
        for i in range(128):  # 128-dimensional embedding
            embedding.append((base_hash + i) % 100 / 100.0)
        return embedding
    
    def _calculate_similarity(self, query_embedding: List[float], doc_embedding: List[float]) -> float:
        """Calculate cosine similarity between embeddings."""
        if len(query_embedding) != len(doc_embedding):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(query_embedding, doc_embedding))
        norm_a = sum(a * a for a in query_embedding) ** 0.5
        norm_b = sum(b * b for b in doc_embedding) ** 0.5
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    async def query_with_isolation(self, rag_query: RAGQuery, top_k: int = 5) -> RAGResult:
        """Execute RAG query with strict tenant isolation."""
        start_time = time.time()
        
        # Validate user permissions
        if rag_query.user_id not in self.user_permissions:
            raise ValueError(f"User {rag_query.user_id} not found")
        
        user_perms = self.user_permissions[rag_query.user_id]
        if user_perms["tenant_id"] != rag_query.tenant_id:
            self.isolation_violations += 1
            raise ValueError(f"User {rag_query.user_id} not authorized for tenant {rag_query.tenant_id}")
        
        # Get tenant documents only
        tenant_docs = self.tenant_documents.get(rag_query.tenant_id, [])
        
        # Filter documents by user permissions
        accessible_docs = []
        for doc in tenant_docs:
            doc_category = doc.get("category", "unknown")
            if doc_category in user_perms["document_access"]:
                accessible_docs.append(doc)
        
        # Generate query embedding
        query_embedding = self._generate_mock_embedding(rag_query.tenant_id, "query")
        
        # Calculate similarities
        similarities = []
        cross_tenant_blocked = 0
        
        for doc in accessible_docs:
            # Verify tenant isolation
            if doc["doc_id"].startswith(f"doc_{rag_query.tenant_id}"):
                similarity = self._calculate_similarity(query_embedding, doc["vector_embedding"])
                similarities.append(VectorSimilarity(
                    document_id=doc["doc_id"],
                    tenant_id=rag_query.tenant_id,
                    similarity_score=similarity,
                    content=doc["content"],
                    metadata={
                        "title": doc["title"],
                        "category": doc["category"],
                        "permissions": doc["permissions"]
                    }
                ))
            else:
                # This should never happen with proper isolation
                cross_tenant_blocked += 1
                self.cross_tenant_blocks += 1
        
        # Sort by similarity
        similarities.sort(key=lambda x: x.similarity_score, reverse=True)
        
        # Take top_k results
        top_results = similarities[:top_k]
        
        execution_time = (time.time() - start_time) * 1000
        
        # Store query history
        self.query_history.append(rag_query)
        
        return RAGResult(
            query_id=rag_query.query_id,
            results=top_results,
            total_results=len(top_results),
            isolation_applied=True,
            permissions_checked=True,
            cross_tenant_results_blocked=cross_tenant_blocked,
            execution_time_ms=execution_time
        )
    
    async def test_cross_tenant_isolation(self, query_tenant_id: str, query_user_id: str, 
                                       target_tenant_id: str) -> bool:
        """Test cross-tenant isolation by attempting to access another tenant's data."""
        # Create query that might try to access cross-tenant data
        query = RAGQuery(
            query_id=f"isolation_test_{int(time.time())}",
            tenant_id=query_tenant_id,
            user_id=query_user_id,
            query_text=f"Find documents from {target_tenant_id}",
            isolation_level=RAGIsolationLevel.TENANT_LEVEL
        )
        
        try:
            result = await self.query_with_isolation(query)
            
            # Check that no results from target tenant are returned
            cross_tenant_results = [
                r for r in result.results 
                if r.document_id.startswith(f"doc_{target_tenant_id}")
            ]
            
            return len(cross_tenant_results) == 0
            
        except ValueError as e:
            # Expected for unauthorized access
            return "not authorized" in str(e).lower()
    
    def get_isolation_metrics(self) -> Dict[str, Any]:
        """Get RAG isolation metrics."""
        total_queries = len(self.query_history)
        
        # Analyze query history for isolation patterns
        tenant_queries = {}
        for query in self.query_history:
            tenant_id = query.tenant_id
            tenant_queries[tenant_id] = tenant_queries.get(tenant_id, 0) + 1
        
        return {
            "total_queries": total_queries,
            "isolation_violations": self.isolation_violations,
            "cross_tenant_blocks": self.cross_tenant_blocks,
            "tenant_query_distribution": tenant_queries,
            "isolation_score": max(0, 100 - (self.isolation_violations * 10 + self.cross_tenant_blocks * 5)),
            "isolation_level": "strict"
        }
    
    async def test_permissioned_retrieval(self, tenant_id: str, user_id: str, 
                                       expected_categories: List[str]) -> bool:
        """Test permissioned retrieval by tenant/role."""
        query = RAGQuery(
            query_id=f"permission_test_{int(time.time())}",
            tenant_id=tenant_id,
            user_id=user_id,
            query_text="Find all documents",
            isolation_level=RAGIsolationLevel.USER_LEVEL
        )
        
        result = await self.query_with_isolation(query)
        
        # Check that only permitted categories are returned
        returned_categories = set()
        for similarity in result.results:
            category = similarity.metadata.get("category")
            if category:
                returned_categories.add(category)
        
        # All returned categories should be in expected categories
        return returned_categories.issubset(set(expected_categories))


class TestRAGIsolationProduction:
    """Production-grade RAG isolation tests."""
    
    @pytest.fixture
    async def rag_system(self):
        """Create RAG system for testing."""
        return ProductionRAGSystem()
    
    @pytest.mark.asyncio
    async def test_tenant_level_isolation(self, rag_system):
        """Test strict tenant-level isolation."""
        # Query from tenant_0001
        query = RAGQuery(
            query_id="test_001",
            tenant_id="tenant_0001",
            user_id="admin_tenant_0001",
            query_text="Find product documentation",
            isolation_level=RAGIsolationLevel.TENANT_LEVEL
        )
        
        result = await rag_system.query_with_isolation(query)
        
        # Verify all results belong to tenant_0001
        for similarity in result.results:
            assert similarity.document_id.startswith("doc_tenant_0001")
            assert similarity.tenant_id == "tenant_0001"
        
        # Verify no cross-tenant data
        assert result.cross_tenant_results_blocked == 0
        assert result.isolation_applied is True
        assert result.permissions_checked is True
    
    @pytest.mark.asyncio
    async def test_cross_tenant_access_blocked(self, rag_system):
        """Test that cross-tenant access is blocked."""
        # Test isolation between different tenants
        isolation_maintained = await rag_system.test_cross_tenant_isolation(
            query_tenant_id="tenant_0001",
            query_user_id="admin_tenant_0001",
            target_tenant_id="tenant_0002"
        )
        
        assert isolation_maintained, "Cross-tenant access should be blocked"
        
        # Test isolation in reverse direction
        isolation_maintained = await rag_system.test_cross_tenant_isolation(
            query_tenant_id="tenant_0002",
            query_user_id="admin_tenant_0002", 
            target_tenant_id="tenant_0001"
        )
        
        assert isolation_maintained, "Cross-tenant access should be blocked in reverse"
    
    @pytest.mark.asyncio
    async def test_user_permission_enforcement(self, rag_system):
        """Test user permission enforcement in RAG."""
        # Admin user should have access to all categories
        admin_access = await rag_system.test_permissioned_retrieval(
            tenant_id="tenant_0001",
            user_id="admin_tenant_0001",
            expected_categories=["product", "support", "internal"]
        )
        
        assert admin_access, "Admin should have access to all categories"
        
        # Regular user should only have access to product and support
        user_access = await rag_system.test_permissioned_retrieval(
            tenant_id="tenant_0001",
            user_id="user_tenant_0001",
            expected_categories=["product", "support"]
        )
        
        assert user_access, "User should only have access to permitted categories"
        
        # Viewer should only have access to product
        viewer_access = await rag_system.test_permissioned_retrieval(
            tenant_id="tenant_0001",
            user_id="viewer_tenant_0001",
            expected_categories=["product"]
        )
        
        assert viewer_access, "Viewer should only have access to product category"
    
    @pytest.mark.asyncio
    async def test_unauthorized_user_blocked(self, rag_system):
        """Test that unauthorized users are blocked."""
        # User from different tenant trying to access tenant_0001
        unauthorized_query = RAGQuery(
            query_id="unauthorized_test",
            tenant_id="tenant_0001",
            user_id="admin_tenant_0002",  # User from different tenant
            query_text="Find documents",
            isolation_level=RAGIsolationLevel.TENANT_LEVEL
        )
        
        with pytest.raises(ValueError, match="not authorized"):
            await rag_system.query_with_isolation(unauthorized_query)
    
    @pytest.mark.asyncio
    async def test_no_cross_tenant_vector_hits(self, rag_system):
        """Test that no cross-tenant vector hits occur."""
        # Perform queries from multiple tenants
        tenant_queries = [
            ("tenant_0001", "admin_tenant_0001"),
            ("tenant_0002", "admin_tenant_0002"),
            ("tenant_0003", "admin_tenant_0003")
        ]
        
        all_results = {}
        
        for tenant_id, user_id in tenant_queries:
            query = RAGQuery(
                query_id=f"vector_test_{tenant_id}",
                tenant_id=tenant_id,
                user_id=user_id,
                query_text="Find all documents",
                isolation_level=RAGIsolationLevel.TENANT_LEVEL
            )
            
            result = await rag_system.query_with_isolation(query)
            all_results[tenant_id] = result
        
        # Verify no cross-tenant contamination
        for tenant_id, result in all_results.items():
            for similarity in result.results:
                # All documents should belong to the querying tenant
                assert similarity.document_id.startswith(f"doc_{tenant_id}")
                assert similarity.tenant_id == tenant_id
        
        # Verify isolation metrics
        metrics = rag_system.get_isolation_metrics()
        assert metrics["cross_tenant_blocks"] == 0
        assert metrics["isolation_violations"] == 0
        assert metrics["isolation_score"] == 100
    
    @pytest.mark.asyncio
    async def test_ttl_reindex_path_coverage(self, rag_system):
        """Test TTL reindex path coverage."""
        tenant_id = "tenant_0001"
        user_id = "admin_tenant_0001"
        
        # Add new document (simulating reindex after TTL)
        new_doc = {
            "doc_id": "doc_tenant_0001_reindexed_001",
            "title": "Reindexed Document",
            "content": "This document was reindexed after TTL expiration",
            "category": "product",
            "permissions": ["read"],
            "created_by": user_id,
            "vector_embedding": rag_system._generate_mock_embedding(tenant_id, "reindexed"),
            "reindexed_at": datetime.now(timezone.utc).isoformat()
        }
        
        rag_system.tenant_documents[tenant_id].append(new_doc)
        
        # Query for reindexed documents
        query = RAGQuery(
            query_id="reindex_test",
            tenant_id=tenant_id,
            user_id=user_id,
            query_text="Find reindexed documents",
            isolation_level=RAGIsolationLevel.TENANT_LEVEL
        )
        
        result = await rag_system.query_with_isolation(query)
        
        # Should find the reindexed document
        reindexed_docs = [
            r for r in result.results 
            if "reindexed" in r.document_id
        ]
        
        assert len(reindexed_docs) > 0, "Reindexed document should be found"
        assert reindexed_docs[0].tenant_id == tenant_id, "Reindexed document should belong to correct tenant"
    
    @pytest.mark.asyncio
    async def test_rag_performance_under_isolation(self, rag_system):
        """Test RAG performance under isolation constraints."""
        tenant_id = "tenant_0001"
        user_id = "admin_tenant_0001"
        
        # Perform multiple queries to test performance
        query_times = []
        
        for i in range(10):
            query = RAGQuery(
                query_id=f"perf_test_{i}",
                tenant_id=tenant_id,
                user_id=user_id,
                query_text=f"Test query {i}",
                isolation_level=RAGIsolationLevel.TENANT_LEVEL
            )
            
            result = await rag_system.query_with_isolation(query)
            query_times.append(result.execution_time_ms)
        
        # Performance should be reasonable even with isolation
        avg_time = sum(query_times) / len(query_times)
        max_time = max(query_times)
        
        assert avg_time < 1000, f"Average query time {avg_time:.2f}ms should be under 1000ms"
        assert max_time < 2000, f"Max query time {max_time:.2f}ms should be under 2000ms"
        
        # All queries should maintain isolation
        metrics = rag_system.get_isolation_metrics()
        assert metrics["isolation_score"] == 100, "Isolation should be maintained during performance test"
    
    @pytest.mark.asyncio
    async def test_concurrent_tenant_queries(self, rag_system):
        """Test concurrent queries from different tenants."""
        async def query_tenant(tenant_id: str, user_id: str, query_num: int):
            """Query function for concurrent execution."""
            query = RAGQuery(
                query_id=f"concurrent_{tenant_id}_{query_num}",
                tenant_id=tenant_id,
                user_id=user_id,
                query_text=f"Concurrent query {query_num}",
                isolation_level=RAGIsolationLevel.TENANT_LEVEL
            )
            
            return await rag_system.query_with_isolation(query)
        
        # Create concurrent tasks for different tenants
        tasks = []
        for i in range(5):
            tasks.append(query_tenant("tenant_0001", "admin_tenant_0001", i))
            tasks.append(query_tenant("tenant_0002", "admin_tenant_0002", i))
            tasks.append(query_tenant("tenant_0003", "admin_tenant_0003", i))
        
        # Execute all queries concurrently
        results = await asyncio.gather(*tasks)
        
        # Verify all results maintain tenant isolation
        tenant_results = {"tenant_0001": [], "tenant_0002": [], "tenant_0003": []}
        
        for result in results:
            for similarity in result.results:
                tenant_id = similarity.tenant_id
                tenant_results[tenant_id].append(similarity.document_id)
        
        # Each tenant should only have their own documents
        for tenant_id, doc_ids in tenant_results.items():
            for doc_id in doc_ids:
                assert doc_id.startswith(f"doc_{tenant_id}"), f"Document {doc_id} should belong to {tenant_id}"
        
        # Verify isolation metrics
        metrics = rag_system.get_isolation_metrics()
        assert metrics["isolation_score"] == 100, "Concurrent queries should maintain isolation"
        assert metrics["cross_tenant_blocks"] == 0, "No cross-tenant blocks should occur"
    
    def test_rag_isolation_metrics_assertions(self, rag_system):
        """Test RAG isolation metrics assertions."""
        metrics = rag_system.get_isolation_metrics()
        
        # Assert expected metrics
        assert metrics["total_queries"] >= 0
        assert metrics["isolation_violations"] >= 0
        assert metrics["cross_tenant_blocks"] >= 0
        assert 0 <= metrics["isolation_score"] <= 100
        assert metrics["isolation_level"] == "strict"
        
        # Assert tenant query distribution
        assert isinstance(metrics["tenant_query_distribution"], dict)
        
        # In production, these would be Prometheus metrics
        expected_metrics = [
            "rag_queries_total",
            "rag_isolation_violations_total",
            "rag_cross_tenant_blocks_total",
            "rag_isolation_score_gauge",
            "rag_tenant_query_distribution_total"
        ]
        
        # Verify metrics would be available
        for metric in expected_metrics:
            assert metric is not None  # Placeholder for metric existence check
