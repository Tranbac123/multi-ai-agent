"""Payment processor for billing service."""

import asyncio
import time
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import structlog
import redis.asyncio as redis

logger = structlog.get_logger(__name__)


class PaymentStatus(Enum):
    """Payment status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentMethodType(Enum):
    """Payment method types."""

    CREDIT_CARD = "credit_card"
    BANK_ACCOUNT = "bank_account"
    PAYPAL = "paypal"
    STRIPE = "stripe"
    BRAINTREE = "braintree"


@dataclass
class PaymentMethod:
    """Payment method."""

    method_id: str
    tenant_id: str
    method_type: PaymentMethodType
    provider: str
    provider_id: str
    is_default: bool = False
    metadata: Dict[str, Any] = None


@dataclass
class Payment:
    """Payment record."""

    payment_id: str
    tenant_id: str
    invoice_id: str
    amount: float
    currency: str
    method: PaymentMethod
    status: PaymentStatus
    provider_transaction_id: str = None
    created_at: float = None
    processed_at: float = None
    metadata: Dict[str, Any] = None


class PaymentProcessor:
    """Payment processor for billing service."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.providers = {}
        self.webhook_handlers = {}

    async def create_payment_method(
        self,
        tenant_id: str,
        method_type: PaymentMethodType,
        provider: str,
        provider_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create payment method for tenant."""
        try:
            method_id = f"pm_{int(time.time())}_{tenant_id}"

            payment_method = PaymentMethod(
                method_id=method_id,
                tenant_id=tenant_id,
                method_type=method_type,
                provider=provider,
                provider_id=provider_id,
                metadata=metadata or {},
            )

            # Store payment method
            await self._store_payment_method(payment_method)

            logger.info(
                "Payment method created",
                method_id=method_id,
                tenant_id=tenant_id,
                method_type=method_type.value,
            )

            return method_id

        except Exception as e:
            logger.error("Failed to create payment method", error=str(e))
            raise

    async def process_payment(
        self,
        tenant_id: str,
        invoice_id: str,
        amount: float,
        method_id: str,
        currency: str = "USD",
    ) -> str:
        """Process payment for invoice."""
        try:
            payment_id = f"pay_{int(time.time())}_{tenant_id}"

            # Get payment method
            payment_method = await self._get_payment_method(method_id)
            if not payment_method:
                raise ValueError(f"Payment method {method_id} not found")

            # Create payment record
            payment = Payment(
                payment_id=payment_id,
                tenant_id=tenant_id,
                invoice_id=invoice_id,
                amount=amount,
                currency=currency,
                method=payment_method,
                status=PaymentStatus.PENDING,
                created_at=time.time(),
            )

            # Store payment
            await self._store_payment(payment)

            # Process payment with provider
            success = await self._process_with_provider(payment)

            if success:
                payment.status = PaymentStatus.COMPLETED
                payment.processed_at = time.time()
            else:
                payment.status = PaymentStatus.FAILED

            # Update payment record
            await self._store_payment(payment)

            logger.info(
                "Payment processed",
                payment_id=payment_id,
                tenant_id=tenant_id,
                invoice_id=invoice_id,
                amount=amount,
                status=payment.status.value,
            )

            return payment_id

        except Exception as e:
            logger.error("Failed to process payment", error=str(e))
            raise

    async def get_payment_methods(self, tenant_id: str) -> List[PaymentMethod]:
        """Get payment methods for tenant."""
        try:
            pattern = f"payment_method:{tenant_id}:*"
            keys = await self.redis.keys(pattern)

            methods = []
            for key in keys:
                try:
                    method_data = await self.redis.hgetall(key)
                    if method_data:
                        method = PaymentMethod(
                            method_id=method_data["method_id"],
                            tenant_id=method_data["tenant_id"],
                            method_type=PaymentMethodType(method_data["method_type"]),
                            provider=method_data["provider"],
                            provider_id=method_data["provider_id"],
                            is_default=method_data.get("is_default", "false") == "true",
                            metadata=json.loads(method_data.get("metadata", "{}")),
                        )
                        methods.append(method)
                except Exception as e:
                    logger.error(
                        "Failed to parse payment method", error=str(e), key=key
                    )

            return methods

        except Exception as e:
            logger.error("Failed to get payment methods", error=str(e))
            return []

    async def get_payment_history(
        self, tenant_id: str, limit: int = 100
    ) -> List[Payment]:
        """Get payment history for tenant."""
        try:
            pattern = f"payment:{tenant_id}:*"
            keys = await self.redis.keys(pattern)

            payments = []
            for key in keys:
                try:
                    payment_data = await self.redis.hgetall(key)
                    if payment_data:
                        payment = Payment(
                            payment_id=payment_data["payment_id"],
                            tenant_id=payment_data["tenant_id"],
                            invoice_id=payment_data["invoice_id"],
                            amount=float(payment_data["amount"]),
                            currency=payment_data["currency"],
                            method=await self._get_payment_method(
                                payment_data["method_id"]
                            ),
                            status=PaymentStatus(payment_data["status"]),
                            provider_transaction_id=payment_data.get(
                                "provider_transaction_id"
                            ),
                            created_at=float(payment_data["created_at"]),
                            processed_at=float(payment_data["processed_at"])
                            if payment_data.get("processed_at")
                            else None,
                            metadata=json.loads(payment_data.get("metadata", "{}")),
                        )
                        payments.append(payment)
                except Exception as e:
                    logger.error("Failed to parse payment", error=str(e), key=key)

            # Sort by creation date (newest first)
            payments.sort(key=lambda x: x.created_at, reverse=True)

            return payments[:limit]

        except Exception as e:
            logger.error("Failed to get payment history", error=str(e))
            return []

    async def handle_stripe_webhook(
        self, payload: bytes, signature: str
    ) -> Dict[str, Any]:
        """Handle Stripe webhook events."""
        try:
            # In a real implementation, you would verify the signature
            # and parse the payload using Stripe's webhook library

            event_data = json.loads(payload)
            event_type = event_data.get("type")

            if event_type == "payment_intent.succeeded":
                await self._handle_stripe_payment_success(event_data)
            elif event_type == "payment_intent.payment_failed":
                await self._handle_stripe_payment_failure(event_data)
            elif event_type == "customer.subscription.updated":
                await self._handle_stripe_subscription_update(event_data)

            logger.info("Stripe webhook processed", event_type=event_type)
            return event_data

        except Exception as e:
            logger.error("Failed to handle Stripe webhook", error=str(e))
            raise

    async def handle_braintree_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Braintree webhook events."""
        try:
            event_type = payload.get("kind")

            if event_type == "subscription_charged_successfully":
                await self._handle_braintree_payment_success(payload)
            elif event_type == "subscription_charged_unsuccessfully":
                await self._handle_braintree_payment_failure(payload)
            elif event_type == "subscription_canceled":
                await self._handle_braintree_subscription_canceled(payload)

            logger.info("Braintree webhook processed", event_type=event_type)
            return payload

        except Exception as e:
            logger.error("Failed to handle Braintree webhook", error=str(e))
            raise

    async def _process_with_provider(self, payment: Payment) -> bool:
        """Process payment with provider."""
        try:
            # Mock payment processing
            # In a real implementation, you would call the actual payment provider API

            await asyncio.sleep(0.1)  # Simulate API call

            # Simulate success/failure based on amount
            success = payment.amount > 0 and payment.amount < 10000

            if success:
                payment.provider_transaction_id = f"txn_{int(time.time())}"

            return success

        except Exception as e:
            logger.error("Failed to process with provider", error=str(e))
            return False

    async def _handle_stripe_payment_success(self, event_data: Dict[str, Any]) -> None:
        """Handle Stripe payment success event."""
        try:
            payment_intent = event_data.get("data", {}).get("object", {})
            amount = payment_intent.get("amount", 0) / 100  # Convert from cents
            currency = payment_intent.get("currency", "usd")

            # Update payment status
            # In a real implementation, you would update the payment record

            logger.info("Stripe payment succeeded", amount=amount, currency=currency)

        except Exception as e:
            logger.error("Failed to handle Stripe payment success", error=str(e))

    async def _handle_stripe_payment_failure(self, event_data: Dict[str, Any]) -> None:
        """Handle Stripe payment failure event."""
        try:
            payment_intent = event_data.get("data", {}).get("object", {})
            failure_code = payment_intent.get("last_payment_error", {}).get("code")

            # Update payment status
            # In a real implementation, you would update the payment record

            logger.warning("Stripe payment failed", failure_code=failure_code)

        except Exception as e:
            logger.error("Failed to handle Stripe payment failure", error=str(e))

    async def _handle_stripe_subscription_update(
        self, event_data: Dict[str, Any]
    ) -> None:
        """Handle Stripe subscription update event."""
        try:
            subscription = event_data.get("data", {}).get("object", {})
            status = subscription.get("status")

            # Update subscription status
            # In a real implementation, you would update the subscription record

            logger.info("Stripe subscription updated", status=status)

        except Exception as e:
            logger.error("Failed to handle Stripe subscription update", error=str(e))

    async def _handle_braintree_payment_success(
        self, event_data: Dict[str, Any]
    ) -> None:
        """Handle Braintree payment success event."""
        try:
            subscription = event_data.get("subscription", {})
            amount = subscription.get("price", 0)

            # Update payment status
            # In a real implementation, you would update the payment record

            logger.info("Braintree payment succeeded", amount=amount)

        except Exception as e:
            logger.error("Failed to handle Braintree payment success", error=str(e))

    async def _handle_braintree_payment_failure(
        self, event_data: Dict[str, Any]
    ) -> None:
        """Handle Braintree payment failure event."""
        try:
            subscription = event_data.get("subscription", {})
            failure_reason = subscription.get("failure_reason")

            # Update payment status
            # In a real implementation, you would update the payment record

            logger.warning("Braintree payment failed", failure_reason=failure_reason)

        except Exception as e:
            logger.error("Failed to handle Braintree payment failure", error=str(e))

    async def _handle_braintree_subscription_canceled(
        self, event_data: Dict[str, Any]
    ) -> None:
        """Handle Braintree subscription canceled event."""
        try:
            subscription = event_data.get("subscription", {})
            status = subscription.get("status")

            # Update subscription status
            # In a real implementation, you would update the subscription record

            logger.info("Braintree subscription canceled", status=status)

        except Exception as e:
            logger.error(
                "Failed to handle Braintree subscription canceled", error=str(e)
            )

    async def _store_payment_method(self, payment_method: PaymentMethod) -> None:
        """Store payment method in Redis."""
        try:
            method_key = (
                f"payment_method:{payment_method.tenant_id}:{payment_method.method_id}"
            )

            method_data = {
                "method_id": payment_method.method_id,
                "tenant_id": payment_method.tenant_id,
                "method_type": payment_method.method_type.value,
                "provider": payment_method.provider,
                "provider_id": payment_method.provider_id,
                "is_default": str(payment_method.is_default).lower(),
                "metadata": json.dumps(payment_method.metadata or {}),
            }

            await self.redis.hset(method_key, mapping=method_data)
            await self.redis.expire(method_key, 86400 * 365 * 2)  # 2 years TTL

        except Exception as e:
            logger.error("Failed to store payment method", error=str(e))

    async def _get_payment_method(self, method_id: str) -> Optional[PaymentMethod]:
        """Get payment method by ID."""
        try:
            pattern = f"payment_method:*:{method_id}"
            keys = await self.redis.keys(pattern)

            if not keys:
                return None

            method_key = keys[0].decode()
            method_data = await self.redis.hgetall(method_key)

            if not method_data:
                return None

            return PaymentMethod(
                method_id=method_data["method_id"],
                tenant_id=method_data["tenant_id"],
                method_type=PaymentMethodType(method_data["method_type"]),
                provider=method_data["provider"],
                provider_id=method_data["provider_id"],
                is_default=method_data.get("is_default", "false") == "true",
                metadata=json.loads(method_data.get("metadata", "{}")),
            )

        except Exception as e:
            logger.error("Failed to get payment method", error=str(e))
            return None

    async def _store_payment(self, payment: Payment) -> None:
        """Store payment in Redis."""
        try:
            payment_key = f"payment:{payment.tenant_id}:{payment.payment_id}"

            payment_data = {
                "payment_id": payment.payment_id,
                "tenant_id": payment.tenant_id,
                "invoice_id": payment.invoice_id,
                "amount": payment.amount,
                "currency": payment.currency,
                "method_id": payment.method.method_id,
                "status": payment.status.value,
                "provider_transaction_id": payment.provider_transaction_id or "",
                "created_at": payment.created_at,
                "processed_at": payment.processed_at or 0,
                "metadata": json.dumps(payment.metadata or {}),
            }

            await self.redis.hset(payment_key, mapping=payment_data)
            await self.redis.expire(payment_key, 86400 * 365 * 2)  # 2 years TTL

        except Exception as e:
            logger.error("Failed to store payment", error=str(e))
