"""
Publication model - tracks posts to Telegram channels.
"""

from datetime import datetime
from typing import Optional, Union
from enum import Enum
from beanie import Document, Link
from pydantic import Field
from .resume import Resume
from .vacancy import Vacancy


class PublicationType(str, Enum):
    """Type of publication."""
    RESUME = "resume"
    VACANCY = "vacancy"


class Publication(Document):
    """Publication tracking model."""

    # Type and content
    publication_type: PublicationType
    resume: Optional[Link[Resume]] = None
    vacancy: Optional[Link[Vacancy]] = None

    # Channel information
    channel_id: str  # @channel_name or chat_id
    channel_name: str

    # Telegram message details
    message_id: Optional[int] = None
    message_text: str
    message_url: Optional[str] = None

    # Status
    is_published: bool = Field(default=False)
    is_deleted: bool = Field(default=False)

    # Analytics
    views_count: int = Field(default=0)
    clicks_count: int = Field(default=0)  # Клики на кнопку "Откликнуться"

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    # Error tracking
    error_message: Optional[str] = None

    class Settings:
        name = "publications"
        indexes = [
            "publication_type",
            "resume",
            "vacancy",
            "channel_id",
            "created_at",
            "is_published",
        ]

    class Config:
        json_schema_extra = {
            "example": {
                "publication_type": "vacancy",
                "channel_id": "@horeca_msk1",
                "channel_name": "HoReCa Москва - Бармены",
                "message_text": "🍸 Вакансия: Бармен...",
                "is_published": True,
            }
        }


class Analytics(Document):
    """Analytics and statistics model."""

    # Entity reference
    entity_type: str  # "vacancy" or "resume"
    entity_id: str

    # Daily stats
    date: datetime
    views: int = Field(default=0)
    responses: int = Field(default=0)
    clicks: int = Field(default=0)

    # Conversion metrics
    conversion_rate: float = Field(default=0.0)  # responses/views

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "analytics"
        indexes = [
            "entity_type",
            "entity_id",
            "date",
        ]
