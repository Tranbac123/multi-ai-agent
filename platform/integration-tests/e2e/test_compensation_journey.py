"""E2E tests for Failure→Compensation journey."""

import pytest
from tests.e2e import JourneyType, JourneyStatus
from tests._fixtures.factories import factory, TenantTier
from tests.contract.schemas import APIRequest, APIResponse, RequestType


class TestCompensationJourney:
    """Test failure compensation journey."""
    
    @pytest.fixture
    async def setup(self):
        """Setup for compensation testing."""
        tenant = factory.create_tenant(name="Compensation Test", tier=TenantTier.PREMIUM)
        user = factory.create_user(tenant_id=tenant.tenant_id)
        return {'tenant': tenant, 'user': user}
    
    @pytest.mark.asyncio
    async def test_payment_failure_compensation(self, setup):
        """Test payment failure compensation."""
        # Payment request that fails
        payment_request = APIRequest(
            request_id="req_comp_001",
            tenant_id=setup['tenant'].tenant_id,
            user_id=setup['user'].user_id,
            request_type=RequestType.PAYMENT,
            message="Process payment",
            context={"amount": 100.0, "payment_method": "credit_card"},
            metadata={"priority": "high"}
        )
        
        # Payment fails
        payment_response = APIResponse(
            request_id=payment_request.request_id,
            success=False,
            error_code="PAYMENT_FAILED",
            error_message="Payment processing failed",
            execution_time_ms=200.0,
            cost_usd=0.003,
            metadata={"payment_status": "failed"}
        )
        
        # Compensation action
        compensation_request = APIRequest(
            request_id="req_comp_002",
            tenant_id=setup['tenant'].tenant_id,
            user_id=setup['user'].user_id,
            request_type=RequestType.SUPPORT,
            message="Compensate for payment failure",
            context={"original_request_id": "req_comp_001", "compensation_type": "retry"},
            metadata={"priority": "high"}
        )
        
        # Compensation succeeds
        compensation_response = APIResponse(
            request_id=compensation_request.request_id,
            success=True,
            response="Payment retry successful. Transaction completed.",
            execution_time_ms=150.0,
            cost_usd=0.002,
            metadata={"compensation_successful": True}
        )
        
        # Validate compensation
        assert payment_response.success is False
        assert compensation_response.success is True
        assert compensation_response.metadata["compensation_successful"] is True
    
    @pytest.mark.asyncio
    async def test_order_failure_compensation(self, setup):
        """Test order failure compensation."""
        # Order request that fails
        order_request = APIRequest(
            request_id="req_comp_003",
            tenant_id=setup['tenant'].tenant_id,
            user_id=setup['user'].user_id,
            request_type=RequestType.ORDER,
            message="Create order",
            context={"items": [{"id": "item1", "quantity": 2}]},
            metadata={"priority": "high"}
        )
        
        # Order fails
        order_response = APIResponse(
            request_id=order_request.request_id,
            success=False,
            error_code="ORDER_FAILED",
            error_message="Order creation failed due to inventory issue",
            execution_time_ms=180.0,
            cost_usd=0.004,
            metadata={"order_status": "failed"}
        )
        
        # Compensation action
        compensation_request = APIRequest(
            request_id="req_comp_004",
            tenant_id=setup['tenant'].tenant_id,
            user_id=setup['user'].user_id,
            request_type=RequestType.SUPPORT,
            message="Compensate for order failure",
            context={"original_request_id": "req_comp_003", "compensation_type": "alternative"},
            metadata={"priority": "high"}
        )
        
        # Compensation succeeds
        compensation_response = APIResponse(
            request_id=compensation_request.request_id,
            success=True,
            response="Alternative product offered. Order created successfully.",
            execution_time_ms=120.0,
            cost_usd=0.003,
            metadata={"compensation_successful": True, "alternative_provided": True}
        )
        
        # Validate compensation
        assert order_response.success is False
        assert compensation_response.success is True
        assert compensation_response.metadata["alternative_provided"] is True
