"""
Service for publishing resumes and vacancies to Telegram channels.
"""

from typing import Optional
from datetime import datetime
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger

from config.settings import settings
from backend.models import Resume, Vacancy, Publication, PublicationType
from shared.constants import PositionCategory


class TelegramPublisher:
    """Service for publishing to Telegram channels."""

    def __init__(self):
        """Initialize Telegram bot."""
        self.bot = Bot(token=settings.bot_token)

    def get_channel_for_position(self, position_category: str, is_vacancy: bool = True) -> str:
        """Get appropriate channel based on position category."""
        if is_vacancy:
            channel_map = {
                PositionCategory.BARMAN: settings.channel_vacancies_barmen,
                PositionCategory.WAITER: settings.channel_vacancies_waiters,
                PositionCategory.COOK: settings.channel_vacancies_cooks,
                PositionCategory.BARISTA: settings.channel_vacancies_barista,
                PositionCategory.MANAGEMENT: settings.channel_vacancies_admin,
                PositionCategory.SUPPORT: settings.channel_vacancies_support,
            }
            default_channel = settings.channel_vacancies_general
        else:
            # For resumes, use separate channels for employers
            channel_map = {
                PositionCategory.BARMAN: settings.channel_resumes_barmen,
                PositionCategory.WAITER: settings.channel_resumes_waiters,
                PositionCategory.COOK: settings.channel_resumes_cooks,
                PositionCategory.BARISTA: settings.channel_resumes_barista,
                PositionCategory.MANAGEMENT: settings.channel_resumes_admin,
                PositionCategory.SUPPORT: settings.channel_resumes_support,
            }
            default_channel = settings.channel_resumes_general

        return channel_map.get(position_category, default_channel)

    def format_vacancy_message(self, vacancy: Vacancy) -> str:
        """Format vacancy as HTML message for Telegram."""
        # Build message parts
        parts = []

        # Title
        parts.append(f"🍴 <b>Вакансия: {vacancy.position}</b>\n")

        # Company
        if not vacancy.is_anonymous:
            parts.append(f"🏢 <b>Компания:</b> {vacancy.company_name} ({vacancy.company_type})")

        # Location
        parts.append(f"📍 <b>Место работы:</b> {vacancy.city}")
        if vacancy.nearest_metro:
            parts.append(f"🚇 {vacancy.nearest_metro}")

        # Salary
        if vacancy.salary_min or vacancy.salary_max:
            salary_parts = []
            if vacancy.salary_min:
                salary_parts.append(f"от {vacancy.salary_min:,}")
            if vacancy.salary_max:
                salary_parts.append(f"до {vacancy.salary_max:,}")
            salary_str = " ".join(salary_parts) + " руб."
            parts.append(f"💰 <b>Зарплата:</b> {salary_str} ({vacancy.salary_type})")

        # Schedule
        if vacancy.work_schedule:
            parts.append(f"⏰ <b>График:</b> {', '.join(vacancy.work_schedule)}")

        # Requirements
        parts.append(f"\n<b>Требования:</b>")
        parts.append(f"• Опыт: {vacancy.required_experience}")
        parts.append(f"• Образование: {vacancy.required_education}")

        if vacancy.required_skills:
            skills_str = ", ".join(vacancy.required_skills[:5])  # Limit to 5 skills
            if len(vacancy.required_skills) > 5:
                skills_str += f" и ещё {len(vacancy.required_skills) - 5}"
            parts.append(f"• Навыки: {skills_str}")

        # Benefits
        if vacancy.benefits:
            benefits_str = ", ".join(vacancy.benefits[:3])
            if len(vacancy.benefits) > 3:
                benefits_str += f" и ещё {len(vacancy.benefits) - 3}"
            parts.append(f"\n✨ <b>Условия:</b> {benefits_str}")

        # Description (truncated)
        if vacancy.description:
            desc = vacancy.description[:200]
            if len(vacancy.description) > 200:
                desc += "..."
            parts.append(f"\n{desc}")

        # Footer
        parts.append(f"\n📅 Опубликовано: {vacancy.created_at.strftime('%d.%m.%Y')}")
        parts.append(f"📊 Просмотров: {vacancy.views_count}")

        return "\n".join(parts)

    def format_resume_message(self, resume: Resume) -> str:
        """Format resume as HTML message for Telegram."""
        parts = []

        # Title
        parts.append(f"👤 <b>Резюме: {resume.desired_position}</b>\n")

        # Basic info
        parts.append(f"📝 <b>ФИО:</b> {resume.full_name}")
        parts.append(f"📍 <b>Город:</b> {resume.city}")
        if resume.ready_to_relocate:
            parts.append("✈️ Готов к переезду")

        # Salary
        if resume.desired_salary:
            parts.append(f"💰 <b>Желаемая зарплата:</b> {resume.desired_salary:,} руб. ({resume.salary_type})")

        # Schedule
        if resume.work_schedule:
            parts.append(f"⏰ <b>График:</b> {', '.join(resume.work_schedule)}")

        # Experience
        if resume.total_experience_years:
            parts.append(f"💼 <b>Опыт работы:</b> {resume.total_experience_years} лет")

        # Last work experience
        if resume.work_experience and len(resume.work_experience) > 0:
            last_job = resume.work_experience[0]
            parts.append(f"\n<b>Последнее место работы:</b>")
            parts.append(f"• {last_job.company} - {last_job.position}")

        # Skills
        if resume.skills:
            skills_str = ", ".join(resume.skills[:5])
            if len(resume.skills) > 5:
                skills_str += f" и ещё {len(resume.skills) - 5}"
            parts.append(f"\n🎯 <b>Навыки:</b> {skills_str}")

        # About (truncated)
        if resume.about:
            about = resume.about[:200]
            if len(resume.about) > 200:
                about += "..."
            parts.append(f"\n{about}")

        # Footer
        parts.append(f"\n📅 Опубликовано: {resume.created_at.strftime('%d.%m.%Y')}")

        return "\n".join(parts)

    def get_callback_keyboard(self, entity_id: str, entity_type: str) -> InlineKeyboardMarkup:
        """Create keyboard with callback button."""
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="📬 Откликнуться" if entity_type == "vacancy" else "💼 Пригласить",
            url=f"https://t.me/{settings.bot_token.split(':')[0]}?start={entity_type}_{entity_id}"
        ))
        return builder.as_markup()

    async def publish_vacancy(self, vacancy: Vacancy) -> Optional[Publication]:
        """Publish vacancy to appropriate Telegram channel."""
        try:
            # Get channel
            channel = self.get_channel_for_position(vacancy.position_category, is_vacancy=True)

            # Format message
            message_text = self.format_vacancy_message(vacancy)

            # Create keyboard
            keyboard = self.get_callback_keyboard(str(vacancy.id), "vacancy")

            # Send message
            message = await self.bot.send_message(
                chat_id=channel,
                text=message_text,
                parse_mode="HTML",
                reply_markup=keyboard
            )

            # Create publication record
            publication = Publication(
                publication_type=PublicationType.VACANCY,
                vacancy=vacancy,
                channel_id=channel,
                channel_name=channel,
                message_id=message.message_id,
                message_text=message_text,
                is_published=True,
                published_at=datetime.utcnow()
            )
            await publication.insert()

            logger.info(f"Published vacancy {vacancy.id} to channel {channel}")
            return publication

        except Exception as e:
            logger.error(f"Failed to publish vacancy {vacancy.id}: {e}")
            # Create failed publication record
            publication = Publication(
                publication_type=PublicationType.VACANCY,
                vacancy=vacancy,
                channel_id=channel,
                channel_name=channel,
                message_text=message_text,
                is_published=False,
                error_message=str(e)
            )
            await publication.insert()
            return None

    async def publish_resume(self, resume: Resume) -> Optional[Publication]:
        """Publish resume to appropriate Telegram channel."""
        try:
            # Get channel (for employers)
            channel = self.get_channel_for_position(resume.position_category, is_vacancy=False)

            # Format message
            message_text = self.format_resume_message(resume)

            # Create keyboard
            keyboard = self.get_callback_keyboard(str(resume.id), "resume")

            # Send message
            message = await self.bot.send_message(
                chat_id=channel,
                text=message_text,
                parse_mode="HTML",
                reply_markup=keyboard
            )

            # Create publication record
            publication = Publication(
                publication_type=PublicationType.RESUME,
                resume=resume,
                channel_id=channel,
                channel_name=channel,
                message_id=message.message_id,
                message_text=message_text,
                is_published=True,
                published_at=datetime.utcnow()
            )
            await publication.insert()

            logger.info(f"Published resume {resume.id} to channel {channel}")
            return publication

        except Exception as e:
            logger.error(f"Failed to publish resume {resume.id}: {e}")
            publication = Publication(
                publication_type=PublicationType.RESUME,
                resume=resume,
                channel_id=channel,
                channel_name=channel,
                message_text=message_text,
                is_published=False,
                error_message=str(e)
            )
            await publication.insert()
            return None

    async def delete_publication(self, publication: Publication) -> bool:
        """Delete publication from channel."""
        try:
            if publication.message_id:
                await self.bot.delete_message(
                    chat_id=publication.channel_id,
                    message_id=publication.message_id
                )
                publication.is_deleted = True
                publication.deleted_at = datetime.utcnow()
                await publication.save()
                logger.info(f"Deleted publication {publication.id}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete publication {publication.id}: {e}")
            return False


# Global instance
telegram_publisher = TelegramPublisher()
