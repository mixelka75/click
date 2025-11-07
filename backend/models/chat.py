"""
Chat model for MongoDB.
Handles direct messaging between applicants and employers.
"""

from datetime import datetime
from typing import Optional, List
from beanie import Document, Link
from pydantic import BaseModel, Field
from .user import User
from .response import Response


class Message(BaseModel):
    """Single chat message."""
    sender_id: str  # User ID who sent the message
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    is_read: bool = Field(default=False)

    # Optional attachments
    photo_file_id: Optional[str] = None
    document_file_id: Optional[str] = None


class Chat(Document):
    """Chat conversation document model."""

    # Participants
    applicant: Link[User]  # Link to applicant user
    employer: Link[User]   # Link to employer user

    # Context
    response: Link[Response]  # Link to job application that started this chat

    # Messages
    messages: List[Message] = Field(default_factory=list)

    # Status
    is_active: bool = Field(default=True)
    is_archived_by_applicant: bool = Field(default=False)
    is_archived_by_employer: bool = Field(default=False)

    # Last activity
    last_message_at: datetime = Field(default_factory=datetime.utcnow)
    last_message_text: Optional[str] = None  # Preview of last message

    # Unread counts
    unread_count_applicant: int = Field(default=0)
    unread_count_employer: int = Field(default=0)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "chats"
        indexes = [
            "applicant",
            "employer",
            "response",
            "last_message_at",
            "is_active",
        ]

    def add_message(self, sender_id: str, text: str, photo_file_id: Optional[str] = None, document_file_id: Optional[str] = None):
        """Add a new message to the chat."""
        message = Message(
            sender_id=sender_id,
            text=text,
            photo_file_id=photo_file_id,
            document_file_id=document_file_id
        )
        self.messages.append(message)
        self.last_message_at = datetime.utcnow()
        self.last_message_text = text[:100]  # First 100 chars as preview
        self.updated_at = datetime.utcnow()

        # Increment unread counter for recipient
        if sender_id == str(self.applicant.ref.id):
            self.unread_count_employer += 1
        else:
            self.unread_count_applicant += 1

    def mark_as_read(self, user_id: str):
        """Mark all messages as read for a specific user."""
        # Mark messages from other user as read
        for message in self.messages:
            if message.sender_id != user_id and not message.is_read:
                message.is_read = True

        # Reset unread counter for this user
        if user_id == str(self.applicant.ref.id):
            self.unread_count_applicant = 0
        else:
            self.unread_count_employer = 0

        self.updated_at = datetime.utcnow()

    def get_other_participant(self, current_user_id: str) -> Link[User]:
        """Get the other participant in the chat."""
        if str(self.applicant.ref.id) == current_user_id:
            return self.employer
        else:
            return self.applicant

    def get_unread_count(self, user_id: str) -> int:
        """Get unread message count for a specific user."""
        if user_id == str(self.applicant.ref.id):
            return self.unread_count_applicant
        else:
            return self.unread_count_employer

    def is_archived_by(self, user_id: str) -> bool:
        """Check if chat is archived by a specific user."""
        if user_id == str(self.applicant.ref.id):
            return self.is_archived_by_applicant
        else:
            return self.is_archived_by_employer
