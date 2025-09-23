import asyncio
import time
import httpx
from typing import Dict, Any, Optional
from .models import AdapterRequest, AdapterResponse, ChatResponse, Platform
from .adapters import DiscordAdapter, SlackAdapter
from .settings import settings

class MessageProcessor:
    def __init__(self):
        self.adapters = {}
        self._initialize_adapters()
    
    def _initialize_adapters(self):
        """Initialize chat platform adapters"""
        if settings.discord_token:
            self.adapters[Platform.DISCORD] = DiscordAdapter(settings.discord_token)
        
        if settings.slack_token:
            self.adapters[Platform.SLACK] = SlackAdapter(
                settings.slack_token, 
                settings.slack_signing_secret
            )
    
    async def process_message(self, request: AdapterRequest) -> AdapterResponse:
        """Process incoming chat message and generate response"""
        start_time = time.time()
        
        try:
            # 1. Validate platform support
            if request.platform not in self.adapters:
                return AdapterResponse(
                    success=False,
                    error=f"Platform {request.platform} not configured",
                    processing_time_ms=int((time.time() - start_time) * 1000)
                )
            
            # 2. Process message through model gateway
            model_response = await self._call_model_gateway(request)
            if not model_response:
                return AdapterResponse(
                    success=False,
                    error="Failed to get response from model gateway",
                    processing_time_ms=int((time.time() - start_time) * 1000)
                )
            
            # 3. Create chat response
            chat_response = ChatResponse(
                platform=request.platform,
                channel_id=request.channel_id,
                content=model_response,
                metadata={
                    "tenant_id": request.tenant_id,
                    "user_id": request.user_id,
                    "username": request.username
                }
            )
            
            # 4. Send response through appropriate adapter
            adapter = self.adapters[request.platform]
            success = await adapter.send_message(
                request.channel_id,
                model_response,
                chat_response.metadata
            )
            
            if not success:
                return AdapterResponse(
                    success=False,
                    error=f"Failed to send message via {request.platform}",
                    processing_time_ms=int((time.time() - start_time) * 1000)
                )
            
            return AdapterResponse(
                success=True,
                response=chat_response,
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
            
        except Exception as e:
            return AdapterResponse(
                success=False,
                error=str(e),
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
    
    async def _call_model_gateway(self, request: AdapterRequest) -> Optional[str]:
        """Call model gateway for response generation"""
        try:
            # Prepare request for model gateway
            model_request = {
                "tenant_id": request.tenant_id,
                "model": "gpt-3.5-turbo",  # Default model
                "messages": [
                    {
                        "role": "system",
                        "content": f"You are a helpful AI assistant responding in {request.platform} chat. Keep responses concise and appropriate for chat format."
                    },
                    {
                        "role": "user",
                        "content": f"User {request.username}: {request.content}"
                    }
                ],
                "max_tokens": 500,
                "temperature": 0.7,
                "metadata": {
                    "platform": request.platform,
                    "channel_id": request.channel_id,
                    "user_id": request.user_id,
                    "context": request.context or {}
                }
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{settings.model_gateway_url}/v1/chat/completions",
                    json=model_request
                )
                response.raise_for_status()
                data = response.json()
                
                return data.get("content", "")
                
        except Exception as e:
            print(f"Model gateway error: {e}")
            return None
    
    async def get_platform_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health status for all configured platforms"""
        health_status = {}
        
        for platform, adapter in self.adapters.items():
            if hasattr(adapter, 'health_check'):
                health_status[platform.value] = await adapter.health_check()
            else:
                health_status[platform.value] = {"status": "unknown"}
        
        return health_status

