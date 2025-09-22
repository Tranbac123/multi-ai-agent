"""Facebook Messenger Chat Adapter."""

import asyncio
from typing import Dict, Any, Optional
import httpx
import structlog
from fastapi import APIRouter, Request, HTTPException, status

from src..core.unified_message import UnifiedMessage, UnifiedResponse, UserProfile, MessageContent, Channel, MessageType
from libs.resilience.tool_adapter_base import ResilientToolAdapter

logger = structlog.get_logger(__name__)


class FacebookMessengerAdapter(ResilientToolAdapter):
    """Facebook Messenger chat adapter for webhook handling and message sending."""
    
    def __init__(self, page_access_token: str, webhook_verify_token: str, **kwargs):
        super().__init__(name="facebook_messenger", **kwargs)
        self.page_access_token = page_access_token
        self.webhook_verify_token = webhook_verify_token
        self.api_url = "https://graph.facebook.com/v18.0"
        self.router = APIRouter(prefix="/facebook", tags=["Facebook Messenger"])
        self.setup_routes()
    
    def setup_routes(self):
        """Setup FastAPI routes for Facebook webhook."""
        
        @self.router.get("/webhook")
        async def verify_webhook(request: Request):
            """Verify Facebook webhook endpoint."""
            verify_token = request.query_params.get("hub.verify_token")
            challenge = request.query_params.get("hub.challenge")
            
            if verify_token == self.webhook_verify_token:
                logger.info("Facebook webhook verified successfully")
                return int(challenge) if challenge else "OK"
            
            logger.error("Facebook webhook verification failed", verify_token=verify_token)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid verify token"
            )
        
        @self.router.post("/webhook")
        async def handle_webhook(request: Request):
            """Handle incoming Facebook webhook events."""
            try:
                payload = await request.json()
                logger.info("Received Facebook webhook", payload=payload)
                
                # Process webhook events
                await self.process_webhook_events(payload)
                
                return {"status": "success"}
                
            except Exception as e:
                logger.error("Error processing Facebook webhook", error=str(e))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error processing webhook"
                )
    
    async def process_webhook_events(self, payload: Dict[str, Any]) -> None:
        """Process incoming webhook events from Facebook."""
        for entry in payload.get("entry", []):
            for event in entry.get("messaging", []):
                if event.get("message"):
                    await self.process_message(event)
                elif event.get("postback"):
                    await self.process_postback(event)
                elif event.get("delivery"):
                    await self.process_delivery(event)
                elif event.get("read"):
                    await self.process_read(event)
    
    async def process_message(self, event: Dict[str, Any]) -> UnifiedMessage:
        """Process incoming Facebook message and convert to unified format."""
        sender_id = event["sender"]["id"]
        message = event["message"]
        timestamp = event.get("timestamp", 0)
        
        # Extract message content
        content = MessageContent()
        
        if message.get("text"):
            content.text = message["text"]
        elif message.get("attachments"):
            attachment = message["attachments"][0]
            content.media_type = attachment.get("type")
            content.media_url = attachment.get("payload", {}).get("url")
        
        # Create user profile
        user_profile = UserProfile(
            user_id=sender_id,
            platform_user_id=sender_id,
            channel=Channel.FACEBOOK,
            metadata={"facebook_user_id": sender_id}
        )
        
        # Create unified message
        unified_message = UnifiedMessage(
            channel=Channel.FACEBOOK,
            user_profile=user_profile,
            message_type=MessageType.TEXT if content.text else MessageType.IMAGE,
            content=content,
            context={
                "facebook_message_id": message.get("mid"),
                "facebook_timestamp": timestamp,
                "original_event": event
            }
        )
        
        logger.info("Processed Facebook message", 
                   message_id=unified_message.message_id,
                   user_id=sender_id,
                   content_type=unified_message.message_type.value)
        
        return unified_message
    
    async def process_postback(self, event: Dict[str, Any]) -> UnifiedMessage:
        """Process Facebook postback event."""
        sender_id = event["sender"]["id"]
        postback = event["postback"]
        
        # Create user profile
        user_profile = UserProfile(
            user_id=sender_id,
            platform_user_id=sender_id,
            channel=Channel.FACEBOOK
        )
        
        # Create unified message for postback
        content = MessageContent(text=postback.get("title", ""))
        
        unified_message = UnifiedMessage(
            channel=Channel.FACEBOOK,
            user_profile=user_profile,
            message_type=MessageType.POSTBACK,
            content=content,
            context={
                "facebook_postback_payload": postback.get("payload"),
                "facebook_timestamp": event.get("timestamp", 0),
                "original_event": event
            }
        )
        
        logger.info("Processed Facebook postback", 
                   message_id=unified_message.message_id,
                   user_id=sender_id,
                   payload=postback.get("payload"))
        
        return unified_message
    
    async def process_delivery(self, event: Dict[str, Any]) -> None:
        """Process message delivery confirmation."""
        logger.info("Message delivery confirmed", 
                   recipient_id=event["sender"]["id"],
                   message_ids=event["delivery"].get("mids", []))
    
    async def process_read(self, event: Dict[str, Any]) -> None:
        """Process message read confirmation."""
        logger.info("Message read confirmed", 
                   recipient_id=event["sender"]["id"],
                   timestamp=event["read"].get("watermark", 0))
    
    async def send_message(self, recipient_id: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send message via Facebook Messenger API."""
        url = f"{self.api_url}/me/messages"
        params = {"access_token": self.page_access_token}
        
        payload = {
            "recipient": {"id": recipient_id},
            "message": message
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, params=params, json=payload)
                response.raise_for_status()
                
                result = response.json()
                logger.info("Facebook message sent successfully", 
                           recipient_id=recipient_id,
                           message_id=result.get("message_id"))
                
                return result
                
        except httpx.HTTPError as e:
            logger.error("Failed to send Facebook message", 
                        recipient_id=recipient_id,
                        error=str(e))
            raise
    
    async def send_unified_response(self, response: UnifiedResponse) -> Dict[str, Any]:
        """Send unified response via Facebook Messenger."""
        # Convert unified response to Facebook format
        facebook_message = self._convert_to_facebook_format(response)
        
        return await self.send_message(response.recipient_id, facebook_message)
    
    def _convert_to_facebook_format(self, response: UnifiedResponse) -> Dict[str, Any]:
        """Convert unified response to Facebook Messenger format."""
        content = response.content
        
        if content.text and not content.buttons and not content.quick_replies:
            # Simple text message
            return {"text": content.text}
        
        elif content.text and content.quick_replies:
            # Text with quick replies
            return {
                "text": content.text,
                "quick_replies": [
                    {
                        "content_type": "text",
                        "title": reply.get("title", "Reply"),
                        "payload": reply.get("payload", reply.get("title"))
                    }
                    for reply in content.quick_replies
                ]
            }
        
        elif content.buttons:
            # Message with buttons
            return {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "button",
                        "text": content.text or "Choose an option:",
                        "buttons": [
                            {
                                "type": "postback",
                                "title": button.get("title", "Button"),
                                "payload": button.get("payload", button.get("title"))
                            }
                            for button in content.buttons
                        ]
                    }
                }
            }
        
        elif content.media_url:
            # Media message
            return {
                "attachment": {
                    "type": content.media_type or "image",
                    "payload": {
                        "url": content.media_url
                    }
                }
            }
        
        else:
            # Fallback to text
            return {"text": content.text or "Message sent"}
    
    async def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get Facebook user profile information."""
        url = f"{self.api_url}/{user_id}"
        params = {
            "access_token": self.page_access_token,
            "fields": "first_name,last_name,profile_pic,locale,timezone"
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error("Failed to get Facebook user profile", 
                        user_id=user_id,
                        error=str(e))
            return {}
    
    async def set_typing_indicator(self, recipient_id: str, typing: bool = True) -> Dict[str, Any]:
        """Set typing indicator for Facebook user."""
        url = f"{self.api_url}/me/messages"
        params = {"access_token": self.page_access_token}
        
        action = "typing_on" if typing else "typing_off"
        payload = {
            "recipient": {"id": recipient_id},
            "sender_action": action
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, params=params, json=payload)
                response.raise_for_status()
                
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error("Failed to set Facebook typing indicator", 
                        recipient_id=recipient_id,
                        error=str(e))
            return {}
    
    async def execute_operation(self, operation: str, payload: Dict[str, Any], 
                              headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Execute the actual Facebook API operation."""
        if operation == "send_message":
            return await self.send_message(
                recipient_id=payload["recipient_id"],
                message_text=payload["message_text"],
                message_type=payload.get("message_type", "text")
            )
        elif operation == "set_typing":
            return await self.set_typing_indicator(
                recipient_id=payload["recipient_id"],
                action=payload.get("action", "typing_on")
            )
        elif operation == "get_user_profile":
            return await self.get_user_profile(payload["user_id"])
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def compensate(self, operation: str, payload: Dict[str, Any], 
                        result: Dict[str, Any]) -> bool:
        """Compensate for a completed Facebook operation (rollback side effects)."""
        try:
            if operation == "send_message":
                # For Facebook messages, we can't actually unsend, but we can log the compensation
                logger.info("Compensating Facebook message send", 
                           message_id=result.get("message_id"),
                           recipient_id=payload["recipient_id"])
                return True
            
            elif operation == "set_typing":
                # Turn off typing indicator as compensation
                if payload.get("action") == "typing_on":
                    await self.set_typing_indicator(
                        recipient_id=payload["recipient_id"],
                        action="typing_off"
                    )
                return True
            
            elif operation == "get_user_profile":
                # No side effects to compensate for read operations
                return True
            
            else:
                logger.warning(f"No compensation logic for operation: {operation}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to compensate operation {operation}: {e}")
            return False
