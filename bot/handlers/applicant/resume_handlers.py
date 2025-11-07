"""
Resume management handlers for applicants.
Includes resume listing, viewing, editing, statistics and archiving.
"""

from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
import httpx

from backend.models import User, Resume
from shared.constants import UserRole, ResumeStatus
from config.settings import settings
from bot.utils.formatters import format_salary_range, format_date
from bot.states.resume_states import ResumeCreationStates, ResumeEditStates
from bot.keyboards.common import get_cancel_keyboard


router = Router()


# ============ START RESUME CREATION ============

@router.message(F.text == "📝 Создать резюме")
async def start_resume_creation(message: Message, state: FSMContext):
    """Start resume creation process."""
    logger.warning(f"🔥 resume_handlers: '📝 Создать резюме' handler called")
    telegram_id = message.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user or user.role != UserRole.APPLICANT:
        await message.answer("Эта функция доступна только для соискателей.")
        return

    logger.info(f"User {telegram_id} started resume creation")

    await state.set_data({})

    welcome_text = (
        "📝 <b>Создание резюме</b>\n\n"
        "Отлично! Давайте создадим ваше резюме.\n"
        "Я буду задавать вам вопросы шаг за шагом.\n\n"
        "Вы можете в любой момент:\n"
        "• Использовать кнопку '🚫 Отменить создание' для отмены\n"
        "• Пропустить необязательные поля\n\n"
        "Начнём с основной информации.\n\n"
        "<b>Как вас зовут?</b> (ФИО полностью)"
    )

    await message.answer(welcome_text, reply_markup=get_cancel_keyboard())
    await state.set_state(ResumeCreationStates.full_name)
    logger.warning(f"🔥 resume_handlers set state to: {await state.get_state()}")


# ============ RESUME MANAGEMENT ============


def get_resume_status_emoji(status: str) -> str:
    """Get emoji for resume status."""
    status_map = {
        "published": "✅",
        "archived": "📦",
        "draft": "📝"
    }
    return status_map.get(status.lower(), "📝")


def format_resume_details(resume: Resume) -> str:
    """Format detailed resume information."""
    lines = []

    status = resume.status.value if hasattr(resume.status, 'value') else str(resume.status)
    status_emoji = get_resume_status_emoji(status)

    lines.append(f"📋 <b>ДЕТАЛИ РЕЗЮМЕ</b> {status_emoji}\n")

    # Personal info
    lines.append(f"👤 <b>ФИО:</b> {resume.full_name}")
    lines.append(f"📍 <b>Город:</b> {resume.city}")
    if resume.ready_to_relocate:
        lines.append("   ✈️ Готов к переезду")

    # Contacts
    lines.append(f"\n📞 <b>Контакты:</b>")
    if resume.phone:
        lines.append(f"   📱 {resume.phone}")
    if resume.email:
        lines.append(f"   📧 {resume.email}")

    # Desired position
    lines.append(f"\n💼 <b>ЖЕЛАЕМАЯ ДОЛЖНОСТЬ</b>")
    lines.append(f"   Должность: {resume.desired_position}")
    if resume.cuisines:
        lines.append(f"   Кухни: {', '.join(resume.cuisines[:3])}")
    if resume.desired_salary:
        salary_type = resume.salary_type.value if hasattr(resume.salary_type, 'value') else "На руки"
        lines.append(f"   💰 Зарплата: {resume.desired_salary:,} руб. ({salary_type})")

    # Work schedule
    if resume.work_schedule:
        lines.append(f"   ⏰ График: {', '.join(resume.work_schedule[:2])}")

    # Experience
    if resume.work_experience:
        lines.append(f"\n💼 <b>ОПЫТ РАБОТЫ</b> ({len(resume.work_experience)} записей)")
        for i, exp in enumerate(resume.work_experience[:2], 1):
            lines.append(f"\n   <b>{i}. {exp.company}</b>")
            lines.append(f"   {exp.position}")
            if exp.start_date and exp.end_date:
                lines.append(f"   {exp.start_date} - {exp.end_date}")

        if len(resume.work_experience) > 2:
            lines.append(f"\n   ... и ещё {len(resume.work_experience) - 2}")

    # Education
    if resume.education:
        lines.append(f"\n🎓 <b>ОБРАЗОВАНИЕ</b>")
        for edu in resume.education[:2]:
            lines.append(f"   • {edu.level} - {edu.institution}")

    # Skills
    if resume.skills:
        lines.append(f"\n🎯 <b>НАВЫКИ</b>")
        skills_text = ", ".join(resume.skills[:8])
        if len(resume.skills) > 8:
            skills_text += f" (+{len(resume.skills) - 8})"
        lines.append(f"   {skills_text}")

    # Languages
    if resume.languages:
        lines.append(f"\n🗣 <b>ЯЗЫКИ</b>")
        for lang in resume.languages[:3]:
            lines.append(f"   • {lang.language} - {lang.level}")

    # Analytics
    lines.append(f"\n📊 <b>Статистика:</b>")
    lines.append(f"   👁 Просмотров: {resume.views_count}")
    lines.append(f"   📬 Откликов: {resume.responses_count}")
    if resume.views_count > 0:
        conversion = (resume.responses_count / resume.views_count * 100)
        lines.append(f"   📈 Активность: {conversion:.1f}%")

    # Dates
    lines.append(f"\n📅 Создано: {format_date(resume.created_at)}")
    if resume.published_at:
        lines.append(f"📅 Опубликовано: {format_date(resume.published_at)}")

    return "\n".join(lines)


def get_resume_management_keyboard(resume_id: str, status: str) -> InlineKeyboardMarkup:
    """Get keyboard for resume management."""
    builder = InlineKeyboardBuilder()

    # First row: Statistics and Edit
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data=f"resume:stats:{resume_id}"),
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"resume:edit:{resume_id}")
    )

    # Second row: Archive/Restore
    if status == "published":
        builder.row(
            InlineKeyboardButton(text="🗄️ Архивировать", callback_data=f"resume:archive:{resume_id}")
        )
    elif status == "archived":
        builder.row(
            InlineKeyboardButton(text="♻️ Восстановить", callback_data=f"resume:restore:{resume_id}")
        )

    # Third row: Back
    builder.row(
        InlineKeyboardButton(text="🔙 Назад к списку", callback_data="resume:list")
    )

    return builder.as_markup()


@router.message(F.text == "📋 Мои резюме")
async def my_resumes(message: Message, state: FSMContext):
    """Show user's resumes with interactive buttons."""
    telegram_id = message.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        await message.answer("Пользователь не найден. Используйте /start")
        return

    try:
        resumes = await Resume.find({"user.$id": user.id}).to_list()

        if not resumes:
            await message.answer(
                "📋 <b>Мои резюме</b>\n\n"
                "У вас пока нет созданных резюме.\n"
                "Создайте первое резюме, чтобы начать поиск работы!"
            )
            return

        # Show resume list with inline buttons
        text = "📋 <b>Мои резюме</b>\n\n"
        text += "Выберите резюме для просмотра деталей:\n\n"

        builder = InlineKeyboardBuilder()

        for resume in resumes:
            status = resume.status.value if hasattr(resume.status, 'value') else str(resume.status)
            status_emoji = get_resume_status_emoji(status)

            # Create button text with emoji and extended info
            position = resume.desired_position or "Не указана должность"
            salary_str = f"{resume.desired_salary:,}₽" if resume.desired_salary else "не указана"
            button_text = f"{status_emoji} {position} | {salary_str} | {resume.city}"
            builder.row(
                InlineKeyboardButton(
                    text=button_text[:64],  # Limit button text length
                    callback_data=f"resume:view:{resume.id}"
                )
            )

        await message.answer(text, reply_markup=builder.as_markup())

        # Store resumes in state for quick access
        await state.update_data(my_resumes_ids=[str(r.id) for r in resumes])

    except Exception as e:
        logger.error(f"Error fetching resumes: {e}")
        await message.answer("Ошибка при загрузке резюме. Попробуйте позже.")


@router.callback_query(F.data.startswith("resume:view:"))
async def view_resume_details(callback: CallbackQuery, state: FSMContext):
    """Show detailed resume information."""
    await callback.answer()

    resume_id = callback.data.split(":")[-1]

    try:
        resume = await Resume.get(resume_id)

        if not resume:
            await callback.message.edit_text("❌ Резюме не найдено.")
            return

        # Format resume details
        text = format_resume_details(resume)
        status = resume.status.value if hasattr(resume.status, 'value') else str(resume.status)
        keyboard = get_resume_management_keyboard(resume_id, status)

        # If resume has photo, send photo with caption
        if resume.photo_file_id:
            # Delete the callback message
            await callback.message.delete()
            # Send new message with photo
            await callback.message.answer_photo(
                photo=resume.photo_file_id,
                caption=text,
                reply_markup=keyboard
            )
        else:
            # No photo, just edit the text
            await callback.message.edit_text(
                text,
                reply_markup=keyboard
            )

    except Exception as e:
        logger.error(f"Error viewing resume {resume_id}: {e}")
        await callback.message.edit_text("❌ Ошибка при загрузке резюме.")


@router.callback_query(F.data == "resume:list")
async def return_to_resume_list(callback: CallbackQuery, state: FSMContext):
    """Return to resume list."""
    await callback.answer()

    telegram_id = callback.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        await callback.message.edit_text("Пользователь не найден. Используйте /start")
        return

    try:
        resumes = await Resume.find({"user.$id": user.id}).to_list()

        if not resumes:
            await callback.message.edit_text(
                "📋 <b>Мои резюме</b>\n\n"
                "У вас пока нет созданных резюме."
            )
            return

        text = "📋 <b>Мои резюме</b>\n\n"
        text += "Выберите резюме для просмотра деталей:\n\n"

        builder = InlineKeyboardBuilder()

        for resume in resumes:
            status = resume.status.value if hasattr(resume.status, 'value') else str(resume.status)
            status_emoji = get_resume_status_emoji(status)

            position = resume.desired_position or "Не указана должность"
            salary_str = f"{resume.desired_salary:,}₽" if resume.desired_salary else "не указана"
            button_text = f"{status_emoji} {position} | {salary_str} | {resume.city}"
            builder.row(
                InlineKeyboardButton(
                    text=button_text[:64],
                    callback_data=f"resume:view:{resume.id}"
                )
            )

        await callback.message.edit_text(text, reply_markup=builder.as_markup())

    except Exception as e:
        logger.error(f"Error returning to resume list: {e}")
        await callback.message.edit_text("❌ Ошибка при загрузке списка резюме.")


@router.callback_query(F.data.startswith("resume:archive:"))
async def archive_resume(callback: CallbackQuery):
    """Archive a resume with confirmation."""
    resume_id = callback.data.split(":")[-1]

    # Show confirmation dialog
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, архивировать", callback_data=f"resume:archive_confirm:{resume_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"resume:view:{resume_id}")
    )

    await callback.message.edit_text(
        "🗄️ <b>Архивирование резюме</b>\n\n"
        "Вы уверены, что хотите архивировать это резюме?\n\n"
        "⚠️ Архивированное резюме будет скрыто из поиска, но вы сможете его восстановить позже.",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("resume:archive_confirm:"))
async def confirm_archive_resume(callback: CallbackQuery):
    """Confirm and archive resume."""
    await callback.answer("🗄️ Архивирую резюме...")

    resume_id = callback.data.split(":")[-1]

    try:
        # Call backend API to archive resume
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{settings.api_url}/resumes/{resume_id}/archive"
            )

            if response.status_code == 200:
                # Reload resume and update display
                resume = await Resume.get(resume_id)
                text = format_resume_details(resume)
                status = resume.status.value if hasattr(resume.status, 'value') else str(resume.status)

                await callback.message.edit_text(
                    text,
                    reply_markup=get_resume_management_keyboard(resume_id, status)
                )
                await callback.answer("✅ Резюме архивировано", show_alert=True)
            else:
                await callback.answer("❌ Ошибка при архивировании", show_alert=True)

    except Exception as e:
        logger.error(f"Error archiving resume {resume_id}: {e}")
        await callback.answer("❌ Ошибка при архивировании", show_alert=True)


@router.callback_query(F.data.startswith("resume:restore:"))
async def restore_resume(callback: CallbackQuery):
    """Restore an archived resume."""
    await callback.answer("♻️ Восстанавливаю резюме...")

    resume_id = callback.data.split(":")[-1]

    try:
        # Call backend API to restore resume (publish it again)
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{settings.api_url}/resumes/{resume_id}/publish"
            )

            if response.status_code == 200:
                # Reload resume and update display
                resume = await Resume.get(resume_id)
                text = format_resume_details(resume)
                status = resume.status.value if hasattr(resume.status, 'value') else str(resume.status)

                await callback.message.edit_text(
                    text,
                    reply_markup=get_resume_management_keyboard(resume_id, status)
                )
                await callback.answer("✅ Резюме восстановлено", show_alert=True)
            else:
                await callback.answer("❌ Ошибка при восстановлении", show_alert=True)

    except Exception as e:
        logger.error(f"Error restoring resume {resume_id}: {e}")
        await callback.answer("❌ Ошибка при восстановлении", show_alert=True)


@router.message(F.text == "📬 Мои отклики")
async def my_responses(message: Message):
    """Show user's responses to vacancies."""
    telegram_id = message.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        await message.answer("Пользователь не найден. Используйте /start")
        return

    try:
        from backend.models import Response, Vacancy

        responses = await Response.find(
            Response.applicant.id == user.id
        ).to_list()

        if not responses:
            await message.answer(
                "📬 <b>Мои отклики</b>\n\n"
                "У вас пока нет откликов на вакансии.\n"
                "Найдите интересные вакансии и откликнитесь!"
            )
            return

        # Show responses
        text = "📬 <b>Мои отклики</b>\n\n"
        for i, resp in enumerate(responses[:10], 1):  # Show first 10
            # Get vacancy
            vacancy = await Vacancy.get(resp.vacancy_id)

            status = resp.status.value if hasattr(resp.status, 'value') else str(resp.status)
            status_emoji = {
                "pending": "⏳",
                "viewed": "👀",
                "invited": "✅",
                "accepted": "🎉",
                "rejected": "❌"
            }.get(status, "📝")

            text += (
                f"{status_emoji} <b>{i}. {vacancy.position if vacancy else 'Вакансия'}</b>\n"
                f"   Компания: {vacancy.company_name if vacancy else '-'}\n"
                f"   Статус: {status}\n\n"
            )

        if len(responses) > 10:
            text += f"\n... и ещё {len(responses) - 10}"

        await message.answer(text)

    except Exception as e:
        logger.error(f"Error fetching responses: {e}")
        await message.answer("Ошибка при загрузке откликов. Попробуйте позже.")


# ============================================================================
# RESUME EDITING
# ============================================================================

@router.callback_query(F.data.startswith("resume:edit:"))
async def start_resume_edit(callback: CallbackQuery, state: FSMContext):
    """Start resume editing - show field selection menu."""
    await callback.answer()

    resume_id = callback.data.split(":")[-1]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.api_url}/resumes/{resume_id}"
            )

            if response.status_code != 200:
                await callback.message.answer("❌ Резюме не найдено")
                return

            resume = response.json()

            # Save resume to state
            await state.update_data(editing_resume_id=resume_id, resume_data=resume)

            # Show field selection menu
            text = (
                "✏️ <b>Редактирование резюме</b>\n\n"
                "Выберите поле для редактирования:"
            )

            builder = InlineKeyboardBuilder()

            # Basic fields
            builder.row(
                InlineKeyboardButton(text="💰 Желаемая зарплата", callback_data=f"edit_resume_field:salary:{resume_id}"),
            )
            builder.row(
                InlineKeyboardButton(text="📍 Город", callback_data=f"edit_resume_field:city:{resume_id}"),
                InlineKeyboardButton(text="💼 Должность", callback_data=f"edit_resume_field:position:{resume_id}")
            )
            builder.row(
                InlineKeyboardButton(text="🎯 Навыки", callback_data=f"edit_resume_field:skills:{resume_id}"),
                InlineKeyboardButton(text="📞 Телефон", callback_data=f"edit_resume_field:phone:{resume_id}")
            )
            builder.row(
                InlineKeyboardButton(text="✉️ Email", callback_data=f"edit_resume_field:email:{resume_id}"),
                InlineKeyboardButton(text="📝 О себе", callback_data=f"edit_resume_field:about:{resume_id}")
            )
            builder.row(
                InlineKeyboardButton(text="📸 Фото", callback_data=f"edit_resume_field:photo:{resume_id}")
            )
            builder.row(
                InlineKeyboardButton(text="🔙 Отмена", callback_data=f"resume:view:{resume_id}")
            )

            await callback.message.edit_text(text, reply_markup=builder.as_markup())
            await state.set_state(ResumeEditStates.select_field)

    except Exception as e:
        logger.error(f"Error starting resume edit: {e}")
        await callback.message.answer("❌ Ошибка при загрузке резюме")


@router.callback_query(ResumeEditStates.select_field, F.data.startswith("edit_resume_field:"))
async def select_resume_field(callback: CallbackQuery, state: FSMContext):
    """Handle field selection for editing."""
    await callback.answer()

    parts = callback.data.split(":")
    field = parts[1]
    resume_id = parts[2]

    await state.update_data(editing_field=field)

    # Show input prompt based on field type
    prompts = {
        "salary": "💰 <b>Желаемая зарплата</b>\n\nВведите желаемую зарплату (только число):\nПример: 50000",
        "city": "📍 <b>Город</b>\n\nВведите город:",
        "position": "💼 <b>Должность</b>\n\nВведите желаемую должность:",
        "skills": "🎯 <b>Навыки</b>\n\nВведите навыки через запятую:\nПример: Работа с кассой, Знание меню, Сервис",
        "phone": "📞 <b>Телефон</b>\n\nВведите номер телефона:\nПример: +7 900 123-45-67",
        "email": "✉️ <b>Email</b>\n\nВведите email:",
        "about": "📝 <b>О себе</b>\n\nНапишите информацию о себе:",
        "photo": "📸 <b>Фото</b>\n\nОтправьте новое фото для резюме:"
    }

    prompt = prompts.get(field, "Введите новое значение:")

    await callback.message.edit_text(prompt)
    await state.set_state(ResumeEditStates.edit_value)


@router.message(ResumeEditStates.edit_value, F.photo)
async def process_resume_photo_edit(message: Message, state: FSMContext):
    """Process photo upload in edit mode."""
    data = await state.get_data()
    resume_id = data.get("editing_resume_id")
    field = data.get("editing_field")

    if not resume_id or field != "photo":
        await message.answer("❌ Ошибка: данные редактирования потеряны")
        await state.clear()
        return

    # Get the largest photo
    photo = message.photo[-1]
    update_data = {"photo_file_id": photo.file_id}

    try:
        # Update via API
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.patch(
                f"{settings.api_url}/resumes/{resume_id}",
                json=update_data
            )

            if response.status_code == 200:
                await message.answer(
                    "✅ Фото успешно обновлено!",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="👀 Посмотреть резюме", callback_data=f"resume:view:{resume_id}")
                    ]])
                )
                logger.info(f"Resume {resume_id} photo updated")
            else:
                error_detail = response.json().get("detail", "Unknown error")
                await message.answer(f"❌ Ошибка обновления: {error_detail}")

    except Exception as e:
        logger.error(f"Error updating resume photo: {e}")
        await message.answer("❌ Произошла ошибка при обновлении фото")

    await state.clear()


@router.message(ResumeEditStates.edit_value)
async def process_resume_field_edit(message: Message, state: FSMContext):
    """Process the new field value from user."""
    data = await state.get_data()
    resume_id = data.get("editing_resume_id")
    field = data.get("editing_field")

    # Check if user is trying to edit photo with text
    if field == "photo":
        await message.answer("❌ Пожалуйста, отправьте фотографию, а не текст")
        return

    new_value = message.text.strip()

    if not resume_id or not field:
        await message.answer("❌ Ошибка: данные редактирования потеряны")
        await state.clear()
        return

    # Validate and prepare data
    update_data = {}

    try:
        if field == "salary":
            # Extract number
            import re
            numbers = re.findall(r'\d+', new_value.replace(',', '').replace(' ', ''))
            if numbers:
                update_data["desired_salary"] = int(numbers[0])
            else:
                await message.answer("❌ Некорректная зарплата. Попробуйте еще раз:")
                return

        elif field == "city":
            update_data["city"] = new_value

        elif field == "position":
            update_data["desired_position"] = new_value

        elif field == "skills":
            skills = [s.strip() for s in new_value.split(",") if s.strip()]
            update_data["skills"] = skills

        elif field == "phone":
            update_data["phone"] = new_value

        elif field == "email":
            # Basic email validation
            if "@" not in new_value or "." not in new_value:
                await message.answer("❌ Некорректный email. Попробуйте еще раз:")
                return
            update_data["email"] = new_value

        elif field == "about":
            update_data["about"] = new_value

        # Update via API
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.patch(
                f"{settings.api_url}/resumes/{resume_id}",
                json=update_data
            )

            if response.status_code == 200:
                await message.answer(
                    "✅ Резюме успешно обновлено!",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="👀 Посмотреть резюме", callback_data=f"resume:view:{resume_id}")
                    ]])
                )
                logger.info(f"Resume {resume_id} field '{field}' updated")
            else:
                error_detail = response.json().get("detail", "Unknown error")
                await message.answer(f"❌ Ошибка обновления: {error_detail}")

    except Exception as e:
        logger.error(f"Error updating resume field: {e}")
        await message.answer("❌ Произошла ошибка при обновлении резюме")

    await state.clear()


@router.callback_query(F.data.startswith("resume:stats:"))
async def show_resume_statistics(callback: CallbackQuery):
    """Show detailed resume statistics."""
    await callback.answer()

    resume_id = callback.data.split(":")[-1]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Get resume
            resume_response = await client.get(
                f"{settings.api_url}/resumes/{resume_id}"
            )

            if resume_response.status_code != 200:
                await callback.message.answer("❌ Резюме не найдено")
                return

            resume = resume_response.json()

            # Get analytics
            analytics_response = await client.get(
                f"{settings.api_url}/analytics/resume/{resume_id}"
            )

            if analytics_response.status_code == 200:
                analytics = analytics_response.json()
            else:
                analytics = {}

            # Format statistics
            text = format_resume_statistics(resume, analytics)

            # Add back button
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="🔙 Назад к резюме", callback_data=f"resume:view:{resume_id}")
            )

            await callback.message.edit_text(text, reply_markup=builder.as_markup())

    except httpx.TimeoutException:
        await callback.message.answer("⏱ Превышено время ожидания. Попробуйте позже.")
    except Exception as e:
        logger.error(f"Error fetching resume statistics: {e}")
        await callback.message.answer("❌ Ошибка при загрузке статистики")


def format_resume_statistics(resume: dict, analytics: dict) -> str:
    """Format detailed resume statistics."""
    text = [
        "📊 <b>СТАТИСТИКА РЕЗЮМЕ</b>\n",
        f"💼 <b>{resume.get('desired_position', 'Не указано')}</b>",
        f"👤 {resume.get('full_name', 'Не указано')}\n"
    ]

    # Basic stats
    views = analytics.get('views_count', resume.get('views_count', 0))
    responses = analytics.get('responses_count', resume.get('responses_count', 0))

    text.append("<b>📈 ОСНОВНЫЕ ПОКАЗАТЕЛИ</b>")
    text.append(f"👁 Просмотры: {views}")
    text.append(f"📬 Приглашения: {responses}")

    # Conversion rate
    if views > 0:
        conversion = (responses / views) * 100
        text.append(f"📊 Конверсия: {conversion:.1f}%")

    text.append("")

    # Response breakdown
    if analytics.get('response_breakdown'):
        text.append("<b>📬 СТАТУС ПРИГЛАШЕНИЙ</b>")
        breakdown = analytics['response_breakdown']
        for status, count in breakdown.items():
            status_emoji = {
                "pending": "⏳",
                "viewed": "👀",
                "invited": "✅",
                "accepted": "🎉",
                "rejected": "❌"
            }.get(status, "📝")
            text.append(f"{status_emoji} {status}: {count}")
        text.append("")

    # Time metrics
    if resume.get('published_at'):
        from datetime import datetime
        pub_date = resume.get('published_at')
        if isinstance(pub_date, str):
            pub_date = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
        days_active = (datetime.utcnow() - pub_date.replace(tzinfo=None)).days
        text.append(f"📅 Опубликовано: {days_active} дней назад")

    # Performance insights
    text.append("\n<b>💡 РЕКОМЕНДАЦИИ</b>")
    if views < 10:
        text.append("• Обновите навыки для лучшей видимости")
        text.append("• Добавьте больше деталей об опыте")
    elif views >= 10 and responses == 0:
        text.append("• Уточните желаемую должность")
        text.append("• Проверьте контактные данные")
    elif conversion < 5:
        text.append("• Улучшите описание навыков")
        text.append("• Добавьте портфолио или сертификаты")
    else:
        text.append("✅ Резюме работает хорошо!")

    return "\n".join(text)
