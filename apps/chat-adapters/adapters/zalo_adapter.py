"""Zalo Chat Adapter for Vietnamese Market."""

import asyncio
from typing import Dict, Any, Optional
import httpx
import structlog
from fastapi import APIRouter, Request, HTTPException, status

from ..core.unified_message import UnifiedMessage, UnifiedResponse, UserProfile, MessageContent, Channel, MessageType
from libs.resilience.tool_adapter_base import ResilientToolAdapter

logger = structlog.get_logger(__name__)


class ZaloChatAdapter(ResilientToolAdapter):
    """Zalo chat adapter for Vietnamese market integration."""
    
    def __init__(self, oa_id: str, secret_key: str, **kwargs):
        super().__init__(name="zalo_chat", **kwargs)
        self.oa_id = oa_id
        self.secret_key = secret_key
        self.api_url = "https://openapi.zalo.me/v2.0"
        self.router = APIRouter(prefix="/zalo", tags=["Zalo Chat"])
        self.setup_routes()
    
    def setup_routes(self):
        """Setup FastAPI routes for Zalo webhook."""
        
        @self.router.post("/webhook")
        async def handle_webhook(request: Request):
            """Handle incoming Zalo webhook events."""
            try:
                payload = await request.json()
                logger.info("Received Zalo webhook", payload=payload)
                
                # Process webhook events
                await self.process_webhook_events(payload)
                
                return {"status": "success"}
                
            except Exception as e:
                logger.error("Error processing Zalo webhook", error=str(e))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error processing webhook"
                )
    
    async def process_webhook_events(self, payload: Dict[str, Any]) -> None:
        """Process incoming webhook events from Zalo."""
        event_name = payload.get("event_name")
        
        if event_name == "user_send_text":
            await self.process_text_message(payload)
        elif event_name == "user_send_image":
            await self.process_image_message(payload)
        elif event_name == "user_send_sticker":
            await self.process_sticker_message(payload)
        elif event_name == "user_send_location":
            await self.process_location_message(payload)
        elif event_name == "user_send_contact":
            await self.process_contact_message(payload)
        else:
            logger.info("Unhandled Zalo event", event_name=event_name)
    
    async def process_text_message(self, payload: Dict[str, Any]) -> UnifiedMessage:
        """Process Zalo text message."""
        user_id = payload["user_id_by_app"]
        message = payload["message"]
        timestamp = payload.get("timestamp", 0)
        
        # Create user profile
        user_profile = UserProfile(
            user_id=user_id,
            platform_user_id=user_id,
            channel=Channel.ZALO,
            language="vi",  # Default to Vietnamese
            metadata={"zalo_user_id": user_id}
        )
        
        # Create message content
        content = MessageContent(text=message.get("text", ""))
        
        # Create unified message
        unified_message = UnifiedMessage(
            channel=Channel.ZALO,
            user_profile=user_profile,
            message_type=MessageType.TEXT,
            content=content,
            context={
                "zalo_message_id": message.get("msg_id"),
                "zalo_timestamp": timestamp,
                "original_payload": payload
            }
        )
        
        logger.info("Processed Zalo text message", 
                   message_id=unified_message.message_id,
                   user_id=user_id,
                   text=content.text[:100])
        
        return unified_message
    
    async def process_image_message(self, payload: Dict[str, Any]) -> UnifiedMessage:
        """Process Zalo image message."""
        user_id = payload["user_id_by_app"]
        message = payload["message"]
        timestamp = payload.get("timestamp", 0)
        
        # Create user profile
        user_profile = UserProfile(
            user_id=user_id,
            platform_user_id=user_id,
            channel=Channel.ZALO,
            language="vi"
        )
        
        # Create message content
        content = MessageContent(
            text=message.get("text", ""),
            media_url=message.get("attachments", [{}])[0].get("payload", {}).get("url"),
            media_type="image"
        )
        
        # Create unified message
        unified_message = UnifiedMessage(
            channel=Channel.ZALO,
            user_profile=user_profile,
            message_type=MessageType.IMAGE,
            content=content,
            context={
                "zalo_message_id": message.get("msg_id"),
                "zalo_timestamp": timestamp,
                "original_payload": payload
            }
        )
        
        logger.info("Processed Zalo image message", 
                   message_id=unified_message.message_id,
                   user_id=user_id,
                   media_url=content.media_url)
        
        return unified_message
    
    async def process_sticker_message(self, payload: Dict[str, Any]) -> UnifiedMessage:
        """Process Zalo sticker message."""
        user_id = payload["user_id_by_app"]
        message = payload["message"]
        timestamp = payload.get("timestamp", 0)
        
        # Create user profile
        user_profile = UserProfile(
            user_id=user_id,
            platform_user_id=user_id,
            channel=Channel.ZALO,
            language="vi"
        )
        
        # Create message content
        content = MessageContent(
            media_url=message.get("attachments", [{}])[0].get("payload", {}).get("url"),
            media_type="sticker"
        )
        
        # Create unified message
        unified_message = UnifiedMessage(
            channel=Channel.ZALO,
            user_profile=user_profile,
            message_type=MessageType.STICKER,
            content=content,
            context={
                "zalo_message_id": message.get("msg_id"),
                "zalo_timestamp": timestamp,
                "original_payload": payload
            }
        )
        
        logger.info("Processed Zalo sticker message", 
                   message_id=unified_message.message_id,
                   user_id=user_id)
        
        return unified_message
    
    async def process_location_message(self, payload: Dict[str, Any]) -> UnifiedMessage:
        """Process Zalo location message."""
        user_id = payload["user_id_by_app"]
        message = payload["message"]
        timestamp = payload.get("timestamp", 0)
        
        # Create user profile
        user_profile = UserProfile(
            user_id=user_id,
            platform_user_id=user_id,
            channel=Channel.ZALO,
            language="vi"
        )
        
        # Extract location data
        location_data = message.get("attachments", [{}])[0].get("payload", {})
        location = {
            "lat": location_data.get("coordinates", {}).get("lat"),
            "lng": location_data.get("coordinates", {}).get("long")
        }
        
        # Create message content
        content = MessageContent(
            text=message.get("text", ""),
            location=location
        )
        
        # Create unified message
        unified_message = UnifiedMessage(
            channel=Channel.ZALO,
            user_profile=user_profile,
            message_type=MessageType.LOCATION,
            content=content,
            context={
                "zalo_message_id": message.get("msg_id"),
                "zalo_timestamp": timestamp,
                "original_payload": payload
            }
        )
        
        logger.info("Processed Zalo location message", 
                   message_id=unified_message.message_id,
                   user_id=user_id,
                   location=location)
        
        return unified_message
    
    async def process_contact_message(self, payload: Dict[str, Any]) -> UnifiedMessage:
        """Process Zalo contact message."""
        user_id = payload["user_id_by_app"]
        message = payload["message"]
        timestamp = payload.get("timestamp", 0)
        
        # Create user profile
        user_profile = UserProfile(
            user_id=user_id,
            platform_user_id=user_id,
            channel=Channel.ZALO,
            language="vi"
        )
        
        # Extract contact data
        contact_data = message.get("attachments", [{}])[0].get("payload", {})
        contact = {
            "name": contact_data.get("name"),
            "phone": contact_data.get("phone"),
            "email": contact_data.get("email")
        }
        
        # Create message content
        content = MessageContent(
            text=message.get("text", ""),
            contact=contact
        )
        
        # Create unified message
        unified_message = UnifiedMessage(
            channel=Channel.ZALO,
            user_profile=user_profile,
            message_type=MessageType.CONTACT,
            content=content,
            context={
                "zalo_message_id": message.get("msg_id"),
                "zalo_timestamp": timestamp,
                "original_payload": payload
            }
        )
        
        logger.info("Processed Zalo contact message", 
                   message_id=unified_message.message_id,
                   user_id=user_id,
                   contact_name=contact.get("name"))
        
        return unified_message
    
    async def send_message(self, user_id: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send message via Zalo API."""
        url = f"{self.api_url}/oa/message"
        
        payload = {
            "recipient": {"user_id": user_id},
            "message": message
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                result = response.json()
                logger.info("Zalo message sent successfully", 
                           user_id=user_id,
                           message_id=result.get("message_id"))
                
                return result
                
        except httpx.HTTPError as e:
            logger.error("Failed to send Zalo message", 
                        user_id=user_id,
                        error=str(e))
            raise
    
    async def send_unified_response(self, response: UnifiedResponse) -> Dict[str, Any]:
        """Send unified response via Zalo."""
        # Convert unified response to Zalo format
        zalo_message = self._convert_to_zalo_format(response)
        
        return await self.send_message(response.recipient_id, zalo_message)
    
    def _convert_to_zalo_format(self, response: UnifiedResponse) -> Dict[str, Any]:
        """Convert unified response to Zalo format."""
        content = response.content
        
        if content.text and not content.buttons:
            # Simple text message
            return {"text": content.text}
        
        elif content.text and content.buttons:
            # Text with buttons (Zalo supports basic buttons)
            return {
                "text": content.text,
                "attachments": [
                    {
                        "type": "template",
                        "payload": {
                            "template_type": "button",
                            "text": content.text,
                            "buttons": [
                                {
                                    "type": "web_url",
                                    "title": button.get("title", "Button"),
                                    "url": button.get("url", "#")
                                }
                                for button in content.buttons[:3]  # Zalo limits buttons
                            ]
                        }
                    }
                ]
            }
        
        elif content.media_url:
            # Media message
            return {
                "attachments": [
                    {
                        "type": content.media_type or "image",
                        "payload": {
                            "url": content.media_url
                        }
                    }
                ]
            }
        
        else:
            # Fallback to text
            return {"text": content.text or "Tin nhắn đã được gửi"}
    
    async def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get Zalo user profile information."""
        url = f"{self.api_url}/oa/getprofile"
        params = {
            "data": user_id
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error("Failed to get Zalo user profile", 
                        user_id=user_id,
                        error=str(e))
            return {}
    
    async def send_sticker(self, user_id: str, sticker_id: str) -> Dict[str, Any]:
        """Send Zalo sticker."""
        message = {
            "attachments": [
                {
                    "type": "sticker",
                    "payload": {
                        "sticker_id": sticker_id
                    }
                }
            ]
        }
        
        return await self.send_message(user_id, message)
    
    async def execute_operation(self, operation: str, payload: Dict[str, Any], 
                              headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Execute the actual Zalo API operation."""
        if operation == "send_message":
            return await self.send_message(
                user_id=payload["user_id"],
                message_text=payload["message_text"]
            )
        elif operation == "send_location":
            return await self.send_location(
                user_id=payload["user_id"],
                latitude=payload["latitude"],
                longitude=payload["longitude"],
                name=payload.get("name", "Location"),
                address=payload.get("address", "")
            )
        elif operation == "get_user_profile":
            return await self.get_user_profile(payload["user_id"])
        elif operation == "send_quick_reply":
            return await self.send_quick_reply(
                user_id=payload["user_id"],
                message_text=payload["message_text"],
                quick_replies=payload["quick_replies"]
            )
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def compensate(self, operation: str, payload: Dict[str, Any], 
                        result: Dict[str, Any]) -> bool:
        """Compensate for a completed Zalo operation (rollback side effects)."""
        try:
            if operation == "send_message":
                # For Zalo messages, we can't actually unsend, but we can log the compensation
                logger.info("Compensating Zalo message send", 
                           message_id=result.get("message_id"),
                           user_id=payload["user_id"])
                return True
            
            elif operation == "send_location":
                # For location sharing, we can send a "location shared" cancellation message
                logger.info("Compensating Zalo location send", 
                           user_id=payload["user_id"])
                return True
            
            elif operation == "send_quick_reply":
                # For quick replies, we can send a message indicating the action was cancelled
                logger.info("Compensating Zalo quick reply", 
                           user_id=payload["user_id"])
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
    
    async def send_location(self, user_id: str, latitude: float, longitude: float, 
                           name: str = "", address: str = "") -> Dict[str, Any]:
        """Send location via Zalo."""
        message = {
            "attachments": [
                {
                    "type": "location",
                    "payload": {
                        "coordinates": {
                            "lat": latitude,
                            "long": longitude
                        },
                        "title": name,
                        "address": address
                    }
                }
            ]
        }
        
        return await self.send_message(user_id, message)
    
    async def execute_operation(self, operation: str, payload: Dict[str, Any], 
                              headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Execute the actual Zalo API operation."""
        if operation == "send_message":
            return await self.send_message(
                user_id=payload["user_id"],
                message_text=payload["message_text"]
            )
        elif operation == "send_location":
            return await self.send_location(
                user_id=payload["user_id"],
                latitude=payload["latitude"],
                longitude=payload["longitude"],
                name=payload.get("name", "Location"),
                address=payload.get("address", "")
            )
        elif operation == "get_user_profile":
            return await self.get_user_profile(payload["user_id"])
        elif operation == "send_quick_reply":
            return await self.send_quick_reply(
                user_id=payload["user_id"],
                message_text=payload["message_text"],
                quick_replies=payload["quick_replies"]
            )
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def compensate(self, operation: str, payload: Dict[str, Any], 
                        result: Dict[str, Any]) -> bool:
        """Compensate for a completed Zalo operation (rollback side effects)."""
        try:
            if operation == "send_message":
                # For Zalo messages, we can't actually unsend, but we can log the compensation
                logger.info("Compensating Zalo message send", 
                           message_id=result.get("message_id"),
                           user_id=payload["user_id"])
                return True
            
            elif operation == "send_location":
                # For location sharing, we can send a "location shared" cancellation message
                logger.info("Compensating Zalo location send", 
                           user_id=payload["user_id"])
                return True
            
            elif operation == "send_quick_reply":
                # For quick replies, we can send a message indicating the action was cancelled
                logger.info("Compensating Zalo quick reply", 
                           user_id=payload["user_id"])
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
