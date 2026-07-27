"""
Pydantic models for core domain objects: User, Message, Media, Settings, Statistics.
These models are intentionally simple and validation-focused; they are not ORM models.
They are used for data interchange between modules (backup/restore, handlers, sender).
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .constants import Mode


class UserModel(BaseModel):
    id: int = Field(..., description="Local DB user id")
    telegram_id: Optional[int] = Field(None, description="Telegram user id if known")
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_bot: Optional[bool] = False


class MediaModel(BaseModel):
    file_id: str
    file_unique_id: Optional[str] = None
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None


class MessageModel(BaseModel):
    id: int = Field(..., description="Local DB message id")
    telegram_message_id: Optional[int] = Field(None, description="Telegram message id if available")
    chat_id: Optional[int] = None
    user_id: Optional[int] = None
    text: Optional[str] = None
    message_type: Optional[str] = None
    date: datetime = Field(default_factory=datetime.utcnow)
    reply_to_id: Optional[int] = Field(None, description="Local DB id of the message this replies to")
    media: Optional[List[MediaModel]] = None
    entities: Optional[List[dict]] = None  # raw Telegram entity dicts


class SettingsModel(BaseModel):
    mode: Mode = Mode.PARAGRAPH
    shrink: bool = False


class StatisticsModel(BaseModel):
    total_messages: int = 0
    unique_users: int = 0
    active_users_7d: int = 0
    active_users_30d: int = 0


__all__ = [
    "UserModel",
    "MediaModel",
    "MessageModel",
    "SettingsModel",
    "StatisticsModel",
]
