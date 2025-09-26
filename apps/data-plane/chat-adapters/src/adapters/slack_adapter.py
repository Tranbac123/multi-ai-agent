import asyncio
import httpx
import hmac
import hashlib
import time
from typing import Dict, Any, Optional

class SlackAdapter:
    def __init__(self, token: str, signing_secret: Optional[str] = None):
        self.token = token
        self.signing_secret = signing_secret
        self.base_url = "https://slack.com/api"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def _verify_signature(self, body: str, timestamp: str, signature: str) -> bool:
        """Verify Slack request signature"""
        if not self.signing_secret:
            return True  # Skip verification if no secret provided
        
        expected_signature = (
            "v0=" + 
            hmac.new(
                self.signing_secret.encode(),
                f"v0:{timestamp}:{body}".encode(),
                hashlib.sha256
            ).hexdigest()
        )
        return hmac.compare_digest(expected_signature, signature)
    
    async def send_message(self, channel_id: str, content: str, metadata: Dict[str, Any] = None) -> bool:
        """Send a message to Slack channel"""
        try:
            payload = {
                "channel": channel_id,
                "text": content
            }
            
            # Add blocks if specified in metadata
            if metadata and "blocks" in metadata:
                payload["blocks"] = metadata["blocks"]
                payload["text"] = metadata.get("fallback_text", content)
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.base_url}/chat.postMessage",
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                return data.get("ok", False)
                
        except Exception as e:
            print(f"Slack adapter error: {e}")
            return False
    
    async def get_channel_info(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get channel information"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.base_url}/conversations.info",
                    headers=self.headers,
                    params={"channel": channel_id}
                )
                response.raise_for_status()
                data = response.json()
                return data.get("channel") if data.get("ok") else None
        except Exception:
            return None
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Slack API health"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{self.base_url}/auth.test",
                    headers=self.headers
                )
                response.raise_for_status()
                data = response.json()
                return {
                    "status": "healthy" if data.get("ok") else "unhealthy",
                    "user": data.get("user"),
                    "latency_ms": int(response.elapsed.total_seconds() * 1000)
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

