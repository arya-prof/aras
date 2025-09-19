"""
Communication tools for messaging, email, and notifications.
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Dict, List, Optional

from .base import AsyncTool
from ..models import ToolCategory
from ..config import settings


class EmailTool(AsyncTool):
    """Tool for sending emails."""
    
    def __init__(self):
        super().__init__(
            name="email_sender",
            category=ToolCategory.COMMUNICATION,
            description="Send emails via SMTP"
        )
        self.smtp_server = settings.smtp_server
        self.smtp_port = settings.smtp_port
        self.email_username = settings.email_username
        self.email_password = settings.email_password
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute email operation."""
        operation = parameters.get("operation")
        
        if operation == "send_email":
            return await self._send_email(
                to_email=parameters.get("to_email"),
                subject=parameters.get("subject"),
                body=parameters.get("body"),
                is_html=parameters.get("is_html", False)
            )
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _send_email(self, to_email: str, subject: str, body: str, is_html: bool = False) -> Dict[str, Any]:
        """Send an email."""
        if not all([self.smtp_server, self.email_username, self.email_password]):
            raise RuntimeError("Email configuration not complete")
        
        if not to_email or not subject or not body:
            raise ValueError("to_email, subject, and body are required")
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = self.email_username
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Add body
        if is_html:
            msg.attach(MIMEText(body, 'html'))
        else:
            msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.email_username, self.email_password)
                server.send_message(msg)
            
            return {
                "success": True,
                "to": to_email,
                "subject": subject,
                "message": "Email sent successfully"
            }
        except Exception as e:
            raise RuntimeError(f"Failed to send email: {e}")
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["send_email"],
                    "description": "Email operation"
                },
                "to_email": {
                    "type": "string",
                    "format": "email",
                    "description": "Recipient email address"
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject"
                },
                "body": {
                    "type": "string",
                    "description": "Email body"
                },
                "is_html": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether body is HTML"
                }
            },
            "required": ["operation", "to_email", "subject", "body"]
        }


class NotificationTool(AsyncTool):
    """Tool for sending notifications."""
    
    def __init__(self):
        super().__init__(
            name="notification_sender",
            category=ToolCategory.COMMUNICATION,
            description="Send notifications via various channels"
        )
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute notification operation."""
        operation = parameters.get("operation")
        
        if operation == "send_notification":
            return await self._send_notification(
                title=parameters.get("title"),
                message=parameters.get("message"),
                notification_type=parameters.get("notification_type", "info")
            )
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _send_notification(self, title: str, message: str, notification_type: str = "info") -> Dict[str, Any]:
        """Send a notification."""
        if not title or not message:
            raise ValueError("Title and message are required")
        
        # This is a placeholder implementation
        # In a real implementation, you'd integrate with notification services
        # like Windows notifications, push services, etc.
        
        return {
            "success": True,
            "title": title,
            "message": message,
            "type": notification_type,
            "message": "Notification sent (placeholder)"
        }
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["send_notification"],
                    "description": "Notification operation"
                },
                "title": {
                    "type": "string",
                    "description": "Notification title"
                },
                "message": {
                    "type": "string",
                    "description": "Notification message"
                },
                "notification_type": {
                    "type": "string",
                    "enum": ["info", "warning", "error", "success"],
                    "default": "info",
                    "description": "Notification type"
                }
            },
            "required": ["operation", "title", "message"]
        }
