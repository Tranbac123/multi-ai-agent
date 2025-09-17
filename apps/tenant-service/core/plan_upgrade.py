"""Plan Upgrade Manager for tenant plan management and upgrades."""

import asyncio
import uuid
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = structlog.get_logger(__name__)


class UpgradeType(Enum):
    """Upgrade types."""
    IMMEDIATE = "immediate"
    SCHEDULED = "scheduled"
    TRIAL = "trial"


class UpgradeStatus(Enum):
    """Upgrade status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BillingCycle(Enum):
    """Billing cycles."""
    MONTHLY = "monthly"
    YEARLY = "yearly"


class PaymentStatus(Enum):
    """Payment status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


@dataclass
class UpgradeRequest:
    """Plan upgrade request."""
    upgrade_id: str
    tenant_id: str
    current_plan: str
    target_plan: str
    upgrade_type: UpgradeType
    billing_cycle: BillingCycle
    scheduled_at: Optional[datetime] = None
    status: UpgradeStatus = UpgradeStatus.PENDING
    created_at: datetime = None
    updated_at: datetime = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None


@dataclass
class PaymentInfo:
    """Payment information."""
    payment_id: str
    tenant_id: str
    upgrade_id: str
    amount: float
    currency: str
    billing_cycle: BillingCycle
    payment_method: Dict[str, Any]
    status: PaymentStatus
    created_at: datetime
    processed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    metadata: Dict[str, Any] = None


@dataclass
class PlanLimits:
    """Plan limits."""
    api_calls_per_month: int
    storage_gb: int
    users: int
    projects: int
    custom_models: int
    support_level: str
    sla_uptime: float


@dataclass
class PlanPricing:
    """Plan pricing."""
    monthly_price: float
    yearly_price: float
    currency: str
    trial_days: int
    setup_fee: float = 0.0


class PlanUpgradeManager:
    """Manages tenant plan upgrades and downgrades."""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.upgrade_requests: Dict[str, UpgradeRequest] = {}
        self.payment_info: Dict[str, PaymentInfo] = {}
        self.plan_limits: Dict[str, PlanLimits] = {}
        self.plan_pricing: Dict[str, PlanPricing] = {}
        self.upgrade_hooks: List[Callable] = []
        self._initialize_plan_data()
    
    def _initialize_plan_data(self):
        """Initialize plan limits and pricing."""
        try:
            # Plan limits
            self.plan_limits = {
                "free": PlanLimits(
                    api_calls_per_month=1000,
                    storage_gb=1,
                    users=1,
                    projects=3,
                    custom_models=0,
                    support_level="email",
                    sla_uptime=99.0
                ),
                "starter": PlanLimits(
                    api_calls_per_month=10000,
                    storage_gb=10,
                    users=5,
                    projects=15,
                    custom_models=1,
                    support_level="priority",
                    sla_uptime=99.5
                ),
                "professional": PlanLimits(
                    api_calls_per_month=100000,
                    storage_gb=100,
                    users=25,
                    projects=50,
                    custom_models=5,
                    support_level="24/7",
                    sla_uptime=99.9
                ),
                "enterprise": PlanLimits(
                    api_calls_per_month=-1,  # Unlimited
                    storage_gb=-1,
                    users=-1,
                    projects=-1,
                    custom_models=-1,
                    support_level="dedicated",
                    sla_uptime=99.99
                )
            }
            
            # Plan pricing
            self.plan_pricing = {
                "free": PlanPricing(
                    monthly_price=0.0,
                    yearly_price=0.0,
                    currency="USD",
                    trial_days=0
                ),
                "starter": PlanPricing(
                    monthly_price=29.0,
                    yearly_price=290.0,
                    currency="USD",
                    trial_days=14
                ),
                "professional": PlanPricing(
                    monthly_price=99.0,
                    yearly_price=990.0,
                    currency="USD",
                    trial_days=14
                ),
                "enterprise": PlanPricing(
                    monthly_price=0.0,  # Custom pricing
                    yearly_price=0.0,
                    currency="USD",
                    trial_days=30,
                    setup_fee=1000.0
                )
            }
            
            logger.info("Plan data initialized", 
                       plan_count=len(self.plan_limits),
                       pricing_count=len(self.plan_pricing))
            
        except Exception as e:
            logger.error("Failed to initialize plan data", error=str(e))
    
    async def request_upgrade(self, tenant_id: str, target_plan: str, 
                            upgrade_type: UpgradeType = UpgradeType.IMMEDIATE,
                            billing_cycle: BillingCycle = BillingCycle.MONTHLY,
                            scheduled_at: Optional[datetime] = None,
                            metadata: Optional[Dict[str, Any]] = None) -> str:
        """Request plan upgrade."""
        try:
            logger.info("Requesting plan upgrade",
                       tenant_id=tenant_id,
                       target_plan=target_plan,
                       upgrade_type=upgrade_type.value)
            
            # Get current plan
            current_plan = await self._get_tenant_plan(tenant_id)
            if not current_plan:
                raise ValueError("Tenant not found")
            
            # Validate upgrade
            if not await self._validate_upgrade(current_plan, target_plan):
                raise ValueError(f"Invalid upgrade from {current_plan} to {target_plan}")
            
            # Create upgrade request
            upgrade_id = str(uuid.uuid4())
            upgrade_request = UpgradeRequest(
                upgrade_id=upgrade_id,
                tenant_id=tenant_id,
                current_plan=current_plan,
                target_plan=target_plan,
                upgrade_type=upgrade_type,
                billing_cycle=billing_cycle,
                scheduled_at=scheduled_at,
                status=UpgradeStatus.PENDING,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                metadata=metadata or {}
            )
            
            # Store upgrade request
            self.upgrade_requests[upgrade_id] = upgrade_request
            
            # Process upgrade based on type
            if upgrade_type == UpgradeType.IMMEDIATE:
                await self._process_immediate_upgrade(upgrade_request)
            elif upgrade_type == UpgradeType.SCHEDULED:
                await self._schedule_upgrade(upgrade_request)
            elif upgrade_type == UpgradeType.TRIAL:
                await self._process_trial_upgrade(upgrade_request)
            
            logger.info("Plan upgrade requested successfully",
                       upgrade_id=upgrade_id,
                       tenant_id=tenant_id)
            
            return upgrade_id
            
        except Exception as e:
            logger.error("Failed to request upgrade",
                        tenant_id=tenant_id,
                        error=str(e))
            raise
    
    async def _get_tenant_plan(self, tenant_id: str) -> Optional[str]:
        """Get tenant's current plan."""
        try:
            query = text("SELECT plan_type FROM tenants WHERE tenant_id = :tenant_id")
            result = await self.db_session.execute(query, {"tenant_id": tenant_id})
            plan_type = result.scalar_one_or_none()
            return plan_type
            
        except Exception as e:
            logger.error("Failed to get tenant plan", error=str(e))
            return None
    
    async def _validate_upgrade(self, current_plan: str, target_plan: str) -> bool:
        """Validate upgrade request."""
        try:
            # Check if plans exist
            if current_plan not in self.plan_limits or target_plan not in self.plan_limits:
                return False
            
            # Check if target plan is higher tier
            plan_hierarchy = ["free", "starter", "professional", "enterprise"]
            
            try:
                current_index = plan_hierarchy.index(current_plan)
                target_index = plan_hierarchy.index(target_plan)
                
                # Allow upgrade to higher tier or same tier (for billing cycle change)
                return target_index >= current_index
                
            except ValueError:
                return False
            
        except Exception as e:
            logger.error("Failed to validate upgrade", error=str(e))
            return False
    
    async def _process_immediate_upgrade(self, upgrade_request: UpgradeRequest):
        """Process immediate upgrade."""
        try:
            logger.info("Processing immediate upgrade",
                       upgrade_id=upgrade_request.upgrade_id)
            
            upgrade_request.status = UpgradeStatus.PROCESSING
            upgrade_request.updated_at = datetime.now(timezone.utc)
            
            # Calculate pricing
            pricing = await self._calculate_upgrade_pricing(upgrade_request)
            
            if pricing["amount"] > 0:
                # Process payment
                payment_id = await self._process_payment(upgrade_request, pricing)
                
                if payment_id:
                    # Update tenant plan
                    await self._update_tenant_plan(upgrade_request)
                    
                    # Execute upgrade hooks
                    await self._execute_upgrade_hooks(upgrade_request)
                    
                    # Mark as completed
                    upgrade_request.status = UpgradeStatus.COMPLETED
                    upgrade_request.updated_at = datetime.now(timezone.utc)
                    
                    logger.info("Immediate upgrade completed",
                               upgrade_id=upgrade_request.upgrade_id)
                else:
                    upgrade_request.status = UpgradeStatus.FAILED
                    upgrade_request.error_message = "Payment processing failed"
                    upgrade_request.updated_at = datetime.now(timezone.utc)
            else:
                # Free upgrade (e.g., from paid to free)
                await self._update_tenant_plan(upgrade_request)
                await self._execute_upgrade_hooks(upgrade_request)
                
                upgrade_request.status = UpgradeStatus.COMPLETED
                upgrade_request.updated_at = datetime.now(timezone.utc)
                
                logger.info("Free upgrade completed",
                           upgrade_id=upgrade_request.upgrade_id)
            
        except Exception as e:
            logger.error("Failed to process immediate upgrade",
                        upgrade_id=upgrade_request.upgrade_id,
                        error=str(e))
            
            upgrade_request.status = UpgradeStatus.FAILED
            upgrade_request.error_message = str(e)
            upgrade_request.updated_at = datetime.now(timezone.utc)
    
    async def _schedule_upgrade(self, upgrade_request: UpgradeRequest):
        """Schedule upgrade for later execution."""
        try:
            logger.info("Scheduling upgrade",
                       upgrade_id=upgrade_request.upgrade_id,
                       scheduled_at=upgrade_request.scheduled_at)
            
            # In production, this would schedule a background job
            # For this implementation, we'll store the scheduled upgrade
            
            upgrade_request.status = UpgradeStatus.PENDING
            upgrade_request.updated_at = datetime.now(timezone.utc)
            
            logger.info("Upgrade scheduled successfully",
                       upgrade_id=upgrade_request.upgrade_id)
            
        except Exception as e:
            logger.error("Failed to schedule upgrade",
                        upgrade_id=upgrade_request.upgrade_id,
                        error=str(e))
            raise
    
    async def _process_trial_upgrade(self, upgrade_request: UpgradeRequest):
        """Process trial upgrade."""
        try:
            logger.info("Processing trial upgrade",
                       upgrade_id=upgrade_request.upgrade_id)
            
            upgrade_request.status = UpgradeStatus.PROCESSING
            upgrade_request.updated_at = datetime.now(timezone.utc)
            
            # Get trial period
            target_plan = upgrade_request.target_plan
            trial_days = self.plan_pricing[target_plan].trial_days
            
            if trial_days > 0:
                # Update tenant plan with trial
                await self._update_tenant_plan(upgrade_request, trial=True, trial_days=trial_days)
                
                # Execute upgrade hooks
                await self._execute_upgrade_hooks(upgrade_request)
                
                upgrade_request.status = UpgradeStatus.COMPLETED
                upgrade_request.updated_at = datetime.now(timezone.utc)
                
                logger.info("Trial upgrade completed",
                           upgrade_id=upgrade_request.upgrade_id,
                           trial_days=trial_days)
            else:
                upgrade_request.status = UpgradeStatus.FAILED
                upgrade_request.error_message = "No trial available for this plan"
                upgrade_request.updated_at = datetime.now(timezone.utc)
            
        except Exception as e:
            logger.error("Failed to process trial upgrade",
                        upgrade_id=upgrade_request.upgrade_id,
                        error=str(e))
            
            upgrade_request.status = UpgradeStatus.FAILED
            upgrade_request.error_message = str(e)
            upgrade_request.updated_at = datetime.now(timezone.utc)
    
    async def _calculate_upgrade_pricing(self, upgrade_request: UpgradeRequest) -> Dict[str, Any]:
        """Calculate upgrade pricing."""
        try:
            current_plan = upgrade_request.current_plan
            target_plan = upgrade_request.target_plan
            billing_cycle = upgrade_request.billing_cycle
            
            # Get current and target pricing
            current_pricing = self.plan_pricing[current_plan]
            target_pricing = self.plan_pricing[target_plan]
            
            # Calculate amounts
            if billing_cycle == BillingCycle.MONTHLY:
                current_amount = current_pricing.monthly_price
                target_amount = target_pricing.monthly_price
            else:
                current_amount = current_pricing.yearly_price
                target_amount = target_pricing.yearly_price
            
            # Calculate upgrade amount (prorated)
            upgrade_amount = max(0, target_amount - current_amount)
            
            # Add setup fee for enterprise
            if target_plan == "enterprise":
                upgrade_amount += target_pricing.setup_fee
            
            return {
                "amount": upgrade_amount,
                "currency": target_pricing.currency,
                "billing_cycle": billing_cycle.value,
                "current_amount": current_amount,
                "target_amount": target_amount,
                "setup_fee": target_pricing.setup_fee if target_plan == "enterprise" else 0.0
            }
            
        except Exception as e:
            logger.error("Failed to calculate upgrade pricing", error=str(e))
            return {"amount": 0.0, "currency": "USD", "billing_cycle": "monthly"}
    
    async def _process_payment(self, upgrade_request: UpgradeRequest, pricing: Dict[str, Any]) -> Optional[str]:
        """Process payment for upgrade."""
        try:
            if pricing["amount"] <= 0:
                return "free_upgrade"
            
            payment_id = str(uuid.uuid4())
            
            # Create payment info
            payment_info = PaymentInfo(
                payment_id=payment_id,
                tenant_id=upgrade_request.tenant_id,
                upgrade_id=upgrade_request.upgrade_id,
                amount=pricing["amount"],
                currency=pricing["currency"],
                billing_cycle=upgrade_request.billing_cycle,
                payment_method=upgrade_request.metadata.get("payment_method", {}),
                status=PaymentStatus.PROCESSING,
                created_at=datetime.now(timezone.utc),
                metadata=upgrade_request.metadata
            )
            
            # Store payment info
            self.payment_info[payment_id] = payment_info
            
            # In production, this would integrate with payment processor
            # For this implementation, we'll simulate payment processing
            
            await asyncio.sleep(1)  # Simulate payment processing time
            
            # Simulate successful payment
            payment_info.status = PaymentStatus.COMPLETED
            payment_info.processed_at = datetime.now(timezone.utc)
            
            logger.info("Payment processed successfully",
                       payment_id=payment_id,
                       amount=pricing["amount"])
            
            return payment_id
            
        except Exception as e:
            logger.error("Failed to process payment", error=str(e))
            return None
    
    async def _update_tenant_plan(self, upgrade_request: UpgradeRequest, 
                                trial: bool = False, trial_days: int = 0):  # noqa: F841
        """Update tenant plan in database."""
        try:
            query = text("""
                UPDATE tenants 
                SET plan_type = :plan_type,
                    updated_at = :updated_at
                WHERE tenant_id = :tenant_id
            """)
            
            await self.db_session.execute(query, {
                "tenant_id": upgrade_request.tenant_id,
                "plan_type": upgrade_request.target_plan,
                "updated_at": datetime.now(timezone.utc)
            })
            
            await self.db_session.commit()
            
            logger.info("Tenant plan updated",
                       tenant_id=upgrade_request.tenant_id,
                       new_plan=upgrade_request.target_plan)
            
        except Exception as e:
            logger.error("Failed to update tenant plan", error=str(e))
            await self.db_session.rollback()
            raise
    
    async def _execute_upgrade_hooks(self, upgrade_request: UpgradeRequest):
        """Execute upgrade hooks."""
        try:
            for hook in self.upgrade_hooks:
                try:
                    await hook(upgrade_request)
                except Exception as e:
                    logger.error("Upgrade hook failed", error=str(e))
            
            logger.info("Upgrade hooks executed",
                       upgrade_id=upgrade_request.upgrade_id,
                       hook_count=len(self.upgrade_hooks))
            
        except Exception as e:
            logger.error("Failed to execute upgrade hooks", error=str(e))
    
    async def add_upgrade_hook(self, hook: Callable):
        """Add upgrade hook."""
        try:
            self.upgrade_hooks.append(hook)
            logger.info("Upgrade hook added", hook_count=len(self.upgrade_hooks))
            
        except Exception as e:
            logger.error("Failed to add upgrade hook", error=str(e))
    
    async def get_upgrade_status(self, upgrade_id: str) -> Optional[Dict[str, Any]]:
        """Get upgrade status."""
        try:
            if upgrade_id not in self.upgrade_requests:
                return None
            
            upgrade_request = self.upgrade_requests[upgrade_id]
            
            return {
                "upgrade_id": upgrade_id,
                "tenant_id": upgrade_request.tenant_id,
                "current_plan": upgrade_request.current_plan,
                "target_plan": upgrade_request.target_plan,
                "upgrade_type": upgrade_request.upgrade_type.value,
                "billing_cycle": upgrade_request.billing_cycle.value,
                "status": upgrade_request.status.value,
                "scheduled_at": upgrade_request.scheduled_at.isoformat() if upgrade_request.scheduled_at else None,
                "created_at": upgrade_request.created_at.isoformat(),
                "updated_at": upgrade_request.updated_at.isoformat(),
                "error_message": upgrade_request.error_message,
                "metadata": upgrade_request.metadata
            }
            
        except Exception as e:
            logger.error("Failed to get upgrade status", error=str(e))
            return None
    
    async def cancel_upgrade(self, upgrade_id: str, reason: str = "User requested") -> bool:
        """Cancel upgrade request."""
        try:
            logger.info("Cancelling upgrade", upgrade_id=upgrade_id)
            
            if upgrade_id not in self.upgrade_requests:
                return False
            
            upgrade_request = self.upgrade_requests[upgrade_id]
            
            if upgrade_request.status in [UpgradeStatus.COMPLETED, UpgradeStatus.FAILED]:
                return False
            
            upgrade_request.status = UpgradeStatus.CANCELLED
            upgrade_request.updated_at = datetime.now(timezone.utc)
            upgrade_request.error_message = reason
            
            logger.info("Upgrade cancelled successfully", upgrade_id=upgrade_id)
            return True
            
        except Exception as e:
            logger.error("Failed to cancel upgrade", error=str(e))
            return False
    
    async def get_tenant_upgrades(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get all upgrades for a tenant."""
        try:
            upgrades = []
            
            for upgrade_request in self.upgrade_requests.values():
                if upgrade_request.tenant_id == tenant_id:
                    upgrade_data = await self.get_upgrade_status(upgrade_request.upgrade_id)
                    if upgrade_data:
                        upgrades.append(upgrade_data)
            
            # Sort by creation date (newest first)
            upgrades.sort(key=lambda x: x["created_at"], reverse=True)
            
            return upgrades
            
        except Exception as e:
            logger.error("Failed to get tenant upgrades", error=str(e))
            return []
    
    async def get_plan_limits(self, plan_type: str) -> Optional[PlanLimits]:
        """Get plan limits."""
        try:
            return self.plan_limits.get(plan_type)
            
        except Exception as e:
            logger.error("Failed to get plan limits", error=str(e))
            return None
    
    async def get_plan_pricing(self, plan_type: str) -> Optional[PlanPricing]:
        """Get plan pricing."""
        try:
            return self.plan_pricing.get(plan_type)
            
        except Exception as e:
            logger.error("Failed to get plan pricing", error=str(e))
            return None
    
    async def process_scheduled_upgrades(self):
        """Process scheduled upgrades."""
        try:
            current_time = datetime.now(timezone.utc)
            scheduled_upgrades = []
            
            for upgrade_request in self.upgrade_requests.values():
                if (upgrade_request.status == UpgradeStatus.PENDING and
                    upgrade_request.scheduled_at and
                    upgrade_request.scheduled_at <= current_time):
                    scheduled_upgrades.append(upgrade_request)
            
            # Process scheduled upgrades
            for upgrade_request in scheduled_upgrades:
                try:
                    await self._process_immediate_upgrade(upgrade_request)
                except Exception as e:
                    logger.error("Failed to process scheduled upgrade",
                               upgrade_id=upgrade_request.upgrade_id,
                               error=str(e))
            
            if scheduled_upgrades:
                logger.info("Processed scheduled upgrades", count=len(scheduled_upgrades))
            
        except Exception as e:
            logger.error("Failed to process scheduled upgrades", error=str(e))
