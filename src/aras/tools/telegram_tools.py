"""
Telegram tools for messaging, chat management, and other Telegram operations using Telethon.
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import json

from telethon import TelegramClient, events
from telethon.tl.types import (
    User, Chat, Channel, Message, 
    InputPeerUser, InputPeerChat, InputPeerChannel,
    MessageMediaPhoto, MessageMediaDocument, MessageMediaWebPage,
    ChatBannedRights
)
from telethon.tl.functions.channels import CreateChannelRequest, InviteToChannelRequest, EditBannedRequest
from telethon.errors import (
    SessionPasswordNeededError, PhoneCodeInvalidError,
    FloodWaitError, ChatAdminRequiredError, UserNotParticipantError,
    ChannelPrivateError, UserBannedInChannelError
)

from .base import AsyncTool
from ..models import ToolCategory
from ..config import settings

logger = logging.getLogger(__name__)


class TelegramTool(AsyncTool):
    """Tool for Telegram operations using Telethon."""
    
    def __init__(self):
        super().__init__(
            name="telegram_manager",
            category=ToolCategory.COMMUNICATION,
            description="Send messages, manage chats, and perform Telegram operations"
        )
        self.requires_auth = True
        self.client = None
        self.session_file = None
        self.api_id = getattr(settings, 'telegram_api_id', None)
        self.api_hash = getattr(settings, 'telegram_api_hash', None)
        self.phone_number = getattr(settings, 'telegram_phone', None)
        self.session_name = "aras_telegram_session"
    
    async def _setup_resources(self):
        """Setup Telegram client and session."""
        if not all([self.api_id, self.api_hash]):
            raise RuntimeError("Telegram API credentials not configured")
        
        # Create session file path
        session_dir = Path(self.get_temp_dir()) / "telegram_sessions"
        session_dir.mkdir(exist_ok=True)
        self.session_file = str(session_dir / f"{self.session_name}.session")
        
        # Initialize client
        self.client = TelegramClient(
            self.session_file,
            self.api_id,
            self.api_hash
        )
        
        # Add client to resources for cleanup
        self.add_resource(self.client)
        
        # Start client
        await self.client.start(phone=self.phone_number)
        
        logger.info("Telegram client initialized successfully")
    
    async def _cleanup_resources(self):
        """Cleanup Telegram client."""
        if self.client:
            try:
                await self.client.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting Telegram client: {e}")
            self.client = None
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute Telegram operation."""
        operation = parameters.get("operation")
        
        try:
            if operation == "send_message":
                return await self._send_message(
                    chat_id=parameters.get("chat_id"),
                    message=parameters.get("message"),
                    parse_mode=parameters.get("parse_mode", "html"),
                    reply_to=parameters.get("reply_to"),
                    file_path=parameters.get("file_path")
                )
            elif operation == "get_chats":
                return await self._get_chats(
                    limit=parameters.get("limit", 20),
                    chat_type=parameters.get("chat_type", "all")
                )
            elif operation == "get_chat_info":
                return await self._get_chat_info(
                    chat_id=parameters.get("chat_id")
                )
            elif operation == "get_messages":
                return await self._get_messages(
                    chat_id=parameters.get("chat_id"),
                    limit=parameters.get("limit", 20),
                    offset_id=parameters.get("offset_id", 0)
                )
            elif operation == "search_messages":
                return await self._search_messages(
                    chat_id=parameters.get("chat_id"),
                    query=parameters.get("query"),
                    limit=parameters.get("limit", 20)
                )
            elif operation == "create_group":
                return await self._create_group(
                    title=parameters.get("title"),
                    users=parameters.get("users", [])
                )
            elif operation == "add_users_to_group":
                return await self._add_users_to_group(
                    group_id=parameters.get("group_id"),
                    users=parameters.get("users", [])
                )
            elif operation == "remove_users_from_group":
                return await self._remove_users_from_group(
                    group_id=parameters.get("group_id"),
                    users=parameters.get("users", [])
                )
            elif operation == "get_me":
                return await self._get_me()
            elif operation == "forward_message":
                return await self._forward_message(
                    chat_id=parameters.get("chat_id"),
                    from_chat_id=parameters.get("from_chat_id"),
                    message_id=parameters.get("message_id")
                )
            elif operation == "delete_message":
                return await self._delete_message(
                    chat_id=parameters.get("chat_id"),
                    message_id=parameters.get("message_id")
                )
            elif operation == "edit_message":
                return await self._edit_message(
                    chat_id=parameters.get("chat_id"),
                    message_id=parameters.get("message_id"),
                    new_text=parameters.get("new_text"),
                    parse_mode=parameters.get("parse_mode", "html")
                )
            else:
                raise ValueError(f"Unknown operation: {operation}")
        
        except FloodWaitError as e:
            raise RuntimeError(f"Rate limited. Please wait {e.seconds} seconds before retrying.")
        except (ChatAdminRequiredError, UserNotParticipantError, 
                ChannelPrivateError, UserBannedInChannelError) as e:
            raise RuntimeError(f"Permission denied: {e}")
        except Exception as e:
            logger.error(f"Telegram operation failed: {e}")
            raise RuntimeError(f"Telegram operation failed: {e}")
    
    async def _send_message(self, chat_id: Union[str, int], message: str, 
                           parse_mode: str = "html", reply_to: Optional[int] = None,
                           file_path: Optional[str] = None) -> Dict[str, Any]:
        """Send a message to a chat."""
        if not message and not file_path:
            raise ValueError("Message text or file_path is required")
        
        # Parse chat_id
        entity = await self._get_entity(chat_id)
        
        # Prepare message parameters
        kwargs = {
            "entity": entity,
            "message": message or "",
            "parse_mode": parse_mode if parse_mode != "none" else None
        }
        
        if reply_to:
            kwargs["reply_to"] = reply_to
        
        if file_path:
            kwargs["file"] = file_path
        
        # Send message
        sent_message = await self.client.send_message(**kwargs)
        
        return {
            "success": True,
            "message_id": sent_message.id,
            "chat_id": chat_id,
            "text": message,
            "date": sent_message.date.isoformat(),
            "from_user": {
                "id": sent_message.from_id.user_id if sent_message.from_id else None,
                "username": getattr(sent_message.from_id, 'username', None) if sent_message.from_id else None
            } if sent_message.from_id else None
        }
    
    async def _get_chats(self, limit: int = 20, chat_type: str = "all") -> Dict[str, Any]:
        """Get list of chats."""
        chats = []
        
        async for dialog in self.client.iter_dialogs(limit=limit):
            chat_info = {
                "id": dialog.id,
                "name": dialog.name,
                "type": self._get_chat_type(dialog.entity),
                "username": getattr(dialog.entity, 'username', None),
                "unread_count": dialog.unread_count,
                "is_pinned": dialog.is_pinned,
                "is_archived": dialog.is_archived
            }
            
            # Filter by chat type if specified
            if chat_type == "all" or chat_info["type"] == chat_type:
                chats.append(chat_info)
        
        return {
            "success": True,
            "chats": chats,
            "total": len(chats)
        }
    
    async def _get_chat_info(self, chat_id: Union[str, int]) -> Dict[str, Any]:
        """Get detailed information about a chat."""
        entity = await self._get_entity(chat_id)
        
        # Get full entity info
        full_entity = await self.client.get_entity(entity)
        
        info = {
            "id": full_entity.id,
            "type": self._get_chat_type(full_entity),
            "title": getattr(full_entity, 'title', None) or getattr(full_entity, 'first_name', ''),
            "username": getattr(full_entity, 'username', None),
            "description": getattr(full_entity, 'about', None),
            "participants_count": getattr(full_entity, 'participants_count', None),
            "is_verified": getattr(full_entity, 'verified', False),
            "is_scam": getattr(full_entity, 'scam', False),
            "is_fake": getattr(full_entity, 'fake', False),
            "is_restricted": getattr(full_entity, 'restricted', False),
            "is_creator": getattr(full_entity, 'creator', False),
            "is_admin": getattr(full_entity, 'admin_rights', None) is not None
        }
        
        return {
            "success": True,
            "chat_info": info
        }
    
    async def _get_messages(self, chat_id: Union[str, int], limit: int = 20, 
                           offset_id: int = 0) -> Dict[str, Any]:
        """Get messages from a chat."""
        entity = await self._get_entity(chat_id)
        
        messages = []
        async for message in self.client.iter_messages(
            entity, limit=limit, offset_id=offset_id
        ):
            msg_data = {
                "id": message.id,
                "text": message.text or "",
                "date": message.date.isoformat(),
                "from_user": {
                    "id": message.from_id.user_id if message.from_id else None,
                    "username": getattr(message.from_id, 'username', None) if message.from_id else None
                } if message.from_id else None,
                "reply_to": message.reply_to_msg_id,
                "media_type": self._get_media_type(message.media),
                "is_forwarded": message.fwd_from is not None,
                "views": getattr(message, 'views', None),
                "forwards": getattr(message, 'forwards', None)
            }
            messages.append(msg_data)
        
        return {
            "success": True,
            "messages": messages,
            "total": len(messages)
        }
    
    async def _search_messages(self, chat_id: Union[str, int], query: str, 
                              limit: int = 20) -> Dict[str, Any]:
        """Search messages in a chat."""
        if not query:
            raise ValueError("Search query is required")
        
        entity = await self._get_entity(chat_id)
        
        messages = []
        async for message in self.client.iter_messages(
            entity, search=query, limit=limit
        ):
            msg_data = {
                "id": message.id,
                "text": message.text or "",
                "date": message.date.isoformat(),
                "from_user": {
                    "id": message.from_id.user_id if message.from_id else None,
                    "username": getattr(message.from_id, 'username', None) if message.from_id else None
                } if message.from_id else None
            }
            messages.append(msg_data)
        
        return {
            "success": True,
            "query": query,
            "messages": messages,
            "total": len(messages)
        }
    
    async def _create_group(self, title: str, users: List[Union[str, int]]) -> Dict[str, Any]:
        """Create a new group."""
        if not title:
            raise ValueError("Group title is required")
        
        # Create group
        group = await self.client(CreateChannelRequest(
            title=title,
            about="",
            megagroup=True
        ))
        
        # Add users if provided
        if users:
            await self._add_users_to_group(group.id, users)
        
        return {
            "success": True,
            "group_id": group.id,
            "title": title,
            "invite_link": f"https://t.me/{group.username}" if group.username else None
        }
    
    async def _add_users_to_group(self, group_id: Union[str, int], 
                                 users: List[Union[str, int]]) -> Dict[str, Any]:
        """Add users to a group."""
        entity = await self._get_entity(group_id)
        
        added_users = []
        for user in users:
            try:
                user_entity = await self._get_entity(user)
                await self.client(InviteToChannelRequest(entity, [user_entity]))
                added_users.append(str(user))
            except Exception as e:
                logger.warning(f"Failed to add user {user}: {e}")
        
        return {
            "success": True,
            "group_id": group_id,
            "added_users": added_users,
            "total_added": len(added_users)
        }
    
    async def _remove_users_from_group(self, group_id: Union[str, int], 
                                      users: List[Union[str, int]]) -> Dict[str, Any]:
        """Remove users from a group."""
        entity = await self._get_entity(group_id)
        
        removed_users = []
        for user in users:
            try:
                user_entity = await self._get_entity(user)
                await self.client(EditBannedRequest(entity, user_entity, ChatBannedRights(until_date=None, view_messages=True)))
                removed_users.append(str(user))
            except Exception as e:
                logger.warning(f"Failed to remove user {user}: {e}")
        
        return {
            "success": True,
            "group_id": group_id,
            "removed_users": removed_users,
            "total_removed": len(removed_users)
        }
    
    async def _get_me(self) -> Dict[str, Any]:
        """Get current user information."""
        me = await self.client.get_me()
        
        return {
            "success": True,
            "user": {
                "id": me.id,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "username": me.username,
                "phone": me.phone,
                "is_bot": me.bot,
                "is_verified": me.verified,
                "is_premium": getattr(me, 'premium', False)
            }
        }
    
    async def _forward_message(self, chat_id: Union[str, int], 
                              from_chat_id: Union[str, int], 
                              message_id: int) -> Dict[str, Any]:
        """Forward a message to another chat."""
        to_entity = await self._get_entity(chat_id)
        from_entity = await self._get_entity(from_chat_id)
        
        forwarded = await self.client.forward_messages(
            to_entity, message_id, from_entity
        )
        
        return {
            "success": True,
            "forwarded_message_id": forwarded[0].id,
            "to_chat_id": chat_id,
            "from_chat_id": from_chat_id,
            "original_message_id": message_id
        }
    
    async def _delete_message(self, chat_id: Union[str, int], 
                             message_id: int) -> Dict[str, Any]:
        """Delete a message."""
        entity = await self._get_entity(chat_id)
        
        await self.client.delete_messages(entity, message_id)
        
        return {
            "success": True,
            "deleted_message_id": message_id,
            "chat_id": chat_id
        }
    
    async def _edit_message(self, chat_id: Union[str, int], message_id: int, 
                           new_text: str, parse_mode: str = "html") -> Dict[str, Any]:
        """Edit a message."""
        if not new_text:
            raise ValueError("New text is required")
        
        entity = await self._get_entity(chat_id)
        
        edited = await self.client.edit_message(
            entity, message_id, new_text, parse_mode=parse_mode if parse_mode != "none" else None
        )
        
        return {
            "success": True,
            "edited_message_id": edited.id,
            "chat_id": chat_id,
            "new_text": new_text
        }
    
    async def _get_entity(self, chat_id: Union[str, int]):
        """Get Telegram entity from chat_id."""
        if isinstance(chat_id, int):
            return chat_id
        
        # Try to get entity by username or phone
        try:
            return await self.client.get_entity(chat_id)
        except ValueError:
            # If it's a numeric string, try as integer
            try:
                return int(chat_id)
            except ValueError:
                raise ValueError(f"Invalid chat_id: {chat_id}")
    
    def _get_chat_type(self, entity) -> str:
        """Get chat type from entity."""
        if isinstance(entity, User):
            return "private"
        elif isinstance(entity, Chat):
            return "group"
        elif isinstance(entity, Channel):
            return "supergroup" if entity.megagroup else "channel"
        else:
            return "unknown"
    
    def _get_media_type(self, media) -> Optional[str]:
        """Get media type from message media."""
        if isinstance(media, MessageMediaPhoto):
            return "photo"
        elif isinstance(media, MessageMediaDocument):
            return "document"
        elif isinstance(media, MessageMediaWebPage):
            return "webpage"
        else:
            return None
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": [
                        "send_message", "get_chats", "get_chat_info", 
                        "get_messages", "search_messages", "create_group",
                        "add_users_to_group", "remove_users_from_group",
                        "get_me", "forward_message", "delete_message", "edit_message"
                    ],
                    "description": "Telegram operation to perform"
                },
                "chat_id": {
                    "type": "string",
                    "description": "Chat ID (username, phone, or numeric ID)"
                },
                "message": {
                    "type": "string",
                    "description": "Message text to send"
                },
                "parse_mode": {
                    "type": "string",
                    "enum": ["html", "markdown", "none"],
                    "default": "html",
                    "description": "Message parsing mode"
                },
                "reply_to": {
                    "type": "integer",
                    "description": "Message ID to reply to"
                },
                "file_path": {
                    "type": "string",
                    "description": "Path to file to send"
                },
                "limit": {
                    "type": "integer",
                    "default": 20,
                    "description": "Number of items to retrieve"
                },
                "chat_type": {
                    "type": "string",
                    "enum": ["all", "private", "group", "supergroup", "channel"],
                    "default": "all",
                    "description": "Type of chats to retrieve"
                },
                "offset_id": {
                    "type": "integer",
                    "default": 0,
                    "description": "Offset for message pagination"
                },
                "query": {
                    "type": "string",
                    "description": "Search query for messages"
                },
                "title": {
                    "type": "string",
                    "description": "Group title"
                },
                "users": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of user IDs or usernames"
                },
                "group_id": {
                    "type": "string",
                    "description": "Group ID for user management"
                },
                "from_chat_id": {
                    "type": "string",
                    "description": "Source chat ID for forwarding"
                },
                "message_id": {
                    "type": "integer",
                    "description": "Message ID"
                },
                "new_text": {
                    "type": "string",
                    "description": "New text for message editing"
                }
            },
            "required": ["operation"]
        }
