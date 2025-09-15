"""E2E test data fixtures with Pydantic validation."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from uuid import uuid4
from pydantic import BaseModel, Field, validator
import json


class UserContext(BaseModel):
    """User context for E2E tests."""
    user_id: str = Field(default_factory=lambda: f"user_{uuid4().hex[:8]}")
    tenant_id: str = Field(default_factory=lambda: f"tenant_{uuid4().hex[:8]}")
    session_id: str = Field(default_factory=lambda: f"session_{uuid4().hex[:8]}")
    role: str = "customer"
    preferences: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        extra = "forbid"


class FAQContext(BaseModel):
    """FAQ handling context."""
    question: str
    expected_category: str
    expected_response_type: str = "informational"
    user_context: UserContext
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrderContext(BaseModel):
    """Order management context."""
    order_id: str = Field(default_factory=lambda: f"order_{uuid4().hex[:8]}")
    customer_id: str
    items: List[Dict[str, Any]]
    total_amount: float
    currency: str = "USD"
    status: str = "pending"
    user_context: UserContext
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TrackingContext(BaseModel):
    """Order tracking context."""
    tracking_number: str = Field(default_factory=lambda: f"TRK{uuid4().hex[:8].upper()}")
    order_id: str
    carrier: str = "DHL"
    estimated_delivery: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(days=3))
    user_context: UserContext
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LeadContext(BaseModel):
    """Lead capture context."""
    lead_id: str = Field(default_factory=lambda: f"lead_{uuid4().hex[:8]}")
    contact_info: Dict[str, str]
    source: str = "website"
    interest_level: str = "high"
    user_context: UserContext
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PaymentContext(BaseModel):
    """Payment processing context."""
    payment_id: str = Field(default_factory=lambda: f"pay_{uuid4().hex[:8]}")
    amount: float = Field(gt=0)
    currency: str = "USD"
    payment_method: str = "credit_card"
    user_context: UserContext
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MultiChannelContext(BaseModel):
    """Multi-channel ingress context."""
    channel: str = Field(pattern="^(web|facebook|zalo|telegram)$")
    message: str
    channel_specific_data: Dict[str, Any] = Field(default_factory=dict)
    user_context: UserContext
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CompensationContext(BaseModel):
    """Saga compensation context."""
    saga_id: str = Field(default_factory=lambda: f"saga_{uuid4().hex[:8]}")
    steps: List[Dict[str, Any]]
    failure_step: Optional[int] = None
    user_context: UserContext
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AuditLog(BaseModel):
    """Audit log entry."""
    log_id: str = Field(default_factory=lambda: f"log_{uuid4().hex[:8]}")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tenant_id: str
    user_id: str
    action: str
    resource_type: str
    resource_id: str
    details: Dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TestDataFactory:
    """Factory for creating test data."""
    
    @staticmethod
    def create_faq_scenarios() -> List[FAQContext]:
        """Create FAQ test scenarios."""
        return [
            FAQContext(
                question="What are your business hours?",
                expected_category="business_info",
                expected_response_type="informational",
                user_context=UserContext(),
                metadata={"priority": "low"}
            ),
            FAQContext(
                question="How do I track my order?",
                expected_category="order_support",
                expected_response_type="actionable",
                user_context=UserContext(),
                metadata={"priority": "medium"}
            ),
            FAQContext(
                question="What is your return policy?",
                expected_category="policies",
                expected_response_type="informational",
                user_context=UserContext(),
                metadata={"priority": "medium"}
            )
        ]
    
    @staticmethod
    def create_order_scenarios() -> List[OrderContext]:
        """Create order test scenarios."""
        return [
            OrderContext(
                customer_id="cust_123",
                items=[
                    {"product_id": "prod_001", "quantity": 2, "price": 29.99},
                    {"product_id": "prod_002", "quantity": 1, "price": 49.99}
                ],
                total_amount=109.97,
                user_context=UserContext(),
                metadata={"source": "web", "promo_code": "SAVE10"}
            ),
            OrderContext(
                customer_id="cust_456",
                items=[
                    {"product_id": "prod_003", "quantity": 1, "price": 99.99}
                ],
                total_amount=99.99,
                user_context=UserContext(),
                metadata={"source": "mobile", "express_shipping": True}
            )
        ]
    
    @staticmethod
    def create_tracking_scenarios() -> List[TrackingContext]:
        """Create tracking test scenarios."""
        return [
            TrackingContext(
                order_id="order_123",
                carrier="DHL",
                estimated_delivery=datetime.utcnow() + timedelta(days=2),
                user_context=UserContext(),
                metadata={"priority": "express"}
            ),
            TrackingContext(
                order_id="order_456",
                carrier="FedEx",
                estimated_delivery=datetime.utcnow() + timedelta(days=5),
                user_context=UserContext(),
                metadata={"priority": "standard"}
            )
        ]
    
    @staticmethod
    def create_lead_scenarios() -> List[LeadContext]:
        """Create lead capture scenarios."""
        return [
            LeadContext(
                contact_info={
                    "name": "John Doe",
                    "email": "john@example.com",
                    "phone": "+1234567890"
                },
                source="website",
                interest_level="high",
                user_context=UserContext(),
                metadata={"product_interest": "enterprise", "budget": "10k-50k"}
            ),
            LeadContext(
                contact_info={
                    "name": "Jane Smith",
                    "email": "jane@example.com",
                    "phone": "+1987654321"
                },
                source="facebook",
                interest_level="medium",
                user_context=UserContext(),
                metadata={"product_interest": "starter", "budget": "1k-5k"}
            )
        ]
    
    @staticmethod
    def create_payment_scenarios() -> List[PaymentContext]:
        """Create payment test scenarios."""
        return [
            PaymentContext(
                amount=109.97,
                currency="USD",
                payment_method="credit_card",
                user_context=UserContext(),
                metadata={"card_type": "visa", "last_four": "1234"}
            ),
            PaymentContext(
                amount=99.99,
                currency="USD",
                payment_method="paypal",
                user_context=UserContext(),
                metadata={"paypal_email": "user@example.com"}
            )
        ]
    
    @staticmethod
    def create_multi_channel_scenarios() -> List[MultiChannelContext]:
        """Create multi-channel test scenarios."""
        return [
            MultiChannelContext(
                channel="web",
                message="I need help with my order #12345",
                channel_specific_data={"user_agent": "Mozilla/5.0"},
                user_context=UserContext(),
                metadata={"session_id": "web_session_123"}
            ),
            MultiChannelContext(
                channel="facebook",
                message="Hi, I want to know about your products",
                channel_specific_data={"page_id": "123456789", "post_id": "987654321"},
                user_context=UserContext(),
                metadata={"messenger_id": "fb_user_123"}
            ),
            MultiChannelContext(
                channel="zalo",
                message="Xin chào, tôi muốn hỏi về dịch vụ",
                channel_specific_data={"zalo_user_id": "zalo_123"},
                user_context=UserContext(),
                metadata={"language": "vi"}
            )
        ]
    
    @staticmethod
    def create_compensation_scenarios() -> List[CompensationContext]:
        """Create saga compensation scenarios."""
        return [
            CompensationContext(
                steps=[
                    {"step": 1, "action": "create_order", "compensate": "cancel_order"},
                    {"step": 2, "action": "charge_payment", "compensate": "refund_payment"},
                    {"step": 3, "action": "reserve_inventory", "compensate": "release_inventory"}
                ],
                failure_step=2,
                user_context=UserContext(),
                metadata={"retry_count": 0}
            ),
            CompensationContext(
                steps=[
                    {"step": 1, "action": "send_email", "compensate": "send_apology_email"},
                    {"step": 2, "action": "update_database", "compensate": "rollback_database"},
                    {"step": 3, "action": "notify_external", "compensate": "cancel_notification"}
                ],
                failure_step=3,
                user_context=UserContext(),
                metadata={"retry_count": 1}
            )
        ]
    
    @staticmethod
    def create_audit_logs(tenant_id: str, user_id: str, count: int = 10) -> List[AuditLog]:
        """Create audit log entries."""
        logs = []
        actions = ["create", "read", "update", "delete", "login", "logout"]
        resource_types = ["order", "payment", "user", "product", "lead"]
        
        for i in range(count):
            logs.append(AuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                action=actions[i % len(actions)],
                resource_type=resource_types[i % len(resource_types)],
                resource_id=f"resource_{i}",
                details={"test": True, "iteration": i},
                success=i % 3 != 0  # Some failures
            ))
        
        return logs


# External gateway mocks
class ExternalGatewayMock:
    """Mock for external gateways."""
    
    @staticmethod
    async def mock_payment_gateway(payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock payment gateway response."""
        return {
            "transaction_id": f"txn_{uuid4().hex[:8]}",
            "status": "success" if payment_data.get("amount", 0) > 0 else "failed",
            "gateway_response": {
                "code": "00",
                "message": "Approved"
            },
            "processed_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    async def mock_shipping_carrier(tracking_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock shipping carrier response."""
        return {
            "tracking_number": tracking_data.get("tracking_number"),
            "status": "in_transit",
            "location": "Distribution Center",
            "estimated_delivery": (datetime.utcnow() + timedelta(days=2)).isoformat(),
            "events": [
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": "picked_up",
                    "location": "Origin Facility"
                }
            ]
        }
    
    @staticmethod
    async def mock_crm_system(lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock CRM system response."""
        return {
            "lead_id": lead_data.get("lead_id"),
            "status": "created",
            "assigned_to": "sales_rep_001",
            "created_at": datetime.utcnow().isoformat(),
            "priority": lead_data.get("interest_level", "medium")
        }
    
    @staticmethod
    async def mock_facebook_api(message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock Facebook API response."""
        return {
            "message_id": f"msg_{uuid4().hex[:8]}",
            "recipient_id": message_data.get("user_id"),
            "timestamp": int(datetime.utcnow().timestamp()),
            "status": "sent"
        }
    
    @staticmethod
    async def mock_zalo_api(message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock Zalo API response."""
        return {
            "message_id": f"zalo_{uuid4().hex[:8]}",
            "user_id": message_data.get("user_id"),
            "timestamp": int(datetime.utcnow().timestamp()),
            "status": "delivered"
        }
