# RAG Permissions Testing

## 🔍 **Overview**

This document defines RAG (Retrieval-Augmented Generation) permissions testing for the Multi-AI-Agent platform, covering tenant isolation, role-based access control, and vector database security.

## 🎯 **RAG Security Objectives**

### **Primary Goals**

- **Tenant Isolation**: Ensure complete data separation between tenants
- **Role-Based Access**: Enforce permission-based document retrieval
- **Vector Security**: Prevent cross-tenant vector hits
- **Data Privacy**: Maintain document-level access controls

### **RAG Security Layers**

- **Collection Isolation**: Tenant-specific vector collections
- **Document Permissions**: Role-based document access
- **Query Filtering**: Tenant and role-based query filtering
- **Result Validation**: Cross-tenant hit prevention

## 🏗️ **RAG Architecture**

### **Vector Database Structure**

```python
class RAGArchitecture:
    """RAG architecture with security layers."""

    def __init__(self):
        self.collections = {
            "tenant_123": "tenant_123_knowledge",
            "tenant_456": "tenant_456_knowledge",
            "tenant_789": "tenant_789_knowledge"
        }

        self.document_permissions = {
            "public": ["admin", "user", "guest"],
            "internal": ["admin", "user"],
            "confidential": ["admin"]
        }

        self.role_hierarchies = {
            "admin": ["admin", "user", "guest"],
            "user": ["user", "guest"],
            "guest": ["guest"]
        }
```

### **Vector Collection Isolation**

```python
class VectorCollectionIsolation:
    """Ensures tenant isolation in vector collections."""

    def __init__(self, vector_db):
        self.vector_db = vector_db
        self.tenant_collections = {}

    def create_tenant_collection(self, tenant_id: str):
        """Create isolated collection for tenant."""
        collection_name = f"{tenant_id}_knowledge"

        # Create collection with tenant-specific configuration
        collection_config = {
            "name": collection_name,
            "vectors": {
                "size": 1536,  # OpenAI embedding size
                "distance": "Cosine"
            },
            "payload_schema": {
                "tenant_id": "keyword",
                "document_id": "keyword",
                "permissions": "keyword",
                "created_at": "datetime",
                "updated_at": "datetime"
            }
        }

        self.vector_db.create_collection(collection_config)
        self.tenant_collections[tenant_id] = collection_name

        return collection_name

    def get_tenant_collection(self, tenant_id: str) -> str:
        """Get tenant-specific collection."""
        if tenant_id not in self.tenant_collections:
            return self.create_tenant_collection(tenant_id)

        return self.tenant_collections[tenant_id]

    def validate_tenant_access(self, tenant_id: str, collection_name: str) -> bool:
        """Validate tenant access to collection."""
        expected_collection = f"{tenant_id}_knowledge"
        return collection_name == expected_collection
```

## 🔐 **Permission-Based Document Retrieval**

### **Document Permission System**

```python
class DocumentPermissionSystem:
    """Manages document-level permissions."""

    def __init__(self):
        self.permission_levels = {
            "public": 0,
            "internal": 1,
            "confidential": 2,
            "restricted": 3
        }

        self.role_permissions = {
            "admin": [0, 1, 2, 3],  # All levels
            "user": [0, 1],         # Public and internal
            "guest": [0]            # Public only
        }

    def check_document_access(self, user_role: str, document_permission: str) -> bool:
        """Check if user role can access document permission level."""
        if user_role not in self.role_permissions:
            return False

        permission_level = self.permission_levels.get(document_permission, 999)
        user_levels = self.role_permissions[user_role]

        return permission_level in user_levels

    def filter_documents_by_permission(self, documents: List[dict], user_role: str) -> List[dict]:
        """Filter documents based on user permissions."""
        filtered_documents = []

        for doc in documents:
            doc_permission = doc.get("permission", "public")
            if self.check_document_access(user_role, doc_permission):
                filtered_documents.append(doc)

        return filtered_documents
```

### **Query Permission Filtering**

```python
class QueryPermissionFilter:
    """Filters queries based on user permissions."""

    def __init__(self, permission_system: DocumentPermissionSystem):
        self.permission_system = permission_system

    def build_permission_filter(self, tenant_id: str, user_role: str) -> dict:
        """Build permission filter for vector query."""
        # Get user's permission levels
        user_permissions = self.permission_system.role_permissions.get(user_role, [])

        # Build filter for vector database
        permission_filter = {
            "must": [
                {
                    "key": "tenant_id",
                    "match": {"value": tenant_id}
                },
                {
                    "key": "permission",
                    "match": {"any": user_permissions}
                }
            ]
        }

        return permission_filter

    def validate_query_permissions(self, query: dict, tenant_id: str, user_role: str) -> bool:
        """Validate query has proper permission filters."""
        # Check tenant filter
        if "tenant_id" not in query.get("filter", {}):
            return False

        if query["filter"]["tenant_id"] != tenant_id:
            return False

        # Check permission filter
        if "permission" not in query.get("filter", {}):
            return False

        user_permissions = self.permission_system.role_permissions.get(user_role, [])
        query_permissions = query["filter"]["permission"]

        # Ensure query only requests accessible permissions
        for perm in query_permissions:
            if perm not in user_permissions:
                return False

        return True
```

## 🧪 **RAG Permission Tests**

### **Tenant Isolation Tests**

```python
class TenantIsolationTests:
    """Test tenant isolation in RAG system."""

    @pytest.mark.asyncio
    async def test_tenant_collection_isolation(self):
        """Test that tenants can only access their own collections."""
        # Create test data for different tenants
        tenant_a_docs = [
            {"id": "doc_a1", "content": "Tenant A document 1", "tenant_id": "tenant_a"},
            {"id": "doc_a2", "content": "Tenant A document 2", "tenant_id": "tenant_a"}
        ]

        tenant_b_docs = [
            {"id": "doc_b1", "content": "Tenant B document 1", "tenant_id": "tenant_b"},
            {"id": "doc_b2", "content": "Tenant B document 2", "tenant_id": "tenant_b"}
        ]

        # Index documents for each tenant
        await rag_service.index_documents("tenant_a", tenant_a_docs)
        await rag_service.index_documents("tenant_b", tenant_b_docs)

        # Query from tenant A
        results_a = await rag_service.search("tenant_a", "document 1", user_role="user")

        # Verify tenant A only gets their documents
        assert len(results_a) > 0
        for result in results_a:
            assert result["tenant_id"] == "tenant_a"
            assert "tenant_b" not in result["content"]

        # Query from tenant B
        results_b = await rag_service.search("tenant_b", "document 1", user_role="user")

        # Verify tenant B only gets their documents
        assert len(results_b) > 0
        for result in results_b:
            assert result["tenant_id"] == "tenant_b"
            assert "tenant_a" not in result["content"]

    @pytest.mark.asyncio
    async def test_cross_tenant_vector_hits(self):
        """Test prevention of cross-tenant vector hits."""
        # Create similar documents in different tenants
        tenant_a_doc = {
            "id": "doc_a1",
            "content": "How to reset password for user account",
            "tenant_id": "tenant_a"
        }

        tenant_b_doc = {
            "id": "doc_b1",
            "content": "How to reset password for user account",
            "tenant_id": "tenant_b"
        }

        # Index documents
        await rag_service.index_documents("tenant_a", [tenant_a_doc])
        await rag_service.index_documents("tenant_b", [tenant_b_doc])

        # Query from tenant A
        results_a = await rag_service.search("tenant_a", "reset password", user_role="user")

        # Verify no cross-tenant hits
        for result in results_a:
            assert result["tenant_id"] == "tenant_a"
            assert result["tenant_id"] != "tenant_b"

        # Query from tenant B
        results_b = await rag_service.search("tenant_b", "reset password", user_role="user")

        # Verify no cross-tenant hits
        for result in results_b:
            assert result["tenant_id"] == "tenant_b"
            assert result["tenant_id"] != "tenant_a"

    @pytest.mark.asyncio
    async def test_tenant_context_validation(self):
        """Test tenant context validation in queries."""
        # Test missing tenant context
        with pytest.raises(TenantContextError):
            await rag_service.search(None, "test query", user_role="user")

        # Test invalid tenant context
        with pytest.raises(TenantContextError):
            await rag_service.search("invalid_tenant", "test query", user_role="user")

        # Test empty tenant context
        with pytest.raises(TenantContextError):
            await rag_service.search("", "test query", user_role="user")
```

### **Role-Based Access Tests**

```python
class RoleBasedAccessTests:
    """Test role-based access control in RAG system."""

    @pytest.mark.asyncio
    async def test_admin_access_all_documents(self):
        """Test admin role can access all document types."""
        # Create documents with different permission levels
        documents = [
            {"id": "doc1", "content": "Public document", "permission": "public"},
            {"id": "doc2", "content": "Internal document", "permission": "internal"},
            {"id": "doc3", "content": "Confidential document", "permission": "confidential"},
            {"id": "doc4", "content": "Restricted document", "permission": "restricted"}
        ]

        await rag_service.index_documents("tenant_123", documents)

        # Query as admin
        results = await rag_service.search("tenant_123", "document", user_role="admin")

        # Verify admin gets all documents
        assert len(results) == 4
        permission_levels = [doc["permission"] for doc in results]
        assert "public" in permission_levels
        assert "internal" in permission_levels
        assert "confidential" in permission_levels
        assert "restricted" in permission_levels

    @pytest.mark.asyncio
    async def test_user_access_limited_documents(self):
        """Test user role can only access public and internal documents."""
        # Create documents with different permission levels
        documents = [
            {"id": "doc1", "content": "Public document", "permission": "public"},
            {"id": "doc2", "content": "Internal document", "permission": "internal"},
            {"id": "doc3", "content": "Confidential document", "permission": "confidential"},
            {"id": "doc4", "content": "Restricted document", "permission": "restricted"}
        ]

        await rag_service.index_documents("tenant_123", documents)

        # Query as user
        results = await rag_service.search("tenant_123", "document", user_role="user")

        # Verify user gets only public and internal documents
        assert len(results) == 2
        permission_levels = [doc["permission"] for doc in results]
        assert "public" in permission_levels
        assert "internal" in permission_levels
        assert "confidential" not in permission_levels
        assert "restricted" not in permission_levels

    @pytest.mark.asyncio
    async def test_guest_access_public_documents_only(self):
        """Test guest role can only access public documents."""
        # Create documents with different permission levels
        documents = [
            {"id": "doc1", "content": "Public document", "permission": "public"},
            {"id": "doc2", "content": "Internal document", "permission": "internal"},
            {"id": "doc3", "content": "Confidential document", "permission": "confidential"},
            {"id": "doc4", "content": "Restricted document", "permission": "restricted"}
        ]

        await rag_service.index_documents("tenant_123", documents)

        # Query as guest
        results = await rag_service.search("tenant_123", "document", user_role="guest")

        # Verify guest gets only public documents
        assert len(results) == 1
        assert results[0]["permission"] == "public"
        assert "internal" not in [doc["permission"] for doc in results]
        assert "confidential" not in [doc["permission"] for doc in results]
        assert "restricted" not in [doc["permission"] for doc in results]

    @pytest.mark.asyncio
    async def test_invalid_role_access_denied(self):
        """Test invalid role is denied access."""
        # Create documents
        documents = [
            {"id": "doc1", "content": "Public document", "permission": "public"}
        ]

        await rag_service.index_documents("tenant_123", documents)

        # Query with invalid role
        with pytest.raises(InvalidRoleError):
            await rag_service.search("tenant_123", "document", user_role="invalid_role")
```

### **Vector Security Tests**

```python
class VectorSecurityTests:
    """Test vector database security."""

    @pytest.mark.asyncio
    async def test_vector_embedding_isolation(self):
        """Test that vector embeddings are isolated by tenant."""
        # Create similar documents in different tenants
        tenant_a_doc = {
            "id": "doc_a1",
            "content": "Customer service policies and procedures",
            "tenant_id": "tenant_a"
        }

        tenant_b_doc = {
            "id": "doc_b1",
            "content": "Customer service policies and procedures",
            "tenant_id": "tenant_b"
        }

        # Index documents
        await rag_service.index_documents("tenant_a", [tenant_a_doc])
        await rag_service.index_documents("tenant_b", [tenant_b_doc])

        # Get vector embeddings
        embedding_a = await rag_service.get_document_embedding("tenant_a", "doc_a1")
        embedding_b = await rag_service.get_document_embedding("tenant_b", "doc_b1")

        # Verify embeddings are different (due to tenant context)
        assert embedding_a != embedding_b

        # Verify embeddings are stored in separate collections
        collection_a = rag_service.get_tenant_collection("tenant_a")
        collection_b = rag_service.get_tenant_collection("tenant_b")
        assert collection_a != collection_b

    @pytest.mark.asyncio
    async def test_vector_query_tenant_validation(self):
        """Test that vector queries are validated for tenant context."""
        # Create test document
        document = {
            "id": "doc1",
            "content": "Test document content",
            "tenant_id": "tenant_123"
        }

        await rag_service.index_documents("tenant_123", [document])

        # Test valid tenant query
        results = await rag_service.search("tenant_123", "test content", user_role="user")
        assert len(results) > 0

        # Test invalid tenant query (should return empty results)
        results = await rag_service.search("tenant_456", "test content", user_role="user")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_vector_result_tenant_validation(self):
        """Test that vector search results are validated for tenant context."""
        # Create documents in different tenants
        tenant_a_docs = [
            {"id": "doc_a1", "content": "Tenant A specific content", "tenant_id": "tenant_a"},
            {"id": "doc_a2", "content": "Another tenant A document", "tenant_id": "tenant_a"}
        ]

        tenant_b_docs = [
            {"id": "doc_b1", "content": "Tenant B specific content", "tenant_id": "tenant_b"},
            {"id": "doc_b2", "content": "Another tenant B document", "tenant_id": "tenant_b"}
        ]

        await rag_service.index_documents("tenant_a", tenant_a_docs)
        await rag_service.index_documents("tenant_b", tenant_b_docs)

        # Query from tenant A
        results = await rag_service.search("tenant_a", "specific content", user_role="user")

        # Verify all results belong to tenant A
        for result in results:
            assert result["tenant_id"] == "tenant_a"
            assert result["id"].startswith("doc_a")

        # Query from tenant B
        results = await rag_service.search("tenant_b", "specific content", user_role="user")

        # Verify all results belong to tenant B
        for result in results:
            assert result["tenant_id"] == "tenant_b"
            assert result["id"].startswith("doc_b")
```

## 🔄 **TTL Reindex Testing**

### **TTL Reindex System**

```python
class TTLReindexSystem:
    """Manages TTL-based reindexing for document freshness."""

    def __init__(self):
        self.ttl_config = {
            "public": 86400,      # 24 hours
            "internal": 43200,    # 12 hours
            "confidential": 21600, # 6 hours
            "restricted": 10800   # 3 hours
        }

        self.reindex_queue = []
        self.reindex_lock = asyncio.Lock()

    async def schedule_reindex(self, tenant_id: str, document_id: str, permission: str):
        """Schedule document for reindexing based on TTL."""
        ttl = self.ttl_config.get(permission, 86400)
        reindex_time = datetime.now() + timedelta(seconds=ttl)

        reindex_item = {
            "tenant_id": tenant_id,
            "document_id": document_id,
            "permission": permission,
            "reindex_time": reindex_time,
            "status": "scheduled"
        }

        async with self.reindex_lock:
            self.reindex_queue.append(reindex_item)

    async def process_reindex_queue(self):
        """Process scheduled reindexing tasks."""
        current_time = datetime.now()

        async with self.reindex_lock:
            items_to_reindex = [
                item for item in self.reindex_queue
                if item["reindex_time"] <= current_time and item["status"] == "scheduled"
            ]

        for item in items_to_reindex:
            await self.reindex_document(
                item["tenant_id"],
                item["document_id"],
                item["permission"]
            )

            # Mark as completed
            item["status"] = "completed"

    async def reindex_document(self, tenant_id: str, document_id: str, permission: str):
        """Reindex document with updated permissions."""
        # Get document from source
        document = await self.get_document(tenant_id, document_id)

        # Update permissions if needed
        if document["permission"] != permission:
            document["permission"] = permission
            document["updated_at"] = datetime.now()

        # Reindex in vector database
        await rag_service.index_documents(tenant_id, [document])

        # Log reindex event
        logger.info(f"Reindexed document {document_id} for tenant {tenant_id}")
```

### **TTL Reindex Tests**

```python
class TTLReindexTests:
    """Test TTL-based reindexing system."""

    @pytest.mark.asyncio
    async def test_ttl_reindex_scheduling(self):
        """Test TTL reindex scheduling."""
        ttl_system = TTLReindexSystem()

        # Schedule reindex for different permission levels
        await ttl_system.schedule_reindex("tenant_123", "doc1", "public")
        await ttl_system.schedule_reindex("tenant_123", "doc2", "internal")
        await ttl_system.schedule_reindex("tenant_123", "doc3", "confidential")

        # Verify items are scheduled
        assert len(ttl_system.reindex_queue) == 3

        # Verify TTL times are correct
        public_item = next(item for item in ttl_system.reindex_queue if item["document_id"] == "doc1")
        internal_item = next(item for item in ttl_system.reindex_queue if item["document_id"] == "doc2")
        confidential_item = next(item for item in ttl_system.reindex_queue if item["document_id"] == "doc3")

        assert public_item["permission"] == "public"
        assert internal_item["permission"] == "internal"
        assert confidential_item["permission"] == "confidential"

    @pytest.mark.asyncio
    async def test_ttl_reindex_processing(self):
        """Test TTL reindex processing."""
        ttl_system = TTLReindexSystem()

        # Schedule reindex with short TTL for testing
        ttl_system.ttl_config["test"] = 1  # 1 second
        await ttl_system.schedule_reindex("tenant_123", "doc1", "test")

        # Wait for TTL to expire
        await asyncio.sleep(1.1)

        # Process reindex queue
        await ttl_system.process_reindex_queue()

        # Verify item is marked as completed
        completed_item = next(item for item in ttl_system.reindex_queue if item["document_id"] == "doc1")
        assert completed_item["status"] == "completed"

    @pytest.mark.asyncio
    async def test_ttl_reindex_permission_update(self):
        """Test TTL reindex with permission updates."""
        ttl_system = TTLReindexSystem()

        # Create test document
        document = {
            "id": "doc1",
            "content": "Test document",
            "permission": "public",
            "tenant_id": "tenant_123"
        }

        await rag_service.index_documents("tenant_123", [document])

        # Schedule reindex with permission change
        await ttl_system.schedule_reindex("tenant_123", "doc1", "internal")

        # Wait for TTL to expire
        await asyncio.sleep(1.1)

        # Process reindex queue
        await ttl_system.process_reindex_queue()

        # Verify document permission is updated
        updated_doc = await rag_service.get_document("tenant_123", "doc1")
        assert updated_doc["permission"] == "internal"
```

## 📊 **RAG Security Metrics**

### **Security Metrics Collection**

```python
class RAGSecurityMetrics:
    """Collect and track RAG security metrics."""

    def __init__(self):
        self.cross_tenant_hits = 0
        self.permission_violations = 0
        self.invalid_role_attempts = 0
        self.ttl_reindexes = 0
        self.security_audits = 0

    def record_cross_tenant_hit(self, tenant_id: str, query: str):
        """Record cross-tenant hit attempt."""
        self.cross_tenant_hits += 1
        logger.warning(f"Cross-tenant hit attempted: tenant={tenant_id}, query={query}")

    def record_permission_violation(self, user_role: str, document_permission: str):
        """Record permission violation attempt."""
        self.permission_violations += 1
        logger.warning(f"Permission violation: role={user_role}, permission={document_permission}")

    def record_invalid_role_attempt(self, role: str):
        """Record invalid role attempt."""
        self.invalid_role_attempts += 1
        logger.warning(f"Invalid role attempt: role={role}")

    def record_ttl_reindex(self, tenant_id: str, document_id: str):
        """Record TTL reindex event."""
        self.ttl_reindexes += 1
        logger.info(f"TTL reindex: tenant={tenant_id}, document={document_id}")

    def record_security_audit(self, audit_type: str, result: str):
        """Record security audit event."""
        self.security_audits += 1
        logger.info(f"Security audit: type={audit_type}, result={result}")

    def get_security_summary(self) -> dict:
        """Get security metrics summary."""
        return {
            "cross_tenant_hits": self.cross_tenant_hits,
            "permission_violations": self.permission_violations,
            "invalid_role_attempts": self.invalid_role_attempts,
            "ttl_reindexes": self.ttl_reindexes,
            "security_audits": self.security_audits
        }
```

## 🚨 **RAG Security Alerts**

### **Security Alert Rules**

```yaml
alerts:
  - name: "Cross-Tenant Vector Hit"
    condition: "cross_tenant_hits > 0"
    severity: "critical"
    description: "Cross-tenant vector hit detected"

  - name: "Permission Violation"
    condition: "permission_violations > 0"
    severity: "warning"
    description: "Document permission violation detected"

  - name: "Invalid Role Attempt"
    condition: "invalid_role_attempts > 10"
    severity: "warning"
    description: "High number of invalid role attempts"

  - name: "TTL Reindex Failure"
    condition: "ttl_reindex_failures > 0"
    severity: "warning"
    description: "TTL reindex failures detected"
```

---

**Status**: ✅ Production-Ready RAG Permissions Testing  
**Last Updated**: September 2024  
**Version**: 1.0.0
