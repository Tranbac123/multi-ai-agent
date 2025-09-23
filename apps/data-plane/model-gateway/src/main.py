import uuid
import time
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from .settings import settings
from .models import (
    CompletionRequest, CompletionResponse, HealthResponse, 
    ProviderStatus, TokenMeteringEvent, Provider
)
from .providers import ProviderFactory
from .circuit_breaker import CircuitBreakerManager, CircuitBreakerConfig
from .rate_limiter import RateLimiter

app = FastAPI(title=settings.app_name, version="0.1.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
circuit_breakers = CircuitBreakerManager()
rate_limiter = RateLimiter()

async def publish_metering_event(event: TokenMeteringEvent):
    """Publish token usage event for billing"""
    # TODO: Integrate with NATS event bus from libs/data-plane
    print(f"Metering event: {event.tenant_id} used {event.total_tokens} tokens")

async def check_tenant_policy(tenant_id: str, model: str) -> bool:
    """Check if tenant is allowed to use this model"""
    # TODO: Integrate with policy-adapter service
    return True

@app.get("/healthz")
async def health_check():
    return {"ok": True, "service": settings.app_name}

@app.get("/v1/health", response_model=HealthResponse)
async def detailed_health():
    """Detailed health check including provider status"""
    provider_statuses = []
    
    for provider in Provider:
        try:
            # Quick health check - could ping provider endpoints
            provider_statuses.append(ProviderStatus(
                provider=provider,
                status="healthy",
                error_rate=0.0,
                avg_latency_ms=100,
                last_check=str(int(time.time()))
            ))
        except Exception:
            provider_statuses.append(ProviderStatus(
                provider=provider,
                status="down",
                error_rate=1.0,
                avg_latency_ms=0,
                last_check=str(int(time.time()))
            ))
    
    return HealthResponse(
        status="healthy",
        providers=provider_statuses,
        circuit_breakers=circuit_breakers.get_all_states()
    )

@app.post("/v1/chat/completions", response_model=CompletionResponse)
async def chat_completion(
    request: CompletionRequest,
    background_tasks: BackgroundTasks
):
    """Main endpoint for chat completions with all safety features"""
    
    # 1. Rate limiting check
    if not await rate_limiter.check_rate_limit(request.tenant_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    # 2. Policy check
    if not await check_tenant_policy(request.tenant_id, request.model):
        raise HTTPException(status_code=403, detail="Model not allowed for tenant")
    
    # 3. Determine provider
    provider_enum = request.provider or ProviderFactory.get_default_provider(request.model)
    
    # 4. Get circuit breaker for this provider
    breaker_name = f"{provider_enum.value}_{request.model}"
    breaker = circuit_breakers.get_breaker(
        breaker_name,
        CircuitBreakerConfig(
            failure_threshold=settings.failure_threshold,
            recovery_timeout=settings.recovery_timeout
        )
    )
    
    # 5. Execute with circuit breaker and retry logic
    provider = ProviderFactory.get_provider(provider_enum)
    
    async def make_request():
        return await provider.complete(request)
    
    try:
        # Execute with circuit breaker
        response = await breaker.call(make_request)
        
        # 6. Publish metering event
        metering_event = TokenMeteringEvent(
            tenant_id=request.tenant_id,
            model=response.model,
            provider=response.provider,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            cost_usd=response.usage.cost_usd or 0.0,
            request_id=response.id,
            timestamp=str(int(time.time()))
        )
        
        background_tasks.add_task(publish_metering_event, metering_event)
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Provider error: {str(e)}")

@app.get("/v1/models")
async def list_models():
    """List available models across all providers"""
    return {
        "models": [
            *[{"id": model, "provider": "openai"} for model in settings.openai_models],
            *[{"id": model, "provider": "anthropic"} for model in settings.anthropic_models],
            *[{"id": model, "provider": "azure_openai"} for model in settings.azure_models],
        ]
    }

@app.get("/v1/providers/{provider}/status")
async def provider_status(provider: str):
    """Get status of a specific provider"""
    breaker_pattern = f"{provider}_*"
    states = circuit_breakers.get_all_states()
    provider_breakers = {k: v for k, v in states.items() if k.startswith(provider)}
    
    return {
        "provider": provider,
        "circuit_breakers": provider_breakers,
        "available": len([b for b in provider_breakers.values() if b["state"] != "open"]) > 0
    }

