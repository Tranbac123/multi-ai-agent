"""TikTok Chat Adapter for Social Commerce Integration."""

import asyncio
from typing import Dict, Any, Optional
import httpx
import structlog
from fastapi import APIRouter, Request, HTTPException, status

from src..core.unified_message import UnifiedMessage, UnifiedResponse, UserProfile, MessageContent, Channel, MessageType
from libs.resilience.tool_adapter_base import ResilientToolAdapter

logger = structlog.get_logger(__name__)


class TikTokChatAdapter(ResilientToolAdapter):
    """TikTok chat adapter for social commerce and creator interactions."""
    
    def __init__(self, app_id: str, app_secret: str, **kwargs):
        super().__init__(name="tiktok_chat", **kwargs)
        self.app_id = app_id
        self.app_secret = app_secret
        self.api_url = "https://business-api.tiktok.com/open_api/v1.3"
        self.router = APIRouter(prefix="/tiktok", tags=["TikTok Chat"])
        self.setup_routes()
    
    def setup_routes(self):
        """Setup FastAPI routes for TikTok webhook."""
        
        @self.router.post("/webhook")
        async def handle_webhook(request: Request):
            """Handle incoming TikTok webhook events."""
            try:
                payload = await request.json()
                logger.info("Received TikTok webhook", payload=payload)
                
                # Process webhook events
                await self.process_webhook_events(payload)
                
                return {"status": "success"}
                
            except Exception as e:
                logger.error("Error processing TikTok webhook", error=str(e))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error processing webhook"
                )
    
    async def process_webhook_events(self, payload: Dict[str, Any]) -> None:
        """Process incoming webhook events from TikTok."""
        event = payload.get("event")
        
        if event == "message_received":
            await self.process_message(payload)
        elif event == "user_action":
            await self.process_user_action(payload)
        elif event == "video_shared":
            await self.process_video_shared(payload)
        else:
            logger.info("Unhandled TikTok event", event=event)
    
    async def process_message(self, payload: Dict[str, Any]) -> UnifiedMessage:
        """Process TikTok chat message."""
        user_id = payload.get("user_id")
        message_data = payload.get("message", {})
        timestamp = payload.get("timestamp", 0)
        
        # Create user profile
        user_profile = UserProfile(
            user_id=user_id,
            platform_user_id=user_id,
            channel=Channel.TIKTOK,
            metadata={"tiktok_user_id": user_id}
        )
        
        # Extract message content
        content = MessageContent()
        
        if message_data.get("text"):
            content.text = message_data["text"]
        elif message_data.get("media"):
            media = message_data["media"]
            content.media_url = media.get("url")
            content.media_type = media.get("type")
        
        # Determine message type
        message_type = MessageType.TEXT
        if content.media_type:
            if content.media_type == "image":
                message_type = MessageType.IMAGE
            elif content.media_type == "video":
                message_type = MessageType.VIDEO
        
        # Create unified message
        unified_message = UnifiedMessage(
            channel=Channel.TIKTOK,
            user_profile=user_profile,
            message_type=message_type,
            content=content,
            context={
                "tiktok_message_id": message_data.get("id"),
                "tiktok_timestamp": timestamp,
                "original_payload": payload
            }
        )
        
        logger.info("Processed TikTok message", 
                   message_id=unified_message.message_id,
                   user_id=user_id,
                   message_type=message_type.value)
        
        return unified_message
    
    async def process_user_action(self, payload: Dict[str, Any]) -> UnifiedMessage:
        """Process TikTok user action (like, follow, etc.)."""
        user_id = payload.get("user_id")
        action = payload.get("action", {})
        timestamp = payload.get("timestamp", 0)
        
        # Create user profile
        user_profile = UserProfile(
            user_id=user_id,
            platform_user_id=user_id,
            channel=Channel.TIKTOK
        )
        
        # Create message content for action
        content = MessageContent(text=f"User action: {action.get('type', 'unknown')}")
        
        # Create unified message
        unified_message = UnifiedMessage(
            channel=Channel.TIKTOK,
            user_profile=user_profile,
            message_type=MessageType.TEXT,
            content=content,
            context={
                "tiktok_action": action,
                "tiktok_timestamp": timestamp,
                "original_payload": payload
            }
        )
        
        logger.info("Processed TikTok user action", 
                   message_id=unified_message.message_id,
                   user_id=user_id,
                   action_type=action.get("type"))
        
        return unified_message
    
    async def process_video_shared(self, payload: Dict[str, Any]) -> UnifiedMessage:
        """Process TikTok video shared event."""
        user_id = payload.get("user_id")
        video_data = payload.get("video", {})
        timestamp = payload.get("timestamp", 0)
        
        # Create user profile
        user_profile = UserProfile(
            user_id=user_id,
            platform_user_id=user_id,
            channel=Channel.TIKTOK
        )
        
        # Create message content for shared video
        content = MessageContent(
            text=f"Video shared: {video_data.get('title', 'Untitled')}",
            media_url=video_data.get("url"),
            media_type="video"
        )
        
        # Create unified message
        unified_message = UnifiedMessage(
            channel=Channel.TIKTOK,
            user_profile=user_profile,
            message_type=MessageType.VIDEO,
            content=content,
            context={
                "tiktok_video_id": video_data.get("id"),
                "tiktok_video_title": video_data.get("title"),
                "tiktok_timestamp": timestamp,
                "original_payload": payload
            }
        )
        
        logger.info("Processed TikTok video shared", 
                   message_id=unified_message.message_id,
                   user_id=user_id,
                   video_title=video_data.get("title"))
        
        return unified_message
    
    async def send_message(self, user_id: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send message via TikTok API."""
        url = f"{self.api_url}/chat/message/send"
        
        payload = {
            "user_id": user_id,
            "message": message
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                result = response.json()
                logger.info("TikTok message sent successfully", 
                           user_id=user_id,
                           message_id=result.get("message_id"))
                
                return result
                
        except httpx.HTTPError as e:
            logger.error("Failed to send TikTok message", 
                        user_id=user_id,
                        error=str(e))
            raise
    
    async def send_unified_response(self, response: UnifiedResponse) -> Dict[str, Any]:
        """Send unified response via TikTok."""
        # Convert unified response to TikTok format
        tiktok_message = self._convert_to_tiktok_format(response)
        
        return await self.send_message(response.recipient_id, tiktok_message)
    
    def _convert_to_tiktok_format(self, response: UnifiedResponse) -> Dict[str, Any]:
        """Convert unified response to TikTok format."""
        content = response.content
        
        if content.text and not content.buttons:
            # Simple text message
            return {"text": content.text}
        
        elif content.text and content.buttons:
            # Text with interactive elements
            return {
                "text": content.text,
                "interactive_elements": [
                    {
                        "type": "button",
                        "text": button.get("title", "Button"),
                        "action": {
                            "type": "url",
                            "url": button.get("url", "#")
                        }
                    }
                    for button in content.buttons
                ]
            }
        
        elif content.media_url:
            # Media message
            return {
                "media": {
                    "type": content.media_type or "image",
                    "url": content.media_url
                }
            }
        
        else:
            # Fallback to text
            return {"text": content.text or "Message sent"}
    
    async def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get TikTok user profile information."""
        url = f"{self.api_url}/user/info"
        params = {"user_id": user_id}
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error("Failed to get TikTok user profile", 
                        user_id=user_id,
                        error=str(e))
            return {}
    
    async def send_video_message(self, user_id: str, video_url: str, 
                                title: str = "", description: str = "") -> Dict[str, Any]:
        """Send video message via TikTok."""
        message = {
            "media": {
                "type": "video",
                "url": video_url,
                "title": title,
                "description": description
            }
        }
        
        return await self.send_message(user_id, message)
    
    async def send_product_message(self, user_id: str, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send product showcase message for social commerce."""
        message = {
            "text": f"Check out this product: {product_data.get('name', 'Product')}",
            "interactive_elements": [
                {
                    "type": "product_showcase",
                    "product": {
                        "id": product_data.get("id"),
                        "name": product_data.get("name"),
                        "price": product_data.get("price"),
                        "image_url": product_data.get("image_url"),
                        "description": product_data.get("description")
                    }
                }
            ]
        }
        
        return await self.send_message(user_id, message)
    
    async def send_creator_tools_message(self, user_id: str, tool_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send creator tools message for content creators."""
        message = {
            "text": "Creator tools available:",
            "interactive_elements": [
                {
                    "type": "creator_tool",
                    "tool": tool_data
                }
            ]
        }
        
        return await self.send_message(user_id, message)
    
    async def get_trending_content(self, category: str = "general") -> Dict[str, Any]:
        """Get trending TikTok content for engagement."""
        url = f"{self.api_url}/trending/content"
        params = {"category": category}
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error("Failed to get trending TikTok content", 
                        category=category,
                        error=str(e))
            return {}
    
    async def execute_operation(self, operation: str, payload: Dict[str, Any], 
                              headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Execute the actual TikTok API operation."""
        if operation == "send_message":
            return await self.send_message(
                recipient_id=payload["recipient_id"],
                message_text=payload["message_text"]
            )
        elif operation == "get_user_profile":
            return await self.get_user_profile(payload["user_id"])
        elif operation == "get_trending_content":
            return await self.get_trending_content(payload.get("category", "general"))
        elif operation == "create_live_session":
            return await self.create_live_session(
                creator_id=payload["creator_id"],
                title=payload.get("title", "Live Session")
            )
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def compensate(self, operation: str, payload: Dict[str, Any], 
                        result: Dict[str, Any]) -> bool:
        """Compensate for a completed TikTok operation (rollback side effects)."""
        try:
            if operation == "send_message":
                # For TikTok messages, we can't actually unsend, but we can log the compensation
                logger.info("Compensating TikTok message send", 
                           message_id=result.get("message_id"),
                           recipient_id=payload["recipient_id"])
                return True
            
            elif operation == "create_live_session":
                # End the live session as compensation
                session_id = result.get("session_id")
                if session_id:
                    await self.end_live_session(session_id)
                return True
            
            elif operation in ["get_user_profile", "get_trending_content"]:
                # No side effects to compensate for read operations
                return True
            
            else:
                logger.warning(f"No compensation logic for operation: {operation}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to compensate operation {operation}: {e}")
            return False
