"""Payment adapter with Saga compensation support."""

import asyncio
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import structlog
import redis.asyncio as redis

from .base_adapter import BaseAdapter, AdapterConfig

logger = structlog.get_logger(__name__)


class PaymentStatus(Enum):
    """Payment status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


@dataclass
class PaymentRequest:
    """Payment request structure."""
    amount: float
    currency: str
    customer_id: str
    payment_method_id: str
    description: str
    metadata: Dict[str, Any] = None


@dataclass
class PaymentResult:
    """Payment operation result."""
    payment_id: str
    status: PaymentStatus
    amount: float
    currency: str
    customer_id: str
    processed_at: float
    transaction_id: Optional[str] = None
    error_message: Optional[str] = None


class PaymentAdapter(BaseAdapter):
    """Payment adapter with reliability patterns and Saga compensation."""
    
    def __init__(self, redis_client: redis.Redis, payment_config: Dict[str, Any]):
        config = AdapterConfig(
            timeout_ms=45000,  # Longer timeout for payment processing
            max_retries=2,     # Fewer retries for payments
            retry_delay_ms=2000,
            circuit_breaker_threshold=3,  # Lower threshold for payments
            circuit_breaker_timeout_ms=120000,  # 2 minutes
            bulkhead_max_concurrent=5,  # Lower concurrency for payments
            idempotency_ttl_seconds=7200,  # 2 hours for payments
            saga_compensation_enabled=True,
            saga_compensation_timeout_ms=120000
        )
        
        super().__init__("payment_adapter", config, redis_client)
        self.payment_config = payment_config
        self.processed_payments: Dict[str, PaymentResult] = {}  # For compensation tracking
    
    async def process_payment(self, request: PaymentRequest) -> PaymentResult:
        """Process payment with reliability patterns."""
        async def _payment_operation():
            # Validate payment request
            if request.amount <= 0:
                payment_id = f"pay_{int(time.time() * 1000)}"
                return PaymentResult(
                    payment_id=payment_id,
                    status=PaymentStatus.FAILED,
                    amount=request.amount,
                    currency=request.currency,
                    customer_id=request.customer_id,
                    processed_at=time.time(),
                    error_message="Invalid amount: must be greater than 0"
                )
            
            # Simulate payment processing
            await asyncio.sleep(0.2)  # Simulate payment gateway delay
            
            # In production, this would integrate with payment gateways like Stripe, PayPal, etc.
            payment_id = f"pay_{int(time.time() * 1000)}"
            transaction_id = f"txn_{int(time.time() * 1000)}"
            
            # Simulate payment success/failure
            success_rate = 0.95  # 95% success rate
            import random
            is_successful = random.random() < success_rate
            
            if is_successful:
                result = PaymentResult(
                    payment_id=payment_id,
                    status=PaymentStatus.COMPLETED,
                    amount=request.amount,
                    currency=request.currency,
                    customer_id=request.customer_id,
                    processed_at=time.time(),
                    transaction_id=transaction_id
                )
                
                # Store for potential compensation
                self.processed_payments[payment_id] = result
                
                logger.info("Payment processed successfully", payment_id=payment_id, amount=request.amount, currency=request.currency)
            else:
                result = PaymentResult(
                    payment_id=payment_id,
                    status=PaymentStatus.FAILED,
                    amount=request.amount,
                    currency=request.currency,
                    customer_id=request.customer_id,
                    processed_at=time.time(),
                    error_message="Payment gateway error"
                )
                
                logger.warning("Payment failed", payment_id=payment_id, amount=request.amount, error=result.error_message)
            
            return result
        
        return await self.call(_payment_operation)
    
    async def refund_payment(self, payment_id: str, amount: Optional[float] = None) -> PaymentResult:
        """Refund payment with reliability patterns."""
        async def _refund_operation():
            # Simulate refund processing
            await asyncio.sleep(0.15)  # Simulate refund processing delay
            
            # In production, this would call payment gateway refund API
            refund_id = f"refund_{int(time.time() * 1000)}"
            
            # Find original payment
            original_payment = None
            for payment in self.processed_payments.values():
                if payment.payment_id == payment_id:
                    original_payment = payment
                    break
            
            if not original_payment:
                raise ValueError(f"Payment {payment_id} not found for refund")
            
            refund_amount = amount or original_payment.amount
            
            result = PaymentResult(
                payment_id=refund_id,
                status=PaymentStatus.REFUNDED,
                amount=refund_amount,
                currency=original_payment.currency,
                customer_id=original_payment.customer_id,
                processed_at=time.time(),
                transaction_id=f"refund_txn_{int(time.time() * 1000)}"
            )
            
            logger.info("Payment refunded", payment_id=payment_id, refund_id=refund_id, amount=refund_amount)
            return result
        
        return await self.call(_refund_operation)
    
    async def compensate_payment(self, payment_id: str) -> bool:
        """Compensate for processed payment (refund)."""
        async def _compensation_operation():
            if payment_id in self.processed_payments:
                payment = self.processed_payments[payment_id]
                
                if payment.status == PaymentStatus.COMPLETED:
                    # Refund the payment
                    refund_result = await self.refund_payment(payment_id)
                    
                    # Update original payment status
                    payment.status = PaymentStatus.REFUNDED
                    
                    logger.info("Payment compensation executed (refunded)", payment_id=payment_id, refund_id=refund_result.payment_id)
                    return True
                else:
                    logger.warning("Payment not completed, no compensation needed", payment_id=payment_id, status=payment.status.value)
                    return True
            else:
                logger.warning("Payment not found for compensation", payment_id=payment_id)
                return False
        
        return await self.compensate(_compensation_operation)
    
    async def get_payment_status(self, payment_id: str) -> Optional[PaymentResult]:
        """Get payment status."""
        return self.processed_payments.get(payment_id)
    
    async def get_processed_payments(self) -> List[PaymentResult]:
        """Get list of processed payments for compensation tracking."""
        return list(self.processed_payments.values())
    
    async def get_payment_metrics(self) -> Dict[str, Any]:
        """Get payment adapter metrics."""
        base_metrics = await self.get_metrics()
        
        # Calculate payment-specific metrics
        total_amount = sum(p.amount for p in self.processed_payments.values() if p.status == PaymentStatus.COMPLETED)
        successful_payments = len([p for p in self.processed_payments.values() if p.status == PaymentStatus.COMPLETED])
        failed_payments = len([p for p in self.processed_payments.values() if p.status == PaymentStatus.FAILED])
        refunded_payments = len([p for p in self.processed_payments.values() if p.status == PaymentStatus.REFUNDED])
        
        return {
            **base_metrics,
            "processed_payments_count": len(self.processed_payments),
            "successful_payments": successful_payments,
            "failed_payments": failed_payments,
            "refunded_payments": refunded_payments,
            "total_amount_processed": total_amount,
            "payment_gateway": self.payment_config.get("gateway", "unknown")
        }