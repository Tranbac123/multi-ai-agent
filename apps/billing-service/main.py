"""Billing service for usage tracking and payment processing."""

import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from uuid import UUID, uuid4

import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
from opentelemetry import trace

from libs.contracts.billing import (
    UsageCounter,
    BillingPlan,
    Invoice,
    PaymentMethod,
    UsageReport,
    BillingEvent,
    MeteredUsage,
)
from .core.billing_engine import BillingEngine
from .core.usage_tracker import UsageTracker
from .core.payment_processor import PaymentProcessor
from .core.webhook_aggregator import WebhookAggregator

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Billing Service")

    # Initialize Redis client
    import redis.asyncio as redis

    redis_client = redis.Redis(host="localhost", port=6379, db=0)

    # Initialize billing engine
    app.state.usage_tracker = UsageTracker(redis_client)
    app.state.billing_engine = BillingEngine(redis_client, app.state.usage_tracker)
    app.state.payment_processor = PaymentProcessor(redis_client)
    app.state.webhook_aggregator = WebhookAggregator(
        redis_client, app.state.usage_tracker, app.state.billing_engine
    )

    yield

    # Shutdown
    logger.info("Shutting down Billing Service")


def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="Billing Service",
        version="2.0.0",
        description="Multi-tenant billing and usage tracking service",
        lifespan=lifespan,
    )

    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
        request_id = str(uuid4())

        # Add request ID to state
        request.state.request_id = request_id

        response = await call_next(request)

        process_time = time.time() - start_time
        logger.info(
            "Request processed",
            request_id=request_id,
            method=request.method,
            url=str(request.url),
            status_code=response.status_code,
            process_time=process_time,
        )

        return response

    return app


app = create_app()


# API Routes
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "billing-service"}


@app.get("/api/v1/usage/{tenant_id}")
async def get_usage(
    tenant_id: UUID,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    """Get usage statistics for tenant."""
    try:
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()

        usage = await app.state.usage_tracker.get_all_usage_summary(str(tenant_id))

        return {"status": "success", "data": usage}

    except Exception as e:
        logger.error("Failed to get usage", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get usage")


@app.post("/api/v1/usage/meter")
async def meter_usage(usage: MeteredUsage):
    """Record metered usage."""
    try:
        from .core.usage_tracker import UsageType

        # Convert usage type
        usage_type_map = {
            "tokens": UsageType.TOKENS_IN,
            "tool_calls": UsageType.TOOL_CALLS,
            "ws_minutes": UsageType.WS_MINUTES,
            "storage": UsageType.STORAGE_MB,
            "api_calls": UsageType.API_CALLS,
        }

        usage_type = usage_type_map.get(usage.usage_type, UsageType.API_CALLS)

        success = await app.state.usage_tracker.record_usage(
            tenant_id=str(usage.tenant_id),
            usage_type=usage_type,
            quantity=float(usage.amount),
            metadata=usage.metadata,
        )

        if success:
            return {"status": "success", "data": {"status": "recorded"}}
        else:
            raise HTTPException(status_code=500, detail="Failed to record usage")

    except Exception as e:
        logger.error("Failed to meter usage", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to meter usage")


@app.get("/api/v1/plans")
async def get_plans():
    """Get available billing plans."""
    try:
        # Mock billing plans
        plans = [
            {
                "plan_id": "basic",
                "name": "Basic Plan",
                "description": "Basic usage plan",
                "price_usd": 29.99,
                "usage_limits": {
                    "tokens": 100000,
                    "tool_calls": 1000,
                    "ws_minutes": 1000,
                },
                "features": ["Basic support", "Standard SLA"],
            },
            {
                "plan_id": "pro",
                "name": "Pro Plan",
                "description": "Professional usage plan",
                "price_usd": 99.99,
                "usage_limits": {
                    "tokens": 500000,
                    "tool_calls": 5000,
                    "ws_minutes": 5000,
                },
                "features": ["Priority support", "Enhanced SLA", "Advanced analytics"],
            },
        ]
        return {"status": "success", "data": plans}

    except Exception as e:
        logger.error("Failed to get plans", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get plans")


@app.get("/api/v1/invoices/{tenant_id}")
async def get_invoices(tenant_id: UUID, limit: int = 10, offset: int = 0):
    """Get invoices for tenant."""
    try:
        invoices = await app.state.billing_engine.get_tenant_invoices(
            str(tenant_id), limit=limit
        )
        return {"status": "success", "data": invoices}

    except Exception as e:
        logger.error("Failed to get invoices", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get invoices")


@app.post("/api/v1/invoices/{tenant_id}/preview")
async def preview_invoice(tenant_id: UUID, start_date: datetime, end_date: datetime):
    """Preview invoice for tenant."""
    try:
        preview = await app.state.webhook_aggregator.generate_invoice_preview(
            str(tenant_id), start_date.timestamp(), end_date.timestamp()
        )
        return {"status": "success", "data": preview}

    except Exception as e:
        logger.error("Failed to preview invoice", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to preview invoice")


@app.post("/api/v1/payment-methods")
async def create_payment_method(payment_method: PaymentMethod, tenant_id: UUID):
    """Create payment method for tenant."""
    try:
        from .core.payment_processor import PaymentMethodType

        method_type_map = {
            "credit_card": PaymentMethodType.CREDIT_CARD,
            "bank_account": PaymentMethodType.BANK_ACCOUNT,
            "paypal": PaymentMethodType.PAYPAL,
        }

        method_type = method_type_map.get(
            payment_method.method_type, PaymentMethodType.CREDIT_CARD
        )

        result = await app.state.payment_processor.create_payment_method(
            str(tenant_id),
            method_type,
            payment_method.provider,
            payment_method.provider_id,
            payment_method.metadata,
        )
        return {"status": "success", "data": {"method_id": result}}

    except Exception as e:
        logger.error("Failed to create payment method", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create payment method")


@app.post("/api/v1/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    try:
        payload = await request.body()
        signature = request.headers.get("stripe-signature")

        event = await app.state.payment_processor.handle_stripe_webhook(
            payload, signature
        )

        logger.info("Stripe webhook processed", event_type=event.get("type"))
        return {"status": "success"}

    except Exception as e:
        logger.error("Failed to process Stripe webhook", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid webhook")


@app.post("/api/v1/webhooks/braintree")
async def braintree_webhook(request: Request):
    """Handle Braintree webhook events."""
    try:
        payload = await request.json()

        event = await app.state.payment_processor.handle_braintree_webhook(payload)

        logger.info("Braintree webhook processed", event_type=event.get("kind"))
        return {"status": "success"}

    except Exception as e:
        logger.error("Failed to process Braintree webhook", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid webhook")


@app.post("/api/v1/daily-rollup")
async def daily_rollup():
    """Run daily usage rollup job."""
    try:
        # Mock daily rollup
        result = {"status": "completed", "processed_tenants": 0}
        return {"status": "success", "data": result}

    except Exception as e:
        logger.error("Failed to run daily rollup", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to run daily rollup")


if __name__ == "__main__":
    uvicorn.run("apps.billing_service.main:app", host="0.0.0.0", port=8006, reload=True)
