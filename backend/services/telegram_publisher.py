"""
Service for publishing resumes and vacancies to Telegram channels.
"""

from typing import Optional
from datetime import datetime
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LinkPreviewOptions, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger

from config.settings import settings
from backend.models import Resume, Vacancy, Publication, PublicationType
from shared.constants import PositionCategory

# Translation maps for enum values
COMPANY_TYPE_NAMES = {
    "restaurant": "Ресторан",
    "cafe": "Кафе",
    "bar": "Бар",
    "pub": "Паб",
    "club": "Клуб",
    "coffee_shop": "Кофейня",
    "catering": "Общепит",
    "events": "Кейтеринг",
    "hotel": "Гостиница",
    "resort": "Отель",
    "bakery": "Пекарня",
    "confectionery": "Кондитерская",
}

EMPLOYMENT_TYPE_NAMES = {
    "full_time": "Полная занятость",
    "part_time": "Частичная занятость",
    "project": "Проектная работа",
    "internship": "Стажировка",
    "volunteer": "Волонтерство",
}

EXPERIENCE_LEVEL_NAMES = {
    "no_experience": "Не требуется",
    "1_year": "От 1 года",
    "3_years": "От 3 лет",
    "6_years": "Более 6 лет",
}

EDUCATION_LEVEL_NAMES = {
    "not_required": "Не имеет значения",
    "secondary": "Среднее",
    "vocational": "Среднее специальное",
    "higher": "Высшее",
}

SALARY_TYPE_NAMES = {
    "gross": "До вычета налогов",
    "net": "На руки",
    "monthly": "В месяц",
    "hourly": "В час",
    "daily": "В день",
}

WORK_SCHEDULE_NAMES = {
    "5/2": "5/2",
    "2/2": "2/2",
    "shift": "Сменный график",
    "flexible": "Гибкий график",
    "rotational": "Вахтовый метод",
    "night": "Ночные смены",
    "weekends": "Выходные дни",
}


def translate_value(value: str, mapping: dict) -> str:
    """Translate enum value using provided mapping."""
    if not value:
        return value
    return mapping.get(value, value)


class TelegramPublisher:
    """Service for publishing to Telegram channels."""

    def __init__(self):
        """Initialize Telegram bot."""
        self.bot = Bot(token=settings.bot_token)
        self._bot_username: Optional[str] = None  # Cache for bot username

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
        lines = []

        # Title
        lines.append(f"💼 <b>{vacancy.position}</b>\n")

        # Company
        if not vacancy.is_anonymous:
            company_type = translate_value(vacancy.company_type, COMPANY_TYPE_NAMES)
            lines.append(f"🏢 <b>Компания:</b> {vacancy.company_name} ({company_type})")

            if vacancy.company_description:
                desc = vacancy.company_description[:150]
                if len(vacancy.company_description) > 150:
                    desc += "..."
                lines.append(f"   {desc}")

            if vacancy.company_size:
                lines.append(f"👥 <b>Размер:</b> {vacancy.company_size}")

            if vacancy.company_website:
                lines.append(f"🌐 <b>Сайт:</b> {vacancy.company_website}")

        # Location
        lines.append(f"\n📍 <b>МЕСТОПОЛОЖЕНИЕ</b>")
        lines.append(f"Город: {vacancy.city}")
        if vacancy.address:
            lines.append(f"Адрес: {vacancy.address}")
        if vacancy.nearest_metro:
            lines.append(f"🚇 {vacancy.nearest_metro}")

        # Salary
        if vacancy.salary_min or vacancy.salary_max:
            lines.append(f"\n💰 <b>ЗАРПЛАТА</b>")
            salary_parts = []
            if vacancy.salary_min:
                salary_parts.append(f"от {vacancy.salary_min:,}")
            if vacancy.salary_max:
                salary_parts.append(f"до {vacancy.salary_max:,}")
            salary_str = " ".join(salary_parts) + " руб."
            salary_type_text = vacancy.salary_type.value if hasattr(vacancy.salary_type, 'value') else str(vacancy.salary_type)
            salary_type_translated = translate_value(salary_type_text, SALARY_TYPE_NAMES)
            lines.append(f"{salary_str} ({salary_type_translated})")

        # Employment
        if vacancy.employment_type:
            lines.append(f"\n⏰ <b>ЗАНЯТОСТЬ И ГРАФИК</b>")
            employment_type = translate_value(vacancy.employment_type, EMPLOYMENT_TYPE_NAMES)
            lines.append(f"Тип: {employment_type}")
            if vacancy.work_schedule:
                schedule_translated = [translate_value(s, WORK_SCHEDULE_NAMES) for s in vacancy.work_schedule]
                schedule = ", ".join(schedule_translated)
                lines.append(f"График: {schedule}")

        # Requirements
        lines.append(f"\n📋 <b>ТРЕБОВАНИЯ</b>")
        if vacancy.required_experience:
            experience = translate_value(vacancy.required_experience, EXPERIENCE_LEVEL_NAMES)
            lines.append(f"• Опыт: {experience}")
        if vacancy.required_education:
            education = translate_value(vacancy.required_education, EDUCATION_LEVEL_NAMES)
            lines.append(f"• Образование: {education}")
        if vacancy.required_skills:
            skills = ", ".join(vacancy.required_skills[:5])
            if len(vacancy.required_skills) > 5:
                skills += f" и ещё {len(vacancy.required_skills) - 5}"
            lines.append(f"• Навыки: {skills}")

        # Job conditions
        if vacancy.has_employment_contract or vacancy.probation_duration or vacancy.allows_remote_work:
            lines.append(f"\n📋 <b>УСЛОВИЯ РАБОТЫ</b>")
            if vacancy.has_employment_contract:
                lines.append("• Трудовой договор: Да")
            if vacancy.probation_duration:
                lines.append(f"• Испытательный срок: {vacancy.probation_duration}")
            if vacancy.allows_remote_work:
                lines.append("• Возможна удаленная работа")

        # Required documents
        if vacancy.required_documents:
            lines.append(f"\n📄 <b>ТРЕБУЕМЫЕ ДОКУМЕНТЫ</b>")
            for doc in vacancy.required_documents[:3]:
                lines.append(f"• {doc}")
            if len(vacancy.required_documents) > 3:
                lines.append(f"• ... и ещё {len(vacancy.required_documents) - 3}")

        # Benefits
        if vacancy.benefits:
            lines.append(f"\n✨ <b>МЫ ПРЕДЛАГАЕМ</b>")
            for benefit in vacancy.benefits[:5]:
                lines.append(f"• {benefit}")
            if len(vacancy.benefits) > 5:
                lines.append(f"• ... и ещё {len(vacancy.benefits) - 5}")

        # Description
        if vacancy.description:
            lines.append(f"\n📝 <b>ОПИСАНИЕ</b>")
            desc = vacancy.description[:200]
            if len(vacancy.description) > 200:
                desc += "..."
            lines.append(desc)

        # Responsibilities
        if vacancy.responsibilities:
            lines.append(f"\n📋 <b>ОБЯЗАННОСТИ</b>")
            for resp in vacancy.responsibilities[:5]:
                lines.append(f"• {resp}")
            if len(vacancy.responsibilities) > 5:
                lines.append(f"• ... и ещё {len(vacancy.responsibilities) - 5}")

        # Footer
        lines.append(f"\n📅 Опубликовано: {vacancy.created_at.strftime('%d.%m.%Y')}")

        return "\n".join(lines)

    def format_resume_message(self, resume: Resume) -> str:
        """Format resume as HTML message for Telegram."""
        lines = []

        # Title
        lines.append(f"👤 <b>{resume.desired_position}</b>\n")

        # Basic info
        lines.append(f"<b>ФИО:</b> {resume.full_name}")

        if resume.birth_date:
            from datetime import date
            today = date.today()
            # Handle both date object and string
            birth_date = resume.birth_date
            if isinstance(birth_date, str):
                from datetime import datetime
                birth_date = datetime.strptime(birth_date, "%Y-%m-%d").date()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            lines.append(f"🎂 <b>Возраст:</b> {age} лет")

        if resume.citizenship:
            lines.append(f"🌍 <b>Гражданство:</b> {resume.citizenship}")

        # Location
        lines.append(f"\n📍 <b>МЕСТОПОЛОЖЕНИЕ</b>")
        lines.append(f"Город: {resume.city}")
        if resume.ready_to_relocate:
            lines.append("✈️ Готов к переезду")

        # Contacts removed from channel publication for privacy
        # Contact info is only visible after employer clicks "Пригласить"

        # Desired position
        lines.append(f"\n💼 <b>ЖЕЛАЕМАЯ ДОЛЖНОСТЬ</b>")
        lines.append(f"Должность: {resume.desired_position}")

        if resume.cuisines:
            cuisines = ", ".join(resume.cuisines[:3])
            if len(resume.cuisines) > 3:
                cuisines += f" и ещё {len(resume.cuisines) - 3}"
            lines.append(f"Кухни: {cuisines}")

        # Salary and schedule
        if resume.desired_salary:
            salary_type_text = resume.salary_type.value if hasattr(resume.salary_type, 'value') else str(resume.salary_type)
            salary_type_translated = translate_value(salary_type_text, SALARY_TYPE_NAMES)
            lines.append(f"💰 <b>Зарплата:</b> {resume.desired_salary:,} руб. ({salary_type_translated})")

        if resume.work_schedule:
            schedule_translated = [translate_value(s, WORK_SCHEDULE_NAMES) for s in resume.work_schedule]
            schedule = ", ".join(schedule_translated)
            lines.append(f"⏰ <b>График:</b> {schedule}")

        # Experience
        if resume.total_experience_years or resume.work_experience:
            lines.append(f"\n💼 <b>ОПЫТ РАБОТЫ</b>")
            if resume.total_experience_years:
                lines.append(f"Общий опыт: {resume.total_experience_years} лет")

            # Show last 2 jobs
            if resume.work_experience:
                for i, exp in enumerate(resume.work_experience[:2], 1):
                    lines.append(f"\n<b>{i}. {exp.company}</b>")
                    lines.append(f"   Должность: {exp.position}")
                    if exp.start_date and exp.end_date:
                        lines.append(f"   Период: {exp.start_date} - {exp.end_date}")

                if len(resume.work_experience) > 2:
                    lines.append(f"\n   ... и ещё {len(resume.work_experience) - 2}")

        # Education
        if resume.education:
            lines.append(f"\n🎓 <b>ОБРАЗОВАНИЕ</b>")
            for edu in resume.education[:2]:
                edu_line = f"{edu.level}"
                if edu.institution:
                    edu_line += f" - {edu.institution}"
                lines.append(f"• {edu_line}")
            if len(resume.education) > 2:
                lines.append(f"• ... и ещё {len(resume.education) - 2}")

        # Skills
        if resume.skills:
            lines.append(f"\n🎯 <b>НАВЫКИ</b>")
            skills = ", ".join(resume.skills[:10])
            if len(resume.skills) > 10:
                skills += f" и ещё {len(resume.skills) - 10}"
            lines.append(skills)

        # Languages
        if resume.languages:
            lines.append(f"\n🗣 <b>ЯЗЫКИ</b>")
            for lang in resume.languages[:3]:
                lines.append(f"• {lang.language} - {lang.level}")
            if len(resume.languages) > 3:
                lines.append(f"• ... и ещё {len(resume.languages) - 3}")

        # Courses
        if resume.courses:
            lines.append(f"\n🎓 <b>КУРСЫ</b>")
            for course in resume.courses[:3]:
                course_line = course.name
                if course.organization:
                    course_line += f", {course.organization}"
                if course.completion_year:
                    course_line += f" ({course.completion_year})"
                lines.append(f"• {course_line}")
            if len(resume.courses) > 3:
                lines.append(f"• ... и ещё {len(resume.courses) - 3}")

        # About
        if resume.about:
            lines.append(f"\n📝 <b>О СЕБЕ</b>")
            about = resume.about[:200]
            if len(resume.about) > 200:
                about += "..."
            lines.append(about)

        # Footer
        lines.append(f"\n📅 Опубликовано: {resume.created_at.strftime('%d.%m.%Y')}")

        return "\n".join(lines)

    async def get_bot_username(self) -> str:
        """Get bot username from Telegram API (with caching)."""
        if self._bot_username is None:
            try:
                bot_info = await self.bot.get_me()
                self._bot_username = bot_info.username
                logger.info(f"Fetched bot username from Telegram API: @{self._bot_username}")
            except Exception as e:
                logger.error(f"Failed to fetch bot username: {e}")
                # Fallback to bot token ID
                self._bot_username = settings.bot_token.split(':')[0]
                logger.warning(f"Using bot token ID as fallback: {self._bot_username}")
        return self._bot_username

    async def get_callback_keyboard(self, entity_id: str, entity_type: str) -> InlineKeyboardMarkup:
        """Create keyboard with callback button."""
        builder = InlineKeyboardBuilder()

        # Get bot username from Telegram API
        bot_username = await self.get_bot_username()

        # Main action button
        builder.row(InlineKeyboardButton(
            text="📬 Откликнуться" if entity_type == "vacancy" else "💼 Пригласить",
            url=f"https://t.me/{bot_username}?start={entity_type}_{entity_id}"
        ))

        # Report button (smaller, secondary)
        builder.row(InlineKeyboardButton(
            text="🚨 Пожаловаться",
            url=f"https://t.me/{bot_username}?start=report_{entity_type}_{entity_id}"
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
            keyboard = await self.get_callback_keyboard(str(vacancy.id), "vacancy")

            # Send message
            message = await self.bot.send_message(
                chat_id=channel,
                text=message_text,
                parse_mode="HTML",
                reply_markup=keyboard,
                link_preview_options=LinkPreviewOptions(is_disabled=True)
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
            keyboard = await self.get_callback_keyboard(str(resume.id), "resume")

            # Send message with photos if available
            photo_ids = getattr(resume, 'photo_file_ids', None) or []
            if not photo_ids and resume.photo_file_id:
                photo_ids = [resume.photo_file_id]

            if len(photo_ids) > 1:
                # Multiple photos - send as media group (doesn't support inline keyboards)
                # Then send buttons as separate message
                media_group = []
                for i, photo_id in enumerate(photo_ids):
                    if i == 0:
                        # First photo gets the caption
                        media_group.append(InputMediaPhoto(
                            media=photo_id,
                            caption=message_text,
                            parse_mode="HTML"
                        ))
                    else:
                        media_group.append(InputMediaPhoto(media=photo_id))

                messages = await self.bot.send_media_group(
                    chat_id=channel,
                    media=media_group
                )
                message = messages[0]  # Use first message for publication record

                # Send keyboard as separate message (Telegram API limitation)
                await self.bot.send_message(
                    chat_id=channel,
                    text="👆 Резюме выше",
                    reply_markup=keyboard
                )
                logger.info(f"Published resume {resume.id} with {len(photo_ids)} photos to channel {channel}")

            elif len(photo_ids) == 1:
                # Single photo
                message = await self.bot.send_photo(
                    chat_id=channel,
                    photo=photo_ids[0],
                    caption=message_text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                    show_caption_above_media=True
                )
                logger.info(f"Published resume {resume.id} with photo to channel {channel}")
            else:
                # No photos
                message = await self.bot.send_message(
                    chat_id=channel,
                    text=message_text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                    link_preview_options=LinkPreviewOptions(is_disabled=True)
                )
                logger.info(f"Published resume {resume.id} without photo to channel {channel}")

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
