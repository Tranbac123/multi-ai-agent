import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Optional
from ..models import NotificationRequest, NotificationType
from ..settings import settings

class EmailChannel:
    def __init__(self):
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        self.smtp_use_tls = settings.smtp_use_tls
        self.from_email = settings.from_email
    
    async def send(self, request: NotificationRequest) -> Dict[str, Any]:
        """Send email notification"""
        if not self.smtp_host:
            return {
                "success": False,
                "error": "SMTP not configured",
                "sent_to": [],
                "failed_recipients": request.recipients
            }
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = ', '.join(request.recipients)
            msg['Subject'] = request.subject or "Notification"
            
            # Add body
            body = request.message
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            sent_to = []
            failed_recipients = []
            
            # Use asyncio to run SMTP in thread pool
            def send_email():
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    if self.smtp_use_tls:
                        server.starttls()
                    if self.smtp_username and self.smtp_password:
                        server.login(self.smtp_username, self.smtp_password)
                    server.send_message(msg)
            
            await asyncio.get_event_loop().run_in_executor(None, send_email)
            sent_to = request.recipients
            
            return {
                "success": True,
                "sent_to": sent_to,
                "failed_recipients": failed_recipients
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "sent_to": [],
                "failed_recipients": request.recipients
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check email channel health"""
        if not self.smtp_host:
            return {
                "status": "not_configured",
                "error": "SMTP host not set"
            }
        
        try:
            def test_connection():
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    if self.smtp_use_tls:
                        server.starttls()
                    return True
            
            await asyncio.get_event_loop().run_in_executor(None, test_connection)
            return {"status": "healthy"}
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

