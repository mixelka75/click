"""
Moderation handlers - handles moderator actions from moderation group.
"""

from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from loguru import logger
from beanie import PydanticObjectId

from backend.models import (
    User, Vacancy, Resume,
    Complaint, ReporterBan, ComplaintStats
)
from backend.models.publication import Publication, PublicationType
from shared.constants import (
    ComplaintStatus, ModerationAction,
    ComplaintType, DISMISSED_COMPLAINTS_FOR_BAN
)
from config.settings import settings

router = Router()


async def update_moderation_message(
    bot: Bot,
    complaint: Complaint,
    action_text: str,
    moderator_name: str
):
    """Update the moderation message after action."""
    if not complaint.moderation_message_id or not complaint.moderation_chat_id:
        return

    try:
        await bot.edit_message_text(
            chat_id=complaint.moderation_chat_id,
            message_id=complaint.moderation_message_id,
            text=(
                f"✅ <b>ОБРАБОТАНО</b>\n\n"
                f"Действие: {action_text}\n"
                f"Модератор: {moderator_name}\n"
                f"Время: {datetime.utcnow().strftime('%d.%m.%Y %H:%M')}"
            ),
            reply_markup=None
        )
    except Exception as e:
        logger.warning(f"Failed to update moderation message: {e}")


async def notify_user(bot: Bot, user: User, message: str):
    """Send notification to user."""
    if not user or not user.telegram_id:
        return
    try:
        await bot.send_message(
            chat_id=user.telegram_id,
            text=message
        )
    except Exception as e:
        logger.warning(f"Failed to notify user {user.id}: {e}")


# ============================================================================
# MODERATION ACTIONS
# ============================================================================

@router.callback_query(F.data.startswith("mod_dismiss:"))
async def dismiss_complaint(callback: CallbackQuery, bot: Bot):
    """Dismiss the complaint (leave content as is)."""
    complaint_id = callback.data.split(":")[1]
    moderator_name = callback.from_user.full_name

    try:
        complaint = await Complaint.get(PydanticObjectId(complaint_id))
        if not complaint:
            await callback.answer("Жалоба не найдена", show_alert=True)
            return

        # Update complaint
        complaint.status = ComplaintStatus.DISMISSED
        complaint.moderation_action = ModerationAction.NONE
        complaint.moderator_id = PydanticObjectId(str(callback.from_user.id))
        complaint.moderated_at = datetime.utcnow()
        await complaint.save()

        # Update stats
        stats = await ComplaintStats.get_or_create(complaint.target_type, complaint.target_id)
        stats.pending_complaints = max(0, stats.pending_complaints - 1)
        stats.dismissed_complaints += 1
        await stats.save()

        # Check if reporter should be banned (too many dismissed complaints)
        reporter = await complaint.reporter.fetch()
        if reporter:
            dismissed_count = await Complaint.find(
                Complaint.reporter.id == reporter.id,
                Complaint.status == ComplaintStatus.DISMISSED
            ).count()

            if dismissed_count >= DISMISSED_COMPLAINTS_FOR_BAN:
                # Create ban for 7 days
                ban = ReporterBan(
                    user=reporter,
                    reason=f"Слишком много отклонённых жалоб ({dismissed_count})",
                    banned_until=datetime.utcnow() + timedelta(days=7)
                )
                await ban.insert()
                logger.info(f"Reporter {reporter.id} banned for 7 days due to dismissed complaints")

        await callback.answer("✅ Жалоба отклонена")
        await update_moderation_message(bot, complaint, "Оставить (жалоба отклонена)", moderator_name)

        logger.info(f"Complaint {complaint_id} dismissed by {moderator_name}")

    except Exception as e:
        logger.error(f"Error dismissing complaint: {e}")
        await callback.answer("Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("mod_delete:"))
async def delete_content(callback: CallbackQuery, bot: Bot):
    """Delete the reported content."""
    complaint_id = callback.data.split(":")[1]
    moderator_name = callback.from_user.full_name

    try:
        complaint = await Complaint.get(PydanticObjectId(complaint_id))
        if not complaint:
            await callback.answer("Жалоба не найдена", show_alert=True)
            return

        # Get content and author
        if complaint.target_type == ComplaintType.VACANCY:
            target = await Vacancy.get(complaint.target_id)
            content_type = "Вакансия"
        else:
            target = await Resume.get(complaint.target_id)
            content_type = "Резюме"

        if target:
            # Remove from channel if published
            publication = await Publication.find_one(
                {
                    "publication_type": (
                        PublicationType.VACANCY.value
                        if complaint.target_type == ComplaintType.VACANCY
                        else PublicationType.RESUME.value
                    ),
                    f"{complaint.target_type.value}.$id": target.id
                }
            )

            if publication and publication.message_id:
                try:
                    await bot.delete_message(
                        chat_id=publication.channel_id,
                        message_id=publication.message_id
                    )
                    publication.is_published = False
                    await publication.save()
                except Exception as e:
                    logger.warning(f"Failed to delete channel message: {e}")

            # Archive the content
            target.status = "archived"
            await target.save()

            # Notify author
            author = await complaint.target_author.fetch()
            if author:
                await notify_user(
                    bot, author,
                    f"⚠️ <b>Ваш контент удалён</b>\n\n"
                    f"{content_type} был удалён модератором по жалобе.\n"
                    f"Если вы считаете это ошибкой, обратитесь в поддержку."
                )

        # Update complaint
        complaint.status = ComplaintStatus.RESOLVED
        complaint.moderation_action = ModerationAction.DELETE
        complaint.moderator_id = PydanticObjectId(str(callback.from_user.id))
        complaint.moderated_at = datetime.utcnow()
        await complaint.save()

        # Update stats
        stats = await ComplaintStats.get_or_create(complaint.target_type, complaint.target_id)
        stats.pending_complaints = max(0, stats.pending_complaints - 1)
        stats.resolved_complaints += 1
        await stats.save()

        await callback.answer("🗑 Контент удалён")
        await update_moderation_message(bot, complaint, "Удалить объявление", moderator_name)

        logger.info(f"Content deleted for complaint {complaint_id} by {moderator_name}")

    except Exception as e:
        logger.error(f"Error deleting content: {e}")
        await callback.answer("Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("mod_warn:"))
async def warn_author(callback: CallbackQuery, bot: Bot):
    """Send warning to content author."""
    complaint_id = callback.data.split(":")[1]
    moderator_name = callback.from_user.full_name

    try:
        complaint = await Complaint.get(PydanticObjectId(complaint_id))
        if not complaint:
            await callback.answer("Жалоба не найдена", show_alert=True)
            return

        # Get author
        author = await complaint.target_author.fetch()

        if author:
            content_type = "вакансию" if complaint.target_type == ComplaintType.VACANCY else "резюме"
            await notify_user(
                bot, author,
                f"⚠️ <b>Предупреждение от модерации</b>\n\n"
                f"На вашу {content_type} поступила жалоба.\n"
                f"Пожалуйста, проверьте содержание и убедитесь, "
                f"что оно соответствует правилам платформы.\n\n"
                f"При повторных нарушениях ваш аккаунт может быть заблокирован."
            )

        # Update complaint
        complaint.status = ComplaintStatus.RESOLVED
        complaint.moderation_action = ModerationAction.WARNING
        complaint.moderator_id = PydanticObjectId(str(callback.from_user.id))
        complaint.moderated_at = datetime.utcnow()
        await complaint.save()

        # Update stats
        stats = await ComplaintStats.get_or_create(complaint.target_type, complaint.target_id)
        stats.pending_complaints = max(0, stats.pending_complaints - 1)
        stats.resolved_complaints += 1
        await stats.save()

        await callback.answer("⚠️ Предупреждение отправлено")
        await update_moderation_message(bot, complaint, "Предупреждение автору", moderator_name)

        logger.info(f"Warning sent for complaint {complaint_id} by {moderator_name}")

    except Exception as e:
        logger.error(f"Error sending warning: {e}")
        await callback.answer("Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("mod_ban:"))
async def ban_author(callback: CallbackQuery, bot: Bot):
    """Ban the content author."""
    complaint_id = callback.data.split(":")[1]
    moderator_name = callback.from_user.full_name

    try:
        complaint = await Complaint.get(PydanticObjectId(complaint_id))
        if not complaint:
            await callback.answer("Жалоба не найдена", show_alert=True)
            return

        # Get author
        author = await complaint.target_author.fetch()

        if author:
            # Deactivate user
            author.is_active = False
            await author.save()

            # Notify user
            await notify_user(
                bot, author,
                f"🚫 <b>Ваш аккаунт заблокирован</b>\n\n"
                f"Ваш аккаунт был заблокирован модератором за нарушение правил платформы.\n"
                f"Если вы считаете это ошибкой, обратитесь в поддержку."
            )

            # Archive all user's content
            if complaint.target_type == ComplaintType.VACANCY:
                await Vacancy.find({"user.$id": author.id}).update_many({"$set": {"status": "archived"}})
            else:
                await Resume.find({"user.$id": author.id}).update_many({"$set": {"status": "archived"}})

        # Update complaint
        complaint.status = ComplaintStatus.RESOLVED
        complaint.moderation_action = ModerationAction.BAN
        complaint.moderator_id = PydanticObjectId(str(callback.from_user.id))
        complaint.moderated_at = datetime.utcnow()
        await complaint.save()

        # Update stats
        stats = await ComplaintStats.get_or_create(complaint.target_type, complaint.target_id)
        stats.pending_complaints = max(0, stats.pending_complaints - 1)
        stats.resolved_complaints += 1
        await stats.save()

        await callback.answer("🚫 Автор заблокирован")
        await update_moderation_message(bot, complaint, "Заблокировать автора", moderator_name)

        logger.info(f"Author banned for complaint {complaint_id} by {moderator_name}")

    except Exception as e:
        logger.error(f"Error banning author: {e}")
        await callback.answer("Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("mod_ignore:"))
async def ignore_reporter(callback: CallbackQuery, bot: Bot):
    """Ignore future complaints from reporter."""
    parts = callback.data.split(":")
    complaint_id = parts[1]
    duration_hours = int(parts[2])  # -1 for permanent
    moderator_name = callback.from_user.full_name

    try:
        complaint = await Complaint.get(PydanticObjectId(complaint_id))
        if not complaint:
            await callback.answer("Жалоба не найдена", show_alert=True)
            return

        # Get reporter
        reporter = await complaint.reporter.fetch()

        if reporter:
            # Create ban record
            banned_until = None if duration_hours == -1 else datetime.utcnow() + timedelta(hours=duration_hours)

            ban = ReporterBan(
                user=reporter,
                reason="Игнорирование жалоб (решение модератора)",
                banned_until=banned_until
            )
            await ban.insert()

            duration_text = "навсегда" if duration_hours == -1 else f"на {duration_hours} час(ов)"
            logger.info(f"Reporter {reporter.id} ignored {duration_text} by {moderator_name}")

        # Update complaint
        complaint.status = ComplaintStatus.DISMISSED
        complaint.moderation_action = ModerationAction.IGNORE_REPORTER
        complaint.moderator_id = PydanticObjectId(str(callback.from_user.id))
        complaint.moderated_at = datetime.utcnow()
        await complaint.save()

        # Update stats
        stats = await ComplaintStats.get_or_create(complaint.target_type, complaint.target_id)
        stats.pending_complaints = max(0, stats.pending_complaints - 1)
        stats.dismissed_complaints += 1
        await stats.save()

        duration_text = "навсегда" if duration_hours == -1 else f"на {duration_hours}ч"
        await callback.answer(f"🔇 Жалобщик игнорируется {duration_text}")
        await update_moderation_message(bot, complaint, f"Игнорировать жалобщика {duration_text}", moderator_name)

    except Exception as e:
        logger.error(f"Error ignoring reporter: {e}")
        await callback.answer("Ошибка", show_alert=True)
