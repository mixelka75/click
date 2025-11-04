"""
User model for MongoDB using Beanie ODM.
"""

from datetime import datetime
from typing import Optional, List
from beanie import Document, Indexed
from pydantic import Field, EmailStr
from shared.constants import UserRole


class User(Document):
    """User document model."""

    # Telegram data
    telegram_id: Indexed(int, unique=True)  # type: ignore
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    # Role
    role: UserRole = Field(default=UserRole.APPLICANT)

    # Contact information
    phone: Optional[str] = None
    email: Optional[EmailStr] = None

    # Settings
    language_code: str = Field(default="ru")
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)

    # For employers
    company_name: Optional[str] = None
    company_description: Optional[str] = None
    company_type: Optional[str] = None
    company_website: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "users"
        indexes = [
            "telegram_id",
            "role",
            "created_at",
        ]

    class Config:
        json_schema_extra = {
            "example": {
                "telegram_id": 123456789,
                "username": "john_doe",
                "first_name": "John",
                "last_name": "Doe",
                "role": "applicant",
                "phone": "+79001234567",
                "email": "john@example.com",
            }
        }


class Manager(Document):
    """Manager with API access."""

    # Basic info
    telegram_id: Indexed(int)  # type: ignore
    name: str
    email: EmailStr

    # API credentials
    api_key: Indexed(str, unique=True)  # type: ignore
    api_secret: str

    # Permissions
    is_active: bool = Field(default=True)
    allowed_operations: List[str] = Field(default_factory=list)

    # Google Sheets integration
    google_sheet_id: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_api_call: Optional[datetime] = None

    class Settings:
        name = "managers"
        indexes = [
            "telegram_id",
            "api_key",
        ]
