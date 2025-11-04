"""
Response (отклик) model - connection between resume and vacancy.
"""

from datetime import datetime
from typing import Optional
from beanie import Document, Link
from pydantic import Field
from shared.constants import ResponseStatus
from .user import User
from .resume import Resume
from .vacancy import Vacancy


class Response(Document):
    """Response document model - applicant's response to vacancy or employer's invitation."""

    # Main entities
    applicant: Link[User]  # Соискатель
    employer: Link[User]   # Работодатель
    resume: Link[Resume]
    vacancy: Link[Vacancy]

    # Status
    status: ResponseStatus = Field(default=ResponseStatus.PENDING)

    # Type
    is_invitation: bool = Field(default=False)  # True если приглашение от работодателя

    # Cover letter / message
    message: Optional[str] = None

    # Interview details (if invited)
    interview_date: Optional[datetime] = None
    interview_location: Optional[str] = None
    interview_notes: Optional[str] = None

    # Rejection reason
    rejection_reason: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    viewed_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None

    class Settings:
        name = "responses"
        indexes = [
            "applicant",
            "employer",
            "resume",
            "vacancy",
            "status",
            "created_at",
        ]

    class Config:
        json_schema_extra = {
            "example": {
                "status": "pending",
                "is_invitation": False,
                "message": "Здравствуйте! Хочу откликнуться на вакансию бармена.",
            }
        }
