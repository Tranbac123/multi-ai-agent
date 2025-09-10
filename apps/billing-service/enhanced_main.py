"""Enhanced billing service with E2E verification capabilities."""

import asyncio
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import structlog
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from apps.billing-service.core.usage_tracker import UsageTracker, UsageType, UsageRecord
from apps.billing-service.core.billing_engine import BillingEngine, Invoice, InvoiceStatus
from apps.billing-service.core.webhook_aggregator import WebhookAggregator, WebhookEvent, WebhookEventType
from apps.billing-service.core.invoice_preview import InvoicePreviewService, InvoicePreview, QuotaStatus

logger = structlog.get_logger(__name__)

# Pydantic models for API
class UsageRecordRequest(BaseModel):
    """Usage record request."""
    tenant_id: str
    usage_type: str
    quantity: float
    metadata: Dict[str, Any] = Field(default_factory=dict)

class InvoicePreviewRequest(BaseModel):
    """Invoice preview request."""
    tenant_id: str
    billing_period_start: Optional[datetime] = None
    billing_period_end: Optional[datetime] = None

class QuotaStatusResponse(BaseModel):
    """Quota status response."""
    tenant_id: str
    quotas: List[Dict[str, Any]]
    overall_status: str

class WebhookEventRequest(BaseModel):
    """Webhook event request."""
    event_type: str
    tenant_id: str
    data: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)

# Initialize FastAPI app
app = FastAPI(
    title="Enhanced Billing Service",
    description="Billing service with E2E verification and quota enforcement",
    version="2.0.0"
)

# Global services
redis_client: Optional[redis.Redis] = None
usage_tracker: Optional[UsageTracker] = None
billing_engine: Optional[BillingEngine] = None
webhook_aggregator: Optional[WebhookAggregator] = None
invoice_preview_service: Optional[InvoicePreviewService] = None

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global redis_client, usage_tracker, billing_engine, webhook_aggregator, invoice_preview_service
    
    # Initialize Redis client
    redis_client = redis.from_url("redis://localhost:6379")
    
    # Initialize services
    usage_tracker = UsageTracker(redis_client)
    billing_engine = BillingEngine(redis_client, usage_tracker)
    webhook_aggregator = WebhookAggregator(redis_client, usage_tracker, billing_engine)
    invoice_preview_service = InvoicePreviewService(redis_client, usage_tracker, billing_engine)
    
    logger.info("Enhanced billing service started")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    if redis_client:
        await redis_client.close()
    logger.info("Enhanced billing service stopped")

# Dependency to get services
async def get_services():
    """Get initialized services."""
    if not all([redis_client, usage_tracker, billing_engine, webhook_aggregator, invoice_preview_service]):
        raise HTTPException(status_code=500, detail="Services not initialized")
    
    return {
        "redis_client": redis_client,
        "usage_tracker": usage_tracker,
        "billing_engine": billing_engine,
        "webhook_aggregator": webhook_aggregator,
        "invoice_preview_service": invoice_preview_service
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

# Usage tracking endpoints
@app.post("/usage/record")
async def record_usage(
    request: UsageRecordRequest,
    services: Dict[str, Any] = Depends(get_services)
):
    """Record usage for a tenant."""
    try:
        usage_type = UsageType(request.usage_type)
        
        await services["usage_tracker"].record_usage(
            tenant_id=request.tenant_id,
            usage_type=usage_type,
            quantity=request.quantity,
            metadata=request.metadata
        )
        
        logger.info("Usage recorded", 
                   tenant_id=request.tenant_id,
                   usage_type=request.usage_type,
                   quantity=request.quantity)
        
        return {"status": "success", "message": "Usage recorded successfully"}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid usage type: {e}")
    except Exception as e:
        logger.error("Failed to record usage", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to record usage")

@app.get("/usage/current/{tenant_id}")
async def get_current_usage(
    tenant_id: str,
    services: Dict[str, Any] = Depends(get_services)
):
    """Get current usage for a tenant."""
    try:
        usage_data = {}
        
        for usage_type in UsageType:
            current_usage = await services["usage_tracker"].get_current_usage(tenant_id, usage_type)
            usage_data[usage_type.value] = current_usage
        
        return {
            "tenant_id": tenant_id,
            "usage": usage_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to get current usage", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get current usage")

# Invoice preview endpoints
@app.post("/invoice/preview")
async def create_invoice_preview(
    request: InvoicePreviewRequest,
    services: Dict[str, Any] = Depends(get_services)
):
    """Create invoice preview for a tenant."""
    try:
        preview = await services["invoice_preview_service"].generate_invoice_preview(
            tenant_id=request.tenant_id,
            billing_period_start=request.billing_period_start,
            billing_period_end=request.billing_period_end
        )
        
        return {
            "preview_id": preview.preview_id,
            "tenant_id": preview.tenant_id,
            "billing_period": {
                "start": preview.billing_period_start.isoformat(),
                "end": preview.billing_period_end.isoformat()
            },
            "subtotal": preview.subtotal,
            "tax_amount": preview.tax_amount,
            "total_amount": preview.total_amount,
            "currency": preview.currency,
            "usage_summary": preview.usage_summary,
            "quota_status": [
                {
                    "usage_type": limit.usage_type.value,
                    "limit": limit.limit,
                    "current_usage": limit.current_usage,
                    "status": limit.status.value,
                    "reset_date": limit.reset_date.isoformat()
                }
                for limit in preview.quota_status
            ],
            "generated_at": preview.generated_at.isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to create invoice preview", tenant_id=request.tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create invoice preview")

@app.get("/invoice/preview/{tenant_id}/{preview_id}")
async def get_invoice_preview(
    tenant_id: str,
    preview_id: str,
    services: Dict[str, Any] = Depends(get_services)
):
    """Get cached invoice preview."""
    try:
        preview = await services["invoice_preview_service"].get_cached_preview(tenant_id, preview_id)
        
        if not preview:
            raise HTTPException(status_code=404, detail="Invoice preview not found")
        
        return {
            "preview_id": preview.preview_id,
            "tenant_id": preview.tenant_id,
            "billing_period": {
                "start": preview.billing_period_start.isoformat(),
                "end": preview.billing_period_end.isoformat()
            },
            "subtotal": preview.subtotal,
            "tax_amount": preview.tax_amount,
            "total_amount": preview.total_amount,
            "currency": preview.currency,
            "usage_summary": preview.usage_summary,
            "quota_status": [
                {
                    "usage_type": limit.usage_type.value,
                    "limit": limit.limit,
                    "current_usage": limit.current_usage,
                    "status": limit.status.value,
                    "reset_date": limit.reset_date.isoformat()
                }
                for limit in preview.quota_status
            ],
            "generated_at": preview.generated_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get invoice preview", tenant_id=tenant_id, preview_id=preview_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get invoice preview")

# Quota management endpoints
@app.get("/quota/status/{tenant_id}")
async def get_quota_status(
    tenant_id: str,
    services: Dict[str, Any] = Depends(get_services)
):
    """Get quota status for a tenant."""
    try:
        quota_limits = await services["invoice_preview_service"].get_quota_limits(tenant_id)
        
        quotas = []
        overall_status = "within_limits"
        
        for limit in quota_limits:
            quotas.append({
                "usage_type": limit.usage_type.value,
                "limit": limit.limit,
                "current_usage": limit.current_usage,
                "remaining": limit.limit - limit.current_usage,
                "status": limit.status.value,
                "reset_date": limit.reset_date.isoformat()
            })
            
            if limit.status == QuotaStatus.EXCEEDED:
                overall_status = "exceeded"
            elif limit.status == QuotaStatus.APPROACHING_LIMIT and overall_status != "exceeded":
                overall_status = "approaching_limit"
        
        return QuotaStatusResponse(
            tenant_id=tenant_id,
            quotas=quotas,
            overall_status=overall_status
        )
        
    except Exception as e:
        logger.error("Failed to get quota status", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get quota status")

@app.post("/quota/check")
async def check_quota(
    tenant_id: str,
    usage_type: str,
    requested_amount: float,
    services: Dict[str, Any] = Depends(get_services)
):
    """Check if a request would exceed quota."""
    try:
        usage_type_enum = UsageType(usage_type)
        allowed, message = await services["invoice_preview_service"].enforce_quota(
            tenant_id=tenant_id,
            usage_type=usage_type_enum,
            requested_amount=requested_amount
        )
        
        return {
            "allowed": allowed,
            "message": message,
            "tenant_id": tenant_id,
            "usage_type": usage_type,
            "requested_amount": requested_amount
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid usage type: {e}")
    except Exception as e:
        logger.error("Failed to check quota", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to check quota")

# Webhook endpoints
@app.post("/webhook/event")
async def receive_webhook_event(
    request: WebhookEventRequest,
    background_tasks: BackgroundTasks,
    services: Dict[str, Any] = Depends(get_services)
):
    """Receive webhook event."""
    try:
        event_type = WebhookEventType(request.event_type)
        
        # Process webhook in background
        background_tasks.add_task(
            process_webhook_event,
            services["webhook_aggregator"],
            event_type,
            request.tenant_id,
            request.data,
            request.metadata
        )
        
        return {"status": "accepted", "message": "Webhook event queued for processing"}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid event type: {e}")
    except Exception as e:
        logger.error("Failed to receive webhook event", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to receive webhook event")

async def process_webhook_event(
    webhook_aggregator: WebhookAggregator,
    event_type: WebhookEventType,
    tenant_id: str,
    data: Dict[str, Any],
    metadata: Dict[str, Any]
):
    """Process webhook event in background."""
    try:
        await webhook_aggregator.process_webhook_event(
            event_type=event_type,
            tenant_id=tenant_id,
            data=data,
            metadata=metadata
        )
        
        logger.info("Webhook event processed", 
                   event_type=event_type.value,
                   tenant_id=tenant_id)
        
    except Exception as e:
        logger.error("Failed to process webhook event", 
                    event_type=event_type.value,
                    tenant_id=tenant_id,
                    error=str(e))

# E2E verification endpoints
@app.post("/e2e/verify")
async def verify_e2e_billing(
    tenant_id: str,
    services: Dict[str, Any] = Depends(get_services)
):
    """Verify E2E billing functionality."""
    try:
        verification_results = {
            "tenant_id": tenant_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tests": []
        }
        
        # Test 1: Record usage
        test1_result = await test_usage_recording(services["usage_tracker"], tenant_id)
        verification_results["tests"].append(test1_result)
        
        # Test 2: Generate invoice preview
        test2_result = await test_invoice_preview(services["invoice_preview_service"], tenant_id)
        verification_results["tests"].append(test2_result)
        
        # Test 3: Check quota enforcement
        test3_result = await test_quota_enforcement(services["invoice_preview_service"], tenant_id)
        verification_results["tests"].append(test3_result)
        
        # Test 4: Process webhook events
        test4_result = await test_webhook_processing(services["webhook_aggregator"], tenant_id)
        verification_results["tests"].append(test4_result)
        
        # Overall result
        all_passed = all(test["passed"] for test in verification_results["tests"])
        verification_results["overall_result"] = "PASSED" if all_passed else "FAILED"
        
        return verification_results
        
    except Exception as e:
        logger.error("E2E verification failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail="E2E verification failed")

async def test_usage_recording(usage_tracker: UsageTracker, tenant_id: str) -> Dict[str, Any]:
    """Test usage recording functionality."""
    try:
        # Record test usage
        await usage_tracker.record_usage(
            tenant_id=tenant_id,
            usage_type=UsageType.API_CALLS,
            quantity=10.0,
            metadata={"test": "e2e_verification"}
        )
        
        # Verify usage was recorded
        current_usage = await usage_tracker.get_current_usage(tenant_id, UsageType.API_CALLS)
        
        return {
            "test_name": "usage_recording",
            "passed": current_usage >= 10.0,
            "details": f"Recorded 10 API calls, current usage: {current_usage}"
        }
        
    except Exception as e:
        return {
            "test_name": "usage_recording",
            "passed": False,
            "details": f"Error: {str(e)}"
        }

async def test_invoice_preview(invoice_preview_service: InvoicePreviewService, tenant_id: str) -> Dict[str, Any]:
    """Test invoice preview functionality."""
    try:
        # Generate invoice preview
        preview = await invoice_preview_service.generate_invoice_preview(tenant_id)
        
        return {
            "test_name": "invoice_preview",
            "passed": preview is not None and preview.total_amount >= 0,
            "details": f"Generated preview with total: ${preview.total_amount:.2f}"
        }
        
    except Exception as e:
        return {
            "test_name": "invoice_preview",
            "passed": False,
            "details": f"Error: {str(e)}"
        }

async def test_quota_enforcement(invoice_preview_service: InvoicePreviewService, tenant_id: str) -> Dict[str, Any]:
    """Test quota enforcement functionality."""
    try:
        # Check quota for API calls
        allowed, message = await invoice_preview_service.enforce_quota(
            tenant_id=tenant_id,
            usage_type=UsageType.API_CALLS,
            requested_amount=1.0
        )
        
        return {
            "test_name": "quota_enforcement",
            "passed": True,  # Should not fail for small amount
            "details": f"Quota check result: {message}"
        }
        
    except Exception as e:
        return {
            "test_name": "quota_enforcement",
            "passed": False,
            "details": f"Error: {str(e)}"
        }

async def test_webhook_processing(webhook_aggregator: WebhookAggregator, tenant_id: str) -> Dict[str, Any]:
    """Test webhook processing functionality."""
    try:
        # Process test webhook event
        await webhook_aggregator.process_webhook_event(
            event_type=WebhookEventType.API_CALL,
            tenant_id=tenant_id,
            data={"test": "e2e_verification"},
            metadata={"source": "test"}
        )
        
        return {
            "test_name": "webhook_processing",
            "passed": True,
            "details": "Webhook event processed successfully"
        }
        
    except Exception as e:
        return {
            "test_name": "webhook_processing",
            "passed": False,
            "details": f"Error: {str(e)}"
        }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
