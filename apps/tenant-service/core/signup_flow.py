"""Tenant Signup Flow Manager for self-serve tenant onboarding."""

import asyncio
import json
import uuid
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = structlog.get_logger(__name__)


class SignupStep(Enum):
    """Signup flow steps."""
    INITIAL = "initial"
    EMAIL_VERIFICATION = "email_verification"
    COMPANY_INFO = "company_info"
    PLAN_SELECTION = "plan_selection"
    PAYMENT_SETUP = "payment_setup"
    BILLING_INFO = "billing_info"
    TERMS_ACCEPTANCE = "terms_acceptance"
    ACCOUNT_CREATION = "account_creation"
    WELCOME = "welcome"
    COMPLETED = "completed"


class SignupStatus(Enum):
    """Signup status."""
    IN_PROGRESS = "in_progress"
    PENDING_VERIFICATION = "pending_verification"
    PENDING_PAYMENT = "pending_payment"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    FAILED = "failed"


class PlanType(Enum):
    """Plan types."""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


@dataclass
class SignupData:
    """Signup data structure."""
    email: str
    password: str
    first_name: str
    last_name: str
    company_name: str
    company_size: str
    industry: str
    phone_number: str
    country: str
    timezone: str
    plan_type: PlanType
    billing_address: Dict[str, str]
    payment_method: Dict[str, str]
    terms_accepted: bool
    marketing_consent: bool
    data_region: str = "us-east-1"
    metadata: Dict[str, Any] = None


@dataclass
class SignupSession:
    """Signup session data."""
    session_id: str
    email: str
    current_step: SignupStep
    status: SignupStatus
    signup_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    verification_token: Optional[str] = None
    verification_expires_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None


@dataclass
class PlanDetails:
    """Plan details."""
    plan_type: PlanType
    name: str
    description: str
    price_monthly: float
    price_yearly: float
    features: List[str]
    limits: Dict[str, int]
    trial_days: int
    available: bool


class TenantSignupFlowManager:
    """Manages tenant signup flow for self-serve onboarding."""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.signup_sessions: Dict[str, SignupSession] = {}
        self.available_plans: Dict[PlanType, PlanDetails] = {}
        self.step_handlers: Dict[SignupStep, Callable] = {}
        self._initialize_plans()
        self._initialize_step_handlers()
    
    def _initialize_plans(self):
        """Initialize available plans."""
        try:
            self.available_plans = {
                PlanType.FREE: PlanDetails(
                    plan_type=PlanType.FREE,
                    name="Free Plan",
                    description="Perfect for getting started with AI automation",
                    price_monthly=0.0,
                    price_yearly=0.0,
                    features=[
                        "Up to 1,000 API calls per month",
                        "Basic AI models",
                        "Email support",
                        "Standard data processing"
                    ],
                    limits={
                        "api_calls_per_month": 1000,
                        "storage_gb": 1,
                        "users": 1,
                        "projects": 3
                    },
                    trial_days=0,
                    available=True
                ),
                PlanType.STARTER: PlanDetails(
                    plan_type=PlanType.STARTER,
                    name="Starter Plan",
                    description="Great for small teams and growing businesses",
                    price_monthly=29.0,
                    price_yearly=290.0,
                    features=[
                        "Up to 10,000 API calls per month",
                        "Advanced AI models",
                        "Priority support",
                        "Enhanced data processing",
                        "Basic analytics"
                    ],
                    limits={
                        "api_calls_per_month": 10000,
                        "storage_gb": 10,
                        "users": 5,
                        "projects": 15
                    },
                    trial_days=14,
                    available=True
                ),
                PlanType.PROFESSIONAL: PlanDetails(
                    plan_type=PlanType.PROFESSIONAL,
                    name="Professional Plan",
                    description="Ideal for growing teams and advanced use cases",
                    price_monthly=99.0,
                    price_yearly=990.0,
                    features=[
                        "Up to 100,000 API calls per month",
                        "Premium AI models",
                        "24/7 support",
                        "Advanced analytics",
                        "Custom integrations",
                        "Team collaboration tools"
                    ],
                    limits={
                        "api_calls_per_month": 100000,
                        "storage_gb": 100,
                        "users": 25,
                        "projects": 50
                    },
                    trial_days=14,
                    available=True
                ),
                PlanType.ENTERPRISE: PlanDetails(
                    plan_type=PlanType.ENTERPRISE,
                    name="Enterprise Plan",
                    description="Custom solutions for large organizations",
                    price_monthly=0.0,  # Custom pricing
                    price_yearly=0.0,
                    features=[
                        "Unlimited API calls",
                        "Custom AI models",
                        "Dedicated support",
                        "Advanced security",
                        "Custom integrations",
                        "SLA guarantees",
                        "On-premise deployment"
                    ],
                    limits={
                        "api_calls_per_month": -1,  # Unlimited
                        "storage_gb": -1,
                        "users": -1,
                        "projects": -1
                    },
                    trial_days=30,
                    available=True
                )
            }
            
            logger.info("Available plans initialized", plan_count=len(self.available_plans))
            
        except Exception as e:
            logger.error("Failed to initialize plans", error=str(e))
    
    def _initialize_step_handlers(self):
        """Initialize step handlers."""
        try:
            self.step_handlers = {
                SignupStep.INITIAL: self._handle_initial_step,
                SignupStep.EMAIL_VERIFICATION: self._handle_email_verification_step,
                SignupStep.COMPANY_INFO: self._handle_company_info_step,
                SignupStep.PLAN_SELECTION: self._handle_plan_selection_step,
                SignupStep.PAYMENT_SETUP: self._handle_payment_setup_step,
                SignupStep.BILLING_INFO: self._handle_billing_info_step,
                SignupStep.TERMS_ACCEPTANCE: self._handle_terms_acceptance_step,
                SignupStep.ACCOUNT_CREATION: self._handle_account_creation_step,
                SignupStep.WELCOME: self._handle_welcome_step
            }
            
            logger.info("Step handlers initialized", handler_count=len(self.step_handlers))
            
        except Exception as e:
            logger.error("Failed to initialize step handlers", error=str(e))
    
    async def start_signup(self, email: str, password: str, first_name: str, 
                          last_name: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Start tenant signup process."""
        try:
            logger.info("Starting tenant signup", email=email)
            
            # Check if email already exists
            if await self._email_exists(email):
                raise ValueError("Email already exists")
            
            # Create signup session
            session_id = str(uuid.uuid4())
            signup_session = SignupSession(
                session_id=session_id,
                email=email,
                current_step=SignupStep.INITIAL,
                status=SignupStatus.IN_PROGRESS,
                signup_data={
                    "email": email,
                    "password": password,
                    "first_name": first_name,
                    "last_name": last_name
                },
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
                metadata=metadata or {}
            )
            
            # Store session
            self.signup_sessions[session_id] = signup_session
            
            # Send email verification
            await self._send_email_verification(signup_session)
            
            # Update session to email verification step
            signup_session.current_step = SignupStep.EMAIL_VERIFICATION
            signup_session.status = SignupStatus.PENDING_VERIFICATION
            signup_session.updated_at = datetime.now(timezone.utc)
            
            logger.info("Tenant signup started", session_id=session_id, email=email)
            
            return session_id
            
        except Exception as e:
            logger.error("Failed to start signup", email=email, error=str(e))
            raise
    
    async def _email_exists(self, email: str) -> bool:
        """Check if email already exists in the system."""
        try:
            query = text("SELECT COUNT(*) FROM tenants WHERE email = :email")
            result = await self.db_session.execute(query, {"email": email})
            count = result.scalar()
            return count > 0
            
        except Exception as e:
            logger.error("Failed to check email existence", email=email, error=str(e))
            return False
    
    async def _send_email_verification(self, signup_session: SignupSession):
        """Send email verification."""
        try:
            # Generate verification token
            verification_token = str(uuid.uuid4())
            verification_expires = datetime.now(timezone.utc) + timedelta(hours=1)
            
            signup_session.verification_token = verification_token
            signup_session.verification_expires_at = verification_expires
            
            # In production, this would send actual email
            logger.info("Email verification sent",
                       session_id=signup_session.session_id,
                       email=signup_session.email,
                       verification_token=verification_token)
            
        except Exception as e:
            logger.error("Failed to send email verification", error=str(e))
            raise
    
    async def verify_email(self, session_id: str, verification_token: str) -> bool:
        """Verify email address."""
        try:
            logger.info("Verifying email", session_id=session_id)
            
            if session_id not in self.signup_sessions:
                raise ValueError("Signup session not found")
            
            signup_session = self.signup_sessions[session_id]
            
            # Check if session is expired
            if signup_session.expires_at < datetime.now(timezone.utc):
                signup_session.status = SignupStatus.ABANDONED
                raise ValueError("Signup session expired")
            
            # Check verification token
            if (signup_session.verification_token != verification_token or
                signup_session.verification_expires_at < datetime.now(timezone.utc)):
                raise ValueError("Invalid or expired verification token")
            
            # Move to next step
            signup_session.current_step = SignupStep.COMPANY_INFO
            signup_session.status = SignupStatus.IN_PROGRESS
            signup_session.updated_at = datetime.now(timezone.utc)
            signup_session.verification_token = None
            signup_session.verification_expires_at = None
            
            logger.info("Email verified successfully", session_id=session_id)
            
            return True
            
        except Exception as e:
            logger.error("Failed to verify email", session_id=session_id, error=str(e))
            raise
    
    async def update_signup_data(self, session_id: str, step: SignupStep, 
                                data: Dict[str, Any]) -> bool:
        """Update signup data for a specific step."""
        try:
            logger.info("Updating signup data",
                       session_id=session_id,
                       step=step.value)
            
            if session_id not in self.signup_sessions:
                raise ValueError("Signup session not found")
            
            signup_session = self.signup_sessions[session_id]
            
            # Check if session is expired
            if signup_session.expires_at < datetime.now(timezone.utc):
                signup_session.status = SignupStatus.ABANDONED
                raise ValueError("Signup session expired")
            
            # Update signup data
            signup_session.signup_data.update(data)
            signup_session.updated_at = datetime.now(timezone.utc)
            
            # Execute step handler
            if step in self.step_handlers:
                await self.step_handlers[step](signup_session, data)
            
            logger.info("Signup data updated successfully",
                       session_id=session_id,
                       step=step.value)
            
            return True
            
        except Exception as e:
            logger.error("Failed to update signup data",
                        session_id=session_id,
                        step=step.value,
                        error=str(e))
            raise
    
    async def _handle_initial_step(self, signup_session: SignupSession, data: Dict[str, Any]):
        """Handle initial signup step."""
        try:
            # Validate required fields
            required_fields = ["email", "password", "first_name", "last_name"]
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Validate email format
            if "@" not in data["email"]:
                raise ValueError("Invalid email format")
            
            # Validate password strength
            if len(data["password"]) < 8:
                raise ValueError("Password must be at least 8 characters long")
            
            logger.info("Initial step validation passed", session_id=signup_session.session_id)
            
        except Exception as e:
            logger.error("Initial step validation failed", error=str(e))
            raise
    
    async def _handle_email_verification_step(self, signup_session: SignupSession, data: Dict[str, Any]):
        """Handle email verification step."""
        try:
            # This step is handled by verify_email method
            logger.info("Email verification step handled", session_id=signup_session.session_id)
            
        except Exception as e:
            logger.error("Email verification step failed", error=str(e))
            raise
    
    async def _handle_company_info_step(self, signup_session: SignupSession, data: Dict[str, Any]):
        """Handle company info step."""
        try:
            # Validate required fields
            required_fields = ["company_name", "company_size", "industry", "phone_number", "country"]
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Validate phone number format
            phone = data["phone_number"]
            if not phone.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "").isdigit():
                raise ValueError("Invalid phone number format")
            
            # Move to plan selection
            signup_session.current_step = SignupStep.PLAN_SELECTION
            signup_session.updated_at = datetime.now(timezone.utc)
            
            logger.info("Company info step completed", session_id=signup_session.session_id)
            
        except Exception as e:
            logger.error("Company info step failed", error=str(e))
            raise
    
    async def _handle_plan_selection_step(self, signup_session: SignupSession, data: Dict[str, Any]):
        """Handle plan selection step."""
        try:
            # Validate plan selection
            if "plan_type" not in data:
                raise ValueError("Plan type is required")
            
            plan_type = PlanType(data["plan_type"])
            
            if plan_type not in self.available_plans:
                raise ValueError("Invalid plan type")
            
            plan_details = self.available_plans[plan_type]
            
            if not plan_details.available:
                raise ValueError("Selected plan is not available")
            
            # Move to next step based on plan type
            if plan_type == PlanType.FREE:
                # Free plan doesn't require payment
                signup_session.current_step = SignupStep.TERMS_ACCEPTANCE
            else:
                # Paid plans require payment setup
                signup_session.current_step = SignupStep.PAYMENT_SETUP
                signup_session.status = SignupStatus.PENDING_PAYMENT
            
            signup_session.updated_at = datetime.now(timezone.utc)
            
            logger.info("Plan selection completed",
                       session_id=signup_session.session_id,
                       plan_type=plan_type.value)
            
        except Exception as e:
            logger.error("Plan selection step failed", error=str(e))
            raise
    
    async def _handle_payment_setup_step(self, signup_session: SignupSession, data: Dict[str, Any]):
        """Handle payment setup step."""
        try:
            # Validate payment method
            if "payment_method" not in data:
                raise ValueError("Payment method is required")
            
            payment_method = data["payment_method"]
            
            # Validate payment method type
            if "type" not in payment_method:
                raise ValueError("Payment method type is required")
            
            if payment_method["type"] not in ["credit_card", "bank_transfer", "paypal"]:
                raise ValueError("Invalid payment method type")
            
            # Move to billing info
            signup_session.current_step = SignupStep.BILLING_INFO
            signup_session.updated_at = datetime.now(timezone.utc)
            
            logger.info("Payment setup completed", session_id=signup_session.session_id)
            
        except Exception as e:
            logger.error("Payment setup step failed", error=str(e))
            raise
    
    async def _handle_billing_info_step(self, signup_session: SignupSession, data: Dict[str, Any]):
        """Handle billing info step."""
        try:
            # Validate billing information
            if "billing_address" not in data:
                raise ValueError("Billing address is required")
            
            billing_address = data["billing_address"]
            
            # Validate required billing fields
            required_billing_fields = ["street", "city", "state", "postal_code", "country"]
            for field in required_billing_fields:
                if field not in billing_address:
                    raise ValueError(f"Missing required billing field: {field}")
            
            # Move to terms acceptance
            signup_session.current_step = SignupStep.TERMS_ACCEPTANCE
            signup_session.updated_at = datetime.now(timezone.utc)
            
            logger.info("Billing info completed", session_id=signup_session.session_id)
            
        except Exception as e:
            logger.error("Billing info step failed", error=str(e))
            raise
    
    async def _handle_terms_acceptance_step(self, signup_session: SignupSession, data: Dict[str, Any]):
        """Handle terms acceptance step."""
        try:
            # Validate terms acceptance
            if "terms_accepted" not in data:
                raise ValueError("Terms acceptance is required")
            
            if not data["terms_accepted"]:
                raise ValueError("Terms must be accepted to continue")
            
            # Move to account creation
            signup_session.current_step = SignupStep.ACCOUNT_CREATION
            signup_session.updated_at = datetime.now(timezone.utc)
            
            logger.info("Terms acceptance completed", session_id=signup_session.session_id)
            
        except Exception as e:
            logger.error("Terms acceptance step failed", error=str(e))
            raise
    
    async def _handle_account_creation_step(self, signup_session: SignupSession, data: Dict[str, Any]):
        """Handle account creation step."""
        try:
            # Create tenant account
            tenant_id = await self._create_tenant_account(signup_session)
            
            # Move to welcome step
            signup_session.current_step = SignupStep.WELCOME
            signup_session.status = SignupStatus.COMPLETED
            signup_session.updated_at = datetime.now(timezone.utc)
            signup_session.signup_data["tenant_id"] = tenant_id
            
            logger.info("Account creation completed",
                       session_id=signup_session.session_id,
                       tenant_id=tenant_id)
            
        except Exception as e:
            logger.error("Account creation step failed", error=str(e))
            signup_session.status = SignupStatus.FAILED
            signup_session.error_message = str(e)
            raise
    
    async def _create_tenant_account(self, signup_session: SignupSession) -> str:
        """Create tenant account in database."""
        try:
            tenant_id = str(uuid.uuid4())
            
            # Prepare tenant data
            tenant_data = {
                "tenant_id": tenant_id,
                "email": signup_session.email,
                "first_name": signup_session.signup_data["first_name"],
                "last_name": signup_session.signup_data["last_name"],
                "company_name": signup_session.signup_data["company_name"],
                "company_size": signup_session.signup_data["company_size"],
                "industry": signup_session.signup_data["industry"],
                "phone_number": signup_session.signup_data["phone_number"],
                "country": signup_session.signup_data["country"],
                "timezone": signup_session.signup_data.get("timezone", "UTC"),
                "plan_type": signup_session.signup_data["plan_type"],
                "data_region": signup_session.signup_data.get("data_region", "us-east-1"),
                "status": "active",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            
            # Insert tenant record
            query = text("""
                INSERT INTO tenants (
                    tenant_id, email, first_name, last_name, company_name,
                    company_size, industry, phone_number, country, timezone,
                    plan_type, data_region, status, created_at, updated_at
                ) VALUES (
                    :tenant_id, :email, :first_name, :last_name, :company_name,
                    :company_size, :industry, :phone_number, :country, :timezone,
                    :plan_type, :data_region, :status, :created_at, :updated_at
                )
            """)
            
            await self.db_session.execute(query, tenant_data)
            await self.db_session.commit()
            
            logger.info("Tenant account created", tenant_id=tenant_id)
            
            return tenant_id
            
        except Exception as e:
            logger.error("Failed to create tenant account", error=str(e))
            await self.db_session.rollback()
            raise
    
    async def _handle_welcome_step(self, signup_session: SignupSession, data: Dict[str, Any]):
        """Handle welcome step."""
        try:
            # Send welcome email
            await self._send_welcome_email(signup_session)
            
            # Move to completed
            signup_session.current_step = SignupStep.COMPLETED
            signup_session.updated_at = datetime.now(timezone.utc)
            
            logger.info("Welcome step completed", session_id=signup_session.session_id)
            
        except Exception as e:
            logger.error("Welcome step failed", error=str(e))
            raise
    
    async def _send_welcome_email(self, signup_session: SignupSession):
        """Send welcome email."""
        try:
            # In production, this would send actual email
            logger.info("Welcome email sent",
                       session_id=signup_session.session_id,
                       email=signup_session.email)
            
        except Exception as e:
            logger.error("Failed to send welcome email", error=str(e))
            raise
    
    async def get_signup_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get signup status."""
        try:
            if session_id not in self.signup_sessions:
                return None
            
            signup_session = self.signup_sessions[session_id]
            
            return {
                "session_id": session_id,
                "email": signup_session.email,
                "current_step": signup_session.current_step.value,
                "status": signup_session.status.value,
                "created_at": signup_session.created_at.isoformat(),
                "updated_at": signup_session.updated_at.isoformat(),
                "expires_at": signup_session.expires_at.isoformat(),
                "error_message": signup_session.error_message,
                "progress_percentage": self._calculate_progress(signup_session.current_step)
            }
            
        except Exception as e:
            logger.error("Failed to get signup status", error=str(e))
            return None
    
    def _calculate_progress(self, current_step: SignupStep) -> int:
        """Calculate signup progress percentage."""
        step_order = [
            SignupStep.INITIAL,
            SignupStep.EMAIL_VERIFICATION,
            SignupStep.COMPANY_INFO,
            SignupStep.PLAN_SELECTION,
            SignupStep.PAYMENT_SETUP,
            SignupStep.BILLING_INFO,
            SignupStep.TERMS_ACCEPTANCE,
            SignupStep.ACCOUNT_CREATION,
            SignupStep.WELCOME,
            SignupStep.COMPLETED
        ]
        
        try:
            current_index = step_order.index(current_step)
            total_steps = len(step_order)
            return int((current_index / total_steps) * 100)
            
        except ValueError:
            return 0
    
    async def get_available_plans(self) -> List[Dict[str, Any]]:
        """Get available plans."""
        try:
            plans = []
            
            for plan_type, plan_details in self.available_plans.items():
                if plan_details.available:
                    plans.append({
                        "plan_type": plan_type.value,
                        "name": plan_details.name,
                        "description": plan_details.description,
                        "price_monthly": plan_details.price_monthly,
                        "price_yearly": plan_details.price_yearly,
                        "features": plan_details.features,
                        "limits": plan_details.limits,
                        "trial_days": plan_details.trial_days
                    })
            
            return plans
            
        except Exception as e:
            logger.error("Failed to get available plans", error=str(e))
            return []
    
    async def cleanup_expired_sessions(self):
        """Cleanup expired signup sessions."""
        try:
            current_time = datetime.now(timezone.utc)
            expired_sessions = []
            
            for session_id, signup_session in self.signup_sessions.items():
                if signup_session.expires_at < current_time:
                    expired_sessions.append(session_id)
            
            # Remove expired sessions
            for session_id in expired_sessions:
                del self.signup_sessions[session_id]
            
            if expired_sessions:
                logger.info("Cleaned up expired sessions", count=len(expired_sessions))
            
        except Exception as e:
            logger.error("Failed to cleanup expired sessions", error=str(e))
