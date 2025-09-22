"""Multi-Channel Chat Adapters Service."""

import os
from contextlib import asynccontextmanager
from typing import Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from src.adapters.facebook_adapter import FacebookMessengerAdapter
from src.adapters.zalo_adapter import ZaloChatAdapter
from src.adapters.tiktok_adapter import TikTokChatAdapter
from src.core.unified_message import UnifiedMessage, UnifiedResponse

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

# Global adapter instances
adapters: Dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    logger.info("Starting Chat Adapters Service")
    
    # Initialize adapters based on environment variables
    try:
        # Facebook Messenger Adapter
        facebook_token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")
        facebook_verify = os.getenv("FACEBOOK_WEBHOOK_VERIFY_TOKEN")
        if facebook_token and facebook_verify:
            adapters["facebook"] = FacebookMessengerAdapter(facebook_token, facebook_verify)
            app.include_router(adapters["facebook"].router)
            logger.info("Facebook Messenger adapter initialized")
        
        # Zalo Chat Adapter
        zalo_oa_id = os.getenv("ZALO_OA_ID")
        zalo_secret = os.getenv("ZALO_SECRET_KEY")
        if zalo_oa_id and zalo_secret:
            adapters["zalo"] = ZaloChatAdapter(zalo_oa_id, zalo_secret)
            app.include_router(adapters["zalo"].router)
            logger.info("Zalo Chat adapter initialized")
        
        # TikTok Chat Adapter
        tiktok_app_id = os.getenv("TIKTOK_APP_ID")
        tiktok_secret = os.getenv("TIKTOK_APP_SECRET")
        if tiktok_app_id and tiktok_secret:
            adapters["tiktok"] = TikTokChatAdapter(tiktok_app_id, tiktok_secret)
            app.include_router(adapters["tiktok"].router)
            logger.info("TikTok Chat adapter initialized")
        
        logger.info("All chat adapters initialized successfully", 
                   adapters=list(adapters.keys()))
        
    except Exception as e:
        logger.error("Failed to initialize chat adapters", error=str(e))
        raise
    
    yield
    
    logger.info("Shutting down Chat Adapters Service")


# Create FastAPI app
app = FastAPI(
    title="Multi-Channel Chat Adapters",
    description="Unified chat integration for Facebook, Zalo, TikTok, and other platforms",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Multi-Channel Chat Adapters",
        "version": "1.0.0",
        "status": "healthy",
        "adapters": list(adapters.keys()),
        "endpoints": {
            "facebook": "/facebook/webhook" if "facebook" in adapters else None,
            "zalo": "/zalo/webhook" if "zalo" in adapters else None,
            "tiktok": "/tiktok/webhook" if "tiktok" in adapters else None,
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "chat-adapters",
        "adapters": {
            name: "active" for name in adapters.keys()
        }
    }


@app.get("/adapters")
async def list_adapters():
    """List available chat adapters."""
    return {
        "adapters": [
            {
                "name": name,
                "type": adapter.__class__.__name__,
                "status": "active",
                "endpoints": {
                    "webhook": f"/{name}/webhook"
                }
            }
            for name, adapter in adapters.items()
        ]
    }


@app.post("/send/{channel}")
async def send_message(channel: str, message_data: Dict[str, Any]):
    """Send message via specified channel."""
    if channel not in adapters:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel '{channel}' not available"
        )
    
    try:
        adapter = adapters[channel]
        user_id = message_data.get("user_id")
        message = message_data.get("message", {})
        
        result = await adapter.send_message(user_id, message)
        
        logger.info("Message sent successfully", 
                   channel=channel, 
                   user_id=user_id,
                   message_id=result.get("message_id"))
        
        return {
            "status": "success",
            "channel": channel,
            "result": result
        }
        
    except Exception as e:
        logger.error("Failed to send message", 
                    channel=channel, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message via {channel}: {str(e)}"
        )


@app.get("/user/{channel}/{user_id}")
async def get_user_profile(channel: str, user_id: str):
    """Get user profile from specified channel."""
    if channel not in adapters:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel '{channel}' not available"
        )
    
    try:
        adapter = adapters[channel]
        profile = await adapter.get_user_profile(user_id)
        
        return {
            "status": "success",
            "channel": channel,
            "user_id": user_id,
            "profile": profile
        }
        
    except Exception as e:
        logger.error("Failed to get user profile", 
                    channel=channel, 
                    user_id=user_id,
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user profile from {channel}: {str(e)}"
        )


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error("Unhandled exception", 
                path=request.url.path,
                method=request.method,
                error=str(exc))
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "detail": str(exc) if os.getenv("DEBUG") == "true" else "An error occurred"
        }
    )


if __name__ == "__main__":
    port = int(os.getenv("CHAT_ADAPTER_PORT", 8006))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("DEBUG") == "true",
        log_level="info"
    )
