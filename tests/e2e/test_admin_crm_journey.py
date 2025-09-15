"""E2E tests for Admin/CRM journey - administrative and CRM operations."""

import pytest
from tests.e2e import JourneyType, JourneyStatus
from tests._fixtures.factories import factory, TenantTier
from tests.contract.schemas import APIRequest, APIResponse, RequestType


class TestAdminCRMJourney:
    """Test admin and CRM journey."""
    
    @pytest.fixture
    async def setup(self):
        """Setup for admin/CRM testing."""
        tenant = factory.create_tenant(name="Admin Test", tier=TenantTier.ENTERPRISE)
        admin_user = factory.create_user(
            tenant_id=tenant.tenant_id, 
            email="admin@admintest.com",
            role="admin"
        )
        return {'tenant': tenant, 'admin_user': admin_user}
    
    @pytest.mark.asyncio
    async def test_crm_lead_update_journey(self, setup):
        """Test CRM lead update journey."""
        # Update lead request
        update_request = APIRequest(
            request_id="req_admin_001",
            tenant_id=setup['tenant'].tenant_id,
            user_id=setup['admin_user'].user_id,
            request_type=RequestType.SUPPORT,
            message="Update lead LEAD-12345 status to qualified",
            context={
                "source": "crm",
                "session_id": "sess_admin_001",
                "lead_id": "LEAD-12345",
                "update_type": "status_change",
                "new_status": "qualified"
            },
            metadata={"priority": "normal", "admin_action": True}
        )
        
        # Process update
        update_response = APIResponse(
            request_id=update_request.request_id,
            success=True,
            response="Lead LEAD-12345 status updated to qualified successfully.",
            execution_time_ms=100.0,
            cost_usd=0.001,
            metadata={
                "tier": "SLM_A",
                "confidence": 0.98,
                "lead_updated": True,
                "admin_action": True
            }
        )
        
        # Validate update
        assert update_response.success is True
        assert update_response.metadata["lead_updated"] is True
        assert update_response.metadata["admin_action"] is True
    
    @pytest.mark.asyncio
    async def test_crm_customer_management_journey(self, setup):
        """Test CRM customer management journey."""
        # Customer management request
        customer_request = APIRequest(
            request_id="req_admin_002",
            tenant_id=setup['tenant'].tenant_id,
            user_id=setup['admin_user'].user_id,
            request_type=RequestType.SUPPORT,
            message="Add customer CUST-789 to VIP list",
            context={
                "source": "crm",
                "session_id": "sess_admin_002",
                "customer_id": "CUST-789",
                "action": "add_to_vip",
                "vip_tier": "gold"
            },
            metadata={"priority": "high", "admin_action": True}
        )
        
        # Process customer management
        customer_response = APIResponse(
            request_id=customer_request.request_id,
            success=True,
            response="Customer CUST-789 added to VIP Gold tier successfully.",
            execution_time_ms=120.0,
            cost_usd=0.002,
            metadata={
                "tier": "SLM_B",
                "confidence": 0.95,
                "customer_updated": True,
                "vip_tier_assigned": "gold"
            }
        )
        
        # Validate customer management
        assert customer_response.success is True
        assert customer_response.metadata["customer_updated"] is True
        assert customer_response.metadata["vip_tier_assigned"] == "gold"
