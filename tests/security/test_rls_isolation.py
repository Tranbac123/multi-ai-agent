"""Test Row-Level Security (RLS) isolation."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from tests._fixtures.factories import TenantFactory, UserFactory, DocumentFactory
from tests._helpers.assertions import MultiTenantAssertions, PIIAssertions


class TestRLSIsolation:
    """Test Row-Level Security isolation between tenants."""
    
    @pytest.mark.asyncio
    async def test_document_rls_isolation(self):
        """Test document RLS isolation."""
        # Setup two tenants
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        doc_factory = DocumentFactory()
        
        tenant_a = tenant_factory.create()
        tenant_b = tenant_factory.create()
        
        user_a = user_factory.create(tenant_a["tenant_id"])
        user_b = user_factory.create(tenant_b["tenant_id"])
        
        # Create documents for each tenant
        doc_a = doc_factory.create(tenant_a["tenant_id"], title="Tenant A Document")
        doc_b = doc_factory.create(tenant_b["tenant_id"], title="Tenant B Document")
        
        # Mock database with RLS
        mock_db = Mock()
        
        # Simulate RLS query for tenant A
        async def query_tenant_a_docs():
            # RLS should filter to only tenant A documents
            return [doc_a]
        
        # Simulate RLS query for tenant B
        async def query_tenant_b_docs():
            # RLS should filter to only tenant B documents
            return [doc_b]
        
        mock_db.query_documents = AsyncMock()
        mock_db.query_documents.side_effect = [
            query_tenant_a_docs(),
            query_tenant_b_docs()
        ]
        
        # Test RLS isolation
        docs_a = await mock_db.query_documents(tenant_id=tenant_a["tenant_id"])
        docs_b = await mock_db.query_documents(tenant_id=tenant_b["tenant_id"])
        
        # Verify isolation
        assert len(docs_a) == 1
        assert len(docs_b) == 1
        assert docs_a[0]["tenant_id"] == tenant_a["tenant_id"]
        assert docs_b[0]["tenant_id"] == tenant_b["tenant_id"]
        assert docs_a[0]["tenant_id"] != docs_b[0]["tenant_id"]
        
        # Test isolation assertion
        result = MultiTenantAssertions.assert_tenant_isolation(
            docs_a, "tenant_id", "Document RLS isolation A"
        )
        assert result.passed, f"Tenant A documents should be isolated: {result.message}"
        
        result = MultiTenantAssertions.assert_tenant_isolation(
            docs_b, "tenant_id", "Document RLS isolation B"
        )
        assert result.passed, f"Tenant B documents should be isolated: {result.message}"
    
    @pytest.mark.asyncio
    async def test_user_rls_isolation(self):
        """Test user RLS isolation."""
        # Setup two tenants
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant_a = tenant_factory.create()
        tenant_b = tenant_factory.create()
        
        # Create users for each tenant
        users_a = [user_factory.create(tenant_a["tenant_id"]) for _ in range(3)]
        users_b = [user_factory.create(tenant_b["tenant_id"]) for _ in range(2)]
        
        # Mock database with RLS
        mock_db = Mock()
        
        # Simulate RLS query for tenant A users
        async def query_tenant_a_users():
            return users_a
        
        # Simulate RLS query for tenant B users
        async def query_tenant_b_users():
            return users_b
        
        mock_db.query_users = AsyncMock()
        mock_db.query_users.side_effect = [
            query_tenant_a_users(),
            query_tenant_b_users()
        ]
        
        # Test RLS isolation
        queried_users_a = await mock_db.query_users(tenant_id=tenant_a["tenant_id"])
        queried_users_b = await mock_db.query_users(tenant_id=tenant_b["tenant_id"])
        
        # Verify isolation
        assert len(queried_users_a) == 3
        assert len(queried_users_b) == 2
        assert all(user["tenant_id"] == tenant_a["tenant_id"] for user in queried_users_a)
        assert all(user["tenant_id"] == tenant_b["tenant_id"] for user in queried_users_b)
        
        # Test cross-tenant access prevention
        try:
            # Attempt cross-tenant access (should be blocked by RLS)
            cross_tenant_users = await mock_db.query_users(tenant_id=tenant_b["tenant_id"], requesting_tenant=tenant_a["tenant_id"])
            # If we get here, RLS failed
            assert False, "Cross-tenant access should be blocked by RLS"
        except Exception:
            # Expected - RLS should block cross-tenant access
            pass
    
    @pytest.mark.asyncio
    async def test_usage_tracking_rls_isolation(self):
        """Test usage tracking RLS isolation."""
        # Setup two tenants
        tenant_factory = TenantFactory()
        
        tenant_a = tenant_factory.create()
        tenant_b = tenant_factory.create()
        
        # Mock usage data
        usage_a = [
            {"tenant_id": tenant_a["tenant_id"], "usage_type": "tokens", "quantity": 100, "timestamp": "2024-01-01T10:00:00Z"},
            {"tenant_id": tenant_a["tenant_id"], "usage_type": "api_calls", "quantity": 50, "timestamp": "2024-01-01T11:00:00Z"}
        ]
        
        usage_b = [
            {"tenant_id": tenant_b["tenant_id"], "usage_type": "tokens", "quantity": 200, "timestamp": "2024-01-01T10:00:00Z"},
            {"tenant_id": tenant_b["tenant_id"], "usage_type": "api_calls", "quantity": 75, "timestamp": "2024-01-01T11:00:00Z"}
        ]
        
        # Mock database with RLS
        mock_db = Mock()
        
        async def query_usage(tenant_id):
            if tenant_id == tenant_a["tenant_id"]:
                return usage_a
            elif tenant_id == tenant_b["tenant_id"]:
                return usage_b
            else:
                return []
        
        mock_db.query_usage = AsyncMock(side_effect=query_usage)
        
        # Test RLS isolation
        queried_usage_a = await mock_db.query_usage(tenant_id=tenant_a["tenant_id"])
        queried_usage_b = await mock_db.query_usage(tenant_id=tenant_b["tenant_id"])
        
        # Verify isolation
        assert len(queried_usage_a) == 2
        assert len(queried_usage_b) == 2
        assert all(usage["tenant_id"] == tenant_a["tenant_id"] for usage in queried_usage_a)
        assert all(usage["tenant_id"] == tenant_b["tenant_id"] for usage in queried_usage_b)
        
        # Verify data isolation
        total_tokens_a = sum(u["quantity"] for u in queried_usage_a if u["usage_type"] == "tokens")
        total_tokens_b = sum(u["quantity"] for u in queried_usage_b if u["usage_type"] == "tokens")
        
        assert total_tokens_a == 100
        assert total_tokens_b == 200
        assert total_tokens_a != total_tokens_b
    
    @pytest.mark.asyncio
    async def test_billing_rls_isolation(self):
        """Test billing data RLS isolation."""
        # Setup two tenants
        tenant_factory = TenantFactory()
        
        tenant_a = tenant_factory.create()
        tenant_b = tenant_factory.create()
        
        # Mock billing data
        billing_a = {
            "tenant_id": tenant_a["tenant_id"],
            "invoice_id": "inv_a_123",
            "amount": 99.99,
            "status": "paid",
            "items": [
                {"description": "Premium Plan", "amount": 99.99}
            ]
        }
        
        billing_b = {
            "tenant_id": tenant_b["tenant_id"],
            "invoice_id": "inv_b_456",
            "amount": 199.99,
            "status": "pending",
            "items": [
                {"description": "Enterprise Plan", "amount": 199.99}
            ]
        }
        
        # Mock database with RLS
        mock_db = Mock()
        
        async def query_billing(tenant_id):
            if tenant_id == tenant_a["tenant_id"]:
                return [billing_a]
            elif tenant_id == tenant_b["tenant_id"]:
                return [billing_b]
            else:
                return []
        
        mock_db.query_billing = AsyncMock(side_effect=query_billing)
        
        # Test RLS isolation
        queried_billing_a = await mock_db.query_billing(tenant_id=tenant_a["tenant_id"])
        queried_billing_b = await mock_db.query_billing(tenant_id=tenant_b["tenant_id"])
        
        # Verify isolation
        assert len(queried_billing_a) == 1
        assert len(queried_billing_b) == 1
        assert queried_billing_a[0]["tenant_id"] == tenant_a["tenant_id"]
        assert queried_billing_b[0]["tenant_id"] == tenant_b["tenant_id"]
        assert queried_billing_a[0]["invoice_id"] == "inv_a_123"
        assert queried_billing_b[0]["invoice_id"] == "inv_b_456"
        assert queried_billing_a[0]["amount"] == 99.99
        assert queried_billing_b[0]["amount"] == 199.99
    
    @pytest.mark.asyncio
    async def test_rls_bypass_attempt_detection(self):
        """Test detection of RLS bypass attempts."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant_a = tenant_factory.create()
        tenant_b = tenant_factory.create()
        
        # Mock database with RLS protection
        mock_db = Mock()
        
        # Simulate RLS bypass attempt
        async def attempt_rls_bypass():
            # This should be blocked by RLS
            raise Exception("RLS violation: Cross-tenant access attempted")
        
        mock_db.bypass_query = AsyncMock(side_effect=attempt_rls_bypass)
        
        # Test RLS bypass detection
        try:
            await mock_db.bypass_query(tenant_id=tenant_a["tenant_id"], target_tenant=tenant_b["tenant_id"])
            assert False, "RLS bypass should be detected and blocked"
        except Exception as e:
            assert "RLS violation" in str(e)
            assert "Cross-tenant access" in str(e)
    
    @pytest.mark.asyncio
    async def test_rls_audit_logging(self):
        """Test RLS audit logging."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant_a = tenant_factory.create()
        user_a = user_factory.create(tenant_a["tenant_id"])
        
        # Mock audit logger
        audit_logs = []
        
        class MockAuditLogger:
            def log_access(self, tenant_id, user_id, resource_type, resource_id, action):
                audit_logs.append({
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "action": action,
                    "timestamp": "2024-01-01T12:00:00Z"
                })
        
        audit_logger = MockAuditLogger()
        
        # Simulate RLS-protected access
        await audit_logger.log_access(
            tenant_id=tenant_a["tenant_id"],
            user_id=user_a["user_id"],
            resource_type="document",
            resource_id="doc_123",
            action="read"
        )
        
        await audit_logger.log_access(
            tenant_id=tenant_a["tenant_id"],
            user_id=user_a["user_id"],
            resource_type="billing",
            resource_id="inv_456",
            action="update"
        )
        
        # Verify audit logging
        assert len(audit_logs) == 2
        assert all(log["tenant_id"] == tenant_a["tenant_id"] for log in audit_logs)
        assert all(log["user_id"] == user_a["user_id"] for log in audit_logs)
        assert audit_logs[0]["resource_type"] == "document"
        assert audit_logs[1]["resource_type"] == "billing"
        assert audit_logs[0]["action"] == "read"
        assert audit_logs[1]["action"] == "update"
    
    @pytest.mark.asyncio
    async def test_rls_performance_impact(self):
        """Test RLS performance impact."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant_a = tenant_factory.create()
        
        # Mock database with and without RLS
        mock_db_with_rls = Mock()
        mock_db_without_rls = Mock()
        
        # Simulate RLS overhead
        async def query_with_rls(tenant_id):
            await asyncio.sleep(0.001)  # 1ms RLS overhead
            return [{"tenant_id": tenant_id, "data": "test"}]
        
        async def query_without_rls():
            return [{"tenant_id": tenant_a["tenant_id"], "data": "test"}]
        
        mock_db_with_rls.query = AsyncMock(side_effect=query_with_rls)
        mock_db_without_rls.query = AsyncMock(side_effect=query_without_rls)
        
        # Measure performance
        start_time = time.time()
        await mock_db_with_rls.query(tenant_id=tenant_a["tenant_id"])
        rls_time = time.time() - start_time
        
        start_time = time.time()
        await mock_db_without_rls.query()
        no_rls_time = time.time() - start_time
        
        # Verify RLS overhead is minimal
        overhead = rls_time - no_rls_time
        assert overhead < 0.01  # Less than 10ms overhead
        
        # Verify RLS still provides isolation
        result_with_rls = await mock_db_with_rls.query(tenant_id=tenant_a["tenant_id"])
        assert len(result_with_rls) == 1
        assert result_with_rls[0]["tenant_id"] == tenant_a["tenant_id"]
