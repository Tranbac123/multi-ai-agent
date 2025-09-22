"""Integration tests for self-serve plans and lifecycle hooks."""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text

from apps.tenant-service.main import create_app as create_tenant_app
from apps.admin-portal.main import create_app as create_admin_app
from apps.tenant-service.core.tenant_onboarding import TenantOnboardingManager
from apps.tenant-service.core.plan_upgrade_manager import PlanUpgradeManager
from apps.tenant-service.core.webhook_manager import WebhookManager, WebhookEvent


# Mock database session for tests
@pytest.fixture
async def mock_db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE tenants (
                tenant_id VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                email VARCHAR NOT NULL,
                company_name VARCHAR,
                plan VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                trial_ends_at DATETIME,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                metadata TEXT
            );
        """))
        await conn.execute(text("""
            CREATE TABLE plan_configurations (
                plan_name VARCHAR PRIMARY KEY,
                display_name VARCHAR NOT NULL,
                description TEXT,
                price_monthly DECIMAL(10,2) NOT NULL,
                price_yearly DECIMAL(10,2) NOT NULL,
                features TEXT NOT NULL,
                limits TEXT NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT TRUE,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );
        """))
        await conn.execute(text("""
            CREATE TABLE webhook_endpoints (
                endpoint_id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR NOT NULL,
                url VARCHAR NOT NULL,
                events TEXT NOT NULL,
                secret VARCHAR NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT TRUE,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                metadata TEXT
            );
        """))
        await conn.execute(text("""
            CREATE TABLE webhook_deliveries (
                delivery_id VARCHAR PRIMARY KEY,
                endpoint_id VARCHAR NOT NULL,
                event VARCHAR NOT NULL,
                payload TEXT NOT NULL,
                status VARCHAR NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                next_retry_at DATETIME,
                last_attempt_at DATETIME,
                response_status INTEGER,
                response_body TEXT,
                error_message TEXT,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );
        """))
        await conn.execute(text("""
            CREATE TABLE plan_upgrade_history (
                upgrade_id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR NOT NULL,
                old_plan VARCHAR NOT NULL,
                new_plan VARCHAR NOT NULL,
                billing_cycle VARCHAR NOT NULL,
                upgrade_date DATETIME NOT NULL,
                next_billing_date DATETIME NOT NULL,
                cost TEXT NOT NULL,
                payment_method_id VARCHAR,
                status VARCHAR NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );
        """))
        
        # Insert test plan configurations
        await conn.execute(text("""
            INSERT INTO plan_configurations (
                plan_name, display_name, description, price_monthly, price_yearly,
                features, limits, enabled, created_at, updated_at
            ) VALUES 
            ('trial', 'Trial', 'Free trial', 0.00, 0.00, '["Basic features"]', '{"users": 1}', true, datetime('now'), datetime('now')),
            ('basic', 'Basic', 'Basic plan', 29.00, 290.00, '["All features"]', '{"users": 5}', true, datetime('now'), datetime('now')),
            ('pro', 'Pro', 'Pro plan', 99.00, 990.00, '["Advanced features"]', '{"users": 25}', true, datetime('now'), datetime('now'));
        """))
    
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def mock_auth_client():
    with patch('libs.clients.auth.AuthClient', autospec=True) as MockAuthClient:
        instance = MockAuthClient.return_value
        instance.validate_token.return_value = {"tenant_id": "test-tenant"}
        yield instance


@pytest.fixture
def mock_billing_client():
    with patch('libs.clients.billing.BillingClient', autospec=True) as MockBillingClient:
        instance = MockBillingClient.return_value
        instance.create_customer.return_value = {"customer_id": "cust_123"}
        instance.create_subscription.return_value = {"subscription_id": "sub_123"}
        instance.update_subscription.return_value = {"subscription_id": "sub_123"}
        yield instance


@pytest.fixture
def mock_quota_client():
    with patch('libs.clients.quota.QuotaClient', autospec=True) as MockQuotaClient:
        instance = MockQuotaClient.return_value
        instance.create_tenant_quotas.return_value = True
        instance.update_tenant_quotas.return_value = True
        yield instance


@pytest.fixture
def mock_redis_client():
    with patch('redis.asyncio.from_url') as mock_redis:
        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        mock_client.get.return_value = None
        mock_client.set.return_value = True
        mock_redis.return_value = mock_client
        yield mock_client


@pytest.fixture
def tenant_app(mock_db_session, mock_auth_client, mock_billing_client, mock_quota_client, mock_redis_client):
    app = create_tenant_app()
    app.state.db_session = AsyncMock(return_value=mock_db_session)
    app.state.redis_client = mock_redis_client
    app.state.auth_client = mock_auth_client
    app.state.billing_client = mock_billing_client
    app.state.quota_client = mock_quota_client
    return app


@pytest.fixture
def admin_app(mock_db_session, mock_auth_client, mock_billing_client, mock_quota_client, mock_redis_client):
    app = create_admin_app()
    app.state.db_session = AsyncMock(return_value=mock_db_session)
    app.state.redis_client = mock_redis_client
    app.state.auth_client = mock_auth_client
    app.state.billing_client = mock_billing_client
    app.state.quota_client = mock_quota_client
    return app


@pytest.mark.asyncio
async def test_tenant_signup_flow(tenant_app, mock_db_session):
    """Test complete tenant signup flow."""
    with patch('libs.clients.auth.get_tenant_from_jwt', return_value='new-tenant'):
        async with AsyncClient(app=tenant_app, base_url="http://test") as client:
            # Test tenant signup
            signup_data = {
                "name": "Test Company",
                "email": "admin@testcompany.com",
                "company_name": "Test Company Inc",
                "plan": "trial",
                "metadata": {"source": "website"}
            }
            
            response = await client.post("/api/v1/tenants/signup", json=signup_data)
            assert response.status_code == 200
            
            tenant_data = response.json()
            assert tenant_data["name"] == "Test Company"
            assert tenant_data["email"] == "admin@testcompany.com"
            assert tenant_data["plan"] == "trial"
            assert tenant_data["status"] == "active"
            
            # Verify tenant was created in database
            query = text("SELECT * FROM tenants WHERE tenant_id = :tenant_id")
            result = await mock_db_session.execute(query, {"tenant_id": tenant_data["tenant_id"]})
            tenant_row = result.fetchone()
            assert tenant_row is not None
            assert tenant_row.name == "Test Company"


@pytest.mark.asyncio
async def test_plan_upgrade_flow(tenant_app, mock_db_session):
    """Test plan upgrade flow."""
    # First create a tenant
    query = text("""
        INSERT INTO tenants (
            tenant_id, name, email, company_name, plan, status,
            created_at, updated_at, metadata
        ) VALUES (
            :tenant_id, :name, :email, :company_name, :plan, :status,
            :created_at, :updated_at, :metadata
        )
    """)
    
    tenant_id = "test-tenant-123"
    await mock_db_session.execute(query, {
        "tenant_id": tenant_id,
        "name": "Test Company",
        "email": "admin@testcompany.com",
        "company_name": "Test Company Inc",
        "plan": "basic",
        "status": "active",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "metadata": json.dumps({})
    })
    await mock_db_session.commit()
    
    with patch('libs.clients.auth.get_tenant_from_jwt', return_value=tenant_id):
        async with AsyncClient(app=tenant_app, base_url="http://test") as client:
            # Test plan upgrade
            upgrade_data = {
                "plan": "pro",
                "billing_cycle": "monthly",
                "payment_method_id": "pm_123"
            }
            
            response = await client.post(f"/api/v1/tenants/{tenant_id}/upgrade", json=upgrade_data)
            assert response.status_code == 200
            
            upgrade_result = response.json()
            assert upgrade_result["tenant_id"] == tenant_id
            assert upgrade_result["old_plan"] == "basic"
            assert upgrade_result["new_plan"] == "pro"
            assert upgrade_result["billing_cycle"] == "monthly"
            
            # Verify plan upgrade was recorded in database
            query = text("SELECT * FROM plan_upgrade_history WHERE tenant_id = :tenant_id")
            result = await mock_db_session.execute(query, {"tenant_id": tenant_id})
            upgrade_row = result.fetchone()
            assert upgrade_row is not None
            assert upgrade_row.new_plan == "pro"


@pytest.mark.asyncio
async def test_webhook_endpoint_management(tenant_app, mock_db_session):
    """Test webhook endpoint creation and management."""
    # First create a tenant
    query = text("""
        INSERT INTO tenants (
            tenant_id, name, email, company_name, plan, status,
            created_at, updated_at, metadata
        ) VALUES (
            :tenant_id, :name, :email, :company_name, :plan, :status,
            :created_at, :updated_at, :metadata
        )
    """)
    
    tenant_id = "test-tenant-webhook"
    await mock_db_session.execute(query, {
        "tenant_id": tenant_id,
        "name": "Test Company",
        "email": "admin@testcompany.com",
        "company_name": "Test Company Inc",
        "plan": "pro",
        "status": "active",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "metadata": json.dumps({})
    })
    await mock_db_session.commit()
    
    with patch('libs.clients.auth.get_tenant_from_jwt', return_value=tenant_id):
        async with AsyncClient(app=tenant_app, base_url="http://test") as client:
            # Create webhook endpoint
            webhook_data = {
                "url": "https://testcompany.com/webhooks",
                "events": ["tenant.created", "plan.upgraded", "payment.success"],
                "secret": "test-secret-key",
                "metadata": {"description": "Test webhook"}
            }
            
            response = await client.post(f"/api/v1/tenants/{tenant_id}/webhooks", json=webhook_data)
            assert response.status_code == 200
            
            webhook_result = response.json()
            assert webhook_result["url"] == "https://testcompany.com/webhooks"
            assert "tenant.created" in webhook_result["events"]
            assert webhook_result["enabled"] is True
            
            # Get webhook endpoints
            response = await client.get(f"/api/v1/tenants/{tenant_id}/webhooks")
            assert response.status_code == 200
            
            webhooks = response.json()
            assert len(webhooks) == 1
            assert webhooks[0]["url"] == "https://testcompany.com/webhooks"
            
            # Delete webhook endpoint
            response = await client.delete(f"/api/v1/tenants/{tenant_id}/webhooks/{webhook_result['endpoint_id']}")
            assert response.status_code == 200
            
            # Verify webhook was deleted
            response = await client.get(f"/api/v1/tenants/{tenant_id}/webhooks")
            assert response.status_code == 200
            webhooks = response.json()
            assert len(webhooks) == 0


@pytest.mark.asyncio
async def test_webhook_event_delivery(tenant_app, mock_db_session):
    """Test webhook event delivery."""
    # Create tenant and webhook endpoint
    query = text("""
        INSERT INTO tenants (
            tenant_id, name, email, company_name, plan, status,
            created_at, updated_at, metadata
        ) VALUES (
            :tenant_id, :name, :email, :company_name, :plan, :status,
            :created_at, :updated_at, :metadata
        )
    """)
    
    tenant_id = "test-tenant-events"
    await mock_db_session.execute(query, {
        "tenant_id": tenant_id,
        "name": "Test Company",
        "email": "admin@testcompany.com",
        "company_name": "Test Company Inc",
        "plan": "pro",
        "status": "active",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "metadata": json.dumps({})
    })
    await mock_db_session.commit()
    
    # Create webhook endpoint
    query = text("""
        INSERT INTO webhook_endpoints (
            endpoint_id, tenant_id, url, events, secret, enabled,
            created_at, updated_at, metadata
        ) VALUES (
            :endpoint_id, :tenant_id, :url, :events, :secret, :enabled,
            :created_at, :updated_at, :metadata
        )
    """)
    
    endpoint_id = "webhook-123"
    await mock_db_session.execute(query, {
        "endpoint_id": endpoint_id,
        "tenant_id": tenant_id,
        "url": "https://testcompany.com/webhooks",
        "events": json.dumps(["tenant.created", "plan.upgraded"]),
        "secret": "test-secret",
        "enabled": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "metadata": json.dumps({})
    })
    await mock_db_session.commit()
    
    # Test webhook event triggering
    webhook_manager = WebhookManager(mock_db_session)
    
    # Mock webhook delivery
    with patch.object(webhook_manager, '_send_webhook_request', return_value=True):
        delivery_ids = await webhook_manager.trigger_webhook_event(
            WebhookEvent.TENANT_CREATED,
            tenant_id,
            {"tenant_id": tenant_id, "name": "Test Company"}
        )
        
        assert len(delivery_ids) == 1
        
        # Verify delivery was created
        deliveries = await webhook_manager.get_webhook_deliveries(endpoint_id)
        assert len(deliveries) == 1
        assert deliveries[0]["event"] == "tenant.created"
        assert deliveries[0]["status"] == "delivered"


@pytest.mark.asyncio
async def test_admin_portal_tenant_search(admin_app, mock_db_session):
    """Test admin portal tenant search functionality."""
    # Create test tenants
    query = text("""
        INSERT INTO tenants (
            tenant_id, name, email, company_name, plan, status,
            created_at, updated_at, metadata
        ) VALUES 
        (:tenant_id_1, :name_1, :email_1, :company_name_1, :plan_1, :status_1, :created_at, :updated_at, :metadata),
        (:tenant_id_2, :name_2, :email_2, :company_name_2, :plan_2, :status_2, :created_at, :updated_at, :metadata)
    """)
    
    now = datetime.now(timezone.utc)
    await mock_db_session.execute(query, {
        "tenant_id_1": "tenant-1",
        "name_1": "Company A",
        "email_1": "admin@companya.com",
        "company_name_1": "Company A Inc",
        "plan_1": "basic",
        "status_1": "active",
        "tenant_id_2": "tenant-2",
        "name_2": "Company B",
        "email_2": "admin@companyb.com",
        "company_name_2": "Company B Inc",
        "plan_2": "pro",
        "status_2": "active",
        "created_at": now,
        "updated_at": now,
        "metadata": json.dumps({})
    })
    await mock_db_session.commit()
    
    async with AsyncClient(app=admin_app, base_url="http://test") as client:
        # Test tenant search
        search_data = {
            "query": "Company A",
            "limit": 10,
            "offset": 0
        }
        
        response = await client.post("/api/v1/tenants/search", json=search_data)
        assert response.status_code == 200
        
        tenants = response.json()
        assert len(tenants) == 1
        assert tenants[0]["name"] == "Company A"
        assert tenants[0]["plan"] == "basic"
        
        # Test plan filtering
        search_data = {
            "plan": "pro",
            "limit": 10,
            "offset": 0
        }
        
        response = await client.post("/api/v1/tenants/search", json=search_data)
        assert response.status_code == 200
        
        tenants = response.json()
        assert len(tenants) == 1
        assert tenants[0]["name"] == "Company B"
        assert tenants[0]["plan"] == "pro"


@pytest.mark.asyncio
async def test_admin_portal_plan_management(admin_app, mock_db_session):
    """Test admin portal plan management."""
    async with AsyncClient(app=admin_app, base_url="http://test") as client:
        # Create new plan
        plan_data = {
            "plan_name": "premium",
            "display_name": "Premium",
            "description": "Premium plan with advanced features",
            "price_monthly": 199.00,
            "price_yearly": 1990.00,
            "features": ["All Pro features", "Priority support", "Custom integrations"],
            "limits": {"users": 100, "storage_gb": 500, "api_calls_per_day": 50000},
            "enabled": True
        }
        
        response = await client.post("/api/v1/plans", json=plan_data)
        assert response.status_code == 200
        
        plan_result = response.json()
        assert plan_result["plan_name"] == "premium"
        assert plan_result["price_monthly"] == 199.00
        assert "Priority support" in plan_result["features"]
        
        # Get all plans
        response = await client.get("/api/v1/plans")
        assert response.status_code == 200
        
        plans = response.json()
        assert len(plans) >= 4  # trial, basic, pro, premium
        plan_names = [plan["plan_name"] for plan in plans]
        assert "premium" in plan_names


@pytest.mark.asyncio
async def test_tenant_onboarding_manager(tenant_app, mock_db_session, mock_billing_client, mock_quota_client):
    """Test tenant onboarding manager functionality."""
    onboarding_manager = TenantOnboardingManager(
        mock_db_session,
        tenant_app.state.redis_client,
        tenant_app.state.auth_client,
        tenant_app.state.billing_client,
        tenant_app.state.quota_client
    )
    
    # Test tenant creation
    tenant = await onboarding_manager.create_tenant(
        name="Test Onboarding Company",
        email="admin@onboarding.com",
        company_name="Onboarding Inc",
        plan="trial",
        metadata={"source": "api"}
    )
    
    assert tenant.name == "Test Onboarding Company"
    assert tenant.email == "admin@onboarding.com"
    assert tenant.plan == "trial"
    assert tenant.status.value == "active"
    
    # Verify billing customer was created
    mock_billing_client.create_customer.assert_called_once()
    
    # Verify quotas were set
    mock_quota_client.create_tenant_quotas.assert_called_once()
    
    # Test getting tenant
    retrieved_tenant = await onboarding_manager.get_tenant(tenant.tenant_id)
    assert retrieved_tenant is not None
    assert retrieved_tenant.name == "Test Onboarding Company"


@pytest.mark.asyncio
async def test_plan_upgrade_manager(tenant_app, mock_db_session, mock_billing_client, mock_quota_client):
    """Test plan upgrade manager functionality."""
    # Create a tenant first
    query = text("""
        INSERT INTO tenants (
            tenant_id, name, email, company_name, plan, status,
            created_at, updated_at, metadata
        ) VALUES (
            :tenant_id, :name, :email, :company_name, :plan, :status,
            :created_at, :updated_at, :metadata
        )
    """)
    
    tenant_id = "upgrade-test-tenant"
    await mock_db_session.execute(query, {
        "tenant_id": tenant_id,
        "name": "Upgrade Test Company",
        "email": "admin@upgradetest.com",
        "company_name": "Upgrade Test Inc",
        "plan": "basic",
        "status": "active",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "metadata": json.dumps({})
    })
    await mock_db_session.commit()
    
    upgrade_manager = PlanUpgradeManager(
        mock_db_session,
        tenant_app.state.redis_client,
        tenant_app.state.billing_client,
        tenant_app.state.quota_client
    )
    
    # Test plan upgrade
    upgrade_result = await upgrade_manager.upgrade_plan(
        tenant_id=tenant_id,
        new_plan="pro",
        billing_cycle="monthly",
        payment_method_id="pm_123"
    )
    
    assert upgrade_result.tenant_id == tenant_id
    assert upgrade_result.old_plan == "basic"
    assert upgrade_result.new_plan == "pro"
    assert upgrade_result.billing_cycle == "monthly"
    
    # Verify subscription was updated
    mock_billing_client.update_subscription.assert_called_once()
    
    # Verify quotas were updated
    mock_quota_client.update_tenant_quotas.assert_called_once()
    
    # Verify upgrade was recorded in database
    query = text("SELECT * FROM plan_upgrade_history WHERE tenant_id = :tenant_id")
    result = await mock_db_session.execute(query, {"tenant_id": tenant_id})
    upgrade_row = result.fetchone()
    assert upgrade_row is not None
    assert upgrade_row.new_plan == "pro"


@pytest.mark.asyncio
async def test_webhook_signature_verification(tenant_app, mock_db_session):
    """Test webhook signature verification."""
    webhook_manager = WebhookManager(mock_db_session)
    
    # Create webhook endpoint
    endpoint_id = await webhook_manager.create_webhook_endpoint(
        tenant_id="test-tenant",
        url="https://test.com/webhook",
        events=[WebhookEvent.TENANT_CREATED],
        secret="test-secret-key",
        metadata={}
    )
    
    # Test signature verification
    payload = '{"event": "tenant.created", "data": {"tenant_id": "123"}}'
    
    # Generate valid signature
    import hmac
    import hashlib
    valid_signature = hmac.new(
        "test-secret-key".encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Verify valid signature
    is_valid = await webhook_manager.verify_webhook_signature(
        payload, f"sha256={valid_signature}", endpoint_id
    )
    assert is_valid is True
    
    # Test invalid signature
    is_valid = await webhook_manager.verify_webhook_signature(
        payload, "sha256=invalid-signature", endpoint_id
    )
    assert is_valid is False
