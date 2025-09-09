"""Router v2 service with feature store and bandit policy."""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from uuid import UUID, uuid4

import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
import structlog
from opentelemetry import trace

from libs.clients.database import get_db_session
from libs.clients.auth import get_current_tenant
from libs.clients.rate_limiter import RateLimiter
from libs.clients.event_bus import EventBus, EventProducer
from libs.utils.responses import success_response, error_response
from .core.feature_store import FeatureStore
from .core.bandit_policy import BanditPolicy, RoutingDecision
from .core.llm_judge import LLMJudge

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
tracer = trace.get_tracer(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Router v2 Service")
    
    # Initialize Redis client
    import redis.asyncio as redis
    app.state.redis = redis.from_url("redis://localhost:6379")
    
    # Initialize components
    app.state.feature_store = FeatureStore(app.state.redis)
    app.state.bandit_policy = BanditPolicy(app.state.redis)
    app.state.llm_judge = LLMJudge(api_key="your_openai_api_key_here")
    app.state.rate_limiter = RateLimiter(app.state.redis)
    app.state.event_bus = EventBus()
    app.state.event_producer = EventProducer(app.state.event_bus)
    
    yield
    
    # Shutdown
    logger.info("Shutting down Router v2 Service")
    await app.state.redis.close()


def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="Router v2 Service",
        version="2.0.0",
        description="Intelligent routing service with feature store and bandit policy",
        lifespan=lifespan
    )
    
    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app


app = create_app()


# API Routes
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "router-v2-service"}


@app.post("/api/v1/decide")
async def decide_route(
    request: Dict[str, Any],
    tenant_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db_session)
):
    """Make routing decision for request."""
    try:
        start_time = time.time()
        request_id = str(uuid4())
        
        # Extract request text and context
        request_text = request.get("text", "")
        context = request.get("context", {})
        
        if not request_text:
            raise HTTPException(status_code=400, detail="Request text is required")
        
        # Check rate limits
        if not await app.state.rate_limiter.is_tenant_allowed(tenant_id):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        # Extract features
        features = await app.state.feature_store.extract_features(
            request_text, context, tenant_id
        )
        
        # Make routing decision
        decision = await app.state.bandit_policy.decide_route(
            features, tenant_id, request_id
        )
        
        # Use LLM judge for borderline cases
        if decision.policy_escalation or decision.confidence < 0.7:
            judgment = await app.state.llm_judge.judge_routing_decision(
                request_text, features, decision.tier, decision.confidence, tenant_id
            )
            
            # Update decision based on judgment
            if judgment.get("final_tier") != decision.tier:
                decision.tier = judgment["final_tier"]
                decision.confidence = judgment.get("confidence", decision.confidence)
                decision.reasons.append(f"LLM judge override: {judgment.get('reasoning', '')}")
        
        # Store features for learning
        await app.state.feature_store.store_features(request_id, features, tenant_id)
        
        # Publish routing event
        await app.state.event_producer.publish(
            "router.decision.made",
            {
                "request_id": request_id,
                "tenant_id": str(tenant_id),
                "tier": decision.tier,
                "confidence": decision.confidence,
                "expected_cost": decision.expected_cost,
                "expected_latency": decision.expected_latency,
                "processing_time": time.time() - start_time
            }
        )
        
        # Prepare response
        response_data = {
            "request_id": request_id,
            "tier": decision.tier,
            "confidence": decision.confidence,
            "expected_cost_usd": decision.expected_cost,
            "expected_latency_ms": decision.expected_latency,
            "reasons": decision.reasons,
            "policy_escalation": decision.policy_escalation,
            "processing_time_ms": (time.time() - start_time) * 1000
        }
        
        logger.info("Routing decision made", 
                   request_id=request_id, 
                   tier=decision.tier, 
                   confidence=decision.confidence,
                   tenant_id=tenant_id)
        
        return success_response(data=response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Routing decision failed", 
                    tenant_id=tenant_id, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Routing decision failed")


@app.post("/api/v1/feedback")
async def submit_feedback(
    feedback: Dict[str, Any],
    tenant_id: UUID = Depends(get_current_tenant)
):
    """Submit feedback for routing decision."""
    try:
        request_id = feedback.get("request_id")
        tier = feedback.get("tier")
        success = feedback.get("success", False)
        latency_ms = feedback.get("latency_ms", 0)
        actual_cost = feedback.get("actual_cost", 0)
        
        if not request_id or not tier:
            raise HTTPException(status_code=400, detail="Request ID and tier are required")
        
        # Update bandit policy performance
        await app.state.bandit_policy.update_performance(
            tier, success, latency_ms, tenant_id
        )
        
        # Publish feedback event
        await app.state.event_producer.publish(
            "router.feedback.received",
            {
                "request_id": request_id,
                "tenant_id": str(tenant_id),
                "tier": tier,
                "success": success,
                "latency_ms": latency_ms,
                "actual_cost": actual_cost
            }
        )
        
        logger.info("Feedback received", 
                   request_id=request_id, 
                   tier=tier, 
                   success=success,
                   tenant_id=tenant_id)
        
        return success_response(data={"status": "feedback_received"})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Feedback submission failed", 
                    tenant_id=tenant_id, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Feedback submission failed")


@app.get("/api/v1/features/{request_id}")
async def get_features(
    request_id: str,
    tenant_id: UUID = Depends(get_current_tenant)
):
    """Get features for request."""
    try:
        features = await app.state.feature_store.get_features(request_id)
        
        if not features:
            raise HTTPException(status_code=404, detail="Features not found")
        
        return success_response(data=features)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get features", 
                    request_id=request_id, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get features")


@app.get("/api/v1/performance/{tenant_id}")
async def get_performance_stats(tenant_id: UUID):
    """Get performance statistics for tenant."""
    try:
        stats = {}
        
        # Get tier performance
        for tier in ["SLM_A", "SLM_B", "LLM"]:
            performance = await app.state.bandit_policy._get_tier_performance(tier, tenant_id)
            stats[tier] = performance
        
        # Get judgment stats
        judgment_stats = await app.state.llm_judge.get_judgment_stats(tenant_id)
        stats["judgment_stats"] = judgment_stats
        
        return success_response(data=stats)
        
    except Exception as e:
        logger.error("Failed to get performance stats", 
                    tenant_id=tenant_id, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get performance stats")


@app.post("/api/v1/canary/{tenant_id}")
async def enable_canary_mode(
    tenant_id: UUID,
    enabled: bool = True
):
    """Enable/disable canary mode for tenant."""
    try:
        canary_key = f"canary_mode:{tenant_id}"
        
        if enabled:
            await app.state.redis.set(canary_key, "true", ex=86400)  # 24 hours
        else:
            await app.state.redis.delete(canary_key)
        
        logger.info("Canary mode updated", 
                   tenant_id=tenant_id, 
                   enabled=enabled)
        
        return success_response(data={"canary_enabled": enabled})
        
    except Exception as e:
        logger.error("Failed to update canary mode", 
                    tenant_id=tenant_id, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update canary mode")


if __name__ == "__main__":
    uvicorn.run(
        "apps.router_service.main:app",
        host="0.0.0.0",
        port=8002,
        reload=True
    )