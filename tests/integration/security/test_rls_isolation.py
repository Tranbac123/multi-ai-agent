"""Row-Level Security (RLS) isolation tests for multi-tenant data safety."""

import pytest
import asyncio
from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta

from tests.integration.security import SecurityViolation, IsolationLevel, SecurityAudit
from tests._fixtures.factories import factory, TenantTier
from tests._helpers import test_helpers
from tests.contract.schemas import APIRequest, APIResponse, RequestType


class MockRLSDatabase:
    """Mock database with Row-Level Security (RLS) for testing."""
    
    def __init__(self):
        self.tenant_data = {
            "tenant_1234": {
                "users": ["user_1234", "user_5678"],
                "documents": [
                    {"id": "doc_001", "title": "Tenant 1 Doc 1", "content": "Content for tenant 1"},
                    {"id": "doc_002", "title": "Tenant 1 Doc 2", "content": "Content for tenant 1"}
                ],
                "quota_usage": {"requests": 100, "cost": 5.50, "limit": 1000}
            },
            "tenant_5678": {
                "users": ["user_9012", "user_3456"],
                "documents": [
                    {"id": "doc_003", "title": "Tenant 2 Doc 1", "content": "Content for tenant 2"},
                    {"id": "doc_004", "title": "Tenant 2 Doc 2", "content": "Content for tenant 2"}
                ],
                "quota_usage": {"requests": 50, "cost": 2.25, "limit": 500}
            }
        }
        self.security_audit: List[SecurityAudit] = []
    
    async def query_with_rls(self, query: str, tenant_id: str, user_id: str) -> Tuple[List[Dict[str, Any]], List[SecurityAudit]]:
        """Execute query with RLS enforcement."""
        audits = []
        
        # Validate tenant access
        if tenant_id not in self.tenant_data:
            audit = SecurityAudit(
                violation_type=SecurityViolation.UNAUTHORIZED_ACCESS,
                tenant_id=tenant_id,
                user_id=user_id,
                resource_accessed=query,
                isolation_level=IsolationLevel.TENANT_LEVEL,
                timestamp=datetime.now(),
                severity="HIGH",
                blocked=True
            )
            audits.append(audit)
            self.security_audit.append(audit)
            return [], audits
        
        # Validate user belongs to tenant
        if user_id not in self.tenant_data[tenant_id]["users"]:
            audit = SecurityAudit(
                violation_type=SecurityViolation.CROSS_TENANT_ACCESS,
                tenant_id=tenant_id,
                user_id=user_id,
                resource_accessed=query,
                isolation_level=IsolationLevel.USER_LEVEL,
                timestamp=datetime.now(),
                severity="CRITICAL",
                blocked=True
            )
            audits.append(audit)
            self.security_audit.append(audit)
            return [], audits
        
        # Execute query with tenant isolation
        tenant_docs = self.tenant_data[tenant_id]["documents"]
        
        # Simulate query execution
        if "SELECT" in query.upper():
            results = tenant_docs.copy()
        elif "INSERT" in query.upper():
            # Simulate insert
            new_doc_id = f"doc_{tenant_id}_{len(tenant_docs)+1}"
            new_doc = {"id": new_doc_id, "title": "New Doc", "content": "New Content"}
            self.tenant_data[tenant_id]["documents"].append(new_doc)
            results = [new_doc]
        else:
            results = []
        
        return results, audits
    
    async def check_quota(self, tenant_id: str, user_id: str, request_cost: float = 0.001) -> Tuple[bool, List[SecurityAudit]]:
        """Check tenant quota and rate limiting."""
        audits = []
        
        if tenant_id not in self.tenant_data:
            return False, audits
        
        tenant_info = self.tenant_data[tenant_id]
        quota_usage = tenant_info["quota_usage"]
        
        # Check request quota
        if quota_usage["requests"] >= quota_usage["limit"]:
            audit = SecurityAudit(
                violation_type=SecurityViolation.QUOTA_EXCEEDED,
                tenant_id=tenant_id,
                user_id=user_id,
                resource_accessed="quota_check",
                isolation_level=IsolationLevel.TENANT_LEVEL,
                timestamp=datetime.now(),
                severity="MEDIUM",
                blocked=True
            )
            audits.append(audit)
            self.security_audit.append(audit)
            return False, audits
        
        # Check cost quota
        if quota_usage["cost"] + request_cost > quota_usage["limit"] * 0.01:  # 1% of limit
            audit = SecurityAudit(
                violation_type=SecurityViolation.QUOTA_EXCEEDED,
                tenant_id=tenant_id,
                user_id=user_id,
                resource_accessed="cost_quota",
                isolation_level=IsolationLevel.TENANT_LEVEL,
                timestamp=datetime.now(),
                severity="MEDIUM",
                blocked=True
            )
            audits.append(audit)
            self.security_audit.append(audit)
            return False, audits
        
        # Update quota usage
        quota_usage["requests"] += 1
        quota_usage["cost"] += request_cost
        
        return True, audits


class TestRLSIsolation:
    """Test Row-Level Security isolation for multi-tenant data safety."""
    
    @pytest.fixture
    def mock_rls_db(self):
        """Create mock RLS database."""
        return MockRLSDatabase()
    
    @pytest.mark.asyncio
    async def test_cross_tenant_query_isolation(self, mock_rls_db):
        """Test cross-tenant query isolation."""
        # Query from tenant 1
        results1, audits1 = await mock_rls_db.query_with_rls(
            "SELECT * FROM documents",
            "tenant_1234",
            "user_1234"
        )
        
        # Query from tenant 2
        results2, audits2 = await mock_rls_db.query_with_rls(
            "SELECT * FROM documents", 
            "tenant_5678",
            "user_9012"
        )
        
        # Validate isolation
        assert len(results1) == 2  # Tenant 1 has 2 documents
        assert len(results2) == 2  # Tenant 2 has 2 documents
        
        # Ensure no cross-tenant data leakage
        tenant1_doc_ids = {doc["id"] for doc in results1}
        tenant2_doc_ids = {doc["id"] for doc in results2}
        
        assert tenant1_doc_ids.isdisjoint(tenant2_doc_ids)  # No overlap
        assert "doc_001" in tenant1_doc_ids
        assert "doc_002" in tenant1_doc_ids
        assert "doc_003" in tenant2_doc_ids
        assert "doc_004" in tenant2_doc_ids
        
        # No security violations
        assert len(audits1) == 0
        assert len(audits2) == 0
    
    @pytest.mark.asyncio
    async def test_unauthorized_tenant_access(self, mock_rls_db):
        """Test unauthorized tenant access."""
        # Try to access non-existent tenant
        results, audits = await mock_rls_db.query_with_rls(
            "SELECT * FROM documents",
            "tenant_9999",  # Non-existent tenant
            "user_1234"
        )
        
        # Should be blocked
        assert len(results) == 0
        assert len(audits) == 1
        
        audit = audits[0]
        assert audit.violation_type == SecurityViolation.UNAUTHORIZED_ACCESS
        assert audit.blocked is True
        assert audit.severity == "HIGH"
    
    @pytest.mark.asyncio
    async def test_cross_tenant_user_access(self, mock_rls_db):
        """Test cross-tenant user access."""
        # Try to access tenant 2 with user from tenant 1
        results, audits = await mock_rls_db.query_with_rls(
            "SELECT * FROM documents",
            "tenant_5678",  # Tenant 2
            "user_1234"     # User from tenant 1
        )
        
        # Should be blocked
        assert len(results) == 0
        assert len(audits) == 1
        
        audit = audits[0]
        assert audit.violation_type == SecurityViolation.CROSS_TENANT_ACCESS
        assert audit.blocked is True
        assert audit.severity == "CRITICAL"
    
    @pytest.mark.asyncio
    async def test_quota_enforcement(self, mock_rls_db):
        """Test quota enforcement."""
        # Use up quota for tenant 2
        tenant_info = mock_rls_db.tenant_data["tenant_5678"]
        tenant_info["quota_usage"]["requests"] = tenant_info["quota_usage"]["limit"]  # Max out requests
        
        # Try to make another request
        allowed, audits = await mock_rls_db.check_quota("tenant_5678", "user_9012")
        
        # Should be blocked
        assert allowed is False
        assert len(audits) == 1
        
        audit = audits[0]
        assert audit.violation_type == SecurityViolation.QUOTA_EXCEEDED
        assert audit.blocked is True
        assert audit.severity == "MEDIUM"
    
    @pytest.mark.asyncio
    async def test_cost_quota_enforcement(self, mock_rls_db):
        """Test cost quota enforcement."""
        # Use up cost quota for tenant 2
        tenant_info = mock_rls_db.tenant_data["tenant_5678"]
        tenant_info["quota_usage"]["cost"] = tenant_info["quota_usage"]["limit"] * 0.01  # Max out cost
        
        # Try to make expensive request
        allowed, audits = await mock_rls_db.check_quota("tenant_5678", "user_9012", request_cost=0.01)
        
        # Should be blocked
        assert allowed is False
        assert len(audits) == 1
        
        audit = audits[0]
        assert audit.violation_type == SecurityViolation.QUOTA_EXCEEDED
        assert audit.blocked is True
    
    @pytest.mark.asyncio
    async def test_data_insertion_isolation(self, mock_rls_db):
        """Test data insertion isolation."""
        # Insert document in tenant 1
        results1, audits1 = await mock_rls_db.query_with_rls(
            "INSERT INTO documents VALUES ('New Doc 1', 'New Content 1')",
            "tenant_1234",
            "user_1234"
        )
        
        # Insert document in tenant 2
        results2, audits2 = await mock_rls_db.query_with_rls(
            "INSERT INTO documents VALUES ('New Doc 2', 'New Content 2')",
            "tenant_5678",
            "user_9012"
        )
        
        # Validate isolation
        assert len(results1) == 1
        assert len(results2) == 1
        assert len(audits1) == 0
        assert len(audits2) == 0
        
        # Verify documents are in correct tenants
        tenant1_docs = mock_rls_db.tenant_data["tenant_1234"]["documents"]
        tenant2_docs = mock_rls_db.tenant_data["tenant_5678"]["documents"]
        
        assert len(tenant1_docs) == 3  # Original 2 + 1 new
        assert len(tenant2_docs) == 3  # Original 2 + 1 new
        
        # Ensure no cross-tenant contamination
        tenant1_ids = {doc["id"] for doc in tenant1_docs}
        tenant2_ids = {doc["id"] for doc in tenant2_docs}
        # Check that tenant-specific IDs don't overlap
        tenant1_specific = {doc_id for doc_id in tenant1_ids if doc_id.startswith("doc_tenant_1234") or doc_id in ["doc_001", "doc_002"]}
        tenant2_specific = {doc_id for doc_id in tenant2_ids if doc_id.startswith("doc_tenant_5678") or doc_id in ["doc_003", "doc_004"]}
        assert len(tenant1_specific) == 3  # Original 2 + 1 new
        assert len(tenant2_specific) == 3  # Original 2 + 1 new
    
    @pytest.mark.asyncio
    async def test_concurrent_tenant_access(self, mock_rls_db):
        """Test concurrent access from different tenants."""
        async def tenant_query(tenant_id: str, user_id: str):
            return await mock_rls_db.query_with_rls(
                "SELECT * FROM documents",
                tenant_id,
                user_id
            )
        
        # Execute concurrent queries
        results = await asyncio.gather(
            tenant_query("tenant_1234", "user_1234"),
            tenant_query("tenant_5678", "user_9012"),
            tenant_query("tenant_1234", "user_5678"),
            tenant_query("tenant_5678", "user_3456")
        )
        
        # Validate all queries succeeded with proper isolation
        for (results_list, audits) in results:
            assert len(audits) == 0  # No security violations
            assert len(results_list) == 2  # Each tenant has 2 documents
        
        # Verify no cross-tenant data leakage
        # Check that each result set contains only documents from the correct tenant
        tenant1_queries = [results[0], results[2]]  # Queries from tenant 1
        tenant2_queries = [results[1], results[3]]  # Queries from tenant 2
        
        for (results_list, audits) in tenant1_queries:
            doc_ids = {doc["id"] for doc in results_list}
            # Should not contain tenant 2 documents
            assert not any(doc_id in ["doc_003", "doc_004"] for doc_id in doc_ids)
        
        for (results_list, audits) in tenant2_queries:
            doc_ids = {doc["id"] for doc in results_list}
            # Should not contain tenant 1 documents
            assert not any(doc_id in ["doc_001", "doc_002"] for doc_id in doc_ids)
    
    @pytest.mark.asyncio
    async def test_security_audit_logging(self, mock_rls_db):
        """Test security audit logging."""
        # Perform unauthorized access
        await mock_rls_db.query_with_rls(
            "SELECT * FROM documents",
            "tenant_9999",  # Non-existent tenant
            "user_1234"
        )
        
        # Perform cross-tenant access
        await mock_rls_db.query_with_rls(
            "SELECT * FROM documents",
            "tenant_5678",  # Different tenant
            "user_1234"     # User from tenant 1
        )
        
        # Check audit log
        assert len(mock_rls_db.security_audit) == 2
        
        audit1 = mock_rls_db.security_audit[0]
        assert audit1.violation_type == SecurityViolation.UNAUTHORIZED_ACCESS
        assert audit1.tenant_id == "tenant_9999"
        assert audit1.blocked is True
        
        audit2 = mock_rls_db.security_audit[1]
        assert audit2.violation_type == SecurityViolation.CROSS_TENANT_ACCESS
        assert audit2.tenant_id == "tenant_5678"
        assert audit2.blocked is True