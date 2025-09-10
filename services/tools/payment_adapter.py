"""Payment adapter with saga compensation."""

import asyncio
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import structlog
import redis.asyncio as redis

from services.tools.base_adapter import BaseAdapter, AdapterConfig
from services.tools.saga_adapter import SagaAdapter, SagaStep

logger = structlog.get_logger(__name__)


class PaymentStatus(Enum):
    """Payment status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


@dataclass
class PaymentRequest:
    """Payment request."""
    amount: float
    currency: str = "USD"
    payment_method: str = "card"
    customer_id: str = ""
    order_id: str = ""
    description: str = ""
    metadata: Dict[str, Any] = None


@dataclass
class PaymentResult:
    """Payment result."""
    payment_id: str
    status: PaymentStatus
    amount: float
    currency: str
    processed_at: float
    transaction_id: Optional[str] = None
    error: Optional[str] = None


class PaymentAdapter:
    """Payment adapter with saga compensation."""
    
    def __init__(
        self,
        name: str,
        config: AdapterConfig,
        redis_client: redis.Redis
    ):
        self.name = name
        self.config = config
        self.redis = redis_client
        self.base_adapter = BaseAdapter(name, config, redis_client)
        self.saga_adapter = SagaAdapter(name, config, redis_client)
    
    async def process_payment(
        self,
        request: PaymentRequest,
        tenant_id: str,
        user_id: str
    ) -> PaymentResult:
        """Process payment using base adapter."""
        try:
            # Generate payment ID
            payment_id = f"payment_{int(time.time())}_{hash(request.customer_id)}"
            
            # Mock payment processing
            result = await self.base_adapter.call(
                self._process_payment_operation,
                request,
                payment_id
            )
            
            return result
            
        except Exception as e:
            logger.error("Failed to process payment", error=str(e), amount=request.amount, customer_id=request.customer_id)
            raise
    
    async def process_payment_with_saga(
        self,
        request: PaymentRequest,
        tenant_id: str,
        user_id: str
    ) -> PaymentResult:
        """Process payment using saga pattern."""
        try:
            # Generate saga ID
            saga_id = f"payment_saga_{int(time.time())}_{hash(request.customer_id)}"
            
            # Create saga steps
            steps = [
                SagaStep(
                    step_id="process_payment",
                    operation=self._process_payment_operation,
                    compensate=self._compensate_payment_operation,
                    args=(request,),
                    kwargs={}
                )
            ]
            
            # Execute saga
            context = await self.saga_adapter.execute_saga(
                saga_id=saga_id,
                steps=steps,
                tenant_id=tenant_id,
                user_id=user_id
            )
            
            # Get result from first step
            if context.steps and context.steps[0].result:
                return context.steps[0].result
            
            # If saga failed, raise exception
            if context.status.value in ['failed', 'compensated']:
                error_msg = context.steps[0].error if context.steps else "Unknown error"
                raise Exception(f"Payment saga failed: {error_msg}")
            
            raise Exception("Payment saga completed but no result found")
            
        except Exception as e:
            logger.error("Failed to process payment with saga", error=str(e), amount=request.amount, customer_id=request.customer_id)
            raise
    
    async def _process_payment_operation(
        self,
        request: PaymentRequest,
        payment_id: Optional[str] = None
    ) -> PaymentResult:
        """Process payment operation (mock implementation)."""
        try:
            if not payment_id:
                payment_id = f"payment_{int(time.time())}_{hash(request.customer_id)}"
            
            # Mock payment processing delay
            await asyncio.sleep(0.2)
            
            # Mock payment service response
            result = PaymentResult(
                payment_id=payment_id,
                status=PaymentStatus.COMPLETED,
                amount=request.amount,
                currency=request.currency,
                processed_at=time.time(),
                transaction_id=f"txn_{int(time.time())}_{hash(payment_id)}"
            )
            
            logger.info("Payment processed successfully", payment_id=payment_id, amount=request.amount, customer_id=request.customer_id)
            return result
            
        except Exception as e:
            logger.error("Payment processing failed", error=str(e), amount=request.amount, customer_id=request.customer_id)
            raise
    
    async def _compensate_payment_operation(
        self,
        result: PaymentResult,
        request: PaymentRequest
    ) -> None:
        """Compensate payment operation (mock implementation)."""
        try:
            # Mock payment compensation (e.g., refund, void transaction)
            logger.info("Compensating payment operation", payment_id=result.payment_id, amount=result.amount)
            
            # Mock compensation delay
            await asyncio.sleep(0.1)
            
            # In a real implementation, this might:
            # - Refund the payment
            # - Void the transaction
            # - Update payment status
            # - Send notification to customer
            # - Log for manual review
            
            logger.info("Payment operation compensated", payment_id=result.payment_id)
            
        except Exception as e:
            logger.error("Payment compensation failed", error=str(e), payment_id=result.payment_id)
            raise
    
    async def get_payment_metrics(self) -> Dict[str, Any]:
        """Get payment adapter metrics."""
        try:
            # Get base adapter metrics
            base_metrics = await self.base_adapter.get_metrics()
            
            # Get saga metrics
            saga_metrics = await self.saga_adapter.get_saga_metrics()
            
            return {
                'adapter_name': self.name,
                'base_metrics': base_metrics,
                'saga_metrics': saga_metrics
            }
            
        except Exception as e:
            logger.error("Failed to get payment metrics", error=str(e))
            return {'error': str(e)}
