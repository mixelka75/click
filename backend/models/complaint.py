"""
Complaint model - жалобы на вакансии и резюме.
"""

from datetime import datetime
from typing import Optional
from beanie import Document, Link, PydanticObjectId
from pydantic import Field

from shared.constants import ComplaintType, ComplaintStatus, ModerationAction
from .user import User


class Complaint(Document):
    """Complaint document model - жалоба на вакансию или резюме."""

    # Кто жалуется
    reporter: Link[User]

    # На что жалоба
    target_type: ComplaintType  # vacancy или resume
    target_id: PydanticObjectId  # ID вакансии или резюме

    # Автор контента (для быстрого доступа)
    target_author: Link[User]

    # Причина жалобы (код из COMPLAINT_REASONS)
    reason_code: str

    # Дополнительный комментарий от жалобщика
    comment: Optional[str] = None

    # Статус
    status: ComplaintStatus = Field(default=ComplaintStatus.PENDING)

    # Модерация
    moderator_id: Optional[PydanticObjectId] = None  # Кто рассмотрел
    moderation_action: Optional[ModerationAction] = None  # Какое действие
    moderation_comment: Optional[str] = None  # Комментарий модератора
    moderated_at: Optional[datetime] = None

    # ID сообщения в модерационной группе (для обновления)
    moderation_message_id: Optional[int] = None
    moderation_chat_id: Optional[int] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "complaints"
        indexes = [
            "reporter",
            "target_type",
            "target_id",
            "target_author",
            "status",
            "created_at",
        ]

    class Config:
        json_schema_extra = {
            "example": {
                "target_type": "vacancy",
                "reason_code": "false_info",
                "comment": "Зарплата указана неверно",
                "status": "pending",
            }
        }


class ReporterBan(Document):
    """Ban record for spam reporters."""

    user: Link[User]

    # Причина бана
    reason: str = "Слишком много отклонённых жалоб"

    # До какого времени бан (None = навсегда)
    banned_until: Optional[datetime] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "reporter_bans"
        indexes = ["user", "banned_until"]

    @property
    def is_active(self) -> bool:
        """Check if ban is still active."""
        if self.banned_until is None:
            return True  # Permanent ban
        return datetime.utcnow() < self.banned_until


class ComplaintStats(Document):
    """Statistics per target (vacancy/resume) for auto-moderation."""

    target_type: ComplaintType
    target_id: PydanticObjectId

    # Счётчики
    total_complaints: int = 0
    pending_complaints: int = 0
    resolved_complaints: int = 0
    dismissed_complaints: int = 0

    # Автомодерация
    is_auto_hidden: bool = False  # Скрыто автоматически при 5+ жалобах
    auto_hidden_at: Optional[datetime] = None

    # Отправлено на модерацию
    sent_to_moderation: bool = False
    sent_to_moderation_at: Optional[datetime] = None

    class Settings:
        name = "complaint_stats"
        indexes = [
            [("target_type", 1), ("target_id", 1)],  # Compound index
            "is_auto_hidden",
        ]

    @classmethod
    async def get_or_create(
        cls,
        target_type: ComplaintType,
        target_id: PydanticObjectId
    ) -> "ComplaintStats":
        """Get existing stats or create new."""
        stats = await cls.find_one(
            cls.target_type == target_type,
            cls.target_id == target_id
        )
        if not stats:
            stats = cls(target_type=target_type, target_id=target_id)
            await stats.insert()
        return stats

    async def increment(self) -> None:
        """Increment complaint count and check thresholds."""
        from shared.constants import (
            COMPLAINTS_FOR_AUTO_MODERATION,
            COMPLAINTS_FOR_AUTO_HIDE
        )

        self.total_complaints += 1
        self.pending_complaints += 1
        await self.save()

        # Check auto-hide threshold
        if self.total_complaints >= COMPLAINTS_FOR_AUTO_HIDE and not self.is_auto_hidden:
            self.is_auto_hidden = True
            self.auto_hidden_at = datetime.utcnow()
            await self.save()
