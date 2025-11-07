"""
Favorite model for MongoDB.
Allows users to save vacancies and resumes to favorites.
"""

from datetime import datetime
from beanie import Document, Link
from pydantic import Field
from .user import User


class Favorite(Document):
    """Favorite document model."""

    # Owner
    user: Link[User]

    # What is being favorited
    entity_id: str  # ID of vacancy or resume
    entity_type: str  # "vacancy" or "resume"

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "favorites"
        indexes = [
            "user",
            "entity_id",
            "entity_type",
            [("user", 1), ("entity_id", 1), ("entity_type", 1)],  # Compound unique index
        ]

    class Config:
        json_schema_extra = {
            "example": {
                "entity_id": "507f1f77bcf86cd799439011",
                "entity_type": "vacancy",
            }
        }
