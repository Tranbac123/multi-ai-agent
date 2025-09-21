"""Router service v2 with calibrated bandit policy, early exit, and canary support."""

import asyncio
import time
from typing import Dict, Any
import structlog
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from apps.router_service.core.router_v2 import RouterV2, RouterDecision
from apps.router_service.core.feature_extractor import Tier

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
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Pydantic models
class RouteRequest(BaseModel):
    """Request model for routing."""
    message: str = Field(..., description="User message to route")
    user_id: str = Field(..., description="User ID")
    tenant_id: str = Field(..., description="Tenant ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class RouteResponse(BaseModel):
    """Response model for routing."""
    tier: str = Field(..., description="Selected tier (A, B, or C)")
    confidence: float = Field(..., description="Confidence score (0.0 to 1.0)")
    decision_time_ms: float = Field(..., description="Decision time in milliseconds")
    features: Dict[str, Any] = Field(..., description="Extracted features")
    escalation_info: Dict[str, Any] = Field(default_factory=dict, description="Escalation information")
    canary_info: Dict[str, Any] = Field(default_factory=dict, description="Canary information")
    bandit_info: Dict[str, Any] = Field(default_factory=dict, description="Bandit information")


class OutcomeRequest(BaseModel):
    """Request model for recording outcomes."""
    user_id: str = Field(..., description="User ID")
    tenant_id: str = Field(..., description="Tenant ID")
    tier: str = Field(..., description="Tier used")
    success: bool = Field(..., description="Whether the request was successful")
    latency_ms: float = Field(..., description="Request latency in milliseconds")
    quality_score: float = Field(default=0.0, description="Quality score (0.0 to 1.0)")


class StatisticsResponse(BaseModel):
    """Response model for statistics."""
    tenant_id: str = Field(..., description="Tenant ID")
    bandit_statistics: Dict[str, Any] = Field(..., description="Bandit statistics")
    canary_status: Dict[str, Any] = Field(..., description="Canary status")
    escalation_statistics: Dict[str, Any] = Field(..., description="Escalation statistics")
    recent_metrics: Dict[str, Any] = Field(..., description="Recent metrics")


# Global router instance
router_v2: RouterV2 = None
redis_client: redis.Redis = None

# FastAPI app
app = FastAPI(
    title="Router Service v2",
    description="Intelligent router with calibrated bandit policy, early exit, and canary support",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_router() -> RouterV2:
    """Get router instance."""
    if router_v2 is None:
        raise HTTPException(status_code=503, detail="Router not initialized")
    return router_v2


async def get_redis() -> redis.Redis:
    """Get Redis client."""
    if redis_client is None:
        raise HTTPException(status_code=503, detail="Redis not initialized")
    return redis_client


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global router_v2, redis_client
    
    try:
        # Initialize Redis client
        redis_client = redis.Redis(
            host="localhost",
            port=6379,
            db=0,
            decode_responses=False,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )
        
        # Test Redis connection
        await redis_client.ping()
        logger.info("Redis connection established")
        
        # Initialize router v2
        router_v2 = RouterV2(redis_client)
        logger.info("Router v2 initialized")
        
    except Exception as e:
        logger.error("Failed to initialize services", error=str(e))
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global redis_client
    
    if redis_client:
        await redis_client.close()
        logger.info("Redis connection closed")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check Redis connection
        if redis_client:
            await redis_client.ping()
        
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "service": "router_service-v2"
        }
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service unhealthy")


@app.post("/route", response_model=RouteResponse)
async def route_request(
    request: RouteRequest,
    router: RouterV2 = Depends(get_router)
) -> RouteResponse:
    """Route a request using router v2."""
    try:
        start_time = time.time()
        
        # Convert request to dict
        request_dict = {
            'message': request.message,
            'user_id': request.user_id,
            'tenant_id': request.tenant_id,
            **request.metadata
        }
        
        # Route request
        decision: RouterDecision = await router.route_request(
            request_dict, request.tenant_id, request.user_id
        )
        
        # Convert features to dict
        features_dict = {
            'token_count': decision.features.token_count,
            'schema_strictness': decision.features.schema_strictness,
            'domain_flags': decision.features.domain_flags,
            'novelty_score': decision.features.novelty_score,
            'historical_failure_rate': decision.features.historical_failure_rate,
            'user_tier': decision.features.user_tier,
            'time_of_day': decision.features.time_of_day,
            'day_of_week': decision.features.day_of_week,
            'request_complexity': decision.features.request_complexity
        }
        
        # Convert escalation info
        escalation_info = {}
        if decision.escalation_decision:
            escalation_info = {
                'should_escalate': decision.escalation_decision.should_escalate,
                'reason': decision.escalation_decision.reason.value if decision.escalation_decision.reason else None,
                'target_tier': decision.escalation_decision.target_tier.value if decision.escalation_decision.target_tier else None,
                'early_exit_tier': decision.escalation_decision.early_exit_tier.value if decision.escalation_decision.early_exit_tier else None,
                'early_exit_confidence': decision.escalation_decision.early_exit_confidence
            }
        
        # Convert canary info
        canary_info = decision.canary_info or {}
        
        # Convert bandit info
        bandit_info = decision.bandit_info or {}
        
        # Convert classifier info
        classifier_info = decision.classifier_info or {}
        
        response = RouteResponse(
            tier=decision.tier.value,
            confidence=decision.confidence,
            decision_time_ms=decision.decision_time_ms,
            features=features_dict,
            escalation_info=escalation_info,
            canary_info=canary_info,
            bandit_info=bandit_info
        )
        
        # Log routing decision
        logger.info(
            "Request routed",
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            tier=decision.tier.value,
            confidence=decision.confidence,
            decision_time_ms=decision.decision_time_ms,
            canary=bool(decision.canary_info),
            escalated=decision.escalation_decision.should_escalate if decision.escalation_decision else False
        )
        
        return response
        
    except Exception as e:
        logger.error("Routing failed", error=str(e), tenant_id=request.tenant_id, user_id=request.user_id)
        raise HTTPException(status_code=500, detail=f"Routing failed: {str(e)}")


@app.post("/outcome")
async def record_outcome(
    request: OutcomeRequest,
    router: RouterV2 = Depends(get_router)
):
    """Record routing outcome for learning."""
    try:
        # Convert tier string to enum
        try:
            tier = Tier(request.tier.upper())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid tier: {request.tier}")
        
        # Record outcome
        await router.record_outcome(
            request.tenant_id,
            request.user_id,
            tier,
            request.success,
            request.latency_ms,
            request.quality_score
        )
        
        logger.info(
            "Outcome recorded",
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            tier=request.tier,
            success=request.success,
            latency_ms=request.latency_ms,
            quality_score=request.quality_score
        )
        
        return {"status": "success", "message": "Outcome recorded"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to record outcome", error=str(e), tenant_id=request.tenant_id, user_id=request.user_id)
        raise HTTPException(status_code=500, detail=f"Failed to record outcome: {str(e)}")


@app.get("/statistics/{tenant_id}", response_model=StatisticsResponse)
async def get_statistics(
    tenant_id: str,
    router: RouterV2 = Depends(get_router)
) -> StatisticsResponse:
    """Get router statistics for tenant."""
    try:
        stats = await router.get_router_statistics(tenant_id)
        
        return StatisticsResponse(
            tenant_id=stats['tenant_id'],
            bandit_statistics=stats['bandit_statistics'],
            canary_status=stats['canary_status'],
            escalation_statistics=stats['escalation_statistics'],
            recent_metrics=stats['recent_metrics']
        )
        
    except Exception as e:
        logger.error("Failed to get statistics", error=str(e), tenant_id=tenant_id)
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@app.post("/calibrate/{tenant_id}")
async def calibrate_models(
    tenant_id: str,
    router: RouterV2 = Depends(get_router)
):
    """Calibrate models for tenant."""
    try:
        await router.calibrate_models(tenant_id)
        
        logger.info("Models calibrated", tenant_id=tenant_id)
        
        return {"status": "success", "message": "Models calibrated"}
        
    except Exception as e:
        logger.error("Failed to calibrate models", error=str(e), tenant_id=tenant_id)
        raise HTTPException(status_code=500, detail=f"Failed to calibrate models: {str(e)}")


@app.post("/reset/{tenant_id}")
async def reset_learning(
    tenant_id: str,
    router: RouterV2 = Depends(get_router)
):
    """Reset learning for tenant."""
    try:
        await router.reset_learning(tenant_id)
        
        logger.info("Learning reset", tenant_id=tenant_id)
        
        return {"status": "success", "message": "Learning reset"}
        
    except Exception as e:
        logger.error("Failed to reset learning", error=str(e), tenant_id=tenant_id)
        raise HTTPException(status_code=500, detail=f"Failed to reset learning: {str(e)}")


@app.get("/metrics")
async def get_metrics(tenant_id: str = "default"):
    """Get Prometheus metrics."""
    try:
        router = await get_router()
        metrics = await router.get_prometheus_metrics(tenant_id)
        
        return metrics
        
    except Exception as e:
        logger.error("Failed to get metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level="info"
    )