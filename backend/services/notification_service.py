"""
Notification service for sending Telegram notifications to users.
"""

import asyncio
from typing import Optional
from loguru import logger
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from config.settings import settings
from backend.models import User, Vacancy, Resume, Response


class NotificationService:
    """Service for sending notifications to users via Telegram."""

    def __init__(self):
        """Initialize notification service."""
        self.bot: Optional[Bot] = None

    def initialize(self, bot: Bot):
        """Initialize with bot instance."""
        self.bot = bot

    async def send_notification(self, user: User, message: str):
        """Send notification to user."""
        if not self.bot:
            logger.warning("Notification service not initialized with bot")
            return False

        try:
            await self.bot.send_message(
                chat_id=user.telegram_id,
                text=message,
                parse_mode="HTML"
            )
            logger.info(f"Notification sent to user {user.telegram_id}")
            return True

        except TelegramForbiddenError:
            logger.warning(f"User {user.telegram_id} blocked the bot")
            return False

        except TelegramBadRequest as e:
            logger.error(f"Bad request sending notification to {user.telegram_id}: {e}")
            return False

        except Exception as e:
            logger.error(f"Error sending notification to {user.telegram_id}: {e}")
            return False

    async def notify_new_response(self, response: Response):
        """Notify employer about new response to their vacancy."""
        try:
            # Fetch related data
            await response.fetch_all_links()

            if not response.vacancy or not response.vacancy.user:
                logger.error("Cannot send notification: vacancy or employer not found")
                return False

            employer = response.vacancy.user
            resume = response.resume
            vacancy = response.vacancy

            message = (
                "🔔 <b>Новый отклик на вашу вакансию!</b>\n\n"
                f"💼 <b>Вакансия:</b> {vacancy.position}\n"
                f"📍 {vacancy.city}\n\n"
                f"👤 <b>Кандидат:</b> {resume.full_name if resume else 'Неизвестно'}\n"
                f"💼 Желаемая должность: {resume.desired_position if resume else '-'}\n"
            )

            if response.cover_letter:
                message += f"\n✉️ <b>Сопроводительное письмо:</b>\n{response.cover_letter[:200]}"
                if len(response.cover_letter) > 200:
                    message += "..."

            message += "\n\n📋 Посмотреть все отклики: /menu → 'Отклики на мои вакансии'"

            return await self.send_notification(employer, message)

        except Exception as e:
            logger.error(f"Error notifying about new response: {e}")
            return False

    async def notify_new_invitation(self, response: Response):
        """Notify applicant about invitation from employer."""
        try:
            # Fetch related data
            await response.fetch_all_links()

            if not response.resume or not response.resume.user:
                logger.error("Cannot send notification: resume or applicant not found")
                return False

            applicant = response.resume.user
            vacancy = response.vacancy
            employer_user = vacancy.user if vacancy else None

            message = (
                "🔔 <b>Вас пригласили на вакансию!</b>\n\n"
                f"💼 <b>Вакансия:</b> {vacancy.position if vacancy else 'Неизвестно'}\n"
            )

            if vacancy and not vacancy.is_anonymous:
                message += f"🏢 <b>Компания:</b> {vacancy.company_name}\n"

            if vacancy:
                message += f"📍 {vacancy.city}\n"

                if vacancy.salary_min or vacancy.salary_max:
                    salary_parts = []
                    if vacancy.salary_min:
                        salary_parts.append(f"от {vacancy.salary_min:,}")
                    if vacancy.salary_max:
                        salary_parts.append(f"до {vacancy.salary_max:,}")
                    message += f"💰 {' '.join(salary_parts)} ₽\n"

            if response.invitation_message:
                message += f"\n✉️ <b>Сообщение от работодателя:</b>\n{response.invitation_message[:200]}"
                if len(response.invitation_message) > 200:
                    message += "..."

            message += "\n\n📋 Посмотреть все приглашения: /menu → 'Мои отклики'"

            return await self.send_notification(applicant, message)

        except Exception as e:
            logger.error(f"Error notifying about invitation: {e}")
            return False

    async def notify_response_status_changed(self, response: Response, old_status: str):
        """Notify applicant when response status changes."""
        try:
            await response.fetch_all_links()

            if not response.resume or not response.resume.user:
                logger.error("Cannot send notification: resume or applicant not found")
                return False

            applicant = response.resume.user
            vacancy = response.vacancy
            new_status = response.status

            # Status messages
            status_messages = {
                "viewed": "👀 <b>Ваш отклик просмотрен</b>",
                "invited": "✅ <b>Вас приглашают на собеседование!</b>",
                "accepted": "🎉 <b>Ваш отклик принят!</b>",
                "rejected": "❌ <b>Отклик отклонен</b>"
            }

            if new_status not in status_messages:
                return False

            message = status_messages[new_status] + "\n\n"
            message += f"💼 <b>Вакансия:</b> {vacancy.position if vacancy else 'Неизвестно'}\n"

            if vacancy and not vacancy.is_anonymous:
                message += f"🏢 Компания: {vacancy.company_name}\n"

            if vacancy:
                message += f"📍 {vacancy.city}\n"

            if new_status == "invited":
                message += "\n🎯 Работодатель заинтересован в вашей кандидатуре!"
            elif new_status == "accepted":
                message += "\n🎯 Поздравляем! Свяжитесь с работодателем для уточнения деталей."
            elif new_status == "rejected":
                message += "\n💪 Не расстраивайтесь! Продолжайте поиск."

            message += "\n\n📋 Подробнее: /menu → 'Мои отклики'"

            return await self.send_notification(applicant, message)

        except Exception as e:
            logger.error(f"Error notifying about status change: {e}")
            return False

    async def notify_resume_published(self, resume: Resume):
        """Notify user that their resume was published."""
        try:
            if not resume.user:
                logger.error("Cannot send notification: user not found")
                return False

            message = (
                "✅ <b>Резюме успешно опубликовано!</b>\n\n"
                f"💼 {resume.desired_position}\n"
                f"📍 {resume.city}\n\n"
                "Ваше резюме размещено в Telegram каналах и доступно работодателям.\n\n"
                "🔍 Рекомендуем также активно искать вакансии:\n"
                "/menu → 'Найти вакансию'"
            )

            return await self.send_notification(resume.user, message)

        except Exception as e:
            logger.error(f"Error notifying about resume publication: {e}")
            return False

    async def notify_vacancy_published(self, vacancy: Vacancy):
        """Notify employer that their vacancy was published."""
        try:
            if not vacancy.user:
                logger.error("Cannot send notification: user not found")
                return False

            message = (
                "✅ <b>Вакансия успешно опубликована!</b>\n\n"
                f"💼 {vacancy.position}\n"
                f"🏢 {vacancy.company_name}\n"
                f"📍 {vacancy.city}\n\n"
                "Ваша вакансия размещена в Telegram каналах и доступна соискателям.\n\n"
                "🔍 Рекомендуем также активно искать кандидатов:\n"
                "/menu → 'Найти резюме'"
            )

            return await self.send_notification(vacancy.user, message)

        except Exception as e:
            logger.error(f"Error notifying about vacancy publication: {e}")
            return False


# Global instance
notification_service = NotificationService()
