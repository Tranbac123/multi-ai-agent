import asyncio
import httpx
from typing import Dict, Any, Optional
from ..models import ChatResponse, Platform

class DiscordAdapter:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://discord.com/api/v10"
        self.headers = {
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json"
        }
    
    async def send_message(self, channel_id: str, content: str, metadata: Dict[str, Any] = None) -> bool:
        """Send a message to Discord channel"""
        try:
            payload = {
                "content": content[:2000]  # Discord limit
            }
            
            # Add embeds if specified in metadata
            if metadata and "embeds" in metadata:
                payload["embeds"] = metadata["embeds"]
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.base_url}/channels/{channel_id}/messages",
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                return True
                
        except Exception as e:
            print(f"Discord adapter error: {e}")
            return False
    
    async def get_channel_info(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get channel information"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.base_url}/channels/{channel_id}",
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except Exception:
            return None
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Discord API health"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{self.base_url}/gateway/bot",
                    headers=self.headers
                )
                response.raise_for_status()
                return {
                    "status": "healthy",
                    "latency_ms": int(response.elapsed.total_seconds() * 1000)
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

